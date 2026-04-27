`include "defs.vh"

module alu (
    input wire [15:0] a, b,
    input wire [2:0] alu_op,
    output reg [15:0] y,
    output wire zero
);

    always @(*) begin
        case (alu_op)
            `ALU_ADD: y = a + b;
            `ALU_SUB: y = a - b;
            `ALU_AND: y = a & b;
            `ALU_OR: y = a | b;
            `ALU_SLT: y = ($signed(a) < $signed(b)) ? 16'h0001 : 16'h0000;
            `ALU_SLL: y = a << b[2:0];
            `ALU_SRL: y = a >> b[2:0];
            default: y = b;
        endcase
    end

    assign zero = (y == 16'h0000);
endmodule
