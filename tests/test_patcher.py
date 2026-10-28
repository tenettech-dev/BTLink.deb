import struct
import unittest
from patch_import import inspect_and_patch

class PEPatchTests(unittest.TestCase):
    def make_pe(self):
        b = bytearray(2048)
        b[:2] = b'MZ'
        struct.pack_into('<I', b, 0x3c, 0x80)
        b[0x80:0x84] = b'PE\0\0'
        struct.pack_into('<H', b, 0x84, 0x14c)  # machine
        struct.pack_into('<H', b, 0x86, 1)  # section count
        struct.pack_into('<H', b, 0x94, 0xe0) # opt size
        struct.pack_into('<H', b, 0x98, 0x10b) # PE32
        struct.pack_into('<I', b, 0x98+92, 16)
        struct.pack_into('<II', b, 0x98+104, 0x1000, 40)
        sec = 0x98+0xe0
        b[sec:sec+7] = b'.idata\0'
        struct.pack_into('<IIII', b, sec+8, 0x400, 0x1000, 0x400, 0x200)
        struct.pack_into('<IIIII', b, 0x200, 0x1060, 0, 0, 0x1080, 0x1060)
        struct.pack_into('<II', b, 0x260, 0x10a0, 0)
        b[0x280:0x28d] = b'SETUPAPI.DLL\0'
        b[0x2a2:0x2a2+22] = b'SetupDiGetClassDevsA\0'
        return bytes(b)

    def test_valid_import_is_patched(self):
        original = self.make_pe()
        output, names = inspect_and_patch(original)
        self.assertEqual(names, ['SetupDiGetClassDevsA'])
        self.assertEqual(bytes(output[0x280:0x28d]), b'BTVERIFY.DLL\0')
        self.assertEqual(original[0x280:0x28d], b'SETUPAPI.DLL\0')

    def test_unknown_import_fails_closed(self):
        b = bytearray(self.make_pe())
        b[0x2a2:0x2a2+22] = b'UnsupportedSetupCall\0'
        with self.assertRaisesRegex(ValueError, 'Unimplemented SetupAPI'):
            inspect_and_patch(b)

    def test_non_pe_fails_closed(self):
        with self.assertRaises(ValueError):
            inspect_and_patch(b'not a PE')

if __name__ == '__main__':
    unittest.main()
