## PYNQ-Z2 教學用最小 User-I/O 約束
## 來源核對：PYNQ-Z2 Master XDC / Reference Manual
## 使用方式：只保留目前 top module 真正存在的 ports；不用的行請註解。
## 注意：PS-PL AXI 設計通常用 PS FCLK，不要把該 AXI clock 再綁到 sysclk/H16。

## 125 MHz PL clock
set_property -dict { PACKAGE_PIN H16 IOSTANDARD LVCMOS33 } [get_ports { sysclk }]
create_clock -add -name sys_clk_pin -period 8.000 -waveform {0.000 4.000} [get_ports { sysclk }]

## Slide switches
set_property -dict { PACKAGE_PIN M20 IOSTANDARD LVCMOS33 } [get_ports { sw[0] }]
set_property -dict { PACKAGE_PIN M19 IOSTANDARD LVCMOS33 } [get_ports { sw[1] }]

## Four single-color LEDs
set_property -dict { PACKAGE_PIN R14 IOSTANDARD LVCMOS33 } [get_ports { led[0] }]
set_property -dict { PACKAGE_PIN P14 IOSTANDARD LVCMOS33 } [get_ports { led[1] }]
set_property -dict { PACKAGE_PIN N16 IOSTANDARD LVCMOS33 } [get_ports { led[2] }]
set_property -dict { PACKAGE_PIN M14 IOSTANDARD LVCMOS33 } [get_ports { led[3] }]

## Push buttons
set_property -dict { PACKAGE_PIN D19 IOSTANDARD LVCMOS33 } [get_ports { btn[0] }]
set_property -dict { PACKAGE_PIN D20 IOSTANDARD LVCMOS33 } [get_ports { btn[1] }]
set_property -dict { PACKAGE_PIN L20 IOSTANDARD LVCMOS33 } [get_ports { btn[2] }]
set_property -dict { PACKAGE_PIN L19 IOSTANDARD LVCMOS33 } [get_ports { btn[3] }]

