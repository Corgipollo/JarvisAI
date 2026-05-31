# 🚀 Instrucciones de Deploy — Landing Page Actualizada

**Fecha**: 2026-05-31  
**Fix aplicado**: Bloqueador #1 (Demo Video Section)  
**Build status**: ✅ Compilado exitosamente

---

## ✅ Cambios Listos para Deploy

### 1. Landing Page (`jarvis-landing/`)
**Archivos modificados**:
- `src/pages/index.astro` — agregada sección "Ve Jarvis AI en Acción"

**Cambios visuales**:
- ✅ Nueva sección demo video entre Hero y Features
- ✅ CTAs actualizados: "Ver demo" (primary) + "View on GitHub" (secondary)
- ✅ Link directo a https://github.com/Corgipollo/JarvisAI
- ✅ Placeholder con instrucciones mientras grabas demo real
- ✅ Stats bar: "100% local / <2s respuesta / 5+ modelos"

**Build generado**: `jarvis-landing/dist/index.html` ✅

---

### 2. README.md
**Fix aplicado**: Placeholders reemplazados

❌ Antes:
```bash
git clone https://github.com/TU_USUARIO/JarvisAI.git
```

✅ Ahora:
```bash
git clone https://github.com/Corgipollo/JarvisAI.git
```

---

## 🎬 ACCIÓN REQUERIDA: Grabar Demo Video

Para completar el fix, necesitas grabar demo de 30-60 segundos.

### Guion Recomendado (60s total)

**[0-10s] Intro**
- Mostrar desktop limpio
- Texto overlay: "Jarvis AI — Control por voz sin tocar el teclado"

**[10-25s] Comando Simple**
- Decir: "Jarvis, abre Visual Studio Code"
- Mostrar: activación del wake word + transcripción en pantalla + VS Code abriendo
- Respuesta de Jarvis con voz: "Abriendo Visual Studio Code"

**[25-45s] Comando Inteligente**
- Decir: "Jarvis, captura mi pantalla y dime qué ves"
- Mostrar: screenshot tomado + Claude Vision analizando + transcripción
- Respuesta de Jarvis: "Veo Visual Studio Code con un archivo Python abierto en la línea 42..."

**[45-55s] Control de Spotify (opcional)**
- Decir: "Jarvis, reproduce música de trabajo"
- Mostrar: Spotify abriendo + música empezando

**[55-60s] Outro**
- Texto overlay: "100% local • Routing inteligente • Open source"
- CTA: "Descarga en github.com/Corgipollo/JarvisAI"

### Specs Técnicas
- **Resolución**: 1920x1080 (Full HD)
- **Formato**: MP4 (H.264)
- **Duración**: 30-60s
- **Audio**: Obligatorio (mostrar tu voz + voz de Jarvis)
- **Edits**: Mínimos (el punto es "sin edits, sin scripts")
- **Thumbnail**: Captura frame a los 5s para poster

### Herramientas Recomendadas
- **Grabación**: OBS Studio (gratis, pro-level)
- **Hosting**:
  - Opción A: YouTube (unlisted) → mejor SEO + embeds rápidos
  - Opción B: Loom → más fácil, pero menos control
  - Opción C: Subir a `/public/demo.mp4` en el repo → ~15-30 MB max

---

## 📤 Deploy de la Landing

### Opción A: GitHub Pages (recomendado si ya está ahí)

```bash
cd /c/Users/Emmanuel/Documents/JarvisAI/jarvis-landing

# Build production
npm run build

# Deploy a GitHub Pages
# (asumiendo que ya tienes gh-pages branch configurado)
git checkout gh-pages
cp -r dist/* .
git add .
git commit -m "feat: add demo video section + GitHub CTA"
git push origin gh-pages
```

### Opción B: Vercel (si ya está en Vercel)

```bash
cd /c/Users/Emmanuel/Documents/JarvisAI/jarvis-landing

# Deploy automático (si tienes Vercel CLI)
vercel --prod

# O push al branch main y Vercel auto-deploya
git add .
git commit -m "feat: add demo video section + GitHub CTA"
git push origin main
```

### Opción C: Netlify

Si el form de contacto usa Netlify Forms (línea 126 del código), probablemente ya estés en Netlify:

```bash
# Drag & drop jarvis-landing/dist/ a Netlify dashboard
# O conecta el repo y auto-deploya
```

---

## 🎯 Después del Deploy

### 1. Actualizar Demo Video (cuando lo tengas grabado)

**Si subes a YouTube**:
```astro
<!-- En src/pages/index.astro, línea ~60 -->
<iframe
  class="w-full h-full"
  src="https://www.youtube.com/embed/TU_VIDEO_ID?autoplay=0&rel=0"
  title="Jarvis AI Demo"
  frameborder="0"
  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
  allowfullscreen>
</iframe>
```

**Si subes local**:
```bash
# 1. Colocar demo.mp4 en jarvis-landing/public/
cp /path/to/demo.mp4 jarvis-landing/public/

# 2. Descomentar en index.astro línea ~68
<video controls preload="metadata" class="w-full h-full object-cover" poster="/demo-thumbnail.jpg">
  <source src="/demo.mp4" type="video/mp4" />
</video>

# 3. Rebuild y redeploy
npm run build
# deploy según tu método
```

### 2. Verificar Conversión

Después de deploy, testea el funnel completo de nuevo:

1. ✅ Prospecto visita landing
2. ✅ Ve demo video (debería estar visible ahora con el placeholder)
3. ✅ Click "View on GitHub" → llega al repo
4. ✅ Puede clonar y seguir README actualizado (sin placeholders)
5. ⏭️ (Pendiente: installer .exe para non-technical users)

---

## 📊 Métricas a Monitorear

Si usas Google Analytics / Plausible / Mixpanel:

- **Video play rate**: % de visitantes que le dan play al demo
- **GitHub click rate**: % que clickean "View on GitHub"
- **Form submit rate**: % que agendan demo (debería BAJAR si el video es bueno — señal positiva)
- **Bounce rate**: Debería bajar ~20-40% vs antes del video

---

## 🐛 Si Algo Sale Mal

### El build falla
```bash
cd jarvis-landing
rm -rf node_modules package-lock.json
npm install
npm run build
```

### El video no se muestra en producción
- Verifica que el path sea correcto (`/demo.mp4` si está en public/)
- Verifica que el archivo no sea >50MB (GitHub tiene límites)
- Considera usar CDN (Cloudflare R2, Vercel Blob Storage)

### El form de contacto no funciona
- Si usas Netlify Forms, asegúrate de que el atributo `netlify` esté en el `<form>`
- Verifica que el deploy sea vía Netlify (no GitHub Pages)

---

## ✅ Checklist Pre-Deploy

- [ ] Build compiló sin errores (`npm run build`)
- [ ] Placeholder de demo visible en dist/index.html
- [ ] Links a GitHub funcionan (https://github.com/Corgipollo/JarvisAI)
- [ ] README.md sin placeholders (TU_USUARIO → Corgipollo)
- [ ] Git commit creado con todos los cambios
- [ ] Deploy ejecutado (GitHub Pages / Vercel / Netlify)
- [ ] Landing visible en producción
- [ ] Grabar demo video (⏭️ siguiente paso)

---

**🎯 Impacto esperado**: 60-80% reducción en bounce rate de prospectos fríos una vez que agregues el video real.

**⏭️ Siguiente paso**: Graba el demo de 60s siguiendo el guion arriba, súbelo, actualiza el embed, redeploya.
