`timescale 1ns/1ps

// Dense signed dot-product processing element (PE).
//
// Packing convention (lane 0 is always in the least-significant bits):
//   mode_int4 = 0: four signed INT8 lanes, lane i = data[i*8 +: 8]
//   mode_int4 = 1: eight signed INT4 lanes, lane i = data[i*4 +: 4]
// INT4 values use two's-complement, so their legal range is -8 to +7.
module dense_int_pe #(
    parameter integer ACC_WIDTH = 32
) (
    input  logic                        clk,
    input  logic                        rst_n,

    input  logic                        in_valid,
    output logic                        in_ready,
    input  logic [31:0]                 in_activation,
    input  logic [31:0]                 in_weight,
    input  logic                        in_mode_int4,
    input  logic                        in_clear_acc,
    input  logic                        in_last,

    output logic                        out_valid,
    input  logic                        out_ready,
    output logic signed [ACC_WIDTH-1:0] out_acc,
    output logic                        out_last
);

    logic signed [ACC_WIDTH-1:0] acc_state;
    logic signed [ACC_WIDTH-1:0] dot_product;
    logic signed [ACC_WIDTH-1:0] next_acc;

    function automatic signed [ACC_WIDTH-1:0] packed_dot (
        input logic [31:0] activation,
        input logic [31:0] weight,
        input logic        mode_int4
    );
        integer lane;
        reg signed [7:0] a8;
        reg signed [7:0] w8;
        reg signed [3:0] a4;
        reg signed [3:0] w4;
        reg signed [15:0] product8;
        reg signed [7:0]  product4;
        reg signed [ACC_WIDTH-1:0] sum;
        begin
            sum = '0;
            if (mode_int4) begin
                for (lane = 0; lane < 8; lane = lane + 1) begin
                    a4 = $signed(activation[lane*4 +: 4]);
                    w4 = $signed(weight[lane*4 +: 4]);
                    product4 = a4 * w4;
                    sum = sum + product4;
                end
            end else begin
                for (lane = 0; lane < 4; lane = lane + 1) begin
                    a8 = $signed(activation[lane*8 +: 8]);
                    w8 = $signed(weight[lane*8 +: 8]);
                    product8 = a8 * w8;
                    sum = sum + product8;
                end
            end
            packed_dot = sum;
        end
    endfunction

    always_comb begin
        dot_product = packed_dot(in_activation, in_weight, in_mode_int4);
        if (in_clear_acc)
            next_acc = dot_product;
        else
            next_acc = acc_state + dot_product;
    end

    // A one-entry elastic output register. It may accept a new transaction when
    // empty, or in the same cycle in which the previous result is consumed.
    always_comb begin
        in_ready = (~out_valid) | out_ready;
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            acc_state <= '0;
            out_acc   <= '0;
            out_last  <= 1'b0;
            out_valid <= 1'b0;
        end else begin
            if (in_valid && in_ready) begin
                acc_state <= next_acc;
                out_acc   <= next_acc;
                out_last  <= in_last;
                out_valid <= 1'b1;
            end else if (out_valid && out_ready) begin
                out_valid <= 1'b0;
            end
        end
    end

endmodule
