"""Self-contained CLI checks; optional command arguments test another patcher."""
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import re5_korean_patch as patch

COMMAND = [sys.executable, str(ROOT / 're5_korean_patch.py')]


def entry(name, raw=b'original', kind=1):
    return [name.ljust(64, b'\0'), kind, len(raw), zlib.compress(raw)]


class PatcherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.game = Path(self.temp.name)
        self.folder = self.game / patch.ARCHIVE_DIR
        self.folder.mkdir(parents=True)
        payload = patch.read_arc(patch.PATCH.read_bytes(), 'payload')[1]
        self.originals = {}
        for name in patch.TARGETS:
            selected = [e for e in payload if (b'font00_j' in e[0]) == (name == 'CoreResource.arc')]
            entries = [entry(e[0], kind=e[1]) for e in selected]
            entries.append(entry(b'untouched', b'keep this data'))
            if name == 'CoreResource.arc':
                entries.append(entry(patch.CURRENT_BUILD_MARKER))
            data = patch.build_arc(entries, 0x8000)
            (self.folder / name).write_bytes(data)
            self.originals[name] = data

    def run_patch(self, *args):
        return subprocess.run([*COMMAND, str(self.game), *args], text=True, capture_output=True,
                              env=dict(os.environ, RE5_PATCH_NO_PAUSE='1'), stdin=subprocess.DEVNULL)

    def test_font_selection_and_restore(self):
        font_flag = '-Font' if '-File' in COMMAND else '--font'
        result = self.run_patch()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for font in ('malgun', 'nanum', 'kyeon', 'malgun'):
            result = self.run_patch(font_flag, font)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            donor = patch.read_arc(patch.PATCH.read_bytes(), 'payload')[1]
            if font != 'nanum':
                alternate = patch.read_arc((ROOT / 'data/fonts' / (font + '.arc')).read_bytes(), font)[1]
                donor = [e for e in donor if e[0] != alternate[0][0]] + alternate
            expected = {patch.key(e): e for e in donor}
            for name, original in self.originals.items():
                data = (self.folder / name).read_bytes()
                patch.verify(data, name, expected, original)
                self.assertEqual((self.folder / (name + '.orig')).read_bytes(), original)
            again = self.run_patch(font_flag, font)
            self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
            self.assertEqual(again.stdout.count('already patched'), 3)
        # No font argument must select Malgun, including when switching from another font.
        self.assertEqual(self.run_patch(font_flag, 'kyeon').returncode, 0)
        self.assertEqual(self.run_patch().returncode, 0)
        actual = patch.read_arc((self.folder / 'CoreResource.arc').read_bytes(), 'core')[1]
        malgun = patch.read_arc((ROOT / 'data/fonts/malgun.arc').read_bytes(), 'malgun')[1][0]
        self.assertIn(malgun, actual)
        before = {n: (self.folder / n).read_bytes() for n in patch.TARGETS}
        self.assertNotEqual(self.run_patch(font_flag, 'invalid').returncode, 0)
        self.assertEqual(before, {n: (self.folder / n).read_bytes() for n in patch.TARGETS})
        result = self.run_patch('-Restore' if '-File' in COMMAND else '--restore')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name, original in self.originals.items():
            self.assertEqual((self.folder / name).read_bytes(), original)
            self.assertFalse((self.folder / (name + '.orig')).exists())

    def test_bad_archive_writes_nothing(self):
        (self.folder / 'MsgResource_e.arc').write_bytes(b'not an archive')
        self.assertNotEqual(self.run_patch().returncode, 0)
        self.assertEqual((self.folder / 'CoreResource.arc').read_bytes(), self.originals['CoreResource.arc'])
        self.assertFalse(list(self.folder.glob('*.orig')))

    def test_old_core_is_rejected(self):
        name = 'CoreResource.arc'
        start, entries = patch.read_arc(self.originals[name], name)
        entries = [e for e in entries if e[0].rstrip(b'\0') != patch.CURRENT_BUILD_MARKER]
        old = patch.build_arc(entries, start)
        (self.folder / name).write_bytes(old)
        result = self.run_patch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Verify', result.stderr)
        self.assertEqual((self.folder / name).read_bytes(), old)
        self.assertFalse(list(self.folder.glob('*.orig')))

    def test_menu_build_is_repeatable(self):
        before = patch.read_arc(patch.PATCH.read_bytes(), 'payload')[1]
        result = subprocess.run([sys.executable, str(ROOT / 'tools/update_menu.py')], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        after = patch.read_arc(patch.PATCH.read_bytes(), 'payload')[1]
        self.assertEqual([patch.key(e) for e in before], [patch.key(e) for e in after])
        for old, new in zip(before, after):
            self.assertEqual(zlib.decompress(old[3]), zlib.decompress(new[3]))
        digest = hashlib.sha256(patch.PATCH.read_bytes()).digest()
        result = subprocess.run([sys.executable, str(ROOT / 'tools/update_menu.py')], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(hashlib.sha256(patch.PATCH.read_bytes()).digest(), digest)
        for e in patch.read_arc(patch.PATCH.read_bytes(), 'payload')[1]:
            raw = zlib.decompress(e[3])
            self.assertEqual(len(raw), e[2] & patch.SIZE_MASK)
            if b'mes_system_e' in e[0]:
                self.assertEqual(struct.unpack_from('<I', raw, 8)[0], len(raw))


if __name__ == '__main__':
    if len(sys.argv) > 1:
        COMMAND = sys.argv[1:]
    unittest.main(argv=[sys.argv[0]])
