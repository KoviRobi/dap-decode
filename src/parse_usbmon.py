"""
Simple script to parse Linux usbmon "u" format (see
https://www.kernel.org/doc/html/v5.14/usb/usbmon.html)

To use

# Make sure the Linux usbmon module is loaded
$ sudo modprobe usbmon

# Find which USB bus we are on for USBMON
$ lsusb -d 04b4:f138
Bus 002 Device 016: ID 04b4:f138 Cypress Semiconductor Corp. CMSIS-DAP

# Open the stream and forward it to this script (this way you don't need to run
# this script/python as root)
$ sudo cat /sys/kernel/debug/usb/usbmon/2u | python parse_usbmon.py 16
"""

from __future__ import annotations

import logging
import re
import typing as t
from argparse import ArgumentParser
from contextlib import ExitStack
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from commands import Decoder
import general_commands
import swj_commands
import swd_commands
import transfer_commands


logger = logging.getLogger(__name__)


class UsbMonError(RuntimeError):
    pass


class StrEnumEvalRepr(StrEnum):
    """StrEnum which has `x = eval(repr(x))`"""

    @classmethod
    def __init_subclass__(cls, name: str):
        cls.__name__ = name

    def __repr__(self) -> str:
        return f"{type(self).__name__}('{StrEnum.__str__(self)}')"

    def __str__(self) -> str:
        return StrEnum.__repr__(self)


@dataclass
class UsbEvent:
    urb_tag: str
    timestamp: int
    event_type: str
    type: UsbEvent.Type
    direction: UsbEvent.Direction
    bus: int
    device: int
    endpoint: int
    status: str
    length: int
    data: t.Optional[bytes]

    _USBMON_RE = re.compile(
        r"""
        # URB Tag. This is used to identify URBs, and is normally an in-kernel
        # address of the URB structure in hexadecimal, but can be a sequence number
        # or any other unique string, within reason.
        (?P<urb_tag>\S+)
        # Timestamp in microseconds, a decimal number. The timestamp’s resolution
        # depends on available clock, and so it can be much worse than a microsecond
        # (if the implementation uses jiffies, for example).
        \s+ (?P<timestamp>\S+)
        # Event Type. This type refers to the format of the event, not URB type.
        # Available types are: S - submission, C - callback, E - submission error.
        \s+ (?P<event_type>\S+)
        # “Address” word (formerly a “pipe”). It consists of four fields, separated
        # by colons: URB type and direction, Bus number, Device address, Endpoint
        # number. Type and direction are encoded with two bytes in the following
        # manner:
        # - Ci/Co: Control input and output
        # - Zi/Zo: Isochronous input and output
        # - Ii/Io: Interrupt input and output
        # - Bi/Bo: Bulk input and output
        # Bus number, Device address, and Endpoint are decimal numbers, but they
        # may have leading zeros, for the sake of human readers.
        \s+ (?P<urb_type>.)
            (?P<urb_direction>.)
        :   (?P<bus_number>\d+)
        :   (?P<device_address>\d+)
        :   (?P<endpoint_number>\d+)

        # URB Status word. This is either a letter, or several numbers separated by
        # colons: URB status, interval, start frame, and error count. Unlike the
        # “address” word, all fields save the status are optional. Interval is
        # printed only for interrupt and isochronous URBs. Start frame is printed
        # only for isochronous URBs. Error count is printed only for isochronous
        # callback events.
        #
        # The status field is a decimal number, sometimes negative, which represents
        # a “status” field of the URB. This field makes no sense for submissions, but
        # is present anyway to help scripts with parsing. When an error occurs, the
        # field contains the error code.
        #
        # In case of a submission of a Control packet, this field contains a Setup
        # Tag instead of an group of numbers. It is easy to tell whether the Setup
        # Tag is present because it is never a number. Thus if scripts find a set of
        # numbers in this word, they proceed to read Data Length (except for
        # isochronous URBs). If they find something else, like a letter, they read
        # the setup packet before reading the Data Length or isochronous descriptors.
        #
        # Setup packet, if present, consists of 5 words: one of each for
        # bmRequestType, bRequest, wValue, wIndex, wLength, as specified by the USB
        # Specification 2.0. These words are safe to decode if Setup Tag was ‘s’.
        # Otherwise, the setup packet was present, but not captured, and the fields
        # contain filler.
        #
        # Number of isochronous frame descriptors and descriptors themselves. If an
        # Isochronous transfer event has a set of descriptors, a total number of them
        # in an URB is printed first, then a word per descriptor, up to a total of 5.
        # The word consists of 3 colon-separated decimal numbers for status, offset,
        # and length respectively. For submissions, initial length is reported. For
        # callbacks, actual length is reported.
        \s+ (?P<urb_status>\S+)

        # Data Length. For submissions, this is the requested length. For callbacks,
        # this is the actual length.
        \s+ (?P<data_length>\S+)

        # Data tag. The usbmon may not always capture data, even if length is
        # nonzero. The data words are present only if this tag is ‘=’.
        \s+ (?P<data_tag>\S+)

        # Data words follow, in big endian hexadecimal format. Notice that they are
        # not machine words, but really just a byte stream split into words to make
        # it easier to read. Thus, the last word may contain from one to four bytes.
        # The length of collected data is limited and can be less than the data
        # length reported in the Data Length word. In the case of an Isochronous
        # input (Zi) completion where the received data is sparse in the buffer, the
        # length of the collected data can be greater than the Data Length value
        # (because Data Length counts only the bytes that were received whereas the
        # Data words contain the entire transfer buffer).
        (\s+ (?P<data>.+))?
        """,
        flags=re.VERBOSE,
    )

    class Type(StrEnumEvalRepr, name="UsbEvent.Type"):
        Control = "C"
        Isochronous = "Z"
        Interrupt = "I"
        Bulk = "B"

    class Direction(StrEnumEvalRepr, name="UsbEvent.Direction"):
        In = "i"
        Out = "o"

    @classmethod
    def from_usbmon(cls, usbmon_line: str) -> t.Optional[UsbEvent]:
        match = cls._USBMON_RE.match(usbmon_line)
        if match is None:
            raise UsbMonError("Bad usbmon line", usbmon_line)
        event = match.groupdict()
        if event["urb_status"] != "s":
            return UsbEvent(
                urb_tag=event["urb_tag"],
                timestamp=int(event["timestamp"]),
                event_type=event["event_type"],
                type=UsbEvent.Type(event["urb_type"]),
                direction=UsbEvent.Direction(event["urb_direction"]),
                bus=int(event["bus_number"]),
                device=int(event["device_address"]),
                endpoint=int(event["endpoint_number"]),
                status=event["urb_status"],
                length=int(event["data_length"]),
                data=bytes.fromhex(event["data"]) if event["data_tag"] == "=" else None,
            )

    def __str__(self) -> str:
        ret = ""
        ret += f"{self.bus}:{self.device}:{self.endpoint}"
        ret += f" {self.type.name}"
        if self.direction == UsbEvent.Direction.Out:
            ret += " >"
        if self.direction == UsbEvent.Direction.In:
            ret += " <"
        if self.data is not None:
            ret += f" {self.data.hex(':')}"
        else:
            ret += f"({self.length})"
        return ret


