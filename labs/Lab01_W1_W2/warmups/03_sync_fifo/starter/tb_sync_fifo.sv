`timescale 1ns/1ps

module tb_sync_fifo;
    localparam integer WIDTH      = 8;
    localparam integer DEPTH      = 4;
    localparam integer CLK_PERIOD = 10;

    logic clk = 1'b0;
    logic rst_n;
    logic wr_en;
    logic [WIDTH-1:0] wr_data;
    logic full;
    logic rd_en;
    logic [WIDTH-1:0] rd_data;
    logic empty;
    logic [$clog2(DEPTH+1)-1:0] count;

    // TODO 7：完成 FIFO 所有邊界測試後改為 1'b1。
    logic tb_todos_done = 1'b0;

    always #(CLK_PERIOD/2) clk = ~clk;

    sync_fifo #(.WIDTH(WIDTH), .DEPTH(DEPTH)) dut (
        .clk(clk), .rst_n(rst_n),
        .wr_en(wr_en), .wr_data(wr_data), .full(full),
        .rd_en(rd_en), .rd_data(rd_data), .empty(empty), .count(count)
    );

    initial begin
        $display("=== Starter：同步 FIFO ===");
        rst_n   = 1'b0;
        wr_en   = 1'b0;
        rd_en   = 1'b0;
        wr_data = '0;

        repeat (2) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        // 已提供一筆 smoke write；成功後 count 應為 1。
        @(negedge clk);
        wr_en   = 1'b1;
        wr_data = 8'hA5;
        @(posedge clk);
        #1;
        wr_en = 1'b0;

        if (count !== 1 || empty !== 1'b0)
            $fatal(1, "[TODO] FIFO 尚未完成：寫入後 count=%0d empty=%b，預期 1、0。",
                   count, empty);
        $display("[OK] 基本 write 通過。");

        // TODO 8：讀回 A5，並檢查 registered rd_data。
        // TODO 9：補上 full/empty 拒絕、pointer 回捲、同 cycle 讀寫測試。

        if (!tb_todos_done)
            $fatal(1, "[TODO] DUT smoke test 已過；請補齊 FIFO TB 並設定 tb_todos_done=1。");

        $display("[PASS] Starter 的 FIFO DUT 與 TB TODO 均已完成。");
        $finish;
    end

    initial begin
        #(200*CLK_PERIOD);
        $fatal(1, "[FAIL] FIFO 模擬逾時。");
    end
endmodule
