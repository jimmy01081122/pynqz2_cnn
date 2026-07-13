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
    integer expected_count = 0;
    integer error_count = 0;

    always #(CLK_PERIOD/2) clk = ~clk;

    sync_fifo #(.WIDTH(WIDTH), .DEPTH(DEPTH)) dut (
        .clk(clk), .rst_n(rst_n),
        .wr_en(wr_en), .wr_data(wr_data), .full(full),
        .rd_en(rd_en), .rd_data(rd_data), .empty(empty), .count(count)
    );

    task automatic check_flags(input string label_text);
        logic expected_full;
        logic expected_empty;
        begin
            expected_full  = (expected_count == DEPTH);
            expected_empty = (expected_count == 0);
            if ((count !== expected_count) ||
                (full !== expected_full) || (empty !== expected_empty)) begin
                error_count = error_count + 1;
                $display("[FAIL] %s：count/full/empty=%0d/%b/%b；預期 %0d/%b/%b",
                         label_text, count, full, empty,
                         expected_count, expected_full, expected_empty);
            end else begin
                $display("[OK] %s：count=%0d full=%b empty=%b",
                         label_text, count, full, empty);
            end
        end
    endtask

    task automatic push(input logic [WIDTH-1:0] value);
        begin
            @(negedge clk);
            wr_en   = 1'b1;
            rd_en   = 1'b0;
            wr_data = value;
            @(posedge clk);
            #1;
            wr_en = 1'b0;
            expected_count = expected_count + 1;
            check_flags("push");
        end
    endtask

    task automatic pop(input logic [WIDTH-1:0] expected_value);
        begin
            @(negedge clk);
            wr_en = 1'b0;
            rd_en = 1'b1;
            @(posedge clk);
            #1;
            rd_en = 1'b0;
            expected_count = expected_count - 1;
            if (rd_data !== expected_value) begin
                error_count = error_count + 1;
                $display("[FAIL] pop：rd_data=%h，預期 %h", rd_data, expected_value);
            end
            check_flags("pop");
        end
    endtask

    task automatic simultaneous_rw(
        input logic [WIDTH-1:0] write_value,
        input logic [WIDTH-1:0] expected_read
    );
        begin
            @(negedge clk);
            wr_en   = 1'b1;
            rd_en   = 1'b1;
            wr_data = write_value;
            @(posedge clk);
            #1;
            wr_en = 1'b0;
            rd_en = 1'b0;
            if (rd_data !== expected_read) begin
                error_count = error_count + 1;
                $display("[FAIL] 同時讀寫：rd_data=%h，預期 %h", rd_data, expected_read);
            end
            // 一讀一寫，expected_count 不變。
            check_flags("同 cycle 讀寫");
        end
    endtask

    initial begin
        logic [WIDTH-1:0] held_rd_data;

        $display("=== Solution：同步 FIFO self-checking TB ===");
        rst_n   = 1'b0;
        wr_en   = 1'b0;
        rd_en   = 1'b0;
        wr_data = '0;

        repeat (2) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;
        #1;
        check_flags("reset 後");

        push(8'h11);
        push(8'h22);
        push(8'h33);
        push(8'h44);

        // full 時多寫一筆，必須被忽略。
        @(negedge clk);
        wr_en   = 1'b1;
        wr_data = 8'hEE;
        @(posedge clk);
        #1;
        wr_en = 1'b0;
        check_flags("full 拒絕寫入");

        pop(8'h11);
        simultaneous_rw(8'h55, 8'h22);
        push(8'h66);

        // 這一輪跨過陣列尾端，可驗證兩個 pointer 的回捲。
        pop(8'h33);
        pop(8'h44);
        pop(8'h55);
        pop(8'h66);

        // empty 時讀取，count 與 rd_data 都不應改變。
        held_rd_data = rd_data;
        @(negedge clk);
        rd_en = 1'b1;
        @(posedge clk);
        #1;
        rd_en = 1'b0;
        if (rd_data !== held_rd_data) begin
            error_count = error_count + 1;
            $display("[FAIL] empty read 改變了 rd_data。");
        end
        check_flags("empty 拒絕讀取");

        if (error_count == 0)
            $display("[PASS] 全部同步 FIFO 測試通過。");
        else
            $fatal(1, "[FAIL] 共有 %0d 個 FIFO 測試失敗。", error_count);
        $finish;
    end

    initial begin
        #(300*CLK_PERIOD);
        $fatal(1, "[FAIL] FIFO 模擬逾時。");
    end
endmodule
