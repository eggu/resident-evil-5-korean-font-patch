# Resident Evil 5 Korean Patch (current Steam version)

Applies Korean fonts and messages to the current Steam game files. Choose Malgun Gothic, Nanum Myeongjo or Kyeon Myeongjo; Malgun Gothic is the default.

## Supported

- Resident Evil 5 / Biohazard 5 Gold Edition, current Steam version
- Windows (PowerShell 5.1+), macOS and Linux/Steam Deck (Python 3.10+)

## Install

Download the ZIP under **Assets** on the [latest release](https://github.com/eggu/resident-evil-5-korean-font-patch/releases/latest) and extract it.

1. **If you installed the older Korean patch, restore the original files first.**
   In the Steam library, right-click the game → Properties → Installed Files → **Verify integrity of game files**.
2. Copy this patch folder into the game folder (the folder with `re5dx9.exe`).
   Steam: right-click the game → Manage → Browse local files.
3. Close the game completely, then run the file for your system:
   - **Windows**: double-click `Apply-Windows.bat`
   - **macOS**: double-click `Apply-macOS.command`
   - **Linux / Steam Deck**: run `sh apply.sh` in a terminal
4. Choose a font: `1` Malgun Gothic, `2` Nanum Myeongjo, or `3` Kyeon Myeongjo. Press Enter for Malgun Gothic.
5. When it prints `Done.`, start the game; the text is in Korean.

If the patch folder is outside the game folder, drag the game folder into the window when asked and press Enter.

## Change font

![Font preview](data/fonts/preview.png)

Close the game completely, run the installer again and choose another font. The translation stays the same.

From a terminal: `sh apply.sh --font malgun "GAME_FOLDER"`. Supported values are `malgun`, `nanum` and `kyeon`. With Windows PowerShell, use `-Font malgun -GameFolder "GAME_FOLDER"`.

## Restore

- **Windows**: double-click `Restore-Windows.bat`
- **macOS / Linux**: run `sh apply.sh --restore` in a terminal
- Without backups, use **Verify integrity of game files** in Steam.

The originals are kept next to the game files as `.orig` files.

## Notes

- A Steam update or file verification undoes the patch. Run step 3 again afterwards.
- On macOS, if a window asks to install developer tools on first run, install them (Python 3.10 or later is required).
- The existing Korean translation includes missing Action Assist, Camera, split-screen and privacy policy messages from the current version. Other added or changed lines may still appear in English or not match.

## Credits

See [CREDITS.md](CREDITS.md) for the original Korean patch credits and data source.

## Development

Python 3.10 or later is required; no additional packages are needed.

```sh
python3 tools/update_menu.py
python3 -m unittest discover -s tests
python3 tools/build.py --version 1.0.0
```

The ZIP and SHA256 file are written to `dist/`. Edit `data/menu_ko.json` to change menu translations; `data/menu_charmap.json` maps characters to the bundled font cells. The existing translated messages and fonts are included as build inputs.

The patcher code is MIT licensed. Existing translation and font assets have separate ownership; see [LICENSE](LICENSE) and [CREDITS.md](CREDITS.md).
