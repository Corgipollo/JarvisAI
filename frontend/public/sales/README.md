# Jarvis AI — Sales Kit Completo

> **Generado**: 1 de junio de 2026  
> **Versión**: 1.0  
> **Propósito**: Material listo para enviar a prospectos y cerrar ventas

---

## 📦 Contenido del Kit

| Archivo | Descripción | Uso |
|---------|-------------|-----|
| **pricing-strategy.md** | Estrategia de pricing con 3 tiers (Personal $9, Pro $29, Business $99), análisis competitivo completo con 10+ fuentes, proyecciones de revenue Año 1 | Referencia interna para negociaciones, base para argumentación de valor |
| **jarvis-ai-one-pager.pdf** | One-pager profesional de 1 página con elevator pitch, diferenciadores, pricing, casos de uso y tabla comparativa vs competencia | Primer contacto con prospectos (email, LinkedIn DM), follow-up post-demo |
| **contract-template.md** | Template legal completo de Software License Agreement (SaaS) con términos de uso, privacidad, limitación de responsabilidad, cláusulas de terminación | Adaptar para cada cliente Business tier (requiere firma), Personal/Pro usan ToS web |
| **jarvis-ai-pitch-deck.pdf** | Pitch deck de 5 slides (Portada, Problema, Solución, Mercado, Pricing+CTA) diseñado para presentaciones en vivo o envío async | Llamadas de ventas, presentaciones a equipos, inversionistas (si aplica) |
| **generate_sales_pdfs.py** | Script Python (reportlab) para regenerar PDFs si cambias branding/pricing | Ejecutar cuando actualices planes o colores de marca |

---

## 🎯 Cómo Usar Este Kit

### 1. Prospecting Frío (Cold Outreach)
**Secuencia recomendada**:
1. Email inicial: texto breve + **one-pager PDF** adjunto
2. Follow-up día 3: "¿Tuviste chance de revisar el one-pager? Te comparto el **pitch deck** para más contexto"
3. Follow-up día 7: Caso de uso específico según su industria (personalizar)

**Template de email** (adaptar):
```
Asunto: Jarvis AI — Asistente de voz que procesa localmente

Hola [Nombre],

Vi que [contexto específico del prospecto — ej: tu equipo usa mucho ChatGPT].

Creé Jarvis AI para resolver el problema de privacidad y velocidad en asistentes de IA:
- Procesa todo localmente (tu voz nunca sale del dispositivo)
- Responde en <2 segundos (vs 5-10s de OpenAI Voice)
- 90% más barato que alternativas cloud

Adjunto el one-pager con detalles. ¿Te interesa una demo de 15 min?

Saludos,
Emmanuel Pedraza
Fundador, Jarvis AI
```

### 2. Demo en Vivo
1. **Pre-demo**: enviar **pitch deck** 24h antes para que lleguen preparados
2. **Durante demo**:
   - Mostrar casos de uso reales (investigación, gestión tareas, análisis Obsidian)
   - Enfatizar diferenciadores (privacidad, offline, velocidad)
   - Mostrar el routing jerárquico en acción (Claude → Gemini → Ollama)
3. **Post-demo**: enviar **one-pager** + link a pricing (cerrar mientras está caliente el lead)

### 3. Negociación de Contratos (Business Tier)
1. Cliente pide custom terms → usar **contract-template.md** como base
2. Ajustar cláusulas según necesidades:
   - White-label: agregar adenda de branding
   - SLA custom: modificar §5.2 con tiempos específicos
   - Facturación anual: descuento 17% (2 meses gratis)
3. Firmar digitalmente (DocuSign o similar)

### 4. Presentaciones a Inversionistas (si aplica)
- Usar **pitch deck** como estructura
- Agregar slides de traction (usuarios, MRR, growth rate) después de Slide 4
- Incluir roadmap técnico (features próximos 6 meses)

---

## 📊 Pricing Strategy — TL;DR

| Tier | Precio | Target Audience | Conversión Esperada |
|------|--------|-----------------|---------------------|
| **Personal Free** | $0/mes | Early adopters, estudiantes | Base de usuarios (10K Año 1) |
| **Personal Paid** | $9/mes | Individuos que superan límite free | 5% de free users → $4.5K MRR |
| **Pro** | $29/mes | Profesionales, freelancers | 1% de total users → $2.9K MRR |
| **Business** | $99/mes | Equipos pequeños (3-5 personas) | 0.1% de total users → $1K MRR |

**Total MRR Año 1**: ~$8.4K ($100K ARR)  
**Margen bruto**: 68% (costos Claude API + infra ~$2.7K/mes)

---

## 🔄 Actualizar el Kit

### Cambiar Pricing
1. Editar `pricing-strategy.md` con nuevos precios
2. Actualizar `generate_sales_pdfs.py` (variables `pricing_data` en one-pager y `plans` en pitch deck)
3. Ejecutar: `python generate_sales_pdfs.py`
4. Revisar PDFs generados

### Cambiar Branding
1. Editar colores en `generate_sales_pdfs.py`:
   ```python
   BRAND_PRIMARY = colors.HexColor('#TU_COLOR')
   BRAND_SECONDARY = colors.HexColor('#TU_COLOR')
   ```
2. Regenerar PDFs

### Actualizar Contrato
1. Consultar con abogado local (México: verificar Ley Federal de Protección de Datos Personales)
2. Actualizar `contract-template.md` según feedback legal
3. Versionar (incrementar "Versión X.Y" en header)

---

## 🎨 Brand Guidelines Actuales

**Colores**:
- Primary: #2563EB (azul tech)
- Secondary: #10B981 (verde success)
- Accent: #F59E0B (naranja energy)
- Dark: #1F2937 (texto)
- Light: #F3F4F6 (backgrounds)

**Tipografía**: Helvetica (sistema), sans-serif clean

**Tono de voz**: Técnico pero accesible, directo, sin hype, enfocado en valor real

---

## 📝 Próximos Pasos Sugeridos

1. **Landing page de ventas** (`/pricing`) con Stripe Checkout integrado
2. **Case studies** de early adopters (1-2 testimonios escritos + video)
3. **Webinar grabado** (20 min) para enviar a prospectos async
4. **Email drip campaign** (5 emails automatizados para nurturing)
5. **Affiliate program** (20% comisión recurrente para referrals)

---

**Contacto**:  
Emmanuel Pedraza  
contact@jarvisai.com  
www.jarvisai.com
