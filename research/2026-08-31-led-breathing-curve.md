# LED Breathing Effects: Curves, Perception, and 8-bit Reality

## エグゼクティブサマリー

The canonical "breathing" LED formula `(exp(sin(t)) - 1/e) * (255/(e - 1/e))` did not come from Sean Voisen and does not model human breathing — it originated as a 2010 blog comment by Adam Shea proposing an exponential to correct the *logarithmic response of the eye*, and it is exactly time-symmetric about its peak. Apple's own primary source, US 6,658,577 B2, specifies something different again: a positively-biased sinusoid at ~25% max duty, 125 Hz PWM, a ~1.8 s period and an explicit ~0.4 s quiet interval — while a photodiode measurement of a real MacBook found ~12 breaths/min and a Gaussian, not a sinusoid, contradicting both the patent's period and its curve shape. Below the curve question sits a second, harder one: on 8-bit WS2812/SK6812 the bottom of any perceptual curve collapses into a handful of levels, and the accepted answers (temporal dithering, minimum-on floors, higher-bit-depth parts) each fail in a specific measurable way. The strongest practical guidance in the whole corpus is negative: a plain sine is wrong because its inter-breath transitions are too sharp, and most published CIE-L\* code carries a transcription bug (119 for 116).

## Key Findings

Ranked by verification strength.

**Unanimous / primary-source backed:**

