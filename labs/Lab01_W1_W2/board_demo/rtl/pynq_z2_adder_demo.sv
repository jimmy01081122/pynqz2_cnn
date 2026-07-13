`timescale 1ns/1ps

// Optional clock-free first bitstream for the PYNQ-Z2.
// SW0 and SW1 are two one-bit operands. LED[1:0] displays their two-bit sum;
// LED2 and LED3 are intentionally off.
module pynq_z2_adder_demo (
    input  logic [1:0] sw,
    output logic [3:0] led
);
    logic [1:0] sum;

    always_comb begin
        sum = {1'b0, sw[0]} + {1'b0, sw[1]};
        led = {2'b00, sum};
    end
endmodule
