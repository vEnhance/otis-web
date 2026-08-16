# fourFn.py
#
# Demonstration of the pyparsing module, implementing a simple 4-function expression parser,
# with support for scientific notation, and symbols for e and pi.
# Extended to add exponentiation and simple built-in functions.
# Extended test cases, simplified pushFirst method.
# Removed unnecessary expr.suppress() call (thanks Nathaniel Peterson!), and added Group
# Changed fnumber to use a Regex, which is now the preferred method
# Reformatted to latest pypyparsing features, support multiple and variable args to functions
#
# Copyright 2003-2019 by Paul McGuire
#

# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import math
import operator
from contextvars import ContextVar
from typing import Any, Optional, Union

from pyparsing import (
    CaselessKeyword,
    DelimitedList,
    Forward,
    Group,
    Literal,
    Regex,
    Suppress,
    Token,
    Word,
    alphanums,
    alphas,
)

# The parse actions below push tokens onto a stack as the grammar matches them,
# which evaluate_stack then consumes.  That stack belongs to a single call to
# expr_compute: were it shared, two quiz submissions being scored at the same
# time would interleave their tokens and silently mis-score each other.  A
# ContextVar hands every thread (and every async task) its own.
_expr_stack: ContextVar[list[Any]] = ContextVar("_expr_stack")


def push_first(toks: list[Token]):
    _expr_stack.get().append(toks[0])


def push_unary_minus(toks: list[Token]):
    stack = _expr_stack.get()
    for t in toks:
        if t == "-":
            stack.append("unary -")
        else:
            break


def make_bnf() -> Any:
    """
    expop   :: '^'
    multop  :: '*' | '/'
    addop   :: '+' | '-'
    integer :: ['+' | '-'] '0'..'9'+
    atom    :: PI | E | real | fn '(' expr ')' | '(' expr ')'
    factor  :: atom [ expop factor ]*
    term    :: factor [ multop factor ]*
    expr    :: term [ addop term ]*
    """
    # use CaselessKeyword for e and pi, to avoid accidentally matching
    # functions that start with 'e' or 'pi' (such as 'exp'); Keyword
    # and CaselessKeyword only match whole words
    e = CaselessKeyword("E")
    pi = CaselessKeyword("PI")
    fnumber = Regex(r"[+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?")
    ident = Word(alphas, f"{alphanums}_$")

    plus, minus, mult, div = map(Literal, "+-*/")
    lpar, rpar = map(Suppress, "()")
    addop = plus | minus
    multop = mult | div
    expop = Literal("^")

    expr = Forward()
    expr_list = DelimitedList(Group(expr))

    # add parse action that replaces the function identifier with a (name, number of args) tuple
    def insert_fn_argcount_tuple(t: list[Any]):
        fn = t.pop(0)
        num_args = len(t[0])
        t.insert(0, (fn, num_args))

    f = ident + lpar - Group(expr_list) + rpar  # type: ignore
    fn_call = f.set_parse_action(insert_fn_argcount_tuple)  # type: ignore
    g = fn_call | pi | e | fnumber | ident  # type: ignore
    assert g is not None
    atom = addop[...] + (
        g.set_parse_action(push_first) | Group(lpar + expr + rpar)  # type: ignore
    )
    atom = atom.set_parse_action(push_unary_minus)  # type: ignore

    # by defining exponentiation as "atom [ ^ factor ]..." instead of "atom [ ^ atom ]...", we get right-to-left
    # exponents, instead of left-to-right that is, 2^3^2 = 2^(3^2), not (2^3)^2.
    factor = Forward()
    factor <<= atom + (expop + factor).set_parse_action(push_first)[...]  # type: ignore
    term = factor + (multop + factor).set_parse_action(push_first)[...]  # type: ignore
    expr <<= term + (addop + term).set_parse_action(push_first)[...]  # type: ignore
    return expr


# Built (and streamlined) once, at import: the grammar is only read from during
# a parse, so one instance is safe to share, but building it lazily on first use
# would race -- and so would leaving parse_string to streamline it, since that
# rewrites the grammar in place the first time it runs.
BNF = make_bnf()
BNF.streamline()


# Largest magnitude, as a power of ten, that exponentiation is allowed to
# produce.  Results are ultimately consumed as floats (whose range stops around
# 1e308), so this is generous; the point is only to keep an input like 9^9^9
# from asking Python for a 370-million-digit integer, which takes hours and
# gigabytes of memory.  Anything under the cap is computed instantly.
MAX_RESULT_LOG10 = 1000


def safe_pow(op1: Union[int, float], op2: Union[int, float]) -> Union[int, float]:
    """Exponentiation that refuses to evaluate absurdly large results.

    Only int ** nonnegative int can run away: every other combination of
    operands either returns immediately or raises OverflowError, because
    Python falls back to floating point.
    """
    if isinstance(op1, int) and isinstance(op2, int) and abs(op1) > 1 and op2 > 0:
        # equivalent to op2 * log10(|op1|) > MAX_RESULT_LOG10, but written so
        # that an enormous op2 doesn't have to be converted to a float
        if op2 > MAX_RESULT_LOG10 / math.log10(abs(op1)):
            raise OverflowError("exponentiation result is too large to evaluate")
    return operator.pow(op1, op2)


# map operator symbols to corresponding arithmetic operations
epsilon = 1e-12
opn = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
    "^": safe_pow,
}

fn = {
    "sqrt": math.sqrt,
}


def evaluate_stack(s: list[Any]) -> Union[int, float]:
    op, num_args = s.pop(), 0
    if isinstance(op, tuple):
        op, num_args = op
    if op == "unary -":
        return -evaluate_stack(s)
    if op in "+-*/^":
        # note: operands are pushed onto the stack in reverse order
        op2 = evaluate_stack(s)
        op1 = evaluate_stack(s)
        return opn[op](op1, op2)
    elif op == "PI":
        return math.pi  # 3.1415926535
    elif op == "E":
        return math.e  # 2.718281828
    elif op in fn:
        # note: args are pushed onto the stack in reverse order
        args = reversed([evaluate_stack(s) for _ in range(num_args)])
        return fn[op](*args)
    elif op[0].isalpha():
        raise Exception(f"invalid identifier {op}")
    else:
        # try to evaluate as int first, then as float if int fails
        try:
            return int(op)
        except ValueError:
            return float(op)


def expr_compute(s: str) -> Optional[float]:
    if not s:
        return None
    stack: list[Any] = []
    reset_token = _expr_stack.set(stack)
    try:
        BNF.parse_string(s, parse_all=True)
        return evaluate_stack(stack)
    finally:
        _expr_stack.reset(reset_token)


# Warm the grammar up while we are still single-threaded.  pyparsing works out
# each parse action's arity by calling it and catching TypeError, and that probe
# writes to state shared by every later call, so two threads reaching an
# un-probed action at once can trim the wrong number of arguments.  This
# expression exercises all six of the parse actions attached in make_bnf().
assert expr_compute("-sqrt(4)^2*3-1/2") == 11.5

# flake8: noqa
