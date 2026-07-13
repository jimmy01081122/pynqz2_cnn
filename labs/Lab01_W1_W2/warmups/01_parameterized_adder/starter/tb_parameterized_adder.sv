`timescale 1ns/1ps

module tb_parameterized_adder;
    localparam integer WIDTH = 8;

    logic [WIDTH-1:0] a;
    logic [WIDTH-1:0] b;
    logic [WIDTH-1:0] sum;
    logic             carry_out;
    logic             overflow;

    // TODO 4：完成全部測試案例後改成 1'b1。
    logic tb_todos_done = 1'b0;

    parameterized_adder #(.WIDTH(WIDTH)) dut (
        .a(a), .b(b), .sum(sum),
        .carry_out(carry_out), .overflow(overflow)
    );

    task automatic check_case(
        input logic [WIDTH-1:0] test_a,
        input logic [WIDTH-1:0] test_b,
        input logic [WIDTH-1:0] expected_sum,
        input logic             expected_carry,
        input logic             expected_overflow
    );
        begin
            a = test_a;
            b = test_b;
            #1;
            if ((sum !== expected_sum) ||
                (carry_out !== expected_carry) ||
                (overflow !== expected_overflow)) begin
                $display("[FAIL] a=%h b=%h -> sum=%h carry=%b ov=%b；預期 %h %b %b",
                         a, b, sum, carry_out, overflow,
                         expected_sum, expected_carry, expected_overflow);
                $fatal(1, "[TODO] 請完成 parameterized_adder.sv 的輸出與 overflow TODO。");
            end
            $display("[OK] a=%h b=%h -> sum=%h carry=%b ov=%b",
                     a, b, sum, carry_out, overflow);
        end
    endtask

    initial begin
        $display("=== Starter：參數化加法器 ===");
        a = '0;
        b = '0;

        // 已提供一個 smoke test，確認接線與基本功能。
        check_case(8'h01, 8'h01, 8'h02, 1'b0, 1'b0);

        // TODO 5：在此呼叫 check_case，加入一般、carry、正 overflow、負 overflow 測試。

        if (!tb_todos_done)
            $fatal(1, "[TODO] DUT smoke test 已過；請補齊 TB 測試並設定 tb_todos_done=1。");

        $display("[PASS] Starter 的 DUT 與 TB TODO 均已完成。");
        $finish;
    end
endmodule
