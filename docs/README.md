# Jarvis AI — Landing Page

Landing page estática one-pager para Jarvis AI.

## 🚀 Deploy en GitHub Pages

### Paso 1: Activar GitHub Pages

1. Ve a tu repo en GitHub: `https://github.com/Corgipollo/JarvisAI`
2. Click en **Settings** (Configuración)
3. Scroll down hasta **Pages** (en el menú lateral izquierdo)
4. En **Source**, selecciona:
   - **Branch**: `main` (o `master`)
   - **Folder**: `/docs`
5. Click en **Save**

### Paso 2: Esperar deploy automático

GitHub Pages desplegará automáticamente en ~1-3 minutos.

Tu landing estará en:
```
https://corgipollo.github.io/JarvisAI
```

### Paso 3: Custom domain (opcional)

Si quieres usar un dominio custom (ej: `jarvisai.com`):

1. Compra el dominio en Namecheap/Cloudflare/GoDaddy
2. Agrega estos DNS records:
   ```
   A     @    185.199.108.153
   A     @    185.199.109.153
   A     @    185.199.110.153
   A     @    185.199.111.153
   CNAME www  corgipollo.github.io
   ```
3. En GitHub Pages settings, agrega tu dominio en **Custom domain**

---

## 📝 TODOs antes de lanzar

- [ ] **Reemplazar video placeholder** con URL real de YouTube/Loom
  - Línea 276 en `index.html`
  - Cambiar `src="https://www.youtube.com/embed/dQw4w9WgXcQ"` por tu video
  
- [ ] **Crear imagen OG (Open Graph)** para shares en redes sociales
  - Tamaño: 1200x630 px
  - Guardar como `docs/og-image.jpg`
  - Diseño: título "Jarvis AI" + subtítulo + screenshot de la app
  
- [ ] **Configurar Google Form para waitlist**
  - Crear form en https://forms.google.com
  - Reemplazar línea 467: `href="https://forms.gle/YOUR_GOOGLE_FORM_ID"`

- [ ] **Agregar Google Analytics** (opcional)
  - Crear propiedad en https://analytics.google.com
  - Agregar script de tracking antes del `</head>`

---

## 🛠️ Personalización

### Colores

Editables en el `tailwind.config` (línea 36-42):

```js
colors: {
    primary: '#3b82f6',      // Azul principal
    secondary: '#8b5cf6',    // Púrpura
    dark: '#0f172a',         // Gris oscuro
    light: '#f8fafc',        // Gris claro
}
```

### Contenido

Todo el texto está en español y es fácilmente editable directo en el HTML.

---

## 📊 Performance

- **Peso total**: ~45 KB (HTML + Tailwind CDN inline)
- **LCP**: <2.5s (sin video pesado)
- **Mobile-first**: responsive desde 320px
- **SEO**: meta tags incluidos

---

## 🔗 Links útiles

- [GitHub Pages Docs](https://docs.github.com/en/pages)
- [Tailwind CSS Docs](https://tailwindcss.com/docs)
- [Open Graph Protocol](https://ogp.me/)
