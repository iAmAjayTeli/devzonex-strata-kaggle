import hashlib
import tempfile
import tarfile
import unittest
from pathlib import Path

from scripts.strata_kaggle import redact, safe_extract_runtime, _sha256, opencode_config_snippet


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

    def test_open_code_snippet_has_provider_wrapper_and_no_key(self):
        value = opencode_config_snippet("https://sample.trycloudflare.com", "qwen3.8-flash-next-gyro-gyro-s")
        import json
        parsed = json.loads(value)
        self.assertIn("strata", parsed)
        self.assertEqual(parsed["strata"]["settings"]["apiKey"], "{file:~/.config/opencode/strata-key.txt}")
        self.assertNotIn("sk-strata-", value)


if __name__ == "__main__":
    unittest.main()
