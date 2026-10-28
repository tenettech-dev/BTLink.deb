"""Acquire the *user's own* KONNWEI Windows installer; never redistribute it.

Automatic discovery uses only manufacturer-designated HTTPS hosts. If they do
not publish a usable download, fall back to a user-provided URL or file chooser.
"""
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urljoin, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

OFFICIAL_PAGE = 'https://www.konnwei.com/capabilities/Download-Update-Tool.html'
OFFICIAL_PORTAL = 'https://www.itoscanner.com/download/'
ALLOWED_HOSTS = frozenset({'konnwei.com', 'www.konnwei.com', 'itoscanner.com', 'www.itoscanner.com'})
MAX_HTML = 2 * 1024 * 1024
MAX_INSTALLER = 150 * 1024 * 1024
MIN_INSTALLER = 100 * 1024


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


def is_vendor_https(url):
    p = urlparse(url)
    return p.scheme == 'https' and (p.hostname or '').lower() in ALLOWED_HOSTS and not p.username and not p.password


def vendor_links(html, base):
    parser = Links()
    parser.feed(html)
    result = []
    for href, label in parser.links:
        url = urljoin(base, href)
        if not is_vendor_https(url):
            continue
        name = (urlparse(url).path + ' ' + label).lower()
        if 'btlink' in name and 'uplink' not in name:
            result.append(url)
    return list(dict.fromkeys(result))


def official_candidates(fetch_html):
    """Yield vendor-advertised installer links. Never guess an executable URL."""
    candidates = []
    seen = set()
    for page in (OFFICIAL_PAGE, OFFICIAL_PORTAL):
        try:
            html = fetch_html(page)
            for url in vendor_links(html, page):
                if url not in seen:
                    seen.add(url)
                    candidates.append(url)
        except (InstallerError, OSError, ValueError) as exc:
            print(f'Official download page unavailable ({page}): {exc}', file=sys.stderr)
    return candidates


