---
name: web-builder
description: Use when the user wants to build a website, landing page, blog, docs site, SaaS UI, e-commerce storefront, portfolio, or marketing page. Orchestrates the full pipeline from decision (stack choice) to deploy. Picks the optimal 2026 stack based on use case (Astro for content, Next.js 16 for SaaS, SvelteKit for dashboards, Shopify for e-commerce, Qwik for extreme perf), wires up shadcn/ui + Tailwind v4, enforces Core Web Vitals budget (LCP under 2.5s, INP under 200ms, CLS under 0.1), and hands off to specialized skills (ui-ux-pro-max, react-expert, shopify-expert, ai-seo, a11y-audit) when needed. Trigger phrases include "haz una web", "landing page", "sitio web", "crea un website", "portfolio", "SaaS UI", "storefront", or "blog nuevo".
---

# Web Builder — Orquestador de construccion de sitios web

> Skill para decidir el stack optimo 2026 y orquestar la construccion end-to-end.
> NO duplica a `ui-ux-pro-max` / `react-expert` / `shopify-expert` — las usa como sub-herramientas.

## Cuando activar

- "haz una web para {X}"
- "landing page de {producto}"
- "sitio web para {cliente/nicho}"
- "blog nuevo en {tema}"
- "portfolio", "SaaS UI", "dashboard", "storefront"
- "clonar {sitio}" (con browser-automation)
- "mejora el performance de {sitio}" (Core Web Vitals)

## Fase 1 — Decision Tree del stack (2026)

### Tabla de decision

| Tipo de sitio | Stack recomendado | Por que | Deploy |
|---|---|---|---|
| **Landing page** (1-5 paginas, estatica) | **Astro 5 + Tailwind v4 + shadcn/ui** | Ship minimal JS, mejor SEO, Cloudflare-backed (Jan 2026) | Vercel / Cloudflare Pages |
| **Blog / docs / content site** | **Astro 5** + Content Collections | Static output, marcas con MDX, islands arch | Cloudflare Pages |
| **Marketing site con ads** | **Astro** + Vercel Analytics | Core Web Vitals verde por default | Vercel |
| **SaaS / dashboard / app** | **Next.js 16** + Tailwind v4 + shadcn/ui + TanStack Query | Turbopack GA, PPR GA, ecosystem maduro | Vercel |
| **SaaS minimalista / small team** | **SvelteKit + Svelte 5 runes** | Compile-time, menos JS, DX rapido | Cloudflare Pages |
| **E-commerce custom** | **Next.js 16 + Shopify Storefront API** o **Astro + Shopify** | Ver skill `shopify-expert` | Vercel |
| **E-commerce rapido (sin dev)** | **Shopify + theme custom Liquid** | Ver skill `shopify-expert` para GROP | Shopify CDN |
| **Portfolio personal** | **Astro** (recomendado) o **Next.js** | Astro si es 90% contenido, Next si tiene interactividad | Vercel |
| **Docs tecnico** | **Astro + Starlight** o **Nextra** | Mejores defaults para docs | Cloudflare |
| **Alto performance consumer** | **Qwik** | Resumability, 0 JS initial | Cloudflare / Vercel Edge |
| **Enterprise React data-heavy** | **React Router v7** (ex-Remix) | Nested routes, mutations | Vercel / AWS |
| **Rapid prototype con AI** | **v0 by Vercel** → export Next.js | Generacion UI con AI en minutos | Vercel |
| **Sitio content blazing-fast** | **Hugo** (Go) | Renderiza sitios enormes en segundos | Cloudflare / Netlify |

### Reglas de descarte rapido

- ¿Tiene >5 paginas de contenido? → NO uses Next.js (overhead), usa Astro
- ¿Necesitas SSR con auth/session? → Next.js 16 o SvelteKit, NO Astro static
- ¿Es un dashboard con mucho state? → Next.js o SvelteKit, NO Astro
- ¿E-commerce con inventory real? → Shopify (usa skill `shopify-expert`)
- ¿El cliente no tecnico actualizara contenido? → Agregar un CMS (Sanity / Contentful / TinaCMS)

## Fase 2 — Stack default recomendado (si hay duda)

**El stack "default Emmanuel 2026" para cualquier sitio nuevo:**

```
Framework:    Astro 5 (para content) o Next.js 16 (para app)
Styling:      Tailwind CSS v4 (con @theme directive)
Components:   shadcn/ui (via CLI, Tailwind v4 compatible)
Icons:        lucide-react o heroicons
Forms:        react-hook-form + zod
Fonts:        next/font o @fontsource (variable fonts)
Images:       next/image (Next) o astro:assets (Astro)
Analytics:    Vercel Analytics (free tier) + Plausible (self-host)
SEO:          next-seo o @astrojs/seo + structured data (JSON-LD)
Deploy:       Vercel (default) o Cloudflare Pages (si quieres Cloudflare edge)
CMS opcional: Sanity (headless, free tier) o Markdown en repo
```

## Fase 2.5 — Premium Interactive Tier (Awwwards-style)

> Cuando el usuario dice "premium", "como Apple", "animaciones", "scroll interactivo",
> "3D", "video hero", "Awwwards", "motion", "interactivo profesional" — ACTIVAR este tier.

### Decision: ¿Es tier standard o premium?

| Senal | Tier standard | Tier premium |
|---|---|---|
| Timeline | 1-3 dias | 1-3 semanas |
| Budget | Low/mid | High |
| Target | PyME, lead gen | Brand, producto premium, portfolio creativo |
| Objetivo | Conversion rapida | Wow factor + conversion |
| Core Web Vitals | Verde estricto | Verde pero con INP ~150-180ms tolerable |
| Bundle budget | < 100KB JS | 150-300KB JS aceptable |
| Dispositivo target | Mobile-first | Desktop-hero, mobile-optimizado despues |

