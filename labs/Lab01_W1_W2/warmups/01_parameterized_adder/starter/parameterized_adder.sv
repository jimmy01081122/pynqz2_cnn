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

    always_comb begin
        // 第一段先提供：各補一個 0 再相加，才不會在 WIDTH 位就丟掉進位。
        extended_sum = {1'b0, a} + {1'b0, b};

        // TODO 1：從 extended_sum 取出 WIDTH 位 sum 與 carry_out。
        sum       = '0;
        carry_out = 1'b0;

        // TODO 2：根據 a、b、sum 的符號位判斷二補數 signed overflow。
        overflow = 1'b0;
    end
endmodule
