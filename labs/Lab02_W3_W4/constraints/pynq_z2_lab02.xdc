# PYNQ-Z2 PL clock reference constraint.
# The board's 125 MHz clock is connected to package pin H16.
# This Lab's PE has wide teaching/test ports, so only synthesis and simulation are
# intended here. Do not run implementation on dense_int_pe directly; Lab04 shows
# how to place the datapath behind AXI interfaces in a Zynq Block Design.

set lab_clk [get_ports -quiet clk]
if {[llength $lab_clk] == 1} {
    set_property PACKAGE_PIN H16 $lab_clk
    set_property IOSTANDARD LVCMOS33 $lab_clk
    create_clock -add -name lab_clk_125m -period 8.000 -waveform {0.000 4.000} $lab_clk
}
