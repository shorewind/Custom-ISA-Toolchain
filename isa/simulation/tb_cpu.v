`timescale 1ns/1ps

`include "defs.vh"
`include "cpu.v"

module tb_cpu;

    reg clk;
    reg reset;
    integer i;

    // Unit under test
    cpu uut (
        .clk  (clk),
        .reset(reset)
    );

    // clock: 10ns period
    always #5 clk = ~clk;

    // ------------------------------
    // Encoding helpers (match ISA)
    // ------------------------------

    // R-Type:
    // [15:13] op
    // [12:10] rs
    // [ 9:7 ] rt_or_imm
    // [ 6:4 ] rd
    // [ 3:1 ] funct
    // [ 0   ] iflag
    function [15:0] enc_rtype;
        input [2:0] op;
        input [2:0] rs;
        input [2:0] rt_or_imm;
        input [2:0] rd;
        input [2:0] funct;
        input       iflag;
        begin
            enc_rtype = {op, rs, rt_or_imm, rd, funct, iflag};
        end
    endfunction

    // LS-Type:
    // [15:13] op
    // [12:10] rs   (base)
    // [ 9:7 ] rt   (reg)
    // [ 6:0 ] imm7 (offset)
    function [15:0] enc_ls;
        input [2:0] op;
        input [2:0] rs;
        input [2:0] rt;
        input [6:0] imm7;
        begin
            enc_ls = {op, rs, rt, imm7};
        end
    endfunction

    // IJ-Type:
    // [15:13] op
    // [12:10] rd_or_rs
    // [ 9:0 ] imm10
    function [15:0] enc_ij;
        input [2:0] op;
        input [2:0] rd;
        input [9:0] imm10;
        begin
            enc_ij = {op, rd, imm10};
        end
    endfunction

    task dump_mem64;
        integer idx;
        begin
            $display("\n==== MEMORY [0:63] ====");
            for (idx = 0; idx < 64; idx = idx + 1) begin
                $display("MEM[%0d] = 0x%04h (%0d)", idx, uut.unified_mem.mem[idx], uut.unified_mem.mem[idx]);
            end
        end
    endtask

    initial begin
        clk   = 1'b1;
        reset = 1'b1;

        // Clear instruction/data memory before optional file load.
        for (i = 0; i < 64; i = i + 1) begin
            uut.unified_mem.mem[i] = 16'h0000;
        end

        // Clear registers (r[])
        for (i = 0; i < 8; i = i + 1) begin
            uut.reg_file.r[i] = 16'h0000;
        end

        $readmemb("test-case.memb", uut.unified_mem.mem);
        $display("Loaded .memb: test-case.memb");
        // Alternate hex image:
        // $readmemh("test-case.memh", uut.unified_mem.mem);
        // $display("Loaded .memh: test-case.memh");

        $display("\n==== MEMORY BEFORE RUN ====");
        dump_mem64();

        // Release reset after 20 time units (~2 cycles)
        #20;
        reset = 1'b0;

        // Run long enough to step through the loaded image
        #200;

        $display("\n==== FINAL REGISTERS ====");
        for (i = 0; i < 8; i = i + 1) begin
            $display("R%0d = 0x%04h (%0d)", i, uut.reg_file.r[i], uut.reg_file.r[i]);
        end

        $display("\n==== MEMORY AFTER RUN ====");
        dump_mem64();
        $finish;
    end

    // Cycle-by-cycle debug tracing
    always @(posedge clk) begin
        if (reset) begin
            $display("----- t=%0t (RESET ACTIVE) -----", $time);
            $display("PC = %0d", uut.pc);
            $display("-----------------------------\n");
        end else begin
            $display("----- t=%0t -----", $time);
            $display("PC     = %0d", uut.pc);
            $display("INSTR  = 0x%04h", uut.instr);
            $display("DECODE : opcode=%b rs=%0d rt=%0d rd=%0d funct=%b iflag=%b",
                     uut.instr[15:13], uut.instr[12:10],
                     uut.instr[9:7],   uut.instr[6:4],
                     uut.instr[3:1],   uut.instr[0]);

            $display("CONTROL: alu_op=%b reg_dst=%b alu_src=%b mem_to_reg=%b reg_write=%b mem_read=%b mem_write=%b branch_eq=%b branch_ne=%b imm_jump=%b reg_jump=%b return_link=%b halt=%b",
                     uut.alu_op, uut.reg_dst, uut.alu_src,
                     uut.mem_to_reg, uut.reg_write,
                     uut.mem_read, uut.mem_write,
                     uut.branch_eq, uut.branch_ne, uut.imm_jump, uut.reg_jump, uut.return_link, uut.halt);

            $display("ALU    : vrs(a)=%0d alu_b(b)=%0d -> y=%0d zero=%b",
                     uut.vrs, uut.alu_b, uut.alu_y, uut.alu_zero);

            $display("WB     : write_reg=%0d wb_data=%0d reg_write=%b",
                     uut.write_reg, uut.wb_data, uut.reg_write);

            $display("REGS   : r0=%0d r1=%0d r2=%0d r3=%0d r4=%0d r5=%0d r6=%0d r7=%0d",
                     uut.reg_file.r[0], uut.reg_file.r[1], uut.reg_file.r[2], uut.reg_file.r[3],
                     uut.reg_file.r[4], uut.reg_file.r[5], uut.reg_file.r[6], uut.reg_file.r[7]);

            $display("MEM    : M[14]=%0d",
                     uut.unified_mem.mem[14]);
            $display("-----------------------------\n");
        end
    end

endmodule
