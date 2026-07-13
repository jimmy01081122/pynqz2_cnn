`timescale 1ns/1ps

// Integer-only requantization:
// q = saturate_int8(round_to_nearest_ties_away(acc * multiplier / 2^shift)
//                   + zero_point)
module requantize #(
    parameter integer ACC_WIDTH = 32
) (
    input  logic signed [ACC_WIDTH-1:0] acc_in,
    input  logic signed [15:0]          multiplier,
    input  logic [5:0]                  shift,
    input  logic signed [15:0]          zero_point,
    output logic signed [7:0]           q_out
);
    localparam integer WORK_WIDTH = ACC_WIDTH + 17;

    logic signed [WORK_WIDTH-1:0] wide_product;
    logic signed [WORK_WIDTH-1:0] extended_acc;
    logic signed [WORK_WIDTH-1:0] extended_multiplier;
    logic signed [WORK_WIDTH-1:0] rounding_bias;
    logic signed [WORK_WIDTH-1:0] shifted_value;
    logic signed [WORK_WIDTH-1:0] with_zero_point;

    always_comb begin
        extended_acc        = {{(WORK_WIDTH-ACC_WIDTH){acc_in[ACC_WIDTH-1]}}, acc_in};
        extended_multiplier = {{(WORK_WIDTH-16){multiplier[15]}}, multiplier};
        wide_product        = extended_acc * extended_multiplier;
        rounding_bias  = '0;
        shifted_value  = wide_product;

        if (shift != 0) begin
            rounding_bias = {{(WORK_WIDTH-1){1'b0}}, 1'b1};
            rounding_bias = rounding_bias <<< (shift - 1'b1);
            if (wide_product < 0)
                shifted_value = -(((-wide_product) + rounding_bias) >>> shift);
            else
                shifted_value = (wide_product + rounding_bias) >>> shift;
        end

        with_zero_point = shifted_value + $signed(zero_point);
        if (with_zero_point > 127)
            q_out = 8'sd127;
        else if (with_zero_point < -128)
            q_out = 8'sh80;
        else
            q_out = with_zero_point[7:0];
    end
endmodule
