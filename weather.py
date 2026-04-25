import logging

import httpx

import config

logger = logging.getLogger(__name__)

_OWM_URL = "https://api.openweathermap.org/data/2.5/weather"


async def fetch_weather() -> dict | None:
    """Fetch current weather for Kiryat Ono. Returns dict or None on any failure."""
    params = {
        "lat": config.OWM_LAT,
        "lon": config.OWM_LON,
        "units": "metric",
        "appid": config.OWM_API_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(_OWM_URL, params=params)
            response.raise_for_status()
            data = response.json()
            return {
                "temp_c": data["main"]["temp"],
                "humidity_pct": data["main"]["humidity"],
                "pressure_hpa": data["main"]["pressure"],
            }
    except Exception as exc:
        logger.error("Weather fetch failed: %s", exc)
        return None
