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

**Important:** v1.0 is scoped to USB CDC ACM devices reporting **VID `2e3c`, PID `5740`** and a 12-character hardware serial. A model name cannot be inferred from the VID/PID. Other hardware revisions and the other vendor-listed models are *not validated*. Software fails closed if the expected USB interface is absent, ambiguous, or lacks the expected serial format.

## Easy installation: obtain the manufacturer installer inside the app

The `.deb` packages **only the open-source compatibility bridge**, not KONNWEI's copyrighted Windows program. Beginning in **v1.1.0**, users do not have to locate and run the Windows installer manually: the setup wizard handles it.

The installer offers three choices:

1. **Automatic download (default selection)** — checks KONNWEI's official update-tool page and its designated itoscanner download portal for a usable **HTTPS** BTLink `.exe` download. The vendor has not published a confirmed, permanent direct BTLink URL; if the current pages do not provide a compatible executable or are unavailable, automatic download fails safely and the wizard offers another method.
2. **Direct download URL** — paste the full HTTPS URL of a Windows BTLink installer, such as one supplied by the manufacturer or another source you independently trust. HTTP links are rejected; if the source only supports HTTP, download the file yourself and use Browse. Files are checked for a valid Windows PE header and size before Wine is launched; this is **not an authenticity signature check**. Review the source before consenting to run it.
3. **Browse local files** — select an already downloaded official `BTlink.exe` installer using a graphical file picker (Zenity, or Tkinter where available). It is a **local file selection**, not an upload to the internet.

The wizard shows the chosen download source and SHA256, and asks before executing the vendor installer. Files downloaded automatically are stored in `~/.cache/btlink-wine/vendor-downloads/` **locally only**. Nothing is bundled, published, or uploaded by this project.

**Run the installer wizard:**

```bash
sudo apt install ./btlink-wine_1.1.0_all.deb
btlink-wine --install-btlink
```

To skip the source-selection menu and directly pick a method:

```bash
btlink-wine --auto-installer
btlink-wine --installer-url 'https://manufacturer.example/path/to/BTlink.exe'
btlink-wine --browse-installer
btlink-wine --installer-file "$HOME/Downloads/BTlink.exe"
```

The example URL is a placeholder; use a verified real link. **Nothing is downloaded when the `.deb` itself is installed**; downloads happen only when explicitly starting the wizard or first launch, and the installer requests confirmation before Wine executes the EXE. If the BTLink application is missing when you run `btlink-wine --setup` or launch the desktop shortcut, setup presents the same installer choices. With a supported USB tester already connected, the desktop shortcut also configures the bridge and starts BTLink after the vendor installer finishes.

## Install on Debian, Ubuntu or Linux Mint

For a 64-bit host, ensure **32-bit Wine application support** is installed. For example, Wine 9 from Linux Mint's Wine installer packages has worked; a different Wine distribution may require installing the appropriate `wine32` package. The BTLink application is 32-bit; a 64-bit-only Wine installation is not sufficient.

1. Download [`btlink-wine_1.1.0_all.deb`](dist/btlink-wine_1.1.0_all.deb) from this repository, or build it yourself with `bash packaging/build-deb.sh`. GitHub Actions also builds a downloadable package artifact on every successful run.
2. Install the bridge package:

   ```bash
   sudo apt install ./btlink-wine_1.1.0_all.deb
   ```

3. Run **`btlink-wine --install-btlink`** and choose automatic manufacturer download, paste a direct HTTPS installer link, or browse for an existing BTlink installer. The wizard creates its own 32-bit Wine prefix when needed, verifies the Windows executable format, asks for consent, and runs the manufacturer's installer through Wine. **Do not run the bundled Windows kernel driver installer**; Linux's `cdc_acm` handles the USB connection. If BTLink is already installed in the dedicated prefix, skip this step.

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
- `src/vendor_installer.py`: obtains the manufacturer installer from official HTTPS pages where available, user-supplied HTTPS URL, or a local file picker, then runs it in a user-local Wine prefix with consent.
- `src/main.py`: performs setup, maps Wine COM3 to the correct Linux tty, injects the device serial only into a locally generated adapter DLL, starts Wine and monitors disconnects. It does not send firmware commands.
- `packaging/build-deb.sh`: creates the installable `.deb` and runs privacy and unit tests.

## Build and test

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/privacy_audit.py
bash packaging/build-deb.sh
sudo apt install ./dist/btlink-wine_1.1.0_all.deb
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

### Automatic download limitation

KONNWEI directs users to its [official download tool page](https://www.konnwei.com/capabilities/Download-Update-Tool.html), which refers to `itoscanner.com`. As of this release we could not verify a stable, HTTPS direct `.exe` download URL. The automatic option actively checks the official pages at setup time and only downloads a discoverable vendor-hosted HTTPS Windows installer; **it will not guess URLs, download an unrelated UPLINK installer, or silently switch to an untrusted mirror**. Use the direct URL or file-picker fallback if the official site is down or doesn't publish a usable direct link.

## License

MIT for the **bridge code, build tooling and documentation only**. KONNWEI BTLink, Microsoft runtimes, manufacturer firmware and drivers are not part of this license or package.
