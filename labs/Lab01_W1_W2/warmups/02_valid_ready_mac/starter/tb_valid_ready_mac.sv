`timescale 1ns/1ps

module tb_valid_ready_mac;
    localparam integer DATA_WIDTH = 8;
    localparam integer ACC_WIDTH  = 24;
    localparam integer CLK_PERIOD = 10;

    logic clk = 1'b0;
    logic rst_n;
    logic in_valid;
    logic in_ready;
    logic signed [DATA_WIDTH-1:0] a;
    logic signed [DATA_WIDTH-1:0] b;
    logic out_valid;
    logic out_ready;
    logic signed [ACC_WIDTH-1:0] out_data;

    // TODO 5：負數、stall、back-to-back 測試都完成後改成 1'b1。
    logic tb_todos_done = 1'b0;

    always #(CLK_PERIOD/2) clk = ~clk;

    valid_ready_mac #(
        .DATA_WIDTH(DATA_WIDTH), .ACC_WIDTH(ACC_WIDTH)
    ) dut (
        .clk(clk), .rst_n(rst_n),
        .in_valid(in_valid), .in_ready(in_ready), .a(a), .b(b),
        .out_valid(out_valid), .out_ready(out_ready), .out_data(out_data)
    );

    initial begin
        $display("=== Starter：valid/ready MAC ===");
        rst_n     = 1'b0;
        in_valid  = 1'b0;
        out_ready = 1'b0;
        a          = '0;
        b          = '0;

        repeat (2) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        // 已提供一筆 smoke transaction：2*3，預期新累加值為 6。
        @(negedge clk);
        a         = 8'sd2;
        b         = 8'sd3;
        in_valid  = 1'b1;
        out_ready = 1'b0;
        @(posedge clk);
        #1;
        in_valid = 1'b0;

        if (!out_valid || ($signed(out_data) !== 24'sd6))
            $fatal(1, "[TODO] MAC 尚未完成：預期 out_valid=1、out_data=6，實際 %b、%0d。",
                   out_valid, $signed(out_data));
        $display("[OK] 基本 transaction 通過。");

        // TODO 6：out_ready 保持 0 數個 cycle，檢查 out_data 必須穩定。
        // TODO 7：加入負數乘法與連續兩 cycle input handshake。

        if (!tb_todos_done)
            $fatal(1, "[TODO] DUT smoke test 已過；請補齊 MAC TB 並設定 tb_todos_done=1。");

        $display("[PASS] Starter 的 MAC DUT 與 TB TODO 均已完成。");
        $finish;
    end

    initial begin
        #(100*CLK_PERIOD);
        $fatal(1, "[FAIL] 模擬逾時，請檢查 valid/ready 是否形成等待死結。");
    end
endmodule
