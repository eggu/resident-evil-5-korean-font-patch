#!/usr/bin/env python3
"""Resident Evil 5 Korean patch for the current Steam build.

Replaces only the Korean font and the English-slot message entries inside the game's own
archives. Every other resource (sound, stage, menu data, other fonts) stays as shipped, so the
patch never brings back data from the older game version the original Korean patch was made for.

Usage:
    python3 re5_korean_patch.py [GAME_FOLDER]            apply (choose a font)
    python3 re5_korean_patch.py --font malgun [GAME_FOLDER]  Malgun Gothic
    python3 re5_korean_patch.py --restore [GAME_FOLDER]  put the backed-up originals back
GAME_FOLDER is the folder with re5dx9.exe. Without it, the script looks next to itself and in the
current folder, then asks.
"""
import argparse
import os
import struct
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATCH = HERE / 'data' / 'ko_patch.arc'
FONTS = {'malgun': '맑은고딕체', 'nanum': '나눔명조체', 'kyeon': '견명조체'}
TARGETS = ['CoreResource.arc', 'MsgResource_e.arc', 'Msg2Resource_e.arc']
ARCHIVE_DIR = Path('nativePC_MT', 'Image', 'Archive')
BACKUP_SUFFIX = '.orig'
# Present in the current Steam build only; the old full CoreResource.arc replacement drops it.
CURRENT_BUILD_MARKER = b'etc\\message\\font00_ch'
ENTRY = struct.Struct('<64sIIII')
SIZE_MASK = 0x1FFFFFFF


class PatchError(Exception):
    pass


def read_arc(data: bytes, label: str) -> tuple[int, list[list]]:
    """Returns (data_start, [[name, type, raw_size_field, blob], ...])."""
    if len(data) < 8:
        raise PatchError(f'{label}: file too small')
    magic, version, count = struct.unpack_from('<4sHH', data)
    if magic != b'ARC\0' or version != 7:
        raise PatchError(f'{label}: not an RE5 archive (magic {magic!r}, version {version})')
    if 8 + count * ENTRY.size > len(data):
        raise PatchError(f'{label}: entry table is truncated')
    entries = []
    for i in range(count):
        name, typ, csize, dsize, offset = ENTRY.unpack_from(data, 8 + i * ENTRY.size)
        if offset + csize > len(data):
            raise PatchError(f'{label}: entry {i} points past the end of the file')
        entries.append([name, typ, dsize, data[offset:offset + csize]])
    start = min((ENTRY.unpack_from(data, 8 + i * ENTRY.size)[4] for i in range(count)), default=8)
    return start, entries


def build_arc(entries: list[list], data_start: int) -> bytes:
    head = struct.pack('<4sHH', b'ARC\0', 7, len(entries))
    table, offset = [], max(data_start, 8 + len(entries) * ENTRY.size)
    for name, typ, dsize, blob in entries:
        table.append(ENTRY.pack(name, typ, len(blob), dsize, offset))
        offset += len(blob)
    head += b''.join(table)
    return head + b'\0' * (max(data_start, len(head)) - len(head)) + b''.join(e[3] for e in entries)


def key(entry: list) -> tuple[bytes, int]:
    return entry[0], entry[1]


def patched_copy(data: bytes, label: str, patch: dict) -> tuple[bytes, int, int]:
    """Returns (new_bytes, swapped_count, already_count) for one game archive."""
    start, entries = read_arc(data, label)
    swapped = already = 0
    for entry in entries:
        donor = patch.get(key(entry))
        if donor is None:
            continue
        if entry[2:] == donor[2:]:
            already += 1
        else:
            entry[2], entry[3] = donor[2], donor[3]
            swapped += 1
    return build_arc(entries, start), swapped, already


def verify(new: bytes, label: str, patch: dict, original: bytes) -> None:
    """Re-reads the written bytes: patched entries match the patch, every other entry is unchanged."""
    _, after = read_arc(new, label)
    _, before = read_arc(original, label)
    if [key(e) for e in after] != [key(e) for e in before]:
        raise PatchError(f'{label}: entry list changed while writing')
    for a, b in zip(after, before):
        expected = patch.get(key(a), b)
        if a[2:] != expected[2:]:
            raise PatchError(f'{label}: entry {a[0].rstrip(bytes(1)).decode("latin1")} was not written correctly')
        if key(a) in patch and len(zlib.decompress(a[3])) != a[2] & SIZE_MASK:
            raise PatchError(f'{label}: patched entry failed to decompress')


