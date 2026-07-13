# Intentionally no PL PACKAGE_PIN constraints are required for this design.
#
# DDR and FIXED_IO belong to the Zynq Processing System and are supplied by the
# PYNQ-Z2 board preset in the Block Design. AXI4-Stream, GPIO configuration, clock,
# and reset are internal nets. FCLK_CLK0 gets its timing definition from the PS7
# configuration. If Vivado reports unconstrained top-level AXIS ports, the RTL was
# synthesized directly instead of generating/using the Block Design wrapper.