### Stack PREMIUM default 2026 (React)

```
Framework:        Next.js 16 (App Router)
Smooth scroll:    Lenis (darkroomengineering) — cinematic scroll
Scroll animation: GSAP + ScrollTrigger — industry standard Awwwards
UI animations:    Motion (ex Framer Motion) — hover, page transitions, layout
3D:               React Three Fiber + Drei (wrapper Three.js para React)
3D animation:     Motion for React Three Fiber
Physics:          React Spring (cuando se necesita fisica natural)
Cursor custom:    blobity o custom con Motion
Video hero:       mux.com (o next-video) con poster + lazy
Loader:           GSAP timeline + blur transition
Page transitions: Motion layout animations + view transitions API
Marquee:          react-fast-marquee o GSAP custom
Text reveal:      SplitText (GSAP club) o split-type (free)
Images:           next/image + blur placeholder
Fonts:            Variable fonts con next/font (1-2 max)
```

### Stack PREMIUM para Astro (content-heavy con animaciones)

```
Framework:        Astro 5 con islands React/Vue
Smooth scroll:    Lenis integrado en layout global
Scroll animation: GSAP + ScrollTrigger (cargado en cliente solo donde se usa)
Micro animations: Motion One (ligero, ex Framer Motion vanilla) o GSAP
3D hero:          Spline embed o React Three Fiber como island
Video hero:       astro-video o raw <video> con lazy + poster
```

### Librerias por caso de uso (triangulado 2026)

| Necesidad | Libreria | Peso | Por que |
|---|---|---|---|
| **Smooth scroll cinematic** | **Lenis** | ~5KB | Standard Awwwards, interpola scroll |
| **Scroll scrubbing** | **GSAP ScrollTrigger** | ~78KB (GSAP) | Industry std, timelines, pinning |
| **UI hover/tap/layout** | **Motion** (ex Framer Motion) | ~85KB | React-native, gran DX, layout animations |
| **3D escenas** | **React Three Fiber + Drei** | ~120KB (R3F) | R3F es wrapper R3F declarativo |
| **3D sin codigo** | **Spline** | embed | Para 3D que no quieres codear |
| **Animaciones de fisica** | **React Spring** | ~40KB | Tension/friction/mass naturales |
| **CSS simple utility** | **Tailwind CSS Motion** | ~5KB | Para fade/slide/scale sin JS |
| **Lottie (JSON)** | **lottie-react** | ~60KB | Cuando el disenador te da Lottie |
| **Canvas 2D custom** | **Konva.js** o **Pixi.js** | varia | Cursor effects, particles |
| **Text split + reveal** | **split-type** (free) o **SplitText** (GSAP club) | ~3KB | Text animations por letra/palabra |
| **Marquee infinito** | **react-fast-marquee** o GSAP custom | ~5KB | Brand tickers, logo scroll |
| **Video premium** | **mux-video** (con mux.com) | streaming | Optimizado, ABR, thumbnails |
| **Video simple** | **next-video** o raw `<video>` | nativo | Poster + lazy + muted autoplay |

### Combos PREMIUM probados (Awwwards-tier)

**Combo 1: Brand + Storytelling**
```
Next.js 16 + Lenis + GSAP ScrollTrigger + Motion + R3F
→ Hero con video fullscreen + text reveal scroll-driven
→ Secciones con pinning + parallax layers
→ 3D scene como accent (R3F + Drei environment)
→ Page transitions con Motion layout
```

**Combo 2: Portfolio creativo**
```
Astro + Lenis + GSAP + Motion islands
→ Grid sticky con animacion scroll-driven
→ Hover effects masivos con Motion
→ Cursor custom trail
→ Marquee de skills + logos
→ Case studies con scroll-scrubbing
```

**Combo 3: SaaS premium (ej Linear, Vercel)**
```
Next.js 16 + Motion + GSAP para hero + R3F accent
→ Hero con mesh 3D interactivo (R3F)
→ Feature sections con scroll-triggered reveals (GSAP)
→ Product demos con Motion layout
→ Marquee de testimonios
→ Dark mode con color scheme API
```

**Combo 4: Landing producto ligera (performance first)**
```
Astro + Tailwind CSS Motion + Lenis + 1 video hero
→ Animaciones CSS puras (sin GSAP para bundle minimo)
→ Scroll suave con Lenis
→ Video hero optimizado (poster + muted + playsinline)
→ Motion One vanilla para micro-interacciones
```

### Pipeline premium adicional

Aparte del pipeline base de 9 pasos, si es tier PREMIUM agregar:

**Paso 3.5 — Moodboard motion**
1. Recoger 3-5 refs de Awwwards / The FWA / CSS Design Awards
2. Listar las tecnicas clave de cada ref (scroll scrub, pinning, 3D hero, etc)
3. Decidir combo de librerias
4. Validar bundle size estimado (< 300KB gzipped)

**Paso 4.5 — Build de componentes interactivos**
1. `<SmoothScroll>` wrapper con Lenis
2. `<RevealOnScroll>` con GSAP ScrollTrigger
3. `<ParallaxLayer>` con Motion o GSAP
4. `<MagneticButton>` con Motion springs
5. `<MarqueeInfinite>` con react-fast-marquee
6. `<VideoHero>` con lazy + poster + muted autoplay
7. `<CursorTrail>` custom
8. `<TextSplit>` con split-type
9. `<PageTransition>` con Motion layout
10. `<Scene3D>` con React Three Fiber (si aplica)

