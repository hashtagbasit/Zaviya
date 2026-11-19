import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


class FlatpakVideoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        path = ROOT / "steamos-overlay/usr/lib/steamos-arm/hub/hub.py"
        spec = importlib.util.spec_from_file_location("hub_video_test", path)
        self.hub = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.hub)
        self.hub.HOME = self.work / "home"
        self.hub.VA_SYSTEM = self.work / "va"
        self.hub.catalog = lambda: []
        self.ref = "io.github.streetpea.Chiaki4deck"

    def test_steam_shortcut_gets_persistent_driver_and_updates(self):
        self.hub.VA_SYSTEM.mkdir()
        source = self.hub.VA_SYSTEM / "msm_drv_video.so"
        dest = self.hub.HOME / ".var/app" / self.ref / self.hub.VA_DIR / source.name
        with mock.patch.object(self.hub.subprocess, "run") as run:
            run.return_value.stdout = self.ref + "\n"
            for content in (b"original driver", b"updated driver"):
                source.write_bytes(content)
                self.assertEqual(self.hub.video_accel_sync(), 0)
                self.assertEqual(dest.read_bytes(), content)
                run.assert_called_with(
                    ["flatpak", "override", "--user", self.ref,
                     f"--env=LIBVA_DRIVERS_PATH={dest.parent}",
                     "--env=LIBVA_DRIVER_NAME=msm"], timeout=60)
                self.assertFalse(dest.with_name(dest.name + ".new").exists())

    def test_missing_driver_leaves_overrides_unchanged(self):
        with mock.patch.object(self.hub.subprocess, "run") as run:
            run.return_value.stdout = self.ref + "\n"
            self.assertEqual(self.hub.video_accel_sync(), 0)
            self.assertEqual(run.call_count, 1)
            self.assertFalse(self.hub.HOME.exists())
