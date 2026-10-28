#!/usr/bin/env python3
"""BTLink Wine bridge setup/launcher. Never supplies firmware or vendor binaries."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from device_guard import discover, verified
from patch_import import inspect_and_patch
from vendor_installer import install as install_vendor, InstallerError

BASE = Path(__file__).resolve().parent
DEFAULT_PREFIX = Path.home() / '.local/share/wineprefixes/btlink'
TEMPLATE_SERIAL = b'000000000000'


def paths():
    prefix = Path(os.environ.get('BTLINK_WINEPREFIX', str(DEFAULT_PREFIX))).expanduser().resolve()
    bindir = prefix / 'drive_c/Program Files/BTlink/bin'
    return prefix, bindir, bindir/'BTLink.exe', bindir/'BTLink-community.exe', bindir/'BTVERIFY.dll'


def check_files():
    prefix, _, orig, out, dll = paths()
    if not orig.is_file():
        raise RuntimeError('KONNWEI BTLink.exe is not installed in the selected Wine prefix. '
                           'Get the official installer from KONNWEI and run it with Wine first.')
    if not out.is_file() or not dll.is_file():
        raise RuntimeError('Bridge not configured. With tester connected run: btlink-wine --setup')
    return prefix, out, dll


def make_dll(template, serial):
    raw = template.read_bytes()
    if raw.count(TEMPLATE_SERIAL) != 1:
        raise RuntimeError('Unexpected bridge DLL template marker count')
    payload = serial.encode('ascii')
    if len(payload) != len(TEMPLATE_SERIAL):
        raise RuntimeError('This bridge requires a 12-character USB serial')
    return raw.replace(TEMPLATE_SERIAL, payload)


def atomic_write(target, data):
    fd, name = tempfile.mkstemp(prefix='.btlink-staged-', dir=str(target.parent))
    try:
        with os.fdopen(fd, 'wb') as fp:
            fp.write(data)
        os.chmod(name, 0o644)
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def map_port(prefix, tty):
    dosdir = prefix/'dosdevices'
    dosdir.mkdir(parents=True, exist_ok=True)
    dest = dosdir/'com3'
    if dest.is_symlink() and dest.resolve() == tty.resolve():
        pass
    else:
        if dest.exists() and not dest.is_symlink():
            raise RuntimeError('COM3 exists but is not a symlink; cannot replace automatically')
        if dest.is_symlink():
            previous = dosdir/'com3.btlink-original'
            if not previous.exists() and not previous.is_symlink():
                previous.symlink_to(os.readlink(dest))
            dest.unlink()
        dest.symlink_to(tty)
    # This is Wine's user registry, not the host's registry.
    result = subprocess.run(
        ['wine','reg','add',r'HKLM\Software\Wine\Ports','/v','COM3',
         '/t','REG_SZ','/d',str(tty),'/f'],
        env={**os.environ,'WINEPREFIX':str(prefix)},
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    if result.returncode:
        raise RuntimeError('Wine COM3 registry mapping failed: ' + result.stderr.strip())


def setup():
    prefix, bindir, original, target, dll = paths()
    if not original.is_file():
        print('Manufacturer BTLink is missing. Choose automatic download, a URL, or an existing installer.')
        install_vendor(prefix)
    if not (prefix/'dosdevices/z:').is_symlink() or (prefix/'dosdevices/z:').resolve()!=Path('/'):
        raise RuntimeError('Wine Z: must map to /')
    device = discover()
    if not os.access(device.tty, os.R_OK | os.W_OK):
        raise RuntimeError(f'User cannot read and write {device.tty}. See docs/USB_PERMISSIONS.md')
    patched, imports = inspect_and_patch(original.read_bytes())
    generated = make_dll(BASE/'BTVERIFY-template.dll', device.serial)
    # Preserve any existing (possibly earlier private bridge) DLL only locally.
    if dll.is_file() and dll.read_bytes() != generated:
        backup = bindir/'BTVERIFY.dll.precommunity-backup'
        if not backup.exists():
            shutil.copy2(dll, backup)
    map_port(prefix, device.tty)
    atomic_write(dll, generated)
    atomic_write(target, patched)
    os.chmod(target, 0o755)
    verify = verified(prefix)
    print('PASS: BTLink import adapter installed for detected USB device')
    print(f'PASS: COM3 -> {verify.tty}')
    print('The device serial stays in your local Wine files; it is never published.')
    print('SetupAPI imports:', ', '.join(imports))
    print('Next: btlink-wine --check ; btlink-wine')


def run(check=False):
    if not check:
        prefix, _, orig, community, dll = paths()
        if not orig.is_file():
            print('Manufacturer BTLink is not installed. Starting first-run installer.')
            install_vendor(prefix)
        if not community.is_file() or not dll.is_file():
            print('Configuring the bridge for your connected tester...')
            setup()
    prefix, target, dll = check_files()
    device = verified(prefix)
    # Verify the installed DLL belongs to this specific attached unit, not an earlier unit.
    if dll.read_bytes() != make_dll(BASE/'BTVERIFY-template.dll', device.serial):
        raise RuntimeError('Installed bridge does not match connected tester. Run btlink-wine --setup')
    print('PASS: ArteryTek USB device, local serial, COM3 and bridge configuration verified')
    if check:
        print('Read-only checks complete; no USB commands issued.')
        return 0
    env = os.environ.copy()
    env.update({'WINEPREFIX':str(prefix), 'BTLINK_USB_SYSFS':device.wine_sysfs, 'WINEDEBUG':'-all'})
    print('Launching BTLink. Firmware update is user-initiated and carries a bricking risk.', flush=True)
    print('An update might re-enumerate USB; disconnect monitoring WILL NOT kill the updater.', flush=True)
    process = subprocess.Popen(['wine',str(target)],env=env)
    disappeared = False
    try:
        while process.poll() is None:
            time.sleep(0.5)
            try:
                current = verified(prefix)
                present = current.tty == device.tty and current.serial == device.serial
            except (RuntimeError,OSError):
                present = False
            if not present and not disappeared:
                print('WARNING: Tester disconnected/changed. Do not start any new activity.',
                      file=sys.stderr,flush=True)
                disappeared = True
            elif present and disappeared:
                print('Tester reconnected. Restart BTLink before proceeding.',file=sys.stderr,flush=True)
                disappeared = False
        return process.wait()
    except KeyboardInterrupt:
        print('Close BTLink normally; no automatic termination of a firmware update.',file=sys.stderr)
        return 130


def rollback():
    _, bindir, _, target, dll = paths()
    if target.exists():
        if b'BTVERIFY.DLL\0' not in target.read_bytes():
            raise RuntimeError('Refusing to delete an unrecognized community executable')
        target.unlink()
    backup = bindir/'BTVERIFY.dll.precommunity-backup'
    if backup.is_file():
        os.replace(backup, dll)
        print('Restored the previously installed local BTVERIFY.dll')
    else:
        print('No earlier adapter DLL backup; left local DLL in place')
    print('Removed community executable. Wine registry and COM mappings retained.')


def main():
    p=argparse.ArgumentParser(description='KONNWEI BTLink compatibility adapter for Wine (not the vendor app)')
    p.add_argument('--rollback',action='store_true',help='Remove community EXE and restore earlier local adapter DLL')
    p.add_argument('--setup',action='store_true',help='Configure bridge for currently connected supported USB tester')
    p.add_argument('--check',action='store_true',help='Read-only physical device and Wine check')
    p.add_argument('--install-btlink', action='store_true', help='Download or select the official Windows BTLink installer')
    source=p.add_mutually_exclusive_group()
    source.add_argument('--auto-installer', action='store_true', help='Discover BTLink from vendor pages and offer a reported HTTP fallback')
    source.add_argument('--installer-url', metavar='URL', help='Download a Windows installer or ZIP/7z/RAR archive (HTTPS preferred; HTTP requires confirmation)')
    source.add_argument('--installer-file', metavar='PATH', help='Use an existing local BTLink installer or ZIP/7z/RAR archive')
    source.add_argument('--browse-installer', action='store_true', help='Choose BTLink.exe using a graphical file picker')
    args=p.parse_args()
    try:
        if args.rollback:
            rollback()
            return 0
        if args.install_btlink or args.auto_installer or args.installer_url or args.installer_file or args.browse_installer:
            mode = ('AUTO' if args.auto_installer else 'BROWSE' if args.browse_installer else None)
            install_vendor(paths()[0], mode=mode, url=args.installer_url, file=args.installer_file)
            return 0
        if args.setup:
            setup()
            return 0
        return run(args.check)
    except (OSError,RuntimeError,ValueError,InstallerError) as exc:
        print('REFUSED:',exc,file=sys.stderr)
        return 2


if __name__=='__main__': sys.exit(main())
