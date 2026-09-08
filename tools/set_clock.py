#!/usr/bin/env python3
"""Set the Slow Draw hardware RTC from the computer over USB serial."""

import argparse
from datetime import datetime
import os
import time

import capture


def set_clock(fd, stamp, timeout=90):
    command = f"CLOCK {stamp}\n".encode()
    accepted = f"SDACCEPT CLOCK {stamp}".encode()
    ready = f"SDREADY CLOCK {stamp}".encode()
    data = bytearray()
    deadline = time.monotonic() + timeout
    next_request = time.monotonic()
    while accepted not in data:
        if time.monotonic() > deadline:
            raise SystemExit(
                "The device did not recognize the clock command. Flash the latest firmware."
            )
        if time.monotonic() >= next_request:
            os.write(fd, command)
            next_request = time.monotonic() + 0.75
        data.extend(capture.read_some(fd))
    while ready not in data:
        if time.monotonic() > deadline:
            raise SystemExit("The device accepted the clock but did not finish rendering.")
        data.extend(capture.read_some(fd))


def parse_datetime(value):
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "date/time must look like 2026-09-08T14:37 or 2026-09-08 14:37:00"
        ) from error
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def main():
    parser = argparse.ArgumentParser(
        description="Set the M5Paper RTC; defaults to the computer's local time."
    )
    parser.add_argument("--port")
    parser.add_argument("--datetime", type=parse_datetime, dest="date_time")
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="try setting the clock without resetting the sleeping device",
    )
    args = parser.parse_args()

    port = args.port or capture.find_port()
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        capture.configure(fd)
        if not args.no_reset:
            capture.reset_device(fd)
            time.sleep(0.4)
        requested = args.date_time or datetime.now()
        stamp = requested.strftime("%Y.%m.%d %H:%M:%S")
        set_clock(fd, stamp)
    finally:
        os.close(fd)
    print(f"Set Slow Draw clock on {port} to {stamp}")


if __name__ == "__main__":
    main()
