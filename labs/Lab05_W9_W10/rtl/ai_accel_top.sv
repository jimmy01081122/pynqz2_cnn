`timescale 1ns/1ps

// Four-PE teaching accelerator used directly by all Lab05 Vivado configs.
//
// Dense mode:  each PE executes four signed multiplications.
// Sparse mode: each PE receives two compressed signed weights plus a 4-bit
//              mask. Two activation muxes feed exactly two multiplications.
//              A mask with popcount != 2 produces bias-only output for that PE
//              and raises out_mask_error for the transaction.
//
// Lane 0 and PE 0 always occupy the least-significant packed slice.
module ai_accel_top #(
    parameter integer DATA_WIDTH   = 8,
    parameter integer ENABLE_2TO4  = 0,
    parameter integer ACC_WIDTH    = 32,
    parameter integer PES          = 4
) (
    input  logic                                  clk,
    input  logic                                  rst_n,

    input  logic                                  in_valid,
    output logic                                  in_ready,
    input  logic [4*DATA_WIDTH-1:0]               in_activations,
    input  logic [PES*4*DATA_WIDTH-1:0]           in_dense_weights,
    input  logic [PES*2*DATA_WIDTH-1:0]           in_sparse_values,
    input  logic [PES*4-1:0]                      in_sparse_masks,
    input  logic [PES*ACC_WIDTH-1:0]              in_bias,

    output logic                                  out_valid,
    input  logic                                  out_ready,
    output logic [PES*ACC_WIDTH-1:0]              out_result,
    output logic                                  out_mask_error
);
    logic signed [ACC_WIDTH-1:0] pe_dot [0:PES-1];
    logic                         pe_mask_ok [0:PES-1];
    logic [PES*ACC_WIDTH-1:0]     next_result;
    logic                         next_mask_error;

    genvar pe;
    generate
        for (pe = 0; pe < PES; pe = pe + 1) begin : g_pe
            if (ENABLE_2TO4 == 0) begin : g_dense
                logic signed [DATA_WIDTH-1:0] activation0;
                logic signed [DATA_WIDTH-1:0] activation1;
                logic signed [DATA_WIDTH-1:0] activation2;
                logic signed [DATA_WIDTH-1:0] activation3;
                logic signed [DATA_WIDTH-1:0] weight0;
                logic signed [DATA_WIDTH-1:0] weight1;
                logic signed [DATA_WIDTH-1:0] weight2;
                logic signed [DATA_WIDTH-1:0] weight3;
                logic signed [2*DATA_WIDTH-1:0] product0;
                logic signed [2*DATA_WIDTH-1:0] product1;
                logic signed [2*DATA_WIDTH-1:0] product2;
                logic signed [2*DATA_WIDTH-1:0] product3;

                always_comb begin
                    activation0 = $signed(in_activations[0*DATA_WIDTH +: DATA_WIDTH]);
                    activation1 = $signed(in_activations[1*DATA_WIDTH +: DATA_WIDTH]);
                    activation2 = $signed(in_activations[2*DATA_WIDTH +: DATA_WIDTH]);
                    activation3 = $signed(in_activations[3*DATA_WIDTH +: DATA_WIDTH]);
                    weight0 = $signed(in_dense_weights[(pe*4+0)*DATA_WIDTH +: DATA_WIDTH]);
                    weight1 = $signed(in_dense_weights[(pe*4+1)*DATA_WIDTH +: DATA_WIDTH]);
                    weight2 = $signed(in_dense_weights[(pe*4+2)*DATA_WIDTH +: DATA_WIDTH]);
                    weight3 = $signed(in_dense_weights[(pe*4+3)*DATA_WIDTH +: DATA_WIDTH]);

                    // Four multiply operators per dense PE.
                    product0 = activation0 * weight0;
                    product1 = activation1 * weight1;
                    product2 = activation2 * weight2;
                    product3 = activation3 * weight3;
                    pe_dot[pe] =
                        {{(ACC_WIDTH-2*DATA_WIDTH){product0[2*DATA_WIDTH-1]}}, product0} +
                        {{(ACC_WIDTH-2*DATA_WIDTH){product1[2*DATA_WIDTH-1]}}, product1} +
                        {{(ACC_WIDTH-2*DATA_WIDTH){product2[2*DATA_WIDTH-1]}}, product2} +
                        {{(ACC_WIDTH-2*DATA_WIDTH){product3[2*DATA_WIDTH-1]}}, product3};
                    pe_mask_ok[pe] = 1'b1;
                end
            end else begin : g_sparse
                logic signed [DATA_WIDTH-1:0] selected_activation0;
                logic signed [DATA_WIDTH-1:0] selected_activation1;
                logic signed [DATA_WIDTH-1:0] sparse_weight0;
                logic signed [DATA_WIDTH-1:0] sparse_weight1;
                logic signed [2*DATA_WIDTH-1:0] product0;
                logic signed [2*DATA_WIDTH-1:0] product1;
                integer lane;
                integer selected_count;

                always_comb begin
                    selected_activation0 = '0;
                    selected_activation1 = '0;
                    sparse_weight0 = $signed(
                        in_sparse_values[(pe*2+0)*DATA_WIDTH +: DATA_WIDTH]
                    );
                    sparse_weight1 = $signed(
                        in_sparse_values[(pe*2+1)*DATA_WIDTH +: DATA_WIDTH]
                    );
                    selected_count = 0;
                    for (lane = 0; lane < 4; lane = lane + 1) begin
                        if (in_sparse_masks[pe*4+lane]) begin
                            if (selected_count == 0)
                                selected_activation0 = $signed(
                                    in_activations[lane*DATA_WIDTH +: DATA_WIDTH]
                                );
                            else if (selected_count == 1)
                                selected_activation1 = $signed(
                                    in_activations[lane*DATA_WIDTH +: DATA_WIDTH]
                                );
                            selected_count = selected_count + 1;
                        end
                    end
                    pe_mask_ok[pe] = (selected_count == 2);

                    // Two multiply operators per sparse PE. The mask selects
                    // activations; it does not expand weights to four multiplies.
                    product0 = selected_activation0 * sparse_weight0;
                    product1 = selected_activation1 * sparse_weight1;
                    pe_dot[pe] =
                        {{(ACC_WIDTH-2*DATA_WIDTH){product0[2*DATA_WIDTH-1]}}, product0} +
                        {{(ACC_WIDTH-2*DATA_WIDTH){product1[2*DATA_WIDTH-1]}}, product1};
                    if (!pe_mask_ok[pe])
                        pe_dot[pe] = '0;
                end
            end
        end
    endgenerate

    integer result_pe;
    always_comb begin
        next_result = '0;
        next_mask_error = 1'b0;
        for (result_pe = 0; result_pe < PES; result_pe = result_pe + 1) begin
            next_result[result_pe*ACC_WIDTH +: ACC_WIDTH] =
                $signed(in_bias[result_pe*ACC_WIDTH +: ACC_WIDTH]) +
                $signed(pe_dot[result_pe]);
            if ((ENABLE_2TO4 != 0) && !pe_mask_ok[result_pe])
                next_mask_error = 1'b1;
        end
    end

    // One-entry elastic output register. A consumed result may be replaced by
    // a new input in the same cycle; while stalled, all output fields hold.
    always_comb in_ready = (~out_valid) | out_ready;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            out_valid      <= 1'b0;
            out_result     <= '0;
            out_mask_error <= 1'b0;
        end else if (in_ready) begin
            if (in_valid) begin
                out_valid      <= 1'b1;
                out_result     <= next_result;
                out_mask_error <= next_mask_error;
            end else begin
                out_valid <= 1'b0;
            end
        end
    end

    initial begin
        if ((DATA_WIDTH != 4) && (DATA_WIDTH != 8))
            $error("ai_accel_top DATA_WIDTH must be 4 or 8");
        if ((ENABLE_2TO4 != 0) && (ENABLE_2TO4 != 1))
            $error("ai_accel_top ENABLE_2TO4 must be 0 or 1");
        if (PES != 4)
            $error("Lab05 requires PES=4 for a fair four-PE comparison");
    end
endmodule
