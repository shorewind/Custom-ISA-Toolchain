#!/usr/bin/env python3
"""
assemble.py: Assembler for 16-bit custom ISA
Definition: Converts a .s file with .text/.data, labels, .word into a word-addressed .memh
Usage:
  python3 assemble.py <input.s> <output.memh>
"""

import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# -----------------------------------------------------------------------------
# 1) ISA CONSTANTS
# -----------------------------------------------------------------------------
OP_R   = 0b000
OP_ST  = 0b001
OP_LD  = 0b010
OP_LDI = 0b011
OP_BEZ = 0b100
OP_BNZ = 0b101
OP_JL  = 0b110
OP_JR  = 0b111

F_ADD  = 0b000
F_SUB  = 0b001
F_AND  = 0b010
F_OR   = 0b011
F_SLT  = 0b100
F_SLL  = 0b101
F_SRL  = 0b110
F_HALT = 0b111

# register mapping
REGS = {f"r{i}": i for i in range(8)}

# -----------------------------------------------------------------------------
# 2) ENCODING HELPERS
# -----------------------------------------------------------------------------
def enc_rtype(op: int, rs: int, rt_or_imm: int, rd: int, funct: int, iflag: int) -> int:
    return ((op & 0b111) << 13) | ((rs & 0b111) << 10) | ((rt_or_imm & 0b111) << 7) | ((rd & 0b111) << 4) | ((funct & 0b111) << 1) | (iflag & 0b1)

def enc_ls(op: int, rs: int, rt: int, imm7: int) -> int:
    return ((op & 0b111) << 13) | ((rs & 0b111) << 10) | ((rt & 0b111) << 7) | (imm7 & 0b1111111)

def enc_ij(op: int, rd_or_rs: int, imm10: int) -> int:
    return ((op & 0b111) << 13) | ((rd_or_rs & 0b111) << 10) | (imm10 & 0b1111111111)

def to_twos_comp(val: int, bits: int) -> int:
    """Encode signed immediate val into two's complement with width 'bits'"""
    lo = -(1 << (bits - 1))  # 2's complement range: -2^(bits-1) to 2^(bits-1)-1
    hi = (1 << (bits - 1)) - 1
    if not (lo <= val <= hi):
        raise ValueError(f"Immediate {val} out of range for signed {bits}-bit ({lo} to {hi}).")
    return val & ((1 << bits) - 1)  # mask to bits width

# -----------------------------------------------------------------------------
# 3) PARSING (supports .text/.data, labels, .word, directives)
# -----------------------------------------------------------------------------
@dataclass
class Line:
    raw: str
    section: str              # "text" or "data"
    addr: int                 # word address
    kind: str                 # "instr" or "word"
    tokens: List[str]         # tokenized content (mnemonic + operands) or ".word" + value

def strip_comment(s: str) -> str:
    s = s.split(";", 1)[0]
    s = s.split("//", 1)[0]
    return s.strip()

def tokenize(s: str) -> List[str]:
    s = s.replace(",", " ")
    return [t for t in s.split() if t]

# valid label starts with letter/underscore, followed by letters/digits/underscores
LABEL_REGEX = re.compile(r"^[A-Za-z_]\w*$")  # define regex pattern

def is_label_name(s: str) -> bool:
    return bool(LABEL_REGEX.fullmatch(s))

def parse_int(tok: str) -> int:
    tok = tok.strip()
    if tok.startswith("+"):
        tok = tok[1:]  # allow optional + for positive numbers
    return int(tok, 0)  # return int from base

# for LS-type instructions: returns (imm7_value, rs_reg)
def parse_mem_operand(tok: str, sym: Dict[str, int]) -> Tuple[int, int]:
    """
    Parses:
      imm(rs)            e.g., 31(r0)
      label(rs)          e.g., result(r0)
      label+K(rs)        e.g., results+2(r0)
      label-K(rs)        e.g., results-1(r0)
    Returns (imm7_value, rs_reg)
    """
    m = re.fullmatch(r"(.+)\((r[0-7])\)", tok.strip())
    if not m:
        raise ValueError(f"Bad memory operand '{tok}' (expected imm(rs) or label(rs)).")
    off_expr = m.group(1).strip()  # offset expression (could be immediate, label, or label+/-offset)
    rs = REGS[m.group(2)]

    # Case A: offset is a plain label
    if is_label_name(off_expr):
        if off_expr not in sym:
            raise ValueError(f"Unknown label '{off_expr}' in memory operand.")
        imm = sym[off_expr]  # absolute address of label as offset
    else:
        m2 = re.fullmatch(r"([A-Za-z_]\w*)\s*([+-])\s*(.+)", off_expr)
        # Case B: offset is label with + or - immediate
        if m2:
            label = m2.group(1)
            sign = m2.group(2)
            k = parse_int(m2.group(3))
            if label not in sym:
                raise ValueError(f"Unknown label '{label}' in memory operand.")
            imm = sym[label] + (k if sign == "+" else -k)
        # Case C: offset is a plain immediate
        else:
            imm = parse_int(off_expr)

    imm7 = to_twos_comp(imm, 7)  # 7-bit signed: -64 to 63
    return imm7, rs

