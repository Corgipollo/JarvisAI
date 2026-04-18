"""Cliente Shopify para consultar la tienda GROP."""
import httpx
from typing import Optional
from config import settings


class ShopifyClient:
    def __init__(self):
        self.store = settings.SHOPIFY_STORE
        self.token = settings.SHOPIFY_ACCESS_TOKEN
        self.base_url = f"https://{self.store}/admin/api/2024-01"
        self.headers = {
            "X-Shopify-Access-Token": self.token,
            "Content-Type": "application/json",
        }

    @property
    def is_configured(self) -> bool:
        return bool(self.token)

    async def search_products(self, query: str, limit: int = 5) -> list[dict]:
        if not self.is_configured:
            return [{"error": "Shopify no configurado. Agrega SHOPIFY_ACCESS_TOKEN al .env"}]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    f"{self.base_url}/products.json",
                    params={"title": query, "limit": limit},
                    headers=self.headers,
                )
                products = r.json().get("products", [])
                return [
                    {
                        "title": p["title"],
                        "price": p["variants"][0]["price"] if p["variants"] else "N/A",
                        "status": p["status"],
                        "inventory": sum(
                            v.get("inventory_quantity", 0) for v in p["variants"]
                        ),
                        "url": f"https://{self.store}/products/{p['handle']}",
                    }
                    for p in products
                ]
        except Exception as e:
            return [{"error": str(e)}]

    async def get_orders(self, limit: int = 5) -> list[dict]:
        if not self.is_configured:
            return [{"error": "Shopify no configurado"}]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    f"{self.base_url}/orders.json",
                    params={"limit": limit, "status": "any"},
                    headers=self.headers,
                )
                orders = r.json().get("orders", [])
                return [
                    {
                        "order_number": o["order_number"],
                        "total": o["total_price"],
                        "currency": o["currency"],
                        "status": o["financial_status"],
                        "customer": o.get("customer", {}).get("first_name", "N/A"),
                        "created_at": o["created_at"][:10],
                    }
                    for o in orders
                ]
        except Exception as e:
            return [{"error": str(e)}]

    async def get_store_stats(self) -> dict:
        if not self.is_configured:
            return {"error": "Shopify no configurado"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    f"{self.base_url}/products/count.json",
                    headers=self.headers,
                )
                product_count = r.json().get("count", 0)

                r2 = await client.get(
                    f"{self.base_url}/orders/count.json",
                    params={"status": "any"},
                    headers=self.headers,
                )
                order_count = r2.json().get("count", 0)

                return {
                    "products": product_count,
                    "total_orders": order_count,
                    "store": self.store,
                }
        except Exception as e:
            return {"error": str(e)}


shopify = ShopifyClient()
