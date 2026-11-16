"""Update missing menu messages using the existing Korean font; no game files required."""
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import re5_korean_patch as patch


def update():
    chars = json.loads((ROOT / 'data/menu_charmap.json').read_text())
    translations = json.loads((ROOT / 'data/menu_ko.json').read_text())
    target = ROOT / 'data/ko_patch.arc'
    start, entries = patch.read_arc(target.read_bytes(), str(target))
    font = next(zlib.decompress(e[3]) for e in entries if e[0].rstrip(b'\0') == b'etc\\message\\font00_j')
    assert hashlib.sha256(font).hexdigest() == '52ad246f39d0c13fd995b80a461e0a7d8710e69592aafe01404f58fd84ce295a', 'Unexpected font atlas'
    for entry in entries:
        if entry[0].rstrip(b'\0') != b'etc\\message\\mes_system_e':
            continue
        data = zlib.decompress(entry[3])
        pairs = list(struct.iter_unpack('<HH', data[64:]))
        messages = [[]]
        for pair in pairs:
            if pair == (0, 0x401):
                messages.append([])
            else:
                messages[-1].append(pair)
        original_count = len(messages)
        for index, text in translations.items():
            # Keep the stage-change controller icon before its translated label.
            prefix = [(0, 0x419), (6, 126)] if index == '2497' else []
            messages[int(index)] = prefix + [(0, 0x403) if c == '\n' else (chars[c] * 2, 126) for c in text] + [(0, 0x42c)]
        body = []
        for i, message in enumerate(messages):
            if i:
                body.append((0, 0x401))
            body.extend(message)
        out = bytearray(data[:64] + b''.join(struct.pack('<HH', *p) for p in body))
        struct.pack_into('<I', out, 8, len(out))
        assert len(messages) == original_count
        entry[2] = (entry[2] & ~patch.SIZE_MASK) | len(out)
        entry[3] = zlib.compress(out)
    target.write_bytes(patch.build_arc(entries, start))
    print(f'Updated {len(translations)} menu messages')


if __name__ == '__main__':
    update()
