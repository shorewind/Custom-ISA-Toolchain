`include "defs.vh"

module control_unit (
    input wire [2:0] opcode,
    input wire [2:0] funct,
    output reg [2:0] alu_op,
    output reg [2:0] reg_dst, // 00=rt, 01=rd, 10=rs
    output reg branch_eq,
    output reg branch_ne,
    output reg mem_read,
    output reg mem_to_reg,
    output reg mem_write,
    output reg alu_src,
    output reg reg_write,
    output reg imm_to_reg,
    output reg imm_jump,
    output reg reg_jump,
    output reg return_link,
    output reg halt
);
    
    // decode
    always @(*) begin
        alu_op = `ALU_NOP;
        reg_dst = 2'b00;  // default rt
        branch_eq = 0;
        branch_ne = 0;
        mem_read = 0;
        mem_to_reg = 0;
        mem_write = 0;
        alu_src = 0;
        reg_write = 0;
        imm_to_reg = 0;
        imm_jump = 0;
        reg_jump = 0;
	return_link = 0;
	halt = 0;
        case (opcode)
            `OP_R: begin
                reg_dst = 2'b01;  // write rd
                alu_src = 1'b0;  // use rt
                reg_write = 1'b1;
                case (funct)
                    `F_HALT: begin
                        reg_dst = 2'b00;
                        reg_write = 1'b0;
                        alu_op = `ALU_NOP;
                        halt = 1'b1;
                    end
                    `F_ADD: begin
                        alu_op = `ALU_ADD;
                    end
                    `F_SUB: begin
                        alu_op = `ALU_SUB;
                    end
                    `F_AND: begin
                        alu_op = `ALU_AND;
                    end
                    `F_OR: begin
                        alu_op = `ALU_OR;
                    end
                    `F_SLT: begin
                        alu_op = `ALU_SLT;
                    end
                    `F_SLL: begin
                        alu_op = `ALU_SLL;
                    end
                    `F_SRL: begin
                        alu_op = `ALU_SRL;
                    end
                    default: begin
                        alu_op = `ALU_NOP;
                    end
                endcase
            end
            `OP_ST: begin
                alu_op = `ALU_ADD;
                alu_src = 1'b1;  // use imm offset
                mem_write = 1'b1;
            end
            `OP_LD: begin
                alu_op = `ALU_ADD;
                alu_src = 1'b1;
                mem_read = 1'b1;
                mem_to_reg = 1'b1;  // writeback from mem
                reg_dst = 2'b00;  // write rt
                reg_write = 1'b1;
            end
            `OP_LDI: begin
                alu_op = `ALU_NOP;
                alu_src = 1'b1;
                reg_write = 1'b1;
                imm_to_reg = 1'b1;
		reg_dst = 2'b10;  // write rs
            end
            `OP_BEZ: begin
                alu_op = `ALU_SUB;
                branch_eq = 1'b1;
            end
            `OP_BNZ: begin
                alu_op = `ALU_SUB;
                branch_ne = 1'b1;
            end
            `OP_JL: begin
                imm_jump = 1'b1;
                reg_write = 1'b1;
                return_link = 1'b1;
            end
            `OP_JR: begin
                reg_jump = 1'b1;
            end
            default: begin
                halt = 1'b1;
                alu_op = `ALU_NOP;
            end
        endcase
    end

endmodule
