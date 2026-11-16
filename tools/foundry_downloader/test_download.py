import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
import zipfile

from download import download, extract


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class DownloadTests(unittest.TestCase):
    def test_http_download_layouts_and_skip(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            server = ThreadingHTTPServer(("127.0.0.1", 0),
                functools.partial(QuietHandler, directory=str(root)))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for index, prefix in enumerate(("", "module/", "release/nested/")):
                    identity = f"maps-{index}"
                    data = {"id": identity, "download": f"{identity}.zip"}
                    (root / f"{identity}.json").write_text(json.dumps(data), encoding="utf-8")
                    with zipfile.ZipFile(root / f"{identity}.zip", "w") as package:
                        package.writestr(prefix + "module.json", json.dumps(data))
                        package.writestr(prefix + "maps/map.webp", b"map data")
                    url = f"http://127.0.0.1:{server.server_port}/{identity}.json"
                    output = root / "output"
                    self.assertTrue(download(url, output, 5).startswith("OK"))
                    self.assertEqual((output / identity / "maps/map.webp").read_bytes(), b"map data")
                    self.assertTrue(download(url, output, 5).startswith("SKIP"))
                    self.assertFalse(list(output.glob(".foundry-*")))
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_unsafe_paths_and_wrong_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for entry in ("../escape", "/escape", "C:/escape"):
                with zipfile.ZipFile(root / "bad.zip", "w") as package:
                    info = zipfile.ZipInfo("placeholder")
                    info.filename = entry  # Preserve backslashes on Windows for this malformed ZIP.
                    package.writestr(info, "bad")
                with self.assertRaises(ValueError):
                    extract(root / "bad.zip", root / "unpacked", "maps")
                self.assertFalse((root / "unpacked").exists())
            with zipfile.ZipFile(root / "bad.zip", "w") as package:
                package.writestr("module.json", '{"id":"other"}')
            with self.assertRaises(ValueError):
                extract(root / "bad.zip", root / "unpacked", "maps")


if __name__ == "__main__":
    unittest.main()
