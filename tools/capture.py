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
import re
import subprocess
import sys
import shutil
import tempfile


PORT_PATTERNS = (
    "/dev/cu.usbserial*",
    "/dev/cu.wchusbserial*",
    "/dev/cu.SLAB_USBtoUART*",
    "/dev/ttyUSB*",
    "/dev/ttyACM*",
)
CURRENT_GENERATOR_VERSION = 17
EINK_PALETTE = (
    (55, 55, 55), (63, 63, 63), (70, 70, 70), (78, 78, 78),
    (87, 87, 87), (97, 97, 97), (111, 111, 111), (115, 115, 115),
    (119, 119, 119), (124, 124, 124), (130, 130, 130), (137, 137, 137),
    (145, 145, 145), (148, 148, 148), (154, 154, 152), (158, 158, 155),
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


def request_command(fd, command, ready_marker, timeout=90):
    data = bytearray()
    deadline = time.monotonic() + timeout
    os.write(fd, command)
    while ready_marker not in data:
        if time.monotonic() > deadline:
            raise SystemExit("The device did not finish the requested render.")
        data.extend(read_some(fd))


def request_variant(fd, variant):
    request_command(fd, f"VARIANT {variant}\n".encode(), f"SDREADY VARIANT {variant}".encode())


def request_seed(fd, version, seed):
    identity = f"{version:02X}{seed:08X}"
    request_command(fd, f"SEED {identity}\n".encode(), f"SDREADY SEED {identity}".encode())


def parse_variant(value):
    try:
        variant = int(value, 10)
    except ValueError as error:
        raise argparse.ArgumentTypeError("variant must be an unsigned decimal integer") from error
    if not 0 <= variant <= 0xFFFFFFFF:
        raise argparse.ArgumentTypeError("variant must be between 0 and 4294967295")
    return variant


def parse_seed_identity(value):
    match = re.fullmatch(r"([0-9A-Fa-f]{2})([0-9A-Fa-f]{8})", value)
    if not match:
        raise argparse.ArgumentTypeError(f"seed must use the displayed 10-character form {CURRENT_GENERATOR_VERSION:02X}89ABCDEF")
    version = int(match.group(1), 16)
    if version != CURRENT_GENERATOR_VERSION:
        raise argparse.ArgumentTypeError(
            f"this firmware currently supports replay codes beginning with {CURRENT_GENERATOR_VERSION:02X}"
        )
    return version, int(match.group(2), 16)


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


def next_capture_path(seed_identity):
    number = 1
    while True:
        path = f"slow-draw-{number:03d}-{seed_identity}.png"
        if not glob.glob(f"slow-draw-{number:03d}*.png"):
            return path
        number += 1


def create_eink_preview(source):
    if shutil.which("magick") is None:
        print("Capture saved, but e-ink preview requires ImageMagick.", file=sys.stderr)
        return
    stem, _ = os.path.splitext(source)
    output = f"{stem}-eink.png"
    number = 2
    while os.path.exists(output):
        output = f"{stem}-eink-{number:03d}.png"
        number += 1
    with tempfile.TemporaryDirectory(prefix="slow-draw-eink-") as temp:
        clut = os.path.join(temp, "palette.ppm")
        with open(clut, "wb") as palette_file:
            palette_file.write(b"P6\n16 1\n255\n")
            palette_file.write(bytes(channel for color in EINK_PALETTE for channel in color))
        try:
            subprocess.run([
                "magick", source, "-colorspace", "Gray", "-posterize", "16",
                clut, "-interpolate", "NearestNeighbor", "-clut", output,
            ], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as error:
            print(f"Capture saved, but e-ink preview failed: {error.stderr.strip()}", file=sys.stderr)
            return
    print(f"Saved e-ink preview to {output}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?")
    parser.add_argument("--port")
    parser.add_argument("--no-reset", action="store_true", help="try capturing without resetting the sleeping device")
    parser.add_argument("--variant", type=parse_variant, help="render and select this same-day variant before capture")
    parser.add_argument("--seed", type=parse_seed_identity, help="temporarily recreate a displayed versioned seed")
    parser.add_argument("--no-preview", action="store_true", help="skip the automatic e-ink palette preview")
    args = parser.parse_args()
    if args.variant is not None and args.seed is not None:
        parser.error("--variant and --seed cannot be used together")
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
            request_seed(fd, *args.seed)
        response = request_frame(fd, 20)
        header_start = response.index(b"SDFRAME ")
        while b"\n" not in response[header_start:]:
            response += read_some(fd)
        header_end = response.index(b"\n", header_start)
        _, width, height, depth, length, seed_identity = response[header_start:header_end].decode().split()
        width, height, depth, length = map(int, (width, height, depth, length))
        if (depth != 4 or length != width * height // 2 or
                re.fullmatch(r"[0-9A-F]{10}", seed_identity) is None):
            raise SystemExit("Unexpected framebuffer format from device.")
        packed = read_exact(fd, response[header_end + 1:], length)
        output_path = args.output or next_capture_path(seed_identity)
        save_png(output_path, width, height, packed)
        print(f"Saved {width}x{height} capture from {port} to {output_path}")
        if not args.no_preview:
            create_eink_preview(output_path)
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
