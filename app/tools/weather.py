"""Weather from Open-Meteo (free, no API key)."""
from __future__ import annotations

from functools import lru_cache

import httpx

# WMO weather codes -> words
CONDITIONS = {
    0: "clear skies", 1: "mostly clear skies", 2: "partly cloudy skies", 3: "overcast skies",
    45: "fog", 48: "fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "light showers", 81: "showers", 82: "heavy showers", 85: "snow showers", 86: "snow showers",
    95: "thunderstorms", 96: "thunderstorms with hail", 99: "thunderstorms with hail",
}


@lru_cache(maxsize=16)
def _locate(city: str) -> tuple[str, float, float]:
    found = httpx.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": city, "count": 1},
                      timeout=10).json().get("results")
    if not found:
        raise ValueError(f"I couldn't find a place called {city!r}.")
    return found[0]["name"], found[0]["latitude"], found[0]["longitude"]


def today(city: str) -> dict:
    name, lat, lon = _locate(city)
    data = httpx.get("https://api.open-meteo.com/v1/forecast", timeout=10, params={
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 1,
        "current": "temperature_2m,apparent_temperature,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
    }).json()
    now, day = data["current"], {k: v[0] for k, v in data["daily"].items()}
    return {
        "city": name,
        "now_celsius": round(now["temperature_2m"]),
        "feels_like_celsius": round(now["apparent_temperature"]),
        "now": CONDITIONS.get(now["weather_code"], "mixed weather"),
        "high_celsius": round(day["temperature_2m_max"]),
        "low_celsius": round(day["temperature_2m_min"]),
        "rain_chance_percent": day["precipitation_probability_max"],
        "today": CONDITIONS.get(day["weather_code"], "mixed weather"),
    }


def describe(weather: dict) -> str:
    text = (f"In {weather['city']} it's {weather['now_celsius']} degrees with {weather['now']}, "
            f"with a high of {weather['high_celsius']} today")
    if (weather["rain_chance_percent"] or 0) >= 50:
        text += f", and there's a {weather['rain_chance_percent']} percent chance of rain, so keep an umbrella handy"
    return text + "."
