"""Acquire a manufacturer's BTLink installer, optionally inside a vendor archive.

No manufacturer binary is bundled or uploaded. An HTTP transport is never
trusted silently, and extraction emits only a selected Windows executable.
"""
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from urllib.parse import urljoin, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

OFFICIAL_PAGE = 'https://www.konnwei.com/capabilities/Download-Update-Tool.html'
OFFICIAL_PORTAL = 'https://www.itoscanner.com/download/'
# User-reported BTLink link from the KONNWEI-designated download portal.
# Its current response, version, and authenticity have NOT been independently verified.
REPORTED_DOWNLOAD = 'http://www.itoscanner.com/down/4njkteiucfi88'
ALLOWED_HOSTS = frozenset({'konnwei.com', 'www.konnwei.com', 'itoscanner.com', 'www.itoscanner.com'})
MAX_HTML = 2 * 1024 * 1024
MAX_DOWNLOAD = 160 * 1024 * 1024
MAX_INSTALLER = 150 * 1024 * 1024
MIN_INSTALLER = 100 * 1024
MAX_ARCHIVE_MEMBERS = 700
MAX_EXTRACTED_TOTAL = 260 * 1024 * 1024
MAX_ARCHIVE_DEPTH = 2


class InstallerError(RuntimeError):
    pass


class UserCancelled(InstallerError):
    pass


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.href = None
        self.words = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.href = dict(attrs).get('href')
            self.words = []

    def handle_data(self, data):
        if self.href is not None:
            self.words.append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self.href is not None:
            self.links.append((self.href, ' '.join(self.words)))
            self.href = None
            self.words = []


def is_vendor_link(url):
    p = urlparse(url)
    return (p.scheme in ('http', 'https') and (p.hostname or '').lower() in ALLOWED_HOSTS
            and not p.username and not p.password and p.port in (None, 80, 443))


def is_vendor_https(url):
    return is_vendor_link(url) and urlparse(url).scheme == 'https'


def vendor_links(html, base):
    parser = Links()
    parser.feed(html)
    result = []
    for href, label in parser.links:
        url = urljoin(base, href)
        if not is_vendor_link(url):
            continue
        name = (urlparse(url).path + ' ' + label).lower()
        if 'btlink' in name and 'uplink' not in name:
            result.append(url)
    return list(dict.fromkeys(result))


def official_candidates(fetch_html):
    """Vendor page links first; known reported link last, with HTTPS attempted first."""
    candidates = []
    seen = set()
    for page in (OFFICIAL_PAGE, OFFICIAL_PORTAL):
        try:
            for url in vendor_links(fetch_html(page), page):
                if url not in seen:
                    seen.add(url)
                    candidates.append(url)
        except (InstallerError, OSError, ValueError) as exc:
            print(f'Manufacturer download page unavailable ({page}): {exc}', file=sys.stderr)
    # Some versions of itoscanner present a non-descriptive "/down/<id>" link.
    # We do not pretend the reported link is verified or stable.
    reported = urlparse(REPORTED_DOWNLOAD)
    https_version = reported._replace(scheme='https').geturl()
    for url in (https_version, REPORTED_DOWNLOAD):
        if url not in seen:
            seen.add(url)
            candidates.append(url)
    return candidates


