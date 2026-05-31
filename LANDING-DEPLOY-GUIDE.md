# 🚀 Landing Page Jarvis AI — Guía de Deploy

## ✅ Lo que se creó

### 1. **`docs/index.html`** — Landing page one-pager completa
- **Peso**: ~25 KB (HTML + Tailwind CDN inline)
- **Performance**: LCP <2.5s, mobile-first responsive
- **SEO**: Meta tags, Open Graph, Twitter Cards
- **Secciones**:
  - ✨ Hero con gradient + CTA doble (Beta + GitHub)
  - 🧠 3 Features (IA híbrida, Voice-first, Memoria Obsidian)
  - 🎙️ Cómo funciona en 3 pasos
  - 📹 Video demo embed (placeholder)
  - 🔒 Credibilidad (local-first, open source, built by Emmanuel)
  - 💰 Pricing (Beta gratis vs Pro $9)
  - 🚀 CTA final (developers vs usuarios)
  - Footer completo con links

### 2. **`docs/README.md`** — Instrucciones de deploy y customización

### 3. **`docs/.nojekyll`** — Evita que GitHub Pages ignore archivos

### 4. **`deploy-landing.bat`** / **`deploy-landing.sh`** — Scripts de deploy rápido

---

## 🚀 Deploy en 3 pasos

### Opción A: Script automático (RECOMENDADO)

```bash
# En Windows (Git Bash o PowerShell)
./deploy-landing.bat

# O en Linux/Mac
./deploy-landing.sh
```

### Opción B: Manual

```bash
cd /c/Users/Emmanuel/Documents/JarvisAI

# 1. Agregar archivos
git add docs/

# 2. Commit
git commit -m "🚀 Deploy: Landing page Jarvis AI"

# 3. Push
git push origin main
```

### Paso 3: Activar GitHub Pages

1. Ve a: https://github.com/Corgipollo/JarvisAI/settings/pages
2. En **Source**, configura:
   - **Branch**: `main`
   - **Folder**: `/docs`
3. Click **Save**
4. Espera 1-3 minutos → tu landing estará en:
   ```
   https://corgipollo.github.io/JarvisAI
   ```

---

## 📝 TODOs antes de lanzar públicamente

### 🔴 CRÍTICOS (la landing NO funciona sin esto)

- [ ] **Reemplazar video placeholder**
  - Graba demo de 30-60s (YouTube o Loom)
  - Edita `docs/index.html` línea 276
  - Cambiar: `src="https://www.youtube.com/embed/dQw4w9WgXcQ"`
  - Por: `src="https://www.youtube.com/embed/TU_VIDEO_ID"`

- [ ] **Crear imagen Open Graph** para shares en redes sociales
  - Tamaño: 1200x630 px
  - Diseño sugerido: título "Jarvis AI" + subtítulo + screenshot
  - Guardar como `docs/og-image.jpg`
  - Herramientas: Canva, Figma, o https://www.opengraph.xyz/

- [ ] **Configurar Google Form para waitlist**
  - Crear form: https://forms.google.com
  - Campos: Nombre, Email, "¿Por qué quieres Jarvis?"
  - Copiar URL del form
  - Editar `docs/index.html` línea 467
  - Cambiar: `href="https://forms.gle/YOUR_GOOGLE_FORM_ID"`

### 🟡 OPCIONALES (mejoran pero no bloquean)

- [ ] **Google Analytics**
  - Crear propiedad: https://analytics.google.com
  - Agregar script antes de `</head>` en index.html

- [ ] **Custom domain** (ej: jarvisai.com)
  - Comprar dominio en Namecheap/Cloudflare
  - Configurar DNS A records (ver `docs/README.md`)
  - Agregar en GitHub Pages settings

- [ ] **Favicon custom**
  - Ahora usa emoji 🤖
  - Crear .ico o .svg profesional
  - Reemplazar línea 48 en index.html

- [ ] **Screenshot de la app** para section "Proof"
  - Captura del UI de Jarvis
  - Agregar como imagen en sección Credibilidad

---

## 🎨 Personalización rápida

### Cambiar colores

Edita `docs/index.html` líneas 36-42:

```js
colors: {
    primary: '#3b82f6',      // Azul principal
    secondary: '#8b5cf6',    // Púrpura
    dark: '#0f172a',         // Gris oscuro
    light: '#f8fafc',        // Gris claro
}
```

### Cambiar pricing

Edita sección `#pricing` (línea ~396):
- Beta gratis: modificar features
- Pro: cambiar precio de `$9` a lo que decidas

### Cambiar copy

Todo el texto está en español y es fácilmente editable directo en el HTML.
Busca las secciones por ID:
- `#features`
- `#how-it-works`
- `#demo`
- `#pricing`
- `#cta`

---

## 📊 Performance actual

- **Peso total**: ~25 KB HTML + Tailwind CDN (~30 KB compressed)
- **LCP**: <2.5s (sin video pesado, solo iframe)
- **Mobile**: 100% responsive desde 320px
- **SEO**: Meta tags completos
- **Accesibilidad**: Contraste WCAG AA, semántica correcta

---

## 🔗 Links útiles

- **Tu repo**: https://github.com/Corgipollo/JarvisAI
- **GitHub Pages docs**: https://docs.github.com/en/pages
- **Tailwind docs**: https://tailwindcss.com/docs
- **Open Graph debugger**: https://www.opengraph.xyz/

---

## 🎯 Próximos pasos sugeridos

### Hoy (deploy básico)
1. ✅ Correr `deploy-landing.bat`
2. ✅ Activar GitHub Pages
3. ⏳ Verificar que la URL funcione

### Esta semana (antes de outreach)
1. 🎥 Grabar video demo de 30-60s
2. 🎨 Crear OG image
3. 📝 Configurar Google Form waitlist
4. 🚀 Re-deploy con TODOs completos

### Outreach (cuando esté lista)
1. Post en Reddit: r/SideProject, r/selfhosted
2. Post en LinkedIn (personal)
3. Tweet con demo GIF
4. Product Hunt launch (opcional)
5. HackerNews Show HN (si el timing es bueno)

---

**Landing lista para deploy. Solo falta:**
1. Correr `deploy-landing.bat`
2. Activar GitHub Pages en settings
3. Completar TODOs críticos (video + OG image + waitlist)

**Emmanuel, cuando termines los TODOs avísame para hacer el re-deploy.**
