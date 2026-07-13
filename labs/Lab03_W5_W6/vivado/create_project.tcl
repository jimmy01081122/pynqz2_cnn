# Run with Tools -> Run Tcl Script in Vivado.

set script_dir [file dirname [file normalize [info script]]]
set lab_dir    [file normalize [file join $script_dir ..]]
set build_dir  [file join $lab_dir build vivado]

create_project lab03_sparse_array $build_dir -part xc7z020clg400-1 -force
set_property target_language Verilog [current_project]

add_files -norecurse [list \
    [file join $lab_dir rtl sparse_2of4_decoder.sv] \
    [file join $lab_dir rtl sparse_pe.sv] \
    [file join $lab_dir rtl requantize.sv] \
    [file join $lab_dir rtl sparse_array_4x4.sv]]
add_files -fileset sim_1 -norecurse [file join $lab_dir tb tb_sparse_array.sv]
add_files -fileset constrs_1 -norecurse [file join $lab_dir constraints pynq_z2_lab03.xdc]

set_property top sparse_array_4x4 [get_filesets sources_1]
set_property top tb_sparse_array [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1

puts "Lab03 project created at: $build_dir"
puts "Run Behavioral Simulation first; synthesis is optional for resource inspection."