- The exp(sin(t)) formula originates from a **2010 comment by Adam Shea** on an Adafruit post about Ladyada's 2006 reverse-engineering of the Mac breathing LED — not from Sean Voisen, whose 2011 blog post popularized it ([ThingPulse: Breathing LEDs — Cracking the Algorithm](https://thingpulse.com/breathing-leds-cracking-the-algorithm-behind-our-breathing-pattern/)).
- The normalized form is `f(x) = (e^sin(x) − 1/e) × (100/(e − 1/e))`, with `1/e = 0.36787944` and `100/(e − 1/e) = 42.54590641`, because `min(e^sin x) = 1/e` and `max = e` ([ThingPulse](https://thingpulse.com/breathing-leds-cracking-the-algorithm-behind-our-breathing-pattern/)).
- For direct 8-bit PWM the constant becomes `255/(e − 1/e) ≈ 108.0`: `val = (exp(sin(millis()/2000.0 * PI)) - 0.368) * 108.0` ([ThingPulse](https://thingpulse.com/breathing-leds-cracking-the-algorithm-behind-our-breathing-pattern/)).
- Multiplying the argument by `PI/2` gives a **4-second period = 15 breaths/min**, inside the 12–20 bpm human range; in code `x*PI/2` becomes `millis()/2000.0*PI` ([ThingPulse](https://thingpulse.com/breathing-leds-cracking-the-algorithm-behind-our-breathing-pattern/)).
- Apple's patent is **US 6,658,577 B2, "Breathing status LED indicator"**, filed 2002-07-15, granted 2003-12-02, inventors Brian Q. Huppi, Christopher J. Stringer, Jory Bell, Christopher L. Capener ([Google Patents US6658577B2](https://patents.google.com/patent/US6658577B2/en); [ThingPulse](https://thingpulse.com/breathing-leds-cracking-the-algorithm-behind-our-breathing-pattern/)).
- The patent specifies a **positively-biased sinusoid**, max ≈ **25% duty cycle** against 0% min — not a full-range sine — modulated by PWM at **125 Hz** (preferred 100–200 Hz) at constant **6 mA peak** with varying pulse widths ([US6658577B2](https://patents.google.com/patent/US6658577B2/en)).
- The patented cycle has an **overall periodicity of ~1.8 s** including an explicit **quiet (off) period of ~0.4 s**, spanning roughly 1400–1800 ms — i.e. the waveform is asymmetric *by pause*, not by rise/fall ([US6658577B2](https://patents.google.com/patent/US6658577B2/en); [avital.ca](https://avital.ca/notes/a-closer-look-at-apples-breathing-light)).
- **A pure sine is incorrect for breathing because the transitions between successive breaths are too sharp** ([avital.ca: A Closer Look at Apple's Breathing Light](https://avital.ca/notes/a-closer-look-at-apples-breathing-light)).
- Ladyada (Limor Fried) reported in 2006 that **programming a plain sinusoid does not visually match** the Mac LED, which is what motivated capturing the real waveform ([Adafruit: Reverse engineering the Mac breathing LED](https://blog.adafruit.com/2006/08/11/reverse-engineering-the-mac-breathing-led/)).

**Measurement-backed, contradicting the patent:**

- Avital Pekker's 2016 photodiode capture (silicon PIN photodiode → BeagleBone Black ADC, **3000 samples at 10 ms**, moving-average filtered) of a real MacBook sleep light found the actual curve is a **Gaussian, not e^sin(x)** ([avital.ca](https://avital.ca/notes/a-closer-look-at-apples-breathing-light); corroborated in [ThingPulse](https://thingpulse.com/breathing-leds-cracking-the-algorithm-behind-our-breathing-pattern/)).
- The measured fit is a Gaussian with **mean = 18.045, sigma = 48.033** (minimizing squared error), and the measured rate was **~12 breaths/min — not the patent's ~33 bpm implied by 1.8 s** ([avital.ca](https://avital.ca/notes/a-closer-look-at-apples-breathing-light)).
- Pekker's own reimplementation uses a **5.0 second breath period** ([avital.ca](https://avital.ca/notes/a-closer-look-at-apples-breathing-light)).

**Method / measurement-technique findings:**

- Ladyada's 2006 capture used a photocell read through a **MIDIsense board rather than a plain photocell voltage divider**, because a photocell divider responds as **1/R rather than linearly** — an op-amp linearization was required to recover absolute brightness ([Adafruit 2006](https://blog.adafruit.com/2006/08/11/reverse-engineering-the-mac-breathing-led/)).
- The captured trace shows **noise at the brightness peaks attributed to PWM artifacts** picked up through the LED's diffused white plastic — independent confirmation that the Mac sleep LED is PWM-driven ([Adafruit 2006](https://blog.adafruit.com/2006/08/11/reverse-engineering-the-mac-breathing-led/)).
- A reader fitted a **quartic polynomial, `y = 0.0009x⁴ − 0.045x³ + 1.136x² − 16.031x + 119.26`**, to points sampled off Ladyada's scope capture, to reproduce the curve on an Atmel micro ([Adafruit 2006](https://blog.adafruit.com/2006/08/11/reverse-engineering-the-mac-breathing-led/)).

## 詳細

### exp(sin(t)) — 出自と正確な定数

The formula everyone cites as "Sean Voisen's breathing LED" has a three-step provenance, and the first two steps matter for interpreting it correctly. Limor Fried scoped a real MacBook sleep LED in 2006 and published the trace without a formula, noting explicitly that a plain sinusoid did not match what she saw ([Adafruit 2006](https://blog.adafruit.com/2006/08/11/reverse-engineering-the-mac-breathing-led/)). A commenter, Adam Shea, then proposed `exp(sin(t))` — and his stated rationale was **not** breathing at all but **"to correct for the logarithmic response of the rest of the optical system (LED→eye→brain)"** ([ThingPulse](https://thingpulse.com/breathing-leds-cracking-the-algorithm-behind-our-breathing-pattern/)). Voisen's 2011 post turned that into the one-liner that propagated.

The derivation is elementary and worth stating because the constants are otherwise magic numbers. `sin(x) ∈ [−1, 1]`, so `e^sin(x) ∈ [1/e, e]`. Subtract the floor `1/e = 0.36787944`, then scale by `range/(e − 1/e)`:

```
percent form:  f(x) = (e^sin(x) - 0.36787944) * 42.54590641    // 100/(e - 1/e)
8-bit form:    val  = (exp(sin(millis()/2000.0 * PI)) - 0.368) * 108.0   // 255/(e - 1/e)
```

Period control is the `PI/2` factor on the argument, which yields a **4-second cycle ≈ 15 breaths/min**, inside the 12–20 bpm human resting range; the `millis()/2000.0*PI` phrasing is that same scaling folded into the millisecond clock ([ThingPulse](https://thingpulse.com/breathing-leds-cracking-the-algorithm-behind-our-breathing-pattern/)).

**What this curve actually does, correctly stated:** it produces a *narrow peak and a wide trough* — a long dwell near darkness between breaths. That is a brightness-shaping and inter-breath-pause effect. It is **not** an inhale/exhale duration asymmetry: `sin` is symmetric about `π/2`, so `e^sin` has identical rise and fall times. See 相反する見解 below, where this distinction killed a widely-repeated claim.

Alternative fits to the same underlying trace exist and are more literal reproductions of Apple's hardware than `exp(sin)` is — notably the quartic `y = 0.0009x⁴ − 0.045x³ + 1.136x² − 16.031x + 119.26` sampled directly off Ladyada's scope capture ([Adafruit 2006](https://blog.adafruit.com/2006/08/11/reverse-engineering-the-mac-breathing-led/)), and Pekker's Gaussian ([avital.ca](https://avital.ca/notes/a-closer-look-at-apples-breathing-light)).

### CIE 1931 L\* vs. power-law gamma

This is a real standards-vs-practice split, and the most useful finding is not which side wins but that **the most-copied implementation is transcribed wrong**.

The CIE camp argues that gamma is a CRT-voltage artefact that only coincidentally resembles perception, and applies the inverse-L\* transfer directly:

```
Y = L* / 903.3                for L* ≤ 8
Y = ((L* + 16) / 116)^3       for L* > 8
```

That piecewise form is what the mainline Linux kernel's `cie1931()` in `pwm_bl.c` implements, and it is the argument advanced by Jared Sanson (2013), the HP LED Shield writeup (2012), and mbedded.ninja. The gamma camp — Adafruit's learn guide (γ = 2.8), Adafruit's own NeoPixel library (γ = 2.6), WLED (default γ = 2.8), and sRGB-EOTF advocates (γ ≈ 2.2) — concedes the exponent is empirical and argues the practical difference is negligible once it has been baked into a lookup table anyway.

**The transcription bug.** The single most-copied CIE writeup (jared.geek.nz) prints **119 where CIE specifies 116**. The 119 variant is *discontinuous at the breakpoint* and only reaches roughly 93% of the output range. Because the author is unreachable, derived code — the widely-forked mathiasvr gist, `pwm-lightness` — still carries the variant. The same class of error is documented inside the kernel itself (an LKML patch fixing `0.08856` → `L* = 8` and the 903.3 factor) and shipped as a user-visible discontinuity bug in WLED (issue #4396 / PR #4419). *Which* formula you pick is less contested than *which transcription of it you copied.*

> Confidence note: this angle's specifics (kernel `pwm_bl.c`, the 119/116 discrepancy, the WLED issue numbers) come from the angle summary and were not each individually re-verified by the adversarial pass. Treat the piecewise formula and the 119-vs-116 warning as actionable and verify the issue/PR numbers before citing them.

### Apple's sleep indicator — patent vs. measurement

The primary source is unambiguous and *much less specific than the folklore*. US 6,658,577 B2 claims:

| Parameter | Patent value |
|---|---|
| Curve | positively-biased sinusoid (no equation published) |
| Max duty | ~25% |
| Min duty | 0% |
| PWM frequency | 125 Hz (preferred 100–200 Hz) |
| Peak current | 6 mA, constant; pulse width varies |
| Overall period | ~1.8 s |
| Quiet (off) interval | ~0.4 s, roughly 1400–1800 ms of the cycle |

([US6658577B2](https://patents.google.com/patent/US6658577B2/en))

The patent publishes **no equation and no table values**, and — importantly — **never states a breaths-per-minute figure**. The famous "12 breaths per minute = adult resting respiration" story comes from design commentary and its many echoes, not from Apple primary material; treat it as unverified against the patent.

Measurement contradicts the patent on two axes at once. Pekker's photodiode capture on a real MacBook found **~12 breaths/min (a ~5 s cycle, not 1.8 s)** and a **Gaussian rather than sinusoidal** profile ([avital.ca](https://avital.ca/notes/a-closer-look-at-apples-breathing-light)). His model is best described as two half-Gaussians of different width — fast rise, slow fall — and his own reimplementation runs at a 5.0 s period, 25% max duty, 1 kHz PWM, shipped as a lookup table. The patent describes an intent from 2002; the shipping hardware a decade later did something else.

Ladyada's 2006 work sits between them as the earliest independent evidence: her scope trace confirms PWM drive (via the peak-noise artefact) and her stated failure to match the LED with a plain sinusoid is the original documented complaint that started this entire line of inquiry ([Adafruit 2006](https://blog.adafruit.com/2006/08/11/reverse-engineering-the-mac-breathing-led/)).

### Human breathing asymmetry — and whether LEDs mimic it

Real quiet breathing *is* asymmetric: inspiration is shorter than expiration (airway resistance slows outflow), with a distinct end-expiratory pause. But the numbers are softer than usually presented — the ubiquitous "1:2" is a **mechanical-ventilation convention**, while spontaneous adult I:E is variously given as 1:1.5–1:2 (Pekker, citing physiology) up to 1:3–1:5 in respiratory-therapy teaching. Napoli (2022) states flatly that "humans do not breathe sinusoidally."

The finding worth carrying is a triple contrast:

1. **Apple's patent draws a symmetric duty curve** (Fig. 3, 1.8 s period, 0.4 s pause) — so the canonical breathing LED never encoded I:E asymmetry in the first place ([US6658577B2](https://patents.google.com/patent/US6658577B2/en)).
2. **exp(sin(t)) is likewise time-symmetric.** Its narrow peak / wide trough gives an *end-expiratory pause*, not a slower exhale — and this is routinely mis-described in secondary sources.
3. **Only two implementation families deliberately encode asymmetry:** Pekker's piecewise two-half-Gaussian (narrow σ rise, wide σ fall, the tail doubling as the inter-breath pause) ([avital.ca](https://avital.ca/notes/a-closer-look-at-apples-breathing-light)), and hardware LED drivers such as SparkFun's SX1509, whose primitive `io.breathe(pin, low_ms, high_ms, rise_ms, fall_ms)` takes independent rise/fall times plus an explicit LOW dwell (example: 1000/500/500/250 ms).

Everything else in the maker/firmware ecosystem — QMK backlight tables, FastLED examples, kslstn/Breathe, ThingPulse's Icon64 — ships a symmetric curve.

### What firmware actually implements

Nobody ships a plain sine, but the replacements fall into three distinct families.

**Exponentiated-sine LUTs.** QMK's `rgblight` bakes Voisen's `exp(sin(x·π))` — center 1.85, max 255 — into 256/128/64-entry tables that top out at `0xDD`. QMK's separate backlight path uses `sin(x/128·π)^4 · 255` over `BREATHING_STEPS 128` at 120 Hz. OpenRGB Effects uses `pow(sin(progress), 3) · 255` over a half period.

**Easing composed onto a triangle wave.** FastLED's `quadwave8`/`cubicwave8` are `ease8InOutQuad`/`Cubic ∘ triwave8`, documented explicitly as spending more time at the limits than a sine does — the same narrow-peak/wide-trough goal reached without a transcendental.

**Perceptual remapping as a separate stage.** QMK ships an integer piecewise `cie_lightness()` citing jared.geek.nz (and therefore inherits that lineage's transcription risk — see above). Adafruit ships a fixed γ = 2.6 256-byte PROGMEM table. WLED computes `gammaT` at runtime with γ = 2.8 plus a matching inverse table.

Two incidental details land directly on the asymmetry and quantisation questions: QMK's sin⁴ table **opens and closes with ten literal zeros**, and WLED's `mode_breath()` warps phase with bit-shifts, **holds at zero for roughly the last fifth of the cycle**, and floors output at `lum = 30 + var`. That is a deliberate pause at the bottom of the exhale *plus* a minimum-on value, in shipping code.

> Confidence note: these code specifics come from the firmware angle's source reading and were not put through the adversarial verification pass. Read the current source before copying constants — QMK and WLED both churn here.

### 8-bit low-brightness quantisation

The problem is real and well documented: an 8-bit linear channel with a gamma or L\* curve stacked on top collapses the bottom of the range to a handful of distinct levels. Practitioners report that below roughly 2% perceived brightness a WS2812 degenerates to primaries only — you stop seeing colour and start seeing which of R/G/B happened to survive rounding.

Mitigations split three ways:

- **Temporal dithering.** FastLED's `BINARY_DITHER` engages only below `brightness 255` and uses a bit-reversed frame counter. Its quality is **directly proportional to `show()` call rate**, so WS2812's slow one-wire protocol and long strips are exactly the regime where it degrades into visible flicker and stripe artifacts (FastLED issue #1455). Dithering buys depth with refresh rate you may not have.
- **More effective bit depth in hardware.** APA102/HD107 carry a 5-bit global brightness field; FastLED drives this as pseudo-13-bit `APA102HD` mode.
- **Correcting for the LED's own transfer function instead of assuming linearity.** This is the sharpest and least-known point: cpldcpu's measurements show that *genuine* WS2812 dies already apply a non-linear 8→11-bit internal PWM mapping, giving 1:2048 dynamic range, while clones are strictly linear at 1:256. A software gamma table stacked on a genuine die is therefore **double-correcting** — and which behaviour you get depends on which die you were shipped.

The other accepted mitigation is the crude one visible in WLED's shipping code: a **minimum-on floor** (`lum = 30 + var`), which sidesteps the bottom of the range rather than resolving it.

> Confidence note: this section rests on the quantisation angle summary; the cpldcpu genuine-vs-clone finding in particular is the highest-value claim here and the one most worth re-verifying against his original measurements before you design around it.

## 相反する見解・不確実な点

**Killed claim — the asymmetry story attached to exp(sin).** A widely-repeated claim ("human breathing is ~2 s in / 3 s out, and exp(sin(x)) matches this because its peaks are narrower and troughs wider") was refuted on three independent grounds:

1. **The math is wrong and self-refuting.** `exp(sin(x))` is exactly symmetric about its peak — rise time equals fall time — so it *cannot* produce a 2 s-up / 3 s-down asymmetry. "Narrow peaks, wide troughs" describes how long the signal dwells near max vs. min, which is a different property from inhale-vs-exhale *duration*. The claim conflates the two.
2. **The rationale is misattributed.** Adam Shea's original justification was perceptual — correcting the log response of LED→eye→brain — not respiratory. The breathing-asymmetry reading is a later post-hoc gloss offered as a visual impression, never fitted to breathing data.
3. **The source refutes itself.** ThingPulse's own tuning multiplies `x` by `PI/2` for a **4-second** period, contradicting the 2+3 = 5 s premise; and its Credits concede that Pekker's photodiode measurement showed the *actual* curve is Gaussian, not `e^sin(x)`. The 2 s/3 s figure is given with no citation (the supporting evidence offered is literally "Try it!"), and the references linked beside it cover respiratory *rate* (~12 breaths/min) only, never an I:E duration split.

**Correct picture:** `exp(sin)` is a perceptual-brightness hack whose peak/trough shape is symmetric in time; the 2:3 asymmetry is unsourced; and the measured Apple waveform is Gaussian-like.

**Patent vs. hardware — unresolved.** The patent says ~1.8 s (~33 bpm) and a sinusoid; measurement of a shipping MacBook says ~5 s (~12 bpm) and a Gaussian ([US6658577B2](https://patents.google.com/patent/US6658577B2/en) vs. [avital.ca](https://avital.ca/notes/a-closer-look-at-apples-breathing-light)). Both are credible for what they are — an intent document from 2002 and a measurement from 2016 on hardware a decade newer. There is no source reconciling them, and no evidence Apple ever shipped the 1.8 s figure. The widely-cited "12 bpm because that's adult resting respiration" rationale is design commentary, **not** in the patent.

**Voisen's primary URL is dead.** `sean.voisen.org` 301s to `seanvoisen.com`, whose blog archive skips 2011; the 2011 post 404s. The Wayback capture is the canonical citable copy. Anyone citing "Voisen 2011" from memory is citing a page that no longer resolves.

**Scaling-constant rounding varies.** `255/(e − 1/e)` is stated as **108.0** in the primary chain; some independent re-derivations round to **108.4**. Both appear in circulating code; the difference is under half a PWM step at the top of the range.

**Unverified within this research:**
- Whether the CIE-119 transcription bug is still present in current `pwm-lightness` / mathiasvr gist heads (it was, at the time of the angle's source reading).
- Exact current QMK and WLED table values — cited from source reading, not adversarially verified.
- cpldcpu's genuine-vs-clone WS2812 internal-PWM finding — high-value, single-source, and consequential enough that it should be re-measured before you build a gamma pipeline on it.
- Gerald Recktenwald's EAS 199A handout (Portland State, Fall 2011, mirrored on SparkFun's CDN) is cited as the strongest independent side-by-side derivation of linear vs. sine vs. exp-sine, but was not re-fetched.
- Japanese-language sources: one documents the effect's retirement on T2-era Mac minis; no Japanese primary technical source on the curve itself surfaced.

## 参考ソース

- [ThingPulse: Breathing LEDs — Cracking the Algorithm Behind Our Breathing Pattern](https://thingpulse.com/breathing-leds-cracking-the-algorithm-behind-our-breathing-pattern/) — Traces the exp(sin) formula to Adam Shea's 2010 comment, derives the 0.36787944 / 42.5459 / 108.0 constants, and concedes in its own Credits that the measured Apple curve is Gaussian.
- [Avital Pekker: A Closer Look at Apple's Breathing Light](https://avital.ca/notes/a-closer-look-at-apples-breathing-light) — Photodiode + BeagleBone measurement of a real MacBook sleep LED (3000 samples @ 10 ms); fits a Gaussian (mean 18.045, σ 48.033), finds ~12 bpm, and argues plain sine fails because inter-breath transitions are too sharp.
- [Google Patents US6658577B2 — Breathing status LED indicator](https://patents.google.com/patent/US6658577B2/en) — Apple's primary source: positively-biased sinusoid, ~25% max duty, 125 Hz PWM, 6 mA peak, ~1.8 s period with a ~0.4 s quiet interval; no equation, no table, no bpm figure.
- [Adafruit: Reverse engineering the Mac breathing LED (2006)](https://blog.adafruit.com/2006/08/11/reverse-engineering-the-mac-breathing-led/) — Ladyada's original scope capture; documents the 1/R photocell linearization problem, the PWM peak-noise artefact, the "plain sinusoid doesn't match" complaint, and a reader's quartic fit.
- Sean Voisen, "Re-creating the 'breathing' LED" (2011) — the post that popularized the formula; the live URL now 404s, so cite the Wayback capture.
- Gerald Recktenwald, EAS 199A handout (Portland State, Fall 2011; mirrored on SparkFun's CDN) — independent side-by-side derivation of linear vs. sine vs. exp-sine brightness curves. *Not re-verified in this pass.*