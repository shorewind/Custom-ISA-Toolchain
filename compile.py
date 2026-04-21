#!/usr/bin/env python3
"""
compile.py: Tiny C -> custom ISA assembly compiler for a restricted C subset.

Supported subset:
- Global declarations: int x;
- Functions: int name() { ... }
- Statements:
  - int x;
  - int x = <expr>;
  - x = <expr>;
  - if (<expr> != 0) { ... } else { ... }
  - return <expr>;
- Expressions:
  - integer literal
  - variable name
  - a + b
  - func()    (zero-arg call)

Register usage:
- r0: memory base (assumed 0)
- r1, r2: expression temps
- r3: expression result / store source
- r7: return/link register for JL/JR
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional


# -----------------------------------------------------------------------------
# Lexer
# -----------------------------------------------------------------------------
TOKEN_RE = re.compile(r"\s*(\d+|[A-Za-z_]\w*|!=|==|[{}();=+,])")


def lex(src: str) -> List[str]:
    # Remove // comments first for predictable tokenization.
    src = re.sub(r"//.*", "", src)
    tokens: List[str] = []
    pos = 0
    while pos < len(src):
        m = TOKEN_RE.match(src, pos)
        if not m:
            if src[pos].isspace():
                pos += 1
                continue
            raise SyntaxError(f"Unexpected character at offset {pos}: {src[pos]!r}")
        tokens.append(m.group(1))
        pos = m.end()
    return tokens


# -----------------------------------------------------------------------------
# AST
# -----------------------------------------------------------------------------
@dataclass
class Expr:
    kind: str
    name: Optional[str] = None
    value: Optional[int] = None
    left: Optional["Expr"] = None
    right: Optional["Expr"] = None


@dataclass
class Stmt:
    kind: str
    name: Optional[str] = None
    expr: Optional[Expr] = None
    cond: Optional[Expr] = None
    then_body: Optional[List["Stmt"]] = None
    else_body: Optional[List["Stmt"]] = None


@dataclass
class Function:
    name: str
    body: List[Stmt]


@dataclass
class Program:
    globals: List[str]
    functions: List[Function]


# -----------------------------------------------------------------------------
# Parser
# -----------------------------------------------------------------------------
class Parser:
    def __init__(self, tokens: List[str]) -> None:
        self.toks = tokens
        self.i = 0

    def peek(self) -> Optional[str]:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self, expected: Optional[str] = None) -> str:
        tok = self.peek()
        if tok is None:
            raise SyntaxError("Unexpected end of input")
        if expected is not None and tok != expected:
            raise SyntaxError(f"Expected {expected!r}, got {tok!r}")
        self.i += 1
        return tok

    def parse_program(self) -> Program:
        globals_: List[str] = []
        funcs: List[Function] = []
        while self.peek() is not None:
            self.take("int")
            name = self.take()
            nxt = self.peek()
            if nxt == ";":
                self.take(";")
                globals_.append(name)
            elif nxt == "(":
                self.take("(")
                self.take(")")
                body = self.parse_block()
                funcs.append(Function(name=name, body=body))
            else:
                raise SyntaxError(f"Expected ';' or '(', got {nxt!r}")
        return Program(globals=globals_, functions=funcs)

    def parse_block(self) -> List[Stmt]:
        self.take("{")
        out: List[Stmt] = []
        while self.peek() != "}":
            out.append(self.parse_stmt())
        self.take("}")
        return out

    def parse_stmt(self) -> Stmt:
        tok = self.peek()
        if tok == "int":
            self.take("int")
            name = self.take()
            if self.peek() == "=":
                self.take("=")
                expr = self.parse_expr()
                self.take(";")
                return Stmt(kind="decl_init", name=name, expr=expr)
            self.take(";")
            return Stmt(kind="decl", name=name)
        if tok == "if":
            self.take("if")
            self.take("(")
            cond = self.parse_expr()
            op = self.take()
            if op not in ("!=", "=="):
                raise SyntaxError("Only != and == are supported in if condition")
            rhs = self.parse_expr()
            self.take(")")
            then_body = self.parse_block()
            else_body: List[Stmt] = []
            if self.peek() == "else":
                self.take("else")
                else_body = self.parse_block()
            # Normalize (a == b) as (!(a != b)) later in codegen via operand order.
            if op == "==":
                cond = Expr(kind="eq", left=cond, right=rhs)
            else:
                cond = Expr(kind="neq", left=cond, right=rhs)
            return Stmt(kind="if", cond=cond, then_body=then_body, else_body=else_body)
        if tok == "return":
            self.take("return")
            expr = self.parse_expr()
            self.take(";")
            return Stmt(kind="return", expr=expr)

        # assignment
        name = self.take()
        self.take("=")
        expr = self.parse_expr()
        self.take(";")
        return Stmt(kind="assign", name=name, expr=expr)

    def parse_expr(self) -> Expr:
        left = self.parse_term()
        while self.peek() == "+":
            self.take("+")
            right = self.parse_term()
            left = Expr(kind="add", left=left, right=right)
        return left

    def parse_term(self) -> Expr:
        tok = self.take()
        if tok.isdigit():
            return Expr(kind="num", value=int(tok))
        if re.fullmatch(r"[A-Za-z_]\w*", tok):
            if self.peek() == "(":
                self.take("(")
                self.take(")")
                return Expr(kind="call", name=tok)
            return Expr(kind="var", name=tok)
        raise SyntaxError(f"Unexpected token in expression: {tok!r}")


# -----------------------------------------------------------------------------
# Code generator
# -----------------------------------------------------------------------------
class CodeGen:
    def __init__(self, prog: Program) -> None:
        self.prog = prog
        self.lines: List[str] = []
        self.data_symbols: Dict[str, int] = {}
        self.func_locals: Dict[str, Dict[str, str]] = {}
        self.label_id = 0

    def unique_label(self, prefix: str) -> str:
        self.label_id += 1
        return f"{prefix}_{self.label_id}"

    def emit(self, s: str = "") -> None:
        self.lines.append(s)

    def collect_locals(self) -> None:
        for fn in self.prog.functions:
            locals_map: Dict[str, str] = {}

            def walk(stmts: List[Stmt]) -> None:
                for st in stmts:
                    if st.kind in ("decl", "decl_init") and st.name is not None:
                        if st.name not in locals_map:
                            locals_map[st.name] = f"{fn.name}_{st.name}"
                    if st.kind == "if":
                        walk(st.then_body or [])
                        walk(st.else_body or [])

            walk(fn.body)
            self.func_locals[fn.name] = locals_map

    def resolve_var_label(self, fn: str, name: str) -> str:
        if name in self.func_locals[fn]:
            label = self.func_locals[fn][name]
            self.data_symbols.setdefault(label, 0)
            return label
        if name in self.prog.globals:
            self.data_symbols.setdefault(name, 0)
            return name
        raise NameError(f"Unknown variable: {name}")

    def const_eval(self, expr: Optional[Expr]) -> Optional[int]:
        if expr is None:
            return None
        if expr.kind == "num":
            return expr.value
        if expr.kind == "add":
            left = self.const_eval(expr.left)
            right = self.const_eval(expr.right)
            if left is None or right is None:
                return None
            return left + right
        return None

    def emit_load_expr(self, fn: str, expr: Expr, target: str) -> None:
        if expr.kind == "num":
            self.emit(f"    LDI   {target}, {expr.value}")
            return
        if expr.kind == "var":
            label = self.resolve_var_label(fn, expr.name or "")
            self.emit(f"    LD    {target}, {label}(r0)")
            return
        if expr.kind == "call":
            self.emit(f"    JL    r7, {expr.name}")
            self.emit(f"    ADDI  {target}, r1, 0")
            return
        if expr.kind == "add":
            self.emit_load_expr(fn, expr.left, "r1")
            self.emit_load_expr(fn, expr.right, "r2")
            self.emit("    ADD   r3, r1, r2")
            if target != "r3":
                self.emit(f"    ADDI  {target}, r3, 0")
            return
        raise ValueError(f"Unsupported expression kind: {expr.kind}")

    def emit_condition(self, fn: str, cond: Expr, false_label: str) -> None:
        # Supported condition encodings:
        # neq: branch to false when equal (via SUB then BEZ)
        # eq:  branch to false when not equal (via SUB then BNZ)
        if cond.kind not in ("neq", "eq"):
            raise ValueError("if condition must be a != b or a == b")
        self.emit_load_expr(fn, cond.left, "r1")
        self.emit_load_expr(fn, cond.right, "r2")
        self.emit("    SUB   r3, r1, r2")
        if cond.kind == "neq":
            self.emit(f"    BEZ   r3, {false_label}")
        else:
            self.emit(f"    BNZ   r3, {false_label}")

    def emit_stmt(self, fn: str, st: Stmt, is_main: bool) -> None:
        if st.kind == "decl":
            # Storage already allocated in .data; no runtime code needed.
            if st.name:
                _ = self.resolve_var_label(fn, st.name)
            return

        if st.kind == "decl_init":
            label = self.resolve_var_label(fn, st.name or "")
            const_value = self.const_eval(st.expr)
            if const_value is not None:
                self.data_symbols[label] = const_value
                return
            self.emit_load_expr(fn, st.expr, "r3")
            self.emit(f"    ST    r3, {label}(r0)")
            return

        if st.kind == "assign":
            label = self.resolve_var_label(fn, st.name or "")
            self.emit_load_expr(fn, st.expr, "r3")
            self.emit(f"    ST    r3, {label}(r0)")
            return

        if st.kind == "if":
            else_label = self.unique_label("else")
            end_label = self.unique_label("ifend")
            self.emit_condition(fn, st.cond, else_label)
            for inner in st.then_body or []:
                self.emit_stmt(fn, inner, is_main)
            self.emit(f"    BEZ   r0, {end_label}")
            self.emit(f"{else_label}:")
            for inner in st.else_body or []:
                self.emit_stmt(fn, inner, is_main)
            self.emit(f"{end_label}:")
            return

        if st.kind == "return":
            self.emit_load_expr(fn, st.expr, "r1")
            if is_main:
                self.emit("    HALT")
            else:
                self.emit("    JR    r7")
            return

        raise ValueError(f"Unsupported statement kind: {st.kind}")

    def stmt_guarantees_return(self, st: Stmt) -> bool:
        if st.kind == "return":
            return True
        if st.kind == "if":
            then_body = st.then_body or []
            else_body = st.else_body or []
            if not then_body or not else_body:
                return False
            return self.block_guarantees_return(then_body) and self.block_guarantees_return(else_body)
        return False

    def block_guarantees_return(self, body: List[Stmt]) -> bool:
        for st in body:
            if self.stmt_guarantees_return(st):
                return True
        return False

    def generate(self) -> str:
        self.collect_locals()

        # Ensure all known globals end up in data section even if never referenced.
        for g in self.prog.globals:
            self.data_symbols.setdefault(g, 0)

        self.emit(".text")
        self.emit(".global main")
        self.emit("")

        for fn in self.prog.functions:
            is_main = fn.name == "main"
            self.emit(f"{fn.name}:")
            for st in fn.body:
                self.emit_stmt(fn.name, st, is_main)
            # Safety fall-through behavior.
            if not self.block_guarantees_return(fn.body):
                if not is_main:
                    self.emit("    JR    r7")
                else:
                    self.emit("    HALT")
            self.emit("")

        self.emit(".data")
        for sym in sorted(self.data_symbols):
            self.emit(f"{sym}: .word {self.data_symbols[sym]}")

        return "\n".join(self.lines).rstrip() + "\n"


def main() -> None:
    if len(sys.argv) == 1:
        in_path = "c-instr-ref.c"
        out_path = "assembly-instr-ref.s"
    elif len(sys.argv) == 3:
        in_path = sys.argv[1]
        out_path = sys.argv[2]
    else:
        print("usage: python3 compile.py [input.c output.s]")
        sys.exit(1)

    with open(in_path, "r", encoding="utf-8") as f:
        src = f.read()
    tokens = lex(src)
    prog = Parser(tokens).parse_program()
    asm = CodeGen(prog).generate()
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(asm)
    print(f"Wrote assembly to {out_path}")


if __name__ == "__main__":
    main()
