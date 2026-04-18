"""Cliente Free AI — acceso gratuito a modelos potentes via APIs OpenAI-compatible."""
import os
import json
import httpx
from typing import AsyncGenerator, Optional


PROVIDER_CONFIGS = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-2.5-flash",
        "env_key": "GEMINI_API_KEY",
        "auth_style": "bearer",  # also supports query param, but bearer works
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "model": "qwen3-235b",
        "env_key": "CEREBRAS_API_KEY",
        "auth_style": "bearer",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "deepseek/deepseek-chat-v3-0324:free",
        "env_key": "OPENROUTER_API_KEY",
        "auth_style": "bearer",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "env_key": "GROQ_API_KEY",
        "auth_style": "bearer",
    },
}

# Priority order for fallback
FALLBACK_ORDER = ["gemini", "cerebras", "openrouter", "groq"]


class FreeAIClient:
    def __init__(self):
        self.preferred_provider = os.getenv("FREE_AI_PROVIDER", "gemini").lower()
        self.model_override = os.getenv("FREE_AI_MODEL", "")
        self.conversation_history: list[dict] = []
        self.system_prompt = self._build_system_prompt()
        self._available_providers: list[str] = []
        self._refresh_available()

    def _refresh_available(self):
        """Detect which providers have API keys configured."""
        self._available_providers = []
        # Put preferred first, then the rest in fallback order
        ordered = [self.preferred_provider] + [
            p for p in FALLBACK_ORDER if p != self.preferred_provider
        ]
        for name in ordered:
            cfg = PROVIDER_CONFIGS.get(name)
            if cfg and os.getenv(cfg["env_key"], ""):
                self._available_providers.append(name)

    @property
    def is_available(self) -> bool:
        self._refresh_available()
        return len(self._available_providers) > 0

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
        self.system_prompt = self._build_system_prompt(memory_context)

    def clear_history(self):
        self.conversation_history.clear()

    def _get_headers(self, provider_name: str) -> dict:
        cfg = PROVIDER_CONFIGS[provider_name]
        api_key = os.getenv(cfg["env_key"], "")
        headers = {"Content-Type": "application/json"}
        headers["Authorization"] = f"Bearer {api_key}"
        if provider_name == "openrouter":
            headers["HTTP-Referer"] = "http://localhost:8765"
            headers["X-Title"] = "Jarvis AI"
        return headers

    def _get_model(self, provider_name: str) -> str:
        if self.model_override:
            return self.model_override
        return PROVIDER_CONFIGS[provider_name]["model"]

    def _get_url(self, provider_name: str, endpoint: str = "chat/completions") -> str:
        return f"{PROVIDER_CONFIGS[provider_name]['base_url']}/{endpoint}"

    async def check_health(self) -> bool:
        """Check if at least one free provider is reachable."""
        for name in self._available_providers:
            try:
                url = self._get_url(name, "models")
                headers = self._get_headers(name)
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.get(url, headers=headers)
                    if r.status_code == 200:
                        return True
            except Exception:
                continue
        return False

    async def chat_stream(
        self, message: str, images: Optional[list[str]] = None
    ) -> AsyncGenerator[str, None]:
        """Stream chat response, with automatic provider fallback."""
        self._refresh_available()

        if not self._available_providers:
            yield "Error: No hay API keys de Free AI configuradas."
            return

        self.conversation_history.append({"role": "user", "content": message})

        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.conversation_history[-20:])

        # If images provided, attach to last user message as vision content
        if images and len(images) > 0:
            last_msg = messages[-1]
            content = [{"type": "text", "text": last_msg["content"]}]
            for img in images:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img}"},
                })
            messages[-1] = {"role": "user", "content": content}

        full_response = ""
        success = False

        for provider_name in self._available_providers:
            try:
                full_response = ""
                async for chunk in self._stream_from_provider(provider_name, messages):
                    full_response += chunk
                    yield chunk
                success = True
                break
            except Exception as e:
                print(f"[FreeAI] {provider_name} failed: {e}, trying next...")
                continue

        if not success:
            yield "Error: Todos los proveedores Free AI fallaron."
            # Remove the user message we added since we couldn't get a response
            if self.conversation_history and self.conversation_history[-1]["role"] == "user":
                self.conversation_history.pop()
            return

        self.conversation_history.append({"role": "assistant", "content": full_response})

    async def _stream_from_provider(
        self, provider_name: str, messages: list[dict]
    ) -> AsyncGenerator[str, None]:
        """Stream from a specific provider using OpenAI-compatible SSE format."""
        url = self._get_url(provider_name)
        headers = self._get_headers(provider_name)
        model = self._get_model(provider_name)

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "max_tokens": 300,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    raise Exception(
                        f"HTTP {response.status_code}: {body.decode(errors='replace')[:200]}"
                    )

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line == "data: [DONE]":
                        break
                    if line.startswith("data: "):
                        json_str = line[6:]
                        try:
                            data = json.loads(json_str)
                            choices = data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue

    async def chat(self, message: str, images: Optional[list[str]] = None) -> str:
        """Non-streaming chat."""
        result = ""
        async for chunk in self.chat_stream(message, images):
            result += chunk
        return result


free_ai = FreeAIClient()
