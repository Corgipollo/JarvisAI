"""Cliente Ollama para chat local con IA."""
import httpx
import json
import base64
from typing import AsyncGenerator, Optional
from config import settings


class OllamaClient:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self.vision_model = settings.OLLAMA_VISION_MODEL
        self.system_prompt = self._build_system_prompt()
        self.conversation_history: list[dict] = []

    def _build_system_prompt(self, memory_context: str = "") -> str:
        base = """Eres Jarvis, el asistente personal de inteligencia artificial de Emmanuel Pedraza.
Tu personalidad es como el Jarvis de Iron Man: profesional, eficiente, con toques de humor sutil.
Respondes en espanol por defecto. Eres directo y vas al grano.

Capacidades:
- Acceso al cerebro Obsidian de Emmanuel
- Clima, ubicacion, trafico
- Tienda Shopify GROP
- Camara y vision en tiempo real
- Ejecucion de codigo
- Busqueda en internet via Google/DuckDuckGo
- Control de PC: abrir/cerrar apps, volumen, Spotify
- Memoria persistente

REGLAS ABSOLUTAS:
1. MAXIMO 1-2 ORACIONES. NUNCA mas.
2. Habla natural. PROHIBIDO: markdown, listas, asteriscos, backticks.
3. Se directo. Sin frases de relleno.
4. Si te dan DATOS de contexto, usa SOLO esos datos para responder.
5. NUNCA inventes informacion. Si no sabes algo, di "no tengo esa info, quieres que busque en internet?"
6. NO mezcles temas. Solo responde lo que preguntaron."""
        if memory_context:
            base += f"\n\nMEMORIA DEL USUARIO:\n{memory_context}"
        return base

    def update_system_prompt(self, memory_context: str = ""):
        """Actualiza el system prompt con contexto de memoria."""
        self.system_prompt = self._build_system_prompt(memory_context)

    async def check_health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def get_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                data = r.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    async def chat_stream(
        self, message: str, images: Optional[list[str]] = None
    ) -> AsyncGenerator[str, None]:
        """Stream chat response from Ollama."""
        model = self.vision_model if images else self.model

        self.conversation_history.append({"role": "user", "content": message})

        messages = [{"role": "system", "content": self.system_prompt}]
        # Keep last 20 messages for context
        messages.extend(self.conversation_history[-20:])

        if images:
            messages[-1]["images"] = images

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
        }

        full_response = ""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/chat", json=payload
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            data = json.loads(line)
                            chunk = data.get("message", {}).get("content", "")
                            if chunk:
                                full_response += chunk
                                yield chunk
                            if data.get("done"):
                                break
        except httpx.ConnectError:
            yield "Error: Ollama no esta corriendo. Ejecuta 'ollama serve' primero."
            return

        self.conversation_history.append(
            {"role": "assistant", "content": full_response}
        )

    async def chat(self, message: str, images: Optional[list[str]] = None) -> str:
        """Non-streaming chat."""
        result = ""
        async for chunk in self.chat_stream(message, images):
            result += chunk
        return result

    async def analyze_image(self, image_base64: str, prompt: str = "") -> str:
        """Analyze an image using vision model."""
        if not prompt:
            prompt = "Describe lo que ves en esta imagen de forma detallada."
        return await self.chat(prompt, images=[image_base64])

    def clear_history(self):
        self.conversation_history.clear()


ollama = OllamaClient()