**Paso 6.5 — Performance con animaciones**
Cuidados extra para no romper INP budget:
- Lazy-load GSAP y R3F solo en las rutas que los usan
- `will-change: transform` solo en elementos animados activos
- `contain: layout paint` en contenedores
- Offload a GPU con `translateZ(0)` solo donde necesario
- Nunca animar `width`/`height` — usar `transform: scale()`
- Throttle/debounce scroll handlers
- `prefers-reduced-motion` fallback obligatorio
- Dynamic import de Three.js/R3F (ahorra ~120KB en rutas sin 3D)
- Lighthouse CI con budget de INP < 200ms

**Paso 7.5 — Accesibilidad premium**
- `prefers-reduced-motion: reduce` → desactivar animaciones costosas
- Focus visible en TODOS los elementos interactivos
- Keyboard nav funcional aunque haya scroll hijack
- Alt text en videos decorativos (`aria-hidden="true"` si son puramente visual)
- Anunciar transiciones con `aria-live` si cambian contenido dinamicamente

### Referencias premium 2026 (inspiracion)

- **Awwwards** — awwwards.com/websites/ (filtrar por Site of the Day)
- **The FWA** — thefwa.com
- **CSS Design Awards** — cssdesignawards.com
- **Codrops** — tympanus.net/codrops/ (tutoriales scroll-driven con GSAP)
- **Codepen** — codepen.io (colecciones GSAP/Motion/R3F)

### Anti-patterns PREMIUM (nunca hacer)

- Autoplay de video con sonido (browsers lo bloquean)
- Scroll hijack sin opt-out (mata UX en mobile y accesibilidad)
- Loaders infinitos mientras pre-cargan assets (user abandona >3s)
- Animaciones sin `prefers-reduced-motion` fallback
- R3F con modelos >5MB sin compresion (draco, meshopt)
- GSAP cargado en todas las rutas sin code-splitting
- Video hero sin poster (flash of unstyled content)
- Mobile con las mismas animaciones pesadas que desktop
- Scroll snap + Lenis sin sincronizar (pelean entre si)
- Deploy sin validar en Lighthouse mobile (desktop puede verse bien, mobile no)

## Fase 3 — Pipeline end-to-end

### Paso 1: Discovery (invocar skill `ui-ux-pro-max` si aplica)
1. Tipo de sitio + audiencia + objetivo de conversion
2. Referencias visuales (moodboard)
3. Brand guidelines (invocar skill `brand-guidelines`)
4. Sitemap basico (Home / Servicios / About / Contacto / Blog)
5. Copy preliminar (invocar skill `content-production` si necesita copy profesional)

### Paso 2: Stack decision
Usar la tabla de arriba. Confirmar con el usuario el stack elegido antes de empezar.

### Paso 3: Scaffold del proyecto
```bash
# Astro
npm create astro@latest -- --template minimal --typescript strict
npx astro add tailwind
npx shadcn@latest init

# Next.js 16
npx create-next-app@latest --typescript --tailwind --app --turbopack
npx shadcn@latest init

# SvelteKit
npm create svelte@latest
npx shadcn-svelte@latest init
```

### Paso 4: Componentes base
1. Layout + Header + Footer
2. Hero section (con CTA claro)
3. Features / Services grid
4. Testimonials (con Judge.me / manual)
5. CTA final + footer con links legales
6. Forms: Contact / Newsletter (con validacion)

Si es React: **invocar skill `react-expert`** para los componentes.
Si es diseno visual complejo: **invocar skill `ui-ux-pro-max`** para paleta/tipos/estilo.

### Paso 5: Contenido + SEO
- Meta tags en `app/layout.tsx` o `<head>` de Astro
- JSON-LD para LocalBusiness / Product / Article
- Sitemap.xml automatico
- robots.txt
- Open Graph + Twitter cards
- **Invocar skill `ai-seo`** para optimizacion para ChatGPT/Perplexity/Google AI

### Paso 6: Performance budget (Core Web Vitals 2026)
Targets obligatorios:
- **LCP ≤ 2.5s** (img preload + critical CSS inline + SSR/SSG)
- **INP ≤ 200ms** (evitar JS bloqueante, code splitting, web workers para tareas pesadas)
- **CLS ≤ 0.1** (width/height en TODAS las img/video/iframe/ads)

Checklist:
- [ ] `next/image` o `astro:assets` en todas las imagenes
- [ ] Fuentes con `font-display: swap` + preload
- [ ] Critical CSS inline
- [ ] Lazy load de todo lo below-the-fold
- [ ] No bloquear main thread con scripts de terceros (analytics con `strategy="lazyOnload"`)
- [ ] Lighthouse CI en GitHub Actions

### Paso 7: Accesibilidad
**Invocar skill `a11y-audit`** al final. Checklist rapida:
- [ ] Heading hierarchy correcta (solo un h1, luego h2, h3, ...)
- [ ] Alt text en todas las imagenes
- [ ] Aria labels en botones sin texto
- [ ] Contraste >=4.5:1 (WCAG AA)
- [ ] Keyboard navigable (tab order)
- [ ] Focus visible

### Paso 8: Deploy
```bash
# Vercel (default)
npx vercel --prod

# Cloudflare Pages
npx wrangler pages deploy ./dist

# Netlify
npx netlify deploy --prod
```

### Paso 9: Post-deploy
- [ ] Probar en PageSpeed Insights (field data, no solo Lighthouse)
- [ ] Configurar Google Search Console + submit sitemap
- [ ] Configurar analytics (Vercel Analytics o Plausible)
- [ ] Screenshot + test en mobile/tablet/desktop (usar skill `playwright-expert`)
- [ ] Guardar el proyecto en el vault: `01-Proyectos/Agencia-Websites/{cliente}/`

## Fase 4 — Integracion con el ecosistema de Emmanuel

### Si es proyecto Agencia Websites (PyMEs Mexico)
→ Usar agente `agencia-websites` en paralelo
→ Guardar en `01-Proyectos/Agencia-Websites/Templates/{nicho}/`
→ Aplicar templates ya testeados para fumigadores, barberias, etc.

