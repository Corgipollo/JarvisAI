"""llm_structured.py - Wrapper que fuerza output Pydantic-valid del LLM.

Equivalente a langchain `with_structured_output()` pero usando nuestro
proxy local de Claude. Reintenta hasta N veces inyectando el error de
validacion al prompt para que el LLM corrija.
"""
from __future__ import annotations

import json
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


def llm_structured(
    prompt: str,
    schema_cls: Type[T],
    system: str = "",
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 2000,
    max_retries: int = 1,  # antes 2 -> baja gasto en tasks que fallan schema
) -> T:
    """Llama Claude, valida con Pydantic, reintenta si schema falla.

    Raises:
        ValueError: si despues de max_retries la validacion sigue fallando.
    """
    schema_json = schema_cls.model_json_schema()
    base_prompt = (
        f"{prompt}\n\n"
        f"DEBES responder con JSON valido que cumpla EXACTAMENTE este schema:\n"
        f"```json\n{json.dumps(schema_json, indent=2)}\n```\n\n"
        f"Responde SOLO con el JSON, sin texto adicional, sin markdown fences."
    )

    last_err: Exception | None = None
    current_prompt = base_prompt

    for attempt in range(max_retries + 1):
        try:
            from jarvis_bridge.jarvis_brain import ask_claude_json
            raw = ask_claude_json(
                current_prompt,
                system=system,
                model=model,
                max_tokens=max_tokens,
            )
            if raw is None:
                raise ValueError("ask_claude_json returned None")
            obj = schema_cls.model_validate(raw)
            return obj
        except ValidationError as e:
            last_err = e
            errors = "\n".join(
                f"  - {err['loc']}: {err['msg']} (got {err.get('input', '?')})"
                for err in e.errors()[:5]
            )
            current_prompt = (
                f"{base_prompt}\n\n"
                f"INTENTO PREVIO FALLO con estos errores de validacion:\n{errors}\n\n"
                f"Corrige y reintenta. Atencion estricta al schema."
            )
        except Exception as e:
            last_err = e
            current_prompt = (
                f"{base_prompt}\n\n"
                f"INTENTO PREVIO ERROR: {e}\n"
                f"Reintenta con JSON valido."
            )

    raise ValueError(
        f"LLM falló schema {schema_cls.__name__} tras {max_retries + 1} "
        f"intentos. Ultimo error: {last_err}"
    )


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__file__).rsplit("jarvis_v2", 1)[0])
    from jarvis_v2.core.schemas import Plan
    p = llm_structured(
        "Plan: abrir Bloc de notas y escribir 'hola'",
        Plan,
        system="Eres planificador. Pasos atomicos. No invente steps no necesarios.",
    )
    print(p.model_dump_json(indent=2))
