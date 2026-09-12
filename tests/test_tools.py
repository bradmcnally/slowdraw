import argparse
import importlib.util
from pathlib import Path
import os
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


capture = load("capture", ROOT / "tools" / "capture.py")
studies = load("contact_sheet", ROOT / "tools" / "contact_sheet.py")


class CaptureValidationTests(unittest.TestCase):
    def test_accepts_valid_variant_boundaries(self):
        self.assertEqual(capture.parse_variant("0"), 0)
        self.assertEqual(capture.parse_variant("4294967295"), 0xFFFFFFFF)

    def test_rejects_invalid_variants(self):
        for value in ("-1", "4294967296", "abc"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                capture.parse_variant(value)

    def test_accepts_complete_versioned_seed(self):
        self.assertEqual(capture.parse_seed_identity("11e92b7de2"), (17, 0xE92B7DE2))

    def test_rejects_incomplete_or_wrong_version_seed(self):
        for value in ("E92B7DE2", "117DE2", "10E92B7DE2", "11100000000"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                capture.parse_seed_identity(value)

    def test_default_capture_path_contains_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = os.getcwd()
            try:
                os.chdir(directory)
                self.assertEqual(capture.next_capture_path("11E92B7DE2"),
                                 "slow-draw-001-11E92B7DE2.png")
                Path("slow-draw-001-11E92B7DE2.png").touch()
                self.assertEqual(capture.next_capture_path("11E92B7DE2"),
                                 "slow-draw-002-11E92B7DE2.png")
            finally:
                os.chdir(previous)


class FirmwareRandomTests(unittest.TestCase):
    def test_xorshift_sequence_matches_firmware(self):
        rng = studies.FirmwareRandom(0x12345678)
        self.assertEqual([rng.next() for _ in range(4)],
                         [0x87985AA5, 0x155B24A3, 0x4820F4C4, 0x81B3AC98])

    def test_zero_seed_uses_firmware_fallback(self):
        self.assertEqual(studies.FirmwareRandom(0).state, 0x6D2B79F5)

    def test_active_studies_have_device_canvas_dimensions(self):
        for generator in (studies.cellular_aggregate, studies.pixel_field,
                          studies.subdivision, studies.dither_pressure,
                          studies.topography, studies.amoeba):
            image = generator(0xC1234567)
            self.assertEqual((len(image), len(image[0])), (124, 240))


if __name__ == "__main__":
    unittest.main()
