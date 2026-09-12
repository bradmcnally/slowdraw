#!/usr/bin/env python3
"""Start a short unplugged M5Paper RTC power-on test."""

import argparse
import os
import time

import capture


def main():
    parser = argparse.ArgumentParser(
        description="Arm an RTC wake test, then unplug USB when instructed."
    )
    parser.add_argument("minutes", nargs="?", type=int, default=2)
    parser.add_argument("--port")
    parser.add_argument("--no-reset", action="store_true")
    parser.add_argument("--status", action="store_true",
                        help="report the most recently completed wake test")
    args = parser.parse_args()
    if not 1 <= args.minutes <= 30:
        parser.error("minutes must be between 1 and 30")

    port = args.port or capture.find_port()
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        capture.configure(fd)
        if not args.no_reset:
            capture.reset_device(fd)
            time.sleep(0.4)
        if args.status:
            command = b"WAKE_STATUS\n"
            marker = b"SDWAKESTATUS "
            deadline = time.monotonic() + 90
            next_request = time.monotonic()
            data = bytearray()
            while marker not in data or b"\n" not in data[data.index(marker):]:
                if time.monotonic() > deadline:
                    raise SystemExit("The device did not report wake-test status.")
                if time.monotonic() >= next_request:
                    os.write(fd, command)
                    next_request = time.monotonic() + 0.75
                data.extend(capture.read_some(fd))
            result = data[data.index(marker):].splitlines()[0].decode()
            print(result)
            return
        command = f"WAKE_TEST {args.minutes}\n".encode()
        marker = b"SDACCEPT WAKE_TEST"
        deadline = time.monotonic() + 90
        next_request = time.monotonic()
        data = bytearray()
        while marker not in data or b"\n" not in data[data.index(marker):]:
            if time.monotonic() > deadline:
                raise SystemExit("The device did not accept the wake test.")
            if time.monotonic() >= next_request:
                os.write(fd, command)
                next_request = time.monotonic() + 0.75
            data.extend(capture.read_some(fd))
        accepted = data[data.index(marker):].splitlines()[0].decode()
    finally:
        os.close(fd)
    print(accepted)
    print("Wake test armed. Unplug USB now and wait for the displayed target time.")


if __name__ == "__main__":
    main()
