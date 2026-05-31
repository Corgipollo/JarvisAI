# GUÍA RÁPIDA — ENVIAR FOLLOW-UP DAY-3

## OPCIÓN A: Envío Manual (Recomendado)

### 1. Emails (3 mensajes)

**RomanPushkin**
```
To: roman.pushkin@gmail.com
Subject: Bootcamp ICP data you should see
```
Copiar mensaje de `followup_day3_batch1.md` → Mensaje #2

**johnnyfived**
```
To: johnnyfived@protonmail.com
Subject: Domain flipper monetization pattern
```
Copiar mensaje de `followup_day3_batch1.md` → Mensaje #3

**ruairidhwm**
```
To: ruairidhwm@gmail.com
Subject: WinLog GTM idea worth testing
```
Copiar mensaje de `followup_day3_batch1.md` → Mensaje #4

### 2. HN DMs (2 mensajes)

**s9876121**
1. Ir a https://news.ycombinator.com/user?id=s9876121
2. Click "send message"
3. Copiar mensaje de `followup_day3_batch1.md` → Mensaje #1

**alexgotoi**
1. Ir a https://news.ycombinator.com/user?id=alexgotoi
2. Click "send message"
3. Copiar mensaje de `followup_day3_batch1.md` → Mensaje #5

### 3. Actualizar Ledger

Después de enviar cada uno:
```python
python send_followup_day3.py --update-ledger
```

O manualmente editar `data/hn_outreach_ledger.json` y agregar cada send.

---

## OPCIÓN B: Semi-Automático (requiere config SMTP)

1. **Editar `send_followup_day3.py`**:
   - Cambiar `DRY_RUN = False`
   - Descomentar sección SMTP (si tienes Gmail configurado)

2. **Ejecutar**:
   ```bash
   python send_followup_day3.py
   ```

3. **HN DMs** siguen siendo manuales (HN no tiene API)

---

## TRACKING

Después de enviar, revisar respuestas en:
- **48h** (2026-06-02): Check emails + HN inbox
- **7 días** (2026-06-07): Si no responden, enviar follow-up día-10

**Reply rate esperado**: 20-30% (1-2 respuestas)

---

## QUOTA STATUS

- Enviados hoy: 2/10
- Follow-up batch: 5 mensajes
- **Total después**: 7/10 ✅
- Slots restantes: 3

**SAFE** para enviar todos hoy sin exceder límite.
