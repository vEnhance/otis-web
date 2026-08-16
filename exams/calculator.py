"""Evaluates the arithmetic expressions students submit as quiz answers.

A student whose answer is 4^500 may prefer to write 2^1000, so guesses are
scored by evaluating both sides.  The input is untrusted, hence a parser rather
than eval().  Precedence is the usual mathematical one, which is also Python's:
'^' binds tightest and groups to the right, with a leading minus outside it, so
-2^2 is -4 and 2^-2 is 0.25.

The accepted language is inherited from pyparsing's fourFn.py example, which
this module used to be built on.
"""

import math
import operator
import re
from collections.abc import Callable

Number = int | float


class CalculatorError(ValueError):
    """Raised when an expression is malformed and cannot be evaluated."""


# Results are consumed as floats, so a cap well past the float range costs
# nothing and stops 9^9^9 from asking for a 370-million-digit integer.
MAX_RESULT_LOG10 = 1000

# Parentheses and signs recurse, so stay well short of Python's recursion limit.
MAX_DEPTH = 100


def safe_pow(op1: Number, op2: Number) -> Number:
    """Exponentiation that refuses to evaluate absurdly large results."""
    # only int ** positive int can run away; anything involving a float either
    # returns at once or raises OverflowError
    grows_exactly = (
        isinstance(op1, int) and isinstance(op2, int) and abs(op1) > 1 and op2 > 0
    )
    # op2 * log10(|op1|) > MAX_RESULT_LOG10, rearranged so that an enormous op2
    # never has to become a float
    if grows_exactly and op2 > MAX_RESULT_LOG10 / math.log10(abs(op1)):
        raise OverflowError("exponentiation result is too large to evaluate")
    return operator.pow(op1, op2)


LEFT = "left"
RIGHT = "right"

BINARY_OPS: dict[str, tuple[int, str, Callable[[Number, Number], Number]]] = {
    "+": (1, LEFT, operator.add),
    "-": (1, LEFT, operator.sub),
    "*": (2, LEFT, operator.mul),
    "/": (2, LEFT, operator.truediv),
    "^": (4, RIGHT, safe_pow),
}

# looser than '^' so that -2^2 is -(2^2), tighter than '*' so that 3*-2 works
UNARY_PRECEDENCE = 3

CONSTANTS: dict[str, Number] = {"pi": math.pi, "e": math.e}
FUNCTIONS: dict[str, Callable[[Number], Number]] = {"sqrt": math.sqrt}

_TOKEN_RE = re.compile(
    r"""
      (?P<number> \d+ (?:\.\d*)? (?:[eE][+-]?\d+)? )
    | (?P<name>   [A-Za-z][A-Za-z0-9_]* )
    | (?P<op>     [-+*/^()] )
    | (?P<space>  \s+ )
    | (?P<bad>    . )
    """,
    re.VERBOSE | re.DOTALL,
)


def tokenize(s: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    for match in _TOKEN_RE.finditer(s):
        kind = match.lastgroup
        if kind == "bad":
            raise CalculatorError(f"unexpected character {match.group()!r}")
        if kind != "space":
            assert kind is not None
            tokens.append((kind, match.group()))
    return tokens


def to_number(text: str) -> Number:
    """Read a numeric literal, keeping whole numbers exact."""
    try:
        return int(text)
    except ValueError:
        return float(text)


class Parser:
    """A precedence-climbing parser that evaluates as it goes."""

    def __init__(self, tokens: list[tuple[str, str]]):
        self.tokens = tokens
        self.pos = 0
        self.depth = 0

    def parse(self) -> Number:
        value = self.parse_expr(0)
        if self.pos < len(self.tokens):
            raise CalculatorError(f"unexpected {self.tokens[self.pos][1]!r}")
        return value

    def peek(self) -> tuple[str, str] | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def accept(self, text: str) -> bool:
        token = self.peek()
        if token is not None and token[1] == text:
            self.pos += 1
            return True
        return False

    def expect(self, text: str):
        if not self.accept(text):
            found = self.peek()
            raise CalculatorError(
                f"expected {text!r} but found "
                + (repr(found[1]) if found is not None else "end of expression")
            )

    def parse_expr(self, min_precedence: int) -> Number:
        """Evaluate operators binding at least as tightly as min_precedence."""
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise CalculatorError("expression is nested too deeply")
        try:
            lhs = self.parse_unary()
            while (token := self.peek()) is not None:
                op = token[1]
                if token[0] != "op" or op not in BINARY_OPS:
                    break
                precedence, associativity, apply = BINARY_OPS[op]
                if precedence < min_precedence:
                    break
                self.pos += 1
                # recurring at its own precedence is what makes '^' right
                # associative, so that 2^3^2 is 2^(3^2)
                rhs = self.parse_expr(
                    precedence if associativity == RIGHT else precedence + 1
                )
                lhs = apply(lhs, rhs)
            return lhs
        finally:
            self.depth -= 1

    def parse_unary(self) -> Number:
        if self.accept("-"):
            return -self.parse_expr(UNARY_PRECEDENCE)
        if self.accept("+"):
            return self.parse_expr(UNARY_PRECEDENCE)
        return self.parse_atom()

    def parse_atom(self) -> Number:
        token = self.peek()
        if token is None:
            raise CalculatorError("expression ended unexpectedly")
        self.pos += 1
        kind, text = token

        if kind == "number":
            return to_number(text)
        if kind == "name":
            if text.lower() in CONSTANTS:
                return CONSTANTS[text.lower()]
            if text in FUNCTIONS:
                self.expect("(")
                argument = self.parse_expr(0)
                self.expect(")")
                return FUNCTIONS[text](argument)
            raise CalculatorError(f"invalid identifier {text}")
        if text == "(":
            value = self.parse_expr(0)
            self.expect(")")
            return value
        raise CalculatorError(f"unexpected {text!r}")


def expr_compute(s: str) -> float | None:
    """Evaluate an expression, or return None if there isn't one.

    Raises CalculatorError if malformed, OverflowError if impractically large.
    """
    if not s:
        return None
    return Parser(tokenize(s)).parse()
