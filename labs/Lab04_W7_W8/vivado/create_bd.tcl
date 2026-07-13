# Lab04 block design: Zynq PS <-> AXI DMA <-> AXI4-Stream accelerator.
# This file is sourced by create_project.tcl after the RTL has been added.

if {[llength [get_projects -quiet]] == 0} {
    error "Open or create a Vivado project before sourcing create_bd.tcl."
}

set bd_name lab04_bd
if {[llength [get_bd_designs -quiet $bd_name]] != 0} {
    error "Block Design '$bd_name' already exists. Re-run vivado/create_project.tcl to rebuild cleanly."
}

create_bd_design $bd_name
current_bd_design $bd_name

# -----------------------------------------------------------------------------
# Processing System and board preset
# -----------------------------------------------------------------------------
set ps7 [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:* processing_system7_0]
set board_part [get_property BOARD_PART [current_project]]

if {$board_part ne ""} {
    apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
        -config {make_external "FIXED_IO, DDR" apply_board_preset "1" Master "Disable" Slave "Disable"} \
        $ps7
} else {
    # This makes a design that can still be inspected and simulated, but the
    # generic PS settings are not safe for a real PYNQ-Z2 DDR interface.
    make_bd_intf_pins_external [get_bd_intf_pins processing_system7_0/DDR]
    make_bd_intf_pins_external [get_bd_intf_pins processing_system7_0/FIXED_IO]
    puts "WARNING: No PYNQ-Z2 board part is installed; do not generate a hardware image from generic PS settings."
}

set_property -dict [list \
    CONFIG.PCW_USE_M_AXI_GP0 {1} \
    CONFIG.PCW_USE_S_AXI_HP0 {1} \
    CONFIG.PCW_EN_CLK0_PORT {1} \
    CONFIG.PCW_EN_RST0_PORT {1} \
    CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100.000000} \
] $ps7

# -----------------------------------------------------------------------------
# DMA, accelerator, configuration GPIO, and interconnects
# -----------------------------------------------------------------------------
set dma [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:* axis_dma_0]
set_property -dict [list \
    CONFIG.c_include_sg {0} \
    CONFIG.c_sg_include_stscntrl_strm {0} \
    CONFIG.c_include_mm2s {1} \
    CONFIG.c_include_s2mm {1} \
    CONFIG.c_m_axi_mm2s_data_width {32} \
    CONFIG.c_m_axis_mm2s_tdata_width {32} \
    CONFIG.c_m_axi_s2mm_data_width {32} \
    CONFIG.c_s_axis_s2mm_tdata_width {32} \
] $dma

set accel [create_bd_cell -type module -reference axis_dot_accelerator axis_dot_accelerator_0]

# Channel 1: control output [2:0]. Channel 2: sticky status input [0].
set gpio_control [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:* axi_gpio_control]
set_property -dict [list \
    CONFIG.C_GPIO_WIDTH {3} \
    CONFIG.C_ALL_OUTPUTS {1} \
    CONFIG.C_DOUT_DEFAULT {0x00000000} \
    CONFIG.C_IS_DUAL {1} \
    CONFIG.C_GPIO2_WIDTH {1} \
    CONFIG.C_ALL_INPUTS_2 {1} \
] $gpio_control

# Channel 1: packed weight word. Channel 2: signed 32-bit bias word.
set gpio_params [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:* axi_gpio_params]
set_property -dict [list \
    CONFIG.C_GPIO_WIDTH {32} \
    CONFIG.C_ALL_OUTPUTS {1} \
    CONFIG.C_DOUT_DEFAULT {0x00000000} \
    CONFIG.C_IS_DUAL {1} \
    CONFIG.C_GPIO2_WIDTH {32} \
    CONFIG.C_ALL_OUTPUTS_2 {1} \
    CONFIG.C_DOUT_DEFAULT_2 {0x00000000} \
] $gpio_params

# One PS master fans out to DMA registers and the two GPIO register banks.
set ctrl_smc [create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:* axi_smc_control]
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {3}] $ctrl_smc

# The two *memory-mapped* DMA masters share the PS HP0 slave port.
set mem_smc [create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:* axi_smc_memory]
set_property -dict [list CONFIG.NUM_SI {2} CONFIG.NUM_MI {1}] $mem_smc

set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:* proc_sys_reset_0]
set_property -dict [list CONFIG.C_EXT_RESET_HIGH {0}] $rst

