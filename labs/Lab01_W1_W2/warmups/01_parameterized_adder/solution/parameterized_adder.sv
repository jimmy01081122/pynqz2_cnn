`timescale 1ns/1ps

module parameterized_adder #(
    parameter integer WIDTH = 8
) (
    input  logic [WIDTH-1:0] a,
    input  logic [WIDTH-1:0] b,
    output logic [WIDTH-1:0] sum,
    output logic             carry_out,
    output logic             overflow
);
    logic [WIDTH:0] extended_sum;

    // 使用 always @* 可避開部分舊版 Icarus 對 always_comb 固定位元選取的提示；
    // 此區塊仍是完整的組合邏輯。
    always @* begin
        extended_sum = {1'b0, a} + {1'b0, b};
        sum           = extended_sum[WIDTH-1:0];
        carry_out     = extended_sum[WIDTH];
        overflow      = (a[WIDTH-1] == b[WIDTH-1]) &&
                        (sum[WIDTH-1] != a[WIDTH-1]);
    end
endmodule
