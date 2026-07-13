`timescale 1ns/1ps

module valid_ready_mac #(
    parameter integer DATA_WIDTH = 8,
    parameter integer ACC_WIDTH  = 24
) (
    input  logic                         clk,
    input  logic                         rst_n,
    input  logic                         in_valid,
    output logic                         in_ready,
    input  logic signed [DATA_WIDTH-1:0] a,
    input  logic signed [DATA_WIDTH-1:0] b,
    output logic                         out_valid,
    input  logic                         out_ready,
    output logic signed [ACC_WIDTH-1:0]  out_data
);
    logic signed [(2*DATA_WIDTH)-1:0] product;
    logic signed [ACC_WIDTH-1:0]      product_extended;
    logic signed [ACC_WIDTH-1:0]      accumulator;

    always_comb begin
        product          = $signed(a) * $signed(b);
        product_extended = product;
        in_ready         = !out_valid || out_ready;
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            accumulator <= '0;
            out_valid   <= 1'b0;
        end else begin
            if (in_valid && in_ready) begin
                accumulator <= accumulator + product_extended;
                out_valid   <= 1'b1;
            end else if (out_valid && out_ready) begin
                out_valid <= 1'b0;
            end
        end
    end

    assign out_data = accumulator;
endmodule
