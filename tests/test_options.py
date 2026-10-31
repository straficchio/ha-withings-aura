"""Options and diagnostics tests."""

from __future__ import annotations

from custom_components.withings_aura.const import CONF_POLL_INTERVAL, CONF_SLOW_POLL_INTERVAL
from custom_components.withings_aura.diagnostics import async_get_config_entry_diagnostics

from .test_entities import setup_aura


async def test_options_flow(hass, mock_entry) -> None:
    await setup_aura(hass, mock_entry)
    result = await hass.config_entries.options.async_init(mock_entry.entry_id)
    assert result["type"] == "form"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_POLL_INTERVAL: 60, CONF_SLOW_POLL_INTERVAL: 600},
    )
    assert result["type"] == "create_entry"
    assert mock_entry.options[CONF_POLL_INTERVAL] == 60
    assert mock_entry.options[CONF_SLOW_POLL_INTERVAL] == 600
    await hass.async_block_till_done()


async def test_diagnostics_redacts_secret(hass, mock_entry) -> None:
    await setup_aura(hass, mock_entry)
    diag = await async_get_config_entry_diagnostics(hass, mock_entry)
    assert diag["probe"]["secret"] == "**REDACTED**"
    assert diag["probe"]["mac"] == "00:11:22:33:44:55"
    assert diag["status"]["status"] == 0
    assert diag["lamp"]["brightness"] == 0
    assert diag["alarm_count"] == 10
    assert len(diag["alarms"]) == 2


async def test_unload(hass, mock_entry) -> None:
    await setup_aura(hass, mock_entry)
    assert await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state.value == "not_loaded"
