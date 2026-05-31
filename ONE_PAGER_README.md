# 📄 Jarvis AI One-Pager — Guía de Uso

> Landing simple (HTML + Markdown) explicando qué es Jarvis, para quién, caso de uso killer, pricing y CTA.
> **Exportable a PDF** para compartir con leads cuando pregunten "cuéntame más".

---

## 📦 Archivos Creados

| Archivo | Propósito | Cómo usar |
|---------|-----------|-----------|
| `one-pager.html` | Landing visual HTML con Tailwind CSS | Abrir en navegador, exportar a PDF |
| `one-pager.md` | Versión texto Markdown | Copiar/pegar en emails, Slack, Discord |
| `OPEN_ONE_PAGER.bat` | Script para abrir el HTML | Doble clic para abrir en navegador |

---

## 🚀 Uso Rápido

### Opción 1: Ver en navegador
```bash
# Windows
OPEN_ONE_PAGER.bat

# Manual
# Doble clic en one-pager.html
```

### Opción 2: Exportar a PDF (para enviar a leads)
1. Abre `one-pager.html` en cualquier navegador
2. Clic en botón **"Exportar PDF"** (esquina superior derecha)
3. O presiona `Ctrl+P` y selecciona "Guardar como PDF"
4. El PDF queda optimizado (sin botones, márgenes correctos)

### Opción 3: Compartir como texto (email/chat)
1. Abre `one-pager.md`
2. Copia todo el contenido
3. Pega en email, Slack, Discord, etc.

---

## 📧 Casos de Uso

### Caso 1: Lead pregunta "cuéntame más sobre Jarvis"
**Respuesta:**
> Claro! Te comparto el one-pager completo:  
> [adjuntar `one-pager.pdf`]
> 
> En resumen:
> - Asistente voice-first con routing inteligente de IA
> - Ahorra ~85 min/día eliminando cambios de contexto
> - Pricing desde $0 (open source) hasta $250/mes (Professional)
> 
> ¿Te interesa agendar una demo de 15 min?

### Caso 2: Pitch rápido en LinkedIn/Twitter
**Texto:**
> Acabo de lanzar Jarvis AI 🚀  
> Tu asistente personal voice-first con routing inteligente:  
> Claude → Gemini → Ollama local  
> 
> Ahorra 85 min/día eliminando cambios de contexto.  
> 100% local-first, open-source desde $0.  
> 
> [link al one-pager.html hosteado]

### Caso 3: Email frío a PyMEs LATAM
**Subject:** Ahorra 85 min/día con tu asistente de IA personal

**Body:**
> Hola [nombre],
> 
> Soy Emmanuel, creador de Jarvis AI.
> 
> Jarvis es un asistente personal activado por voz que resuelve un problema que afecta a equipos técnicos:
> 
> **El problema:** Cambias entre apps 300 veces/día. Pierdes 20-30% de tu día solo "re-enfocándote".
> 
> **La solución:** Control por voz de Spotify, Obsidian, terminal, debugging visual con Claude Vision, todo sin salir de tu editor.
> 
> **Pricing:** Desde $0 (open source) hasta $250/mes (5 usuarios, instalación asistida).
> 
> [adjuntar one-pager.pdf]
> 
> ¿Te interesa una demo de 15 min la próxima semana?
> 
> Saludos,  
> Emmanuel

---

## 🎨 Personalización

### Cambiar colores
Edita `one-pager.html`:
```html
<!-- Busca estas clases de Tailwind CSS -->
bg-purple-600   → Cambia "purple" por otro color (blue, green, red, indigo)
text-purple-600 → Idem

<!-- Ejemplo: cambiar a azul -->
bg-blue-600
text-blue-600
```

### Cambiar email/links
Busca y reemplaza en `one-pager.html` y `one-pager.md`:
- `emmanuel@jarvisai.lat` → tu email real
- `https://github.com/Corgipollo/JarvisAI` → tu repo real
- Placeholder `[Ver video demo]` → link a YouTube cuando tengas video

### Agregar secciones
El HTML está estructurado con comentarios:
```html
<!-- Hero -->
<!-- Pain Point Killer -->
<!-- How it Works -->
<!-- Para Quién -->
<!-- Pricing -->
<!-- Proof -->
<!-- CTA -->
<!-- Footer -->
```

Duplica cualquier `<section>` para agregar más contenido.

---

## 🌐 Hostear el One-Pager (opcional)

### Opción 1: GitHub Pages (gratis)
```bash
# Crear repo público
# Subir one-pager.html como index.html
# Activar GitHub Pages en Settings → Pages
# URL será: https://tuusuario.github.io/jarvis-landing
```

### Opción 2: Vercel (gratis, más rápido)
```bash
npm install -g vercel
cd JarvisAI
vercel --prod
# Sigue el wizard, selecciona one-pager.html como index
```

### Opción 3: Netlify Drop (gratis, drag & drop)
1. Abre https://app.netlify.com/drop
2. Arrastra `one-pager.html`
3. Listo, te da una URL pública

---

## 📊 Tracking (opcional)

Si quieres saber cuántos leads ven el one-pager, agrega Google Analytics:

```html
<!-- Antes de </head> en one-pager.html -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

O usa Plausible/Fathom para analytics más ligeros.

---

## ✅ Checklist Antes de Compartir

- [ ] Cambié `emmanuel@jarvisai.lat` por mi email real
- [ ] Cambié el link de GitHub si el repo es otro
- [ ] Probé exportar a PDF (se ve bien, sin botones, márgenes OK)
- [ ] Probé abrir en mobile (responsive)
- [ ] Pricing está actualizado (verifiqué `PRICING.md`)
- [ ] CTA link funciona (GitHub repo público o landing hosteada)

---

## 🚀 Siguientes Pasos

1. **Hostea el one-pager** (GitHub Pages / Vercel / Netlify)
2. **Crea un video demo de 3 min** y agrégalo al one-pager
3. **Comparte en LinkedIn/Twitter** con el link
4. **Envía a tus primeros 10 leads** para validar el mensaje
5. **A/B test:** prueba diferentes headlines en el Hero

---

**¿Preguntas?** Edita el one-pager.html o one-pager.md directamente. HTML usa Tailwind CSS vía CDN, no necesita build step.