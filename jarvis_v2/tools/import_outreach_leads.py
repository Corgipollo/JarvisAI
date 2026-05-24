"""import_outreach_leads.py - Importa las 20 empresas target del ICP inicial.

Idempotente: skip empresas que ya existen. Run multiple veces sin duplicar.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import requests

API_URL = "http://127.0.0.1:5000"
TOKEN = "jarvis_a8x29kfp3lz7m2qw9bdv"

LEADS = [
    # ICP 1 - Agro-logistica Bajio
    {"company": "Almer (Almacenadora Mercader)", "vertical": "agro_logistics",
     "location": "Queretaro / Nacional",
     "attack_angle": "Conciliacion volumenes en almacen vs certificados de deposito agricolas",
     "icp_segment": "agro"},
    {"company": "Halten Logistica", "vertical": "agro_logistics",
     "location": "Queretaro",
     "attack_angle": "Automatizacion captura regulaciones SADER y cartas porte",
     "icp_segment": "agro"},
    {"company": "Transportadora Egoba (Traxion)", "vertical": "logistics_freight",
     "location": "Queretaro KM 188",
     "attack_angle": "Auditoria visual de remisiones de carga seca/refrigerada vs facturacion",
     "icp_segment": "agro"},
    {"company": "Tlisa Pipas y Transporte", "vertical": "transport_specialized",
     "location": "Jurica, Qro.",
     "attack_angle": "Lectura y agendamiento automatico de pedidos al ERP",
     "icp_segment": "agro"},
    {"company": "Mechanova", "vertical": "agro_machinery",
     "location": "Queretaro / Bajio",
     "attack_angle": "Sincronizacion inventario implementos y refacciones",
     "icp_segment": "agro"},
    {"company": "Cajas Agricolas de Morelos", "vertical": "agro_packaging",
     "location": "Cobertura Bajio",
     "attack_angle": "Procesamiento ordenes empaque desde correos a hojas produccion",
     "icp_segment": "agro"},
    {"company": "Schryver Logistics", "vertical": "transport_perishables",
     "location": "Centro Sur Qro.",
     "attack_angle": "Consolidacion datos aduaneros y tracking LCL sin data entry humano",
     "icp_segment": "agro"},
    {"company": "Agroinsumos del Centro", "vertical": "agro_distribution",
     "location": "Ezequiel Montes",
     "attack_angle": "Cuadre automatico inventario fertilizantes y semillas vs ventas",
     "icp_segment": "agro"},
    {"company": "Silos y Transportes del Bajio", "vertical": "grain_storage",
     "location": "Pedro Escobedo",
     "attack_angle": "Conciliacion tickets bascula entrada maiz vs liquidacion productores",
     "icp_segment": "agro"},
    {"company": "Nutec", "vertical": "animal_nutrition",
     "location": "El Marques, Qro.",
     "attack_angle": "Procesamiento ordenes compra materia prima a granel en SAP",
     "icp_segment": "agro"},
    {"company": "Omni Logistics", "vertical": "3pl_warehousing",
     "location": "Jardines de la Hacienda",
     "attack_angle": "Kitting y preparacion pedidos: Jarvis auditando ordenes salida WMS",
     "icp_segment": "agro"},
    {"company": "Forrajes y Granos San Juan", "vertical": "grain_distribution",
     "location": "San Juan del Rio",
     "attack_angle": "Automatizacion reporte cobranza clientes credito (Excel a WhatsApp)",
     "icp_segment": "agro"},
    {"company": "Grupo Pecuario San Antonio", "vertical": "agroindustria",
     "location": "Queretaro",
     "attack_angle": "Consolidacion reportes consumo alimento en granjas sin captura manual",
     "icp_segment": "agro"},
    # ICP 2 - E-commerce / fulfillment
    {"company": "Nude Project (LATAM Ops)", "vertical": "apparel_ecommerce",
     "location": "Online",
     "attack_angle": "Sincronizacion stock almacen con variantes Shopify y etiquetas",
     "icp_segment": "ecommerce"},
    {"company": "Alo Yoga (Distribuidores MX)", "vertical": "apparel_ecommerce",
     "location": "Online / Retail",
     "attack_angle": "Conciliacion devoluciones y actualizacion inventario omnicanal",
     "icp_segment": "ecommerce"},
    {"company": "Cubbo", "vertical": "ecommerce_fulfillment",
     "location": "Parque Ind. Qro.",
     "attack_angle": "Jarvis auditando guias Estafeta/DHL vs ordenes Shopify",
     "icp_segment": "ecommerce"},
    {"company": "Muebles Dico (Logistica Reg.)", "vertical": "ecommerce_retail",
     "location": "Queretaro",
     "attack_angle": "Ruteo y confirmacion entregas ultima milla leyendo reportes",
     "icp_segment": "ecommerce"},
    {"company": "Viral Hunter (Ops)", "vertical": "ecommerce_dropshipping",
     "location": "Online",
     "attack_angle": "Jarvis operando AutoDS y actualizando precios Shopify por costo proveedor",
     "icp_segment": "ecommerce"},
    # ICP 3 - Agencies
    {"company": "Agencia Merca", "vertical": "marketing_digital",
     "location": "Queretaro",
     "attack_angle": "Generacion masiva reportes ROAS extrayendo datos Meta Ads a Google Sheets",
     "icp_segment": "agency"},
    {"company": "SmartWeb 3D", "vertical": "dev_agency",
     "location": "Online",
     "attack_angle": "Orquestacion deployments y testing visual automatico animaciones web",
     "icp_segment": "agency"},
]


def main():
    body = {"leads": LEADS}
    r = requests.post(
        f"{API_URL}/api/v1/outreach/leads/import",
        json=body,
        headers={"X-Jarvis-Token": TOKEN, "Content-Type": "application/json"},
        timeout=15,
    )
    print(f"status={r.status_code}")
    print(r.json())


if __name__ == "__main__":
    main()
