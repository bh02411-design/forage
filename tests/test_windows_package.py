import hashlib, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import build_windows, updater

class WindowsPackageTests(unittest.TestCase):
    def test_rejects_wrong_runtime_before_copying_any_program_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);archive=root/'runtime.zip';archive.write_bytes(b'wrong archive')
            with self.assertRaisesRegex(ValueError,'checksum'):build_windows.stage(root,root/'stage',archive)
            self.assertFalse((root/'stage'/'server.py').exists())
    def test_staging_copies_only_allowlisted_program_files_and_preserves_runtime_license(self):
        import io, zipfile
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as archive:
            for name in ['python.exe','pythonw.exe','python313.zip','python313._pth','LICENSE.txt']:archive.writestr(name,b'fixture')
        payload=buffer.getvalue()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source';source.mkdir()
            for name in updater.PROGRAM_FILES:
                path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
            (source/'private-collection.csv').write_text('never package me')
            archive=root/'runtime.zip';archive.write_bytes(payload)
            with patch.object(build_windows,'PYTHON_SHA256',hashlib.sha256(payload).hexdigest()):out=build_windows.stage(source,root/'stage',archive)
            self.assertFalse((out/'private-collection.csv').exists());self.assertFalse((out/'data').exists())
            self.assertTrue((out/'runtime'/'LICENSE.txt').exists());self.assertIn('..\n',(out/'runtime'/'python313._pth').read_text())
            self.assertEqual((out/'Forage.ico').read_bytes()[:6],b'\x00\x00\x01\x00\x01\x00')
