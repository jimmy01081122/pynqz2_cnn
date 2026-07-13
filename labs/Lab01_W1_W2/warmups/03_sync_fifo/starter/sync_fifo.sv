`timescale 1ns/1ps

module sync_fifo #(
    parameter integer WIDTH = 8,
    parameter integer DEPTH = 4
) (
    input  logic                       clk,
    input  logic                       rst_n,
    input  logic                       wr_en,
    input  logic [WIDTH-1:0]           wr_data,
    output logic                       full,
    input  logic                       rd_en,
    output logic [WIDTH-1:0]           rd_data,
    output logic                       empty,
    output logic [$clog2(DEPTH+1)-1:0] count
);
    localparam integer PTR_WIDTH = (DEPTH <= 1) ? 1 : $clog2(DEPTH);

    logic [WIDTH-1:0]     mem [0:DEPTH-1];
    logic [PTR_WIDTH-1:0] wr_ptr;
    logic [PTR_WIDTH-1:0] rd_ptr;
    logic                 do_write;
    logic                 do_read;

    function automatic logic [PTR_WIDTH-1:0] next_ptr(
        input logic [PTR_WIDTH-1:0] ptr
    );
        begin
            // TODO 1：ptr==DEPTH-1 時回到 0，否則加 1。
            next_ptr = ptr;
        end
    endfunction

    always_comb begin
        // 先提供邊界判斷；請在 TB 驗證 full/empty 時要求確實被擋下。
        full     = (count == DEPTH);
        empty    = (count == 0);
        do_write = wr_en && !full;
        do_read  = rd_en && !empty;
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            wr_ptr  <= '0;
            rd_ptr  <= '0;
            rd_data <= '0;
            count   <= '0;
        end else begin
            // TODO 2：do_write 時寫 mem，並更新 wr_ptr。
            // TODO 3：do_read 時更新 rd_data，並更新 rd_ptr。
            // TODO 4：依 {do_write, do_read} 更新 count。
            wr_ptr  <= wr_ptr;
            rd_ptr  <= rd_ptr;
            rd_data <= rd_data;
            count   <= count;
        end
    end
endmodule
