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
        // signed 乘法先提供，請觀察兩個 DATA_WIDTH operand 產生 2*DATA_WIDTH 乘積。
        product          = $signed(a) * $signed(b);

        // TODO 1：把 signed 乘積正確符號延伸到 ACC_WIDTH。
        product_extended = '0;

        // TODO 2：目前只處理 output 格為空；再加入「本 cycle 會被取走」條件。
        in_ready = !out_valid;
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            accumulator <= '0;
            out_valid   <= 1'b0;
        end else begin
            // TODO 3：只在 in_valid && in_ready 時更新 accumulator。
            // TODO 4：有新結果時拉高 out_valid；只有舊輸出被取走且
            //         沒有新輸入時，才清掉 out_valid。
            accumulator <= accumulator;
            out_valid   <= 1'b0;
        end
    end

    assign out_data = accumulator;
endmodule
