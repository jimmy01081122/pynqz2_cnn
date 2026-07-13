`timescale 1ns/1ps

module tb_dense_int_pe;
    localparam integer ACC_WIDTH = 32;

    logic clk;
    logic rst_n;
    logic in_valid;
    logic in_ready;
    logic [31:0] in_activation;
    logic [31:0] in_weight;
    logic in_mode_int4;
    logic in_clear_acc;
    logic in_last;
    logic out_valid;
    logic out_ready;
    logic signed [ACC_WIDTH-1:0] out_acc;
    logic out_last;

    integer errors;

    dense_int_pe #(
        .ACC_WIDTH(ACC_WIDTH)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .in_valid(in_valid),
        .in_ready(in_ready),
        .in_activation(in_activation),
        .in_weight(in_weight),
        .in_mode_int4(in_mode_int4),
        .in_clear_acc(in_clear_acc),
        .in_last(in_last),
        .out_valid(out_valid),
        .out_ready(out_ready),
        .out_acc(out_acc),
        .out_last(out_last)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    task automatic record_error(input string message);
        begin
            errors = errors + 1;
            $display("[ERROR] %s (time=%0t)", message, $time);
        end
    endtask

    // Send one item while deliberately holding the output for three clocks.
    // This simultaneously checks arithmetic, ready/valid, and output stability.
    task automatic send_and_check (
        input logic [31:0] activation,
        input logic [31:0] weight,
        input logic mode_int4,
        input logic clear_acc,
        input logic last,
        input integer expected_acc
    );
        integer k;
        reg signed [ACC_WIDTH-1:0] held_acc;
        reg held_last;
        begin
            out_ready = 1'b0;
            @(negedge clk);
            in_activation = activation;
            in_weight     = weight;
            in_mode_int4  = mode_int4;
            in_clear_acc  = clear_acc;
            in_last       = last;
            in_valid      = 1'b1;

            while (!in_ready)
                @(negedge clk);

            // The transfer occurs at the next rising edge.
            @(negedge clk);
            in_valid = 1'b0;

            while (!out_valid)
                @(negedge clk);

            if ($signed(out_acc) !== expected_acc)
                record_error($sformatf("acc expected %0d, got %0d", expected_acc, $signed(out_acc)));
            if (out_last !== last)
                record_error($sformatf("last expected %0b, got %0b", last, out_last));
            if (in_ready !== 1'b0)
                record_error("in_ready must be low while the full output register is stalled");

            held_acc  = out_acc;
            held_last = out_last;
            for (k = 0; k < 3; k = k + 1) begin
                @(posedge clk);
                #1;
                if (!out_valid)
                    record_error("out_valid dropped during backpressure");
                if ((out_acc !== held_acc) || (out_last !== held_last))
                    record_error("out_acc/out_last changed during backpressure");
            end

            @(negedge clk);
            out_ready = 1'b1;
            @(negedge clk);
            out_ready = 1'b0;
        end
    endtask

    initial begin
        errors         = 0;
        rst_n          = 1'b0;
        in_valid       = 1'b0;
        in_activation  = '0;
        in_weight      = '0;
        in_mode_int4   = 1'b0;
        in_clear_acc   = 1'b0;
        in_last        = 1'b0;
        out_ready      = 1'b0;

        repeat (3) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        // INT8 lanes are [1,2,3,4], LSB lane first. Dot with itself = 30.
        send_and_check(32'h0403_0201, 32'h0403_0201, 1'b0, 1'b1, 1'b0, 30);

        // Add dot([1,1,1,1], [1,2,3,4]) = 10. Accumulator becomes 40.
        send_and_check(32'h0101_0101, 32'h0403_0201, 1'b0, 1'b0, 1'b1, 40);

        // INT4 lanes in 0x87654321 are [1,2,3,4,5,6,7,-8].
        // Dot with eight +1 weights = 20. clear_acc starts a new sum.
        send_and_check(32'h8765_4321, 32'h1111_1111, 1'b1, 1'b1, 1'b0, 20);

        // Eight -1 activations times eight +1 weights add -8 -> 12.
        send_and_check(32'hFFFF_FFFF, 32'h1111_1111, 1'b1, 1'b0, 1'b1, 12);

        repeat (2) @(posedge clk);
        if (errors == 0) begin
            $display("[PASS] Lab02 dense INT8/INT4 PE and backpressure tests passed.");
            $finish;
        end else begin
            $fatal(1, "[FAIL] Lab02 found %0d error(s).", errors);
        end
    end

endmodule
