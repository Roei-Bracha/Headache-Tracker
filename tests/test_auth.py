import os
import pytest
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("OWM_API_KEY", "test")
os.environ.setdefault("AUTHORIZED_USER_ID", "42")

from auth import authorized


async def test_authorized_user_passes_through():
    handler_called = False

    @authorized
    async def handler(update, context):
        nonlocal handler_called
        handler_called = True

    update = MagicMock()
    update.effective_user.id = 42
    await handler(update, MagicMock())
    assert handler_called


async def test_unauthorized_user_is_silently_dropped():
    handler_called = False

    @authorized
    async def handler(update, context):
        nonlocal handler_called
        handler_called = True

    update = MagicMock()
    update.effective_user.id = 999
    result = await handler(update, MagicMock())
    assert not handler_called
    assert result is None
