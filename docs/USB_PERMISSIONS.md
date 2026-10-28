# Linux USB and serial device permissions

The tested KW650 enumerates as `2e3c:5740` and a Linux `cdc_acm` serial device (`/dev/ttyACM0` or similar). Verify with `lsusb -d 2e3c:5740` and `ls -l /dev/ttyACM*`.

**Preferred:** local desktop session permissions or membership in your distribution's `dialout` group. To add yourself (re-login required):

```bash
sudo usermod -aG dialout "$USER"
```

For systems where the user is logged in at the local graphical seat, `uaccess` can also be added with a narrowly scoped udev rule:

```bash
printf '%s\n' 'SUBSYSTEM=="tty", ATTRS{idVendor}=="2e3c", ATTRS{idProduct}=="5740", TAG+="uaccess"' |
    sudo tee /etc/udev/rules.d/70-btlink-wine.rules
sudo udevadm control --reload-rules
```

Reconnect the USB cable and confirm `test -r /dev/ttyACM0 && test -w /dev/ttyACM0` (adjust to the actual port). Do not use `chmod 777`, globally open USB device permissions or run Wine with `sudo`.

Some Wine installations also probe raw `/dev/bus/usb/...`; if that matters, a tightly scoped `uaccess` rule for `SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", ATTR{idVendor}=="2e3c", ATTR{idProduct}=="5740"` can be added by the local administrator. The serial interface should not require raw USB access to send and receive normal test data.
