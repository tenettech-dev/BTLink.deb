import io
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from vendor_installer import (
    InstallerError, UserCancelled, REPORTED_DOWNLOAD, official_candidates,
    vendor_links, is_vendor_https, looks_like_windows_installer,
    validate_installer, download, acquire, prepare_installer, archive_kind,
    _open_url, _select_archive_member,
)


def pe_bytes():
    header = bytearray(hashlib.shake_256(b'fake-windows-binary').digest(150000))
    header[:2] = b'MZ'
    header[0x3c:0x40] = (128).to_bytes(4, 'little')
    header[128:132] = b'PE\x00\x00'
    return bytes(header)


class DummyResponse(io.BytesIO):
    pass


class VendorInstallerTests(unittest.TestCase):
    def test_vendor_links_include_http_but_filter_untrusted_hosts(self):
        html = '''<a href="https://www.itoscanner.com/files/BTlink.zip">Download BTLink</a>
<a href="http://www.itoscanner.com/down/4njkteiucfi88">BTlink</a>
<a href="https://evil.test/BTlink.exe">BTlink untrusted</a>
<a href="https://www.itoscanner.com/UPlink.exe">UPlink</a>'''
        self.assertEqual(vendor_links(html,'https://www.itoscanner.com/download/'),
                         ['https://www.itoscanner.com/files/BTlink.zip',REPORTED_DOWNLOAD])

    def test_vendor_url_validation(self):
        self.assertTrue(is_vendor_https('https://konnwei.com/files/BTlink.zip'))
        self.assertFalse(is_vendor_https('http://konnwei.com/files/BTlink.zip'))
        self.assertFalse(is_vendor_https('https://konnwei.com.evil.test/files/BTlink.zip'))

    def test_auto_includes_reported_down_link_with_secure_preference(self):
        links = official_candidates(lambda _: '<p>No direct downloads</p>')
        self.assertEqual(links[-2:], ['https://www.itoscanner.com/down/4njkteiucfi88',
                                      REPORTED_DOWNLOAD])

    def test_auto_link_order_prioritizes_manufacturer_listed(self):
        def fake_html(url):
            if 'itoscanner' in url:
                return '<a href="/files/BTlink.zip">BTLink 7.2</a>'
            return '<a href="http://www.itoscanner.com/download/">Click here</a>'
        self.assertEqual(official_candidates(fake_html)[0],
                         'https://www.itoscanner.com/files/BTlink.zip')

    def test_auto_fails_when_no_link_delivers_valid_file(self):
        with tempfile.TemporaryDirectory() as d:
            with patch('vendor_installer._open_url', side_effect=OSError('offline')):
                with self.assertRaises(InstallerError):
                    acquire(Path(d),mode='AUTO',fetch_html=lambda _: '<p>No link</p>',
                            insecure_confirm=lambda _: True)

    def test_non_pe_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d)/'BTlink.exe'
            file.write_bytes(b'MZ' + b'x'*200000)
            with self.assertRaises(InstallerError):
                validate_installer(file)

    def test_pe_signature(self):
        data = pe_bytes()
        self.assertTrue(looks_like_windows_installer(data))
        with tempfile.TemporaryDirectory() as d:
            file = Path(d)/'BTlink.exe'
            file.write_bytes(data)
            self.assertEqual(validate_installer(file),file)

    def test_zip_selects_btlink_exe_and_ignores_bundled_driver(self):
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d)/'cache'
            archive = Path(d)/'vendor-download'
            with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr('Package/BTLink.exe', pe_bytes())
                z.writestr('Package/Drivers/Artery_VirtualCOM_DriverInstall.exe',pe_bytes())
                z.writestr('readme.txt','vendor package')
            output = prepare_installer(archive,cache)
            self.assertEqual(output.suffix, '.exe')
            self.assertEqual(output.read_bytes(),pe_bytes())

    def test_zip_rejects_ambiguous_files(self):
        with tempfile.TemporaryDirectory() as d:
            archive=Path(d)/'archive.zip'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('x/BTLink.exe',pe_bytes())
                z.writestr('y/BTlink.exe',pe_bytes())
            with self.assertRaisesRegex(InstallerError,'multiple'):
                prepare_installer(archive,Path(d)/'cache')

    def test_zip_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            archive=Path(d)/'archive.zip'
            with zipfile.ZipFile(archive,'w') as z:
                info=zipfile.ZipInfo('BTLink.exe')
                info.create_system=3
                info.external_attr=(0o120777 << 16)
                z.writestr(info,'../../etc/passwd')
            with self.assertRaisesRegex(InstallerError,'symlink'):
                prepare_installer(archive,Path(d)/'cache')

    def test_zip_rejects_path_traversal(self):
        with self.assertRaises(InstallerError):
            _select_archive_member(['../BTlink.exe'])
        with self.assertRaises(InstallerError):
            _select_archive_member(['x/../../BTlink.exe'])

    def test_nested_zip_supported(self):
        inner=io.BytesIO()
        with zipfile.ZipFile(inner,'w') as z:
            z.writestr('BTLink.exe',pe_bytes())
        with tempfile.TemporaryDirectory() as d:
            archive=Path(d)/'outer.zip'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('btlink.zip',inner.getvalue())
            file=prepare_installer(archive,Path(d)/'cache')
            self.assertEqual(file.read_bytes(),pe_bytes())

    def test_download_magic_detects_zip_even_without_extension(self):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as z:
            z.writestr('BTLink.exe',pe_bytes())
        with tempfile.TemporaryDirectory() as d:
            with patch('vendor_installer._open_url',return_value=DummyResponse(data.getvalue())):
                path=download('https://www.itoscanner.com/down/example',Path(d))
                self.assertEqual(path.name,'vendor-BTLink-installer.exe')
                self.assertEqual(path.read_bytes(),pe_bytes())

    def test_http_requires_interactive_authorization(self):
        with self.assertRaises(UserCancelled):
            _open_url(REPORTED_DOWNLOAD,insecure_confirm=lambda _: False)

    def test_http_downgrade_blocked(self):
        with self.assertRaises(UserCancelled):
            _open_url('http://www.itoscanner.com/down/unknown',insecure_confirm=lambda _: False)

    def test_local_file_not_uploaded(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'BTLink.exe';path.write_bytes(pe_bytes())
            result,origin=acquire(Path(d),file=path)
            self.assertEqual(result,path)
            self.assertIn('local file',origin)

    def test_local_zip_prepared_offline(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'BTLink.zip'
            with zipfile.ZipFile(path,'w') as z:z.writestr('BTLink.exe',pe_bytes())
            result,origin=acquire(Path(d)/'cache',file=path)
            self.assertEqual(result.suffix,'.exe')
            self.assertIn('local file',origin)

    def test_unrecognized_html_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'fake.exe';path.write_bytes(b'<html>Not an archive</html>')
            with self.assertRaises(InstallerError):
                prepare_installer(path,Path(d)/'cache')


if __name__ == '__main__':
    unittest.main()
