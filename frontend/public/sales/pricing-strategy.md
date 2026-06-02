# Jarvis AI — Pricing Strategy 2026

## Investigación Competitiva: Hallazgos Clave

### Competidores Directos (Voice AI)

**OpenAI Voice API** — confianza ALTA
- Realtime API: $0.30/min típico (rango $0.18-$0.46/min sin caché)
- Whisper STT: $0.006/min
- TTS: $0.015/min
- [Fuente: OpenAI Pricing](https://openai.com/api/pricing/)
- [Fuente: CallSphere Analysis](https://callsphere.ai/blog/vw2c-openai-realtime-cost-per-minute-math-2026)

**ElevenLabs** — confianza ALTA
- Free: 10,000 credits (~10 min/mes)
- Creator: $22/mo (121,000 credits)
- Pro: $99/mo (500,000 credits)
- Scale: $330/mo (2M credits)
- [Fuente: ElevenLabs Pricing](https://elevenlabs.io/pricing)
- [Fuente: Cekura Analysis](https://www.cekura.ai/blogs/elevenlabs-pricing)

**Speechify** — confianza ALTA
- Free: lectura limitada
- Premium: $139/año ($11.58/mo) o $29/mo mensual
- [Fuente: Speechify Pricing](https://speechify.com/pricing/)

### Personal AI Assistants (Indirectos)

**ChatGPT Plus / Claude Pro**: $20/mo cada uno (reactivos, no autónomos)
**Alfred_**: $24.99/mo (email autónomo)
**Lindy AI**: $49.99+/mo (agentes custom)
- [Fuente: alfred_ blog](https://get-alfred.ai/blog/best-ai-assistant-like-jarvis)

### Voice AI Business Models — confianza ALTA

**Freemium típico**: 100-500 min/mes gratis → $19-50/mo básico → $99-350/mo pro
**Pay-as-you-go**: $0.08-0.15/min (negocios)
**Hybrid**: base fee + per-minute overage ($0.50/min típico)
- [Fuente: Aircall](https://aircall.io/blog/best-practices/ai-voice-agent-cost/)
- [Fuente: CloudTalk](https://www.cloudtalk.io/blog/how-much-does-voice-ai-cost/)

### Costos STT/TTS (Estructura)

- **Edge TTS**: FREE (Microsoft no oficial, confiable para uso interno)
- **Faster-Whisper**: FREE (open-source, local)
- **Groq Whisper**: FREE (límites diarios)
- [Fuente: Medium Comparison](https://medium.com/@linglijunmail/tts-stt-comparison-groq-edge-google-elevenlabs-ai-homelab-ba24247c0ede)

---

## Ventaja Competitiva de Jarvis

### Stack Cost-Efficient
- **STT**: faster-whisper (gratis, local)
- **TTS**: edge-tts (gratis, Microsoft)
- **LLM**: routing jerárquico Claude API → Gemini free → Ollama local
- **Infraestructura**: Electron desktop (no servidores cloud)

**Costo marginal por usuario**: ~$0.02-0.05/min (90% menos que competidores API-first)

### Diferenciadores Clave
1. **Privacidad**: procesa localmente, no sube audio a cloud (vs OpenAI/ElevenLabs)
2. **Offline-capable**: Ollama local permite trabajo sin internet
3. **Customizable**: open-source, usuarios pueden ajustar prompts/modelos
4. **Voice-first UX**: optimizado para conversación, no chat con voz pegada

---

## Estrategia de Pricing: 3 Tiers

### Tier 1: **Personal** — $0/mes (freemium) o $9/mes

**Target**: individuos, estudiantes, early adopters

**Límites Free**:
- 500 min/mes de conversación
- Ollama + Gemini free tier only (sin Claude)
- 1 dispositivo
- Actualizaciones estables (no beta)

**Límites Paid $9/mo**:
- 2,000 min/mes
- Claude API incluido (routing completo)
- 2 dispositivos
- Soporte email (48h)

**Comparativa**: más barato que Speechify Premium ($11.58/mo) y ChatGPT Plus ($20/mo)

---

### Tier 2: **Pro** — $29/mes

**Target**: profesionales, freelancers, power users

**Features**:
- Conversación ilimitada
- Routing completo (Claude Opus priorizado)
- 3 dispositivos
- Integración Obsidian vault (RAG personal)
- Voice cloning custom (1 voz adicional)
- Soporte prioritario (24h)
- Acceso beta features

**Comparativa**: alineado con Alfred_ ($24.99) y Speechify mensual ($29), pero con más autonomía

---

### Tier 3: **Business** — $99/mes

**Target**: equipos pequeños, profesionales con clientes

**Features**:
- Todo de Pro +
- 5 usuarios/dispositivos
- API access (webhooks, integraciones custom)
- White-label option (quitar branding Jarvis)
- Voice cloning ilimitado
- Asistencia técnica 1:1
- SLA 99% uptime
- Exportar transcripts/analytics

**Comparativa**: competitivo vs ElevenLabs Pro ($99) y voice AI agents ($350/mo), pero con autonomía completa

---

## Estrategia de Go-to-Market

### Fase 1 (Q2 2026): Personal Free + Paid
- Lanzar freemium para tracción
- Convertir 5-10% a $9/mo (benchmark SaaS)
- Validar product-market fit

### Fase 2 (Q3 2026): Pro Tier
- Agregar features avanzados (Obsidian RAG, voice cloning)
- Target: profesionales técnicos (devs, researchers)

### Fase 3 (Q4 2026): Business
- API + white-label para agencias/consultores
- Partnerships con herramientas productivity (Notion, Zapier)

---

## Proyección de Revenue (conservador)

**Año 1 asumiendo**:
- 10,000 usuarios free
- 500 usuarios Personal $9/mo = $4,500/mo
- 100 usuarios Pro $29/mo = $2,900/mo
- 10 usuarios Business $99/mo = $990/mo

**MRR Año 1**: ~$8,400/mo ($100K ARR)

**Costos**:
- Claude API: ~$1,500/mo (usuarios paid)
- Infraestructura: $200/mo (hosting docs/updates)
- Soporte: $1,000/mo (part-time)

**Margen bruto**: 68% (típico SaaS B2C)

---

## Fuentes Completas

1. [OpenAI API Pricing](https://openai.com/api/pricing/)
2. [OpenAI Realtime Cost Analysis](https://callsphere.ai/blog/vw2c-openai-realtime-cost-per-minute-math-2026)
3. [ElevenLabs Pricing](https://elevenlabs.io/pricing)
4. [ElevenLabs Plan Breakdown](https://www.cekura.ai/blogs/elevenlabs-pricing)
5. [Speechify Pricing](https://speechify.com/pricing/)
6. [AI Assistant Alternatives](https://get-alfred.ai/blog/best-ai-assistant-like-jarvis)
7. [STT/TTS Cost Comparison](https://medium.com/@linglijunmail/tts-stt-comparison-groq-edge-google-elevenlabs-ai-homelab-ba24247c0ede)
8. [Voice AI Cost Breakdown](https://aircall.io/blog/best-practices/ai-voice-agent-cost/)
9. [Voice AI Business Models](https://www.cloudtalk.io/blog/how-much-does-voice-ai-cost/)
10. [Voice AI Pricing Guide](https://www.ringly.io/blog/voice-ai-pricing)

---

**Última actualización**: 2026-05-31  
**Próxima revisión**: Q3 2026 (ajustar según competencia)
