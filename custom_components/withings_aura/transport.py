"""Async TCP transport for the Aura WPP bridge."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable

from .const import CMD_DISCONNECT, DEFAULT_PORT
from .exceptions import AuraConnectionError, AuraTimeoutError
from .protocol import AuraProtocolError, decode_wpp, encode_request, extract_frag_frames

_LOGGER = logging.getLogger(__name__)


class AuraBridge:
    """One connection to the Aura's WPP-over-TCP bridge."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        *,
        timeout: float = 5.0,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._request_lock = asyncio.Lock()
        self._pending: dict[int, asyncio.Future[tuple[int, bytes]]] = {}
        self._buffer = bytearray()
        self._closing = False

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    async def async_connect(self) -> None:
        """Open the TCP connection and start the reader."""
        await self.async_close(disconnect=False)
        self._closing = False
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=self.timeout
            )
        except (TimeoutError, OSError) as err:
            self._writer = None
            self._reader = None
            raise AuraConnectionError(f"cannot connect to {self.host}:{self.port}: {err}") from err
        self._buffer.clear()
        self._reader_task = asyncio.create_task(self._read_loop())
        _LOGGER.debug("Connected to Aura bridge at %s:%s", self.host, self.port)

    async def async_close(self, *, disconnect: bool = True) -> None:
        """Close the connection, optionally sending DISCONNECT first."""
        if (
            disconnect
            and self.connected
            and self._reader_task is not None
            and not self._reader_task.done()
        ):
            try:
                await self.async_request(CMD_DISCONNECT, timeout=1.0)
            except Exception:  # noqa: BLE001 - best effort
                pass
        self._closing = True
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._reader_task = None
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass
            self._writer = None
        self._reader = None
        self._buffer.clear()

    async def _read_loop(self) -> None:
        assert self._reader is not None
        try:
            while True:
                data = await self._reader.read(4096)
                if not data:
                    raise AuraConnectionError("bridge closed the connection")
                self._buffer.extend(data)
                for payload in extract_frag_frames(self._buffer):
                    message = decode_wpp(payload)
                    future = self._pending.get(message.command)
                    if future is not None and not future.done():
                        future.set_result((message.command, message.body))
                    else:
                        _LOGGER.debug(
                            "Unsolicited WPP command 0x%04x: %s",
                            message.command,
                            message.body.hex(),
                        )
        except asyncio.CancelledError:
            raise
        except (AuraProtocolError, AuraConnectionError, OSError) as err:
            if not self._closing:
                _LOGGER.debug("Aura reader stopped: %s", err)
                self._fail_pending(err)
        except Exception as err:  # noqa: BLE001
            if not self._closing:
                _LOGGER.exception("Unexpected Aura reader error")
                self._fail_pending(err)

    def _fail_pending(self, err: Exception) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_exception(AuraConnectionError(str(err)))
        self._pending.clear()
        if self._writer is not None:
            self._writer.close()
            self._writer = None

    async def async_request(
        self,
        command: int,
        body: bytes = b"",
        *,
        timeout: float | None = None,
        expect: Iterable[int] | None = None,
    ) -> tuple[int, bytes]:
        """Send one WPP command and wait for its reply."""
        expected = tuple(expect) if expect is not None else (command,)
        async with self._request_lock:
            if not self.connected:
                await self.async_connect()
            assert self._writer is not None
            future: asyncio.Future[tuple[int, bytes]] = asyncio.get_running_loop().create_future()
            for expected_command in expected:
                self._pending[expected_command] = future
            try:
                self._writer.write(encode_request(command, body))
                await self._writer.drain()
                try:
                    return await asyncio.wait_for(future, timeout=timeout or self.timeout)
                except TimeoutError as err:
                    raise AuraTimeoutError(
                        f"no reply to WPP command 0x{command:04x} within {timeout or self.timeout}s"
                    ) from err
            except (OSError, AuraConnectionError) as err:
                raise AuraConnectionError(str(err)) from err
            finally:
                for expected_command in expected:
                    self._pending.pop(expected_command, None)
