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
through 19:00, for 13 artworks per day. From 07:00 until the 19:00 artwork, the
device uses light sleep between updates. During this window, tapping the screen
opens `PRINT OPTIONS`, pressing the center rocker generates another variant for
the active hour, and pressing the rocker left or right changes the recipe.

After rendering the 19:00 artwork, the device enters RTC-controlled shutdown.
The e-ink panel retains that artwork without power. At 07:00 the next morning,
the RTC powers the device on and it automatically renders the new 07:00
artwork. While shut down, screen taps and rocker directions are unavailable;
pressing the center rocker powers the device on manually.

### Daily

Daily mode creates one deterministic artwork at 00:00, then uses RTC-controlled
shutdown until the following midnight. The retained artwork remains visible
while the device is off. Pressing the center rocker powers it on manually and
rerenders the current day's artwork; it does not create a new daily seed.

RTC-controlled shutdown gives Daily mode the lowest idle power consumption.
As in Hourly's overnight period, touch and rocker-direction input are not
available while the device is shut down.

### Options and manual variants

When the device is awake, tap the artwork to open `PRINT OPTIONS`. It shows the
10-character replay code, battery estimate, RTC date and time, and next
scheduled artwork time. Press the center rocker while awake to generate the
next deterministic variant for the current day or active hour. Press the rocker
left or right to cycle the recipe preference: `ALL`, `CELLULAR`, `PIXEL FIELD`,
`SUBDIVISION`, `DITHER`, or `MURMURATION`.

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
