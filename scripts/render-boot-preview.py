#!/usr/bin/env python3
"""Render a concept video of the SpheradianOS boot sequence (docs/BOOT-EXPERIENCE.md).

This is a design preview, not the boot code: it draws the five phases
(Ignite, Gather, Wake, Resolve, Unfold) with a fixed, typical timing and
synthesises the sound from the same timeline. Everything is generated here;
no external assets are used.

Usage: scripts/render-boot-preview.py [--signature N] [--out-dir DIR]
Needs Pillow (development tool only; nothing here ships in the image).
Output: an AVI (MJPEG video + PCM audio), the sound alone as WAV, and a contact sheet PNG.
"""

import argparse
import io
import math
import random
import struct
from multiprocessing import Pool, cpu_count
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

WIDTH, HEIGHT, SUPERSAMPLE, FPS = 1280, 720, 2, 30
SAMPLE_RATE = 44100

# Timeline (seconds). The real boot is elastic; this is one typical run.
T_IGNITE, T_GATHER, T_WAKE, T_RESOLVE, T_UNFOLD, T_SETTLE, T_END = (
    1.0,
    2.5,
    4.5,
    8.0,
    8.8,
    10.3,
    12.5,
)
# Irregular on purpose: each region wakes when its (simulated) milestone completes.
MILESTONES = (4.7, 5.3, 5.8, 6.5, 7.0, 7.5)

# Original palette: a neutral seed, one colour per trust-domain region.
SEED_COOL = (225, 235, 255)
SEED_HOT = (255, 238, 205)
DOMAIN_COLOURS = (
    (58, 214, 197),  # teal
    (74, 163, 255),  # azure
    (155, 123, 255),  # violet
    (255, 111, 168),  # rose
    (255, 179, 71),  # amber
    (226, 234, 250),  # ice
)

CAMERA_DISTANCE = 3.2
FOCAL = 610.0
NEAR = 0.15
TILT = math.radians(20)
SPIN_RATE = math.radians(10)
FINAL_RADIUS = 6.0


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def smooth(start, end, t):
    u = clamp((t - start) / (end - start))
    return u * u * (3 - 2 * u)


def lerp(a, b, u):
    return a + (b - a) * u


def scaled(colour, gain):
    return tuple(int(clamp(c * gain, 0, 255)) for c in colour)


# ---------------------------------------------------------------- geometry


def build_lattice():
    """Unit-sphere polylines as lists of (x, y, z, sector)."""
    curves = []
    for lon_deg in range(0, 360, 30):
        curves.append([sphere_point(lon_deg, lat) for lat in range(-90, 91, 3)])
    for lat_deg in (-60, -30, 0, 30, 60):
        curves.append([sphere_point(lon, lat_deg) for lon in range(0, 361, 3)])
    return curves


