"""Unit and property tests for the boot timeline (BOOT-EXPERIENCE.md, milestone B2).

The timeline is pure: time in, numbers out. No GPU, clock or I/O.
Run from the repository root: python3 -m unittest discover -s tests -v
"""

import importlib.util
import math
import random
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_timeline():
    path = ROOT / "scripts" / "boot_timeline.py"
    spec = importlib.util.spec_from_file_location("boot_timeline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


timeline = load_timeline()
RNG = random.Random(20261115)
TIMES = [0.0, timeline.IGNITE_END, timeline.GATHER_END] + [RNG.uniform(0, 600) for _ in range(500)]


class Seed(unittest.TestCase):
    def test_starts_invisible(self):
        self.assertEqual(timeline.seed_opacity(0.0), 0.0)

    def test_is_fully_lit_after_ignite(self):
        self.assertEqual(timeline.seed_opacity(timeline.IGNITE_END), 1.0)

    def test_opacity_never_decreases_and_stays_in_range(self):
        previous = 0.0
        for t in sorted(TIMES):
            opacity = timeline.seed_opacity(t)
            self.assertGreaterEqual(opacity, previous)
            self.assertLessEqual(opacity, 1.0)
            previous = opacity

    def test_size_stays_within_its_bounds_forever(self):
        for t in TIMES:
            self.assertGreater(timeline.seed_size(t), 0.0)
            self.assertLessEqual(timeline.seed_size(t), 1.0)

    def test_breathing_is_gentle_and_slow(self):
        # Photosensitivity: small amplitude, far below three cycles per second.
        self.assertLess(sum(amplitude for amplitude, _, _ in timeline.BREATH), 0.15)
        self.assertLess(max(rate for _, rate, _ in timeline.BREATH), 1.5)


class Lattice(unittest.TestCase):
    def test_dot_count_respects_the_sprite_budget(self):
        self.assertLessEqual(len(timeline.lattice_dots()), timeline.MAX_DOTS)

    def test_dots_are_unique(self):
        dots = [(round(lat, 6), round(lon, 6)) for lat, lon in timeline.lattice_dots()]
        self.assertEqual(len(dots), len(set(dots)))

    def test_every_projected_dot_lies_on_the_unit_sphere(self):
        for lat, lon in timeline.lattice_dots():
            for t in TIMES[:20]:
                x, y, z = timeline.project(lat, lon, timeline.spin(t))
                self.assertAlmostEqual(x * x + y * y + z * z, 1.0, places=9)

    def test_spin_never_runs_backwards(self):
        ordered = sorted(TIMES)
        for earlier, later in zip(ordered, ordered[1:]):
            self.assertLessEqual(timeline.spin(earlier), timeline.spin(later))


class Reveal(unittest.TestCase):
    def test_nothing_is_revealed_before_the_seed_is_lit(self):
        self.assertEqual(timeline.reveal_radius(0.0), 0.0)
        for lat, lon in timeline.lattice_dots():
            self.assertEqual(timeline.dot_opacity(lat, lon, 0.0), 0.0)

    def test_reveal_never_retreats(self):
        previous = 0.0
        for t in sorted(TIMES):
            radius = timeline.reveal_radius(t)
            self.assertGreaterEqual(radius, previous)
            previous = radius

    def test_the_whole_lattice_is_lit_once_gathered_and_stays_lit(self):
        for t in [timeline.GATHER_END] + [x for x in TIMES if x > timeline.GATHER_END]:
            for lat, lon in timeline.lattice_dots():
                self.assertGreater(timeline.dot_opacity(lat, lon, t), 0.0)

    def test_dot_opacity_is_always_a_valid_opacity(self):
        for t in TIMES[:60]:
            for lat, lon in timeline.lattice_dots():
                self.assertTrue(0.0 <= timeline.dot_opacity(lat, lon, t) <= 1.0)

    def test_front_dots_are_brighter_than_back_dots(self):
        self.assertGreater(timeline.depth_cue(1.0), timeline.depth_cue(-1.0))
        self.assertGreater(timeline.depth_cue(-1.0), 0.0)


class StillFrame(unittest.TestCase):
    def test_still_frame_is_the_gathered_state(self):
        still = timeline.still_frame()
        self.assertEqual(still["seed_opacity"], 1.0)
        self.assertGreaterEqual(still["reveal_radius"], timeline.REVEAL_FULL)

    def test_still_frame_does_not_depend_on_time(self):
        self.assertEqual(timeline.still_frame(), timeline.still_frame())


class Loop(unittest.TestCase):
    def test_the_sequence_never_ends_or_stalls_on_a_slow_boot(self):
        # Ten minutes in, the seed still breathes and the sphere still turns.
        late = 600.0
        self.assertNotEqual(timeline.seed_size(late), timeline.seed_size(late + 0.7))
        self.assertGreater(timeline.spin(late + 1.0), timeline.spin(late))
        self.assertTrue(math.isfinite(timeline.spin(late)))



class Readiness(unittest.TestCase):
    NAMES = [name for name, _ in timeline.MILESTONES]

    def test_nothing_is_awake_before_any_event(self):
        self.assertEqual(timeline.readiness([]), [False] * len(self.NAMES))

    def test_each_milestone_wakes_exactly_its_own_region(self):
        for index, name in enumerate(self.NAMES):
            awake = timeline.readiness([name])
            self.assertEqual([i for i, on in enumerate(awake) if on], [index])

    def test_unknown_events_are_ignored(self):
        self.assertEqual(timeline.readiness(["cron.service", "", "splash"]), [False] * len(self.NAMES))

    def test_progress_never_goes_backwards_whatever_the_event_order(self):
        vocabulary = self.NAMES + ["noise.service", "other.mount"]
        for _ in range(300):
            events = [RNG.choice(vocabulary) for _ in range(RNG.randint(0, 30))]
            previous = [False] * len(self.NAMES)
            for cut in range(len(events) + 1):
                awake = timeline.readiness(events[:cut])
                for was, now in zip(previous, awake):
                    self.assertTrue(now or not was)
                previous = awake
            self.assertEqual(timeline.readiness(events), timeline.readiness(events + events))

    def test_there_is_one_colour_and_one_slice_per_milestone(self):
        self.assertEqual(len(timeline.REGION_COLOURS), len(timeline.MILESTONES))
        self.assertEqual(timeline.REGION_SPAN * len(timeline.MILESTONES), 360)

    def test_every_dot_belongs_to_a_region(self):
        for _, lon in timeline.lattice_dots():
            self.assertIn(timeline.region_of(math.degrees(lon)), range(len(timeline.MILESTONES)))

    def test_wake_is_smooth_bounded_and_permanent(self):
        self.assertEqual(timeline.wake_level(5.0, None), 0.0)
        self.assertEqual(timeline.wake_level(2.0, 2.0), 0.0)
        self.assertEqual(timeline.wake_level(2.0 + timeline.WAKE_SECONDS, 2.0), 1.0)
        self.assertEqual(timeline.wake_level(900.0, 2.0), 1.0)

    def test_an_asleep_region_is_dim_but_visible(self):
        self.assertGreater(timeline.region_glow(0.0), 0.0)
        self.assertLess(timeline.region_glow(0.0), timeline.region_glow(1.0))
        self.assertEqual(timeline.region_glow(1.0), 1.0)

if __name__ == "__main__":
    unittest.main()
