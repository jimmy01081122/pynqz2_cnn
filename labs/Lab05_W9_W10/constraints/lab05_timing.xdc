###############################################################################
# Lab05 timing-only XDC
#
# This file intentionally contains no PACKAGE_PIN or IOSTANDARD assignments.
# Never guess board pins. Copy them from the official master XDC for your board.
# The top-level clock port is assumed to be named "clk".
###############################################################################

if {[info exists ::LAB_TARGET_CLOCK_NS]} {
    set lab_clock_period_ns $::LAB_TARGET_CLOCK_NS
} else {
    set lab_clock_period_ns 10.000
}

set lab_clock_port [get_ports -quiet clk]
if {[llength $lab_clock_port] != 1} {
    error "Lab05 XDC expects exactly one top-level port named clk. Edit lab05_timing.xdc to match your RTL."
}
create_clock -name sys_clk -period $lab_clock_period_ns $lab_clock_port

# Optional asynchronous active-low reset. This only adds a timing exception
# when the port exists; change the name/polarity to match your own design.
set lab_reset_port [get_ports -quiet rst_n]
if {[llength $lab_reset_port] == 1} {
    set_false_path -from $lab_reset_port
}

# TODO before bitstream generation:
# 1. Add verified PACKAGE_PIN and IOSTANDARD constraints from the board vendor.
# 2. Add input/output delay constraints when external interfaces are used.
# 3. Confirm generated clocks and clock-domain crossings.

