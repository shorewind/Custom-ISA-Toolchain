module cpu (
    input  wire clk,
    input  wire reset
);
    // program counter and instruction fetch
    wire [15:0] pc;
    wire [15:0] pc_next;
    wire [15:0] instr;

    // pc register
    pc pc_reg(
        .clk(clk),
        .reset(reset),
        .pc_next(pc_next),
        .pc(pc)
    );

    // next pc logic
    wire [15:0] pc_plus_1;
    wire [15:0] branch_target;

    adder pc_inc(
        .in1(pc),
        .in2(16'h0001),
        .out(pc_plus_1)
    );

    // instruction decode
    wire [2:0] opcode = instr[15:13];
    wire [2:0] rs = instr[12:10];
    wire [2:0] rt = instr[9:7];
    wire [2:0] rd = instr[6:4];
    wire [2:0] funct = instr[3:1];
    wire iflag = instr[0];

    // immediates
    wire [2:0] imm3 = instr[9:7];  // shift, addi
    wire [6:0] imm7 = instr[6:0];  // branch, load/store offset
    wire [9:0] imm10 = instr[9:0];  // jump target, ldi

    // control unit
    wire [2:0] alu_op;
    wire [2:0] reg_dst;
    wire branch_eq, branch_ne;
    wire mem_read, mem_to_reg, mem_write;
    wire alu_src;
    wire reg_write;
    wire imm_to_reg, imm_jump, reg_jump;
    wire return_link;
    wire halt;

    control_unit control_unit(
        .opcode(opcode),
        .funct(funct),
        .alu_op(alu_op),
        .reg_dst(reg_dst),
        .branch_eq(branch_eq),
        .branch_ne(branch_ne),
        .mem_read(mem_read),
        .mem_to_reg(mem_to_reg),
        .mem_write(mem_write),
        .alu_src(alu_src),
        .reg_write(reg_write),
        .imm_to_reg(imm_to_reg),
        .imm_jump(imm_jump),
        .reg_jump(reg_jump),
	    .return_link(return_link),
	    .halt(halt)
    );

    // sign extension
    wire [15:0] imm3_ext;
    wire [15:0] imm7_ext;
    wire [15:0] imm10_ext;
   
    sign_extend #(.IN_WIDTH(3)) sign_extend3(
        .data_in(imm3),
        .data_extended(imm3_ext)
    );

    sign_extend #(.IN_WIDTH(7)) sign_extend7(
        .data_in(imm7),
        .data_extended(imm7_ext)
    );

    sign_extend #(.IN_WIDTH(10)) sign_extend10(
        .data_in(imm10),
        .data_extended(imm10_ext)
    );

    // register file
    wire [2:0] write_reg_stage1, write_reg_stage2, write_reg;
    wire [15:0] vrs;  // value of rs
    wire [15:0] vrt;  // value of rt (also used for stores)
    wire [15:0] wb_data, wb_data_med, wb_data_final; // write-back data to reg_file

    // select destination register: rd vs rt
    mux #(.WIDTH(3)) mux_write_reg_stage1(
        .in1(rt),
        .in2(rd),
        .select(reg_dst[0]),
        .out(write_reg_stage1)
    );

    // select destination register: vs I-type (rs)
    mux #(.WIDTH(3)) mux_write_reg_stage2(
        .in1(write_reg_stage1),
        .in2(rs),
        .select(reg_dst[1]),
        .out(write_reg_stage2)
    );

    // select destination register: jump link r7 = PC + 1
    mux #(.WIDTH(3)) mux_write_reg_final(
        .in1(write_reg_stage2),
        .in2(3'd7),
        .select(return_link),
        .out(write_reg)
    );

    mux mux_write_data(
        .in1(wb_data),
        .in2(imm10_ext),
        .select(imm_to_reg),
        .out(wb_data_med)
    );

    mux mux_write_data_final(
        .in1(wb_data_med),
        .in2(pc_plus_1),
        .select(return_link),
        .out(wb_data_final)
    );

    reg_file reg_file(
        .clk(clk),
        .enable(reg_write),
        .rs(rs),
        .rt(rt),
        .rd(write_reg),
        .wd(wb_data_final),
        .vrs(vrs),
        .vrt(vrt)
    );

    // arithmetic logic unit
    wire [15:0] alu_b;
    wire [15:0] alu_y;
    wire [15:0] alu_in2;  // value between muxes
    wire  alu_zero;

    // select small immediate based on iflag (vrt vs imm3_ext)
    mux mux_imm(
        .in1(vrt),
        .in2(imm3_ext),
        .select(iflag),
        .out(alu_in2)
    );

    // ALU second operand mux: alu_in2 vs imm7_ext
    mux mux_alu_src(
        .in1(alu_in2),
        .in2(imm7_ext),
        .select(alu_src),
        .out(alu_b)
    );

    alu alu(
        .a(vrs),
        .b(alu_b),
        .alu_op(alu_op),
        .y(alu_y),
        .zero(alu_zero)
    );

    // data memory
    wire [15:0] dmem_rdata;

    // unified memory (word-addressed)
    unified_mem unified_mem(
        .clk(clk),
        .i_addr(pc),
        .i_data(instr),
        .d_addr(alu_y), // address from ALU
        .d_wdata(vrt), // store data from rt
        .d_read(mem_read),
        .d_write(mem_write),
        .d_rdata(dmem_rdata)
    );

    // write-back mux (ALU result vs data memory)
    mux mux_writeback(
        .in1(alu_y),
        .in2(dmem_rdata),
        .select(mem_to_reg),
        .out(wb_data)
    );

    // branch_target = pc_plus_1 + imm7_ext
    adder branch_add(
        .in1(pc_plus_1),
        .in2(imm7_ext),
        .out(branch_target)
    );

    // branching and jumping
    wire take_beq, take_bne, take_branch;

    and_gate branch_eq_and(
        .in1(branch_eq),
        .in2(alu_zero),
        .out(take_beq)
    );

    and_gate branch_ne_and(
        .in1(branch_ne),
        .in2(!alu_zero),
        .out(take_bne)
    );

    or_gate take_branch_or(
        .in1(take_beq),
        .in2(take_bne),
        .out(take_branch)
    );

    // PC selection chain using muxes
    wire [15:0] pc_after_branch, pc_after_imm, pc_after_reg;

    // 1. branch vs fall-through
    mux mux_branch(
        .in1(pc_plus_1),
        .in2(branch_target),
        .select(take_branch),
        .out(pc_after_branch)
    );

    // 2. immediate jump vs previous
    mux mux_imm_jump(
        .in1(pc_after_branch),
        .in2(imm10_ext),  // jump_target_imm
        .select(imm_jump),
        .out(pc_after_imm)
    );

    // 3. register jump vs previous
    mux mux_reg_jump(
        .in1(pc_after_imm),
        .in2(vrs),  // jump_target_reg
        .select(reg_jump),
        .out(pc_after_reg)
    );

    // 4. pc halt
    mux mux_pc_select(
        .in1(pc_after_reg),
        .in2(pc),
        .select(halt),
        .out(pc_next)
    );

endmodule
