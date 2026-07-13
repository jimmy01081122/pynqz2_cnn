`timescale 1ns/1ps

module tb_sparse_array;
    localparam integer DATA_WIDTH = 8;
    localparam integer ACC_WIDTH  = 32;
    localparam integer PES        = 4;

    logic clk;
    logic rst_n;
    logic in_valid;
    logic in_ready;
    logic [31:0] in_activations;
    logic [63:0] in_sparse_values;
    logic [15:0] in_sparse_masks;
    logic [127:0] in_bias;
    logic in_clear_acc;
    logic signed [15:0] in_multiplier;
    logic [5:0] in_shift;
    logic signed [15:0] in_zero_point;
    logic out_valid;
    logic out_ready;
    logic [127:0] out_acc;
    logic [31:0] out_q;
    logic out_mask_error;

    logic [15:0] decoder_values;
    logic [3:0] decoder_mask;
    logic [31:0] decoder_dense;
    logic decoder_ok;

    logic signed [31:0] rq_acc;
    logic signed [15:0] rq_multiplier;
    logic [5:0] rq_shift;
    logic signed [15:0] rq_zero_point;
    logic signed [7:0] rq_out;

    integer errors;

    sparse_array_4x4 dut (
        .clk(clk),
        .rst_n(rst_n),
        .in_valid(in_valid),
        .in_ready(in_ready),
        .in_activations(in_activations),
        .in_sparse_values(in_sparse_values),
        .in_sparse_masks(in_sparse_masks),
        .in_bias(in_bias),
        .in_clear_acc(in_clear_acc),
        .in_multiplier(in_multiplier),
        .in_shift(in_shift),
        .in_zero_point(in_zero_point),
        .out_valid(out_valid),
        .out_ready(out_ready),
        .out_acc(out_acc),
        .out_q(out_q),
        .out_mask_error(out_mask_error)
    );

    sparse_2of4_decoder decoder_unit_test (
        .sparse_values(decoder_values),
        .mask(decoder_mask),
        .dense_values(decoder_dense),
        .mask_ok(decoder_ok)
    );

    requantize requant_unit_test (
        .acc_in(rq_acc),
        .multiplier(rq_multiplier),
        .shift(rq_shift),
        .zero_point(rq_zero_point),
        .q_out(rq_out)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    task automatic record_error(input string message);
        begin
            errors = errors + 1;
            $display("[ERROR] %s (time=%0t)", message, $time);
        end
    endtask

    task automatic check_lane (
        input integer lane,
        input integer expected_acc,
        input integer expected_q
    );
        integer got_acc;
        integer got_q;
        begin
            got_acc = $signed(out_acc[lane*ACC_WIDTH +: ACC_WIDTH]);
            got_q   = $signed(out_q[lane*8 +: 8]);
            if (got_acc != expected_acc)
                record_error($sformatf("PE%0d acc expected %0d, got %0d", lane, expected_acc, got_acc));
            if (got_q != expected_q)
                record_error($sformatf("PE%0d q expected %0d, got %0d", lane, expected_q, got_q));
        end
    endtask

    task automatic send_and_check (
        input logic clear_acc,
        input logic [15:0] masks,
        input logic expected_mask_error,
        input integer e_acc0,
        input integer e_acc1,
        input integer e_acc2,
        input integer e_acc3,
        input integer e_q0,
        input integer e_q1,
        input integer e_q2,
        input integer e_q3
    );
        integer k;
        reg [127:0] held_acc;
        reg [31:0] held_q;
        begin
            out_ready = 1'b0;
            @(negedge clk);
            in_clear_acc    = clear_acc;
            in_sparse_masks = masks;
            in_valid        = 1'b1;
            while (!in_ready)
                @(negedge clk);

            @(negedge clk);
            in_valid = 1'b0;
            while (!out_valid)
                @(negedge clk);

            check_lane(0, e_acc0, e_q0);
            check_lane(1, e_acc1, e_q1);
            check_lane(2, e_acc2, e_q2);
            check_lane(3, e_acc3, e_q3);
            if (out_mask_error !== expected_mask_error)
                record_error($sformatf("mask_error expected %0b, got %0b", expected_mask_error, out_mask_error));

            held_acc = out_acc;
            held_q   = out_q;
            for (k = 0; k < 2; k = k + 1) begin
                @(posedge clk);
                #1;
                if (!out_valid || (out_acc !== held_acc) || (out_q !== held_q))
                    record_error("array output changed while out_ready=0");
            end

            @(negedge clk);
            out_ready = 1'b1;
            @(negedge clk);
            out_ready = 1'b0;
        end
    endtask

    initial begin
        errors           = 0;
        rst_n            = 1'b0;
        in_valid         = 1'b0;
        in_activations   = 32'h0403_0201; // lanes [1,2,3,4]
        in_sparse_values = {16'hFE01, 16'h0302, 16'h01FF, 16'h0201};
        in_sparse_masks  = 16'hC3A5;
        in_bias          = '0;
        in_bias[0*32 +: 32] = 32'sd10;
        in_bias[1*32 +: 32] = 32'sd0;
        in_bias[2*32 +: 32] = -32'sd8;
        in_bias[3*32 +: 32] = 32'sd5;
        in_clear_acc     = 1'b0;
        in_multiplier    = 16'sd1;
        in_shift         = 6'd0;
        in_zero_point    = 16'sd0;
        out_ready        = 1'b0;

        decoder_values = 16'hFE03; // value0=3, value1=-2
        decoder_mask   = 4'b1010;  // lane1=3, lane3=-2
        #1;
        if (!decoder_ok || decoder_dense !== 32'hFE00_0300)
            record_error("2:4 decoder valid-mask test failed");
        decoder_mask = 4'b0001;
        #1;
        if (decoder_ok || decoder_dense !== 32'h0000_0000)
            record_error("2:4 decoder invalid mask must report error and output zero");

        // Standalone requantization checks: symmetric rounding and saturation.
        rq_acc = 32'sd7; rq_multiplier = 16'sd3; rq_shift = 6'd1; rq_zero_point = 16'sd0; #1;
        if ($signed(rq_out) != 11) record_error("requant +21/2 should round to +11");
        rq_acc = -32'sd7; #1;
        if ($signed(rq_out) != -11) record_error("requant -21/2 should round to -11");
        rq_acc = 32'sd200; rq_multiplier = 16'sd1; rq_shift = 6'd0; #1;
        if ($signed(rq_out) != 127) record_error("requant positive saturation failed");
        rq_acc = -32'sd200; #1;
        if ($signed(rq_out) != -128) record_error("requant negative saturation failed");

        repeat (3) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        // PE dots are [7, 2, 8, -5]. clear_acc adds biases [10,0,-8,5].
        send_and_check(1'b1, 16'hC3A5, 1'b0,
                       17, 2, 0, 0, 17, 2, 0, 0);

        // A second identical group accumulates once more.
        send_and_check(1'b0, 16'hC3A5, 1'b0,
                       24, 4, 8, -5, 24, 4, 8, -5);

        // PE2 mask has only one bit. Its decoder emits zero; other PEs continue.
        send_and_check(1'b0, 16'hC1A5, 1'b1,
                       31, 6, 8, -10, 31, 6, 8, -10);

        repeat (2) @(posedge clk);
        if (errors == 0) begin
            $display("[PASS] Lab03 decoder, sparse array, requant, and backpressure tests passed.");
            $finish;
        end else begin
            $fatal(1, "[FAIL] Lab03 found %0d error(s).", errors);
        end
    end
endmodule
