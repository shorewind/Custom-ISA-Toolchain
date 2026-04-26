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
  - &variable (address-of, for pointer arguments)
  - *variable (pointer dereference, for pointer parameters)
- Control flow:
  - if / else
  - while
  - for
  - Relational operators in conditions: ==, !=, >, <=, <, >=
- Functions:
  - return expression;
  - parameters by value or by pointer (C: int *x)
  - by-pointer: caller passes &var, callee uses *x to read/write through the pointer

Important codegen note:
- This ISA/toolchain has no hardware stack pointer in the exposed subset, so
  argument slots and temporaries are statically allocated in .data per function.
  Recursion/reentrant calls are therefore not supported.
"""

from __future__ import annotations

import re
import sys
import operator
from dataclasses import dataclass
from typing import Dict, List, Optional, Union


# -----------------------------------------------------------------------------
# 1) LEXER
# -----------------------------------------------------------------------------
TOKEN_RE = re.compile(
    r"\s*(<=|>=|==|!=|[A-Za-z_]\w*|\d+|[{}()\[\];,+\-=&|<>*])"
)  # two-char operators listed first so alternation matches them before single-char prefixes


def lex(src: str) -> List[str]:
    src = re.sub(r"//.*", "", src)  # strip // line comments before tokenizing
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
# 2) AST
# -----------------------------------------------------------------------------
@dataclass
class VarDecl:
    name: str
    size: int = 1
    init: Optional["Expr"] = None


@dataclass
class Param:
    name: str
    by_ptr: bool = False   # C int *x: caller passes &var, callee uses *x explicitly


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
    target_deref: bool = False  # True for *x = expr (write through pointer)


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
# 3) PARSER
# -----------------------------------------------------------------------------
REL_OPS = {"==", "!=", ">", "<=", "<", ">="}
BINARY_OPS = {"add", "sub", "and", "or"}
BINARY_FNS = {
    "add": operator.add,
    "sub": operator.sub,
    "and": operator.and_,
    "or": operator.or_,
}
BINOP_TO_ASM = {"add": "ADD", "sub": "SUB", "and": "AND", "or": "OR"}
RELOP_FALSE_BRANCH = {
    "==": ("SUB   r3, r1, r2", "BNZ"),
    "!=": ("SUB   r3, r1, r2", "BEZ"),
    "<": ("SLT   r3, r1, r2", "BEZ"),
    ">": ("SLT   r3, r2, r1", "BEZ"),
    "<=": ("SLT   r3, r2, r1", "BNZ"),
    ">=": ("SLT   r3, r1, r2", "BNZ"),
}


def eval_binary(op: str, left: int, right: int) -> int:
    fn = BINARY_FNS.get(op)
    if fn is None:
        raise ValueError(f"Unsupported binary operator: {op}")
    return fn(left, right)


def const_eval_expr(expr: Optional["Expr"]) -> Optional[int]:
    if expr is None:
        return None
    if expr.kind == "num":
        return expr.value
    if expr.kind in BINARY_OPS:
        left = const_eval_expr(expr.left)
        right = const_eval_expr(expr.right)
        if left is None or right is None:
            return None
        return eval_binary(expr.kind, left, right)
    return None


def label_with_offset(label: str, offset: int) -> str:
    if offset == 0:
        return label
    if offset > 0:
        return f"{label}+{offset}"
    return f"{label}{offset}"


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
            by_ptr = False

            self.take("int")
            if self.peek() == "*":
                self.take("*")
                by_ptr = True
            name = self.take_ident()

            params.append(Param(name=name, by_ptr=by_ptr))

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

    def parse_deref_assign_stmt(self, require_semi: bool) -> Stmt:
        self.take("*")
        name = self.take_ident()
        self.take("=")
        expr = self.parse_expr()
        if require_semi:
            self.take(";")
        return Stmt(kind="assign", assign=Assign(target_name=name, target_index=None, expr=expr, target_deref=True))

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
        return Cond(left=left, op="!=", right=Expr(kind="num", value=0))  # bare expression: implicitly test expr != 0

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

        if tok == "*":
            return self.parse_deref_assign_stmt(require_semi=True)

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
        if self.peek() == "*":
            # pointer dereference: *x reads through the pointer stored in x
            self.take("*")
            name = self.take_ident()
            return Expr(kind="deref", name=name)
        if self.peek() == "&":
            # address-of: &x yields the address of x (used to pass pointer arguments)
            # Note: binary & is consumed by parse_and before reaching here.
            self.take("&")
            name = self.take_ident()
            return Expr(kind="addr_of", name=name)
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
# 4) IR LOWERING
# -----------------------------------------------------------------------------
# IR values are intentionally tiny: either an integer constant or the name of a
# scalar slot. Arrays and calls become explicit IR instructions so codegen never
# has to recursively evaluate a complex AST while holding live registers.
IRValue = Union[int, str]  # int = compile-time constant; str = named .data slot


@dataclass
class IRInstr:
    op: str
    dst: Optional[str] = None
    src: Optional[IRValue] = None
    left: Optional[IRValue] = None
    right: Optional[IRValue] = None
    binop: Optional[str] = None
    name: Optional[str] = None
    index: Optional[IRValue] = None
    label: Optional[str] = None
    args: Optional[List[IRValue]] = None
    cond_op: Optional[str] = None


@dataclass
class IRFunction:
    name: str
    instrs: List[IRInstr]
    temps: List[str]


@dataclass
class IRProgram:
    functions: List[IRFunction]


class IRGen:
    """Lower AST into simple three-address code before target assembly."""

    def __init__(self, prog: Program) -> None:
        self.prog = prog
        self.func_by_name: Dict[str, Function] = {fn.name: fn for fn in prog.functions}
        self.ir_functions: List[IRFunction] = []
        self.instrs: List[IRInstr] = []
        self.temps: List[str] = []
        self.temp_counter = 0
        self.label_counters: Dict[str, int] = {"if": 0, "while": 0, "for": 0}
        self.current_fn = ""

    def new_temp(self) -> str:
        name = f"t{self.temp_counter}"
        self.temp_counter += 1
        self.temps.append(name)
        return name

    def new_struct_id(self, kind: str) -> int:
        self.label_counters[kind] += 1
        return self.label_counters[kind]

    def label_name(self, kind: str, suffix: str, sid: int) -> str:
        return f"{kind}_{suffix}_{sid}"

    def emit(self, instr: IRInstr) -> None:
        self.instrs.append(instr)

    def emit_expr(self, expr: Expr) -> IRValue:
        # General expression lowering returns a reusable value. Complex
        # expressions materialize into temporaries so later operations can reload
        # them without depending on r1/r2/r3 surviving recursive codegen.
        if expr.kind == "num":
            return expr.value or 0

        if expr.kind == "var":
            return expr.name or ""

        if expr.kind == "array":
            index = self.emit_expr(expr.index)
            dst = self.new_temp()
            self.emit(IRInstr(op="load_array", dst=dst, name=expr.name, index=index))
            return dst

        if expr.kind == "call":
            return self.emit_call(expr)

        if expr.kind == "deref":
            dst = self.new_temp()
            self.emit(IRInstr(op="deref_load", dst=dst, name=expr.name))
            return dst

        if expr.kind == "addr_of":
            dst = self.new_temp()
            self.emit(IRInstr(op="addr", dst=dst, name=expr.name))
            return dst

        if expr.kind in BINARY_OPS:
            left = self.emit_expr(expr.left)
            right = self.emit_expr(expr.right)
            if isinstance(left, int) and isinstance(right, int):
                return eval_binary(expr.kind, left, right)
            dst = self.new_temp()
            self.emit(IRInstr(op="bin", dst=dst, binop=expr.kind, left=left, right=right))
            return dst

        raise ValueError(f"Unsupported expression kind: {expr.kind}")

    def emit_call(self, call_expr: Expr) -> IRValue:
        callee = call_expr.name or ""
        callee_fn = self.func_by_name.get(callee)
        if callee_fn is None:
            raise NameError(f"Unknown function: {callee}")

        args = call_expr.args or []
        if len(args) != len(callee_fn.params):
            raise SyntaxError(
                f"Function '{callee}' expects {len(callee_fn.params)} arg(s), got {len(args)}"
            )

        lowered_args: List[IRValue] = []
        for _, a in zip(callee_fn.params, args):
            lowered_args.append(self.emit_expr(a))

        dst = self.new_temp()
        self.emit(IRInstr(op="call", dst=dst, name=callee, args=lowered_args))
        return dst

    def emit_expr_to(self, expr: Expr, dst: str) -> None:
        """Lower an expression directly into a known scalar destination when safe."""
        # This avoids pointless temps for simple code like "c = a + b" while
        # still using emit_expr for nested subtrees that must be preserved.
        if expr.kind == "num":
            self.emit(IRInstr(op="store", name=dst, src=expr.value or 0))
            return

        if expr.kind == "var":
            self.emit(IRInstr(op="store", name=dst, src=expr.name))
            return

        if expr.kind == "array":
            index = self.emit_expr(expr.index)
            self.emit(IRInstr(op="load_array", dst=dst, name=expr.name, index=index))
            return

        if expr.kind == "call":
            value = self.emit_call(expr)
            if isinstance(value, int):
                self.emit(IRInstr(op="store", name=dst, src=value))
            elif value != dst:
                self.emit(IRInstr(op="store", name=dst, src=value))
            return

        if expr.kind in BINARY_OPS:
            left = self.emit_expr(expr.left)
            right = self.emit_expr(expr.right)
            if isinstance(left, int) and isinstance(right, int):
                self.emit(IRInstr(op="store", name=dst, src=eval_binary(expr.kind, left, right)))
                return
            self.emit(IRInstr(op="bin", dst=dst, binop=expr.kind, left=left, right=right))
            return

        if expr.kind in ("deref", "addr_of"):
            value = self.emit_expr(expr)
            if isinstance(value, int) or value != dst:
                self.emit(IRInstr(op="store", name=dst, src=value))
            return

        raise ValueError(f"Unsupported expression kind: {expr.kind}")

    def emit_condition_false_branch(self, cond: Cond, false_label: str) -> None:
        left = self.emit_expr(cond.left)
        right = self.emit_expr(cond.right or Expr(kind="num", value=0))
        self.emit(IRInstr(op="jump_false", left=left, right=right, cond_op=cond.op, label=false_label))

    def emit_stmt(self, st: Stmt) -> None:
        if st.kind == "decl":
            if st.decl is not None and st.decl.init is not None:
                if self.current_fn == "main" and const_eval_expr(st.decl.init) is not None:
                    return
                self.emit_expr_to(st.decl.init, st.decl.name)
            return

        if st.kind == "assign":
            if st.assign is None:
                return
            if st.assign.target_deref:
                # *x = expr: write through the pointer stored in x
                value = self.emit_expr(st.assign.expr)
                self.emit(IRInstr(op="deref_store", name=st.assign.target_name, src=value))
            elif st.assign.target_index is None:
                self.emit_expr_to(st.assign.expr, st.assign.target_name)
            else:
                # For stores through computed addresses, preserve the RHS first;
                # address calculation is allowed to use the normal scratch regs.
                value = self.emit_expr(st.assign.expr)
                index = self.emit_expr(st.assign.target_index)
                self.emit(IRInstr(op="store_array", name=st.assign.target_name, index=index, src=value))
            return

        if st.kind == "expr":
            if st.expr is not None:
                self.emit_expr(st.expr)
            return

        if st.kind == "block":
            for inner in st.body or []:
                self.emit_stmt(inner)
            return

        if st.kind == "if":
            sid = self.new_struct_id("if")
            else_label = self.label_name("if", "else", sid)
            end_label = self.label_name("if", "end", sid)
            if st.cond is None:
                raise ValueError("if missing condition")
            self.emit_condition_false_branch(st.cond, else_label)
            for inner in st.then_body or []:
                self.emit_stmt(inner)
            self.emit(IRInstr(op="jump", label=end_label))
            self.emit(IRInstr(op="label", label=else_label))
            for inner in st.else_body or []:
                self.emit_stmt(inner)
            self.emit(IRInstr(op="label", label=end_label))
            return

        if st.kind == "while":
            sid = self.new_struct_id("while")
            start_label = self.label_name("while", "start", sid)
            end_label = self.label_name("while", "end", sid)
            self.emit(IRInstr(op="label", label=start_label))
            if st.cond is None:
                raise ValueError("while missing condition")
            self.emit_condition_false_branch(st.cond, end_label)
            for inner in st.body or []:
                self.emit_stmt(inner)
            self.emit(IRInstr(op="jump", label=start_label))
            self.emit(IRInstr(op="label", label=end_label))
            return

        if st.kind == "for":
            if st.init is not None:
                self.emit_stmt(st.init)

            sid = self.new_struct_id("for")
            start_label = self.label_name("for", "start", sid)
            end_label = self.label_name("for", "end", sid)
            self.emit(IRInstr(op="label", label=start_label))
            if st.cond is not None:
                self.emit_condition_false_branch(st.cond, end_label)

            for inner in st.body or []:
                self.emit_stmt(inner)

            if st.update is not None:
                self.emit_stmt(st.update)

            self.emit(IRInstr(op="jump", label=start_label))
            self.emit(IRInstr(op="label", label=end_label))
            return

        if st.kind == "return":
            if st.expr is None:
                raise ValueError("return requires expression")
            value = self.emit_expr(st.expr)
            self.emit(IRInstr(op="return", src=value))
            return

        raise ValueError(f"Unsupported statement kind: {st.kind}")

    def stmt_guarantees_return(self, st: Stmt) -> bool:
        # used to decide whether an implicit "return 0" is needed at function end
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

    def generate(self) -> IRProgram:
        for fn in self.prog.functions:
            self.current_fn = fn.name
            self.instrs = []
            self.temps = []
            self.temp_counter = 0

            for st in fn.body:
                self.emit_stmt(st)

            if not self.block_guarantees_return(fn.body):
                self.emit(IRInstr(op="return", src=0))

            self.ir_functions.append(IRFunction(name=fn.name, instrs=self.instrs, temps=self.temps))

        return IRProgram(functions=self.ir_functions)


# -----------------------------------------------------------------------------
# 5) CODE GENERATOR
# -----------------------------------------------------------------------------
@dataclass
class SymbolInfo:
    kind: str  # scalar, array, param_val, param_ptr
    label: str
    size: int = 1


class CodeGen:
    def __init__(self, prog: Program) -> None:
        self.prog = prog
        self.ir_by_name: Dict[str, IRFunction] = {}
        self.lines: List[str] = []

        self.global_symbols: Dict[str, SymbolInfo] = {}
        self.func_symbols: Dict[str, Dict[str, SymbolInfo]] = {}
        self.func_by_name: Dict[str, Function] = {}

        # Data layout entries in emission order.
        self.data_entries: List[tuple[str, int | str]] = []
        self.data_seen: set[str] = set()
        self.data_index: Dict[str, int] = {}

        # Label-address helpers for pointer math.
        self.addr_helpers: Dict[str, str] = {}
        self.fn_needs_saved_r7: Dict[str, bool] = {}

    def emit(self, s: str = "") -> None:
        self.lines.append(s)

    def add_data_word(self, label: str, value: int | str = 0) -> None:
        if label in self.data_seen:
            return  # deduplication: addr_helpers may re-request an already-allocated label
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
        # The ISA has no PC-relative data addressing; to load a label's address
        # into a register, emit a .word holding the address and load that pointer word.
        if target_label not in self.addr_helpers:
            helper = f"addr_{target_label}"
            self.addr_helpers[target_label] = helper
            self.add_data_word(helper, target_label)  # .word pointing at target_label itself
        return self.addr_helpers[target_label]

    def require_fields(self, instr: IRInstr, *fields: str) -> List[object]:
        values: List[object] = []
        for field in fields:
            value = getattr(instr, field)
            if value is None:
                raise ValueError(f"Malformed {instr.op} instruction")
            values.append(value)
        return values

    def collect_decl(self, fn_name: str, local_map: Dict[str, SymbolInfo], d: VarDecl) -> None:
        if d.name in local_map:
            raise NameError(f"Duplicate local in {fn_name}: {d.name}")
        lbl = f"{fn_name}_{d.name}"
        if d.size == 1:
            local_map[d.name] = SymbolInfo(kind="scalar", label=lbl, size=1)
            self.add_data_word(lbl, 0)
            if fn_name == "main":
                k = const_eval_expr(d.init)
                if k is not None:
                    self.set_data_word(lbl, k)
        else:
            local_map[d.name] = SymbolInfo(kind="array", label=lbl, size=d.size)
            self.add_data_words(lbl, d.size, 0)

    def collect_stmt_decls(self, fn_name: str, local_map: Dict[str, SymbolInfo], stmts: List[Stmt]) -> None:
        for st in stmts:
            if st.kind == "decl" and st.decl is not None:
                self.collect_decl(fn_name, local_map, st.decl)
            elif st.kind == "if":
                self.collect_stmt_decls(fn_name, local_map, st.then_body or [])
                self.collect_stmt_decls(fn_name, local_map, st.else_body or [])
            elif st.kind == "while":
                self.collect_stmt_decls(fn_name, local_map, st.body or [])
            elif st.kind == "for":
                if st.init is not None:
                    self.collect_stmt_decls(fn_name, local_map, [st.init])
                self.collect_stmt_decls(fn_name, local_map, st.body or [])
            elif st.kind == "block":
                self.collect_stmt_decls(fn_name, local_map, st.body or [])

    def collect_symbols(self, ir_prog: IRProgram) -> None:
        self.ir_by_name = {fn.name: fn for fn in ir_prog.functions}

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
            self.func_by_name[fn.name] = fn
            local_map: Dict[str, SymbolInfo] = {}
            self.func_symbols[fn.name] = local_map

            ir_fn = self.ir_by_name.get(fn.name)
            # main exits via HALT so never needs r7 saved; other callers must save r7
            # because JL overwrites it with the return address of the outgoing call.
            self.fn_needs_saved_r7[fn.name] = fn.name != "main" and ir_fn is not None and any(
                instr.op == "call" for instr in ir_fn.instrs
            )

            for p in fn.params:
                if p.name in local_map:
                    raise NameError(f"Duplicate parameter in {fn.name}: {p.name}")
                if p.by_ptr:
                    slot = f"{fn.name}_p_ptr_{p.name}"
                    local_map[p.name] = SymbolInfo(kind="param_ptr", label=slot, size=1)
                    self.add_data_word(slot, 0)
                else:
                    slot = f"{fn.name}_p_val_{p.name}"
                    local_map[p.name] = SymbolInfo(kind="param_val", label=slot, size=1)
                    self.add_data_word(slot, 0)

            self.collect_stmt_decls(fn.name, local_map, fn.body)

            if ir_fn is not None:
                # Temps are explicit storage slots for now. This keeps the
                # backend simple on an ISA without an exposed stack pointer;
                # later register allocation can replace selected temp loads.
                for temp in ir_fn.temps:
                    if temp in local_map:
                        raise NameError(f"Duplicate temporary in {fn.name}: {temp}")
                    local_map[temp] = SymbolInfo(kind="scalar", label=f"{fn.name}_{temp}", size=1)
                    self.add_data_word(f"{fn.name}_{temp}", 0)

            if self.fn_needs_saved_r7[fn.name]:
                self.add_data_word(self.fn_saved_r7_label(fn.name), 0)

    def fn_saved_r7_label(self, fn: str) -> str:
        return f"{fn}_saved_r7"

    def lookup_symbol(self, fn: str, name: str) -> SymbolInfo:
        if name in self.func_symbols.get(fn, {}):
            return self.func_symbols[fn][name]
        if name in self.global_symbols:
            return self.global_symbols[name]
        raise NameError(f"Unknown variable: {name}")

    def emit_load_scalar(self, fn: str, name: str, target: str) -> None:
        info = self.lookup_symbol(fn, name)
        if info.kind in ("scalar", "param_val", "param_ptr"):
            self.emit(f"    LD    {target}, {info.label}(r0)")
            return
        raise ValueError(f"Cannot read array variable '{name}' without index")

    def emit_store_scalar(self, fn: str, name: str, src: str) -> None:
        info = self.lookup_symbol(fn, name)
        if info.kind in ("scalar", "param_val", "param_ptr"):
            self.emit(f"    ST    {src}, {info.label}(r0)")
            return
        raise ValueError(f"Cannot assign array variable '{name}' without index")

    def emit_load_operand(self, fn: str, value: IRValue, target: str) -> None:
        if isinstance(value, int):
            self.emit(f"    LDI   {target}, {value}")
            return
        self.emit_load_scalar(fn, value, target)

    def emit_store_operand(self, fn: str, name: str, value: IRValue) -> None:
        self.emit_load_operand(fn, value, "r3")
        self.emit_store_scalar(fn, name, "r3")

    def emit_load_address_of_scalar(self, fn: str, name: str, target: str) -> None:
        info = self.lookup_symbol(fn, name)
        if info.kind in ("scalar", "param_val", "param_ptr"):
            helper = self.addr_helper_label(info.label)
            self.emit(f"    LD    {target}, {helper}(r0)")
            return
        raise ValueError(f"Cannot take scalar address of array '{name}'")

    def emit_array_index_address_value(self, fn: str, name: str, index: IRValue, target: str) -> None:
        info = self.lookup_symbol(fn, name)
        if info.kind != "array":
            raise ValueError(f"'{name}' is not an array")

        helper = self.addr_helper_label(info.label)
        self.emit(f"    LD    r5, {helper}(r0)")       # load base address of array
        self.emit_load_operand(fn, index, "r2")        # load index
        self.emit(f"    ADD   {target}, r5, r2")       # base + index = element address

    def emit_load_array_elem_value(self, fn: str, name: str, index: IRValue, target: str) -> None:
        info = self.lookup_symbol(fn, name)
        if info.kind != "array":
            raise ValueError(f"'{name}' is not an array")

        if isinstance(index, int):
            self.emit(f"    LD    {target}, {label_with_offset(info.label, index)}(r0)")
            return

        self.emit_array_index_address_value(fn, name, index, "r4")
        self.emit(f"    LD    {target}, 0(r4)")

    def emit_store_array_elem_value(self, fn: str, name: str, index: IRValue, value: IRValue) -> None:
        info = self.lookup_symbol(fn, name)
        if info.kind != "array":
            raise ValueError(f"'{name}' is not an array")

        if isinstance(index, int):
            self.emit_load_operand(fn, value, "r3")
            self.emit(f"    ST    r3, {label_with_offset(info.label, index)}(r0)")
            return

        self.emit_array_index_address_value(fn, name, index, "r4")
        self.emit_load_operand(fn, value, "r3")
        self.emit("    ST    r3, 0(r4)")

    def emit_relop_false_jump(self, op: str, false_label: str) -> None:
        op_info = RELOP_FALSE_BRANCH.get(op)
        if op_info is None:
            raise ValueError(f"Unsupported relational operator: {op}")
        compare_instr, branch_instr = op_info
        self.emit(f"    {compare_instr}")
        self.emit(f"    {branch_instr}   r3, {false_label}")

    def emit_call(self, fn: str, instr: IRInstr) -> None:
        callee = instr.name or ""
        callee_fn = self.func_by_name.get(callee)
        if callee_fn is None:
            raise NameError(f"Unknown function: {callee}")

        args = instr.args or []
        if len(args) != len(callee_fn.params):
            raise SyntaxError(
                f"Function '{callee}' expects {len(callee_fn.params)} arg(s), got {len(args)}"
            )

        for p, a in zip(callee_fn.params, args):
            self.emit_load_operand(fn, a, "r3")
            slot = self.lookup_symbol(callee, p.name).label
            self.emit(f"    ST    r3, {slot}(r0)")

        # Preserve r7 around the call: JL will overwrite it with the new return address.
        if self.fn_needs_saved_r7.get(fn, False):
            saved_lbl = self.fn_saved_r7_label(fn)
            self.emit(f"    ST    r7, {saved_lbl}(r0)")
        self.emit(f"    JL    r7, {callee}")
        if self.fn_needs_saved_r7.get(fn, False):
            self.emit(f"    LD    r7, {saved_lbl}(r0)")

        if instr.dst is not None:
            self.emit_store_scalar(fn, instr.dst, "r1")

    def emit_ir_instr(self, fn: str, instr: IRInstr, is_main: bool) -> None:
        if instr.op == "const":
            dst, src = self.require_fields(instr, "dst", "src")
            self.emit_store_operand(fn, dst, src)
            return

        if instr.op == "store":
            name, src = self.require_fields(instr, "name", "src")
            self.emit_store_operand(fn, name, src)
            return

        if instr.op == "bin":
            dst, binop, left, right = self.require_fields(instr, "dst", "binop", "left", "right")
            self.emit_load_operand(fn, left, "r1")
            self.emit_load_operand(fn, right, "r2")
            asm_op = BINOP_TO_ASM.get(binop)
            if asm_op is None:
                raise ValueError(f"Unsupported binary operator: {binop}")
            self.emit(f"    {asm_op:<5} r3, r1, r2")
            self.emit_store_scalar(fn, dst, "r3")
            return

        if instr.op == "load_array":
            dst, name, index = self.require_fields(instr, "dst", "name", "index")
            self.emit_load_array_elem_value(fn, name, index, "r3")
            self.emit_store_scalar(fn, dst, "r3")
            return

        if instr.op == "store_array":
            name, index, src = self.require_fields(instr, "name", "index", "src")
            self.emit_store_array_elem_value(fn, name, index, src)
            return

        if instr.op == "deref_load":
            dst, name = self.require_fields(instr, "dst", "name")
            info = self.lookup_symbol(fn, name)
            self.emit(f"    LD    r5, {info.label}(r0)")  # load pointer from slot
            self.emit(f"    LD    r3, 0(r5)")             # dereference
            self.emit_store_scalar(fn, dst, "r3")
            return

        if instr.op == "deref_store":
            name, src = self.require_fields(instr, "name", "src")
            info = self.lookup_symbol(fn, name)
            self.emit_load_operand(fn, src, "r3")          # load value to write
            self.emit(f"    LD    r5, {info.label}(r0)")   # load pointer from slot
            self.emit(f"    ST    r3, 0(r5)")              # write through pointer
            return

        if instr.op == "addr":
            dst, name = self.require_fields(instr, "dst", "name")
            if instr.index is None:
                self.emit_load_address_of_scalar(fn, name, "r3")
            else:
                self.emit_array_index_address_value(fn, name, instr.index, "r3")
            self.emit_store_scalar(fn, dst, "r3")
            return

        if instr.op == "call":
            self.emit_call(fn, instr)
            return

        if instr.op == "jump_false":
            left, right, cond_op, label = self.require_fields(instr, "left", "right", "cond_op", "label")
            self.emit_load_operand(fn, left, "r1")
            self.emit_load_operand(fn, right, "r2")
            self.emit_relop_false_jump(cond_op, label)
            return

        if instr.op == "jump":
            label = self.require_fields(instr, "label")[0]
            self.emit(f"    BEZ   r0, {label}")
            return

        if instr.op == "label":
            label = self.require_fields(instr, "label")[0]
            self.emit(f"{label}:")
            return

        if instr.op == "return":
            self.emit_load_operand(fn, instr.src if instr.src is not None else 0, "r1")
            if is_main:
                self.emit("    HALT")
            else:
                self.emit("    JR    r7")
            return

        raise ValueError(f"Unsupported IR instruction: {instr.op}")

    def generate(self) -> str:
        ir_prog = IRGen(self.prog).generate()
        self.collect_symbols(ir_prog)

        self.emit(".text")
        self.emit(".global main")  # entry point for the assembler
        self.emit("")

        for fn in self.prog.functions:
            is_main = fn.name == "main"
            ir_fn = self.ir_by_name[fn.name]
            self.emit(f"{fn.name}:")
            for instr in ir_fn.instrs:
                self.emit_ir_instr(fn.name, instr, is_main)
            self.emit("")

        self.emit(".data")
        for label, value in self.data_entries:
            self.emit(f"{label}: .word {value}")  # emit data entries in allocation order

        return "\n".join(self.lines).rstrip() + "\n"

def main() -> None:
    if len(sys.argv) == 1:
        in_path = "tests/basic/c-example.c"
        out_path = "tests/basic/assembly-example.s"
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