### Si es para GROP Ecommerce
→ NO usar web-builder, usar skill `shopify-expert` + agente `grop-ecommerce`
→ Theme Liquid custom, no framework JS

### Si es sitio personal de Emmanuel
→ Stack: Astro + Tailwind v4 + deploy Cloudflare Pages
→ Guardar en `01-Proyectos/Personal/`

## Reglas anti-basura

- **Nunca** recomendar Create React App (deprecated)
- **Nunca** recomendar Gatsby (stalled since 2023)
- **Nunca** empezar sin Tailwind (es estandar de facto)
- **Nunca** usar CSS-in-JS runtime-heavy (styled-components) — usar Tailwind o vanilla CSS
- **Nunca** omitir el performance budget
- **Nunca** deployar sin validar LCP/INP/CLS con PageSpeed Insights
- **Nunca** skipear accesibilidad — es legal requirement en muchos paises

## Fuentes que informan esta skill

1. https://naturaily.com/blog/best-nextjs-alternatives (comparativa frameworks 2026)
2. https://dev.to/pockit_tools/nextjs-vs-remix-vs-astro-vs-sveltekit-in-2026-the-definitive-framework-decision-guide (decision guide)
3. https://shadcnspace.com/blog/build-shadcn-landing-page (shadcn landing 2026)
4. https://www.digitalapplied.com/blog/core-web-vitals-2026-inp-lcp-cls-optimization-guide (CWV budgets)
5. https://thebcms.com/blog/nextjs-alternatives (frameworks quietly outperforming Next)

## Output format cuando se usa

```markdown
# Website: {nombre}

**Stack elegido**: {framework} + Tailwind v4 + shadcn/ui
**Por que**: {razon en 2 lineas}
**Deploy**: {Vercel / Cloudflare / Netlify}

## Plan (7 pasos)
1. Scaffold con ...
2. Layout + Header/Footer
3. Hero + Features
4. Contenido + SEO
5. Performance budget
6. Accesibilidad
7. Deploy + test

## Siguientes skills a invocar
- `ui-ux-pro-max` para {X}
- `react-expert` para {Y}
- `ai-seo` para {Z}
- `a11y-audit` al final
```

---

# ALL-IN PREMIUM — Catalogo expandido (2026 Q2)

> Esta seccion es la version EXPANDIDA del tier premium con TODO: imagenes,
> video, animaciones, 3D, cursor, easings, choreography, prefabs, APIs nativas.
> Triangulado de 5+ fuentes 2026.

## A. Imagenes premium — pipeline completo

### Stack default imagenes 2026

```
Hosting:        Cloudinary (free tier 25GB) o Vercel Image Optimization
Component:      next/image (Next.js) o astro:assets (Astro)
Format:         AVIF > WebP > JPG (chain)
Placeholder:    LQIP (Low Quality Image Placeholder) o blurDataURL
Sizes:          srcSet completo para responsive (320, 640, 1024, 1920, 3840)
Loading:        eager para hero (above-fold), lazy para todo lo demas
Decoding:       async siempre
Priority:       priority={true} en hero LCP
```

### Cloudinary integracion (recomendado)

```bash
npm install next-cloudinary
```

```jsx
import { CldImage } from 'next-cloudinary';

// Hero LCP — eager + priority
<CldImage
  src="hero/banner-cinematic"
  width={1920}
  height={1080}
  alt="..."
  priority
  sizes="100vw"
  format="auto"
  quality="auto"
  placeholder="blur"
  blurDataURL="data:image/jpeg;base64,..."
/>

// Below-fold — lazy
<CldImage
  src="gallery/img-1"
  width={800}
  height={600}
  loading="lazy"
  format="auto"
  quality="auto"
/>
```

### Reglas no negociables imagenes

1. **NUNCA** lazy-loadear el LCP (matas el LCP score)
2. **SIEMPRE** definir width + height (evita CLS)
3. **SIEMPRE** alt text (a11y + SEO)
4. **Convertir a AVIF/WebP** automaticamente (next/image lo hace)
5. **Trigger pre-fetch a 500px del viewport** (no en el viewport exacto)
6. **Reservar espacio** con bg color o LQIP para evitar layout shift
7. **Hero <300KB** despues de comprimir (sino el LCP sufre)

## B. Video premium — pipeline completo

### Stack default video 2026

```
Hosting:        mux.com (default premium) o Cloudinary Video
Component:      <MuxPlayer> (React/Next) o next-video
Streaming:      HLS adaptive bitrate (mux lo hace solo)
Hero:           muted + autoplay + playsinline + loop + poster
Lazy load:      react-intersection-observer para below-fold
LCP:            Si el video es LCP, NO lazy-load. Poster debe ser <100KB
```

### Mux integracion (premium streaming)

```bash
npm install @mux/mux-player-react @mux/mux-uploader-react
```

```jsx
import MuxPlayer from "@mux/mux-player-react";

// Hero video con poster optimizado
<MuxPlayer
  playbackId="abc123"
  metadata={{ video_title: "Hero" }}
  autoPlay
  muted
  loop
  playsInline
  poster="https://image.mux.com/abc123/thumbnail.webp?width=1920"
  style={{ aspectRatio: "16/9" }}
/>
```

### Lazy video pattern (below-fold)

```jsx
import { useInView } from 'react-intersection-observer';

function LazyVideo({ src, poster }) {
  const { ref, inView } = useInView({ triggerOnce: true, rootMargin: '500px' });

  return (
    <div ref={ref} style={{ aspectRatio: '16/9' }}>
      {inView ? (
        <video src={src} muted loop playsInline poster={poster} />
      ) : (
        <img src={poster} alt="" />
      )}
    </div>
  );
}
```

### Reglas no negociables video