def sphere_point(lon_deg, lat_deg):
    lon, lat = math.radians(lon_deg), math.radians(lat_deg)
    sector = int((lon_deg % 360) // 60)
    return (
        math.cos(lat) * math.sin(lon),
        math.sin(lat),
        math.cos(lat) * math.cos(lon),
        sector,
    )


LATTICE = build_lattice()


def spin_angle(t):
    if t < T_GATHER:
        return 0.0
    if t < T_UNFOLD:
        return SPIN_RATE * (t - T_GATHER)
    span = T_SETTLE + 0.7 - T_UNFOLD
    tau = min(t - T_UNFOLD, span)
    return SPIN_RATE * (T_UNFOLD - T_GATHER) + SPIN_RATE * (tau - tau * tau / (2 * span))


def sphere_radius(t):
    u = clamp((t - T_UNFOLD) / (T_SETTLE - T_UNFOLD))
    return lerp(1.0, FINAL_RADIUS, 1 - (1 - u) ** 3)


def rotate(point, spin):
    x, y, z = point[0], point[1], point[2]
    x, z = x * math.cos(spin) + z * math.sin(spin), -x * math.sin(spin) + z * math.cos(spin)
    y, z = y * math.cos(TILT) - z * math.sin(TILT), y * math.sin(TILT) + z * math.cos(TILT)
    return x, y, z


def project(x, y, z):
    """World point to supersampled screen coordinates, or None if behind the camera."""
    depth = CAMERA_DISTANCE - z
    if depth < NEAR:
        return None
    k = FOCAL * SUPERSAMPLE / depth
    return (WIDTH * SUPERSAMPLE / 2 + x * k, HEIGHT * SUPERSAMPLE / 2 - y * k, depth)


# ------------------------------------------------------------------ layers


def lattice_segments(t):
    spin, radius = spin_angle(t), sphere_radius(t)
    inside = smooth(T_UNFOLD, T_SETTLE, t)
    release_flash = 1 + 1.1 * math.exp(-(((t - T_UNFOLD - 0.15) / 0.35) ** 2))
    wake = [smooth(m, m + 0.7, t) for m in MILESTONES]
    segments = []
    for curve in LATTICE:
        previous = None
        for point in curve:
            x, y, z = rotate(point, spin)
            screen = project(x * radius, y * radius, z * radius)
            if previous and screen and wake[point[3]] > 0.02:
                depth = (screen[2] + previous[2]) / 2
                outside_cue = 0.3 + 0.7 * smooth(-0.3, 0.3, z)
                inside_cue = clamp(11.0 / depth, 0.6, 1.2)
                gain = 0.85 * wake[point[3]] * lerp(outside_cue, inside_cue, inside) * release_flash
                width = round(SUPERSAMPLE * clamp(2.0 * CAMERA_DISTANCE / depth, 2.0, 5.0))
                segments.append(
                    (depth, previous[:2], screen[:2], scaled(DOMAIN_COLOURS[point[3]], gain), width)
                )
            previous = screen
    segments.sort(key=lambda s: -s[0])
    return segments


PANELS = (  # yaw, pitch, half-width, half-height (degrees), domain, fade-in start
    (-27, 2, 12, 8, 1, 10.6),
    (4, 5, 15, 10, 5, 10.8),
    (33, -2, 11, 8, 2, 11.0),
)


def panel_outline(yaw, pitch, half_w, half_h):
    """Outline of a window resting on the inner sphere, as screen points."""
    corners = ((-1, -1), (1, -1), (1, 1), (-1, 1))
    points = []
    for i, (ax, ay) in enumerate(corners):
        bx, by = corners[(i + 1) % 4]
        for step in range(8):
            u = step / 8
            a = math.radians(yaw + lerp(ax, bx, u) * half_w)
            b = math.radians(pitch + lerp(ay, by, u) * half_h)
            screen = project(
                FINAL_RADIUS * math.sin(a) * math.cos(b),
                FINAL_RADIUS * math.sin(b),
                -FINAL_RADIUS * math.cos(a) * math.cos(b),
            )
            points.append(screen[:2])
    return points


def draw_desktop(draw, t):
    for yaw, pitch, half_w, half_h, domain, start in PANELS:
        shown = smooth(start, start + 0.8, t)
        if shown <= 0:
            continue
        colour = DOMAIN_COLOURS[domain]
        outline = panel_outline(yaw, pitch, half_w, half_h)
        draw.polygon(outline, fill=scaled(colour, 0.10 * shown))
        title_bar = panel_outline(yaw, pitch + half_h * 0.82, half_w, half_h * 0.18)
        draw.polygon(title_bar, fill=scaled(colour, 0.32 * shown))
        draw.line(outline + outline[:1], fill=scaled(colour, 0.95 * shown), width=SUPERSAMPLE * 2)
    draw_mini_globe(draw, smooth(10.9, 11.7, t))


def draw_mini_globe(draw, shown):
    if shown <= 0:
        return
    s = SUPERSAMPLE
    cx, cy, r = (WIDTH - 92) * s, 84 * s, 34 * s
    colour = scaled(DOMAIN_COLOURS[5], 0.8 * shown)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=colour, width=s * 2)
    for squash in (0.33, 0.72):
        draw.ellipse((cx - r * squash, cy - r, cx + r * squash, cy + r), outline=colour, width=s)
        draw.ellipse((cx - r, cy - r * squash, cx + r, cy + r * squash), outline=colour, width=s)


