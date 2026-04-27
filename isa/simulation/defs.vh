`ifndef DEFS_VH
`define DEFS_VH

// Opcodes
`define OP_R   3'b000
`define OP_ST  3'b001
`define OP_LD  3'b010
`define OP_LDI 3'b011
`define OP_BEZ 3'b100
`define OP_BNZ 3'b101
`define OP_JL  3'b110
`define OP_JR  3'b111

// Funct codes
`define F_ADD  3'b000
`define F_SUB  3'b001
`define F_AND  3'b010
`define F_OR   3'b011
`define F_SLT  3'b100
`define F_SLL  3'b101
`define F_SRL  3'b110
`define F_HALT 3'b111

// ALU opcodes
`define ALU_NOP 3'b000
`define ALU_ADD 3'b001
`define ALU_SUB 3'b010
`define ALU_AND 3'b011
`define ALU_OR  3'b100
`define ALU_SLT 3'b101
`define ALU_SLL 3'b110
`define ALU_SRL 3'b111

`endif // DEFS_VH
