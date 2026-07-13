`timescale 1ns/1ps

// Decode one 2:4 sparse group.
// sparse_values[value 0] occupies the least-significant DATA_WIDTH bits.
// Values are assigned to asserted mask lanes from lane 0 toward lane 3.
// Any mask whose popcount is not exactly two is rejected and decodes to zeros.
module sparse_2of4_decoder #(
    parameter integer DATA_WIDTH = 8
) (
    input  logic [2*DATA_WIDTH-1:0] sparse_values,
    input  logic [3:0]              mask,
    output logic [4*DATA_WIDTH-1:0] dense_values,
    output logic                    mask_ok
);
    integer lane;
    integer value_index;
    integer one_count;

    always_comb begin
        dense_values = '0;
        value_index  = 0;
        one_count    = 0;

        for (lane = 0; lane < 4; lane = lane + 1) begin
            if (mask[lane]) begin
                one_count = one_count + 1;
                if (value_index < 2)
                    dense_values[lane*DATA_WIDTH +: DATA_WIDTH] =
                        sparse_values[value_index*DATA_WIDTH +: DATA_WIDTH];
                value_index = value_index + 1;
            end
        end

        mask_ok = (one_count == 2);
        if (!mask_ok)
            dense_values = '0;
    end
endmodule
