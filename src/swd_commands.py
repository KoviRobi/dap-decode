from commands import DapCommand, DapResponoseStatus


class SWD_Configure(DapCommand):
    COMMAND_ID = 0x13

    def decode_request(self, data: bytes) -> object:
        return {
            "turnaround": (data[0] & 3) + 1,
            "data_phase": bool((data[0] >> 2) & 1),
        }

    def decode_response(self, data: bytes) -> object:
        return DapResponoseStatus.from_bytes(data)


class SWD_Sequence(DapCommand):
    COMMAND_ID = 0x1D

    def decode_response(self, data: bytes) -> object:
        if len(data) == 1:
            return DapResponoseStatus.from_bytes(data[0:1])
        else:
            return (DapResponoseStatus.from_bytes(data[0:1]), data[1:].hex(":"))


commands = (
    SWD_Configure,
    SWD_Sequence,
)
