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
    logic signed [ACC_WIDTH-1:0] model_acc;
    integer error_count = 0;

    always #(CLK_PERIOD/2) clk = ~clk;

    valid_ready_mac #(
        .DATA_WIDTH(DATA_WIDTH), .ACC_WIDTH(ACC_WIDTH)
    ) dut (
        .clk(clk), .rst_n(rst_n),
        .in_valid(in_valid), .in_ready(in_ready), .a(a), .b(b),
        .out_valid(out_valid), .out_ready(out_ready), .out_data(out_data)
    );

    task automatic expect_output(
        input logic signed [ACC_WIDTH-1:0] expected,
        input string label_text
    );
        begin
            if (!out_valid || ($signed(out_data) !== expected)) begin
                error_count = error_count + 1;
                $display("[FAIL] %s：valid=%b data=%0d，預期 valid=1 data=%0d",
                         label_text, out_valid, $signed(out_data), expected);
            end else begin
                $display("[OK] %s：累加值=%0d", label_text, $signed(out_data));
            end
        end
    endtask

    task automatic send_stalled(
        input logic signed [DATA_WIDTH-1:0] op_a,
        input logic signed [DATA_WIDTH-1:0] op_b,
        input integer stall_cycles,
        input string label_text
    );
        logic signed [ACC_WIDTH-1:0] held_value;
        integer i;
        begin
            @(negedge clk);
            if (!in_ready) begin
                error_count = error_count + 1;
                $display("[FAIL] %s：輸出格應為空，但 in_ready=0。", label_text);
            end
            a          = op_a;
            b          = op_b;
            in_valid   = 1'b1;
            out_ready  = 1'b0;

            @(posedge clk);
            #1;
            in_valid = 1'b0;
            model_acc = model_acc + ($signed(op_a) * $signed(op_b));
            expect_output(model_acc, label_text);
            held_value = out_data;

            for (i = 0; i < stall_cycles; i = i + 1) begin
                @(posedge clk);
                #1;
                if (!out_valid || out_data !== held_value || in_ready !== 1'b0) begin
                    error_count = error_count + 1;
                    $display("[FAIL] %s：backpressure cycle %0d 未保持輸出或 in_ready。",
                             label_text, i);
                end
            end

            @(negedge clk);
            out_ready = 1'b1;
            @(posedge clk);
            #1;
            if (out_valid !== 1'b0) begin
                error_count = error_count + 1;
                $display("[FAIL] %s：output handshake 後 out_valid 應清除。", label_text);
            end
            @(negedge clk);
            out_ready = 1'b0;
        end
    endtask

    task automatic check_back_to_back;
        begin
            @(negedge clk);
            out_ready = 1'b1;
            in_valid  = 1'b1;
            a         = 8'sd4;
            b         = 8'sd5;
            @(posedge clk);
            #1;
            model_acc = model_acc + 24'sd20;
            expect_output(model_acc, "back-to-back 第 1 筆");

            @(negedge clk);
            // out_ready 仍為 1：此上升緣同時取走舊輸出、接收新輸入。
            a = -8'sd3;
            b =  8'sd7;
            @(posedge clk);
            #1;
            model_acc = model_acc - 24'sd21;
            expect_output(model_acc, "back-to-back 第 2 筆");

            @(negedge clk);
            in_valid = 1'b0;
            @(posedge clk);
            #1;
            if (out_valid !== 1'b0) begin
                error_count = error_count + 1;
                $display("[FAIL] back-to-back 最後一筆取走後 out_valid 未清除。");
            end
            @(negedge clk);
            out_ready = 1'b0;
        end
    endtask

    initial begin
        $display("=== Solution：valid/ready MAC self-checking TB ===");
        rst_n     = 1'b0;
        in_valid  = 1'b0;
        out_ready = 1'b0;
        a          = '0;
        b          = '0;
        model_acc  = '0;

        repeat (2) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        send_stalled( 8'sd2,  8'sd3, 2, "正數 + backpressure");
        send_stalled(-8'sd4,  8'sd5, 1, "負數乘法");
        send_stalled(-8'sd2, -8'sd6, 0, "負負得正");
        check_back_to_back();

        if (error_count == 0)
            $display("[PASS] 全部 valid/ready MAC 測試通過。");
        else
            $fatal(1, "[FAIL] 共有 %0d 個 MAC 測試失敗。", error_count);
        $finish;
    end

    initial begin
        #(200*CLK_PERIOD);
        $fatal(1, "[FAIL] 模擬逾時，可能有握手死結。");
    end
endmodule