def count_text_words(lines: List[str]) -> int:
    section = "text"
    pc_text = 0

    for raw in lines:
        line = strip_comment(raw)
        if not line:
            continue

        if line.startswith("."):
            toks = tokenize(line)
            d = toks[0].lower()
            if d == ".text":
                section = "text"
            elif d == ".data":
                section = "data"
            continue

        while True:
            if ":" not in line:
                break
            _, right = line.split(":", 1)
            line = right.strip()
            if not line:
                break

        if not line:
            continue

        toks = tokenize(line)
        if toks[0].lower() != ".word" and section == "text":
            pc_text += 1

    return pc_text

# First pass: define symbols and record their memory addresses
def first_pass(
    lines: List[str],
    text_base: int = 0,
    data_base: Optional[int] = None,
) -> Tuple[List[Line], Dict[str, int]]:
    """
    Builds symbol table (labels->addresses) and a structured line list with addresses.
    Uses simple placement:
      .text starts at text_base
      .data starts at data_base if provided, otherwise immediately after .text
    """
    if data_base is None:
        data_base = text_base + count_text_words(lines)

    section = "text"
    pc_text = 0
    pc_data = 0
    sym: Dict[str, int] = {}  # dictionary mapping label names to addresses
    parsed: List[Line] = []

    for raw in lines:
        line = strip_comment(raw)
        if not line:
            continue

        # directives
        if line.startswith("."):
            toks = tokenize(line)
            d = toks[0].lower()
            if d in (".text",):
                section = "text"
            elif d in (".data",):
                section = "data"
            else:
                # ignore other directive for now
                pass
            continue

        # labels
        while True:
            if ":" in line:
                left, right = line.split(":", 1)  # might be instruction after label
                label = left.strip()
                if not is_label_name(label):
                    raise ValueError(f"Invalid label name: '{label}'")
                # compute address for label based on current section and PC
                addr = (text_base + pc_text) if section == "text" else (data_base + pc_data)
                if label in sym:
                    raise ValueError(f"Duplicate label: '{label}'")
                sym[label] = addr
                line = right.strip()
                if not line:
                    break
                # continue to allow "label: instr ..." style
                continue
            break

        if not line:
            continue

        # tokenize and record line with address
        toks = tokenize(line)
        if toks[0].lower() == ".word":
            if section != "data":
                raise ValueError(".word used outside .data")
            addr = data_base + pc_data  # assign address for .word in data section
            parsed.append(Line(raw=raw, section="data", addr=addr, kind="word", tokens=toks))
            pc_data += 1
        else:
            if section != "text":
                raise ValueError("Instruction used outside .text")
            addr = text_base + pc_text
            parsed.append(Line(raw=raw, section="text", addr=addr, kind="instr", tokens=toks))
            pc_text += 1

    return parsed, sym

