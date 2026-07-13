# PYNQ-Z2 125 MHz PL clock reference (package pin H16).
# sparse_array_4x4 is a teaching/simulation core with wide parallel ports. Run
# synthesis to inspect resources, but place it behind AXI before implementation.

set lab_clk [get_ports -quiet clk]
if {[llength $lab_clk] == 1} {
    set_property PACKAGE_PIN H16 $lab_clk
    set_property IOSTANDARD LVCMOS33 $lab_clk
    create_clock -add -name lab_clk_125m -period 8.000 -waveform {0.000 4.000} $lab_clk
}
