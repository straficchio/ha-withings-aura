"""Config flow tests for the Withings Aura integration."""

from __future__ import annotations

from ipaddress import IPv4Address

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.withings_aura.const import CONF_MAC, DOMAIN, ZEROCONF_TYPE


async def test_user_flow(hass, fake_bridge) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: fake_bridge.host, CONF_PORT: fake_bridge.port},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_MAC] == "00:11:22:33:44:55"
    assert result["data"][CONF_HOST] == fake_bridge.host


async def test_user_flow_cannot_connect(hass) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "127.0.0.1", CONF_PORT: 1}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_zeroconf_flow(hass, fake_bridge) -> None:
    info = ZeroconfServiceInfo(
        ip_address=IPv4Address(fake_bridge.host),
        ip_addresses=[IPv4Address(fake_bridge.host)],
        port=fake_bridge.port,
        hostname="aura.local.",
        type=ZEROCONF_TYPE,
        name="Withings Aura",
        properties={"mac": "00:11:22:33:44:55", "version": "1301"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=info
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_MAC] == "00:11:22:33:44:55"


async def test_duplicate_zeroconf_aborts(hass, fake_bridge) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="00:11:22:33:44:55",
        data={CONF_HOST: fake_bridge.host, CONF_PORT: fake_bridge.port},
    )
    entry.add_to_hass(hass)
    info = ZeroconfServiceInfo(
        ip_address=IPv4Address(fake_bridge.host),
        ip_addresses=[IPv4Address(fake_bridge.host)],
        port=fake_bridge.port,
        hostname="aura.local.",
        type=ZEROCONF_TYPE,
        name="Withings Aura",
        properties={"mac": "00:11:22:33:44:55"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
