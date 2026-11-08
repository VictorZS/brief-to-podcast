import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import wave

from helpers import config, fake_synthesis, renderer, write_episode
import export_mp3 as exporter


def ready_render(directory):
    path = write_episode(directory)
    with patch.object(renderer, "synthesize", side_effect=fake_synthesis):
        manifest, code = renderer.render(path, config())
    assert code == 0
    return manifest


def fake_conversion(command, duration=5):
    """Simulate encoder/decoder outputs; waveform is a test signal, not speech."""
    target = Path(command[-1])
    if target.suffix == ".mp3":
        target.write_bytes(b"synthetic-encoded-data" * 100)
    else:
        with wave.open(str(target), "wb") as output:
            output.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
            output.writeframes(struct.pack("<h", 1000) * (22050 * duration))


class Mp3Tests(unittest.TestCase):
    def test_changed_source_is_rejected_before_conversion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = ready_render(root)
            (root / manifest["audio_file"]).write_bytes(b"modified")
            with patch.object(exporter, "encoder") as encoder:
                with self.assertRaisesRegex(ValueError, "Source audio checksum mismatch"):
                    exporter.export_mp3(root)
                encoder.assert_not_called()
            self.assertEqual(json.loads((root / "mobile_audio.json").read_text())["status"], "failed")

    def test_changed_episode_cannot_relabel_previous_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ready_render(root)
            path = root / "episode.json"
            data = json.loads(path.read_text())
            data["title"] = "A newer fictional report"
            path.write_text(json.dumps(data))
            with patch.object(exporter, "encoder") as encoder:
                with self.assertRaisesRegex(ValueError, "Episode snapshot checksum mismatch"):
                    exporter.export_mp3(root)
                encoder.assert_not_called()

    def test_audio_path_cannot_escape_render_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = ready_render(root)
            manifest["audio_file"] = "../outside.m4a"
            (root / "manifest.json").write_text(json.dumps(manifest))
            with patch.object(exporter, "encoder") as encoder:
                with self.assertRaises(ValueError):
                    exporter.export_mp3(root)
                encoder.assert_not_called()

    def test_audio_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = ready_render(root)
            audio = root / manifest["audio_file"]
            destination = root / "different-file.m4a"
            audio.rename(destination)
            audio.symlink_to(destination)
            with patch.object(exporter, "encoder") as encoder:
                with self.assertRaisesRegex(ValueError, "symlink"):
                    exporter.export_mp3(root)
                encoder.assert_not_called()

    def test_success_receipt_is_cached_only_while_mp3_hash_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = ready_render(root)
            with patch.object(exporter, "encoder", return_value="fake-ffmpeg"), \
                    patch.object(exporter, "run", side_effect=fake_conversion) as convert:
                first = exporter.export_mp3(root)
                second = exporter.export_mp3(root)
                self.assertEqual(first, second)
                self.assertEqual(convert.call_count, 2)
                self.assertEqual(first["status"], "ready")
                self.assertEqual(first["render_fingerprint"], manifest["fingerprint"])
                self.assertEqual(first["sha256"], renderer.file_hash(root / first["file"]))
                (root / first["file"]).write_bytes(b"corrupted")
                rebuilt = exporter.export_mp3(root)
                self.assertEqual(convert.call_count, 4)
                self.assertEqual(rebuilt["status"], "ready")

    def test_decode_duration_mismatch_never_produces_ready_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ready_render(root)
            with patch.object(exporter, "encoder", return_value="fake-ffmpeg"), \
                    patch.object(exporter, "run", side_effect=lambda cmd: fake_conversion(cmd, duration=1)):
                with self.assertRaisesRegex(ValueError, "MP3 duration mismatch"):
                    exporter.export_mp3(root)
            self.assertEqual(json.loads((root / "mobile_audio.json").read_text())["status"], "failed")
            self.assertEqual(list(root.glob("*.mp3")), [])

    def test_text_only_render_cannot_export_stale_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ready_render(root)
            with patch.object(exporter, "encoder", return_value="fake-ffmpeg"), \
                    patch.object(exporter, "run", side_effect=fake_conversion):
                exporter.export_mp3(root)
            renderer.render(root / "episode.json", config(), text_only=True)
            self.assertEqual(json.loads((root / "mobile_audio.json").read_text())["status"], "stale")
            with patch.object(exporter, "encoder") as encoder:
                with self.assertRaisesRegex(ValueError, "Source audio is not ready"):
                    exporter.export_mp3(root)
                encoder.assert_not_called()


if __name__ == "__main__":
    unittest.main()
