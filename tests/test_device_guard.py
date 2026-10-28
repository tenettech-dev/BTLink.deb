import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from device_guard import discover, identity, verify_wine

class DeviceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        self.usb=root/'sys/devices/usb1/2-3'
        (self.usb/'2-3:1.0').mkdir(parents=True)
        sys=root/'sys/class/tty/ttyACM0'
        sys.mkdir(parents=True)
        (sys/'device').symlink_to(self.usb/'2-3:1.0')
        self.sys=sys.parent
        self.dev=root/'dev'
        self.dev.mkdir()
        (self.dev/'ttyACM0').touch()
        self.prefix=root/'prefix'
        (self.prefix/'dosdevices').mkdir(parents=True)
        (self.prefix/'dosdevices/z:').symlink_to('/')
        (self.prefix/'dosdevices/com3').symlink_to(self.dev/'ttyACM0')
        for field,value in {'idVendor':'2e3c','idProduct':'5740','serial':'ABCDEFGHIJKL'}.items():
            (self.usb/field).write_text(value+'\n')

    def test_detects_generic_serial(self):
        d=discover(self.sys,self.dev,character=False)
        self.assertEqual(d.serial,'ABCDEFGHIJKL')
        verify_wine(d,self.prefix)

    def test_bad_pid(self):
        (self.usb/'idProduct').write_text('df11')
        with self.assertRaises(RuntimeError): discover(self.sys,self.dev,character=False)

    def test_missing(self):
        (self.usb/'serial').unlink()
        with self.assertRaises(RuntimeError): discover(self.sys,self.dev,character=False)

    def test_incorrect_serial_length(self):
        (self.usb/'serial').write_text('ABCDEFGHIJKLMNOPQ')
        self.assertIsNone(identity(self.usb))

    def test_incorrect_com_mapping(self):
        d=discover(self.sys,self.dev,character=False)
        (self.prefix/'dosdevices/com3').unlink()
        (self.prefix/'dosdevices/com3').symlink_to('/dev/null')
        with self.assertRaises(RuntimeError):verify_wine(d,self.prefix)

    def test_reserved_marker(self):
        (self.usb/'serial').write_text('000000000000')
        with self.assertRaises(RuntimeError):discover(self.sys,self.dev,character=False)