1. **Hero video debe ser MUTED** (sino los browsers lo bloquean)
2. **playsInline** obligatorio (sino pantalla completa en iOS)
3. **Poster optimizado** (<100KB, primer frame del video)
4. **Comprimir** con HandBrake/ffmpeg antes de subir (target: 1080p H.264 5Mbps max)
5. **Mux** para premium (auto ABR, thumbnails, analytics)
6. **next-video** para self-host simple
7. **NUNCA** video con sonido autoplay (UX terrible + bloqueo)

## C. Animaciones de scroll — catalogo completo

### Patrones de scroll triangulados 2026

| Patron | Tecnica | Lib principal | Ejemplo |
|---|---|---|---|
| **Pinned Mask Reveal** | Sticky + clip-path animado | GSAP ScrollTrigger | M-Trust Co (Awwwards SOTD) |
| **Dynamic Marquee Frame** | Borde con texto en movimiento que cambia con seccion | GSAP custom | Codrops 2026 |
| **Sticky Grid Scroll** | Grid CSS sticky + scroll progress | GSAP + CSS sticky | Codrops marzo 2026 |
| **Jungle Leaves Reveal** | Layers SVG con parallax al scroll | Lenis + GSAP | Codrops |
| **Split-Screen Scroll** | 2 columnas que scrollean a velocidades distintas | GSAP ScrollTrigger | Apple iPhone pages |
| **Text Reveal por palabra/letra** | Split text + scroll progress | split-type + GSAP | Linear, Vercel |
| **Counter Animation** | Numeros que cuentan al entrar viewport | Motion useScroll | Stripe metrics |
| **Image Sequence Scroll** | Scrubbing de PNG sequence con scroll | GSAP ScrollTrigger | Apple AirPods |
| **Parallax Multi-Layer** | 3+ capas a velocidades distintas | GSAP o CSS scroll API | Codrops |
| **Pinning + Horizontal Scroll** | Pin verticalmente, scroll horizontal | GSAP ScrollTrigger | Pinterest stories |
| **Sticky Header Morph** | Header que cambia tamaño al scroll | Motion + Intersection Observer | Linear |
| **Page Transition con View Transitions API** | Native browser API | View Transitions API | Astro 5 native |

### React Kino — componentes prefab

```bash
npm install react-kino
```

Componentes:
- `<Scene>` — wrapper de seccion scroll
- `<Reveal>` — fade/slide al entrar
- `<ScrollTransform>` — transform scrubbing
- `<Parallax>` — multi-layer
- `<Counter>` — numero animado
- `<StickyHeader>` — header sticky con morph
- `<Marquee>` — infinite scroll horizontal
- `<TextReveal>` — word/char/line by line con scroll progress

### Aceternity UI — componentes premium gratis

```bash
# No es paquete npm, son snippets para copiar
# https://ui.aceternity.com/components
```

Top componentes premium:
- **Sticky Scroll Reveal** — perfecto para feature sections con visual + texto
- **Background Beams** — laser beams animadas como Linear
- **Spotlight** — luz follow-mouse cinematica
- **Hero Highlight** — texto con highlight animado
- **3D Card Effect** — tilt 3D al hover
- **Wavy Background** — fondo SVG ondulado animado
- **Floating Navbar** — navbar que aparece/desaparece al scroll
- **Tracing Beam** — linea SVG que sigue el scroll por la pagina

### Scroll-Driven Animations API (nativa, sin JS)

Soporte: Chrome, Edge, Opera (Q2 2026). Firefox detras de flag.

```css
@keyframes fade-in {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

.section {
  animation: fade-in linear;
  animation-timeline: view();
  animation-range: entry 0% cover 30%;
}
```

**Ventaja**: 0 JS, corre en compositor thread, INP no se afecta.
**Desventaja**: No funciona en Safari/iOS (Q2 2026).
**Usar**: como progressive enhancement con fallback Motion/GSAP para Safari.

## D. 3D web — catalogo completo

### Decision tree 3D

| Necesidad | Tool | Por que |
|---|---|---|
| **3D simple, sin codigo** | **Spline** | Browser-based, exporta a embed |
| **3D React complejo** | **R3F + Drei** | Wrapper React de Three.js, declarativo |
| **3D vanilla pro** | **Three.js puro** | Control total, mas verbose |
| **Animaciones 2D interactivas** | **Rive** | State machines con triggers |
| **Animaciones JSON simples** | **Lottie** | Formato standard, 60% mas chico que GIF |
| **Particles + WebGL custom** | **OGL** o **Three.js shader** | Mas ligero que Three full |

### Spline — para 3D rapido sin codear

```html
<!-- Embed directo del visor de Spline -->
<iframe
  src="https://my.spline.design/scene-id/"
  frameBorder="0"
  width="100%"
  height="100%">
</iframe>
```

```jsx
// O como React component
import Spline from '@splinetool/react-spline';
<Spline scene="https://prod.spline.design/scene/scene.splinecode" />
```

### React Three Fiber + Drei — el combo standard React 3D

```bash
npm install three @react-three/fiber @react-three/drei
```

```jsx
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Environment, PerspectiveCamera, Float, Center, Text3D } from '@react-three/drei';

<Canvas dpr={[1, 2]}>
  <PerspectiveCamera makeDefault position={[0, 0, 5]} />
  <Environment preset="studio" />
  <Float speed={2} rotationIntensity={1} floatIntensity={2}>
    <Center>
      <Text3D font="/fonts/inter_bold.json" size={1} height={0.2}>
        GROP
        <meshStandardMaterial color="#C5A882" metalness={0.8} roughness={0.2} />
      </Text3D>
    </Center>
  </Float>
  <OrbitControls enableZoom={false} />
</Canvas>
```

### Rive — para state machines interactivos

```bash
npm install @rive-app/react-canvas
```