def find_archive_dir(arg: str | None) -> Path:
    candidates = [Path(arg)] if arg else [HERE, Path.cwd(), HERE.parent]
    for base in candidates:
        for folder in (base / ARCHIVE_DIR, base):
            if all((folder / t).is_file() for t in TARGETS):
                return folder
    if arg:
        raise PatchError(f'Cannot find {ARCHIVE_DIR} with {", ".join(TARGETS)} under: {arg}')
    entered = input('Drag the Resident Evil 5 folder (with re5dx9.exe) here and press Enter: ').strip().strip('"\'')
    if not entered:
        raise PatchError('No game folder given.')
    return find_archive_dir(entered)


def replace_file(path: Path, data: bytes) -> None:
    temp = path.with_name(path.name + '.tmp')
    temp.write_bytes(data)
    os.replace(temp, path)


def apply(folder: Path, font: str = 'malgun') -> None:
    _, patch_entries = read_arc(PATCH.read_bytes(), PATCH.name)
    if font not in FONTS:
        raise PatchError(f'Unknown font: {font}')
    if font != 'nanum':
        _, font_entries = read_arc((HERE / 'data/fonts' / (font + '.arc')).read_bytes(), font)
        if len(font_entries) != 1 or font_entries[0][0].rstrip(b'\0') != b'etc\\message\\font00_j':
            raise PatchError(f'{font}: invalid font archive')
        patch_entries = [e for e in patch_entries if key(e) != key(font_entries[0])] + font_entries
    patch = {key(e): e for e in patch_entries}
    _, core = read_arc((folder / 'CoreResource.arc').read_bytes(), 'CoreResource.arc')
    if not any(e[0].rstrip(b'\0') == CURRENT_BUILD_MARKER for e in core):
        raise PatchError('CoreResource.arc is the old full replacement from the previous Korean patch.\n'
                         'Restore the game files first (Steam: Properties > Installed Files > Verify integrity), then run this again.')
    planned = []
    for name in TARGETS:
        path = folder / name
        original = path.read_bytes()
        new, swapped, already = patched_copy(original, name, patch)
        if swapped + already == 0:
            raise PatchError(f'{name}: none of the Korean entries exist in this archive')
        verify(new, name, patch, original)
        planned.append((path, original, new, swapped, already))
    for path, original, new, swapped, already in planned:
        if swapped == 0:
            print(f'{path.name}: already patched')
            continue
        backup = path.with_name(path.name + BACKUP_SUFFIX)
        if not backup.exists():
            backup.write_bytes(original)
        replace_file(path, new)
        print(f'{path.name}: replaced {swapped} entr{"y" if swapped == 1 else "ies"} (backup: {backup.name})')


def restore(folder: Path) -> None:
    restored = 0
    for name in TARGETS:
        backup = folder / (name + BACKUP_SUFFIX)
        if backup.exists():
            replace_file(folder / name, backup.read_bytes())
            backup.unlink()
            restored += 1
            print(f'{name}: restored')
    if not restored:
        raise PatchError('No backups found. Use Steam "Verify integrity of game files" instead.')


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('game_folder', nargs='?')
    parser.add_argument('--restore', action='store_true')
    parser.add_argument('--font', choices=FONTS)
    args = parser.parse_args(argv)
    folder = find_archive_dir(args.game_folder)
    print(f'Game archives: {folder}')
    if args.restore:
        restore(folder)
    else:
        font = args.font or 'malgun'
        if args.font is None and sys.stdin.isatty() and os.environ.get('RE5_PATCH_NO_PAUSE') != '1':
            print('1. 맑은고딕체 (기본값)  2. 나눔명조체  3. 견명조체')
            choice = input('Font [1/2/3, Enter=1]: ').strip() or '1'
            if choice not in ('1', '2', '3'):
                raise PatchError('Choose 1, 2 or 3.')
            font = list(FONTS)[int(choice) - 1]
        print(f'Font: {FONTS[font]} ({font})')
        apply(folder, font)
    print('Done.')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    try:
        main(sys.argv[1:])
        code = 0
    except (PatchError, OSError) as error:
        print(f'Error: {error}', file=sys.stderr)
        code = 1
    if sys.stdin.isatty() and os.environ.get('RE5_PATCH_NO_PAUSE') != '1' and len(sys.argv) == 1:
        input('Press Enter to close.')
    sys.exit(code)
