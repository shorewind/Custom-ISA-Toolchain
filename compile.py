#!/usr/bin/env python3
"""
compile.py: Tiny C -> custom ISA assembly compiler for an expanded C subset.

Supported subset:
- Declarations:
  - int x;
  - int x = expression;
  - int a[10];
- Assignment:
  - x = expression;
  - a[i] = expression;
- Expressions:
  - integer literals (16-bit two's-complement expected by ISA)
  - variables and array indexing
  - function calls
  - +, -, &, |
- Control flow:
  - if / else
  - while
  - for
  - Relational operators in conditions: ==, !=, >, <=, <, >=
- Functions:
  - return expression;
  - parameters by value and by reference
  - by-reference syntax accepted as either:
    - int &x

Important codegen note:
- This ISA/toolchain has no hardware stack pointer in the exposed subset, so
  argument slots and temporaries are statically allocated in .data per function.
  Recursion/reentrant calls are therefore not supported.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional


# -----------------------------------------------------------------------------
# Lexer
# -----------------------------------------------------------------------------
TOKEN_RE = re.compile(
    r"\s*(<=|>=|==|!=|[A-Za-z_]\w*|\d+|[{}()\[\];,+\-=&|<>])"
)


def lex(src: str) -> List[str]:
    src = re.sub(r"//.*", "", src)
    toks: List[str] = []
    pos = 0
    while pos < len(src):
        m = TOKEN_RE.match(src, pos)
        if not m:
            if src[pos].isspace():
                pos += 1
                continue
            raise SyntaxError(f"Unexpected character at offset {pos}: {src[pos]!r}")
        toks.append(m.group(1))
        pos = m.end()
    return toks


# -----------------------------------------------------------------------------
# AST
# -----------------------------------------------------------------------------
@dataclass
class VarDecl:
    name: str
    size: int = 1
    init: Optional["Expr"] = None


@dataclass
class Param:
    name: str
    by_ref: bool = False


@dataclass
class Expr:
    kind: str
    name: Optional[str] = None
    value: Optional[int] = None
    left: Optional["Expr"] = None
    right: Optional["Expr"] = None
    args: Optional[List["Expr"]] = None
    index: Optional["Expr"] = None


@dataclass
class Cond:
    left: Expr
    op: str
    right: Optional[Expr] = None


@dataclass
class Assign:
    target_name: str
    target_index: Optional[Expr]
    expr: Expr


@dataclass
class Stmt:
    kind: str
    decl: Optional[VarDecl] = None
    assign: Optional[Assign] = None
    cond: Optional[Cond] = None
    then_body: Optional[List["Stmt"]] = None
    else_body: Optional[List["Stmt"]] = None
    body: Optional[List["Stmt"]] = None
    init: Optional["Stmt"] = None
    update: Optional["Stmt"] = None
    expr: Optional[Expr] = None


@dataclass
class Function:
    name: str
    params: List[Param]
    body: List[Stmt]


@dataclass
class Program:
    globals: List[VarDecl]
    functions: List[Function]


# -----------------------------------------------------------------------------
# Parser
# -----------------------------------------------------------------------------
REL_OPS = {"==", "!=", ">", "<=", "<", ">="}


class Parser:
    def __init__(self, tokens: List[str]) -> None:
        self.toks = tokens
        self.i = 0

    def peek(self) -> Optional[str]:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def peek_n(self, n: int) -> Optional[str]:
        j = self.i + n
        return self.toks[j] if j < len(self.toks) else None

    def take(self, expected: Optional[str] = None) -> str:
        tok = self.peek()
        if tok is None:
            raise SyntaxError("Unexpected end of input")
        if expected is not None and tok != expected:
            raise SyntaxError(f"Expected {expected!r}, got {tok!r}")
        self.i += 1
        return tok

    def take_ident(self) -> str:
        tok = self.take()
        if not re.fullmatch(r"[A-Za-z_]\w*", tok):
            raise SyntaxError(f"Expected identifier, got {tok!r}")
        return tok

    def parse_program(self) -> Program:
        globals_: List[VarDecl] = []
        funcs: List[Function] = []

        while self.peek() is not None:
            self.take("int")
            name = self.take_ident()
            nxt = self.peek()

            if nxt == "(":
                self.take("(")
                params = self.parse_params()
                self.take(")")
                body = self.parse_block()
                funcs.append(Function(name=name, params=params, body=body))
                continue

            decl = self.finish_decl_after_name(name, allow_init=False)
            globals_.append(decl)

        return Program(globals=globals_, functions=funcs)

    def parse_params(self) -> List[Param]:
        params: List[Param] = []
        if self.peek() == ")":
            return params

        while True:
            by_ref = False

            if self.peek() == "ref":
                self.take("ref")
                self.take("int")
                name = self.take_ident()
                by_ref = True
            else:
                self.take("int")
                if self.peek() == "&":
                    self.take("&")
                    by_ref = True
                name = self.take_ident()

            params.append(Param(name=name, by_ref=by_ref))

            if self.peek() == ",":
                self.take(",")
                continue
            break

        return params

    def parse_block(self) -> List[Stmt]:
        self.take("{")
        out: List[Stmt] = []
        while self.peek() != "}":
            out.append(self.parse_stmt())
        self.take("}")
        return out

    def finish_decl_after_name(self, name: str, allow_init: bool, require_semi: bool = True) -> VarDecl:
        if self.peek() == "[":
            self.take("[")
            size_tok = self.take()
            if not size_tok.isdigit():
                raise SyntaxError("Array size must be a positive integer literal")
            size = int(size_tok)
            if size <= 0:
                raise SyntaxError("Array size must be > 0")
            self.take("]")
            if require_semi:
                self.take(";")
            return VarDecl(name=name, size=size)

        init: Optional[Expr] = None
        if allow_init and self.peek() == "=":
            self.take("=")
            init = self.parse_expr()

        if require_semi:
            self.take(";")
        return VarDecl(name=name, size=1, init=init)

    def parse_decl_stmt(self, require_semi: bool = True) -> Stmt:
        self.take("int")
        name = self.take_ident()
        decl = self.finish_decl_after_name(name, allow_init=True, require_semi=require_semi)
        return Stmt(kind="decl", decl=decl)

    def parse_lvalue(self) -> tuple[str, Optional[Expr]]:
        name = self.take_ident()
        idx: Optional[Expr] = None
        if self.peek() == "[":
            self.take("[")
            idx = self.parse_expr()
            self.take("]")
        return name, idx

    def parse_assign_stmt(self, require_semi: bool) -> Stmt:
        name, idx = self.parse_lvalue()
        self.take("=")
        expr = self.parse_expr()
        if require_semi:
            self.take(";")
        return Stmt(kind="assign", assign=Assign(target_name=name, target_index=idx, expr=expr))

    def parse_call_stmt(self, require_semi: bool) -> Stmt:
        call_expr = self.parse_postfix(Expr(kind="var", name=self.take_ident()))
        if call_expr.kind != "call":
            raise SyntaxError("Only assignment or function call statements are supported")
        if require_semi:
            self.take(";")
        return Stmt(kind="expr", expr=call_expr)

    def parse_condition(self) -> Cond:
        left = self.parse_expr()
        if self.peek() in REL_OPS:
            op = self.take()
            right = self.parse_expr()
            return Cond(left=left, op=op, right=right)
        return Cond(left=left, op="!=", right=Expr(kind="num", value=0))

    def parse_for_init(self) -> Optional[Stmt]:
        if self.peek() == ";":
            return None
        if self.peek() == "int":
            return self.parse_decl_stmt(require_semi=False)
        return self.parse_assign_stmt(require_semi=False)

    def parse_stmt(self) -> Stmt:
        tok = self.peek()

        if tok == "{":
            return Stmt(kind="block", body=self.parse_block())

        if tok == "int":
            return self.parse_decl_stmt()

        if tok == "if":
            self.take("if")
            self.take("(")
            cond = self.parse_condition()
            self.take(")")
            then_body = self.parse_block()
            else_body: List[Stmt] = []
            if self.peek() == "else":
                self.take("else")
                else_body = self.parse_block()
            return Stmt(kind="if", cond=cond, then_body=then_body, else_body=else_body)

        if tok == "while":
            self.take("while")
            self.take("(")
            cond = self.parse_condition()
            self.take(")")
            body = self.parse_block()
            return Stmt(kind="while", cond=cond, body=body)

        if tok == "for":
            self.take("for")
            self.take("(")
            init = self.parse_for_init()
            self.take(";")

            cond: Optional[Cond] = None
            if self.peek() != ";":
                cond = self.parse_condition()
            self.take(";")

            update: Optional[Stmt] = None
            if self.peek() != ")":
                update = self.parse_assign_stmt(require_semi=False)
            self.take(")")

            body = self.parse_block()
            return Stmt(kind="for", init=init, cond=cond, update=update, body=body)

        if tok == "return":
            self.take("return")
            expr = self.parse_expr()
            self.take(";")
            return Stmt(kind="return", expr=expr)

        if tok is None:
            raise SyntaxError("Unexpected end of input in statement")

        if not re.fullmatch(r"[A-Za-z_]\w*", tok):
            raise SyntaxError(f"Unexpected token in statement: {tok!r}")

        # Distinguish assignment vs call statement.
        if self.peek_n(1) == "(":
            return self.parse_call_stmt(require_semi=True)
        return self.parse_assign_stmt(require_semi=True)

    def parse_expr(self) -> Expr:
        return self.parse_or()

    def parse_or(self) -> Expr:
        left = self.parse_and()
        while self.peek() == "|":
            self.take("|")
            right = self.parse_and()
            left = Expr(kind="or", left=left, right=right)
        return left

    def parse_and(self) -> Expr:
        left = self.parse_add_sub()
        while self.peek() == "&":
            self.take("&")
            right = self.parse_add_sub()
            left = Expr(kind="and", left=left, right=right)
        return left

    def parse_add_sub(self) -> Expr:
        left = self.parse_unary()
        while self.peek() in ("+", "-"):
            op = self.take()
            right = self.parse_unary()
            left = Expr(kind="add" if op == "+" else "sub", left=left, right=right)
        return left

    def parse_unary(self) -> Expr:
        if self.peek() == "-":
            self.take("-")
            inner = self.parse_unary()
            return Expr(kind="sub", left=Expr(kind="num", value=0), right=inner)
        return self.parse_primary()

    def parse_primary(self) -> Expr:
        tok = self.peek()
        if tok is None:
            raise SyntaxError("Unexpected end of input in expression")

        if tok.isdigit():
            self.take()
            return Expr(kind="num", value=int(tok))

        if tok == "(":
            self.take("(")
            e = self.parse_expr()
            self.take(")")
            return e

        if re.fullmatch(r"[A-Za-z_]\w*", tok):
            self.take()
            return self.parse_postfix(Expr(kind="var", name=tok))

        raise SyntaxError(f"Unexpected token in expression: {tok!r}")

    def parse_postfix(self, base: Expr) -> Expr:
        out = base
        while True:
            if self.peek() == "(":
                self.take("(")
                args: List[Expr] = []
                if self.peek() != ")":
                    while True:
                        args.append(self.parse_expr())
                        if self.peek() == ",":
                            self.take(",")
                            continue
                        break
                self.take(")")
                out = Expr(kind="call", name=out.name, args=args)
                continue

            if self.peek() == "[":
                self.take("[")
                idx = self.parse_expr()
                self.take("]")
                if out.kind != "var":
                    raise SyntaxError("Array indexing must apply to a variable name")
                out = Expr(kind="array", name=out.name, index=idx)
                continue

            break

        return out


# -----------------------------------------------------------------------------
# Code generator
# -----------------------------------------------------------------------------
@dataclass
class SymbolInfo:
    kind: str  # scalar, array, param_val, param_ref
    label: str
    size: int = 1


class CodeGen:
    def __init__(self, prog: Program) -> None:
        self.prog = prog
        self.lines: List[str] = []
        self.label_counters: Dict[str, int] = {
            "if": 0,
            "while": 0,
            "for": 0,
        }

        self.global_symbols: Dict[str, SymbolInfo] = {}
        self.func_symbols: Dict[str, Dict[str, SymbolInfo]] = {}
        self.func_params: Dict[str, List[Param]] = {}

        # Data layout entries in emission order.
        self.data_entries: List[tuple[str, int | str]] = []
        self.data_seen: set[str] = set()
        self.data_index: Dict[str, int] = {}

        # Label-address helpers for pointer math.
        self.addr_helpers: Dict[str, str] = {}
        self.fn_needs_tmp: Dict[str, bool] = {}
        self.fn_needs_saved_r7: Dict[str, bool] = {}

    def next_struct_id(self, struct_kind: str) -> int:
        self.label_counters[struct_kind] += 1
        return self.label_counters[struct_kind]

    def emit(self, s: str = "") -> None:
        self.lines.append(s)

    def add_data_word(self, label: str, value: int | str = 0) -> None:
        if label in self.data_seen:
            return
        self.data_seen.add(label)
        self.data_index[label] = len(self.data_entries)
        self.data_entries.append((label, value))

    def set_data_word(self, label: str, value: int | str) -> None:
        idx = self.data_index.get(label)
        if idx is None:
            raise KeyError(f"Data label not found: {label}")
        self.data_entries[idx] = (label, value)

    def add_data_words(self, base_label: str, count: int, init: int = 0) -> None:
        self.add_data_word(base_label, init)
        for i in range(1, count):
            self.add_data_word(f"{base_label}_{i}", init)

    def addr_helper_label(self, target_label: str) -> str:
        if target_label not in self.addr_helpers:
            helper = f"addr_{target_label}"
            self.addr_helpers[target_label] = helper
            self.add_data_word(helper, target_label)
        return self.addr_helpers[target_label]

    def const_eval(self, expr: Optional[Expr]) -> Optional[int]:
        if expr is None:
            return None
        if expr.kind == "num":
            return expr.value
        if expr.kind in ("add", "sub", "and", "or"):
            left = self.const_eval(expr.left)
            right = self.const_eval(expr.right)
            if left is None or right is None:
                return None
            if expr.kind == "add":
                return left + right
            if expr.kind == "sub":
                return left - right
            if expr.kind == "and":
                return left & right
            if expr.kind == "or":
                return left | right
        return None

    def expr_contains_call(self, expr: Optional[Expr]) -> bool:
        if expr is None:
            return False
        if expr.kind == "call":
            return True
        if expr.kind in ("add", "sub", "and", "or"):
            return self.expr_contains_call(expr.left) or self.expr_contains_call(expr.right)
        if expr.kind == "array":
            return self.expr_contains_call(expr.index)
        if expr.kind in ("num", "var"):
            return False
        for a in expr.args or []:
            if self.expr_contains_call(a):
                return True
        return False

    def stmt_contains_call(self, st: Stmt) -> bool:
        if st.kind == "decl" and st.decl is not None:
            return self.expr_contains_call(st.decl.init)
        if st.kind == "assign" and st.assign is not None:
            return self.expr_contains_call(st.assign.expr) or self.expr_contains_call(st.assign.target_index)
        if st.kind == "expr":
            return self.expr_contains_call(st.expr)
        if st.kind == "return":
            return self.expr_contains_call(st.expr)
        if st.kind == "if":
            c = st.cond
            c_has = c is not None and (self.expr_contains_call(c.left) or self.expr_contains_call(c.right))
            return c_has or any(self.stmt_contains_call(x) for x in (st.then_body or [])) or any(
                self.stmt_contains_call(x) for x in (st.else_body or [])
            )
        if st.kind in ("while", "for"):
            c = st.cond
            c_has = c is not None and (self.expr_contains_call(c.left) or self.expr_contains_call(c.right))
            init_has = st.init is not None and self.stmt_contains_call(st.init)
            upd_has = st.update is not None and self.stmt_contains_call(st.update)
            body_has = any(self.stmt_contains_call(x) for x in (st.body or []))
            return c_has or init_has or upd_has or body_has
        if st.kind == "block":
            return any(self.stmt_contains_call(x) for x in (st.body or []))
        return False

    def stmt_needs_tmp(self, st: Stmt) -> bool:
        def expr_needs_tmp(e: Optional[Expr]) -> bool:
            if e is None:
                return False
            if e.kind in ("add", "sub", "and", "or"):
                if self.expr_contains_call(e.right):
                    return True
                return expr_needs_tmp(e.left) or expr_needs_tmp(e.right)
            if e.kind == "array":
                return expr_needs_tmp(e.index)
            if e.kind == "call":
                return any(expr_needs_tmp(a) for a in (e.args or []))
            return False

        if st.kind == "decl" and st.decl is not None:
            return expr_needs_tmp(st.decl.init)
        if st.kind == "assign" and st.assign is not None:
            return expr_needs_tmp(st.assign.expr) or expr_needs_tmp(st.assign.target_index)
        if st.kind == "expr":
            return expr_needs_tmp(st.expr)
        if st.kind == "return":
            return expr_needs_tmp(st.expr)
        if st.kind in ("if", "while", "for"):
            c = st.cond
            c_need = c is not None and (expr_needs_tmp(c.left) or expr_needs_tmp(c.right) or self.expr_contains_call(c.right))
            init_need = st.init is not None and self.stmt_needs_tmp(st.init)
            upd_need = st.update is not None and self.stmt_needs_tmp(st.update)
            then_need = any(self.stmt_needs_tmp(x) for x in (st.then_body or []))
            else_need = any(self.stmt_needs_tmp(x) for x in (st.else_body or []))
            body_need = any(self.stmt_needs_tmp(x) for x in (st.body or []))
            return c_need or init_need or upd_need or then_need or else_need or body_need
        if st.kind == "block":
            return any(self.stmt_needs_tmp(x) for x in (st.body or []))
        return False

    def fn_tmp_label(self, fn: str) -> str:
        return f"{fn}_tmp"

    def fn_saved_r7_label(self, fn: str) -> str:
        return f"{fn}_saved_r7"

    def collect_symbols(self) -> None:
        for g in self.prog.globals:
            if g.name in self.global_symbols:
                raise NameError(f"Duplicate global: {g.name}")
            if g.size == 1:
                self.global_symbols[g.name] = SymbolInfo(kind="scalar", label=g.name, size=1)
                self.add_data_word(g.name, 0)
            else:
                self.global_symbols[g.name] = SymbolInfo(kind="array", label=g.name, size=g.size)
                self.add_data_words(g.name, g.size, 0)

        for fn in self.prog.functions:
            if fn.name in self.func_symbols:
                raise NameError(f"Duplicate function: {fn.name}")
            local_map: Dict[str, SymbolInfo] = {}
            self.func_symbols[fn.name] = local_map
            self.func_params[fn.name] = fn.params
            self.fn_needs_saved_r7[fn.name] = fn.name != "main" and any(
                self.stmt_contains_call(st) for st in fn.body
            )
            self.fn_needs_tmp[fn.name] = any(self.stmt_needs_tmp(st) for st in fn.body)

            for p in fn.params:
                if p.name in local_map:
                    raise NameError(f"Duplicate parameter in {fn.name}: {p.name}")
                if p.by_ref:
                    slot = f"{fn.name}_p_ref_{p.name}"
                    local_map[p.name] = SymbolInfo(kind="param_ref", label=slot, size=1)
                    self.add_data_word(slot, 0)
                else:
                    slot = f"{fn.name}_p_val_{p.name}"
                    local_map[p.name] = SymbolInfo(kind="param_val", label=slot, size=1)
                    self.add_data_word(slot, 0)

            if self.fn_needs_tmp[fn.name]:
                self.add_data_word(self.fn_tmp_label(fn.name), 0)
            if self.fn_needs_saved_r7[fn.name]:
                self.add_data_word(self.fn_saved_r7_label(fn.name), 0)

            def walk(stmts: List[Stmt]) -> None:
                for st in stmts:
                    if st.kind == "decl" and st.decl is not None:
                        d = st.decl
                        if d.name in local_map:
                            raise NameError(f"Duplicate local in {fn.name}: {d.name}")
                        if d.size == 1:
                            lbl = f"{fn.name}_{d.name}"
                            local_map[d.name] = SymbolInfo(kind="scalar", label=lbl, size=1)
                            self.add_data_word(lbl, 0)
                            if fn.name == "main":
                                k = self.const_eval(d.init)
                                if k is not None:
                                    self.set_data_word(lbl, k)
                        else:
                            lbl = f"{fn.name}_{d.name}"
                            local_map[d.name] = SymbolInfo(kind="array", label=lbl, size=d.size)
                            self.add_data_words(lbl, d.size, 0)

                    if st.kind == "if":
                        walk(st.then_body or [])
                        walk(st.else_body or [])
                    elif st.kind in ("while", "for", "block"):
                        walk(st.body or [])

            walk(fn.body)

    def lookup_symbol(self, fn: str, name: str) -> SymbolInfo:
        if name in self.func_symbols.get(fn, {}):
            return self.func_symbols[fn][name]
        if name in self.global_symbols:
            return self.global_symbols[name]
        raise NameError(f"Unknown variable: {name}")

    def emit_load_scalar(self, fn: str, name: str, target: str) -> None:
        info = self.lookup_symbol(fn, name)
        if info.kind in ("scalar", "param_val"):
            self.emit(f"    LD    {target}, {info.label}(r0)")
            return
        if info.kind == "param_ref":
            self.emit(f"    LD    r6, {info.label}(r0)")
            self.emit(f"    LD    {target}, 0(r6)")
            return
        raise ValueError(f"Cannot read array variable '{name}' without index")

    def emit_store_scalar(self, fn: str, name: str, src: str) -> None:
        info = self.lookup_symbol(fn, name)
        if info.kind in ("scalar", "param_val"):
            self.emit(f"    ST    {src}, {info.label}(r0)")
            return
        if info.kind == "param_ref":
            self.emit(f"    LD    r6, {info.label}(r0)")
            self.emit(f"    ST    {src}, 0(r6)")
            return
        raise ValueError(f"Cannot assign array variable '{name}' without index")

    def emit_load_address_of_scalar(self, fn: str, name: str, target: str) -> None:
        info = self.lookup_symbol(fn, name)
        if info.kind in ("scalar", "param_val"):
            helper = self.addr_helper_label(info.label)
            self.emit(f"    LD    {target}, {helper}(r0)")
            return
        if info.kind == "param_ref":
            self.emit(f"    LD    {target}, {info.label}(r0)")
            return
        raise ValueError(f"Cannot take scalar address of array '{name}'")

    def emit_load_array_elem(self, fn: str, name: str, index_expr: Expr, target: str) -> None:
        info = self.lookup_symbol(fn, name)
        if info.kind != "array":
            raise ValueError(f"'{name}' is not an array")

        const_idx = self.const_eval(index_expr)
        if const_idx is not None:
            if const_idx == 0:
                self.emit(f"    LD    {target}, {info.label}(r0)")
            elif const_idx > 0:
                self.emit(f"    LD    {target}, {info.label}+{const_idx}(r0)")
            else:
                self.emit(f"    LD    {target}, {info.label}{const_idx}(r0)")
            return

        self.emit_expr(fn, index_expr, "r2")
        helper = self.addr_helper_label(info.label)
        self.emit(f"    LD    r5, {helper}(r0)")
        self.emit("    ADD   r6, r5, r2")
        self.emit(f"    LD    {target}, 0(r6)")

    def emit_store_array_elem(self, fn: str, name: str, index_expr: Expr, src: str) -> None:
        info = self.lookup_symbol(fn, name)
        if info.kind != "array":
            raise ValueError(f"'{name}' is not an array")

        const_idx = self.const_eval(index_expr)
        if const_idx is not None:
            if const_idx == 0:
                self.emit(f"    ST    {src}, {info.label}(r0)")
            elif const_idx > 0:
                self.emit(f"    ST    {src}, {info.label}+{const_idx}(r0)")
            else:
                self.emit(f"    ST    {src}, {info.label}{const_idx}(r0)")
            return

        self.emit_expr(fn, index_expr, "r2")
        helper = self.addr_helper_label(info.label)
        self.emit(f"    LD    r5, {helper}(r0)")
        self.emit("    ADD   r6, r5, r2")
        self.emit(f"    ST    {src}, 0(r6)")

    def emit_load_lvalue_address(self, fn: str, name: str, index_expr: Optional[Expr], target: str) -> None:
        if index_expr is None:
            self.emit_load_address_of_scalar(fn, name, target)
            return

        info = self.lookup_symbol(fn, name)
        if info.kind != "array":
            raise ValueError(f"Cannot index non-array '{name}'")
        self.emit_expr(fn, index_expr, "r2")
        helper = self.addr_helper_label(info.label)
        self.emit(f"    LD    r5, {helper}(r0)")
        self.emit(f"    ADD   {target}, r5, r2")

    def emit_call(self, fn: str, call_expr: Expr, target: str) -> None:
        callee = call_expr.name or ""
        callee_fn = None
        for f in self.prog.functions:
            if f.name == callee:
                callee_fn = f
                break
        if callee_fn is None:
            raise NameError(f"Unknown function: {callee}")

        args = call_expr.args or []
        if len(args) != len(callee_fn.params):
            raise SyntaxError(
                f"Function '{callee}' expects {len(callee_fn.params)} arg(s), got {len(args)}"
            )

        for p, a in zip(callee_fn.params, args):
            if p.by_ref:
                if a.kind == "var":
                    self.emit_load_lvalue_address(fn, a.name or "", None, "r3")
                elif a.kind == "array":
                    self.emit_load_lvalue_address(fn, a.name or "", a.index, "r3")
                else:
                    raise SyntaxError(
                        f"By-reference parameter '{p.name}' in call to '{callee}' requires an lvalue"
                    )
                slot = self.lookup_symbol(callee, p.name).label
                self.emit(f"    ST    r3, {slot}(r0)")
            else:
                self.emit_expr(fn, a, "r3")
                slot = self.lookup_symbol(callee, p.name).label
                self.emit(f"    ST    r3, {slot}(r0)")

        # Preserve return-link register in non-main functions.
        if self.fn_needs_saved_r7.get(fn, False):
            self.emit(f"    ST    r7, {self.fn_saved_r7_label(fn)}(r0)")
        self.emit(f"    JL    r7, {callee}")
        if self.fn_needs_saved_r7.get(fn, False):
            self.emit(f"    LD    r7, {self.fn_saved_r7_label(fn)}(r0)")

        if target != "r1":
            self.emit(f"    ADDI  {target}, r1, 0")

    def emit_expr(self, fn: str, expr: Expr, target: str) -> None:
        if expr.kind == "num":
            self.emit(f"    LDI   {target}, {expr.value}")
            return

        if expr.kind == "var":
            self.emit_load_scalar(fn, expr.name or "", target)
            return

        if expr.kind == "array":
            self.emit_load_array_elem(fn, expr.name or "", expr.index, target)
            return

        if expr.kind == "call":
            self.emit_call(fn, expr, target)
            return

        if expr.kind in ("add", "sub", "and", "or"):
            self.emit_expr(fn, expr.left, "r1")
            if self.expr_contains_call(expr.right):
                tmp = self.fn_tmp_label(fn)
                self.emit(f"    ST    r1, {tmp}(r0)")
            self.emit_expr(fn, expr.right, "r2")
            if self.expr_contains_call(expr.right):
                tmp = self.fn_tmp_label(fn)
                self.emit(f"    LD    r1, {tmp}(r0)")

            if expr.kind == "add":
                self.emit("    ADD   r3, r1, r2")
            elif expr.kind == "sub":
                self.emit("    SUB   r3, r1, r2")
            elif expr.kind == "and":
                self.emit("    AND   r3, r1, r2")
            elif expr.kind == "or":
                self.emit("    OR    r3, r1, r2")

            if target != "r3":
                self.emit(f"    ADDI  {target}, r3, 0")
            return

        raise ValueError(f"Unsupported expression kind: {expr.kind}")

    def emit_condition_false_branch(self, fn: str, cond: Cond, false_label: str) -> None:
        self.emit_expr(fn, cond.left, "r1")
        if self.expr_contains_call(cond.right):
            tmp = self.fn_tmp_label(fn)
            self.emit(f"    ST    r1, {tmp}(r0)")
        self.emit_expr(fn, cond.right, "r2")
        if self.expr_contains_call(cond.right):
            tmp = self.fn_tmp_label(fn)
            self.emit(f"    LD    r1, {tmp}(r0)")

        if cond.op == "==":
            self.emit("    SUB   r3, r1, r2")
            self.emit(f"    BNZ   r3, {false_label}")
            return

        if cond.op == "!=":
            self.emit("    SUB   r3, r1, r2")
            self.emit(f"    BEZ   r3, {false_label}")
            return

        if cond.op == "<":
            self.emit("    SLT   r3, r1, r2")
            self.emit(f"    BEZ   r3, {false_label}")
            return

        if cond.op == ">":
            self.emit("    SLT   r3, r2, r1")
            self.emit(f"    BEZ   r3, {false_label}")
            return

        if cond.op == "<=":
            self.emit("    SLT   r3, r2, r1")
            self.emit(f"    BNZ   r3, {false_label}")
            return

        if cond.op == ">=":
            self.emit("    SLT   r3, r1, r2")
            self.emit(f"    BNZ   r3, {false_label}")
            return

        raise ValueError(f"Unsupported relational operator: {cond.op}")

    def emit_stmt(self, fn: str, st: Stmt, is_main: bool) -> None:
        if st.kind == "decl":
            if st.decl is None:
                return
            d = st.decl
            if d.init is not None:
                if is_main and self.const_eval(d.init) is not None:
                    return
                self.emit_expr(fn, d.init, "r3")
                self.emit_store_scalar(fn, d.name, "r3")
            return

        if st.kind == "assign":
            if st.assign is None:
                return
            a = st.assign
            self.emit_expr(fn, a.expr, "r3")
            if a.target_index is None:
                self.emit_store_scalar(fn, a.target_name, "r3")
            else:
                self.emit_store_array_elem(fn, a.target_name, a.target_index, "r3")
            return

        if st.kind == "expr":
            if st.expr is not None:
                self.emit_expr(fn, st.expr, "r1")
            return

        if st.kind == "block":
            for inner in st.body or []:
                self.emit_stmt(fn, inner, is_main)
            return

        if st.kind == "if":
            sid = self.next_struct_id("if")
            else_lbl = f"else_{sid}"
            end_lbl = f"ifend_{sid}"
            if st.cond is None:
                raise ValueError("if missing condition")
            self.emit_condition_false_branch(fn, st.cond, else_lbl)
            for inner in st.then_body or []:
                self.emit_stmt(fn, inner, is_main)
            self.emit(f"    BEZ   r0, {end_lbl}")
            self.emit(f"{else_lbl}:")
            for inner in st.else_body or []:
                self.emit_stmt(fn, inner, is_main)
            self.emit(f"{end_lbl}:")
            return

        if st.kind == "while":
            sid = self.next_struct_id("while")
            start_lbl = f"while_start_{sid}"
            end_lbl = f"while_end_{sid}"
            self.emit(f"{start_lbl}:")
            if st.cond is None:
                raise ValueError("while missing condition")
            self.emit_condition_false_branch(fn, st.cond, end_lbl)
            for inner in st.body or []:
                self.emit_stmt(fn, inner, is_main)
            self.emit(f"    BEZ   r0, {start_lbl}")
            self.emit(f"{end_lbl}:")
            return

        if st.kind == "for":
            if st.init is not None:
                self.emit_stmt(fn, st.init, is_main)

            sid = self.next_struct_id("for")
            start_lbl = f"for_start_{sid}"
            end_lbl = f"for_end_{sid}"
            self.emit(f"{start_lbl}:")
            if st.cond is not None:
                self.emit_condition_false_branch(fn, st.cond, end_lbl)

            for inner in st.body or []:
                self.emit_stmt(fn, inner, is_main)

            if st.update is not None:
                self.emit_stmt(fn, st.update, is_main)

            self.emit(f"    BEZ   r0, {start_lbl}")
            self.emit(f"{end_lbl}:")
            return

        if st.kind == "return":
            if st.expr is None:
                raise ValueError("return requires expression")
            self.emit_expr(fn, st.expr, "r1")
            if is_main:
                self.emit("    HALT")
            else:
                self.emit("    JR    r7")
            return

        raise ValueError(f"Unsupported statement kind: {st.kind}")

    def stmt_guarantees_return(self, st: Stmt) -> bool:
        if st.kind == "return":
            return True
        if st.kind == "block":
            return self.block_guarantees_return(st.body or [])
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
        self.collect_symbols()

        self.emit(".text")
        self.emit(".global main")
        self.emit("")

        for fn in self.prog.functions:
            is_main = fn.name == "main"
            self.emit(f"{fn.name}:")
            for st in fn.body:
                self.emit_stmt(fn.name, st, is_main)
            if not self.block_guarantees_return(fn.body):
                if is_main:
                    self.emit("    HALT")
                else:
                    self.emit("    JR    r7")
            self.emit("")

        self.emit(".data")
        for label, value in self.data_entries:
            self.emit(f"{label}: .word {value}")

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