```jsx
import { useRive } from '@rive-app/react-canvas';

function InteractiveLogo() {
  const { rive, RiveComponent } = useRive({
    src: '/animations/logo.riv',
    stateMachines: 'State Machine 1',
    autoplay: true,
  });

  return <RiveComponent onMouseEnter={() => rive?.play('hover')} />;
}
```

### Lottie — para JSON exportadas de After Effects

```bash
npm install lottie-react
```

```jsx
import Lottie from 'lottie-react';
import animationData from './loading.json';

<Lottie animationData={animationData} loop autoplay />
```

**Cuando usar cada uno**:
- Solo play once → **Lottie**
- Reaccionar a mouse/scroll/state → **Rive**
- Objeto 3D real con luces y materiales → **Spline o R3F**
- Particles, shaders, generative art → **Three.js puro o R3F**

## E. Cursor effects — catalogo

### Libreria todo-en-uno: mouse-animations

```bash
npm install mouse-animations
```

7 efectos built-in:
1. **Trail** — trail con N steps siguiendo el mouse
2. **Ripple** — ondas al click
3. **CustomCursor** — reemplazo del cursor default
4. **Magnetic** — elementos que "atraen" el cursor cerca
5. **Particles** — particulas que siguen el mouse
6. **Parallax** — elementos que se mueven con el mouse
7. **Tilt** — tilt 3D al hover

```jsx
import { MouseAnimations } from 'mouse-animations';

new MouseAnimations({
  effect: 'trail',
  trailLength: 12,
  trailColor: '#C5A882',
});
```

### Motion Custom Cursor (React idiomatic)

```jsx
import { motion, useMotionValue, useSpring } from 'motion/react';

function CustomCursor() {
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const springX = useSpring(x, { stiffness: 200, damping: 20 });
  const springY = useSpring(y, { stiffness: 200, damping: 20 });

  useEffect(() => {
    const handler = (e) => { x.set(e.clientX); y.set(e.clientY); };
    window.addEventListener('mousemove', handler);
    return () => window.removeEventListener('mousemove', handler);
  }, []);

  return (
    <motion.div
      style={{ x: springX, y: springY }}
      className="fixed top-0 left-0 w-8 h-8 bg-arena rounded-full pointer-events-none mix-blend-difference"
    />
  );
}
```

### Magnetic button (premium effect)

```jsx
function MagneticButton({ children, strength = 30 }) {
  const ref = useRef(null);
  const [pos, setPos] = useState({ x: 0, y: 0 });

  const handleMove = (e) => {
    const rect = ref.current.getBoundingClientRect();
    const x = (e.clientX - rect.left - rect.width / 2) / strength;
    const y = (e.clientY - rect.top - rect.height / 2) / strength;
    setPos({ x, y });
  };

  return (
    <motion.button
      ref={ref}
      onMouseMove={handleMove}
      onMouseLeave={() => setPos({ x: 0, y: 0 })}
      animate={pos}
      transition={{ type: 'spring', stiffness: 150, damping: 15 }}
    >
      {children}
    </motion.button>
  );
}
```

## F. Easings y choreography — la diferencia entre amateur y Awwwards

### Easings premium (no usar `linear` ni `ease`)

```js
// GSAP
gsap.to(el, { x: 100, ease: "power3.out", duration: 1.2 });

// Motion
<motion.div animate={{ x: 100 }} transition={{ ease: [0.22, 1, 0.36, 1], duration: 1.2 }} />
```

| Easing | Cuando |
|---|---|
| `power3.out` / `[0.22, 1, 0.36, 1]` | Default para entradas (decelerate) |
| `power4.inOut` / `[0.83, 0, 0.17, 1]` | Movimientos cinematicos largos |
| `expo.out` / `[0.16, 1, 0.3, 1]` | Snap rapido al final |
| `back.out(1.7)` / spring | Bounce sutil al final |
| `circ.inOut` | Movimientos curvos suaves |
| **NUNCA** `linear` (excepto loops infinitos como marquee) |

### Choreography (timing entre elementos)

Award-winning sites NO animan todo a la vez. **Stagger**:

```jsx
// Motion stagger
<motion.ul variants={{ visible: { transition: { staggerChildren: 0.08 } } }}>
  {items.map(i => (
    <motion.li variants={{ hidden: { y: 20, opacity: 0 }, visible: { y: 0, opacity: 1 } }} />
  ))}
</motion.ul>

// GSAP stagger
gsap.from(".item", { y: 20, opacity: 0, duration: 0.8, stagger: 0.08, ease: "power3.out" });
```

### Reglas de duracion

| Tipo | Duracion |
|---|---|
| Hover micro | 150-250ms |
| UI transitions | 300-400ms |
| Reveals scroll | 600-1200ms |
| Hero entrances | 1000-1500ms |
| Page transitions | 600-800ms |

## G. Templates Awwwards-tier para arrancar

### Repos prefab (clonar y customizar)

