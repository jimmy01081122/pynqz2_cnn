`timescale 1ns/1ps

module tb_axis_dot_accelerator;
    logic aclk;
    logic aresetn;
    logic [31:0] s_axis_tdata;
    logic [3:0] s_axis_tkeep;
    logic s_axis_tvalid;
    logic s_axis_tready;
    logic s_axis_tlast;
    logic [31:0] m_axis_tdata;
    logic [3:0] m_axis_tkeep;
    logic m_axis_tvalid;
    logic m_axis_tready;
    logic m_axis_tlast;
    logic cfg_mode_int4;
    logic cfg_enable_2to4;
    logic cfg_clear_status;
    logic [31:0] cfg_weight_tdata;
    logic [31:0] cfg_bias;
    logic status_mask_error;

    integer errors;

    axis_dot_accelerator dut (
        .aclk(aclk),
        .aresetn(aresetn),
        .s_axis_tdata(s_axis_tdata),
        .s_axis_tkeep(s_axis_tkeep),
        .s_axis_tvalid(s_axis_tvalid),
        .s_axis_tready(s_axis_tready),
        .s_axis_tlast(s_axis_tlast),
        .m_axis_tdata(m_axis_tdata),
        .m_axis_tkeep(m_axis_tkeep),
        .m_axis_tvalid(m_axis_tvalid),
        .m_axis_tready(m_axis_tready),
        .m_axis_tlast(m_axis_tlast),
        .cfg_mode_int4(cfg_mode_int4),
        .cfg_enable_2to4(cfg_enable_2to4),
        .cfg_clear_status(cfg_clear_status),
        .cfg_weight_tdata(cfg_weight_tdata),
        .cfg_bias(cfg_bias),
        .status_mask_error(status_mask_error)
    );

    initial aclk = 1'b0;
    always #5 aclk = ~aclk;

    task automatic record_error (input string message);
        begin
            errors = errors + 1;
            $display("[ERROR] %s (time=%0t)", message, $time);
        end
    endtask

    task automatic pulse_clear_status;
        begin
            @(negedge aclk);
            cfg_clear_status = 1'b1;
            @(negedge aclk);
            cfg_clear_status = 1'b0;
            #1;
            if (status_mask_error !== 1'b0)
                record_error("cfg_clear_status did not clear sticky mask error");
        end
    endtask

    task automatic send_and_check (
        input logic [31:0] data,
        input logic last,
        input integer expected,
        input integer stall_cycles,
        input logic expected_status
    );
        integer k;
        reg [31:0] held_data;
        reg [3:0] held_keep;
        reg held_last;
        begin
            m_axis_tready = 1'b0;
            @(negedge aclk);
            s_axis_tdata  = data;
            s_axis_tkeep  = 4'b1111;
            s_axis_tlast  = last;
            s_axis_tvalid = 1'b1;

            while (!s_axis_tready)
                @(negedge aclk);

            @(negedge aclk);
            s_axis_tvalid = 1'b0;

            while (!m_axis_tvalid)
                @(negedge aclk);

            if ($signed(m_axis_tdata) !== expected)
                record_error($sformatf("TDATA expected %0d, got %0d", expected, $signed(m_axis_tdata)));
            if (m_axis_tlast !== last)
                record_error($sformatf("TLAST expected %0b, got %0b", last, m_axis_tlast));
            if (m_axis_tkeep !== 4'b1111)
                record_error("TKEEP was not propagated");
            if (status_mask_error !== expected_status)
                record_error($sformatf("mask status expected %0b, got %0b", expected_status, status_mask_error));
            if (s_axis_tready !== 1'b0)
                record_error("S_AXIS TREADY must be low while output is full and stalled");

            held_data = m_axis_tdata;
            held_keep = m_axis_tkeep;
            held_last = m_axis_tlast;
            for (k = 0; k < stall_cycles; k = k + 1) begin
                @(posedge aclk);
                #1;
                if (!m_axis_tvalid)
                    record_error("M_AXIS TVALID dropped before handshake");
                if ((m_axis_tdata !== held_data) || (m_axis_tkeep !== held_keep) ||
                    (m_axis_tlast !== held_last))
                    record_error("M_AXIS TDATA/TKEEP/TLAST changed under backpressure");
            end

            @(negedge aclk);
            m_axis_tready = 1'b1;
            @(negedge aclk);
            m_axis_tready = 1'b0;
        end
    endtask

    initial begin
        errors           = 0;
        aresetn          = 1'b0;
        s_axis_tdata     = '0;
        s_axis_tkeep     = 4'b1111;
        s_axis_tvalid    = 1'b0;
        s_axis_tlast     = 1'b0;
        m_axis_tready    = 1'b0;
        cfg_mode_int4    = 1'b0;
        cfg_enable_2to4  = 1'b0;
        cfg_clear_status = 1'b0;
        cfg_weight_tdata = 32'h0101_0101;
        cfg_bias         = 32'd5;

        repeat (3) @(posedge aclk);
        @(negedge aclk);
        aresetn = 1'b1;

        // 1) Dense INT8, two-beat packet: [15, 19].
        send_and_check(32'h0403_0201, 1'b0, 15, 3, 1'b0);
        send_and_check(32'h0101_0101, 1'b1, 19, 2, 1'b0);

        // 2) Dense INT4: -3 + dot([1,2,3,4,5,6,7,-8], all ones)=17.
        cfg_mode_int4    = 1'b1;
        cfg_enable_2to4  = 1'b0;
        cfg_weight_tdata = 32'h1111_1111;
        cfg_bias         = 32'hFFFF_FFFD;
        send_and_check(32'h8765_4321, 1'b1, 17, 4, 1'b0);

        // 3) Sparse INT8: mask 0101, values [1,2] -> row [1,0,2,0].
        cfg_mode_int4    = 1'b0;
        cfg_enable_2to4  = 1'b1;
        cfg_weight_tdata = 32'h0005_0201;
        cfg_bias         = 32'd10;
        pulse_clear_status();
        send_and_check(32'h0403_0201, 1'b1, 17, 2, 1'b0);

        // 4) Sparse INT4: g0 mask 0101 values [1,2] -> +7;
        //    g1 mask 1010 values [-1,1] -> -14; bias 3 gives -4.
        cfg_mode_int4    = 1'b1;
        cfg_enable_2to4  = 1'b1;
        cfg_weight_tdata = 32'h00A5_1F21;
        cfg_bias         = 32'd3;
        send_and_check(32'h8765_4321, 1'b1, -4, 3, 1'b0);

        // Invalid INT8 mask 0001: this beat's dot is zero, output is bias, status sticks.
        cfg_mode_int4    = 1'b0;
        cfg_enable_2to4  = 1'b1;
        cfg_weight_tdata = 32'h0001_0201;
        cfg_bias         = 32'd7;
        pulse_clear_status();
        send_and_check(32'h0403_0201, 1'b1, 7, 2, 1'b1);

        // Sticky means a later valid dense beat does not hide the earlier error.
        cfg_enable_2to4  = 1'b0;
        cfg_weight_tdata = 32'h0101_0101;
        cfg_bias         = 32'd0;
        send_and_check(32'h0000_0001, 1'b1, 1, 1, 1'b1);
        pulse_clear_status();

        repeat (2) @(posedge aclk);
        if (errors == 0) begin
            $display("[PASS] Lab04 dense/sparse INT8/INT4, invalid-mask, TLAST, and backpressure tests passed.");
            $finish;
        end else begin
            $fatal(1, "[FAIL] Lab04 found %0d error(s).", errors);
        end
    end
endmodule
