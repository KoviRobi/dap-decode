import struct
from enum import IntFlag, IntEnum
import typing as t

from commands import DapCommand, DapResponoseStatus


class Info(DapCommand):
    COMMAND_ID = 0x00

    class Capabilities(IntFlag):
        SWD = 1
        JTAG = 2
        SWO_UART = 4
        SWO_Manchester = 8
        Atomic = 16
        TestDomainTimer = 32
        SWO_StreamingTrace = 64
        UART = 128
        USB_COM = 256

    INFO_IDs: t.Dict[int, t.Tuple[str, t.Callable[[bytes], t.Any]]] = {
        0x01: ("Vendor name", lambda b: b.decode()),
        0x02: ("Product name", lambda b: b.decode()),
        0x03: ("Serial number", lambda b: b.decode()),
        0x04: ("CMSIS-DAP Protocol version", lambda b: b.decode()),
        0x05: ("Target device vendor", lambda b: b.decode()),
        0x06: ("Target device name", lambda b: b.decode()),
        0x07: ("Target board vendor", lambda b: b.decode()),
        0x08: ("Target board name", lambda b: b.decode()),
        0x09: ("Product firmware version", lambda b: b.decode()),
        0xF0: (
            "Capabilities",
            lambda b: Info.Capabilities.from_bytes(b, byteorder="little"),
        ),
        0xF1: ("Test domain timer", lambda b: struct.unpack("<xI", b)[0]),
        0xFB: ("UART receive buffer size", lambda b: struct.unpack("<I", b)[0]),
        0xFC: ("UART transmit buffer size", lambda b: struct.unpack("<I", b)[0]),
        0xFD: ("SWO trace buffer size", lambda b: struct.unpack("<I", b)[0]),
        0xFE: ("Maximum packet count", lambda b: struct.unpack("<B", b)[0]),
        0xFF: ("Maximum packet size", lambda b: struct.unpack("<H", b)[0]),
    }

    def decode_request(self, data: bytes) -> object:
        self.info_id = data[0]
        return self.INFO_IDs[self.info_id][0]

    def decode_response(self, data: bytes) -> object:
        self.resp_len = data[0]
        assert len(data[1:]) == self.resp_len
        return self.INFO_IDs[self.info_id][1](data[1:])


class HostStatus(DapCommand):
    COMMAND_ID = 0x01

    def decode_request(self, data: bytes) -> object:
        type = "connect" if data[0] == 0 else "running"
        dir = "off" if data[0] == 0 else "on"
        return (type, dir)

    def decode_response(self, data: bytes) -> object:
        assert data[0] == 0x00
        return ()


class Connect(DapCommand):
    COMMAND_ID = 0x02

    class Port(IntEnum):
        Default = 0
        SWD = 1
        JTAG = 2

    def decode_request(self, data: bytes) -> object:
        return Connect.Port.from_bytes(data[1:2])

    def decode_response(self, data: bytes) -> object:
        if data[0] == 0:
            return DapResponoseStatus.Error
        else:
            return Connect.Port.from_bytes(data)


class Disconnect(DapCommand):
    COMMAND_ID = 0x03

    def decode_response(self, data: bytes) -> object:
        return DapResponoseStatus.from_bytes(data)


class WriteABORT(DapCommand):
    COMMAND_ID = 0x08

    def decode_response(self, data: bytes) -> object:
        return DapResponoseStatus.from_bytes(data)


class Delay(DapCommand):
    COMMAND_ID = 0x09

    def decode_response(self, data: bytes) -> object:
        return DapResponoseStatus.from_bytes(data)


class ResetTarget(DapCommand):
    COMMAND_ID = 0x0A

    def decode_response(self, data: bytes) -> object:
        return (DapResponoseStatus.from_bytes(data[:1]), data[2])


commands = (
    Info,
    HostStatus,
    Connect,
    Disconnect,
    WriteABORT,
    Delay,
    ResetTarget,
)
