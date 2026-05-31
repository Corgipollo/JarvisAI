# 📦 Modelo de Entrega — Jarvis AI

> **Documento de decisión técnica**: Tres modelos de distribución para primer cliente de pago

---

## 🎯 Contexto de Decisión

Jarvis AI está listo para su primer cliente de pago. Necesitas decidir **cómo entregar el producto** de forma profesional, segura y escalable.

**Criterios clave**:
- ✅ Instalación simple para cliente (no técnico)
- ✅ Protección de código fuente (propiedad intelectual)
- ✅ Actualizaciones fáciles (bugs, features nuevas)
- ✅ Soporte técnico viable (debugging, logs)
- ✅ Precio sostenible vs esfuerzo de delivery

---

## 📊 Comparativa Rápida

| Criterio | Repo Privado | Binario Empaquetado | Servicio Hosted |
|----------|--------------|---------------------|-----------------|
| **Instalación cliente** | ⚠️ Media (script) | ✅ Muy fácil (installer) | ✅ Inmediata (URL) |
| **Protección IP** | ❌ Código visible | ✅ Código compilado | ✅ Código inaccesible |
| **Actualizaciones** | ✅ Git pull | ⚠️ Nuevo installer | ✅ Transparente |
| **Debugging** | ✅ Logs locales | ⚠️ Logs locales limitados | ✅ Logs centralizados |
| **Escalabilidad** | ❌ 1 cliente = 1 repo | ✅ N clientes | ✅ Multi-tenant |
| **Costo delivery** | Bajo (GitHub) | Medio (build CI/CD) | Alto (infra 24/7) |
| **Precio sugerido** | $150-200/mes | $250-350 one-time o $200/mes | $400-600/mes |
| **Esfuerzo inicial** | 2-4 horas | 8-16 horas | 16-40 horas |
| **Mejor para** | Beta testers, early adopters | Clientes corporativos | Empresas, equipos |

---

## 🔷 Opción 1: Repo Privado GitHub/GitLab

### ¿Cómo funciona?

1. Cliente recibe acceso a repo privado en GitHub/GitLab
2. Clona el repo localmente en su PC Windows
3. Ejecuta `install.ps1` (script automatizado)
4. Configura sus API Keys en `.env`
5. Inicia Jarvis con `START_JARVIS_FULL.bat`

### Ventajas ✅

- **Instalación automatizada**: `install.ps1` hace todo (deps Python, Node, .env)
- **Actualizaciones simples**: `git pull origin main` + reiniciar
- **Debugging fácil**: Cliente puede compartir logs completos (`data/jarvis-service.log`)
- **Costo bajo**: GitHub privado gratis, GitLab free tier permite 5 usuarios
- **Transparencia**: Cliente ve el código (bueno para confianza inicial)

### Desventajas ❌

- **Exposición de código**: Cliente tiene acceso al source completo
- **Riesgo de copia**: Puede clonar y redistribuir (mitigable con licencia + contrato)
- **Dependencia del cliente**: Debe tener Git, Python, Node instalados
- **Soporte técnico**: Clientes no técnicos pueden tener problemas con Git

### Stack Técnico

```bash
# Estructura de entrega
GitHub Privado (repo)
  ├── README.md (instalación)
  ├── install.ps1 (automatización)
  ├── backend/ (Python + FastAPI)
  ├── frontend/ (Electron + React)
  ├── .env.example (template configuración)
  └── START_JARVIS_FULL.bat (launcher)
```

### Precio Sugerido

- **Mensual**: $150-200/mes (incluye actualizaciones + soporte básico)
- **Anual**: $1,500-1,800/año (2 meses gratis)
- **Contrato**: Licencia de uso exclusivo, no redistribución

### Esfuerzo de Implementación

| Tarea | Tiempo |
|-------|--------|
| Limpiar repo (eliminar archivos sensibles) | 1h |
| Escribir README.md completo | 1h |
| Crear install.ps1 | 1h |
| Configurar repo privado GitHub | 30min |
| Agregar cliente como colaborador | 10min |
| Sesión de onboarding (video call) | 1h |
| **TOTAL** | **4.5h** |

### Cuándo elegir esta opción