def render_lattice(t):
    image = Image.new("RGB", (WIDTH * SUPERSAMPLE, HEIGHT * SUPERSAMPLE))
    draw = ImageDraw.Draw(image)
    for _, start, end, colour, width in lattice_segments(t):
        draw.line((start, end), fill=colour, width=width)
    if t > 10.5:
        draw_desktop(draw, t)
    sharp = image.resize((WIDTH, HEIGHT), Image.LANCZOS)
    glow = ImageChops.add(
        sharp.filter(ImageFilter.GaussianBlur(5)).point(lambda v: int(v * 0.9)),
        sharp.filter(ImageFilter.GaussianBlur(20)).point(lambda v: int(v * 0.6)),
    )
    return ImageChops.add(sharp, glow)


def seed_state(t):
    """Seed radius (px), wobble amplitude, opacity and heat for time t."""
    if t < T_IGNITE:
        return 0.0, 0.0, 0.0, 0.0
    if t < T_GATHER:
        u = smooth(T_IGNITE, T_GATHER, t)
        return lerp(1.5, 6, u), 0.0, lerp(0.0, 0.75, u), 0.0
    if t < T_WAKE:
        u = smooth(T_GATHER, T_WAKE, t)
        return lerp(6, 38, u), lerp(0.04, 0.11, u), lerp(0.75, 1.0, u), 0.0
    if t < T_RESOLVE:
        u = (t - T_WAKE) / (T_RESOLVE - T_WAKE)
        activity = sum(math.exp(-(t - m) / 0.4) for m in MILESTONES if t >= m)
        return lerp(38, 47, u), 0.11 + 0.12 * u + 0.07 * min(activity, 1.5), 1.0, 0.0
    if t < T_UNFOLD:
        u = smooth(T_RESOLVE, T_UNFOLD, t)
        return lerp(47, 20, u), lerp(0.25, 0.04, u), 1.0, u
    u = clamp((t - T_UNFOLD) / 0.55)
    return lerp(20, 120, u), 0.04, (1 - u) ** 2, 1 - u


def build_halo(size=384):
    """Smooth radial falloff, computed once, so halos have no banding or edges."""
    halo = Image.new("L", (size, size))
    half = size / 2
    halo.putdata(
        [
            int(255 * math.exp(-(((x + 0.5 - half) ** 2 + (y + 0.5 - half) ** 2) / (half * 0.42) ** 2)))
            if (x + 0.5 - half) ** 2 + (y + 0.5 - half) ** 2 < half * half
            else 0
            for y in range(size)
            for x in range(size)
        ]
    )
    return halo


HALO = build_halo()


