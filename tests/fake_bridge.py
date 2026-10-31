"""A fake Aura TCP bridge for tests."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable

from custom_components.withings_aura.protocol import (
    decode_wpp,
    extract_frag_frames,
    frag,
    tlv,
    wpp,
)

PROBE_BODY = bytes.fromhex(
    "01010041"
    "00000000"
    "03575344"
    "1130303a31313a32323a33333a34343a3535"
    "1030303131323233333434353536363737"
    "0000000c"
    "053930303035"
    "ffffffff"
    "00000515"
    "ffffffff"
)

STATUS_BODY = bytes.fromhex("0907000100090f000100091d000400000000")
LAMP_BODY = bytes.fromhex("09140006000000000000090c000100")
SETTINGS_BODY = bytes.fromhex("090d00020137080b000101")
ALARMS_BODY = bytes.fromhex(
    "05120007062d3e0000000f"
    "0916000401023436"
    "0916001602143138343436373434303733373039353531363135"
    "09160003030131"
    "0512000707003e00000014"
    "0916001601143138343436373434303733373039353531363135"
    "0916001602143138343436373434303733373039353531363135"
    "09160003030131"
)
PROGRAM_SETTINGS_BODY = bytes.fromhex("0916000401023530091600040202353009160003030131")
PROGRAM_INFO_BODY = bytes.fromhex("090900050201010100")

DEFAULT_RESPONSES = {
    257: PROBE_BODY,
    2311: STATUS_BODY,
    2318: LAMP_BODY,
    2320: SETTINGS_BODY,
    293: ALARMS_BODY,
    298: tlv(295, b"\x0a"),
    2330: tlv(2329, b"\x00"),
    2310: PROGRAM_SETTINGS_BODY,
    2313: PROGRAM_INFO_BODY,
}


class FakeBridge:
    """Tiny WPP server that replays captured responses."""

    def __init__(self, responses: dict[int, bytes] | None = None) -> None:
        self.responses = dict(DEFAULT_RESPONSES)
        if responses:
            self.responses.update(responses)
        self.response_commands: dict[int, int] = {}
        self.requests: list[tuple[int, bytes]] = []
        self.server: asyncio.AbstractServer | None = None
        self.host = "127.0.0.1"
        self.port = 0
        self._writers: set[asyncio.StreamWriter] = set()
        self.on_request: Callable[[int, bytes], Awaitable[None]] | None = None

    async def start(self) -> tuple[str, int]:
        self.server = await asyncio.start_server(self._handle, self.host, 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self.host, self.port

    async def stop(self) -> None:
        for writer in list(self._writers):
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
        self._writers.clear()
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
            self.server = None

    def last_request(self, command: int) -> bytes | None:
        for cmd, body in reversed(self.requests):
            if cmd == command:
                return body
        return None

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._writers.add(writer)
        buffer = bytearray()
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    return
                buffer.extend(data)
                while len(buffer) >= 2:
                    length = int.from_bytes(buffer[:2], "big")
                    if len(buffer) < 2 + length:
                        break
                    frame = bytes(buffer[2 : 2 + length])
                    del buffer[: 2 + length]
                    payloads = extract_frag_frames(bytearray(frame))
                    for payload in payloads:
                        message = decode_wpp(payload)
                        self.requests.append((message.command, message.body))
                        if self.on_request is not None:
                            await self.on_request(message.command, message.body)
                        response = self.responses.get(message.command, b"")
                        response_command = self.response_commands.get(
                            message.command, message.command
                        )
                        writer.write(frag(wpp(response_command, response)))
                        await writer.drain()
        except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
            pass
        finally:
            self._writers.discard(writer)
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
