import hashlib
import contextlib
import io
import sys
import tempfile
import tarfile
import unittest
from unittest.mock import patch
from pathlib import Path

from scripts.strata_kaggle import redact, safe_extract_runtime, _sha256, opencode_config_snippet, _cached_model_path, run_streaming, restore_model_cache


class StrataKaggleTests(unittest.TestCase):
    def test_redacts_strata_key(self):
        text = "API key sk-strata-very-secret123\n"
        self.assertIn("sk-strata-<redacted>", redact(text))
        self.assertNotIn("very-secret123", redact(text))

    def test_sha256(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "f"
            path.write_bytes(b"hello")
            self.assertEqual(_sha256(path), hashlib.sha256(b"hello").hexdigest())

    def test_runtime_extractor_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            archive = td_path / "bad.tar"
            with tarfile.open(archive, "w:") as tf:
                info = tarfile.TarInfo("../evil")
                info.size = 1
                import io
                tf.addfile(info, io.BytesIO(b"x"))
            with self.assertRaises(RuntimeError):
                safe_extract_runtime(archive, td_path / "out")
            self.assertFalse((td_path / "evil").exists())

    def test_runtime_extractor_rejects_cross_tree_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            archive = td_path / "cross-tree.tar"
            with tarfile.open(archive, "w:") as tf:
                info = tarfile.TarInfo("terminal/escape")
                info.type = tarfile.SYMTYPE
                info.linkname = "../../components/engine"
                tf.addfile(info)
            with self.assertRaises(RuntimeError):
                safe_extract_runtime(archive, td_path / "out")


    def test_cached_model_path_selects_expected_model(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            model_dir = root / "models" / "gyro-Gyro-S"
            model_dir.mkdir(parents=True)
            (model_dir / "model.gguf").write_bytes(b"model")
            found = _cached_model_path(root, "gyro", "gyro-s")
            self.assertEqual(found, model_dir)


    def test_run_streaming_prints_subprocess_output(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            result = run_streaming(
                [sys.executable, "-c", "print('progress-visible'); print('done')"],
                timeout=10,
            )
        self.assertIn("progress-visible", buffer.getvalue())
        self.assertIn("done", result.stdout)


    def test_run_streaming_reports_heartbeat(self):
        with tempfile.TemporaryDirectory() as td:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                result = run_streaming(
                    [sys.executable, "-c", "import time; time.sleep(0.7)"],
                    timeout=10,
                    heartbeat_interval=0.1,
                    heartbeat_label="test launch",
                    progress_paths=[Path(td)],
                )
            self.assertEqual(result.returncode, 0)
            self.assertIn("test launch still running", buffer.getvalue())
            self.assertIn("0.00 GiB", buffer.getvalue())


    def test_restore_model_cache_symlink_mode_avoids_copy(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_root = root / "input" / "datasets"
            dataset = input_root / "test-owner" / "strata-model-gyro-gyro-s"
            dataset.mkdir(parents=True)
            payload = b"model-bytes"
            flattened = dataset / "0001__model.gguf"
            flattened.write_bytes(payload)
            manifest = {
                "format": "devzonex.strata-model-cache.v1",
                "model": {"family": "gyro", "variant": "gyro-s"},
                "files": [{
                    "dataset_name": flattened.name,
                    "relative_path": "models/gyro-Gyro-S/model.gguf",
                    "size": len(payload),
                }],
            }
            (dataset / "manifest.json").write_text(__import__("json").dumps(manifest), encoding="utf-8")
            target_root = root / "local-model"
            with patch("scripts.strata_kaggle.INPUT_ROOT", input_root):
                restored = restore_model_cache(
                    "test-owner", "strata-model-gyro-gyro-s", target_root,
                    family="gyro", variant="gyro-s", restore_mode="symlink",
                )
            linked = target_root / "models" / "gyro-Gyro-S" / "model.gguf"
            self.assertTrue(restored)
            self.assertTrue(linked.is_symlink())
            self.assertEqual(linked.read_bytes(), payload)
            self.assertEqual(linked.resolve(), flattened.resolve())

    def test_open_code_snippet_has_provider_wrapper_and_no_key(self):
        value = opencode_config_snippet("https://sample.trycloudflare.com", "qwen3.8-flash-next-gyro-gyro-s")
        import json
        parsed = json.loads(value)
        self.assertIn("strata", parsed)
        self.assertEqual(parsed["strata"]["settings"]["apiKey"], "{file:~/.config/opencode/strata-key.txt}")
        self.assertNotIn("sk-strata-", value)


if __name__ == "__main__":
    unittest.main()
