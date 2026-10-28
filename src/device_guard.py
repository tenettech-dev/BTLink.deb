"""Read-only physical USB detection for the Wine BTLink bridge.

No individual tester identity is kept in this public module.
"""
from dataclasses import dataclass
from pathlib import Path
import os
import re
import stat

VID = "2e3c"
PID = "5740"
SERIAL_FORMAT = re.compile(r"[A-Za-z0-9]{12}\Z")


@dataclass(frozen=True)
class Device:
    tty: Path
    usb_dir: Path
    serial: str

    @property
    def wine_sysfs(self):
        return "Z:" + str(self.usb_dir).replace("/", "\\")


def identity(usb_dir):
    """Return device's live serial, or None if hardware does not match."""
    try:
        vid = (usb_dir / "idVendor").read_text().strip().lower()
        pid = (usb_dir / "idProduct").read_text().strip().lower()
        serial = (usb_dir / "serial").read_text().strip()
    except (OSError, UnicodeError):
        return None
    if vid != VID or pid != PID or not SERIAL_FORMAT.fullmatch(serial):
        return None
    if serial == "000000000000":  # reserved build-time template marker
        return None
    return serial.upper()


def discover(sys_tty=Path('/sys/class/tty'), dev_root=Path('/dev'), character=True):
    found = []
    for entry in sorted(sys_tty.glob('ttyACM*')):
        try:
            usb = (entry / 'device').resolve(strict=True).parent
            serial = identity(usb)
            if serial is None:
                continue
            tty = dev_root / entry.name
            if character and not stat.S_ISCHR(tty.stat().st_mode):
                continue
            if not tty.exists():
                continue
            found.append(Device(tty, usb, serial))
        except (OSError, ValueError):
            continue
    if len(found) != 1:
        raise RuntimeError(
            f'Expected exactly one USB CDC ACM tester matching {VID}:{PID} '
            'with a 12-character hardware serial. Found: ' + str(len(found)))
    return found[0]


def verify_wine(device, prefix):
    com3 = prefix / 'dosdevices/com3'
    if not com3.is_symlink() or com3.resolve() != device.tty.resolve():
        raise RuntimeError(f'Wine COM3 must point to {device.tty}; run --setup')
    if not os.access(device.tty, os.R_OK | os.W_OK):
        raise RuntimeError(f'No read/write access to {device.tty}; review dialout/uaccess rules')
    zdrive = prefix / 'dosdevices/z:'
    if not zdrive.is_symlink() or zdrive.resolve() != Path('/'):
        raise RuntimeError('Wine Z: drive must be a symlink to / for read-only sysfs checks')


def verified(prefix):
    device = discover()
    verify_wine(device, prefix)
    return device
