#!/usr/bin/env python3
"""Capture Slow Draw's retained 4-bit framebuffer over USB serial."""

import argparse
import fcntl
import glob
import os
import struct
import termios
import time
import zlib


PORT_PATTERNS = (
    "/dev/cu.usbserial*",
    "/dev/cu.wchusbserial*",
    "/dev/cu.SLAB_USBtoUART*",
    "/dev/ttyUSB*",
    "/dev/ttyACM*",
)


def find_port():
    ports = []
    for pattern in PORT_PATTERNS:
        ports.extend(glob.glob(pattern))
    if not ports:
        raise SystemExit("No USB serial device found. Connect and power on the M5Paper.")
    return sorted(ports)[0]


def configure(fd):
    attrs = termios.tcgetattr(fd)
    attrs[0] = 0
    attrs[1] = 0
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    attrs[3] = 0
    attrs[4] = termios.B115200
    attrs[5] = termios.B115200
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 1
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    termios.tcflush(fd, termios.TCIOFLUSH)


def read_some(fd, count=4096):
    try:
        return os.read(fd, count)
    except BlockingIOError:
        time.sleep(0.01)
        return b""


def reset_device(fd):
    """Pulse ESP32 reset while keeping its boot-select line inactive."""
    dtr = struct.pack("I", termios.TIOCM_DTR)
    rts = struct.pack("I", termios.TIOCM_RTS)
    fcntl.ioctl(fd, termios.TIOCMBIC, dtr)
    fcntl.ioctl(fd, termios.TIOCMBIS, rts)
    time.sleep(0.12)
    fcntl.ioctl(fd, termios.TIOCMBIC, rts)


def request_frame(fd, timeout):
    data = bytearray()
    deadline = time.monotonic() + timeout
    next_request = time.monotonic()
    marker = b"SDFRAME "
    while marker not in data:
        if time.monotonic() > deadline:
            raise SystemExit("The device did not answer. Make sure capture firmware is flashed.")
        if time.monotonic() >= next_request:
            os.write(fd, b"CAPTURE\n")
            next_request = time.monotonic() + 0.75
        data.extend(read_some(fd))
    return bytes(data)


def request_variant(fd, variant, timeout=30):
    data = bytearray()
    deadline = time.monotonic() + timeout
    next_request = time.monotonic()
    marker = f"SDVARIANT {variant}".encode()
    command = f"VARIANT {variant}\n".encode()
    while marker not in data:
        if time.monotonic() > deadline:
            raise SystemExit("The device did not confirm the requested variant.")
        if time.monotonic() >= next_request:
            os.write(fd, command)
            next_request = time.monotonic() + 8.0
        data.extend(read_some(fd))


def request_seed(fd, seed, timeout=30):
    data = bytearray()
    deadline = time.monotonic() + timeout
    next_request = time.monotonic()
    marker = f"SDSEED {seed:08X}".encode()
    command = f"SEED {seed:08X}\n".encode()
    while marker not in data:
        if time.monotonic() > deadline:
            raise SystemExit("The device did not confirm the requested seed.")
        if time.monotonic() >= next_request:
            os.write(fd, command)
            next_request = time.monotonic() + 8.0
        data.extend(read_some(fd))


def read_exact(fd, initial, count, timeout=120):
    data = bytearray(initial)
    deadline = time.monotonic() + timeout
    while len(data) < count:
        if time.monotonic() > deadline:
            raise SystemExit(f"Capture stopped early ({len(data)} of {count} bytes).")
        data.extend(read_some(fd, min(8192, count - len(data))))
    return bytes(data[:count])


def png_chunk(kind, payload):
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def save_png(path, width, height, packed):
    scanlines = bytearray()
    stride = width // 2
    for y in range(height):
        scanlines.append(0)
        for value in packed[y * stride:(y + 1) * stride]:
            scanlines.append((value >> 4) * 17)
            scanlines.append((value & 15) * 17)
    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", header)
    png += png_chunk(b"IDAT", zlib.compress(bytes(scanlines), 9))
    png += png_chunk(b"IEND", b"")
    with open(path, "wb") as output:
        output.write(png)


def next_capture_path():
    number = 1
    while True:
        path = f"slow-draw-{number:03d}.png"
        if not os.path.exists(path):
            return path
        number += 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?")
    parser.add_argument("--port")
    parser.add_argument("--no-reset", action="store_true", help="try capturing without resetting the sleeping device")
    parser.add_argument("--variant", type=int, help="render and select this same-day variant before capture")
    parser.add_argument("--seed", type=lambda value: int(value, 16), help="temporarily recreate an eight-digit hexadecimal seed")
    args = parser.parse_args()
    if args.variant is not None and args.seed is not None:
        parser.error("--variant and --seed cannot be used together")
    output_path = args.output or next_capture_path()
    port = args.port or find_port()

    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        configure(fd)
        if not args.no_reset:
            reset_device(fd)
            time.sleep(0.4)
        if args.variant is not None:
            request_variant(fd, args.variant)
        elif args.seed is not None:
            request_seed(fd, args.seed)
        response = request_frame(fd, 20)
        header_start = response.index(b"SDFRAME ")
        while b"\n" not in response[header_start:]:
            response += read_some(fd)
        header_end = response.index(b"\n", header_start)
        _, width, height, depth, length = response[header_start:header_end].decode().split()
        width, height, depth, length = map(int, (width, height, depth, length))
        if depth != 4 or length != width * height // 2:
            raise SystemExit("Unexpected framebuffer format from device.")
        packed = read_exact(fd, response[header_end + 1:], length)
        save_png(output_path, width, height, packed)
        print(f"Saved {width}x{height} capture from {port} to {output_path}")
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
