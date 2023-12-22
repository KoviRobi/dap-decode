import struct

from commands import DapCommand


class TransferConfigure(DapCommand):
    COMMAND_ID = 0x04

    def decode_request(self, data: bytes) -> object:
        return {
            "idle_cycles": struct.unpack_from("<B", data, 0)[0],
            "wait_retry": struct.unpack_from("<H", data, 1)[0],
            "match_retry": struct.unpack_from("<H", data, 3)[0],
        }


class Transfer(DapCommand):
    COMMAND_ID = 0x05

    def decode_request(self, data: bytes) -> object:
        decoded = [f"DAP Index {data[0]}"]
        xfer_count = data[1]
        offset = 2
        self.reads = 0
        self.timestamp = False
        for i in range(xfer_count):
            (xfer_req,) = struct.unpack_from("<B", data, offset)
            offset += 1
            ap = "AP" if xfer_req & 1 else "DP"
            read = xfer_req & 2
            a32 = xfer_req & 0xC
            value_match = xfer_req & 0x10
            mask_match = xfer_req & 0x20
            self.timestamp = self.timestamp or xfer_req & 0x40
            timestamp = " (TS)" if xfer_req & 0x40 else ""
            if not read:
                (value,) = struct.unpack_from("<I", data, offset)
                offset += 4
                decoded.append(f"{ap} write @ 0x{a32:X} = 0x{value:X}{timestamp}")
            elif value_match:
                (value,) = struct.unpack_from("<I", data, offset)
                offset += 4
                decoded.append(f"{ap} read @ 0x{a32:X} value 0x{value:X}{timestamp}")
                self.reads += 1
            elif mask_match:
                (value,) = struct.unpack_from("<I", data, offset)
                offset += 4
                decoded.append(f"{ap} read @ 0x{a32:X} mask 0x{value:X}{timestamp}")
                self.reads += 1
            else:
                decoded.append(f"{ap} read @ 0x{a32:X}{timestamp}")
                self.reads += 1
        return decoded

    def decode_response(self, data: bytes) -> object:
        xfer_count = data[0]

        last_xfer = data[1]
        ack = last_xfer & 0x7
        err = last_xfer & 0x8
        mismatch = last_xfer & 0x10

        status = ""
        if ack == 7:
            status += "No-ack"
        elif ack == 4:
            status += "Fault"
        elif ack == 2:
            status += "Wait"
        elif ack == 1:
            status += "Ok"
        else:
            status += "???"

        if err:
            status += ", error"

        if mismatch:
            status += ", mismatch"

        response = [status]

        assert not self.timestamp, "Timestamps not supported yet"

        offset = 2
        for i in range(self.reads):
            (value,) = struct.unpack_from("<I", data, offset)
            offset += 4
            response.append(f"0x{value:X}")

        return response


class TransferBlock(DapCommand):
    COMMAND_ID = 0x06

    def decode_request(self, data: bytes) -> object:
        decoded = [f"DAP Index {data[0]}"]
        offset = 1
        (xfer_count,) = struct.unpack_from("<H", data, offset)
        offset += 2
        self.reads = 0
        (xfer_req,) = struct.unpack_from("<B", data, offset)
        offset += 1
        ap = "AP" if xfer_req & 1 else "DP"
        read = xfer_req & 2
        a32 = xfer_req & 0xC
        if not read:
            fmt = f"{ap} write*{xfer_count} @ 0x{a32:X} = "
            for i in range(xfer_count):
                (value,) = struct.unpack_from("<I", data, offset)
                offset += 4
                if i > 0:
                    fmt += ", "
                fmt += f"0x{value:X}"
            decoded.append(fmt)
        else:
            decoded.append(f"{ap} read*{xfer_count} @ 0x{a32:X}")
            self.reads = xfer_count
        return decoded

    def decode_response(self, data: bytes) -> object:
        (xfer_count,) = struct.unpack_from("<H", data)
        offset = 2

        last_xfer = data[offset]
        offset += 1
        ack = last_xfer & 0x7
        err = last_xfer & 0x8

        status = ""
        if ack == 7:
            status += "No-ack"
        elif ack == 4:
            status += "Fault"
        elif ack == 2:
            status += "Wait"
        elif ack == 1:
            status += "Ok"
        else:
            status += "???"

        if err:
            status += ", error"

        response = [status]

        for i in range(self.reads):
            (value,) = struct.unpack_from("<I", data, offset)
            offset += 4
            response.append(f"0x{value:X}")

        return response


class TransferAbort(DapCommand):
    COMMAND_ID = 0x07

    def decode_response(self, data: bytes) -> object:
        assert False, "TransferAbort should have no response"


commands = (
    TransferConfigure,
    Transfer,
    TransferBlock,
    TransferAbort,
)
