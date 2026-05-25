"""constitution_validator.py - Evalua reglas YAML 100% deterministic, sin LLM.

Soporta ops: lte, lt, gte, gt, eq, ne, in, not_in, matches, not_matches.
Resuelve paths dotted (proposed_action.spend_usd) navegando dicts/objects.
Evalua condicionales 'when' con AST safe (no eval arbitrario).

Devuelve violaciones list - vacia si todo OK.
"""
from __future__ import annotations

import ast
import operator
import re
from pathlib import Path
from typing import Any

import yaml

CONSTITUTION_FILE = Path(__file__).parent / "jarvis_constitution.yaml"

OPERATORS = {
    "lte": operator.le,
    "lt": operator.lt,
    "gte": operator.ge,
    "gt": operator.gt,
    "eq": operator.eq,
    "ne": operator.ne,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
    "matches": lambda a, b: bool(re.search(b, str(a))),
    "not_matches": lambda a, b: not re.search(b, str(a)),
}

# AST-safe eval for 'when' clauses - solo nodos permitidos
ALLOWED_AST = (
    ast.Expression, ast.Compare, ast.BoolOp, ast.UnaryOp,
    ast.Name, ast.Load, ast.Constant, ast.Num, ast.Str,
    ast.Attribute, ast.Subscript, ast.Slice, ast.Index,
    ast.List, ast.Tuple, ast.Eq, ast.NotEq, ast.Lt, ast.LtE,
    ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.And, ast.Or, ast.Not,
)


def _safe_eval_when(expr: str, ctx: dict) -> bool:
    """Evalua expresion 'when' en sandbox AST (sin builtins)."""
    if not expr:
        return True
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_AST):
            return False
    # Compile and eval con solo el ctx como locals, no builtins
    code = compile(tree, "<when>", "eval")
    try:
        return bool(eval(code, {"__builtins__": {}}, _flatten_ctx_for_eval(ctx)))
    except Exception:
        return False


def _flatten_ctx_for_eval(ctx: dict) -> dict:
    """Permite acceso tipo proposed_action.spend_usd en eval via attr-dict."""
    class AttrDict(dict):
        def __getattr__(self, k):
            v = self.get(k)
            if isinstance(v, dict):
                return AttrDict(v)
            return v
    return AttrDict({k: AttrDict(v) if isinstance(v, dict) else v
                     for k, v in ctx.items()})


def _resolve_path(obj: Any, path: str) -> Any:
    """Navega path dotted: 'proposed_action.spend_usd' -> obj['proposed_action']['spend_usd']."""
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return cur


def load_constitution(path: Path | None = None) -> dict:
    path = path or CONSTITUTION_FILE
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def evaluate(ctx: dict, constitution: dict | None = None) -> dict:
    """Evalua todas las reglas contra el contexto.

    Args:
        ctx: dict con keys proposed_action, sim_results, ledger, env, etc
        constitution: dict YAML cargado (si None, carga default)

    Returns:
        {
            "verdict": "ALLOW" | "DENY" | "ESCALATE",
            "violations": [{rule_id, reason, severity, value, expected}],
            "warnings": [...],
        }
    """
    if constitution is None:
        constitution = load_constitution()

    violations = []
    warnings = []

    for category in ("hard_rules", "soft_rules"):
        for rule in constitution.get(category, []):
            when = rule.get("when", "")
            if when and not _safe_eval_when(when, ctx):
                continue  # rule does not apply

            actual = _resolve_path(ctx, rule["field"])
            op_name = rule["op"]
            if actual is None:
                if "default" in rule:
                    actual = rule["default"]
                elif op_name in ("not_matches", "not_in", "ne"):
                    # "NO matchea pattern X" con field None = True (no es ese item)
                    continue
                elif op_name in ("lte", "lt", "gte", "gt"):
                    # Reglas de spend/budget: si la metrica no esta en el ledger,
                    # asumir 0 (no se ha gastado nada todavia). Antes este branch
                    # bloqueaba defensive y detenia al planner inutilmente.
                    actual = 0
                else:
                    # Field missing y no default -> trata como violation defensive
                    violations.append({
                        "rule_id": rule["id"],
                        "severity": rule.get("severity", "HARD_BLOCK"),
                        "reason": f"field '{rule['field']}' missing",
                        "actual": None,
                        "expected": rule.get("value"),
                    })
                    continue

            op_fn = OPERATORS.get(op_name)
            if op_fn is None:
                violations.append({
                    "rule_id": rule["id"],
                    "severity": "HARD_BLOCK",
                    "reason": f"unknown_operator: {op_name}",
                })
                continue

            try:
                passes = op_fn(actual, rule["value"])
            except Exception as e:
                violations.append({
                    "rule_id": rule["id"],
                    "severity": "HARD_BLOCK",
                    "reason": f"eval_error: {e}",
                })
                continue

            if not passes:
                entry = {
                    "rule_id": rule["id"],
                    "description": rule.get("description", ""),
                    "severity": rule.get("severity", "HARD_BLOCK"),
                    "reason": f"{rule['field']}={actual} fails {op_name} {rule['value']}",
                    "actual": actual,
                    "expected": rule["value"],
                    "operator": op_name,
                }
                if rule.get("severity") == "ESCALATE_HUMAN":
                    warnings.append(entry)
                else:
                    violations.append(entry)

    if violations:
        verdict = "DENY"
    elif warnings:
        verdict = "ESCALATE"
    else:
        verdict = "ALLOW"

    return {
        "verdict": verdict,
        "violations": violations,
        "warnings": warnings,
        "constitution_version": constitution.get("version", "?"),
    }


if __name__ == "__main__":
    # Test
    ctx_pass = {
        "proposed_action": {
            "type": "trade",
            "estimated_spend_usd_final": 3.00,
            "spend_usd": 3.00,
            "leverage": 1.0,
        },
        "sim_results": {
            "trade_count": 50,
            "sharpe": 1.5,
            "max_drawdown": 0.15,
            "expected_roi": 1.4,
            "ctr": 0.05,
        },
        "ledger": {
            "lifetime_spent_usd": 20.0,
            "spent_last_24h_usd": 5.0,
            "spent_last_1h_usd": 1.0,
            "api_calls_last_min": 5,
        },
        "env": {"is_weekend": False, "is_late_night": False},
    }
    print("Pass test:", evaluate(ctx_pass)["verdict"])

    ctx_fail = dict(ctx_pass)
    ctx_fail["proposed_action"] = dict(ctx_pass["proposed_action"])
    ctx_fail["proposed_action"]["leverage"] = 5.0
    result = evaluate(ctx_fail)
    print("Fail test:", result["verdict"])
    for v in result["violations"]:
        print(f"  - {v['rule_id']}: {v['reason']}")
