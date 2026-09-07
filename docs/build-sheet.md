# Alien Gaze Rig — Build Sheet (Rev A)

Screen eyes that track the nearest face, running on one Raspberry Pi.

| | |
|---|---|
| **Brain** | Pi 4B / 5 |
| **Eyes** | 2× GC9A01 1.28" |
| **Socket fit** | ~1.3" (33mm) |
| **Vision** | Pi Camera, hidden |

## §1 The one bet this build makes

The eyes render an animated iris and pupil, not a live camera feed. A camera hidden
elsewhere on the head (not in the sockets — the sockets are full of display) watches the
room, finds the nearest face, and feeds its position into a drawing loop that shifts a
painted pupil to "look" at it. This is how every convincing screen-eye animatronic works —
it's cheap to compute, looks like an eye instead of a monitor, and lets you fake behaviors
(blinking, idle scanning, a slow reluctant lock-on) that a raw video feed can't. If what you
actually pictured was the sockets showing real video of the room, say so — the whole plan
below changes, and gets a lot harder and less convincing.

Everything from here assumes the bet above. It also assumes a Pi 4B or 5 (you can run this
on a Zero 2 W, but plan on the two-microcontroller escalation in §7 from day one rather than
as a fallback), and that the camera lives in the mouth or a nostril opening rather than an
eye.

## §2 Parts

| Component | Spec | Qty | Note |
|---|---|---|---|
| Raspberry Pi | Pi 4B (4GB) or 5 | 1 | Needs headroom for OpenCV + two SPI panels at once |
| Round LCD | GC9A01, 1.28", 240×240, SPI | 2 | PCB is ~32–34mm across — dry-fit one before ordering the pair |
| Camera | Pi Camera Module 3 (or NoIR) | 1 | NoIR + IR illuminator = it can find faces in the dark, which is worse for everyone |
| CSI ribbon extension | 30–50cm FPC | 1 | Routes the camera from the Pi's CSI port out to the nostril |
| MicroSD card | 32GB, A2-rated | 1 | |
| Dupont jumpers | F–F, M–F assorted | ~20 | |
| Power supply | 5V / 3A USB-C or barrel | 1 | Undervoltage under CPU load is the #1 cause of "it worked yesterday" |
| Small protoboard | optional | 1 | Cleaner than loose jumpers inside a head that gets picked up and moved |

## §3 Wiring

Both displays share the SPI clock and data lines — that's what the bus is for. What they do
not share is chip-select or data/command: get those two crossed between the eyes and you'll
get one working display and one frozen or garbled one.

| Signal | Eye A1 · right | Eye A2 · left | Shared? |
|---|---|---|---|
| VCC | 3V3 — pin 1 | 3V3 — pin 1 | yes |
| GND | GND — pin 6 | GND — pin 9 | either GND pin works |
| SCK | GPIO11 — pin 23 | GPIO11 — pin 23 | yes |
| SDA (MOSI) | GPIO10 — pin 19 | GPIO10 — pin 19 | yes |
| CS | GPIO8 (CE0) — pin 24 | GPIO7 (CE1) — pin 26 | no — this is what picks the eye |
| DC | GPIO24 — pin 18 | GPIO23 — pin 16 | no — the classic wiring mistake |
| RES | GPIO25 — pin 22 | GPIO25 — pin 22 | fine to share, resets together |
| BLK | 3V3 direct | 3V3 direct | skip GPIO for v1 |

Camera: connects to the Pi's CSI port, not the GPIO header. Run the ribbon extension from
there out to whichever gap you're using — the mouth seam or a nostril hole both already
exist on your print — and hot-glue the lens flush from the inside so it doesn't wander.

## §4 Software pipeline

One loop, five stages, running on the Pi. It repeats roughly 15–30 times a second depending
on how big a frame you feed the detector.

1. **Capture** — Grab a frame from the camera. Downscale it — the detector doesn't need
   full resolution, and full resolution is where your frame rate goes to die.
2. **Detect** — Run a Haar-cascade face detector on the grayscale frame. Cheap, fast, plenty
   accurate for "is there a face and roughly where."
3. **Fallback** — No face found → don't freeze. Drive the pupils through a slow synthetic
   scan so the head reads as "awake," not "broken."
4. **Smooth** — Ease the current gaze toward the target instead of snapping to it. This one
   line of math is most of what makes it unsettling instead of jerky.
5. **Render + push** — Draw sclera / iris / pupil to a 240×240 image, then blit it to both
   panels over SPI.

## §5 Reference implementation

This is the shape of it, not a finished program — swap in your actual GPIO pin objects per
§3 and tune the constants once the eyes are in front of you.

