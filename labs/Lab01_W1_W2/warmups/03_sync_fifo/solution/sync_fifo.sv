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
            if (ptr == DEPTH-1)
                next_ptr = '0;
            else
                next_ptr = ptr + 1'b1;
        end
    endfunction

    always_comb begin
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
            if (do_write) begin
                mem[wr_ptr] <= wr_data;
                wr_ptr      <= next_ptr(wr_ptr);
            end

            if (do_read) begin
                rd_data <= mem[rd_ptr];
                rd_ptr  <= next_ptr(rd_ptr);
            end

            case ({do_write, do_read})
                2'b10: count <= count + 1'b1;
                2'b01: count <= count - 1'b1;
                default: count <= count;
            endcase
        end
    end
endmodule