| Template | Stack | Para |
|---|---|---|
| [Fullstack-Empire/GSAP-Awwwards-Website](https://github.com/Fullstack-Empire/GSAP-Awwwards-Website) | React + GSAP + Tailwind | Tutorial completo de un site SOTD |
| [shadcnstudio.com](https://shadcnstudio.com/) | shadcn/ui + Tailwind v4 | Library de blocks premium |
| [aceternity ui](https://ui.aceternity.com/) | React + Motion + Tailwind | Snippets premium copy-paste |
| [Codrops tutorials](https://tympanus.net/codrops/) | varios | Tecnicas individuales con codigo |
| [madewithgsap.com](https://madewithgsap.com/) | varios | Inspiracion de sites con GSAP |

## H. Anti-patterns PREMIUM (lista completa)

| Error | Por que es malo | Fix |
|---|---|---|
| Lazy-load del hero LCP | Mata LCP score | `priority={true}` en hero img |
| Video sin poster | FOUC + LCP terrible | `<video poster="..." />` |
| Autoplay con sonido | Browser bloquea + UX terrible | Solo `muted autoplay` |
| Scroll hijack sin opt-out | Mata mobile + a11y | Lenis con `lerp: 0.1` y respeta normal scroll |
| GSAP en bundle global | +78KB en rutas que no lo usan | Dynamic import por ruta |
| R3F sin Suspense | Block render | `<Suspense fallback={<Loader/>}>` siempre |
| Modelos 3D sin compresion | >5MB por modelo | Draco + meshopt compression |
| Sin `prefers-reduced-motion` | A11y fail | Media query + opt-out |
| Animaciones de `width`/`height` | Reflow caro, bloquea main thread | `transform: scale()` |
| `will-change: *` siempre | Memoria GPU desperdiciada | Solo en elementos animados activos |
| Lottie >500KB | Bundle pesado | Convertir a Rive (60% mas chico) |
| Marquee con setInterval | Salta frames | `requestAnimationFrame` o CSS pure |
| 30+ Three.js objects sin instancing | FPS muere | `<Instances>` de Drei |

## I. Performance budget premium

```
LCP:    < 2.0s  (premium quiere mejor que el 2.5s standard)
INP:    < 150ms (premium quiere mejor que 200ms)
CLS:    < 0.05  (premium quiere mejor que 0.1)
JS:     < 250KB gzipped  (con GSAP+Motion+R3F casi llegas al limite)
CSS:    < 50KB gzipped
Imgs:   < 2MB total above-fold
LCP img: < 200KB
Hero video: < 5MB (1080p H.264 ~5Mbps)
```

### Validar con Lighthouse CI

```yaml
# .github/workflows/lighthouse.yml
- name: Lighthouse CI
  uses: treosh/lighthouse-ci-action@v10
  with:
    urls: |
      https://staging.example.com/
    budgetPath: ./lighthouse-budget.json
    uploadArtifacts: true
```

## J. Pipeline ALL-IN (cuando el cliente quiere TODO)

1. **Discovery**: refs Awwwards + moodboard motion + brand
2. **Stack**: Next.js 16 + Lenis + GSAP + Motion + R3F + Cloudinary + Mux
3. **Scaffold**: `npx create-next-app` + agregar todas las libs
4. **Layouts**: `<SmoothScroll>` global con Lenis, `<PageTransition>` con Motion
5. **Hero**: video Mux + text reveal GSAP + 3D accent R3F (Float + Environment)
6. **Sections**:
   - Sticky scroll reveal (Aceternity)
   - Pinning + parallax (GSAP)
   - Marquee infinito (CSS o GSAP)
   - Counter al entrar viewport (Motion)
   - 3D product showcase (R3F + Drei)
7. **Cursor**: custom Motion + magnetic en CTAs
8. **Imagenes**: Cloudinary con LQIP + AVIF/WebP + priority en hero
9. **Footer**: marquee de logos + Wavy Background
10. **Performance**: dynamic imports, code split por ruta, Lighthouse CI
11. **A11y**: `prefers-reduced-motion` fallback en TODO
12. **Deploy**: Vercel + analytics + Speed Insights
13. **Post-deploy**: Lighthouse mobile + PageSpeed field data + screenshots

## J-bis. INSIGHTS DE VIDEOS Y REPOS REALES (transcribed/fetched 2026-04-08)

### MindStudio guide — Animated 3D websites con Claude Code (workflow completo)

**Stack ganador 2026 (probado en produccion)**:
```
GSAP ScrollTrigger (industria standard)
+ CSS 3D Transforms (80% impacto, 20% complejidad)
+ Three.js opcional (solo si necesitas geometria 3D real)
```

**Workflow paso a paso**:

1. **Genera VIDEOS PRIMERO, despues codeas** (al reves de lo intuitivo)
   - El video define el color palette + tipografia + mood del sitio
   - Asi Claude Code puede usar los colores del video como brand

2. **Prompt pro para video AI** (Runway Gen-4 / Sora / Kling):
   - Mal: "Abstract 3D animation"
   - Bien: "Slow-moving dark blue and violet fluid geometry, smooth looping motion, cinematic depth of field, soft volumetric lighting, 16:9 cinematic aspect ratio"

3. **Comprime con HandBrake/FFmpeg a <5MB** antes de embed
   - 1080p H.264 ~3-5 Mbps
   - Mux/Cloudinary lo hacen automatico si subes ahi

4. **Prompt template para Claude Code**:
   ```
   Build a landing page with:
   - Hero: full-screen video background (autoplay muted loop playsinline)
   - 3 feature cards: fade in + slide up 40px, staggered 0.15s, on scroll into view
   - Pinned section: pin for 300vh scroll distance, animate 3 steps sequentially
   - 3D tilt on hover: mouse tracking, rotate 15deg max, with specular highlight
   - Footer: marquee of logos, infinite loop
   Use GSAP + ScrollTrigger, vanilla HTML/CSS/JS, no React.
   Add prefers-reduced-motion fallback for all animations.
   ```

5. **Refinement prompts** (uno por uno, no todo junto):
   - "Make the feature cards fade in 40px below and stagger by 0.15s"
   - "Pin the hero for 300vh and reveal the 3 sub-sections one by one"
   - "Add mouse-tracking 3D tilt up to 15deg with specular highlight"

6. **Performance no negociable**:
   - `will-change: transform, opacity` en elementos animados activos
   - Test Three.js en mobile, fallback estatico si baja de 30fps
   - Video <5MB
   - `prefers-reduced-motion`: video se reemplaza por poster

7. **Costo total**: ~$5-9 (Claude tokens + AI video credits)
8. **Tiempo total**: 1 tarde (video 30-60min + scaffold 5-15min + refinement 1-3h)

### GreenSock GSAP Skills oficiales (8 skills, instalables via `npx skills add`)

GreenSock publico **AI skills oficiales** para que coding agents usen GSAP correctamente. Son compatibles con Claude Code, Cursor, Copilot, Cline, etc.

| Skill | Que cubre |
|---|---|
| `gsap-core` | API base: `to/from/fromTo`, easing, duration, stagger, defaults |
| `gsap-timeline` | Sequencing, position parameters, labels, nesting, playback control |
| `gsap-scrolltrigger` | Scroll-linked animations, pinning, scrub, triggers, refresh, cleanup |
| `gsap-plugins` | ScrollToPlugin, Flip, Draggable, SplitText, Physics2D, etc |
| `gsap-utils` | clamp, mapRange, interpolate, snap, toArray |
| `gsap-react` | useGSAP hook, context, cleanup en React |
| `gsap-performance` | Transforms over layout properties, will-change correcto |
| `gsap-frameworks` | Vue + Svelte integration |

**Instalacion** (cuando quieras integrarlas a Claude Code):
```bash
# Hay 3 vias segun el agent
npx @greensock/gsap-skills add
# o
git clone https://github.com/greensock/gsap-skills ~/.claude/skills/external/gsap
```

### freshtechbro/claudedesignskills (22 skills + 27 plugins)

Skills agrupados por categoria:

**Core 3D & Animation (5)**:
- Three.js/WebGL deep
- GSAP ScrollTrigger
- React Three Fiber
- Framer Motion (Motion)
- Babylon.js (alternativa a Three.js)

**Extended 3D & Scroll (6)**:
- A-Frame / WebXR (VR/AR)
- Vanta effects (backgrounds 3D animados)
- PlayCanvas (motor 3D web)
- PixiJS (2D performant canvas)
- Locomotive Scroll (alternativa a Lenis)
- Barba.js (page transitions)

**Animation & Components (5)**:
- React Spring (physics)
- Magic UI (componentes Awwwards-tier)
- AOS (Animate On Scroll, lib simple)
- Anime.js (alternativa ligera a GSAP)
- Lottie

**3D Authoring & Motion (4)**:
- Blender web pipeline (export glTF optimizado)
- Spline interactive
- Rive
- Substance 3D texturing

**Meta-skills (2)**:
- Web3D integration patterns
- Modern design principles

**50+ slash commands** + **27+ specialized agents** que auto-activan cuando Claude detecta tareas relevantes.

### Builder.io WAC reveal pattern (buttery scroll)

Easing magico que usa Web & Crafts:
```js
ease: "cubic-bezier(.37,.01,0,.98)"
// equivalente GSAP:
ease: CustomEase.create("custom", "M0,0 C0.37,0.01 0,0.98 1,1")
```

Pattern completo:
```js
gsap.timeline({
  scrollTrigger: {
    trigger: ".section",
    start: "top 80%",
    end: "bottom top",
    pin: true,
    scrub: 1.5,
  }
})
.from(".letter", {
  y: 100,
  opacity: 0,
  stagger: 0.04,
  ease: "cubic-bezier(.37,.01,0,.98)",
  duration: 1.2,
})
.from(".bg-video", {
  scale: 1.2,
  opacity: 0,
}, "<");
```

### DesignCourse — Animated Loader con Claude Code + Rive (37min)

Workflow:
1. Disenar el loader en Rive (state machine: idle → loading → success → error)
2. Exportar `.riv`
3. Pedir a Claude Code: "Integrate this Rive file as a global loader, trigger states based on data fetching status with TanStack Query"
4. Claude genera el componente React + hooks + transition
5. GSAP coordina el fade out del loader cuando la pagina monta

### TL;DR de los videos

- **Video first, code second** (el video define la marca)
- **GSAP ScrollTrigger** es el standard absoluto, no hay debate
- **GreenSock tiene skills oficiales** para AI agents — instalalas
- **claudedesignskills** tiene 22 skills mas — clonar el repo si quieres ALL-IN
- **CSS 3D + GSAP > Three.js** para 80% de los casos
- **Rive > Lottie** cuando necesitas estado e interactividad
- **Easing cubic-bezier(.37,.01,0,.98)** es el "buttery WAC" easing
- **prefers-reduced-motion** SIEMPRE como fallback
- **Costo de un sitio premium con AI**: $5-9 + 1 tarde de trabajo

## K. Sources del research (todas trianguladas)

- [awwwards.com/websites/gsap](https://www.awwwards.com/websites/gsap) — sites SOTD con GSAP
- [Lovable — 10 best interactive websites 2026](https://lovable.dev/guides/best-interactive-websites)
- [Codrops](https://tympanus.net/codrops/) — tutoriales scroll-driven 2026
- [GitHub Fullstack-Empire/GSAP-Awwwards-Website](https://github.com/Fullstack-Empire/GSAP-Awwwards-Website)
- [Cloudinary lazy load best practices](https://cloudinary.com/blog/lazy_loading_for_optimal_performance)
- [Next.js videos guide](https://nextjs.org/docs/app/guides/videos)
- [react-kino](https://github.com/btahir/react-kino) — cinematic scroll React
- [Motion React Three Fiber](https://motion.dev/docs/react-three-fiber)
- [Aceternity UI](https://ui.aceternity.com/components)
- [Rive vs Lottie 2026](https://unicornicons.com/learn/rive-vs-lottie)
- [Spline](https://spline.design/) — 3D browser-based
- [mouse-animations library](https://www.jqueryscript.net/animation/cursor-mouse-effects.html)
- [Lovable — Scrolling design patterns 2026](https://lovable.dev/guides/scrolling-designs-patterns-when-to-use)