"""Shared test fixtures."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.withings_aura.const import (
    CONF_FIRMWARE,
    CONF_HOST,
    CONF_MAC,
    CONF_PORT,
    DOMAIN,
)

from .fake_bridge import FakeBridge

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations, socket_enabled):
    """Enable loading custom integrations and localhost sockets in all tests."""
    yield


@pytest.fixture
async def fake_bridge():
    """Run a fake Aura bridge."""
    bridge = FakeBridge()
    await bridge.start()
    try:
        yield bridge
    finally:
        await bridge.stop()


@pytest.fixture
def mock_entry(fake_bridge: FakeBridge) -> MockConfigEntry:
    """A config entry pointing at the fake bridge."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Withings Aura (00:11:22:33:44:55)",
        unique_id="00:11:22:33:44:55",
        data={
            CONF_HOST: fake_bridge.host,
            CONF_PORT: fake_bridge.port,
            CONF_MAC: "00:11:22:33:44:55",
            CONF_FIRMWARE: "1301",
        },
    )