def paste_halo(light, diameter, gain):
    diameter = int(min(diameter, HEIGHT * 1.6))
    if diameter < 4 or gain <= 0:
        return light
    halo = HALO.resize((diameter, diameter), Image.BICUBIC).point(lambda v: int(min(255, v * gain)))
    layer = Image.new("L", light.size)
    layer.paste(halo, ((light.width - diameter) // 2, (light.height - diameter) // 2))
    return ImageChops.add(light, layer)


def render_seed(t, phases):
    """Full-frame RGB light of the seed: a rippling body plus smooth halos."""
    radius, wobble, opacity, heat = seed_state(t)
    if opacity <= 0:
        return None
    s = SUPERSAMPLE
    tile = int(min(HEIGHT, max(64, radius * 4))) // 2 * 2
    mask = Image.new("L", (tile * s, tile * s))
    centre = tile * s / 2
    outline = []
    for i in range(120):
        angle = 2 * math.pi * i / 120
        ripple = sum(
            weight * math.sin(k * angle + speed * t + phase)
            for k, (weight, speed, phase) in enumerate(phases, start=2)
        )
        r = radius * s * (1 + wobble * ripple)
        outline.append((centre + r * math.cos(angle), centre + r * math.sin(angle)))
    brightness = opacity * (1 + 0.5 * heat)
    ImageDraw.Draw(mask).polygon(outline, fill=int(min(255, 255 * brightness)))
    body = mask.resize((tile, tile), Image.LANCZOS).filter(ImageFilter.GaussianBlur(max(0.6, radius * 0.18)))
    light = Image.new("L", (WIDTH, HEIGHT))
    light.paste(body, ((WIDTH - tile) // 2, (HEIGHT - tile) // 2))
    light = paste_halo(light, radius * 5, 0.55 * brightness)
    light = paste_halo(light, radius * 14, 0.22 * brightness)
    colour = tuple(lerp(c, h, heat) for c, h in zip(SEED_COOL, SEED_HOT, strict=True))
    return Image.merge("RGB", [light.point(lambda v, c=c: int(v * c / 255)) for c in colour])


def load_font(size):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_wordmark(frame, t):
    shown = smooth(10.9, 11.6, t)
    if shown <= 0:
        return
    draw = ImageDraw.Draw(frame)
    font = load_font(20)
    text, spacing = "SPHERADIANOS", 9
    widths = [draw.textlength(ch, font=font) for ch in text]
    x = (WIDTH - sum(widths) - spacing * (len(text) - 1)) / 2
    for ch, width in zip(text, widths, strict=True):
        draw.text((x, HEIGHT - 78), ch, font=font, fill=scaled(DOMAIN_COLOURS[5], 0.75 * shown))
        x += width + spacing


def render_frame(args):
    index, signature = args
    t = index / FPS
    phases = seed_phases(signature)
    frame = render_lattice(t) if t >= MILESTONES[0] else Image.new("RGB", (WIDTH, HEIGHT))
    seed = render_seed(t, phases)
    if seed:
        frame = ImageChops.add(frame, seed)
    draw_wordmark(frame, t)
    buffer = io.BytesIO()
    frame.save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


def seed_phases(signature):
    """Per-boot signature: small variations so no two boots move alike."""
    rng = random.Random(signature)
    return [
        (rng.uniform(0.5, 1.0) / k, rng.uniform(1.2, 3.4) * rng.choice((-1, 1)), rng.uniform(0, 6.283))
        for k in range(2, 7)
    ]


# ------------------------------------------------------------------- sound


# D major pentatonic, ascending: one soft bell per region that wakes.
MILESTONE_NOTES = (293.66, 369.99, 440.00, 493.88, 587.33, 659.25)
# Quickening run during Resolve, then the chord that the release lands on.
RESOLVE_RUN = ((8.05, 739.99), (8.27, 880.00), (8.45, 987.77), (8.59, 1174.66), (8.70, 1318.51))
RELEASE_CHORD = (146.83, 220.00, 293.66, 369.99, 440.00, 659.25)  # D major, added ninth


def render_audio(signature):
    """Soft bells that climb as regions wake, over a warm pad, resolving into a chord.

    Only sine partials with gentle envelopes are used: no sawtooth-like stacks
    and no pitch glides, which are what make a synthetic swell sound harsh.
    """
    rng = random.Random(signature)
    total = int(T_END * SAMPLE_RATE)
    left, right = [0.0] * total, [0.0] * total
    add_pad(left, right)
    # The seed is audible from its first frame: a high glint as the speck appears,
    # then two low notes as it gains body, leading into the climb of the regions.
    add_bell(left, right, T_IGNITE + 0.05, 1174.66, 0.12, 0.5, decay=0.9)
    add_bell(left, right, T_GATHER, 146.83, 0.16, 0.45, decay=0.9)
    add_bell(left, right, T_GATHER + 1.0, 220.00, 0.16, 0.55, decay=0.8)
    add_seed_breath(left, right, rng)
    for i, (when, freq) in enumerate(zip(MILESTONES, MILESTONE_NOTES, strict=True)):
        add_bell(left, right, when + rng.uniform(0.0, 0.03), freq, 0.20 + 0.03 * i, 0.3 + 0.4 * (i % 2))
    for i, (when, freq) in enumerate(RESOLVE_RUN):
        add_bell(
            left,
            right,
            when + rng.uniform(-0.01, 0.01),
            freq,
            0.14 + 0.02 * i,
            0.7 - 0.4 * (i % 2),
            decay=0.35,
        )
    add_release_chord(left, right)
    add_bell(left, right, T_UNFOLD + 0.06, 1174.66, 0.16, 0.5, decay=1.1)
    # Impact layers (docs/BOOT-EXPERIENCE.md, Appendix B): spectrum moves, level stays modest.
    add_breath_sweep(left, right, rng)
    add_low_bloom(left, right)
    add_air_shimmer(left, right, rng)
    left, right = add_reverb(left, 0), add_reverb(right, 23)
    return to_pcm(left, right)


def add_bell(left, right, onset, freq, level, pan, decay=0.55):
    """A glassy, mellow note: a sine with two quiet, faster-fading overtones."""
    partials = ((1.0, 1.0, 1.0), (2.0, 0.22, 0.5), (3.0, 0.06, 0.3))
    start = int(onset * SAMPLE_RATE)
    for n in range(start, min(len(left), start + int(decay * 7 * SAMPLE_RATE))):
        age = (n - start) / SAMPLE_RATE
        attack = smooth(0.0, 0.012, age)
        tone = sum(
            weight * math.exp(-age / (decay * fade)) * math.sin(2 * math.pi * freq * ratio * age)
            for ratio, weight, fade in partials
        )
        left[n] += level * attack * tone * (1 - pan)
        right[n] += level * attack * tone * pan


def add_pad(left, right):
    """A quiet, slowly breathing bed under the bells; it hands over to the chord."""
    voices = ((146.83, 0.0), (220.00, 1.3), (293.66, 2.1))
    for n in range(int(T_IGNITE * SAMPLE_RATE), int((T_UNFOLD + 1.0) * SAMPLE_RATE)):
        t = n / SAMPLE_RATE
        # Present from the first speck of light, then swelling as the lattice wakes.
        build = 0.35 * smooth(T_IGNITE, T_IGNITE + 1.0, t) + 0.65 * smooth(T_WAKE, T_UNFOLD, t) ** 2
        level = 0.09 * build * (1 - smooth(T_UNFOLD, T_UNFOLD + 1.0, t))
        breath = 1 + 0.15 * math.sin(2 * math.pi * 0.31 * t) + 0.08 * math.sin(2 * math.pi * 0.83 * t + 1.0)
        for freq, phase in voices:
            left[n] += level * breath * math.sin(2 * math.pi * freq * 0.9985 * t + phase)
            right[n] += level * breath * math.sin(2 * math.pi * freq * 1.0015 * t + phase)


def add_release_chord(left, right):
    for i, freq in enumerate(RELEASE_CHORD):
        onset = T_UNFOLD + 0.025 * i
        pan = 0.5 + 0.3 * math.sin(i * 2.1)
        level = 0.13 / (1 + 0.25 * i)
        for n in range(int(onset * SAMPLE_RATE), len(left)):
            age = n / SAMPLE_RATE - onset
            envelope = smooth(0.0, 0.14, age) * math.exp(-age / 2.0)
            tone = math.sin(2 * math.pi * freq * age) + 0.18 * math.sin(4 * math.pi * freq * age)
            left[n] += level * envelope * tone * (1 - pan)
            right[n] += level * envelope * tone * pan


def filtered_noise(rng, cutoff, state, highpass=False):
    """One sample of white noise through a state-variable filter (band- or high-pass)."""
    f = 2 * math.sin(math.pi * min(cutoff, SAMPLE_RATE / 7) / SAMPLE_RATE)
    state[0] += f * state[1]
    high = rng.uniform(-1, 1) - state[0] - 0.7 * state[1]
    state[1] += f * high
    return high if highpass else state[1]


def add_seed_breath(left, right, rng):
    """A faint, slow breathing of air while the seed gathers: it sounds alive."""
    states = ([0.0, 0.0], [0.0, 0.0])
    start, end = T_IGNITE + 0.4, T_WAKE + 0.5
    for n in range(int(start * SAMPLE_RATE), int(end * SAMPLE_RATE)):
        t = n / SAMPLE_RATE
        swell = 0.6 + 0.4 * math.sin(2 * math.pi * 0.45 * t)
        level = 0.03 * smooth(start, start + 1.4, t) * (1 - smooth(end - 0.8, end, t)) * swell
        cutoff = 700 + 300 * math.sin(2 * math.pi * 0.2 * t)
        left[n] += level * filtered_noise(rng, cutoff, states[0])
        right[n] += level * filtered_noise(rng, cutoff, states[1])


def add_breath_sweep(left, right, rng):
    """A breath-like riser under the Resolve run: brightness climbs, then lets go."""
    states = ([0.0, 0.0], [0.0, 0.0])
    for n in range(int(T_RESOLVE * SAMPLE_RATE), int((T_UNFOLD + 0.1) * SAMPLE_RATE)):
        t = n / SAMPLE_RATE
        u = clamp((t - T_RESOLVE) / (T_UNFOLD - T_RESOLVE))
        cutoff = 250 * 14**u
        level = 0.09 * u**1.5 * (1 - smooth(T_UNFOLD - 0.02, T_UNFOLD + 0.1, t))
        left[n] += level * filtered_noise(rng, cutoff, states[0])
        right[n] += level * filtered_noise(rng, cutoff, states[1])


def add_low_bloom(left, right):
    """A round low swell on the release, doubled an octave up for small speakers."""
    voices = ((36.71, 0.10), (73.42, 0.22), (146.83, 0.12))
    phases = [0.0] * len(voices)
    start = int(T_UNFOLD * SAMPLE_RATE)
    for n in range(start, min(len(left), start + int(6 * SAMPLE_RATE))):
        age = (n - start) / SAMPLE_RATE
        envelope = smooth(0.0, 0.09, age) * math.exp(-age / 1.4)
        settle = 1 + 0.06 * math.exp(-age / 0.05)  # lands from slightly above: a soft "drop"
        sample = 0.0
        for i, (freq, level) in enumerate(voices):
            phases[i] += 2 * math.pi * freq * settle / SAMPLE_RATE
            sample += level * math.sin(phases[i])
        left[n] += envelope * sample
        right[n] += envelope * sample


def add_air_shimmer(left, right, rng):
    """A brief, quiet breath of high-frequency air as the shell passes the viewer."""
    states = ([0.0, 0.0], [0.0, 0.0])
    start = int(T_UNFOLD * SAMPLE_RATE)
    for n in range(start, start + int(1.2 * SAMPLE_RATE)):
        age = (n - start) / SAMPLE_RATE
        level = 0.035 * smooth(0.0, 0.03, age) * math.exp(-age / 0.28)
        left[n] += level * filtered_noise(rng, 5000, states[0], highpass=True)
        right[n] += level * filtered_noise(rng, 5000, states[1], highpass=True)


def add_reverb(dry, offset, wet=0.28):
    """Small Schroeder reverb (four damped combs, two all-passes) for a sense of space."""
    combs = [[0.0] * (length + offset) for length in (1557, 1617, 1491, 1422)]
    passes = [[0.0] * (length + offset) for length in (556, 225)]
    damp = [0.0] * len(combs)
    positions = [0] * (len(combs) + len(passes))
    out = [0.0] * len(dry)
    for n, sample in enumerate(dry):
        mixed = 0.0
        for i, line in enumerate(combs):
            delayed = line[positions[i]]
            damp[i] = delayed * 0.6 + damp[i] * 0.4
            line[positions[i]] = sample + damp[i] * 0.80
            positions[i] = (positions[i] + 1) % len(line)
            mixed += delayed
        mixed *= 0.25
        for j, line in enumerate(passes, start=len(combs)):
            delayed = line[positions[j]]
            line[positions[j]] = mixed + delayed * 0.5
            positions[j] = (positions[j] + 1) % len(line)
            mixed = delayed - mixed * 0.5
        out[n] = sample + wet * mixed
    return out


def to_pcm(left, right):
    """Normalise with headroom, fade the tail to silence, pack as 16-bit stereo."""
    peak = max(max(map(abs, left)), max(map(abs, right))) or 1.0
    # Peak at -12 dBFS: a boot sound doubles as a volume reference, so it stays modest.
    gain = 0.25 * 32767 / peak
    fade_from = T_END - 1.0
    frames = []
    for n, (left_sample, right_sample) in enumerate(zip(left, right, strict=True)):
        tail = 1 - smooth(fade_from, T_END - 0.05, n / SAMPLE_RATE)
        frames.append(struct.pack("<hh", int(left_sample * gain * tail), int(right_sample * gain * tail)))
    return b"".join(frames)


def write_wav(path, pcm):
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(pcm),
        b"WAVE",
        b"fmt ",
        16,
        1,
        2,
        SAMPLE_RATE,
        SAMPLE_RATE * 4,
        4,
        16,
        b"data",
        len(pcm),
    )
    path.write_bytes(header + pcm)


# --------------------------------------------------------------------- AVI


def chunk(tag, body):
    return tag + struct.pack("<I", len(body)) + body + (b"\x00" if len(body) % 2 else b"")


def riff_list(kind, body):
    return chunk(b"LIST", kind + body)


def write_avi(path, frames, pcm):
    """Minimal AVI: one MJPEG stream and one 16-bit stereo PCM stream, interleaved."""
    block = 4
    per_frame = SAMPLE_RATE // FPS * block
    movi, index, offset = [], [], 4
    for i, jpeg in enumerate(frames):
        for tag, body in ((b"00dc", jpeg), (b"01wb", pcm[i * per_frame : (i + 1) * per_frame])):
            if not body:
                continue
            index.append(tag + struct.pack("<III", 0x10, offset, len(body)))
            data = chunk(tag, body)
            movi.append(data)
            offset += len(data)
    biggest = max(len(f) for f in frames)
    main_header = struct.pack(
        "<14I",
        1_000_000 // FPS,
        biggest * FPS,
        0,
        0x110,
        len(frames),
        0,
        2,
        biggest,
        WIDTH,
        HEIGHT,
        0,
        0,
        0,
        0,
    )
    video = riff_list(
        b"strl",
        chunk(
            b"strh",
            struct.pack(
                "<4s4sIHHIIIIIIII4H",
                b"vids",
                b"MJPG",
                0,
                0,
                0,
                0,
                1,
                FPS,
                0,
                len(frames),
                biggest,
                10000,
                0,
                0,
                0,
                WIDTH,
                HEIGHT,
            ),
        )
        + chunk(
            b"strf",
            struct.pack(
                "<IiiHH4sIiiII",
                40,
                WIDTH,
                HEIGHT,
                1,
                24,
                b"MJPG",
                WIDTH * HEIGHT * 3,
                0,
                0,
                0,
                0,
            ),
        ),
    )
    audio = riff_list(
        b"strl",
        chunk(
            b"strh",
            struct.pack(
                "<4s4sIHHIIIIIIII4H",
                b"auds",
                b"\x00" * 4,
                0,
                0,
                0,
                0,
                1,
                SAMPLE_RATE,
                0,
                len(pcm) // block,
                per_frame,
                0,
                block,
                0,
                0,
                0,
                0,
            ),
        )
        + chunk(
            b"strf",
            struct.pack(
                "<HHIIHH",
                1,
                2,
                SAMPLE_RATE,
                SAMPLE_RATE * block,
                block,
                16,
            ),
        ),
    )
    body = (
        b"AVI "
        + riff_list(b"hdrl", chunk(b"avih", main_header) + video + audio)
        + riff_list(b"movi", b"".join(movi))
        + chunk(b"idx1", b"".join(index))
    )
    path.write_bytes(chunk(b"RIFF", body))


def write_contact_sheet(path, frames):
    times = (1.9, 3.6, 5.6, 7.6, 8.7, 9.1, 9.7, 12.2)
    cell_w, cell_h = WIDTH // 2, HEIGHT // 2
    sheet = Image.new("RGB", (cell_w * 4, cell_h * 2))
    for i, t in enumerate(times):
        frame = Image.open(io.BytesIO(frames[int(t * FPS)])).resize((cell_w, cell_h), Image.LANCZOS)
        sheet.paste(frame, ((i % 4) * cell_w, (i // 4) * cell_h))
    sheet.save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--signature", type=int, default=2026, help="per-boot signature seed")
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent.parent / "preview")
    options = parser.parse_args()
    options.out_dir.mkdir(parents=True, exist_ok=True)

    count = int(T_END * FPS)
    with Pool(max(1, cpu_count() - 2)) as pool:
        frames = pool.map(render_frame, [(i, options.signature) for i in range(count)], chunksize=4)
    pcm = render_audio(options.signature)

    video = options.out_dir / "spheradianos-boot-concept.avi"
    sheet = options.out_dir / "spheradianos-boot-concept-frames.png"
    write_avi(video, frames, pcm)
    write_wav(options.out_dir / "spheradianos-boot-concept.wav", pcm)
    write_contact_sheet(sheet, frames)
    print(f"wrote {video} ({video.stat().st_size // 1024} KiB, {count} frames)")
    print(f"wrote {sheet}")


if __name__ == "__main__":
    main()
