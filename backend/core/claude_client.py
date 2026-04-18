"""Cliente Claude API — cerebro principal de Jarvis cuando hay API key."""
import os
from typing import AsyncGenerator


class ClaudeClient:
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.model = "claude-sonnet-4-20250514"
        self.conversation_history: list[dict] = []
        self.system_prompt = ""

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def update_system_prompt(self, memory_context: str = ""):
        self.system_prompt = f"""Eres Jarvis, el asistente personal de Emmanuel Pedraza. Estilo Iron Man.
Estas en Queretaro, Mexico. Respondes en espanol.

REGLAS ABSOLUTAS:
1. MAXIMO 1-2 ORACIONES. Esto es voz, no texto.
2. Habla natural. PROHIBIDO: markdown, listas, asteriscos, codigo.
3. Se directo. No digas "como IA" ni frases de relleno.
4. Si te dan datos, solo di lo importante.

{memory_context}"""

    async def chat_stream(self, message: str) -> AsyncGenerator[str, None]:
        """Stream response from Claude API."""
        import anthropic

        self.conversation_history.append({"role": "user", "content": message})

        client = anthropic.Anthropic(api_key=self.api_key)

        messages = self.conversation_history[-20:]

        try:
            with client.messages.stream(
                model=self.model,
                max_tokens=200,  # Corto para voz
                system=self.system_prompt,
                messages=messages,
            ) as stream:
                full = ""
                for text in stream.text_stream:
                    full += text
                    yield text

                self.conversation_history.append({"role": "assistant", "content": full})

        except Exception as e:
            yield f"Error con Claude: {str(e)}"

    async def chat(self, message: str) -> str:
        result = ""
        async for chunk in self.chat_stream(message):
            result += chunk
        return result

    def clear_history(self):
        self.conversation_history.clear()


claude_client = ClaudeClient()