# Encode a single instruction line into its 16-bit machine code representation
def encode_instruction(toks: List[str], sym: Dict[str, int], pc: int) -> int:
    mnem = toks[0].upper()  # instruction mnemonic
    ops = toks[1:]  # operands

    if mnem == "NOP":
        return 0x0000

    if mnem == "HALT":
        return enc_rtype(OP_R, 0, 0, 0, F_HALT, 0)

    if mnem == "LDI":
        rd = REGS[ops[0]]
        imm10 = parse_int(ops[1])
        imm10 = to_twos_comp(imm10, 10)  # allow signed immediates for LDI
        return enc_ij(OP_LDI, rd, imm10)

    # R-type with iflag=0 (register operands only)
    if mnem in ("ADD", "SUB", "AND", "OR", "SLT"):
        rd = REGS[ops[0]]
        rs = REGS[ops[1]]
        rt = REGS[ops[2]]
        # map mnemonic to funct code
        funct = {"ADD": F_ADD, "SUB": F_SUB, "AND": F_AND, "OR": F_OR, "SLT": F_SLT}[mnem]
        return enc_rtype(OP_R, rs, rt, rd, funct, 0)

    # R-type with iflag=1 (immediate/shift)
    if mnem == "ADDI":
        rd = REGS[ops[0]]
        rs = REGS[ops[1]]
        imm3 = to_twos_comp(parse_int(ops[2]), 3)
        return enc_rtype(OP_R, rs, imm3, rd, F_ADD, 1)

    if mnem in ("SLL", "SRL"):
        rd = REGS[ops[0]]
        rs = REGS[ops[1]]
        sh3 = parse_int(ops[2]) & 0b111  # 3-bit unsigned shift amount
        funct = F_SLL if mnem == "SLL" else F_SRL
        return enc_rtype(OP_R, rs, sh3, rd, funct, 1)

    # Load/store
    if mnem in ("ST", "LD"):
        rt = REGS[ops[0]]
        imm7, rs = parse_mem_operand(ops[1], sym)
        return enc_ls(OP_ST if mnem == "ST" else OP_LD, rs, rt, imm7)

    # Branches (PC-relative)
    if mnem in ("BEZ", "BNZ"):
        r = REGS[ops[0]]
        target = ops[1]
        if is_label_name(target):
            if target not in sym:
                raise ValueError(f"Unknown label '{target}'")
            off = sym[target] - (pc + 1)
        else:
            off = parse_int(target)  # allow +N or -N directly
        imm10 = to_twos_comp(off, 10)
        return enc_ij(OP_BEZ if mnem == "BEZ" else OP_BNZ, r, imm10)

    # Jump-and-link (absolute)
    if mnem == "JL":
        rd = REGS[ops[0]]  # link register, e.g. r7
        target = ops[1]
        if is_label_name(target):
            if target not in sym:
                raise ValueError(f"Unknown label '{target}'")
            addr = sym[target]
        else:
            addr = parse_int(target)
        if not (0 <= addr <= 1023):
            raise ValueError(f"JL target out of range (0 to 1023): {addr}")
        return enc_ij(OP_JL, rd, addr)

    # Jump register
    if mnem == "JR":
        rs = REGS[ops[0]]
        return enc_ij(OP_JR, rs, 0)

    raise ValueError(f"Unknown/unsupported instruction: {mnem}")

# Second pass: translate instructions and resolve symbols into machine code
def second_pass(parsed: List[Line], sym: Dict[str, int], mem_depth: int = 1024) -> List[int]:
    """
    Produces a unified memory image (word-addressed) suitable for $readmemh.
    .text instructions and .data words share the same address space.
    """
    mem = [0] * mem_depth  # initialize memory with zeros

    for item in parsed:
        # verify address is within memory bounds
        if item.addr < 0 or item.addr >= mem_depth:
            raise ValueError(f"Address {item.addr} out of memory range 0 to {mem_depth-1} (line: {item.raw.strip()})")

        if item.kind == "word":
            if len(item.tokens) != 2:
                raise ValueError(f"Bad .word syntax (expected: .word <value>): {item.raw.strip()}")
            val_tok = item.tokens[1]
            if is_label_name(val_tok):
                if val_tok not in sym:
                    raise ValueError(f"Unknown label in .word: '{val_tok}'")
                val = sym[val_tok]
            else:
                val = parse_int(val_tok)
            mem[item.addr] = val & 0xFFFF  # mask to 16 bits

        elif item.kind == "instr":
            # encode instruction into 16-bit machine code and store in memory
            mem[item.addr] = encode_instruction(item.tokens, sym, item.addr) & 0xFFFF

        else:
            raise ValueError(f"Internal error: unknown kind {item.kind}")

    return mem

# -----------------------------------------------------------------------------
# 4) CLI
# -----------------------------------------------------------------------------
def main():
    if len(sys.argv) != 3:
        print("usage: python3 assemble.py <input.s> <output.memh>")
        sys.exit(1)

    in_path = sys.argv[1]
    out_path = sys.argv[2]

    with open(in_path, "r") as f:
        src_lines = f.readlines()

    # declare base addresses for .text and .data sections and build symbol table
    parsed, sym = first_pass(src_lines, text_base=0)

    # set memory depth and generate unified memory image (word-addressed) for $readmemh
    mem = second_pass(parsed, sym, mem_depth=1024)

    with open(out_path, "w") as f:
        for w in mem:
            f.write(f"{w:04X}\n")
            # f.write(f"{w:016b}\n")  # also write binary for easier debugging

    # DEBUG: print symbol table
    print("Symbols:")
    for k in sorted(sym.keys()):
        print(f"  {k} = {sym[k]}")
    print(f"\nWrote {len(mem)} words to {out_path}")

if __name__ == "__main__":
    main()
