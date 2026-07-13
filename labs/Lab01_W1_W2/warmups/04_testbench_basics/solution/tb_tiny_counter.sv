`timescale 1ns/1ps

module tb_tiny_counter;
    localparam integer WIDTH      = 4;
    localparam integer CLK_PERIOD = 10;

    logic clk = 1'b0;
    logic rst;
    logic en;
    logic [WIDTH-1:0] count;
    integer error_count = 0;

    // 每半週期反相一次，因此兩次反相形成一個完整 clock period。
    always #(CLK_PERIOD/2) clk = ~clk;

    tiny_counter #(.WIDTH(WIDTH)) dut (
        .clk(clk), .rst(rst), .en(en), .count(count)
    );

    task automatic check_count(
        input logic [WIDTH-1:0] expected,
        input string label_text
    );
        begin
            if (count !== expected) begin
                error_count = error_count + 1;
                $display("[FAIL] %s：count=%0d，預期 %0d", label_text, count, expected);
            end else begin
                $display("[OK] %s：count=%0d", label_text, count);
            end
        end
    endtask

    initial begin
        $monitor("[MONITOR] t=%0t clk=%b rst=%b en=%b count=%0d",
                 $time, clk, rst, en, count);
    end

    initial begin
        $display("=== Solution：Testbench 技法 self-checking TB ===");
        rst = 1'b1;
        en  = 1'b0;

        repeat (2) @(posedge clk);
        #1;
        check_count(4'd0, "同步 reset");

        @(negedge clk);
        rst = 1'b0;
        en  = 1'b1;
        repeat (3) @(posedge clk);
        #1;
        check_count(4'd3, "enable 三個 cycle");

        @(negedge clk);
        en = 1'b0;
        repeat (2) @(posedge clk);
        #1;
        check_count(4'd3, "disable 時保持");

        // 4-bit counter：3 再加 13 次等於 16，應回捲到 0。
        @(negedge clk);
        en = 1'b1;
        repeat (13) @(posedge clk);
        #1;
        check_count(4'd0, "固定寬度回捲");

        // en 仍為 1，但 reset 優先權較高。
        @(negedge clk);
        rst = 1'b1;
        @(posedge clk);
        #1;
        check_count(4'd0, "運作中再次 reset");

        @(negedge clk);
        rst = 1'b0;
        en  = 1'b0;

        if (error_count == 0)
            $display("[PASS] 全部 tiny_counter / TB 技法測試通過。");
        else
            $fatal(1, "[FAIL] 共有 %0d 個 counter 測試失敗。", error_count);
        $finish;
    end

    initial begin
        #(100*CLK_PERIOD);
        $fatal(1, "[FAIL] Testbench 模擬逾時。");
    end
endmodule
