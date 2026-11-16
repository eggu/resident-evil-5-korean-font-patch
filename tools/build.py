"""Create the release ZIP and SHA256 file using only Python's standard library."""
import argparse
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    'Apply-Windows.bat', 'Apply-macOS.command', 'Restore-Windows.bat', 'apply.sh',
    're5_korean_patch.py', 're5_korean_patch.ps1', 'README.md', 'README.ko.md',
    'CREDITS.md', 'LICENSE', 'data/ko_patch.arc', 'data/fonts/malgun.arc',
    'data/fonts/kyeon.arc', 'data/fonts/preview.png',
]


def build(version):
    if not version or any(c not in '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-' for c in version):
        raise ValueError('Version must contain only letters, numbers, dots and hyphens')
    folder = f'Resident-Evil-5-Korean-Patch-v{version}'
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    target = output / (folder + '.zip')
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in FILES:
            info = zipfile.ZipInfo(folder + '/' + name, (2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith(('.command', '.sh')) else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (ROOT / name).read_bytes())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(FILES)
        for name in FILES:
            assert archive.read(folder + '/' + name) == (ROOT / name).read_bytes()
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.zip.sha256').write_text(f'{digest}  {target.name}\n')
    print(target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='1.0.0')
    build(parser.parse_args().version)