✅ **Cliente es early adopter** técnico (startup, dev freelance)  
✅ **Necesitas feedback rápido** sobre features/bugs  
✅ **Quieres construir confianza** mostrando código  
✅ **Presupuesto del cliente es limitado** ($150-200/mes)  

---

## 🔷 Opción 2: Binario Empaquetado (Electron + PyInstaller)

### ¿Cómo funciona?

1. Compilas backend (PyInstaller) + frontend (Electron Builder) en un **installer único**
2. Cliente descarga `JarvisAI-Setup-v1.0.0.exe` (firmado digitalmente)
3. Doble clic → instalación wizard (Next, Next, Install)
4. Jarvis se instala en `C:\Program Files\JarvisAI\`
5. Cliente abre Jarvis desde acceso directo del escritorio

### Ventajas ✅

- **Instalación profesional**: Wizard estilo "software tradicional" (inspiración: Obsidian, VS Code)
- **Protección de código**: Binarios compilados (Python → .exe, JS → obfuscado)
- **Sin dependencias externas**: Installer incluye Python runtime + Node embebido
- **Firma digital**: Code signing con certificado (aumenta confianza)
- **Desinstalación limpia**: Registro Windows, Start Menu, shortcuts

### Desventajas ❌

- **Actualizaciones complejas**: Necesitas auto-updater (electron-updater) o nuevo installer
- **Debugging difícil**: Logs compilados, stack traces ofuscados
- **Tamaño grande**: Installer ~300-500 MB (Python runtime + Node + Electron)
- **Costo de firma digital**: $200-400/año (certificado code signing)
- **Build CI/CD**: Necesitas pipeline automatizado (GitHub Actions + AWS S3)

### Stack Técnico

```yaml
# Build Pipeline (GitHub Actions)
1. Backend:
   - PyInstaller: backend/ → jarvis_backend.exe (single file)
   - Incluir: faster-whisper, edge-tts, CUDA libs (si GPU)
   - Ofuscar: pyarmor (protección anti-reverse)

2. Frontend:
   - Electron Builder: frontend/ → JarvisAI-Setup.exe
   - Incluir: jarvis_backend.exe embebido
   - Firmar: code signing con certificado DigiCert/Sectigo

3. Distribución:
   - AWS S3 bucket: installers versioned (v1.0.0, v1.0.1...)
   - CloudFront CDN: descarga rápida global
   - electron-updater: auto-update en background
```

### Precio Sugerido

- **One-time**: $250-350 (instalación perpetua + 3 meses soporte)
- **Mensual**: $200-250/mes (licencia + actualizaciones ilimitadas)
- **Anual**: $2,000-2,400/año (incluye soporte prioritario)

### Esfuerzo de Implementación

| Tarea | Tiempo |
|-------|--------|
| Configurar PyInstaller (backend) | 4h |
| Configurar Electron Builder (frontend) | 3h |
| Integrar auto-updater (electron-updater) | 3h |
| Crear installer wizard (NSIS/Squirrel) | 2h |
| Obtener certificado code signing | 1h |
| Firmar binarios + testear | 2h |
| Configurar CI/CD (GitHub Actions) | 3h |
| Testear en VMs limpias (Win 11) | 2h |
| **TOTAL** | **20h** |

### Cuándo elegir esta opción

✅ **Cliente corporativo** (quiere software "profesional")  
✅ **Necesitas proteger IP** (código compilado)  
✅ **Cliente no técnico** (no sabe usar Git)  
✅ **Producto maduro** (pocas actualizaciones frecuentes)  

---

## 🔷 Opción 3: Servicio Hosted (VM Dedicada / SaaS)

### ¿Cómo funciona?

1. Despliegas Jarvis en una **VM dedicada Windows** en Azure/AWS (o local con IP pública)
2. Cliente accede vía **interfaz web** (React app) en `https://cliente.jarvis-ai.com`
3. Autenticación con email + password (multi-tenant)
4. Voice input funciona vía WebRTC (navegador → servidor)
5. Cliente paga mensual por "seat" (usuario)

### Ventajas ✅

