`timescale 1ns/1ps

module tb_pynq_z2_adder_demo;
    logic [1:0] sw;
    logic [3:0] led;
    integer value;
    integer expected;

    pynq_z2_adder_demo dut (
        .sw(sw),
        .led(led)
    );

    initial begin
        for (value = 0; value < 4; value = value + 1) begin
            sw = value[1:0];
            #1;
            expected = sw[0] + sw[1];
            if (led !== expected[3:0])
                $fatal(1, "[FAIL] sw=%b expected led=%b, got %b", sw, expected[3:0], led);
        end
        $display("[PASS] PYNQ-Z2 combinational adder tested all four switch settings.");
        $finish;
    end
endmodule
