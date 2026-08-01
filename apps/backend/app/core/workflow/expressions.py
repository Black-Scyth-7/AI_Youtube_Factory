"""Safe expression evaluation for workflow edge conditions.

Conditions are author-supplied strings evaluated against a run's context, so
this must never reach ``eval``. Even ``eval(expr, {"__builtins__": {}})`` is only
as safe as whatever filters the input: an allow-list that permits ``*`` still
admits ``9**9**9**9``, which computes an astronomically large integer and hangs
the worker.

Instead the expression is parsed to an AST and walked, permitting only a fixed
set of node types. Anything else — calls, attribute access, comprehensions,
imports — raises. Exponentiation is bounded rather than forbidden so ordinary
arithmetic still works.
"""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable
from typing import Any, Final

from app.exceptions.base import WorkflowError

#: Largest allowed exponent. Keeps ``2 ** 10`` working while refusing the
#: nested-power expressions that turn into an unbounded computation.
MAX_EXPONENT: Final = 64
#: Guards against a deeply nested expression exhausting the C stack.
MAX_DEPTH: Final = 25
MAX_LENGTH: Final = 1000

_BINARY: Final[dict[type[ast.operator], Callable[[Any, Any], Any]]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_COMPARE: Final[dict[type[ast.cmpop], Callable[[Any, Any], Any]]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}

_UNARY: Final[dict[type[ast.unaryop], Callable[[Any], Any]]] = {
    ast.Not: operator.not_,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


class ExpressionError(WorkflowError):
    """The expression is malformed or uses an unsupported construct."""


def _evaluate(node: ast.AST, context: dict[str, Any], depth: int) -> Any:
    if depth > MAX_DEPTH:
        raise ExpressionError("Expression nests too deeply.")

    match node:
        case ast.Expression():
            return _evaluate(node.body, context, depth + 1)

        case ast.Constant():
            return node.value

        # A bare name resolves against the run context; unknown names are None
        # so a condition can test a value a previous node did not set.
        case ast.Name():
            return context.get(node.id)

        case ast.Subscript():
            container = _evaluate(node.value, context, depth + 1)
            key = _evaluate(node.slice, context, depth + 1)
            try:
                return container[key]
            except (KeyError, IndexError, TypeError):
                return None

        case ast.BoolOp():
            values = [_evaluate(v, context, depth + 1) for v in node.values]
            if isinstance(node.op, ast.And):
                return all(values)
            return any(values)

        case ast.UnaryOp():
            unary = _UNARY.get(type(node.op))
            if unary is None:
                raise ExpressionError(f"Unsupported operator: {type(node.op).__name__}")
            return unary(_evaluate(node.operand, context, depth + 1))

        case ast.BinOp():
            binary = _BINARY.get(type(node.op))
            if binary is None:
                raise ExpressionError(f"Unsupported operator: {type(node.op).__name__}")
            left = _evaluate(node.left, context, depth + 1)
            right = _evaluate(node.right, context, depth + 1)
            if isinstance(node.op, ast.Pow) and (
                not isinstance(right, int | float) or abs(right) > MAX_EXPONENT
            ):
                raise ExpressionError(f"Exponent must be at most {MAX_EXPONENT}.")
            try:
                return binary(left, right)
            except ZeroDivisionError as exc:
                raise ExpressionError("Division by zero.") from exc
            except TypeError as exc:
                raise ExpressionError(f"Unsupported operand types: {exc}") from exc

        case ast.Compare():
            left = _evaluate(node.left, context, depth + 1)
            for op, comparator in zip(node.ops, node.comparators, strict=True):
                compare = _COMPARE.get(type(op))
                if compare is None:
                    raise ExpressionError(f"Unsupported comparison: {type(op).__name__}")
                right = _evaluate(comparator, context, depth + 1)
                try:
                    if not compare(left, right):
                        return False
                except TypeError:
                    return False
                left = right
            return True

        case ast.List():
            return [_evaluate(e, context, depth + 1) for e in node.elts]

        case ast.Tuple():
            return tuple(_evaluate(e, context, depth + 1) for e in node.elts)

        case _:
            raise ExpressionError(
                f"Unsupported expression element: {type(node).__name__}"
            )


def evaluate(expression: str, context: dict[str, Any] | None = None) -> Any:
    """Evaluate ``expression`` against ``context``.

    Raises:
        ExpressionError: If the expression is malformed, too long, or uses a
            construct outside the permitted set.
    """
    if len(expression) > MAX_LENGTH:
        raise ExpressionError("Expression is too long.")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"Invalid expression: {exc.msg}") from exc
    return _evaluate(tree, context or {}, 0)


def evaluate_condition(expression: str | None, context: dict[str, Any]) -> bool:
    """Evaluate an edge condition as a boolean.

    An absent or blank condition is treated as always true, so an unconditional
    edge needs no expression.
    """
    if expression is None or not expression.strip():
        return True
    return bool(evaluate(expression, context))