- **Instalación cero**: Cliente solo necesita navegador moderno (Chrome/Edge)
- **Actualizaciones transparentes**: Deploy nuevo código → todos los clientes actualizados
- **Debugging centralizado**: Logs en CloudWatch/Azure Monitor, APM (Sentry)
- **Escalabilidad**: Multi-tenant (1 VM → 10-50 clientes)
- **Protección IP máxima**: Código nunca sale del servidor

### Desventajas ❌

- **Costo de infra alto**: VM Windows ($150-300/mes) + storage + bandwidth
- **Latencia de voz**: WebRTC introduce lag (vs local faster-whisper)
- **Dependencia de internet**: Cliente offline = no puede usar Jarvis
- **Privacidad**: Datos del cliente pasan por tu servidor (GDPR/compliance)
- **Complejidad técnica**: Multi-tenancy, backups, HA, seguridad

### Stack Técnico

```yaml
# Infraestructura (Azure ejemplo)
VM Windows Server 2022:
  - Spec: Standard_D4s_v5 (4 vCPU, 16 GB RAM, RTX optional)
  - OS: Windows Server 2022 Datacenter
  - Backend: FastAPI + Gunicorn/Uvicorn
  - Frontend: React SPA + Nginx reverse proxy
  - DB: PostgreSQL (Azure Database) para multi-tenancy
  - Storage: Azure Blob Storage (chat history, logs)
  - Voice: WebRTC → faster-whisper en VM
  - CDN: Azure CDN para assets estáticos

# Multi-Tenancy:
- 1 base de datos PostgreSQL
- Tabla `tenants` (id, name, api_keys_encrypted, limits)
- Tabla `users` (id, tenant_id, email, password_hash)
- Aislamiento: tenant_id en todas las queries
- Limits: rate limiting por tenant (10 msgs/min)

# Monitoreo:
- Azure Monitor: métricas VM (CPU, RAM, disk)
- Sentry: error tracking + APM
- LogRocket: session replay (debugging UX)
- Uptime Robot: health checks cada 5min
```

### Precio Sugerido

- **Mensual (por seat)**: $400-600/mes para 1-3 usuarios
- **Empresarial**: $1,000-1,500/mes para 5-10 usuarios
- **Customizado**: $2,000+/mes (SLA 99.9%, soporte 24/7, features custom)

### Esfuerzo de Implementación

| Tarea | Tiempo |
|-------|--------|
| Configurar multi-tenancy (DB schema) | 6h |
| Migrar frontend a React SPA web | 8h |
| Implementar WebRTC voice input | 6h |
| Configurar Azure VM + reverse proxy | 4h |
| Implementar autenticación (JWT) | 4h |
| Implementar rate limiting + quotas | 3h |
| Configurar backups automatizados | 2h |
| Integrar Sentry + monitoreo | 3h |
| Testear multi-tenant en staging | 4h |
| **TOTAL** | **40h** |

### Cuándo elegir esta opción

✅ **Cliente empresarial** (equipos de 5+ personas)  
✅ **Quieres SaaS escalable** (10, 50, 100 clientes)  
✅ **Tienes capital inicial** ($5K+ para infra + dev)  
✅ **Visión a largo plazo** (producto como servicio, MRR recurrente)  

---

## 🎯 Recomendación para Primer Cliente

### **FASE 1: Repo Privado (Primeros 1-3 clientes)**

**Por qué**:
- Menor esfuerzo inicial (4.5h vs 20h vs 40h)
- Feedback rápido sobre bugs/features
- Validar product-market fit antes de invertir en binarios/hosted
- Precio accesible para early adopters ($150-200/mes)

**Plan de acción** (2-4 horas):
```bash
# 1. Limpiar repo
git rm -r --cached data/ generated/ *.log .env
git commit -m "Preparar repo para entrega cliente"

# 2. Crear repo privado GitHub
# GitHub → New Repository → Private → "JarvisAI-Cliente1"

# 3. Agregar cliente como colaborador
# Settings → Collaborators → Add people → email@cliente.com

# 4. Documentar instalación
# Ya tienes README.md + install.ps1 (este documento)

# 5. Sesión onboarding (1h video call)
# - Compartir pantalla
# - Ejecutar install.ps1 juntos
# - Configurar API Keys
# - Demostrar comandos de voz
# - Entregar guía de troubleshooting
```

### **FASE 2: Binario Empaquetado (Clientes 4-10)**

