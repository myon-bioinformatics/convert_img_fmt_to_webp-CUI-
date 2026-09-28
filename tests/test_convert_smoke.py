"""Smoke-test the unchanged CUI entry point against real Pillow WebP I/O."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "convert_img_fmt_to_webp(CUI).py"


class ConvertSmokeTest(unittest.TestCase):
    def test_png_jpg_gif_become_valid_webp(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            img_dir = work / "img_folder"
            img_dir.mkdir()

            Image.new("RGBA", (8, 8), (255, 0, 0, 128)).save(img_dir / "a.png")
            Image.new("RGB", (8, 8), (0, 255, 0)).save(img_dir / "b.jpg")
            Image.new("P", (8, 8)).save(img_dir / "c.gif")
            (work / "input_data.json").write_text(
                json.dumps({"img_file_path": "./img_folder"}), encoding="utf-8"
            )
            shutil.copy(SCRIPT, work / "cui.py")

            proc = subprocess.run(
                [sys.executable, "cui.py"],
                cwd=work,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("All Completed!", proc.stdout)

            for stem in ("a", "b", "c"):
                data = (img_dir / f"{stem}.webp").read_bytes()
                self.assertEqual(data[:4], b"RIFF")
                self.assertEqual(data[8:12], b"WEBP")


if __name__ == "__main__":
    unittest.main()