def _open_https(url, vendor_only=False):
    if urlparse(url).scheme != 'https':
        raise InstallerError('Only HTTPS links are accepted. Download HTTP files manually and select them with Browse.')
    if vendor_only and not is_vendor_https(url):
        raise InstallerError('Automatic downloads must originate from KONNWEI-designated HTTPS hosts.')
    # For manually supplied URLs, permit any HTTPS host, but prohibit a downgrade.
    class Redirects(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if urlparse(newurl).scheme != 'https':
                raise InstallerError('Refusing an insecure HTTP redirect')
            if vendor_only and not is_vendor_https(newurl):
                raise InstallerError('Automatic download redirected outside manufacturer hosts')
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    return build_opener(Redirects()).open(Request(url, headers={'User-Agent':'BTLink-Wine-Bridge/1.1'}), timeout=20)


def fetch_official_html(url):
    with _open_https(url, vendor_only=True) as response:
        data = response.read(MAX_HTML + 1)
        if len(data) > MAX_HTML:
            raise InstallerError('Manufacturer download page exceeds expected size')
        return data.decode('utf-8', errors='replace')


def looks_like_windows_installer(data):
    if not MIN_INSTALLER <= len(data) <= MAX_INSTALLER or data[:2] != b'MZ':
        return False
    if len(data) < 0x40:
        return False
    pe = int.from_bytes(data[0x3c:0x40], 'little')
    return 0x40 <= pe <= len(data) - 4 and data[pe:pe+4] == b'PE\x00\x00'


def validate_installer(path):
    if not path.is_file() or path.suffix.lower() != '.exe':
        raise InstallerError('Select the original Windows BTLink installer (.exe), not BTLink program files or a firmware update.')
    size = path.stat().st_size
    if not MIN_INSTALLER <= size <= MAX_INSTALLER:
        raise InstallerError('Installer size is outside the accepted range (100 KiB–150 MiB).')
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


def download(url, cache, vendor_only=False):
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    with _open_https(url, vendor_only=vendor_only) as response:
        with tempfile.NamedTemporaryFile(dir=cache, suffix='.exe', prefix='.btlink-', delete=False) as fp:
            target = Path(fp.name)
            size = 0
            try:
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_INSTALLER:
                        raise InstallerError('Downloaded file is too large.')
                    fp.write(chunk)
            except BaseException:
                target.unlink(missing_ok=True)
                raise
    try:
        validate_installer(target)
        final = cache/'vendor-BTLink-installer.exe'
        os.chmod(target, 0o600)
        os.replace(target, final)
        return final
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def file_picker():
    """Local desktop file selection: nothing is uploaded to the internet."""
    if os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'):
        if shutil.which('zenity'):
            p = subprocess.run(['zenity','--file-selection','--title=Select official KONNWEI BTLink installer',
                                '--file-filter=Windows installers | *.exe'],
                               text=True, capture_output=True)
            if p.returncode == 0 and p.stdout.strip():
                return Path(p.stdout.strip()).expanduser()
            raise UserCancelled('File selection cancelled.')
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk(); root.withdraw()
            selected = filedialog.askopenfilename(title='Select official KONNWEI BTLink installer',
                                                   filetypes=[('Windows installer', '*.exe')])
            root.destroy()
            if selected:
                return Path(selected)
            raise UserCancelled('File selection cancelled.')
        except ImportError:
            pass
    if not sys.stdin.isatty():
        raise InstallerError('No graphical file picker found. Use --installer-file /path/to/BTlink.exe')
    path = input('Enter the path to the official BTLink installer (.exe): ').strip().strip('"\'')
    if not path:
        raise UserCancelled('No installer selected.')
    return Path(path).expanduser()


def choose_source():
    """Prefer a native desktop choice dialog; work in a terminal too."""
    options = {'AUTO':'Automatic download from the manufacturer',
               'URL':'Enter a direct HTTPS download link',
               'BROWSE':'Browse for an existing BTlink.exe'}
    if (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')) and shutil.which('zenity'):
        cmd = ['zenity','--list','--radiolist','--title=Install KONNWEI BTLink',
               '--text=Where should BTLink be obtained?','--column=Select', '--column=Option',
               '--column=Description','--width=620','--height=340']
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
        p = subprocess.run(['zenity','--entry','--title=BTLink direct download URL',
                            '--text=Paste the direct HTTPS link to the official BTLink installer:'],
                           text=True,capture_output=True)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip()
        raise UserCancelled('No URL provided.')
    if not sys.stdin.isatty():
        raise InstallerError('Use --installer-url https://example.com/BTlink.exe')
    return input('Paste the HTTPS download URL: ').strip()


def consent(path, source):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    print(f'Installer source: {source}\nInstaller: {path}\nSHA256: {digest}', flush=True)
    print('The vendor Windows installer will execute inside your local Wine environment.', flush=True)
    if (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')) and shutil.which('zenity'):
        p = subprocess.run(['zenity','--question','--title=Confirm BTLink installation',
                            '--text=Run the selected KONNWEI Windows installer using Wine?\n'
                                     f'Source: {source}\nSHA256: {digest}'],capture_output=True)
        return p.returncode == 0
    if sys.stdin.isatty():
        return input('Continue installing? [y/N]: ').strip().lower() in {'yes','y'}
    return False


def acquire(cache, mode=None, url=None, file=None, fetch_html=None):
    """Return validated path and origin; never execute anything."""
    if file is not None:
        return validate_installer(Path(file).expanduser().resolve()), 'local file selected by user'
    if url is not None:
        return download(url, cache), url
    if mode == 'BROWSE':
        return validate_installer(file_picker()), 'local file selected by user'
    if mode == 'URL':
        link = ask_url()
        return download(link, cache), link
    if mode == 'AUTO':
        for link in official_candidates(fetch_html or fetch_official_html):
            try:
                return download(link, cache, vendor_only=True), link
            except (InstallerError, OSError, ValueError) as exc:
                print(f'Manufacturer link unusable ({link}): {exc}', file=sys.stderr)
        raise InstallerError('No verified HTTPS BTLink executable was available from the official manufacturer pages.')
    raise InstallerError('Installer source not selected')


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
    """Vendor installer acquisition and execution, no serial or firmware commands."""
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
                raise InstallerError('Vendor installer exited, but BTLink.exe was not found. Confirm the Wine installation location.')
            print('PASS: Manufacturer BTLink is installed. Connect your tester and run btlink-wine --setup.')
            return installed
        except UserCancelled:
            raise
        except (InstallerError, OSError, ValueError) as exc:
            print('Installer option failed:', exc,file=sys.stderr)
            if choices is not None or not (sys.stdin.isatty() or shutil.which('zenity')):
                raise
            print('Choose a different source or cancel.',flush=True)