Cuando:
- Tienes $2K+ de MRR (justifica 20h de dev)
- Clientes piden instalación "más profesional"
- Quieres proteger código fuente

### **FASE 3: Servicio Hosted (Clientes 10+)**

Cuando:
- Tienes $5K+ de MRR (justifica $300/mes de infra)
- Clientes piden acceso multi-usuario
- Necesitas escalar sin fricciones

---

## 📝 Contrato y Licencia (Todos los Modelos)

Incluir **siempre** en la entrega:

### LICENSE.md (ejemplo)

```markdown
# Licencia de Uso Comercial — Jarvis AI

Copyright (c) 2026 Emmanuel Pedraza. Todos los derechos reservados.

## Términos de Uso

CLIENTE recibe una licencia **no exclusiva, no transferible, no sublicenciable**
para usar Jarvis AI en su entorno de trabajo.

### Permitido ✅
- Usar Jarvis AI en tu PC personal/trabajo
- Configurar con tus API Keys propias
- Modificar archivos de configuración (.env)

### Prohibido ❌
- Redistribuir el código fuente (total o parcial)
- Vender, sublicenciar o transferir a terceros
- Modificar el código sin autorización escrita
- Uso en más de 1 máquina sin licencia adicional

### Soporte y Actualizaciones
- Soporte técnico incluido (respuesta <24h hábiles)
- Actualizaciones de seguridad incluidas
- Features nuevas sujetas a roadmap

### Terminación
Licencia válida mientras el pago mensual esté al día. Terminación inmediata
en caso de violación de términos.
```

### Contrato de Servicios (1 página)

```
CONTRATO DE LICENCIA DE SOFTWARE — JARVIS AI

PROVEEDOR: Emmanuel Pedraza (@Corgipollo)
CLIENTE: [Nombre completo o razón social]
FECHA: [Fecha de firma]

1. LICENCIA: [Repo Privado / Binario / Hosted]
2. PRECIO: $[X]/mes, pago anticipado cada [1/3/12] meses
3. SOPORTE: Respuesta <24h hábiles vía [Email/Telegram/Slack]
4. TERMINACIÓN: 30 días de aviso por cualquier parte
5. CONFIDENCIALIDAD: Código fuente propiedad de Emmanuel Pedraza
6. GARANTÍA: Software "AS IS", sin garantías implícitas

FIRMAS:
_____________________          _____________________
Emmanuel Pedraza (Proveedor)   [Cliente]
```

---

## 🚀 Checklist de Entrega (Repo Privado)

Antes de dar acceso al cliente:

- [ ] `git rm` archivos sensibles (.env, logs, *.pyc)
- [ ] Verificar `.gitignore` completo
- [ ] README.md actualizado (este documento)
- [ ] install.ps1 testeado en VM limpia Windows 11
- [ ] LICENSE.md incluido en repo
- [ ] Contrato firmado por cliente
- [ ] Primer pago recibido (o depósito 50%)
- [ ] Cliente agregado como colaborador GitHub
- [ ] Sesión onboarding agendada (1h)
- [ ] Canal de soporte definido (Telegram/Slack)
- [ ] Backup del repo en disco local

---

## 📊 Resumen Ejecutivo

| Modelo | Mejor para | Precio | Esfuerzo | Protección IP | Escalable |
|--------|------------|--------|----------|---------------|-----------|
| **Repo Privado** | Early adopters técnicos | $150-200/mes | 4.5h | ⚠️ Baja | ❌ No |
| **Binario** | Clientes corporativos | $250-350 one-time | 20h | ✅ Alta | ⚠️ Media |
| **Hosted** | Empresas/equipos | $400-600/mes | 40h | ✅ Máxima | ✅ Sí |

**Recomendación**: Empezar con **Repo Privado** para primeros 1-3 clientes, validar PMF, luego escalar a **Binario** (4-10 clientes) y finalmente **Hosted** (10+ clientes).

---

## 📞 Contacto

Para discutir implementación o pricing:
- **Telegram**: @corgipollo
- **Email**: emmanuel@jarvis-ai.local
- **GitHub**: @Corgipollo

---

**Documento creado**: 2026-05-31  
**Autor**: Emmanuel Pedraza  
**Versión**: 1.0  
