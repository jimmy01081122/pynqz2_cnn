# Run from the Vivado Tcl Console with:
#   source <absolute-path>/Lab02_W3_W4/vivado/create_project.tcl

set script_dir [file dirname [file normalize [info script]]]
set lab_dir    [file normalize [file join $script_dir ..]]
set build_dir  [file join $lab_dir build vivado]

create_project lab02_dense_pe $build_dir -part xc7z020clg400-1 -force
set_property target_language Verilog [current_project]

add_files -norecurse [file join $lab_dir rtl dense_int_pe.sv]
add_files -fileset sim_1 -norecurse [file join $lab_dir tb tb_dense_int_pe.sv]
add_files -fileset constrs_1 -norecurse [file join $lab_dir constraints pynq_z2_lab02.xdc]

set_property top dense_int_pe [get_filesets sources_1]
set_property top tb_dense_int_pe [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1

puts "Lab02 project created at: $build_dir"
puts "Next: Flow Navigator -> Simulation -> Run Simulation -> Run Behavioral Simulation"
puts "For this lab, run synthesis only. The wide PE ports are intentionally not board-pin mapped."
