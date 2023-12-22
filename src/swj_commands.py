import struct

from commands import DapCommand, DapResponoseStatus


class SWJ_Pins(DapCommand):
    COMMAND_ID = 0x10


class SWJ_Clock(DapCommand):
    COMMAND_ID = 0x11

    def decode_request(self, data: bytes) -> object:
        clock_hz: int = struct.unpack("<I", data)[0]
        if clock_hz < 1_000:
            return f"{clock_hz:0.3f} Hz"
        elif clock_hz < 1_000_000:
            return f"{clock_hz / 1_000:0.3f} kHz"
        elif clock_hz < 1_000_000_000:
            return f"{clock_hz / 1_000_000:0.3f} MHz"
        else:
            return f"{clock_hz / 1_000_000_000:0.3f} GHz"

    def decode_response(self, data: bytes) -> object:
        return DapResponoseStatus.from_bytes(data)


class SWJ_Sequence(DapCommand):
    COMMAND_ID = 0x12

    def decode_response(self, data: bytes) -> object:
        return DapResponoseStatus.from_bytes(data)


commands = (
    SWJ_Pins,
    SWJ_Clock,
    SWJ_Sequence,
)
