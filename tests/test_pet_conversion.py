import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from pc.pet import (CLIPS, STATE_CLIPS, activate, clip_frames, convert,
                    inspect_pack, rgb565, valid_id)


class ConversionTests(unittest.TestCase):
    def test_rgb565_high_byte_first(self):
        image = Image.new("RGB", (4, 1))
        image.putdata([(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)])
        self.assertEqual(rgb565(image), b"\xf8\x00\x07\xe0\x00\x1f\xff\xff")

    def test_generated_pack_dimensions_sizes_and_checksums(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sheet = root / "sheet.png"
            Image.new("RGBA", (1536, 2288), (255, 0, 0, 255)).save(sheet)
            output = root / "pack"
            manifest = convert(sheet, output, "test-pet", {"author": "test"})
            self.assertEqual((manifest["width"], manifest["height"]), (96, 104))
            self.assertEqual(manifest["states"], STATE_CLIPS)
            self.assertEqual(sum(value["frames"] for value in manifest["animations"].values()), 73)
            self.assertEqual(manifest["animations"]["look"]["frames"], 16)
            self.assertEqual(manifest["animations"]["retry"]["frames"], 16)
            for name, clip in CLIPS.items():
                animation = manifest["animations"][name]
                data = (output / animation["file"]).read_bytes()
                self.assertEqual(len(data), clip_frames(clip) * 96 * 104 * 2)
                self.assertEqual(data[:2], b"\xf8\x00")
                self.assertEqual(hashlib.sha256(data).hexdigest(), animation["sha256"])
            self.assertEqual(json.loads((output / "manifest.json").read_text())["id"], "test-pet")
            with self.assertRaises(ValueError):
                convert(sheet, output, "test-pet", {})

    def test_local_pack_inspection_checks_all_animation_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sheet = root / "sheet.png"
            Image.new("RGBA", (1536, 2288), (0, 0, 255, 255)).save(sheet)
            pack = root / "test-pet"
            manifest = convert(sheet, pack, "test-pet", {})
            pet_id, verified, files = inspect_pack(pack)
            self.assertEqual(pet_id, "test-pet")
            self.assertEqual(len(files), len(manifest["animations"]))
            self.assertEqual(verified["id"], pet_id)
            (pack / "idle.rgb565").write_bytes(b"corrupt")
            with self.assertRaises(ValueError):
                inspect_pack(pack)

    def test_activation_checks_existing_sd_pack_without_copying_assets(self):
        with patch("pc.pet.subprocess.run") as run:
            activate(SimpleNamespace(pet="creepy", port="COM_TEST"))
        command = run.call_args_list[0].args[0]
        self.assertIn("COM_TEST", command)
        self.assertTrue(any(str(item).endswith("prepare_pet_activate.py") for item in command))
        self.assertTrue(any(str(item).endswith("verify_pet_sd.py") for item in command))
        self.assertFalse(any("fs" == item for item in command))
        self.assertEqual(len(run.call_args_list), 2)  # Reset after activation.

    def test_retry_plays_running_left_then_running_right(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sheet = Image.new("RGBA", (1536, 2288), (0, 0, 0, 0))
            sheet.paste((255, 0, 0, 255), (0, 2 * 208, 1536, 3 * 208))  # row 2: running-left
            sheet.paste((0, 0, 255, 255), (0, 1 * 208, 1536, 2 * 208))  # row 1: running-right
            image = root / "sheet.png"
            sheet.save(image)
            output = root / "pack"
            convert(image, output, "test-pet", {})
            data = (output / "retry.rgb565").read_bytes()
            frame = 96 * 104 * 2
            self.assertEqual(data[:2], b"\xf8\x00")
            self.assertEqual(data[8 * frame:8 * frame + 2], b"\x00\x1f")

    def test_v1_atlas_has_no_look_clip_and_thinking_falls_back_to_idle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sheet = root / "sheet.png"
            Image.new("RGBA", (1536, 1872), (255, 0, 0, 255)).save(sheet)
            manifest = convert(sheet, root / "pack", "test-pet", {})
            self.assertNotIn("look", manifest["animations"])
            self.assertEqual(manifest["states"]["thinking"], "idle")
            for clip in manifest["states"].values():
                self.assertIn(clip, manifest["animations"])

    def test_invalid_ids_cannot_escape_pack_directory(self):
        for value in ("../escape", "a/b", "", "UPPER", "a\\b"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                valid_id(value)
