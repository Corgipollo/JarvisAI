"""Clima y ubicacion — Open-Meteo (gratis, sin API key, siempre funciona)."""
import httpx


async def get_weather(city: str = None, lat: float = None, lon: float = None) -> dict:
    """Clima actual via Open-Meteo."""

    # Si no tenemos coordenadas, geocodificar la ciudad
    if lat is None or lon is None:
        from config import settings
        city = city or settings.WEATHER_CITY

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": city, "count": 1, "language": "es"},
                )
                data = r.json()
                results = data.get("results", [])
                if results:
                    lat = results[0]["latitude"]
                    lon = results[0]["longitude"]
                    city = results[0].get("name", city)
                else:
                    return {"error": f"No encontre la ciudad: {city}"}
        except Exception as e:
            return {"error": str(e)}

    # Obtener clima
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
                    "timezone": "auto",
                },
            )
            data = r.json()
            current = data.get("current", {})

            # Traducir weather code
            code = current.get("weather_code", 0)
            desc = weather_code_to_spanish(code)

            return {
                "location": city or f"{lat},{lon}",
                "temp_c": str(current.get("temperature_2m", "?")),
                "feels_like": str(current.get("apparent_temperature", "?")),
                "humidity": str(current.get("relative_humidity_2m", "?")),
                "description": desc,
                "wind_kmph": str(current.get("wind_speed_10m", "?")),
            }
    except Exception as e:
        return {"error": str(e)}


def weather_code_to_spanish(code: int) -> str:
    codes = {
        0: "Despejado", 1: "Mayormente despejado", 2: "Parcialmente nublado",
        3: "Nublado", 45: "Niebla", 48: "Niebla helada",
        51: "Llovizna ligera", 53: "Llovizna", 55: "Llovizna intensa",
        61: "Lluvia ligera", 63: "Lluvia", 65: "Lluvia intensa",
        71: "Nevada ligera", 73: "Nevada", 75: "Nevada intensa",
        80: "Chubascos ligeros", 81: "Chubascos", 82: "Chubascos intensos",
        95: "Tormenta", 96: "Tormenta con granizo", 99: "Tormenta con granizo intenso",
    }
    return codes.get(code, "Desconocido")


async def get_location() -> dict:
    """Ubicacion por IP."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get("http://ip-api.com/json/?lang=es")
            data = r.json()
            return {
                "city": data.get("city"),
                "region": data.get("regionName"),
                "country": data.get("country"),
                "lat": data.get("lat"),
                "lon": data.get("lon"),
                "ip": data.get("query"),
            }
    except Exception as e:
        return {"error": str(e)}


async def get_traffic(origin=None, destination=None) -> dict:
    weather = await get_weather()
    return {"weather_impact": weather.get("description", ""), "note": "Trafico general: sin datos en tiempo real"}