set const_one [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:* const_one]
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {1}] $const_one
set const_zero [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:* const_zero]
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {0}] $const_zero

# Split AXI GPIO channel 1 into the accelerator's three scalar control pins.
foreach {cell_name bit_index} {
    slice_mode_int4    0
    slice_enable_2to4  1
    slice_clear_status 2
} {
    set slice [create_bd_cell -type ip -vlnv xilinx.com:ip:xlslice:* $cell_name]
    set_property -dict [list \
        CONFIG.DIN_WIDTH {3} \
        CONFIG.DIN_FROM $bit_index \
        CONFIG.DIN_TO $bit_index \
    ] $slice
    connect_bd_net [get_bd_pins axi_gpio_control/gpio_io_o] [get_bd_pins $cell_name/Din]
}

connect_bd_net [get_bd_pins slice_mode_int4/Dout] \
               [get_bd_pins axis_dot_accelerator_0/cfg_mode_int4]
connect_bd_net [get_bd_pins slice_enable_2to4/Dout] \
               [get_bd_pins axis_dot_accelerator_0/cfg_enable_2to4]
connect_bd_net [get_bd_pins slice_clear_status/Dout] \
               [get_bd_pins axis_dot_accelerator_0/cfg_clear_status]
connect_bd_net [get_bd_pins axi_gpio_params/gpio_io_o] \
               [get_bd_pins axis_dot_accelerator_0/cfg_weight_tdata]
connect_bd_net [get_bd_pins axi_gpio_params/gpio2_io_o] \
               [get_bd_pins axis_dot_accelerator_0/cfg_bias]
connect_bd_net [get_bd_pins axis_dot_accelerator_0/status_mask_error] \
               [get_bd_pins axi_gpio_control/gpio2_io_i]

# -----------------------------------------------------------------------------
# AXI interfaces
# -----------------------------------------------------------------------------
# Streaming path. These are AXIS interfaces, so they connect only to the core.
connect_bd_intf_net [get_bd_intf_pins axis_dma_0/M_AXIS_MM2S] \
                    [get_bd_intf_pins axis_dot_accelerator_0/S_AXIS]
connect_bd_intf_net [get_bd_intf_pins axis_dot_accelerator_0/M_AXIS] \
                    [get_bd_intf_pins axis_dma_0/S_AXIS_S2MM]

# Register/control path from PS GP0.
connect_bd_intf_net [get_bd_intf_pins processing_system7_0/M_AXI_GP0] \
                    [get_bd_intf_pins axi_smc_control/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins axi_smc_control/M00_AXI] \
                    [get_bd_intf_pins axis_dma_0/S_AXI_LITE]
connect_bd_intf_net [get_bd_intf_pins axi_smc_control/M01_AXI] \
                    [get_bd_intf_pins axi_gpio_control/S_AXI]
connect_bd_intf_net [get_bd_intf_pins axi_smc_control/M02_AXI] \
                    [get_bd_intf_pins axi_gpio_params/S_AXI]

# DDR path: these names intentionally contain M_AXI, not M_AXIS. M_AXIS_MM2S is
# a stream and must never be connected to SmartConnect.
connect_bd_intf_net [get_bd_intf_pins axis_dma_0/M_AXI_MM2S] \
                    [get_bd_intf_pins axi_smc_memory/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins axis_dma_0/M_AXI_S2MM] \
                    [get_bd_intf_pins axi_smc_memory/S01_AXI]
connect_bd_intf_net [get_bd_intf_pins axi_smc_memory/M00_AXI] \
                    [get_bd_intf_pins processing_system7_0/S_AXI_HP0]

# -----------------------------------------------------------------------------
# One 100 MHz clock domain and synchronous active-low peripheral reset
# -----------------------------------------------------------------------------
set fclk [get_bd_pins processing_system7_0/FCLK_CLK0]
foreach sink_name {
    processing_system7_0/M_AXI_GP0_ACLK
    processing_system7_0/S_AXI_HP0_ACLK
    axis_dma_0/s_axi_lite_aclk
    axis_dma_0/m_axi_mm2s_aclk
    axis_dma_0/m_axi_s2mm_aclk
    axis_dot_accelerator_0/aclk
    axi_gpio_control/s_axi_aclk
    axi_gpio_params/s_axi_aclk
    axi_smc_control/aclk
    axi_smc_memory/aclk
    proc_sys_reset_0/slowest_sync_clk
} {
    set sink [get_bd_pins -quiet $sink_name]
    if {[llength $sink] != 1} {
        error "Required clock pin '$sink_name' was not found. Check the installed Vivado IP version."
    }
    connect_bd_net $fclk $sink
}

