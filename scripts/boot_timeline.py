"""The boot timeline: pure functions from time to what the splash shows.

Milestone B2 of docs/BOOT-EXPERIENCE.md covers Ignite and Gather, then an
endless loop. Time is seconds since the splash started. Nothing here touches
a clock, a GPU or a file, so all of it is unit-testable.

The Plymouth script cannot import Python, so scripts/gen-boot-assets.py writes
these constants into the generated script and the script repeats the formulas
below. tests/ checks that the committed script matches the generator.
"""

import math

# Phases (seconds).
IGNITE_END = 0.6  # the speck has become a lit seed
GATHER_END = 2.5  # the seed's light has reached the whole lattice

# Seed size, as a fraction of its largest size, and its slow, irregular breathing:
# (amplitude, cycles per second, phase). Two unrelated rates never line up.
SEED_SPECK = 0.12
SEED_FULL = 0.86
BREATH = ((0.06, 0.45, 0.0), (0.03, 0.83, 1.0))

# The light spreading from the seed, in sphere radii from the centre.
REVEAL_START = IGNITE_END * 0.6
REVEAL_FULL = 1.3  # past the limb, so every dot is fully lit
REVEAL_EDGE = 0.25  # width of the soft edge of the light

# Lattice: dots along meridians and parallels of a tilted, slowly turning sphere.
MERIDIAN_STEP = 30
DOT_STEP = 10
PARALLELS = (-60, -30, 0, 30, 60)
MAX_DOTS = 340  # sprite budget for the Plymouth script
TILT = math.radians(20)
SPIN_RATE = math.radians(10)  # per second
STILL_SPIN = math.radians(18)  # pose of the reduced-motion frame
DEPTH_BACK, DEPTH_FRONT = 0.2, 1.0


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def smooth(start, end, t):
    u = clamp((t - start) / (end - start))
    return u * u * (3 - 2 * u)


def seed_opacity(t):
    return smooth(0.0, IGNITE_END, t)


def seed_size(t):
    grown = SEED_SPECK + (SEED_FULL - SEED_SPECK) * smooth(0.0, GATHER_END, t)
    breath = sum(a * math.sin(2 * math.pi * rate * t + phase) for a, rate, phase in BREATH)
    return grown * (1 + breath)


def reveal_radius(t):
    return REVEAL_FULL * smooth(REVEAL_START, GATHER_END, t)


def spin(t):
    return SPIN_RATE * max(0.0, t)


def lattice_dots():
    """Latitude and longitude, in radians, of every dot."""
    dots = []
    for lon in range(0, 360, MERIDIAN_STEP):
        for lat in range(-90 + DOT_STEP, 90, DOT_STEP):
            dots.append((lat, lon))
    for lat in PARALLELS:
        for lon in range(0, 360, DOT_STEP):
            if lon % MERIDIAN_STEP:
                dots.append((lat, lon))
    return [(math.radians(lat), math.radians(lon)) for lat, lon in dots]


def project(lat, lon, spin_angle):
    """Unit-sphere position of a dot: x right, y up, z towards the viewer."""
    around = lon + spin_angle
    x = math.cos(lat) * math.sin(around)
    depth = math.cos(lat) * math.cos(around)
    y = math.sin(lat) * math.cos(TILT) - depth * math.sin(TILT)
    z = math.sin(lat) * math.sin(TILT) + depth * math.cos(TILT)
    return x, y, z


def depth_cue(z):
    return DEPTH_BACK + (DEPTH_FRONT - DEPTH_BACK) * (z + 1) / 2


def lit(x, y, radius):
    """How much of the seed's light has reached a dot at screen position (x, y).

    Written with squared distances (no square root) so the Plymouth script,
    which repeats this for every dot on every frame, stays cheap.
    """
    if radius <= 0:
        return 0.0
    return clamp((radius * radius - (x * x + y * y)) / (2 * radius * REVEAL_EDGE))


def dot_opacity(lat, lon, t):
    x, y, z = project(lat, lon, spin(t))
    return lit(x, y, reveal_radius(t)) * depth_cue(z)


def still_frame():
    """The reduced-motion frame: the gathered state, in a fixed pose."""
    return {
        "seed_opacity": 1.0,
        "seed_size": SEED_FULL,
        "reveal_radius": REVEAL_FULL,
        "spin": STILL_SPIN,
    }


# --- Honest progress (milestone B3) -------------------------------------------
#
# systemd tells Plymouth the name of every service that finishes starting. Each
# region of the lattice (a 60 degree slice of longitude) wakes, taking its
# colour, when its milestone service is up. Nothing is estimated or faked.

MILESTONES = (
    ("systemd-journald.service", "logging"),
    ("systemd-udevd.service", "devices"),
    ("systemd-tmpfiles-setup.service", "filesystems"),
    ("dbus.service", "message bus"),
    ("systemd-logind.service", "seats and login"),
    ("systemd-user-sessions.service", "sessions"),
)
REGION_COLOURS = (
    (58, 214, 197),  # teal
    (74, 163, 255),  # azure
    (155, 123, 255),  # violet
    (255, 111, 168),  # rose
    (255, 179, 71),  # amber
    (226, 234, 250),  # ice
)
REGION_SPAN = 360 // len(MILESTONES)
WAKE_SECONDS = 0.7
ASLEEP_GLOW = 0.45  # a region lit by the seed but not yet awake


def region_of(lon_degrees):
    return int(lon_degrees % 360) // REGION_SPAN


def readiness(events):
    """Which regions are awake after a stream of status events.

    Unknown events are ignored, repeats change nothing, and a region never goes
    back to sleep: progress can only move forward.
    """
    names = [name for name, _ in MILESTONES]
    awake = [False] * len(names)
    for event in events:
        if event in names:
            awake[names.index(event)] = True
    return awake


def wake_level(t, woke_at):
    """0 while asleep, rising smoothly to 1 after the region's milestone."""
    if woke_at is None:
        return 0.0
    return smooth(woke_at, woke_at + WAKE_SECONDS, t)


def region_glow(level):
    return ASLEEP_GLOW + (1 - ASLEEP_GLOW) * level
