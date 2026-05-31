# 🔍 ERROR TRACKING SETUP — Sentry Integration

**Fecha:** 2026-05-31  
**Status:** ✅ Configuración lista para despliegue

---

## 📦 Instalación de Sentry

### Backend (Python/FastAPI)

```bash
cd backend
pip install sentry-sdk[fastapi]
```

Agregar a `requirements.txt`:
```
sentry-sdk[fastapi]==1.45.0
```

---

## 🔧 Configuración

### 1. Obtener DSN de Sentry

1. Crea cuenta en: https://sentry.io/signup/
2. Crea nuevo proyecto: **JarvisAI Backend** (Platform: Python)
3. Copia el **DSN** (ejemplo: `https://abc123@o123456.ingest.sentry.io/7654321`)

### 2. Configurar `.env`

Agregar al archivo `.env`:
```env
# === ERROR TRACKING ===
SENTRY_DSN=https://tu_dsn_aqui@sentry.io/proyecto
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_ENABLED=true
```

### 3. Integrar en `backend/main.py`

Agregar al inicio del archivo:

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
import os
from dotenv import load_dotenv

load_dotenv()

# Inicializar Sentry
if os.getenv("SENTRY_ENABLED", "false").lower() == "true":
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        environment=os.getenv("SENTRY_ENVIRONMENT", "development"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", 0.1)),
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            LoggingIntegration(
                level=logging.INFO,        # Captura logs INFO+
                event_level=logging.ERROR  # Envía a Sentry solo ERROR+
            ),
        ],
        # Tags personalizados
        before_send=lambda event, hint: add_jarvis_context(event, hint),
    )
    print("✅ Sentry initialized")

def add_jarvis_context(event, hint):
    """Agrega contexto adicional a cada error"""
    event["tags"]["jarvis_version"] = "3.0"
    event["tags"]["llm_provider"] = os.getenv("JARVIS_LLM_PROVIDER", "unknown")
    return event
```

---

## 🎯 Errores a Trackear

### Categorías Críticas

| Categoría | Ejemplo | Severidad |
|-----------|---------|-----------|
| **STT Failures** | `faster_whisper.TranscriptionError` | High |
| **LLM Routing Failures** | `anthropic.APIError`, `ollama.ConnectionError` | Critical |
| **Integration Failures** | `spotify.AuthError`, `obsidian.VaultNotFound` | Medium |
| **System Errors** | `MemoryError`, `OSError` | Critical |
| **Timeout Errors** | `asyncio.TimeoutError` en comandos | High |

### Custom Event Tracking

Agregar en puntos críticos del código:

```python
import sentry_sdk

# Capturar evento custom
with sentry_sdk.push_scope() as scope:
    scope.set_tag("command_type", "voice")
    scope.set_context("user_input", {
        "text": transcription,
        "duration_ms": duration
    })
    sentry_sdk.capture_message(
        "Voice command executed",
        level="info"
    )

# Capturar excepción con contexto
try:
    result = await execute_command(cmd)
except Exception as e:
    sentry_sdk.capture_exception(e)
    raise
```

---

## 📊 Dashboards y Alertas

### Dashboard Recomendado

Crear en Sentry dashboard con:

1. **Error Rate** (últimas 24h)
2. **Top 10 errores por frecuencia**
3. **Latencia promedio de comandos**
4. **Errores por proveedor de IA** (Claude vs Gemini vs Ollama)
5. **Tasa de éxito de transcripciones STT**

### Alertas Críticas

Configurar alertas para:

- **Error rate > 5% en 1 hora** → Telegram + Email
- **Más de 10 fallos del mismo error en 15 min** → Telegram
- **Timeout en comandos > 30 segundos** → Log warning
- **Memoria > 12GB** → Telegram

---

## 🧪 Testing de Sentry

### Test Manual

```python
# En backend/main.py, agregar endpoint de test:

@app.get("/sentry-test")
async def test_sentry():
    """Endpoint para probar que Sentry está capturando errores"""
    try:
        # Forzar un error
        1 / 0
    except ZeroDivisionError as e:
        sentry_sdk.capture_exception(e)
        return {"status": "error sent to sentry", "check": "https://sentry.io"}
```

### Verificar

```bash
# 1. Iniciar Jarvis
python backend/main.py

# 2. Disparar error de prueba
curl http://localhost:8000/sentry-test

# 3. Verificar en Sentry dashboard (en ~10 segundos debe aparecer)
```

---

## 📈 Métricas Esperadas

### Baseline (primera semana)

| Métrica | Valor Esperado |
|---------|----------------|
| Error rate | < 2% de requests |
| Timeout rate | < 1% de comandos |
| STT failures | < 5% de voice inputs |
| LLM routing failures | < 0.5% |
| Crashes | 0 por día |

### Alertas si:

- Error rate > 5%
- Timeout rate > 3%
- Cualquier crash (exit code != 0)

---

## 🔐 Privacidad y GDPR

### Data Scrubbing

Configurar en Sentry para NO enviar:

```python
sentry_sdk.init(
    # ... config anterior ...
    
    # Scrub datos sensibles
    send_default_pii=False,  # NO enviar IP, headers, cookies
    
    # Custom scrubbing
    before_send=lambda event, hint: scrub_sensitive_data(event, hint),
)

def scrub_sensitive_data(event, hint):
    """Remueve API keys, tokens, etc de eventos"""
    if 'request' in event:
        # Remover headers sensibles
        headers = event['request'].get('headers', {})
        for key in ['Authorization', 'X-API-Key', 'Cookie']:
            if key in headers:
                headers[key] = '[REDACTED]'
    
    # Remover contenido de Obsidian vault
    if 'extra' in event and 'vault_content' in event['extra']:
        event['extra']['vault_content'] = '[REDACTED]'
    
    return event
```

---

## 📝 Checklist de Implementación

- [ ] Cuenta de Sentry creada
- [ ] Proyecto "JarvisAI Backend" creado
- [ ] DSN copiado a `.env`
- [ ] `sentry-sdk[fastapi]` instalado
- [ ] Código de inicialización agregado a `main.py`
- [ ] Endpoint `/sentry-test` probado exitosamente
- [ ] Dashboard configurado en Sentry
- [ ] Alertas de Telegram configuradas
- [ ] Data scrubbing verificado (sin API keys en eventos)
- [ ] Documentación actualizada

---

## 🚀 Frontend Error Tracking (Opcional)

Para trackear errores en Electron:

```bash
cd frontend
npm install @sentry/electron
```

```javascript
// En frontend/main.js
import * as Sentry from '@sentry/electron';

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.SENTRY_ENVIRONMENT || 'development',
});
```

---

## 📞 Recursos

- **Docs oficiales**: https://docs.sentry.io/platforms/python/guides/fastapi/
- **Best practices**: https://docs.sentry.io/product/best-practices/
- **Alertas**: https://docs.sentry.io/product/alerts/

---

**Status:** ✅ READY FOR IMPLEMENTATION  
**Tiempo estimado de setup:** 15 minutos  
**Última actualización:** 2026-05-31 por Claude Code
