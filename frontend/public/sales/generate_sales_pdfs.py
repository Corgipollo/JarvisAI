"""
Generador de PDFs profesionales para Jarvis AI Sales Kit
Crea: one-pager y pitch deck de 5 slides
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
import os

# Configuración de colores (brand palette moderna)
BRAND_PRIMARY = colors.HexColor('#2563EB')  # Azul vibrante (tech)
BRAND_SECONDARY = colors.HexColor('#10B981')  # Verde (success)
BRAND_ACCENT = colors.HexColor('#F59E0B')  # Naranja (energy)
BRAND_DARK = colors.HexColor('#1F2937')  # Gris oscuro
BRAND_LIGHT = colors.HexColor('#F3F4F6')  # Gris claro

# Directorio de salida
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================
# ONE-PAGER PDF
# ============================================

def create_one_pager():
    """Genera el one-pager profesional de Jarvis AI"""

    filename = os.path.join(OUTPUT_DIR, "jarvis-ai-one-pager.pdf")
    doc = SimpleDocTemplate(filename, pagesize=letter,
                            leftMargin=0.5*inch, rightMargin=0.5*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)

    story = []
    styles = getSampleStyleSheet()

    # Estilos custom
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=28,
        textColor=BRAND_PRIMARY,
        spaceAfter=8,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=BRAND_DARK,
        spaceAfter=16,
        alignment=TA_CENTER,
        fontName='Helvetica'
    )

    section_title = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=BRAND_PRIMARY,
        spaceAfter=10,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )

    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=10,
        textColor=BRAND_DARK,
        spaceAfter=8,
        alignment=TA_JUSTIFY,
        leading=14
    )

    # Header
    story.append(Paragraph("JARVIS AI", title_style))
    story.append(Paragraph("Tu Asistente Personal de IA Operado por Voz", subtitle_style))
    story.append(Spacer(1, 0.2*inch))

    # Elevator pitch
    story.append(Paragraph("¿Qué es Jarvis AI?", section_title))
    story.append(Paragraph(
        """Jarvis AI es un asistente personal inteligente que funciona completamente por voz, diseñado
        para profesionales y equipos que buscan automatizar tareas repetitivas, obtener respuestas instantáneas
        y maximizar su productividad sin sacrificar privacidad. A diferencia de otros asistentes que dependen de
        la nube, Jarvis procesa todo localmente en tu dispositivo.""",
        body_style
    ))

    story.append(Spacer(1, 0.15*inch))

    # Diferenciadores (tabla 3 columnas)
    story.append(Paragraph("¿Por qué Jarvis AI?", section_title))

    diff_data = [
        ['🔒 Privacidad Total', '⚡ Ultra Rápido', '🧠 Inteligencia Híbrida'],
        [
            'Procesa tu voz localmente. Tus conversaciones nunca salen de tu dispositivo.',
            'Respuestas en <2 segundos. Routing inteligente entre Claude, Gemini y Ollama local.',
            'Aprende de tu contexto. Integración con Obsidian para memoria a largo plazo.'
        ]
    ]

    diff_table = Table(diff_data, colWidths=[2.5*inch, 2.5*inch, 2.5*inch])
    diff_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BRAND_PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, BRAND_LIGHT)
    ]))
    story.append(diff_table)

    story.append(Spacer(1, 0.15*inch))

    # Pricing (tabla)
    story.append(Paragraph("Planes y Precios", section_title))

    pricing_data = [
        ['Plan', 'Precio', 'Características Principales', 'Ideal Para'],
        [
            'Personal',
            'Gratis o $9/mes',
            '• 500 min/mes (free)\n• 2,000 min/mes (paid)\n• 1-2 dispositivos\n• Ollama + Gemini',
            'Estudiantes, individuos'
        ],
        [
            'Pro',
            '$29/mes',
            '• Conversación ilimitada\n• Claude Opus prioritario\n• 3 dispositivos\n• Voice cloning custom\n• Beta access',
            'Profesionales, freelancers'
        ],
        [
            'Business',
            '$99/mes',
            '• 5 usuarios\n• API access + webhooks\n• White-label option\n• SLA 99%\n• Soporte 1:1',
            'Equipos, agencias'
        ]
    ]

    pricing_table = Table(pricing_data, colWidths=[1.2*inch, 1.1*inch, 3*inch, 2.2*inch])
    pricing_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BRAND_SECONDARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, BRAND_DARK),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BRAND_LIGHT])
    ]))
    story.append(pricing_table)

    story.append(Spacer(1, 0.15*inch))

    # Use Cases
    story.append(Paragraph("Casos de Uso Principales", section_title))

    use_cases = [
        "✅ <b>Investigación rápida</b>: 'Jarvis, resume los últimos papers sobre RAG multi-modal'",
        "✅ <b>Gestión de tareas</b>: 'Agrega al calendar reunión con cliente mañana 3pm'",
        "✅ <b>Generación de contenido</b>: 'Escribe un thread de Twitter sobre pricing strategies'",
        "✅ <b>Análisis de datos</b>: 'Analiza mi vault de Obsidian y encuentra contradicciones'",
        "✅ <b>Coaching 1:1</b>: 'Revisa mi pitch deck y dame feedback honesto'"
    ]

    for uc in use_cases:
        story.append(Paragraph(uc, body_style))

    story.append(Spacer(1, 0.15*inch))

    # Competencia (tabla comparativa mini)
    story.append(Paragraph("Ventaja vs Competencia", section_title))

    comp_data = [
        ['Feature', 'Jarvis AI', 'ChatGPT Voice', 'ElevenLabs', 'Alfred_'],
        ['Procesamiento Local', '✅', '❌', '❌', '❌'],
        ['Offline Capable', '✅', '❌', '❌', '❌'],
        ['Voice-First UX', '✅', 'Parcial', '✅', '❌'],
        ['Precio (Pro tier)', '$29/mo', '$20/mo*', '$99/mo', '$25/mo'],
        ['API Access', '✅ (Business)', '✅', '✅', '❌']
    ]

    comp_table = Table(comp_data, colWidths=[1.8*inch, 1.3*inch, 1.4*inch, 1.3*inch, 1.3*inch])
    comp_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BRAND_DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, BRAND_LIGHT),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BRAND_LIGHT]),
        ('BACKGROUND', (1, 1), (1, -1), colors.Color(0.9, 0.95, 1))  # Highlight Jarvis column
    ]))
    story.append(comp_table)

    story.append(Paragraph("<i>*ChatGPT Plus no incluye voice-first UX dedicada</i>",
                          ParagraphStyle('footnote', parent=body_style, fontSize=7, textColor=colors.grey)))

    story.append(Spacer(1, 0.15*inch))

    # CTA footer
    cta_style = ParagraphStyle(
        'CTA',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.white,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    cta_data = [[Paragraph("🚀 Prueba gratis hoy | www.jarvisai.com | contact@jarvisai.com", cta_style)]]
    cta_table = Table(cta_data, colWidths=[7.5*inch])
    cta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BRAND_ACCENT),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10)
    ]))
    story.append(cta_table)

    # Construir PDF
    doc.build(story)
    print(f"✅ One-pager generado: {filename}")
    return filename


# ============================================
# PITCH DECK (5 slides)
# ============================================

def create_pitch_deck():
    """Genera el pitch deck de 5 slides"""

    filename = os.path.join(OUTPUT_DIR, "jarvis-ai-pitch-deck.pdf")

    # Usar canvas para más control de layout (slide-style)
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    # ===== SLIDE 1: PORTADA =====
    c.setFillColor(BRAND_PRIMARY)
    c.rect(0, 0, width, height, fill=True)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 48)
    c.drawCentredString(width/2, height*0.6, "JARVIS AI")

    c.setFont("Helvetica", 24)
    c.drawCentredString(width/2, height*0.5, "Tu Asistente Personal de IA")
    c.drawCentredString(width/2, height*0.45, "Operado por Voz")

    c.setFont("Helvetica", 14)
    c.drawCentredString(width/2, height*0.25, "Emmanuel Pedraza | Junio 2026")
    c.drawCentredString(width/2, height*0.20, "www.jarvisai.com")

    c.showPage()

    # ===== SLIDE 2: EL PROBLEMA =====
    c.setFillColor(BRAND_DARK)
    c.rect(0, height*0.85, width, height*0.15, fill=True)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(width/2, height*0.9, "El Problema")

    # Bullets
    c.setFillColor(BRAND_DARK)
    c.setFont("Helvetica", 18)
    y_pos = height*0.75
    problems = [
        "❌  Los asistentes de IA actuales son lentos (>5s por respuesta)",
        "❌  Suben tus conversaciones privadas a la nube (privacidad = 0)",
        "❌  Requieren internet 24/7 (no offline mode)",
        "❌  Interfaces de chat, no voice-first (typing > talking)",
        "❌  Caros: $0.30/min (OpenAI) o $99/mo (ElevenLabs Pro)"
    ]

    for problem in problems:
        c.drawString(inch, y_pos, problem)
        y_pos -= 0.9*inch

    c.setFillColor(BRAND_ACCENT)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width/2, inch*0.8, "→ Profesionales necesitan velocidad + privacidad + costo razonable")

    c.showPage()

    # ===== SLIDE 3: LA SOLUCIÓN =====
    c.setFillColor(BRAND_SECONDARY)
    c.rect(0, height*0.85, width, height*0.15, fill=True)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(width/2, height*0.9, "La Solución: Jarvis AI")

    c.setFillColor(BRAND_DARK)
    c.setFont("Helvetica", 18)
    y_pos = height*0.75
    solutions = [
        "✅  Procesamiento 100% local (faster-whisper + edge-tts)",
        "✅  Respuestas en <2 segundos (routing inteligente)",
        "✅  Offline capable (Ollama local como fallback)",
        "✅  Voice-first UX (diseñado para hablar, no escribir)",
        "✅  90% más barato (costo marginal ~$0.03/min)"
    ]

    for sol in solutions:
        c.drawString(inch, y_pos, sol)
        y_pos -= 0.9*inch

    # Diagrama simple (routing)
    c.setFillColor(BRAND_LIGHT)
    c.roundRect(inch, inch*1.5, width-2*inch, inch*1.2, 10, fill=True)
    c.setFillColor(BRAND_PRIMARY)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width/2, inch*2.3, "Routing Jerárquico de IA")
    c.setFont("Helvetica", 11)
    c.drawCentredString(width/2, inch*2, "Claude API (tareas complejas) → Gemini Free (rápidas) → Ollama Local (offline)")

    c.showPage()

    # ===== SLIDE 4: MERCADO & TRACCIÓN =====
    c.setFillColor(BRAND_PRIMARY)
    c.rect(0, height*0.85, width, height*0.15, fill=True)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(width/2, height*0.9, "Mercado & Oportunidad")

    c.setFillColor(BRAND_DARK)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(inch, height*0.75, "Mercado Total Direccionable (TAM)")
    c.setFont("Helvetica", 16)
    market_data = [
        "• Voice AI market: $27.16B (2026) → $67.38B (2030) — CAGR 25.6%",
        "• Personal AI assistants: 1.2B usuarios globalmente",
        "• Profesionales tech (early adopters): 50M+ (freelancers, devs, researchers)"
    ]
    y_pos = height*0.68
    for data in market_data:
        c.drawString(inch*1.2, y_pos, data)
        y_pos -= 0.5*inch

    c.setFont("Helvetica-Bold", 20)
    c.drawString(inch, height*0.48, "Ventaja Competitiva Sostenible")
    c.setFont("Helvetica", 16)
    advantages = [
        "1. Arquitectura híbrida (local + cloud) = difícil de replicar",
        "2. Stack cost-efficient = márgenes 68% vs 30-40% industria",
        "3. Privacy-first positioning = demanda post-GDPR en crecimiento"
    ]
    y_pos = height*0.41
    for adv in advantages:
        c.drawString(inch*1.2, y_pos, adv)
        y_pos -= 0.5*inch

    c.setFillColor(BRAND_SECONDARY)
    c.roundRect(inch, inch*0.8, width-2*inch, inch*0.6, 10, fill=True)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width/2, inch*1.25, "Proyección Año 1: $100K ARR | 610 usuarios paid")
    c.setFont("Helvetica", 14)
    c.drawCentredString(width/2, inch*1.05, "(500 Personal $9/mo + 100 Pro $29/mo + 10 Business $99/mo)")

    c.showPage()

    # ===== SLIDE 5: PRICING & CTA =====
    c.setFillColor(BRAND_ACCENT)
    c.rect(0, height*0.85, width, height*0.15, fill=True)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(width/2, height*0.9, "Planes & Siguiente Paso")

    # Pricing boxes
    plans = [
        {"name": "Personal", "price": "$9/mo", "color": BRAND_LIGHT, "features": ["2K min/mes", "2 dispositivos", "Claude routing"]},
        {"name": "Pro", "price": "$29/mo", "color": BRAND_SECONDARY, "features": ["Ilimitado", "3 dispositivos", "Beta access"]},
        {"name": "Business", "price": "$99/mo", "color": BRAND_PRIMARY, "features": ["5 usuarios", "API access", "White-label"]}
    ]

    box_width = 2*inch
    box_height = 2.5*inch
    x_start = (width - 3*box_width - 0.8*inch) / 2
    y_start = height*0.5

    for i, plan in enumerate(plans):
        x = x_start + i * (box_width + 0.4*inch)

        # Box
        c.setFillColor(plan["color"])
        c.roundRect(x, y_start, box_width, box_height, 10, fill=True)

        # Text
        text_color = colors.white if i > 0 else BRAND_DARK
        c.setFillColor(text_color)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(x + box_width/2, y_start + box_height - 0.4*inch, plan["name"])
        c.setFont("Helvetica-Bold", 24)
        c.drawCentredString(x + box_width/2, y_start + box_height - 0.8*inch, plan["price"])

        c.setFont("Helvetica", 11)
        y_feature = y_start + box_height - 1.3*inch
        for feature in plan["features"]:
            c.drawCentredString(x + box_width/2, y_feature, f"• {feature}")
            y_feature -= 0.35*inch

    # CTA
    c.setFillColor(BRAND_DARK)
    c.roundRect(inch*1.5, inch*1.2, width-3*inch, inch*0.8, 10, fill=True)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(width/2, inch*1.7, "🚀 Prueba Gratis Hoy")
    c.setFont("Helvetica", 16)
    c.drawCentredString(width/2, inch*1.45, "www.jarvisai.com | contact@jarvisai.com")

    c.setFillColor(BRAND_DARK)
    c.setFont("Helvetica", 12)
    c.drawCentredString(width/2, inch*0.6, "Emmanuel Pedraza | Fundador & CEO")
    c.drawCentredString(width/2, inch*0.4, "Guadalajara, México | +52 [tu-telefono]")

    c.save()
    print(f"✅ Pitch deck generado: {filename}")
    return filename


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    import sys
    import io

    # Fix encoding for Windows console
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("Generando Sales Kit de Jarvis AI...\n")

    # Generar PDFs
    onepager = create_one_pager()
    pitchdeck = create_pitch_deck()

    print(f"\nCOMPLETADO - Sales Kit listo:")
    print(f"   One-pager: {onepager}")
    print(f"   Pitch deck: {pitchdeck}")
    print(f"   Contract template: {os.path.join(OUTPUT_DIR, 'contract-template.md')}")
    print(f"   Pricing strategy: {os.path.join(OUTPUT_DIR, 'pricing-strategy.md')}")
    print(f"\nTodos los archivos en: {OUTPUT_DIR}")
