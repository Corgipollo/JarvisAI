"""schemas.py - Pydantic schemas para validar output del Planner LLM.

Si el LLM no emite estimated_spend_usd o cualquier campo requerido, Pydantic
ValidationError -> reintentar Planner (NO CFO).
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, model_validator


class PlanStep(BaseModel):
    """Un paso atomico del plan. Validado por Pydantic, no por LLM."""

    action: Literal[
        "shell", "api", "click_som", "type", "hotkey", "wait",
        "custom_skill", "binance_market_order", "binance_limit_order",
        "youtube_upload", "ffmpeg_render", "remotion_render",
        "web_scrape", "file_write", "marketing_campaign",
        "browser_interact", "youtube_watch", "desktop_interact", "desktop_scan",
    ] = Field(description="action type, debe estar en el enum")

    command_or_task: str = Field(
        description="comando shell, URL, query, o descripcion de la accion",
        min_length=1,
    )

    estimated_spend_usd: float = Field(
        description="Cost USD estimado por el Planner. 0.0 si es gratis. "
                    "OBLIGATORIO - sin esto el step no puede ejecutarse.",
        ge=0,
    )

    is_financial: bool = Field(
        description="True si este step gasta dinero real (trade, ads, API paga)",
    )

    leverage: float = Field(
        default=1.0,
        ge=0,
        le=10,
        description="Multiplicador de apalancamiento. 1.0 = sin apalancamiento.",
    )

    quantity: float = Field(
        default=1.0,
        ge=0,
        description="Cantidad/repeticiones del action (ej: 5 API calls).",
    )

    pre_condition: str = Field(
        default="",
        description="Que debe ser cierto antes de ejecutar (en lenguaje natural).",
    )

    post_condition: str = Field(
        default="",
        description="Que validacion post-ejecucion confirma exito.",
    )

    reversible: bool = Field(
        default=True,
        description="Si la accion puede revertirse despues. False = sin marcha atras.",
    )

    @model_validator(mode="after")
    def shell_must_be_executable(self):
        """Si action=shell, command_or_task DEBE ser un comando Windows literal
        ejecutable (cmd /c ..., powershell -Command ..., o un binario directo).
        NO descripciones tipo 'crea un archivo' o 'instala paquete'."""
        if self.action == "shell":
            cmd = (self.command_or_task or "").strip().lower()
            if not cmd:
                raise ValueError("shell action requires non-empty command_or_task")
            ok_prefixes = (
                "cmd ", "cmd.exe", "cmd/c", "cmd /c",
                "powershell", "pwsh",
                "python ", "python.exe", "python3",
                "node ", "npm ", "npx ", "git ",
                "mkdir ", "echo ", "del ", "copy ", "move ", "type ",
                "ren ", "rd ", "rmdir ", "dir ", "robocopy ",
                "ffmpeg", "yt-dlp", "curl",
                ".\\", "c:\\", "d:\\", "e:\\", "/", "\"",
            )
            if not any(cmd.startswith(p) for p in ok_prefixes):
                raise ValueError(
                    f"shell command_or_task no parece comando ejecutable Windows: "
                    f"'{self.command_or_task[:80]}'. Debe empezar con 'cmd /c', "
                    f"'powershell -Command', o ser un binario/path directo."
                )
        return self


class Plan(BaseModel):
    """Plan completo emitido por Planner. Multiple steps."""

    steps: list[PlanStep] = Field(
        description="Lista de pasos ordenados a ejecutar.",
        min_length=1,
        max_length=50,
    )

    objective_summary: str = Field(
        description="Resumen 1-linea del objetivo del usuario.",
    )


class JudgeVerdict(BaseModel):
    """Output del Judge agent en el debate adversarial."""

    score: float = Field(
        ge=0, le=1,
        description="0=Skeptic gana totalmente, 1=Proposer gana totalmente.",
    )
    reasoning: str = Field(description="Razon corta del veredicto.")


class VerifyResult(BaseModel):
    """Output del Verifier despues de un step."""

    success: bool = Field(description="True si post_condition cumplida.")
    observed: str = Field(description="Que se observo en pantalla/output.")
    diff_from_expected: str = Field(
        default="",
        description="Discrepancia si success=False, vacio si OK.",
    )


__all__ = ["PlanStep", "Plan", "JudgeVerdict", "VerifyResult"]
