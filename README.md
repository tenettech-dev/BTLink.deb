# BTLink.deb — KONNWEI BTLink for Linux via Wine

[![CI](https://github.com/tenettech-dev/BTLink.deb/actions/workflows/ci.yml/badge.svg)](https://github.com/tenettech-dev/BTLink.deb/actions/workflows/ci.yml)

Unofficial **open-source Linux compatibility adapter** and Debian package for the manufacturer's **KONNWEI BTLink** battery tester software. No VM required. Uses the Linux `cdc_acm` serial driver, Wine's COM3 mapping, and a small Windows SetupAPI proxy.

**This is not KONNWEI BTLink itself.** Install BTLink separately from the manufacturer. Neither the repository nor the `.deb` includes the manufacturer application, drivers, firmware, or update payloads. This project is not endorsed by KONNWEI.

## Compatibility — read before installing

| Tester | Vendor lists BTLink? | Tested with this Linux bridge? |
|---|---|---|
| **KW650** | Yes | **YES** — battery report transfer and successful firmware update on Linux Mint, Wine 9, BTLink 7.2, USB `2e3c:5740` |
| KW210 | Yes | No — not claimed supported by this bridge |
| KW600 | Yes | No — not claimed supported by this bridge |
| KW710 | Yes | No — not claimed supported by this bridge |
| KW720 | Yes | No — not claimed supported by this bridge |
| KW208, KW510, KW808, KW320, KW310, KW309 | Vendor says no update/print | Not applicable |

Official model list: https://www.konnwei.com/capabilities/Download-Update-Tool.html

**Important:** v1.x is scoped to USB CDC ACM devices reporting **VID `2e3c`, PID `5740`** and a 12-character hardware serial. A model name cannot be inferred from the VID/PID. Other hardware revisions and the other vendor-listed models are *not validated*. Software fails closed if the expected USB interface is absent, ambiguous, or lacks the expected serial format.

## Easy installation: obtain the manufacturer installer inside the app

The `.deb` includes **only the open-source Wine compatibility bridge**, not KONNWEI's proprietary Windows application, drivers or firmware. Starting in **v1.2.0**, the setup wizard can detect and safely unpack BTLink download archives rather than requiring a bare `.exe`.

The wizard offers three choices:

1. **Automatic download** — checks KONNWEI's official update-tool page and its designated itoscanner portal for BTLink links. It also tries a **user-reported, unverified** `itoscanner.com/down/...` link (HTTPS first). If only HTTP works, the wizard shows a transport security warning and **requires explicit authorization** before downloading. The link is not guaranteed to remain valid, nor is its current payload verified by this project.
2. **Direct URL** — paste the full link to a BTLink `.exe`, `.zip`, `.7z` or `.rar` download. HTTPS is preferred; HTTP is never used silently. The program detects the content using its **file signature**, not the link extension or Content-Type. Download endpoints that lack a filename are supported.
3. **Browse local files** — select a downloaded Windows `.exe` or compressed archive (`.zip`, `.7z`, `.rar`). This is a **local file picker**, not an internet upload. ZIP uses Python's built-in extractor; 7z/RAR require the optional `7zip` package (`sudo apt install 7zip`).

For archives, setup selects a unique BTLink installer, refuses ambiguous selections, limits archive sizes and expansion ratios, and extracts only that selected file into a private local cache rather than unpacking arbitrary paths. The resulting file must pass Windows PE format and size checks. **A PE-format check and SHA256 fingerprint do not prove a download is authentic**. Confirm that you trust the source before proceeding.

**Install and launch the wizard:**

```bash
sudo apt install ./btlink-wine_1.2.0_all.deb
btlink-wine --install-btlink
```

Or bypass the source-selection menu:

```bash
btlink-wine --auto-installer
btlink-wine --installer-url 'http://www.itoscanner.com/down/4njkteiucfi88'
btlink-wine --browse-installer
btlink-wine --installer-file "$HOME/Downloads/BTLink.zip"
```

The itoscanner link above was provided by a user who saw it when hovering over the vendor download control; **its file contents and final redirect target have not been independently verified**. It is included only as a potential source, not an endorsement or guaranteed download. A manual HTTP approval and a separate **Run in Wine?** confirmation are required.

The wizard prints the download origin and SHA256 hash and asks before executing any Windows installer. Downloaded or extracted files remain only in `~/.cache/btlink-wine/vendor-downloads/` on the user's computer. No installer file, battery report or unique tester identifier is uploaded to GitHub.

**No manufacturer software is downloaded as part of `apt install`.** Downloading starts only when the user chooses to install BTLink or launches the wrapper without the vendor program already installed. If automatic download fails, choose the URL or local-file option instead.

## Install on Debian, Ubuntu or Linux Mint

For a 64-bit host, ensure **32-bit Wine application support** is installed. For example, Wine 9 from Linux Mint's Wine installer packages has worked; a different Wine distribution may require installing the appropriate `wine32` package. The BTLink application is 32-bit; a 64-bit-only Wine installation is not sufficient.

1. Download [`btlink-wine_1.2.0_all.deb`](dist/btlink-wine_1.2.0_all.deb) from this repository, or build it yourself with `bash packaging/build-deb.sh`. GitHub Actions also builds a downloadable package artifact on every successful run.
2. Install the bridge package:

   ```bash
   sudo apt install ./btlink-wine_1.2.0_all.deb
   ```

3. Run **`btlink-wine --install-btlink`** and choose automatic manufacturer download, paste a direct download link, or browse for an existing `.exe`/ZIP/7z/RAR file. The wizard creates its own 32-bit Wine prefix when needed, verifies the Windows executable format, asks for consent, and runs the manufacturer's installer through Wine. **Do not run the bundled Windows kernel driver installer**; Linux's `cdc_acm` handles the USB connection. If BTLink is already installed in the dedicated prefix, skip this step.

4. Connect a supported tester normally, by USB **without holding any keys**. Check that the kernel presents `/dev/ttyACM0` (or another `ttyACM*`):

   ```bash
   lsusb -d 2e3c:5740
   ls -l /dev/ttyACM*
   ```

   If read/write permission is denied, see [USB permissions](docs/USB_PERMISSIONS.md).

5. Configure the bridge for **your** connected tester:

   ```bash
   btlink-wine --setup
   btlink-wine --check
   btlink-wine
   ```

   The setup command patches a **local copy** of the installed vendor executable to use `BTVERIFY.DLL`; it stores your device's serial **only in local Wine files**. The `.deb` and Git repository contain no individual serial number or reports. For a custom Wine prefix, set `BTLINK_WINEPREFIX=/path/to/prefix` when running these commands.

6. To transfer a battery report, open the **Print** tab in BTLink, select the Print/Upload result function on the tester and send the result. This functionality was verified in normal mode using a KW650.

### Firmware updates — use caution

The KW650 was successfully updated from SW 1.5.1 to 1.5.6 through this bridge in a Linux Mint environment; after restarting, the tester displayed the newer SW version and unchanged hardware/serial identity. **That one successful update does not guarantee future updates or other models.** The manufacturer's Check Update button may **download and immediately flash firmware**, not just check versions.

- Check your model, hardware revision, firmware version and official firmware applicability before flashing.
- Enter Update Mode by holding OK when connecting USB (per device instructions), and verify the tester actually says `UPDATE MODE`.
- Use a stable USB cable and computer power. Do not unplug during flash. No software can guarantee recovery from interrupted firmware programming.
- The bridge verifies the device's USB identity, not firmware payload compatibility. It will *not* automatically kill an ongoing updater if the device re-enumerates.
- If in doubt, use manufacturer support rather than attempting an unverified firmware flash.

No confirmed public release notes have been found detailing **specific changes from KW650 SW 1.5.1 to 1.5.6**. Do not infer specific features or fixes from version numbers.

## Rollback

Close BTLink and run `btlink-wine --rollback` to remove the community executable and restore the previous local adapter DLL (when one was saved). This does not delete the vendor BTLink installation or Wine COM3 mapping. Uninstall the Debian package with `sudo apt remove btlink-wine` if no longer needed.

## Architecture

- `src/BTVERIFY-template.dll`: **generic** 32-bit Windows PE DLL (built from included `btverify.c`) intercepts five Windows SetupAPI enumeration functions. Contains a neutral 12-character placeholder, **not a user's serial**.
- `src/patch_import.py`: changes the SetupAPI import library name in a *local copy* of the vendor application; checks PE32 and expected imported functions before modifying.
- `src/device_guard.py`: discovers a real, currently attached Linux USB device, checks VID/PID and reads its serial locally.
- `src/vendor_installer.py`: obtains the manufacturer installer from manufacturer-designated download pages or a user URL/file; recognizes and safely extracts ZIP/7z/RAR archives and requires consent for HTTP transfers, then runs it in a user-local Wine prefix with consent.
- `src/main.py`: performs setup, maps Wine COM3 to the correct Linux tty, injects the device serial only into a locally generated adapter DLL, starts Wine and monitors disconnects. It does not send firmware commands.
- `packaging/build-deb.sh`: creates the installable `.deb` and runs privacy and unit tests.

## Build and test

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/privacy_audit.py
bash packaging/build-deb.sh
sudo apt install ./dist/btlink-wine_1.2.0_all.deb
```

Precompiled generic DLL included for easy installation; to rebuild on a developer's machine with 32-bit MinGW-w64, see [Building the DLL](docs/BUILDING.md).

## Privacy and distribution

**Never commit your installed Wine prefix or logs.** Tester serial numbers, battery reports, original vendor executables, Windows installers and firmware must stay off public GitHub. This repository ships only the original compatibility-code components. See [Privacy](PRIVACY.md), [Security](SECURITY.md) and [Third-party software](THIRD_PARTY.md).

## Troubleshooting

- `REFUSED: ... not found`: ensure the tester is plugged in and appears as `2e3c:5740` with a `ttyACM*` device. See `docs/USB_PERMISSIONS.md`.
- `REFUSED: ... COM3`: rerun `btlink-wine --setup` after unplug/replug if Linux assigned a different serial port. The mapping is local to the Wine prefix.
- Installer says `BTLink.exe not found`: run `btlink-wine --install-btlink` and choose a method. Use an actual vendor installer; this project does not bundle it.
- Version/layout differs: the PE patcher refuses unsupported application binaries. Open an issue with **sanitized** import names and versions; **do not upload proprietary application binaries or personal serials**.
- BTLink shows connection but no responses: first try Print mode; a connection label is not proof of bootloader communication.

### Automatic download limitations

KONNWEI's [official download tool page](https://www.konnwei.com/capabilities/Download-Update-Tool.html) directs visitors to `itoscanner.com`. A user supplied the linked address `http://www.itoscanner.com/down/4njkteiucfi88`, which may serve a compressed archive or redirect to another file. **We could not retrieve or authenticate its live content during development**; do not assume its name, format, version or availability. The downloader tries HTTPS first, requires consent for HTTP, and will not silently run an unexpected file. `UPLINK` is not a substitute for `BTLink`.

For `.7z` or `.rar` archives, install 7-Zip (`sudo apt install 7zip`). For archives containing more than one plausible BTLink executable, the program intentionally refuses automatic selection; inspect the archive and choose a specific known-good `.exe` instead.

## License

MIT for the **bridge code, build tooling and documentation only**. KONNWEI BTLink, Microsoft runtimes, manufacturer firmware and drivers are not part of this license or package.
