`timescale 1ns/1ps

module tb_parameterized_adder;
    localparam integer WIDTH = 8;

    logic [WIDTH-1:0] a;
    logic [WIDTH-1:0] b;
    logic [WIDTH-1:0] sum;
    logic             carry_out;
    logic             overflow;
    integer           error_count = 0;

    parameterized_adder #(.WIDTH(WIDTH)) dut (
        .a(a), .b(b), .sum(sum),
        .carry_out(carry_out), .overflow(overflow)
    );

    task automatic check_case(
        input logic [WIDTH-1:0] test_a,
        input logic [WIDTH-1:0] test_b
    );
        logic [WIDTH:0] expected_extended;
        logic             expected_overflow;
        begin
            a = test_a;
            b = test_b;
            #1;
            expected_extended = {1'b0, test_a} + {1'b0, test_b};
            expected_overflow = (test_a[WIDTH-1] == test_b[WIDTH-1]) &&
                                (expected_extended[WIDTH-1] != test_a[WIDTH-1]);

            if ({carry_out, sum} !== expected_extended ||
                overflow !== expected_overflow) begin
                error_count = error_count + 1;
                $display("[FAIL] a=%h b=%h -> {%b,%h} ov=%b；預期 %h ov=%b",
                         a, b, carry_out, sum, overflow,
                         expected_extended, expected_overflow);
            end else begin
                $display("[OK] a=%h b=%h -> sum=%h carry=%b ov=%b",
                         a, b, sum, carry_out, overflow);
            end
        end
    endtask

    initial begin
        $display("=== Solution：參數化加法器 self-checking TB ===");
        check_case(8'h00, 8'h00);
        check_case(8'h12, 8'h34);
        check_case(8'hff, 8'h01); // unsigned carry，無 signed overflow
        check_case(8'h7f, 8'h01); // 正 + 正變成負
        check_case(8'h80, 8'hff); // 負 + 負變成正
        check_case(8'h80, 8'h80); // -128 + -128
        check_case(8'hff, 8'hff); // -1 + -1，不 overflow
        check_case(8'h55, 8'haa);

        if (error_count == 0)
            $display("[PASS] 全部加法器測試通過。");
        else
            $fatal(1, "[FAIL] 共有 %0d 個加法器測試失敗。", error_count);
        $finish;
    end
endmodule
