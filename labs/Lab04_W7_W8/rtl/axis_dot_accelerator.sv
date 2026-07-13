`timescale 1ns/1ps

// AXI4-Stream packed dot-product accelerator.
//
// Runtime modes:
//   cfg_enable_2to4=0, cfg_mode_int4=0: dense 4-lane signed INT8
//   cfg_enable_2to4=0, cfg_mode_int4=1: dense 8-lane signed INT4
//   cfg_enable_2to4=1, cfg_mode_int4=0: one sparse 2:4 INT8 group
//   cfg_enable_2to4=1, cfg_mode_int4=1: two sparse 2:4 INT4 groups
//
// Sparse cfg_weight_tdata format:
//   INT8: [7:0]=value0, [15:8]=value1, [19:16]=mask.
//   INT4: [3:0]=g0v0, [7:4]=g0v1, [11:8]=g1v0, [15:12]=g1v1,
//         [19:16]=group0 mask, [23:20]=group1 mask.
// Values are consumed from the lowest asserted mask lane toward the highest.
module axis_dot_accelerator (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 aclk CLK" *)
    (* X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF S_AXIS:M_AXIS, ASSOCIATED_RESET aresetn, FREQ_HZ 100000000" *)
    input  logic        aclk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 aresetn RST" *)
    (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
    input  logic        aresetn,

    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TDATA" *)
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME S_AXIS, TDATA_NUM_BYTES 4, HAS_TLAST 1, HAS_TKEEP 1" *)
    input  logic [31:0] s_axis_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TKEEP" *)
    input  logic [3:0]  s_axis_tkeep,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TVALID" *)
    input  logic        s_axis_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TREADY" *)
    output logic        s_axis_tready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TLAST" *)
    input  logic        s_axis_tlast,

    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TDATA" *)
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME M_AXIS, TDATA_NUM_BYTES 4, HAS_TLAST 1, HAS_TKEEP 1" *)
    output logic [31:0] m_axis_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TKEEP" *)
    output logic [3:0]  m_axis_tkeep,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TVALID" *)
    output logic        m_axis_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TREADY" *)
    input  logic        m_axis_tready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TLAST" *)
    output logic        m_axis_tlast,

    input  logic        cfg_mode_int4,
    input  logic        cfg_enable_2to4,
    input  logic        cfg_clear_status,
    input  logic [31:0] cfg_weight_tdata,
    input  logic [31:0] cfg_bias,
    output logic        status_mask_error
);

    logic signed [31:0] accumulator;
    logic signed [31:0] dot_product;
    logic signed [31:0] sparse_sum;
    logic signed [31:0] next_accumulator;
    logic               start_of_packet;
    logic               current_mask_error;

    integer lane;
    integer group;
    integer value_index;
    integer group0_count;
    integer group1_count;
    logic [3:0] selected_mask;
    logic signed [7:0] sparse_a8;
    logic signed [7:0] sparse_w8;
    logic signed [3:0] sparse_a4;
    logic signed [3:0] sparse_w4;
    logic signed [15:0] sparse_product8;
    logic signed [7:0] sparse_product4;

    function automatic integer popcount4 (input logic [3:0] bits);
        integer i;
        begin
            popcount4 = 0;
            for (i = 0; i < 4; i = i + 1)
                popcount4 = popcount4 + bits[i];
        end
    endfunction

    function automatic signed [31:0] dense_packed_dot (
        input logic [31:0] activation,
        input logic [31:0] weight,
        input logic        mode_int4
    );
        integer i;
        reg signed [7:0] a8;
        reg signed [7:0] w8;
        reg signed [3:0] a4;
        reg signed [3:0] w4;
        reg signed [15:0] product8;
        reg signed [7:0] product4;
        reg signed [31:0] sum;
        begin
            sum = 32'sd0;
            if (mode_int4) begin
                for (i = 0; i < 8; i = i + 1) begin
                    a4 = $signed(activation[i*4 +: 4]);
                    w4 = $signed(weight[i*4 +: 4]);
                    product4 = a4 * w4;
                    sum = sum + product4;
                end
            end else begin
                for (i = 0; i < 4; i = i + 1) begin
                    a8 = $signed(activation[i*8 +: 8]);
                    w8 = $signed(weight[i*8 +: 8]);
                    product8 = a8 * w8;
                    sum = sum + product8;
                end
            end
            dense_packed_dot = sum;
        end
    endfunction

    always @* begin
        dot_product          = 32'sd0;
        sparse_sum           = 32'sd0;
        current_mask_error   = 1'b0;
        value_index          = 0;
        group0_count         = 0;
        group1_count         = 0;
        selected_mask        = 4'b0000;
        sparse_a8            = 8'sd0;
        sparse_w8            = 8'sd0;
        sparse_a4            = 4'sd0;
        sparse_w4            = 4'sd0;
        sparse_product8      = 16'sd0;
        sparse_product4      = 8'sd0;

        if (!cfg_enable_2to4) begin
            dot_product = dense_packed_dot(s_axis_tdata, cfg_weight_tdata, cfg_mode_int4);
        end else if (!cfg_mode_int4) begin
            // One four-lane INT8 2:4 group.
            group0_count = popcount4(cfg_weight_tdata[19:16]);
            if (group0_count != 2) begin
                current_mask_error = 1'b1;
                dot_product = 32'sd0;
            end else begin
                value_index = 0;
                for (lane = 0; lane < 4; lane = lane + 1) begin
                    if (cfg_weight_tdata[16+lane]) begin
                        sparse_a8 = $signed(s_axis_tdata[lane*8 +: 8]);
                        sparse_w8 = $signed(cfg_weight_tdata[value_index*8 +: 8]);
                        sparse_product8 = sparse_a8 * sparse_w8;
                        sparse_sum = sparse_sum + sparse_product8;
                        value_index = value_index + 1;
                    end
                end
                dot_product = sparse_sum;
            end
        end else begin
            // Two four-lane INT4 2:4 groups in one 32-bit activation word.
            group0_count = popcount4(cfg_weight_tdata[19:16]);
            group1_count = popcount4(cfg_weight_tdata[23:20]);
            if ((group0_count != 2) || (group1_count != 2)) begin
                current_mask_error = 1'b1;
                dot_product = 32'sd0;
            end else begin
                for (group = 0; group < 2; group = group + 1) begin
                    if (group == 0)
                        selected_mask = cfg_weight_tdata[19:16];
                    else
                        selected_mask = cfg_weight_tdata[23:20];
                    value_index = 0;
                    for (lane = 0; lane < 4; lane = lane + 1) begin
                        if (selected_mask[lane]) begin
                            sparse_a4 = $signed(s_axis_tdata[(group*4+lane)*4 +: 4]);
                            sparse_w4 = $signed(cfg_weight_tdata[group*8+value_index*4 +: 4]);
                            sparse_product4 = sparse_a4 * sparse_w4;
                            sparse_sum = sparse_sum + sparse_product4;
                            value_index = value_index + 1;
                        end
                    end
                end
                dot_product = sparse_sum;
            end
        end

        if (start_of_packet)
            next_accumulator = $signed(cfg_bias) + dot_product;
        else
            next_accumulator = accumulator + dot_product;

        // One-entry elastic output register.
        s_axis_tready = (~m_axis_tvalid) | m_axis_tready;
    end

    always_ff @(posedge aclk or negedge aresetn) begin
        if (!aresetn) begin
            accumulator      <= 32'sd0;
            start_of_packet  <= 1'b1;
            m_axis_tdata     <= 32'd0;
            m_axis_tkeep     <= 4'b0000;
            m_axis_tvalid    <= 1'b0;
            m_axis_tlast     <= 1'b0;
            status_mask_error <= 1'b0;
        end else begin
            if (cfg_clear_status)
                status_mask_error <= 1'b0;

            if (s_axis_tvalid && s_axis_tready) begin
                accumulator     <= next_accumulator;
                m_axis_tdata    <= next_accumulator;
                m_axis_tkeep    <= s_axis_tkeep;
                m_axis_tlast    <= s_axis_tlast;
                m_axis_tvalid   <= 1'b1;
                start_of_packet <= s_axis_tlast;
                if (cfg_enable_2to4 && current_mask_error)
                    status_mask_error <= 1'b1;
            end else if (m_axis_tvalid && m_axis_tready) begin
                m_axis_tvalid <= 1'b0;
            end
        end
    end

endmodule