```python
# gaze_loop.py — one Pi, two eyes, one nervous system
import time, math
import cv2
from PIL import Image, ImageDraw
import board, busio, digitalio
from adafruit_gc9a01a import GC9A01A

# --- displays: right eye on CE0, left eye on CE1 (see §3) ---
spi = busio.SPI(clock=board.SCK, MOSI=board.MOSI)
eye_r = GC9A01A(spi, cs=digitalio.DigitalInOut(board.CE0),
                 dc=digitalio.DigitalInOut(board.D24),
                 rst=digitalio.DigitalInOut(board.D25), baudrate=40_000_000)
eye_l = GC9A01A(spi, cs=digitalio.DigitalInOut(board.CE1),
                 dc=digitalio.DigitalInOut(board.D23),
                 rst=digitalio.DigitalInOut(board.D25), baudrate=40_000_000)

SCLERA, IRIS, PUPIL = (235,235,230), (40,120,60), (10,10,10)

def draw_eye(gx, gy):
    # gx, gy in [-1, 1] — 0,0 is dead ahead
    img = Image.new("RGB", (240,240), SCLERA)
    d = ImageDraw.Draw(img)
    cx, cy = 120 + gx*34, 120 + gy*34
    d.ellipse([cx-55,cy-55,cx+55,cy+55], fill=IRIS)
    d.ellipse([cx-24,cy-24,cx+24,cy+24], fill=PUPIL)
    return img

cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
cap = cv2.VideoCapture(0)

tx, ty = 0.0, 0.0
DAMPING = 0.08  # lower = slower, more unsettling catch-up

while True:
    ok, frame = cap.read()
    if not ok: continue
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, 1.2, 5, minSize=(60,60))

    if len(faces):
        x,y,w,h = max(faces, key=lambda f: f[2]*f[3])  # nearest face
        fh, fw = gray.shape
        nx = ((x+w/2)/fw)*2 - 1
        ny = ((y+h/2)/fh)*2 - 1
        goal_x, goal_y = -nx, ny
    else:
        t = time.time()
        goal_x, goal_y = math.sin(t*0.3)*0.6, math.sin(t*0.21)*0.3

    tx += (goal_x - tx) * DAMPING
    ty += (goal_y - ty) * DAMPING

    frame_img = draw_eye(tx, ty)
    eye_r.image(frame_img)
    eye_l.image(frame_img)
```

## §6 Making it worse (in a good way)

| | |
|---|---|
| **Lag, don't snap** | A slower DAMPING value reads as deliberate attention rather than a servo twitching — the eyes seem to decide to look at you a half-second late. |
| **Blink** | Fade the drawn image toward the sclera color and back every few seconds, or PWM the BLK pin briefly if you did wire it to a GPIO. Irregular intervals beat a metronome. |
| **Lock-on delay** | Require a face to be present for ~400ms before switching targets, so the eyes don't dart between two people — they settle on one and stay. |
| **Night vision** | A NoIR camera plus a couple of 850nm IR LEDs lets it track faces in a dark room while showing no visible light source at all. |
| **Room tone** | Idle scanning that's slightly too slow and slightly too regular sells "watching" far better than fast, random motion. |

## §7 If the frame rate disappoints you

Two 240×240 panels plus a Haar cascade should hold 15–25fps on a Pi 4/5 once you downscale
the detection frame — enough that the lag from §6 hides the rest. If it doesn't, the
standard escalation is to stop asking the Pi to do everything: keep it as the "brain"
running detection only, and hand each eye's own rendering to a small companion
microcontroller (a Seeed XIAO ESP32-S3 per eye works well and is small enough to hide behind
the socket). The Pi then just broadcasts a gaze x/y pair over I²C or serial, and each MCU
redraws its own panel locally — the exact plan to reach for if you're on a Zero 2 W from the
start rather than a Pi 4/5.

## §8 Build audit

**Assumptions made**
- Animated pupil graphic, not live video passthrough — the whole plan hinges on this.
- Pi 4B/5 as the brain; a Zero 2 W is possible but shifts §7 from fallback to default.
- Camera lives in the mouth or a nostril opening, since both sockets are taken by displays.

**Unverified facts**
- [Guessing] Your printed socket's inner clearance and depth behind it — GC9A01 boards run
  ~32–34mm across; dry-fit one before ordering the pair.
- [Likely] Haar cascade hits 15–25fps on a downscaled frame on Pi 4/5 — not benchmarked on
  your specific enclosure and thermals.

**Gaps I couldn't fill**
- Internal depth behind the eye sockets for the display PCB, ribbon, and standoffs.
- Where this will actually live — ambient light level decides whether NoIR + IR is worth the
  extra part.

**What breaks first**
- Crossed DC lines between the two eyes — the single most common wiring mistake with dual
  round SPI panels.
- Frame rate collapse from running detection on a full-resolution frame instead of a
  downscaled copy.

---
*Alien Gaze Rig · Build Sheet · drafted for Todd*
