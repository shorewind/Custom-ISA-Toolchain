#!/usr/bin/env python3
"""
build.py: Build script for 16-bit custom ISA.
Description: Converts a C source file into an assembly string, then assembles that string into a unified memory image.
Usage:
  python3 build.py <input.c> [output_base]

Outputs (derived from input path if output_base is omitted):
  <base>.s            intermediate assembly
  <base>.memh         unified memory image, hex
  <base>.memb         unified memory image, binary
"""

import os
import sys

import assemble
import compile as cc

TEXT_BASE = 0
UNIFIED_MEM_DEPTH = 1024


# -----------------------------------------------------------------------------
# 1) File Writers
# -----------------------------------------------------------------------------
def write_words_hex(path: str, words: list[int]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for w in words:
            f.write(f"{w:04X}\n")


def write_words_bin(path: str, words: list[int]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for w in words:
            f.write(f"{w:016b}\n")


# -----------------------------------------------------------------------------
# 2) Build Flow
# -----------------------------------------------------------------------------
def build(c_path: str, base: str | None = None) -> None:
    if base is None:
        base = os.path.splitext(c_path)[0]

    # 1) compile .c -> assembly string
    with open(c_path, encoding="utf-8") as f:
        src = f.read()
    tokens = cc.lex(src)
    prog = cc.Parser(tokens).parse_program()
    asm = cc.CodeGen(prog).generate()

    asm_path = base + ".s"
    with open(asm_path, "w", encoding="utf-8") as f:
        f.write(asm)

    # 2) assemble -> unified memory image
    parsed, sym = assemble.first_pass(asm.splitlines(), text_base=TEXT_BASE)
    mem = assemble.second_pass(parsed, sym, mem_depth=UNIFIED_MEM_DEPTH)
    write_words_hex(f"{base}.memh", mem)
    write_words_bin(f"{base}.memb", mem)

    print(f"{c_path}")
    print(f"  {asm_path}")
    print(f"  {base}.memh / .memb")


# -----------------------------------------------------------------------------
# 3) CLI
# -----------------------------------------------------------------------------
def main() -> None:
    if len(sys.argv) not in (2, 3):
        print("usage: python3 build.py <input.c> [output_base]")
        sys.exit(1)

    c_path = sys.argv[1]
    base = sys.argv[2] if len(sys.argv) == 3 else None
    build(c_path, base)


if __name__ == "__main__":
    main()
