`timescale 1ns/1ps

module tb_tiny_counter;
    localparam integer WIDTH      = 4;
    localparam integer CLK_PERIOD = 10;

    logic clk = 1'b0;
    logic rst;
    logic en;
    logic [WIDTH-1:0] count;

    // TODO 5：所有 TB 練習完成後改成 1'b1。
    logic tb_todos_done = 1'b0;

    // TODO 2：說明為何反相間隔是「半個」週期；試著修改 CLK_PERIOD 看波形。
    always #(CLK_PERIOD/2) clk = ~clk;

    tiny_counter #(.WIDTH(WIDTH)) dut (
        .clk(clk), .rst(rst), .en(en), .count(count)
    );

    initial begin
        $display("=== Starter：Testbench 技法 ===");

        // TODO 3：取消下一行註解；觀察它與 $display 只印一次的差異。
        // $monitor("[MONITOR] t=%0t clk=%b rst=%b en=%b count=%0d", $time, clk, rst, en, count);

        rst = 1'b1;
        en  = 1'b0;
        repeat (2) @(posedge clk);
        #1;
        $display("reset 後 count=%0d", count);
        if (count !== 0)
            $fatal(1, "[FAIL] reset 後 count 應為 0。");

        // 已提供基本 stimulus：在負緣打開 en，經過兩個正緣應累加成 2。
        @(negedge clk);
        rst = 1'b0;
        en  = 1'b1;
        repeat (2) @(posedge clk);
        #1;
        $display("enable 兩個 cycle 後 count=%0d", count);
        if (count !== 2)
            $fatal(1, "[TODO] counter DUT 尚未完成：count=%0d，預期 2。", count);

        // TODO 4：加入 en=0 保持、WIDTH 位回捲、運作中 reset 的檢查。

        if (!tb_todos_done)
            $fatal(1, "[TODO] 基本測試已過；請完成 $monitor 與額外 TB 測試，再設定 tb_todos_done=1。");

        $display("[PASS] Starter 的 counter DUT 與 TB TODO 均已完成。");
        $finish;
    end

    initial begin
        #(100*CLK_PERIOD);
        $fatal(1, "[FAIL] Testbench 模擬逾時。");
    end
endmodule