def usb_event_stream(capture: t.Optional[Path]) -> t.Iterator[UsbEvent]:
    with ExitStack() as exit_stack:
        fp = None
        if capture is not None:
            fp = exit_stack.enter_context(capture.open("w"))
        while True:
            try:
                line = input()
                event = UsbEvent.from_usbmon(line)
                if fp is not None:
                    print(repr(event), file=fp)
                if event is not None:
                    yield event
            except UsbMonError as e:
                print("UsbMonError", e)


def load_file(file: Path) -> t.Iterator[UsbEvent]:
    with file.open("r") as fp:
        while True:
            line = fp.readline()
            if line == "":
                break
            yield t.cast(UsbEvent, eval(line))


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("device", nargs="?", type=int)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--load", type=Path)
    args = parser.parse_args()

    decoder = Decoder(
        *general_commands.commands,
        *swj_commands.commands,
        *swd_commands.commands,
        *transfer_commands.commands,
    )

    assert not (args.load and args.save)

    if args.load is None:
        event_stream = usb_event_stream(args.save)
    else:
        event_stream = load_file(args.load)
    bulk_data_events = (
        event
        for event in event_stream
        if event.type == UsbEvent.Type.Bulk
        and (args.device is None or event.device == args.device)
        and event.data is not None
    )
    request = None
    for event in bulk_data_events:
        assert event.data is not None
        if request is not None:
            if event.direction == UsbEvent.Direction.Out:
                print(request)
            else:
                request.attach_response(event.data)
                print(request)
                request = None
        if event.direction == UsbEvent.Direction.Out:
            request = decoder.decode_request(event.data)


if __name__ == "__main__":
    main()