# Most AXI DMA releases clock each stream from the corresponding M_AXI clock.
# A few releases expose separate stream clocks; connect them when present.
foreach sink_name {
    axis_dma_0/m_axis_mm2s_aclk
    axis_dma_0/s_axis_s2mm_aclk
} {
    set sink [get_bd_pins -quiet $sink_name]
    if {[llength $sink] == 1} {
        connect_bd_net $fclk $sink
    }
}

connect_bd_net [get_bd_pins processing_system7_0/FCLK_RESET0_N] \
               [get_bd_pins proc_sys_reset_0/ext_reset_in]
connect_bd_net [get_bd_pins const_zero/dout] \
               [get_bd_pins proc_sys_reset_0/aux_reset_in]
connect_bd_net [get_bd_pins const_one/dout] \
               [get_bd_pins proc_sys_reset_0/dcm_locked]

set peripheral_resetn [get_bd_pins proc_sys_reset_0/peripheral_aresetn]
foreach sink_name {
    axis_dma_0/axi_resetn
    axis_dot_accelerator_0/aresetn
    axi_gpio_control/s_axi_aresetn
    axi_gpio_params/s_axi_aresetn
} {
    set sink [get_bd_pins -quiet $sink_name]
    if {[llength $sink] != 1} {
        error "Required reset pin '$sink_name' was not found."
    }
    connect_bd_net $peripheral_resetn $sink
}
connect_bd_net [get_bd_pins proc_sys_reset_0/interconnect_aresetn] \
               [get_bd_pins axi_smc_control/aresetn] \
               [get_bd_pins axi_smc_memory/aresetn]

# -----------------------------------------------------------------------------
# Address map
# -----------------------------------------------------------------------------
set ps_data [get_bd_addr_spaces processing_system7_0/Data]
assign_bd_address -offset 0x40400000 -range 0x00010000 \
    -target_address_space $ps_data [get_bd_addr_segs axis_dma_0/S_AXI_LITE/Reg] -force
assign_bd_address -offset 0x41200000 -range 0x00010000 \
    -target_address_space $ps_data [get_bd_addr_segs axi_gpio_control/S_AXI/Reg] -force
assign_bd_address -offset 0x41210000 -range 0x00010000 \
    -target_address_space $ps_data [get_bd_addr_segs axi_gpio_params/S_AXI/Reg] -force

set hp0_ddr [get_bd_addr_segs -quiet processing_system7_0/S_AXI_HP0/HP0_DDR_LOWOCM]
if {[llength $hp0_ddr] != 1} {
    error "PS7 HP0 DDR segment was not found; verify that S_AXI_HP0 is enabled."
}
assign_bd_address -target_address_space [get_bd_addr_spaces axis_dma_0/Data_MM2S] $hp0_ddr
assign_bd_address -target_address_space [get_bd_addr_spaces axis_dma_0/Data_S2MM] $hp0_ddr

validate_bd_design
save_bd_design

# Generate and select the HDL wrapper so Run Synthesis builds the complete PS/PL
# system rather than the standalone AXI module.
set bd_file [get_files -quiet */$bd_name.bd]
if {[llength $bd_file] != 1} {
    error "Could not locate the generated $bd_name.bd file."
}
generate_target all $bd_file
make_wrapper -files $bd_file -top

set project_dir  [get_property DIRECTORY [current_project]]
set project_name [get_property NAME [current_project]]
set wrapper_file [file join $project_dir ${project_name}.gen sources_1 bd $bd_name hdl ${bd_name}_wrapper.v]
if {![file exists $wrapper_file]} {
    error "Vivado did not generate the expected wrapper: $wrapper_file"
}
add_files -norecurse $wrapper_file
set_property top ${bd_name}_wrapper [get_filesets sources_1]
update_compile_order -fileset sources_1

puts "Lab04 Block Design is ready: $bd_name"
puts "Control map: DMA=0x40400000, control GPIO=0x41200000, parameter GPIO=0x41210000"
puts "Before bitstream generation, confirm that BOARD_PART is PYNQ-Z2 and Validate Design has no Critical Warning."
