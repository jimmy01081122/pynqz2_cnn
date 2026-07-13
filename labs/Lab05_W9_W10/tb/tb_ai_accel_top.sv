`timescale 1ns/1ps

module tb_ai_accel_top #(
    parameter integer DATA_WIDTH  = 8,
    parameter integer ENABLE_2TO4 = 0
);
    localparam integer ACC_WIDTH = 32;
    localparam integer PES = 4;

    logic clk;
    logic rst_n;
    logic in_valid;
    logic in_ready;
    logic [4*DATA_WIDTH-1:0] in_activations;
    logic [PES*4*DATA_WIDTH-1:0] in_dense_weights;
    logic [PES*2*DATA_WIDTH-1:0] in_sparse_values;
    logic [PES*4-1:0] in_sparse_masks;
    logic [PES*ACC_WIDTH-1:0] in_bias;
    logic out_valid;
    logic out_ready;
    logic [PES*ACC_WIDTH-1:0] out_result;
    logic out_mask_error;

    integer errors;

    ai_accel_top #(
        .DATA_WIDTH(DATA_WIDTH),
        .ENABLE_2TO4(ENABLE_2TO4),
        .ACC_WIDTH(ACC_WIDTH),
        .PES(PES)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .in_valid(in_valid),
        .in_ready(in_ready),
        .in_activations(in_activations),
        .in_dense_weights(in_dense_weights),
        .in_sparse_values(in_sparse_values),
        .in_sparse_masks(in_sparse_masks),
        .in_bias(in_bias),
        .out_valid(out_valid),
        .out_ready(out_ready),
        .out_result(out_result),
        .out_mask_error(out_mask_error)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    // A broken combinational network must fail quickly instead of hanging CI.
    initial begin
        #5000;
        $fatal(1, "[FAIL] Lab05 TB watchdog timeout");
    end

    task automatic record_error(input string message);
        begin
            errors = errors + 1;
            $display("[ERROR] %s (time=%0t)", message, $time);
        end
    endtask

    task automatic set_activation(input integer lane, input integer value);
        in_activations[lane*DATA_WIDTH +: DATA_WIDTH] = value;
    endtask

    task automatic set_dense_weight(
        input integer pe,
        input integer lane,
        input integer value
    );
        in_dense_weights[(pe*4+lane)*DATA_WIDTH +: DATA_WIDTH] = value;
    endtask

    task automatic set_sparse_value(
        input integer pe,
        input integer value_index,
        input integer value
    );
        in_sparse_values[(pe*2+value_index)*DATA_WIDTH +: DATA_WIDTH] = value;
    endtask

    task automatic set_bias(input integer pe, input integer value);
        in_bias[pe*ACC_WIDTH +: ACC_WIDTH] = value;
    endtask

    task automatic load_vectors;
        begin
            in_activations   = '0;
            in_dense_weights = '0;
            in_sparse_values = '0;
            in_sparse_masks  = 16'hC3A5;
            in_bias          = '0;

            set_activation(0, 1);
            set_activation(1, 2);
            set_activation(2, 3);
            set_activation(3, 4);

            set_dense_weight(0, 0,  1); set_dense_weight(0, 1,  1);
            set_dense_weight(0, 2,  1); set_dense_weight(0, 3,  1);
            set_dense_weight(1, 0, -1); set_dense_weight(1, 1,  2);
            set_dense_weight(1, 2,  0); set_dense_weight(1, 3,  3);
            set_dense_weight(2, 0,  2); set_dense_weight(2, 1, -2);
            set_dense_weight(2, 2,  2); set_dense_weight(2, 3, -2);
            set_dense_weight(3, 0, -3); set_dense_weight(3, 1, -1);
            set_dense_weight(3, 2,  1); set_dense_weight(3, 3,  3);

            // masks: PE0=0101, PE1=1010, PE2=0011, PE3=1100.
            set_sparse_value(0, 0,  1); set_sparse_value(0, 1,  2);
            set_sparse_value(1, 0, -1); set_sparse_value(1, 1,  1);
            set_sparse_value(2, 0,  2); set_sparse_value(2, 1, -2);
            set_sparse_value(3, 0,  1); set_sparse_value(3, 1, -2);

            set_bias(0,  1);
            set_bias(1, -2);
            set_bias(2,  4);
            set_bias(3,  5);
        end
    endtask

    task automatic check_outputs(
        input integer expected0,
        input integer expected1,
        input integer expected2,
        input integer expected3,
        input logic expected_mask_error
    );
        integer got;
        begin
            got = $signed(out_result[0*ACC_WIDTH +: ACC_WIDTH]);
            if (got != expected0)
                record_error($sformatf("PE0 expected %0d, got %0d", expected0, got));
            got = $signed(out_result[1*ACC_WIDTH +: ACC_WIDTH]);
            if (got != expected1)
                record_error($sformatf("PE1 expected %0d, got %0d", expected1, got));
            got = $signed(out_result[2*ACC_WIDTH +: ACC_WIDTH]);
            if (got != expected2)
                record_error($sformatf("PE2 expected %0d, got %0d", expected2, got));
            got = $signed(out_result[3*ACC_WIDTH +: ACC_WIDTH]);
            if (got != expected3)
                record_error($sformatf("PE3 expected %0d, got %0d", expected3, got));
            if (out_mask_error !== expected_mask_error)
                record_error($sformatf(
                    "mask_error expected %0b, got %0b",
                    expected_mask_error, out_mask_error
                ));
        end
    endtask

    task automatic push_stall_check(
        input integer expected0,
        input integer expected1,
        input integer expected2,
        input integer expected3,
        input logic expected_mask_error
    );
        integer cycle;
        reg [PES*ACC_WIDTH-1:0] held_result;
        reg held_mask_error;
        begin
            out_ready = 1'b0;
            @(negedge clk);
            in_valid = 1'b1;
            while (!in_ready)
                @(negedge clk);
            @(negedge clk);
            in_valid = 1'b0;
            while (!out_valid)
                @(negedge clk);

            check_outputs(expected0, expected1, expected2, expected3, expected_mask_error);
            if (in_ready !== 1'b0)
                record_error("in_ready must be low while the output register is stalled");
            held_result = out_result;
            held_mask_error = out_mask_error;
            for (cycle = 0; cycle < 3; cycle = cycle + 1) begin
                @(posedge clk);
                #1;
                if (!out_valid || out_result !== held_result ||
                    out_mask_error !== held_mask_error)
                    record_error("elastic output changed under backpressure");
            end

            @(negedge clk);
            out_ready = 1'b1;
            @(posedge clk);
            #1;
            @(negedge clk);
            out_ready = 1'b0;
        end
    endtask

    initial begin
        errors = 0;
        rst_n = 1'b0;
        in_valid = 1'b0;
        out_ready = 1'b0;
        load_vectors();

        repeat (3) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        // Nominal transaction plus a three-cycle output stall.
        if (ENABLE_2TO4 != 0)
            push_stall_check(8, 0, 2, 0, 1'b0);
        else
            push_stall_check(11, 13, 0, 15, 1'b0);

        // PE2 mask 0001 is invalid only in sparse mode. Its safe result is bias.
        in_sparse_masks[2*4 +: 4] = 4'b0001;
        if (ENABLE_2TO4 != 0)
            push_stall_check(8, 0, 4, 0, 1'b1);
        else
            push_stall_check(11, 13, 0, 15, 1'b0);

        // Restore masks, enqueue one result, then consume-and-replace it in the
        // same edge. out_valid must remain asserted with the replacement data.
        in_sparse_masks = 16'hC3A5;
        @(negedge clk);
        in_valid = 1'b1;
        out_ready = 1'b0;
        @(negedge clk);
        in_valid = 1'b0;
        while (!out_valid)
            @(negedge clk);
        if (ENABLE_2TO4 != 0)
            check_outputs(8, 0, 2, 0, 1'b0);
        else
            check_outputs(11, 13, 0, 15, 1'b0);

        @(negedge clk);
        set_bias(0, 20);
        in_valid = 1'b1;
        out_ready = 1'b1;
        @(posedge clk);
        #1;
        if (!out_valid)
            record_error("out_valid dropped during simultaneous consume-and-replace");
        if (ENABLE_2TO4 != 0)
            check_outputs(27, 0, 2, 0, 1'b0);
        else
            check_outputs(30, 13, 0, 15, 1'b0);
        @(negedge clk);
        in_valid = 1'b0;
        out_ready = 1'b0;

        // Consume the replacement transaction.
        @(negedge clk);
        out_ready = 1'b1;
        @(posedge clk);
        #1;
        @(negedge clk);
        out_ready = 1'b0;

        repeat (2) @(posedge clk);
        if (errors == 0) begin
            $display(
                "[PASS] Lab05 DATA_WIDTH=%0d ENABLE_2TO4=%0d four-PE arithmetic, invalid-mask, backpressure, and elastic replacement.",
                DATA_WIDTH, ENABLE_2TO4
            );
            $finish;
        end else begin
            $fatal(1, "[FAIL] Lab05 DATA_WIDTH=%0d ENABLE_2TO4=%0d found %0d error(s).",
                   DATA_WIDTH, ENABLE_2TO4, errors);
        end
    end
endmodule
