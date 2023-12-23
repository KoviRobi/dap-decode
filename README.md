This is a simple and incomplete decoder for the [CMSIS-DAP] protocol
(an open-source USB protocol for interacting with JTAG and SWD
debuggers). I wrote it when working on [rp2040-selfdebug]. By default
it reads in USBMON packets. To use:

```console
$ sudo modprobe usbmon

# Find which USB bus we are on for USBMON
$ lsusb -d 04b4:f138
Bus 002 Device 016: ID 04b4:f138 Cypress Semiconductor Corp. CMSIS-DAP

# Open the stream and forward it to this script (this way you don't need to run
# this script/python as root). Also the `16` is optional.
$ sudo cat /sys/kernel/debug/usb/usbmon/2u | python src/parse_usbmon.py 16
# Or if you have `pip install`ed it for some reason
$ sudo cat /sys/kernel/debug/usb/usbmon/2u | dap-decode 16
# You can save and load traces, though really the Unix `tee` command would
# already do this.
$ python src/parse_usbmon.py --load example-traces/probe-rs-info.cap
Info(Maximum packet size) -> Info(64)
Info(Maximum packet count) -> Info(8)
Info(Capabilities) -> Info(SWD|Atomic|USB_COM)
Connect(Default) -> Connect(Error)
Disconnect() -> Disconnect(Ok)
HostStatus(connect, off) -> HostStatus()
Connect(Default) -> Connect(SWD)
SWJ_Clock(1.000 MHz) -> SWJ_Clock(Ok)
TransferConfigure(idle_cycles=0, wait_retry=65535, match_retry=0) -> TransferConfigure(00)
SWD_Configure(turnaround=1, data_phase=False) -> SWD_Configure(Ok)
HostStatus(connect, off) -> HostStatus()
SWJ_Sequence(33:ff:ff:ff:ff:ff:ff:07) -> SWJ_Sequence(Ok)
SWJ_Sequence(10:9e:e7) -> SWJ_Sequence(Ok)
SWJ_Sequence(33:ff:ff:ff:ff:ff:ff:07) -> SWJ_Sequence(Ok)
SWJ_Sequence(03:00) -> SWJ_Sequence(Ok)
```

[CMSIS-DAP]: https://arm-software.github.io/CMSIS_5/latest/DAP/html/index.html
[rp2040-selfdebug]: https://github.com/KoviRobi/rp2040-selfdebug
