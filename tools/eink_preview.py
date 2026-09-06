#!/usr/bin/env python3
"""Remap images to the photographed Slow Draw M5Paper palette."""

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile


# Sampled from the artwork area of the supplied M5Paper photograph, then
# regularized into 16 ordered tones. The slight warmth is intentional.
EINK_PALETTE = (
    (55, 55, 55),
    (63, 63, 63),
    (70, 70, 70),
    (78, 78, 78),
    (87, 87, 87),
    (97, 97, 97),
    (111, 111, 111),
    (115, 115, 115),
    (119, 119, 119),
    (124, 124, 124),
    (130, 130, 130),
    (137, 137, 137),
    (145, 145, 145),
    (148, 148, 148),
    (154, 154, 152),
    (158, 158, 155),
)


def next_output(source):
    candidate = source.with_name(f"{source.stem}-eink.png")
    if not candidate.exists():
        return candidate
    number = 2
    while True:
        candidate = source.with_name(f"{source.stem}-eink-{number:03d}.png")
        if not candidate.exists():
            return candidate
        number += 1


def write_clut(path):
    with path.open("wb") as output:
        output.write(b"P6\n16 1\n255\n")
        output.write(bytes(channel for color in EINK_PALETTE for channel in color))


def recolor(source, output):
    with tempfile.TemporaryDirectory(prefix="slow-draw-eink-") as temp:
        clut = Path(temp) / "palette.ppm"
        write_clut(clut)
        subprocess.run(
            [
                "magick", str(source),
                "-colorspace", "Gray",
                "-posterize", "16",
                str(clut),
                "-interpolate", "NearestNeighbor",
                "-clut",
                str(output),
            ],
            check=True,
        )


def main():
    parser = argparse.ArgumentParser(
        description="Preview images with the grayscale palette measured from the M5Paper photo."
    )
    parser.add_argument("images", nargs="+", type=Path)
    args = parser.parse_args()
    if shutil.which("magick") is None:
        raise SystemExit("ImageMagick is required, but the 'magick' command was not found.")

    for source in args.images:
        if not source.is_file():
            raise SystemExit(f"Image not found: {source}")
        output = next_output(source)
        recolor(source, output)
        print(output)


if __name__ == "__main__":
    main()
