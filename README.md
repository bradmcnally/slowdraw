# Slow Draw

Slow Draw is an offline generative-art experience for the original M5Paper
1.1. On each
boot it reads the hardware RTC, derives a deterministic seed from the calendar
date and generator version, renders one monochrome composition, refreshes the
e-paper display, and sleeps until just after midnight.

![Slow Draw pixel field composition](slow-draw-005-eink.png)
![Slow Draw cellular aggregate composition](slow-draw-003-eink.png)


The current curated generator uses four grammars. Cellular Aggregate grows
connected cells from a seeded random walk; grayscale follows angle and distance
through the resulting mass, while a few detached cells create visual echoes.
Pixel Field distributes the same uniform square pixels independently across the
full canvas, with broad mathematical fields controlling density, omissions, and
grayscale. Subdivision arranges patterned macro-cells made from smaller pixels,
using woven checks, diagonal bands, or corner knots. Dither Pressure converts
smooth abstract fields into hard black-and-white Bayer screens or Atkinson
error diffusion. None of the
grammars deliberately depict a character, object, or environment,
though forms may occasionally feel suggestive. Artwork is quantized to a
240-pixel-wide logical grid and displayed as crisp 4 × 4 blocks. The renderer
uses all 16 native grayscale levels of the M5Paper panel alongside deliberate
ordered dithering and high-contrast value clusters.
The surrounding background is always pure white; grayscale is confined to the
aggregate itself.
Artwork stops on the last complete grid row before the footer, leaving clean
white separation; no cell is clipped by the centered label area.
All connected and detached cells share one size and one global alignment grid;
cells are never individually inset, shifted, or reduced.

Pressing the center of the side rocker generates the next deterministic same-day
variant. The original slow draw is variant zero; alternates are identified by
`/1`, `/2`, and so on. Between presses the ESP32 uses light sleep, waking from
the rocker or automatically just after midnight.

## Build and upload

Install PlatformIO, connect the M5Paper 1.1, then run:

```sh
pio run
pio run --target upload
pio device monitor
```

If the device RTC is unset, the firmware initializes it from the computer's
local build timestamp on first boot. No Wi-Fi or manual clock setup is needed.

The display is targeted at 960 × 540 in landscape orientation. Generator output
is deterministic for `(date, generator version)`. Changing
`kGeneratorVersion` intentionally starts a new sequence.

## Framebuffer capture

The retained 16-shade framebuffer can be captured over the USB cable:

```sh
./tools/capture.py
```

Captures are saved as `slow-draw-001.png`, `slow-draw-002.png`, and so on.
Capture resets the sleeping device so its USB serial connection answers
reliably. The current date and variant are restored from storage, so it rerenders
the same artwork before transferring the framebuffer. Pass `--no-reset` to try
capturing without a reset.
Use `--variant NUMBER` to recreate, select, and capture a particular same-day
variant. The selected variant persists across restarts for the current date.

To recolor a capture with the muted, slightly warm 16-tone palette measured
from the photographed M5Paper display:

```sh
./tools/eink_preview.py slow-draw-001.png
```

The source is preserved. Repeated previews are saved as
`slow-draw-001-eink.png`, `slow-draw-001-eink-002.png`, and so on.
