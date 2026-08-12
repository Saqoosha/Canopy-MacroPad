# Wireless, MagSafe and Qi — what was found before building any of it

Research notes for the phase after the six-key wired pad. Nothing here is
built; the value is that the numbers are settled, so the next attempt
starts from measurements instead of from a search.

The target is concrete: the mount under the display is an **iPhone
MagSafe charger**, and the pad would take the iPhone's place on it.

## The magnet ring, from Apple's own drawing

Apple's Accessory Design Guidelines is a public PDF
(`developer.apple.com/accessories/Accessory-Design-Guidelines.pdf`,
section 42 "MagSafe Attach"). The dimensions live in figures, not text,
so `pdftotext` returns nothing useful — read pages 276-278 as images.

```
ring outer         Ø54.10
ring inner         Ø46.00        the band is only 4.05 wide
magnets            8, 45.00° apart, 22.50° offset
magnet thickness   1.10
DC shield          0.70, low-carbon steel (1010/DT4), Bsat >= 2.0 T
adhesive           0.05
material           N48H NdFeB, NiCuNi 7-13 µm
detach force       650 - 1510 gf
surface flux       <= 0.215 T
```

Aftermarket adhesive rings are sold at 54.1 × 46 × 1.5 mm, i.e. the
market copies the spec exactly. Passive steel rings exist at 0.5-0.55 mm
and are enough to *hold*, but not to *align* — and alignment is what Qi
coupling is sensitive to, which is why Apple specifies self-alignment
within 1.55 mm radial.

**Four of the eight magnets fit a 26 mm deep case with no growth at all.**
At radius 25.03 the magnets at 22.5° sit at y = ±9.58, inside the
`inline` cavity's ±11.0. That is half the ring, so roughly 325-750 gf
normal — ample for a ~120 g pad, and the four positions define
orientation as a bonus.

## The coil is the constraint, not the magnets

| Part | Coil | Board | Out |
|---|---|---|---|
| Adafruit 1901 | **40 × 29** rectangular | 48 × 32 × 0.5 | 5 V / 500 mA |
| generic Qi RX | 46 × 36, or Ø43 round | varies | 5 V / 1 A |

The short axis is what matters and 29 mm is the smallest found. Against
`inline`'s 26.0 mm outer depth:

```
magnets only (4 of 8)     26.0     +0
Adafruit 1901 coil        34.0     +8
generic 46 × 36 coil      40.0     +14
full Ø54.1 magnet ring    59.0     +33
```

So the rectangular Adafruit coil is worth six millimetres of case over
the cheap round ones.

**Z costs nothing.** Recess the coil into the *bottom plate* — 2.40 thick,
so a 1.2 mm pocket leaves 1.2 mm of PLA between coil and charger — with
the module's ferrite sheet facing inward. The ferrite is what makes this
work at all: the key PCB's copper sits directly above, and without the
shield it would absorb the field and heat. Phones are built in exactly
this order for the same reason. Never remove the ferrite to save height.

## Two things to know before buying any of it

**Qi power only makes sense together with BLE.** Receiving power
wirelessly while data still runs over USB buys nothing — the same USB-C
cable already carries both. Adding Qi means committing to the whole of
the wireless phase: nRF52840, a custom GATT service, and CoreBluetooth
plus an `NSBluetoothAlwaysUsageDescription` TCC prompt on the macOS side.
That also gives up the property `README.md` argues for at length: no
entitlement, no TCC, plain file I/O on `/dev/cu.*`.

**The load is too light for the transmitter.** The pad draws roughly
0.25-0.5 W against a 7.5-15 W charger, and Qi transmitters stop when the
receiver asks for nearly nothing. The handoff document already warned
about this. The fix is a small LiPo as a buffer — 100-200 mAh is enough,
because it is there as a load and a reservoir, not for runtime.

## Battery, and why runtime is not the point

Free height under the boards, measured off `params.py`:

```
inline    2.80 floor-to-PCB, minus 1.85 of hot-swap socket  ->  0.95 free
stacked   8.52 floor-to-PCB, minus 1.85                     ->  6.67 free
```

`inline` cannot take a cell without growing. Every millimetre of cell
thickness lands directly on the case height (`inline` is 11.77 today):

| cell | gap needed | case height |
|---|---|---|
| 3.0 mm | 5.35 | 14.32 |
| 4.0 mm | 6.35 | 15.32 |
| 5.0 mm | 7.35 | 16.32 |

Even at 5 mm that is still under `stacked`'s 17.49.

The cell also has to be **≤ 20 mm across one plan axis**, because the
cavity is 21.99 deep. That rules out most first-party cells:

| cell | mm | mAh | fits |
|---|---|---|---|
| **Adafruit 2750** | 36 × 19.6 × 5.2 | 350 | **yes**, JST-PH, protected |
| generic 502060 | 60 × 20 × 5.0 | 600 | yes |
| Adafruit 3898 | 36 × 17 × 7.8 | 400 | width yes, 7.8 thick |
| Adafruit 4236 | 55 × 35 × 3.5 | 420 | no, 35 wide |
| Adafruit 1578 | 29 × 36 × 4.75 | 500 | no, 29 wide |

**Runtime is hours, not days, and no cell fixes that.** Six 3535
NeoPixels idle at about 1 mA each, nRF52840 with CircuitPython and a BLE
link is another 8-12 mA, and lit keys add roughly 30 mA — call it 50 mA,
so 350 mAh is about 7 hours. The device's entire job is to stay lit;
CircuitPython never sleeps. The only real lever is brightness. This is
why the dock pairing is the right shape: the battery exists so the pad
survives being lifted off the charger, not so it runs untethered.

## The MCU, if it ever moves

**Seeed XIAO nRF52840 is a mechanical drop-in for the QT Py** and is a
better choice than the handoff's nice!nano v2.

| | QT Py RP2040 | XIAO nRF52840 | nice!nano v2 |
|---|---|---|---|
| size | 21.8 × 17.8 | **21 × 17.8** | 33 × 18 |
| BLE | — | 5.0 | 5.0 |
| LiPo charging | — | **onboard, 50/100 mA** | yes |
| STEMMA QT | **yes** | no | no |
| CircuitPython | 10.2.1 | 10.2.1, official | yes |

The QT Py's own page says "Pinout and shape is Seeed Xiao compatible",
so the case pocket fits both — cutting it to the deeper of the two
underside clearances costs nothing and saves redesigning the case on the
day the MCU changes. The charger being onboard also deletes the
handoff's separate MCP73831.

Rejected, with reasons:

- **QT Py ESP32-S3** — keeps STEMMA QT and the footprint, but
  CircuitPython's BLE there is younger (central+peripheral only on 8 MB
  flash parts, and an open hard-fault issue), and it draws far more than
  an nRF for battery work.
- **QT Py CH552 (ssci 9718) and QT Py CH32V203 (ssci 9842)** — ¥1,210
  each and the right shape, but **neither runs CircuitPython**. Adafruit
  says so of the CH32V203 outright. Switching to either throws away
  `code.py`, `boot.py`, dual `usb_cdc`, the drive gate, the `CIRCUITPY`
  deploy path and all three error paths proven by injection, in exchange
  for a board that costs more than the one already on the desk.
