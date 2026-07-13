`timescale 1ns/1ps

// One combinational PE: decode one signed 2:4 weight group, then calculate a
// four-lane signed dot product. An invalid mask produces dot_product=0.
module sparse_pe #(
    parameter integer DATA_WIDTH = 8,
    parameter integer ACC_WIDTH  = 32
) (
    input  logic [4*DATA_WIDTH-1:0]             activations,
    input  logic [2*DATA_WIDTH-1:0]             sparse_values,
    input  logic [3:0]                          sparse_mask,
    output logic signed [ACC_WIDTH-1:0]         dot_product,
    output logic                                mask_ok
);
    logic [4*DATA_WIDTH-1:0] dense_weights;
    logic decoder_mask_ok;
    logic signed [ACC_WIDTH-1:0] dot_comb;
    logic signed [DATA_WIDTH-1:0] activation_lane;
    logic signed [DATA_WIDTH-1:0] weight_lane;
    logic signed [2*DATA_WIDTH-1:0] lane_product;
    integer lane;

    sparse_2of4_decoder #(
        .DATA_WIDTH(DATA_WIDTH)
    ) decoder (
        .sparse_values(sparse_values),
        .mask(sparse_mask),
        .dense_values(dense_weights),
        .mask_ok(decoder_mask_ok)
    );

    always_comb begin
        dot_comb = '0;
        for (lane = 0; lane < 4; lane = lane + 1) begin
            activation_lane = $signed(activations[lane*DATA_WIDTH +: DATA_WIDTH]);
            weight_lane     = $signed(dense_weights[lane*DATA_WIDTH +: DATA_WIDTH]);
            lane_product = activation_lane * weight_lane;
            dot_comb = dot_comb + lane_product;
        end

        mask_ok = decoder_mask_ok;
        if (decoder_mask_ok)
            dot_product = dot_comb;
        else
            dot_product = '0;
    end
endmodule
