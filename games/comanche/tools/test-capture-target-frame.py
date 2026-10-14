#!/usr/bin/env python3
"""Exercise capture identity rejection without substituting game parity evidence."""
import importlib.util
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "capture_target", Path(__file__).with_name("capture-target-frame.py"))
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class CaptureIdentityTests(unittest.TestCase):
    def run_capture(self, overrides=None, timeout=False):
        with tempfile.TemporaryDirectory(prefix="capture identity $ ") as directory:
            out = Path(directory)
            (out / "comanche_d.tos").write_bytes(b"test program")
            tos = out / "test tos.rom"
            tos.write_bytes(b"test ROM")
            metadata = out / "target-frame.json"
            metadata.write_text('{"status":"CAPTURED"}')

            def emulate(command, **kwargs):
                self.assertIsInstance(command, list)
                self.assertEqual(kwargs["cwd"], out)
                self.assertNotIn("shell", kwargs)
                arm = (out / "arm.ini").read_text()
                self.assertIn("(demo_cursor).l = 173", arm)
                self.assertIn("(attract_demo_pass).w = 1", arm)
                self.assertIn("(view_variant).b = 1", arm)
                self.assertIn("(demo_active).w = 1", arm)
                self.assertFalse(metadata.exists())
                if timeout:
                    raise subprocess.TimeoutExpired(command, 1)
                (out / "frame.bin").write_bytes(bytes(capture.FRAME_BYTES))
                values = {"demo_cursor": 173, "demo_active": 1,
                          "attract_demo_pass": 1, "view_variant": 1,
                          "work_screen": 0x40000, "display_screen": 0x80000}
                values.update(overrides or {})
                for filename, symbol, size in capture.SCALARS:
                    if values[symbol] is not None:
                        (out / filename).write_bytes(values[symbol].to_bytes(size, "big"))
                return subprocess.CompletedProcess(command, 0)

            with patch.object(sys, "argv", ["capture-target-frame.py", "--record", "20",
                                           "--out", str(out), "--no-build"]), \
                    patch.dict("os.environ", {"TOS": str(tos)}), \
                    patch.object(capture.shutil, "which", return_value=sys.executable), \
                    patch.object(capture.subprocess, "run", side_effect=emulate), \
                    contextlib.redirect_stdout(io.StringIO()):
                if timeout:
                    with self.assertRaises(SystemExit):
                        capture.main()
                    self.assertFalse(metadata.exists())
                    return
                result = capture.main()
                return result, json.loads(metadata.read_text())

    def test_matching_capture(self):
        result, meta = self.run_capture()
        self.assertEqual(result, 0)
        self.assertEqual(meta["status"], "CAPTURED")
        self.assertEqual(len(meta["sha256"]["frame"]), 64)

    def test_reject_wrong_or_missing_identity(self):
        for symbol, value in [("demo_cursor", 181), ("demo_active", 0),
                              ("attract_demo_pass", 2), ("view_variant", 7),
                              ("display_screen", 0), ("view_variant", None)]:
            with self.subTest(symbol=symbol, value=value):
                result, meta = self.run_capture({symbol: value})
                self.assertEqual(result, 1)
                self.assertEqual(meta["status"], "Unproven")
                self.assertTrue(meta["problems"])

    def test_timeout_invalidates_old_metadata(self):
        self.run_capture(timeout=True)


if __name__ == "__main__":
    unittest.main()
