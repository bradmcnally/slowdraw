# Slow Draw

Slow Draw is an e-ink art project for the original M5Paper 1.1. It reads the
hardware RTC, derives a seed, renders a composition using the panel's 16
grayscale levels, and sleeps until the next scheduled print or user interaction.

![Slow Draw 001](examples/slow-draw-001.png)
![Slow Draw 002](examples/slow-draw-002.png)
![Slow Draw 003](examples/slow-draw-003.png)
![Slow Draw 004](examples/slow-draw-004.png)
![Slow Draw 005](examples/slow-draw-005.png)
![Slow Draw 006](examples/slow-draw-006.png)
![Slow Draw 007](examples/slow-draw-007.png)

- Cellular Aggregate grows connected cells from a seeded random walk; grayscale
  follows angle and distance through the resulting mass, while a few detached
  cells create visual echoes.
- Pixel Field distributes square pixels independently across the canvas, with
  broad mathematical fields controlling density, omissions, and grayscale.
- Subdivision arranges patterned macro-cells made from smaller pixels, using
  woven checks, diagonal bands, or corner knots.
- Dither Pressure converts smooth abstract fields into hard black-and-white
  Bayer screens or Atkinson error diffusion.
- Murmuration builds compressed, folding flock-like volumes from overlapping
  and subtractive fields, then renders them with Atkinson diffusion so dense
  cores dissolve into turbulent edges.

## Display modes

### Hourly

Hourly mode creates a new deterministic artwork at 07:00 and every whole hour
through 19:00, for 13 artworks per day. The 19:00 artwork remains displayed
overnight until the new 07:00 artwork is rendered automatically. Between
updates, the ESP32 and e-paper controller use light sleep. Tapping the screen
opens `PRINT OPTIONS`, and pressing the center rocker generates another variant
for the active hour. The rocker directions have no assigned action.

### Daily

Daily mode creates one deterministic artwork at 00:00 and retains it until the
following midnight. It uses the same light-sleep path between updates, so touch
and the center rocker remain available throughout the day.

### Options and manual variants

When the device is awake, tap the artwork to open `PRINT OPTIONS`. It shows the
10-character replay code, battery estimate, RTC date and time, and next
scheduled artwork time. Press the center rocker while awake to generate the
next deterministic variant for the current day or active hour. Choose the recipe
preference from the Options screen.

## Build and upload

Install PlatformIO, connect the M5Paper 1.1, then run:

```sh
pio run
pio run --target upload
pio device monitor
```

If the device RTC is unset, the firmware initializes it from the computer's
local build timestamp on first boot. No Wi-Fi or manual clock setup is needed.

To set an already-valid RTC to the computer's current local time:

```sh
./tools/set_clock.py
```

An explicit date and time can also be supplied:

```sh
./tools/set_clock.py --datetime "2026-09-08 14:37:00"
```

Setting the clock rerenders the appropriate daily or desk-hours hourly print.

## RTC wake validation

RTC-controlled shutdown is not used for normal operation until it has been
validated on the physical device. To run a two-minute battery-powered test:

```sh
./tools/wake_test.py 2
```

When the device displays `UNPLUG USB NOW`, disconnect the cable within 15
seconds. The BM8563 should power the M5Paper on at the displayed target time.
The result screen records whether the RTC alarm flag caused the boot, the actual
wake time, reset reason, and battery reading. Hold the center rocker for two
seconds to recover manually if the alarm does not power the device on.

The result is also saved, so it can be checked later after reconnecting USB:

```sh
./tools/wake_test.py --status
```

## Framebuffer capture

The retained 16-shade framebuffer can be captured over the USB cable:

```sh
./tools/capture.py
```

Captures include their replay seed in filenames such as
`slow-draw-001-0FE92B7DE2.png`. Each
capture also automatically creates an incremented `-eink` preview using the
muted 16-tone palette measured from the photographed M5Paper display. Use
`--no-preview` when only the raw framebuffer PNG is needed.
Capture resets the sleeping device so its USB serial connection answers
reliably. The current date and variant are restored from storage, so it
rerenders the same artwork before transferring the framebuffer.

Use `--variant NUMBER` to recreate, select, and capture a particular variant in
the current day or hour. The selected variant persists for that print period.

To temporarily recreate and capture an artwork from the complete replay code
shown in `PRINT OPTIONS`, without changing the RTC or saved current print:

```sh
./tools/capture.py --seed 0FE92B7DE2
```

Replay identities from unsupported generator versions are rejected rather than
rendered incorrectly. The raw capture is preserved; repeated previews retain
the seed in names such as `slow-draw-001-0FE92B7DE2-eink.png` and
`slow-draw-001-0FE92B7DE2-eink-002.png`.
