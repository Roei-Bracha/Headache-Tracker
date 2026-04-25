import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("OWM_API_KEY", "test-owm")
os.environ.setdefault("AUTHORIZED_USER_ID", "42")

import weather


async def test_fetch_weather_success():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "main": {"temp": 22.5, "humidity": 60, "pressure": 1013}
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("weather.httpx.AsyncClient", return_value=mock_client):
        result = await weather.fetch_weather()

    assert result == {"temp_c": 22.5, "humidity_pct": 60, "pressure_hpa": 1013}


async def test_fetch_weather_network_error_returns_none():
    import httpx

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))

    with patch("weather.httpx.AsyncClient", return_value=mock_client):
        result = await weather.fetch_weather()

    assert result is None


async def test_fetch_weather_non_200_returns_none():
    import httpx

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock()
    )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("weather.httpx.AsyncClient", return_value=mock_client):
        result = await weather.fetch_weather()

    assert result is None
