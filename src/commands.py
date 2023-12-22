from __future__ import annotations

import enum
import struct
import typing as t


class DapResponoseStatus(enum.IntEnum):
    Ok = 0x00
    Error = 0xFF


class DapCommand(t.Protocol):
    """
    Superclass of all DAP commands
    """

    COMMAND_ID: int
    data: object
    response: t.Optional[object] = None

    @classmethod
    def __repr_data__(cls, data) -> str:
        if isinstance(data, list) or isinstance(data, tuple):
            return ", ".join(cls.__repr_data__(d) for d in data)
        elif isinstance(data, dict):
            return ", ".join(
                cls.__repr_data__(k) + "=" + cls.__repr_data__(v)
                for k, v in data.items()
            )
        elif isinstance(data, bytes):
            return data.hex(":")
        elif isinstance(data, str):
            return data
        elif isinstance(data, enum.Enum):
            return data.name
        else:
            return repr(data)

    def __repr__(self) -> str:
        ret = type(self).__name__
        ret += "("
        ret += self.__repr_data__(self.data)
        ret += ")"

        if self.response is not None:
            ret += " -> "
            ret += type(self).__name__
            ret += "("
            ret += self.__repr_data__(self.response)
            ret += ")"

        return ret

    def decode_request(self, data: bytes) -> object:
        return data

    def decode_response(self, data: bytes) -> object:
        return data

    def attach_response(self, data: bytes) -> None:
        assert data[0] == self.COMMAND_ID
        self.response = self.decode_response(data[1:])

    def __init__(self, data: bytes) -> None:
        assert data[0] == self.COMMAND_ID
        self.data = self.decode_request(data[1:])


class Decoder:
    def __init__(self, *commands: t.Type[DapCommand]):
        self._cmd_id_map: t.Dict[int, t.Type[DapCommand]] = {
            cls.COMMAND_ID: cls for cls in commands
        }

    def decode_request(self, data: bytes, offset=0) -> DapCommand:
        cmd_id = data[offset]
        return self._cmd_id_map[cmd_id](data[offset:])
