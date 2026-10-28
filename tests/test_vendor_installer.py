import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from vendor_installer import (InstallerError, official_candidates, vendor_links,
    is_vendor_https, looks_like_windows_installer, validate_installer, download, acquire)


class VendorInstallerTests(unittest.TestCase):
    def test_vendor_links_accept_only_approved_https(self):
        html = '''<a href="https://www.itoscanner.com/files/BTlink.exe">Download BTLink</a>
<a href="http://www.itoscanner.com/BTlink.exe">BTlink insecure</a>
<a href="https://evil.test/BTlink.exe">BTlink untrusted</a>
<a href="https://www.itoscanner.com/UPlink.exe">UPlink</a>'''
        self.assertEqual(vendor_links(html,'https://www.itoscanner.com/download/'),
                         ['https://www.itoscanner.com/files/BTlink.exe'])

    def test_vendor_url_validation(self):
        self.assertTrue(is_vendor_https('https://konnwei.com/files/BTlink.exe'))
        self.assertFalse(is_vendor_https('http://konnwei.com/files/BTlink.exe'))
        self.assertFalse(is_vendor_https('https://konnwei.com.evil.test/files/BTlink.exe'))

    def test_auto_discovers_direct_link_only_when_published(self):
        def fake_html(url):
            if 'itoscanner' in url:
                return '<a href="/files/BTlink.exe">BTLink 7.2</a>'
            return '<a href="http://www.itoscanner.com/download/">Click here</a>'
        self.assertEqual(official_candidates(fake_html),
                         ['https://www.itoscanner.com/files/BTlink.exe'])

    def test_auto_fails_without_direct_link(self):
        self.assertEqual(official_candidates(lambda _: '<a href="/download/">Download</a>'), [])
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(InstallerError):
                acquire(Path(d),mode='AUTO',fetch_html=lambda _: '<p>No installer</p>')

    def test_non_pe_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d)/'BTlink.exe'
            file.write_bytes(b'MZ' + b'x'*200000)
            with self.assertRaises(InstallerError):
                validate_installer(file)

    def test_minimal_pe_signature(self):
        header = bytearray(150000)
        header[:2] = b'MZ'
        header[0x3c:0x40] = (128).to_bytes(4, 'little')
        header[128:132] = b'PE\x00\x00'
        self.assertTrue(looks_like_windows_installer(header))
        with tempfile.TemporaryDirectory() as d:
            file = Path(d)/'BTlink.exe'
            file.write_bytes(header)
            self.assertEqual(validate_installer(file), file)

    def test_https_required_before_download(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(InstallerError):
                download('http://www.itoscanner.com/BTlink.exe',Path(d))

    def test_local_file_never_uploaded(self):
        header = bytearray(150000)
        header[:2] = b'MZ'
        header[0x3c:0x40] = (128).to_bytes(4,'little')
        header[128:132] = b'PE\x00\x00'
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'BTlink.exe'; path.write_bytes(header)
            result,origin = acquire(Path(d),file=path)
            self.assertEqual(result,path)
            self.assertIn('local file', origin)


if __name__ == '__main__':
    unittest.main()