def confirm_insecure(url):
    message = ('This BTLink download uses unencrypted HTTP. The file could be modified in transit. '
               'Its authenticity cannot be verified by the bridge.\n'
               f'URL: {url}\n\nDownload it anyway? You will be asked again before running the installer.')
    if (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')) and shutil.which('zenity'):
        p = subprocess.run(['zenity', '--question', '--title=Insecure manufacturer download',
                            '--width=580', '--text='+message], capture_output=True)
        return p.returncode == 0
    if sys.stdin.isatty():
        print('\nWARNING:', message, file=sys.stderr)
        return input('Allow this HTTP download? [y/N]: ').strip().lower() in ('y', 'yes')
    return False


def _open_url(url, vendor_only=False, insecure_confirm=confirm_insecure):
    p = urlparse(url)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise InstallerError('An HTTP or HTTPS URL without embedded credentials is required.')
    if vendor_only and not is_vendor_link(url):
        raise InstallerError('Automatic downloads are limited to KONNWEI-designated hosts.')
    insecure = p.scheme == 'http'
    if insecure and not insecure_confirm(url):
        raise UserCancelled('HTTP download not approved. Choose HTTPS or a local file instead.')

    class Redirects(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            dest = urlparse(newurl)
            if dest.scheme not in ('http', 'https') or dest.username or dest.password:
                raise InstallerError('Refusing an unsafe download redirect.')
            if dest.scheme == 'http' and (not insecure or (dest.hostname or '').lower() != p.hostname.lower()):
                raise InstallerError('Refusing an insecure redirect; supply the URL explicitly instead.')
            if vendor_only and not is_vendor_link(newurl):
                raise InstallerError('Automatic download redirected outside the designated manufacturer hosts.')
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    return build_opener(Redirects()).open(Request(url, headers={'User-Agent':'BTLink-Wine-Bridge/1.2'}), timeout=25)


def fetch_official_html(url):
    if not is_vendor_https(url):
        raise InstallerError('Manufacturer page discovery must use HTTPS.')
    with _open_url(url, vendor_only=True) as response:
        data = response.read(MAX_HTML + 1)
        if len(data) > MAX_HTML:
            raise InstallerError('Manufacturer page exceeds expected size.')
        return data.decode('utf-8', errors='replace')


def looks_like_windows_installer(data):
    if not MIN_INSTALLER <= len(data) <= MAX_INSTALLER or data[:2] != b'MZ':
        return False
    if len(data) < 0x40:
        return False
    pe = int.from_bytes(data[0x3c:0x40], 'little')
    return 0x40 <= pe <= len(data) - 4 and data[pe:pe+4] == b'PE\x00\x00'


def validate_installer(path):
    path = Path(path)
    if not path.is_file() or path.suffix.lower() != '.exe':
        raise InstallerError('Select a BTLink installer (.exe), or a ZIP/7z/RAR archive containing it.')
    size = path.stat().st_size
    if not MIN_INSTALLER <= size <= MAX_INSTALLER:
        raise InstallerError('Executable size outside allowed range (100 KiB–150 MiB).')
    with path.open('rb') as fp:
        dos = fp.read(0x40)
        if len(dos) != 0x40 or dos[:2] != b'MZ':
            raise InstallerError('Selected file is not a Windows executable.')
        offset = int.from_bytes(dos[0x3c:0x40], 'little')
        if offset < 0x40 or offset > size - 4:
            raise InstallerError('Invalid Windows executable header.')
        fp.seek(offset)
        if fp.read(4) != b'PE\x00\x00':
            raise InstallerError('Selected file is not a valid Windows PE executable.')
    return path


def archive_kind(path):
    with Path(path).open('rb') as fp:
        magic = fp.read(8)
    if magic[:2] == b'MZ':
        return 'exe'
    if magic.startswith((b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08')):
        return 'zip'
    if magic.startswith(b'7z\xbc\xaf\x27\x1c'):
        return '7z'
    if magic.startswith(b'Rar!\x1a\x07'):
        return 'rar'
    raise InstallerError('Download is not a Windows executable or supported ZIP/7z/RAR archive (it may be HTML).')


def _member_priority(name):
    """Only select BTLink-looking installers, never unrelated bundled drivers."""
    normalized = name.replace('\\', '/').strip('/')
    base = normalized.rsplit('/', 1)[-1].lower()
    if not normalized or '\x00' in normalized or normalized.startswith('/'):
        return None
    segments = normalized.split('/')
    if any(s in ('', '.', '..') for s in segments):
        return None
    if any(x in normalized.lower() for x in ('driver/', 'drivers/', 'ch340/', 'artery_')):
        return None
    if base == 'btlink.exe':
        return 0
    if base.endswith('.exe') and 'btlink' in base and 'uplink' not in base:
        return 1
    if base in ('setup.exe', 'install.exe'):
        return 5
    if base.endswith(('.zip', '.7z', '.rar')) and 'btlink' in base:
        return 10
    return None


def _select_archive_member(entries):
    ranked = sorted(((_member_priority(n), n) for n in entries if _member_priority(n) is not None))
    if not ranked:
        raise InstallerError('Archive has no identifiable BTLink installer. Download and inspect it manually.')
    best = ranked[0][0]
    if len([n for p, n in ranked if p == best]) > 1:
        raise InstallerError('Archive contains multiple possible BTLink installers; select a specific file manually.')
    return ranked[0][1]


def _private_target(cache, suffix):
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(cache, 0o700)
    fp = tempfile.NamedTemporaryFile(dir=cache, prefix='.btlink-', suffix=suffix, delete=False)
    return fp, Path(fp.name)


def _copy_limited(source, output, limit):
    amount = 0
    while True:
        chunk = source.read(65536)
        if not chunk:
            break
        amount += len(chunk)
        if amount > limit:
            raise InstallerError('Extracted file exceeds the allowed size.')
        output.write(chunk)


def _extract_zip(source, cache):
    with zipfile.ZipFile(source) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_MEMBERS:
            raise InstallerError('Archive contains too many members.')
        if sum(i.file_size for i in infos) > MAX_EXTRACTED_TOTAL:
            raise InstallerError('Archive declares too much uncompressed data.')
        selectable = []
        for info in infos:
            if info.is_dir():
                continue
            if stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK:
                raise InstallerError('Archive includes symlinks; refusing extraction.')
            if info.flag_bits & 1:
                raise InstallerError('Password-protected archive is not supported.')
            if info.file_size > MAX_INSTALLER:
                continue
            if info.file_size and info.file_size / max(info.compress_size, 1) > 500:
                raise InstallerError('Archive member compression ratio is suspicious.')
            selectable.append(info.filename)
        chosen = _select_archive_member(selectable)
        info = archive.getinfo(chosen)
        suffix = Path(chosen).suffix.lower()
        fp, out = _private_target(cache, suffix)
        try:
            with fp, archive.open(info) as member:
                _copy_limited(member, fp, MAX_INSTALLER)
            return out
        except BaseException:
            out.unlink(missing_ok=True)
            raise


def _extract_7z_or_rar(source, cache):
    exe = shutil.which('7z') or shutil.which('7zz')
    if not exe:
        raise InstallerError('This archive requires 7-Zip. Install it with: sudo apt install 7zip')
    listed = subprocess.run([exe, 'l', '-slt', str(source)], text=True,
                            capture_output=True, timeout=45)
    if listed.returncode:
        raise InstallerError('7-Zip could not list this archive.')
    entries = []
    for block in listed.stdout.split('\n\n'):
        values = {}
        for line in block.splitlines():
            if ' = ' in line:
                k, v = line.split(' = ', 1)
                values[k.strip()] = v.strip()
        if 'Path' not in values or 'Size' not in values or values.get('Folder') == '+':
            continue
        try:
            size = int(values['Size'])
        except ValueError:
            continue
        entries.append((values['Path'], size))
    if len(entries) > MAX_ARCHIVE_MEMBERS or sum(s for _, s in entries) > MAX_EXTRACTED_TOTAL:
        raise InstallerError('Archive exceeds member count or total extracted-size limit.')
    chosen = _select_archive_member([name for name, size in entries if size <= MAX_INSTALLER])
    # stdout-only extraction: never allow 7z to write archive paths to disk.
    proc = subprocess.Popen([exe, 'x', '-so', str(source), chosen], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    suffix = Path(chosen).suffix.lower()
    fp, out = _private_target(cache, suffix)
    try:
        with fp:
            _copy_limited(proc.stdout, fp, MAX_INSTALLER)
        stderr = proc.stderr.read(8192)
        code = proc.wait(timeout=45)
        if code:
            raise InstallerError(f'7-Zip could not extract the selected BTLink installer: {stderr[:160]!r}')
        return out
    except BaseException:
        proc.kill()
        proc.wait()
        out.unlink(missing_ok=True)
        raise
    finally:
        proc.stdout.close()
        proc.stderr.close()


def prepare_installer(path, cache, depth=0):
    """Return a validated .exe, extracting at most one safe member per archive level."""
    if depth > MAX_ARCHIVE_DEPTH:
        raise InstallerError('Archive nesting is too deep.')
    path = Path(path)
    if path.stat().st_size > MAX_DOWNLOAD:
        raise InstallerError('Installer/archive exceeds size limit.')
    kind = archive_kind(path)
    if kind == 'exe':
        if path.suffix.lower() == '.exe':
            return validate_installer(path)
        fp, out = _private_target(cache, '.exe')
        try:
            with fp, path.open('rb') as original:
                _copy_limited(original, fp, MAX_INSTALLER)
            return validate_installer(out)
        except BaseException:
            out.unlink(missing_ok=True)
            raise
    if kind == 'zip':
        extracted = _extract_zip(path, cache)
    else:
        extracted = _extract_7z_or_rar(path, cache)
    try:
        result = prepare_installer(extracted, cache, depth+1)
        if result != extracted:
            extracted.unlink(missing_ok=True)
        return result
    except BaseException:
        extracted.unlink(missing_ok=True)
        raise


def download(url, cache, vendor_only=False, insecure_confirm=confirm_insecure):
    cache = Path(cache)
    fp, target = _private_target(cache, '.download')
    try:
        with fp, _open_url(url, vendor_only=vendor_only, insecure_confirm=insecure_confirm) as response:
            _copy_limited(response, fp, MAX_DOWNLOAD)
        output = prepare_installer(target, cache)
        final = cache/'vendor-BTLink-installer.exe'
        if output != target:
            target.unlink(missing_ok=True)
        os.chmod(output, 0o600)
        os.replace(output, final)
        return final
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def file_picker():
    """Browse local files; nothing is uploaded to the network."""
    if os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'):
        if shutil.which('zenity'):
            p = subprocess.run(['zenity','--file-selection','--title=Select BTLink installer or archive',
                                '--file-filter=BTLink installers and archives | *.exe *.EXE *.zip *.ZIP *.7z *.7Z *.rar *.RAR'],
                               text=True, capture_output=True)
            if p.returncode == 0 and p.stdout.strip():
                return Path(p.stdout.strip()).expanduser()
            raise UserCancelled('File selection cancelled.')
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk(); root.withdraw()
            selected = filedialog.askopenfilename(title='Select BTLink installer or archive',
                                                   filetypes=[('Installers and archives', '*.exe *.zip *.7z *.rar'), ('All files', '*')])
            root.destroy()
            if selected:
                return Path(selected)
            raise UserCancelled('File selection cancelled.')
        except (ImportError, RuntimeError):
            pass
    if not sys.stdin.isatty():
        raise InstallerError('No file picker found; use --installer-file /path/to/BTLink.zip')
    path = input('Path to BTLink installer or ZIP/7z/RAR archive: ').strip().strip('"\'')
    if not path:
        raise UserCancelled('No installer selected.')
    return Path(path).expanduser()


def choose_source():
    options = {'AUTO':'Automatically locate vendor BTLink (archives handled)',
               'URL':'Provide a direct download URL (HTTPS preferred)',
               'BROWSE':'Browse for BTLink.exe, ZIP, 7z or RAR'}
    if (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')) and shutil.which('zenity'):
        cmd = ['zenity','--list','--radiolist','--title=Install KONNWEI BTLink',
               '--text=Where should BTLink be obtained?','--column=Select', '--column=Option',
               '--column=Description','--width=690','--height=340']
        for i,(key,label) in enumerate(options.items()):
            cmd += ['TRUE' if i == 0 else 'FALSE',key,label]
        p = subprocess.run(cmd,text=True,capture_output=True)
        if p.returncode == 0 and p.stdout.strip() in options:
            return p.stdout.strip()
        raise UserCancelled('Installation cancelled.')
    if not sys.stdin.isatty():
        raise InstallerError('Interactive selection requires a terminal or Zenity. Use --auto-installer, --installer-url, or --installer-file.')
    print('\nChoose how to obtain the official KONNWEI BTLink installer:')
    for i,label in enumerate(options.values(),1):
        print(f'  {i}. {label}')
    return {'1':'AUTO','2':'URL','3':'BROWSE'}.get(input('Select [1-3]: ').strip(), '')


def ask_url():
    if (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')) and shutil.which('zenity'):
        p = subprocess.run(['zenity','--entry','--title=BTLink download URL',
                            '--text=Paste the direct BTLink download link (HTTPS preferred):'],
                           text=True,capture_output=True)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip()
        raise UserCancelled('No URL provided.')
    if not sys.stdin.isatty():
        raise InstallerError('Use --installer-url https://example.com/BTlink.zip')
    return input('Paste the BTLink download URL: ').strip()


def consent(path, source):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    print(f'Installer source: {source}\nInstaller: {path}\nSHA256: {digest}', flush=True)
    print('This only confirms PE format, not manufacturer authenticity or firmware compatibility.', flush=True)
    print('The selected Windows program will execute in your local Wine environment.', flush=True)
    if (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')) and shutil.which('zenity'):
        p = subprocess.run(['zenity','--question','--title=Confirm BTLink installation',
                            '--text=Run this Windows installer in Wine?\n'
                                     f'Source: {source}\nSHA256: {digest}\n'
                                     'PE format is not a signature or authenticity check.'],capture_output=True)
        return p.returncode == 0
    if sys.stdin.isatty():
        return input('Continue installing? [y/N]: ').strip().lower() in {'yes','y'}
    return False


def acquire(cache, mode=None, url=None, file=None, fetch_html=None, insecure_confirm=confirm_insecure):
    """Return validated local Windows installer and origin. Never execute it."""
    cache = Path(cache)
    if file is not None:
        return prepare_installer(Path(file).expanduser().resolve(), cache), 'local file selected by user'
    if url is not None:
        return download(url, cache, insecure_confirm=insecure_confirm), url
    if mode == 'BROWSE':
        return prepare_installer(file_picker(), cache), 'local file selected by user'
    if mode == 'URL':
        link = ask_url()
        return download(link, cache, insecure_confirm=insecure_confirm), link
    if mode == 'AUTO':
        for link in official_candidates(fetch_html or fetch_official_html):
            try:
                return download(link, cache, vendor_only=True,
                                insecure_confirm=insecure_confirm), link
            except UserCancelled:
                raise
            except (InstallerError, OSError, ValueError, zipfile.BadZipFile) as exc:
                print(f'Vendor link unavailable or invalid ({link}): {exc}',file=sys.stderr)
        raise InstallerError('No usable vendor BTLink download found. Paste a direct URL or browse for its installer/archive.')
    raise InstallerError('Installer source not selected.')


def _init_prefix(prefix):
    if (prefix/'dosdevices').exists():
        return
    prefix.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ,'WINEPREFIX':str(prefix),'WINEARCH':'win32'}
    print('Creating a dedicated 32-bit Wine prefix...', flush=True)
    p = subprocess.run(['wineboot','-i'],env=env,check=False)
    if p.returncode:
        raise InstallerError('Wine prefix initialization failed; install 32-bit Wine support.')


def install(prefix, mode=None, url=None, file=None, consent_required=True):
    """Vendor installer acquisition + explicit execution consent; no firmware commands."""
    cache = Path.home()/'.cache/btlink-wine/vendor-downloads'
    if any(x is not None for x in (url,file)):
        choices = [('URL' if url else 'BROWSE', url, file)]
    elif mode is not None:
        choices = [(mode,None,None)]
    else:
        choices = None
    while True:
        try:
            method, address, selected_file = choices.pop(0) if choices is not None else (choose_source(),None,None)
            path, origin = acquire(cache, mode=method, url=address, file=selected_file)
            if consent_required and not consent(path,origin):
                raise UserCancelled('Installation cancelled by user.')
            _init_prefix(prefix)
            print('Starting manufacturer BTLink installer under Wine...', flush=True)
            run = subprocess.run(['wine',str(path)],env={**os.environ,'WINEPREFIX':str(prefix)})
            if run.returncode:
                raise InstallerError(f'Windows installer returned exit code {run.returncode}.')
            installed = prefix/'drive_c/Program Files/BTlink/bin/BTLink.exe'
            if not installed.is_file():
                raise InstallerError('Windows installer exited, but BTLink.exe was not found. Check its installation path.')
            print('PASS: Manufacturer BTLink installed. Connect the tester and run btlink-wine --setup.')
            return installed
        except UserCancelled:
            raise
        except (InstallerError, OSError, ValueError, zipfile.BadZipFile) as exc:
            print('Installer option failed:',exc,file=sys.stderr)
            if choices is not None or not (sys.stdin.isatty() or shutil.which('zenity')):
                raise
            print('Choose a different source or cancel.',flush=True)
