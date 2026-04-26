"""Semantic regression tests for the compiler pipeline.

These tests compile small source snippets all the way to custom assembly,
assemble them into machine words, and execute those words in a tiny in-process
ISA interpreter. The goal is to catch behavioral regressions in integrated
compiler output, not just parser-level mistakes.
"""

import unittest

import assemble
import compile as ccompiler


OP_R = 0b000
OP_ST = 0b001
OP_LD = 0b010
OP_LDI = 0b011
OP_BEZ = 0b100
OP_BNZ = 0b101
OP_JL = 0b110
OP_JR = 0b111

F_ADD = 0b000
F_SUB = 0b001
F_AND = 0b010
F_OR = 0b011
F_SLT = 0b100
F_HALT = 0b111


def sext(value, bits):
    sign = 1 << (bits - 1)
    return value - (1 << bits) if value & sign else value


def u16(value):
    return value & 0xFFFF


def s16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def compile_to_asm(src):
    """Run lexing, parsing, and code generation for one source snippet."""
    tokens = ccompiler.lex(src)
    prog = ccompiler.Parser(tokens).parse_program()
    return ccompiler.CodeGen(prog).generate()


def assemble_text(asm):
    """Assemble generated assembly into a 1024-word image plus symbol table."""
    parsed, symbols = assemble.first_pass(asm.splitlines(), text_base=0)
    return assemble.second_pass(parsed, symbols, mem_depth=1024), symbols


def run_words(mem, start_pc=0, max_steps=1000):
    """Execute the custom ISA directly in Python until HALT."""
    mem = list(mem)
    regs = [0] * 8
    pc = start_pc

    for _ in range(max_steps):
        word = mem[pc]
        op = (word >> 13) & 0b111
        next_pc = pc + 1

        if op == OP_R:
            rs = (word >> 10) & 0b111
            rt_or_imm = (word >> 7) & 0b111
            rd = (word >> 4) & 0b111
            funct = (word >> 1) & 0b111
            iflag = word & 0b1

            if funct == F_HALT and iflag == 0:
                return regs, mem

            rhs = sext(rt_or_imm, 3) if iflag else regs[rt_or_imm]
            if funct == F_ADD:
                regs[rd] = u16(regs[rs] + rhs)
            elif funct == F_SUB:
                regs[rd] = u16(regs[rs] - rhs)
            elif funct == F_AND:
                regs[rd] = u16(regs[rs] & rhs)
            elif funct == F_OR:
                regs[rd] = u16(regs[rs] | rhs)
            elif funct == F_SLT:
                regs[rd] = 1 if s16(regs[rs]) < s16(rhs) else 0
            else:
                raise AssertionError(f"Unsupported R funct {funct}")

        elif op in (OP_ST, OP_LD):
            rs = (word >> 10) & 0b111
            rt = (word >> 7) & 0b111
            imm = sext(word & 0b1111111, 7)  # 7-bit signed offset (-64 to 63)
            addr = regs[rs] + imm
            if op == OP_ST:
                mem[addr] = u16(regs[rt])
            else:
                regs[rt] = mem[addr]

        elif op == OP_LDI:
            rd = (word >> 10) & 0b111
            imm = sext(word & 0b1111111111, 10)
            regs[rd] = u16(imm)

        elif op in (OP_BEZ, OP_BNZ):
            r = (word >> 10) & 0b111
            imm = sext(word & 0b1111111111, 10)
            zero = regs[r] == 0
            if (op == OP_BEZ and zero) or (op == OP_BNZ and not zero):
                next_pc = pc + 1 + imm

        elif op == OP_JL:
            rd = (word >> 10) & 0b111
            regs[rd] = pc + 1
            next_pc = word & 0b1111111111

        elif op == OP_JR:
            rs = (word >> 10) & 0b111
            next_pc = regs[rs]

        else:
            raise AssertionError(f"Unsupported opcode {op}")

        regs[0] = 0
        pc = next_pc

    raise AssertionError("Program did not halt")


def run_source(src):
    """Compile, assemble, and execute one source program from main()."""
    asm = compile_to_asm(src)
    mem, symbols = assemble_text(asm)
    regs, final_mem = run_words(mem, start_pc=symbols.get("main", 0))
    return s16(regs[1]), final_mem, symbols, asm


class CompilerSemanticTests(unittest.TestCase):
    def test_basic_addition(self):
        ret, _, _, _ = run_source(
            """
            int main() {
                int a = 2;
                int b = 5;
                int c;
                c = a + b;
                return c;
            }
            """
        )
        self.assertEqual(ret, 7)

    def test_nested_expression_preserves_left_subtree(self):
        ret, _, _, _ = run_source(
            """
            int g;
            int main() {
                int a = 1;
                int b = 2;
                int c = 3;
                int d = 4;
                g = (a + b) + (c + d);
                return g;
            }
            """
        )
        self.assertEqual(ret, 10)

    def test_dynamic_array_store_preserves_rhs_value(self):
        ret, final_mem, symbols, _ = run_source(
            """
            int a[8];
            int main() {
                int i = 1;
                int j = 2;
                a[i + j] = 7;
                return a[3];
            }
            """
        )
        self.assertEqual(ret, 7)
        self.assertEqual(final_mem[symbols["a"] + 3], 7)

    def test_nested_calls_use_ir_temporaries(self):
        ret, _, _, _ = run_source(
            """
            int inc(int x) {
                return x + 1;
            }
            int add(int x, int y) {
                return x + y;
            }
            int main() {
                int a = 3;
                return add(inc(a), inc(4));
            }
            """
        )
        self.assertEqual(ret, 9)

    def test_by_pointer_call_updates_caller_slot(self):
        ret, _, _, _ = run_source(
            """
            int bump(int *x) {
                *x = *x + 1;
                return *x;
            }
            int main() {
                int a = 4;
                bump(&a);
                return a;
            }
            """
        )
        self.assertEqual(ret, 5)


class CompilerRejectionTests(unittest.TestCase):
    def test_cpp_reference_parameter_syntax_is_rejected(self):
        with self.assertRaises(SyntaxError):
            compile_to_asm(
                """
                int bump(int &x) {
                    x = x + 1;
                    return x;
                }
                int main() {
                    int a = 4;
                    bump(a);
                    return a;
                }
                """
            )


class CompilerLoweringAndScopeTests(unittest.TestCase):
    def test_for_loop_decl_collects_initializer_symbol(self):
        ret, _, _, _ = run_source(
            """
            int main() {
                int s = 0;
                for (int i = 0; i < 3; i = i + 1) {
                    s = s + 1;
                }
                return s;
            }
            """
        )
        self.assertEqual(ret, 3)


if __name__ == "__main__":
    unittest.main()
