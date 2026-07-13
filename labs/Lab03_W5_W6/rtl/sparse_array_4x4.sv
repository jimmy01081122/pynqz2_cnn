`timescale 1ns/1ps

// Four input lanes broadcast to PES sparse PEs (default PES=4).
// Each PE owns one compressed 2:4 weight row and one accumulator.
//
// The 2:4 format inherently operates on groups of four, so LANES must be 4 in
// this teaching module. DATA_WIDTH, ACC_WIDTH, and the number of PEs remain
// parameters so students can explore precision and output parallelism.
module sparse_array_4x4 #(
    parameter integer DATA_WIDTH = 8,
    parameter integer ACC_WIDTH  = 32,
    parameter integer LANES      = 4,
    parameter integer PES        = 4
) (
    input  logic                              clk,
    input  logic                              rst_n,

    input  logic                              in_valid,
    output logic                              in_ready,
    input  logic [LANES*DATA_WIDTH-1:0]       in_activations,
    input  logic [PES*2*DATA_WIDTH-1:0]       in_sparse_values,
    input  logic [PES*4-1:0]                  in_sparse_masks,
    input  logic [PES*ACC_WIDTH-1:0]          in_bias,
    input  logic                              in_clear_acc,
    input  logic signed [15:0]                in_multiplier,
    input  logic [5:0]                        in_shift,
    input  logic signed [15:0]                in_zero_point,

    output logic                              out_valid,
    input  logic                              out_ready,
    output logic [PES*ACC_WIDTH-1:0]          out_acc,
    output logic [PES*8-1:0]                  out_q,
    output logic                              out_mask_error
);
    logic [PES*ACC_WIDTH-1:0] acc_state;
    logic [PES*ACC_WIDTH-1:0] dot_vector;
    logic [PES*ACC_WIDTH-1:0] next_acc_vector;
    logic [PES*8-1:0]         q_vector;
    logic [PES-1:0]           mask_ok_vector;
    logic                     any_mask_error;

    genvar pe_index;
    generate
        for (pe_index = 0; pe_index < PES; pe_index = pe_index + 1) begin : g_pe
            sparse_pe #(
                .DATA_WIDTH(DATA_WIDTH),
                .ACC_WIDTH(ACC_WIDTH)
            ) pe (
                .activations(in_activations[4*DATA_WIDTH-1:0]),
                .sparse_values(in_sparse_values[pe_index*2*DATA_WIDTH +: 2*DATA_WIDTH]),
                .sparse_mask(in_sparse_masks[pe_index*4 +: 4]),
                .dot_product(dot_vector[pe_index*ACC_WIDTH +: ACC_WIDTH]),
                .mask_ok(mask_ok_vector[pe_index])
            );

            requantize #(
                .ACC_WIDTH(ACC_WIDTH)
            ) requant (
                .acc_in(next_acc_vector[pe_index*ACC_WIDTH +: ACC_WIDTH]),
                .multiplier(in_multiplier),
                .shift(in_shift),
                .zero_point(in_zero_point),
                .q_out(q_vector[pe_index*8 +: 8])
            );
        end
    endgenerate

    integer p;
    always_comb begin
        next_acc_vector = '0;
        for (p = 0; p < PES; p = p + 1) begin
            if (in_clear_acc) begin
                next_acc_vector[p*ACC_WIDTH +: ACC_WIDTH] =
                    $signed(in_bias[p*ACC_WIDTH +: ACC_WIDTH]) +
                    $signed(dot_vector[p*ACC_WIDTH +: ACC_WIDTH]);
            end else begin
                next_acc_vector[p*ACC_WIDTH +: ACC_WIDTH] =
                    $signed(acc_state[p*ACC_WIDTH +: ACC_WIDTH]) +
                    $signed(dot_vector[p*ACC_WIDTH +: ACC_WIDTH]);
            end
        end
        any_mask_error = ~(&mask_ok_vector);
        in_ready = (~out_valid) | out_ready;
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            acc_state      <= '0;
            out_acc        <= '0;
            out_q          <= '0;
            out_mask_error <= 1'b0;
            out_valid      <= 1'b0;
        end else begin
            if (in_valid && in_ready) begin
                acc_state      <= next_acc_vector;
                out_acc        <= next_acc_vector;
                out_q          <= q_vector;
                out_mask_error <= any_mask_error;
                out_valid      <= 1'b1;
            end else if (out_valid && out_ready) begin
                out_valid <= 1'b0;
            end
        end
    end

`ifndef SYNTHESIS
    initial begin
        if (LANES != 4)
            $error("sparse_array_4x4 requires LANES=4 because this lab decodes one 2:4 group");
    end
`endif

endmodule
