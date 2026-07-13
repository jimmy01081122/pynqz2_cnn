`timescale 1ns/1ps

module tiny_counter #(
    parameter integer WIDTH = 4
) (
    input  logic             clk,
    input  logic             rst,
    input  logic             en,
    output logic [WIDTH-1:0] count
);
    always_ff @(posedge clk) begin
        // TODO 1：rst 時清零；否則 en 時加一；其餘情況保持。
        // 目前骨架每個上升緣都清零，語法合法，但功能尚未完成。
        count <= '0;
    end
endmodule
