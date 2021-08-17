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
from typing import Any, List, Optional, Union

from pyparsing import CaselessKeyword, Forward, Group, Literal, Regex, Suppress, Token, Word, alphanums, alphas, delimitedList  # NOQA

exprStack = []


def push_first(toks: List[Token]):
	exprStack.append(toks[0])


def push_unary_minus(toks: List[Token]):
	for t in toks:
		if t == "-":
			exprStack.append("unary -")
		else:
			break


bnf = None


def BNF() -> Any:
	"""
	expop   :: '^'
	multop  :: '*' | '/'
	addop   :: '+' | '-'
	integer :: ['+' | '-'] '0'..'9'+
	atom	:: PI | E | real | fn '(' expr ')' | '(' expr ')'
	factor  :: atom [ expop factor ]*
	term	:: factor [ multop factor ]*
	expr	:: term [ addop term ]*
	"""
	global bnf
	if not bnf:
		# use CaselessKeyword for e and pi, to avoid accidentally matching
		# functions that start with 'e' or 'pi' (such as 'exp'); Keyword
		# and CaselessKeyword only match whole words
		e = CaselessKeyword("E")
		pi = CaselessKeyword("PI")
		# fnumber = Combine(Word("+-"+nums, nums) +
		#					Optional("." + Optional(Word(nums))) +
		#					Optional(e + Word("+-"+nums, nums)))
		# or use provided pyparsing_common.number, but convert back to str:
		# fnumber = ppc.number().addParseAction(lambda t: str(t[0]))
		fnumber = Regex(r"[+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?")
		ident = Word(alphas, alphanums + "_$")

		plus, minus, mult, div = map(Literal, "+-*/")
		lpar, rpar = map(Suppress, "()")
		addop = plus | minus
		multop = mult | div
		expop = Literal("^")

		expr = Forward()
		expr_list = delimitedList(Group(expr))

		# add parse action that replaces the function identifier with a (name, number of args) tuple
		def insert_fn_argcount_tuple(t: List[Any]):
			fn = t.pop(0)
			num_args = len(t[0])
			t.insert(0, (fn, num_args))

		f = ident + lpar - Group(expr_list) + rpar  # type: ignore
		fn_call = f.setParseAction(insert_fn_argcount_tuple)  # type: ignore
		g = fn_call | pi | e | fnumber | ident  # type: ignore
		assert g is not None
		atom = (
			addop[...]  # type: ignore
			+ (
				g.setParseAction(push_first) | Group(lpar + expr + rpar)  # type: ignore
			)
		).setParseAction(push_unary_minus)  # type: ignore

		# by defining exponentiation as "atom [ ^ factor ]..." instead of "atom [ ^ atom ]...", we get right-to-left
		# exponents, instead of left-to-right that is, 2^3^2 = 2^(3^2), not (2^3)^2.
		factor = Forward()
		factor <<= atom + (expop + factor).setParseAction(push_first)[...]  # type: ignore
		term = factor + (
			multop +  # type: ignore
			factor
		).setParseAction(push_first)[...]  # type: ignore
		expr <<= term + (
			addop +  # type: ignore
			term
		).setParseAction(push_first)[...]  # type: ignore
		bnf = expr
	return bnf


# map operator symbols to corresponding arithmetic operations
epsilon = 1e-12
opn = {
	"+": operator.add,
	"-": operator.sub,
	"*": operator.mul,
	"/": operator.truediv,
	"^": operator.pow,
}

fn = {
	"sin": math.sin,
	"cos": math.cos,
	"tan": math.tan,
	"sqrt": math.sqrt,
}


def evaluate_stack(s: List[Any]) -> Union[int, float]:
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
		raise Exception("invalid identifier '%s'" % op)
	else:
		# try to evaluate as int first, then as float if int fails
		try:
			return int(op)
		except ValueError:
			return float(op)


def expr_compute(s: str) -> Optional[float]:
	if s == '':
		return None
	exprStack[:] = []
	BNF().parseString(s, parseAll=True)
	val = evaluate_stack(exprStack[:])
	return val
