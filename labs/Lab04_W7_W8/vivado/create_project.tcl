# Run with Tools -> Run Tcl Script in Vivado.

set script_dir [file dirname [file normalize [info script]]]
set lab_dir    [file normalize [file join $script_dir ..]]
set build_dir  [file join $lab_dir build vivado]

create_project lab04_axis_accelerator $build_dir -part xc7z020clg400-1 -force
set_property target_language Verilog [current_project]

# Use the PYNQ-Z2 board part when it is installed. A raw xc7z020 part is enough
# for simulation/synthesis, but is not enough to configure real DDR correctly.
set board_candidates [get_board_parts -quiet *pynq-z2*]
if {[llength $board_candidates] == 0} {
    set board_candidates [get_board_parts -quiet *pynq_z2*]
}
if {[llength $board_candidates] > 0} {
    set_property BOARD_PART [lindex $board_candidates 0] [current_project]
    puts "Using board part: [get_property BOARD_PART [current_project]]"
} else {
    puts "WARNING: PYNQ-Z2 board files were not found. Do not build a hardware image without its PS preset."
}

add_files -norecurse [file join $lab_dir rtl axis_dot_accelerator.sv]
add_files -fileset sim_1 -norecurse [file join $lab_dir tb tb_axis_dot_accelerator.sv]
add_files -fileset constrs_1 -norecurse [file join $lab_dir constraints pynq_z2_lab04.xdc]
set_property top axis_dot_accelerator [get_filesets sources_1]
set_property top tb_axis_dot_accelerator [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1

source [file join $script_dir create_bd.tcl]

puts "Lab04 project created at: $build_dir"
puts "Run behavioral simulation before attempting synthesis or implementation."
