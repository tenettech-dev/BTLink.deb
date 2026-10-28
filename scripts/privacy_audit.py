#!/usr/bin/env python3
"""Fail closed on common accidental personal/vendor asset publication."""
from pathlib import Path
import re
import sys
root=Path(__file__).resolve().parents[1]
excluded={'.git','dist','__pycache__','.venv','.mypy_cache','.pytest_cache'}
allowed = {
    '.github/FUNDING.yml', '.github/workflows/ci.yml', '.gitignore',
    'CHANGELOG.md', 'CONTRIBUTING.md', 'LICENSE', 'PRIVACY.md',
    'README.md', 'SECURITY.md', 'THIRD_PARTY.md',
    'docs/BUILDING.md', 'docs/USB_PERMISSIONS.md',
    'packaging/build-deb.sh', 'scripts/privacy_audit.py',
    'scripts/publish-github.sh',
    'src/BTVERIFY-template.dll', 'src/BTVERIFY.def', 'src/btverify.c',
    'src/device_guard.py', 'src/main.py', 'src/patch_import.py', 'src/vendor_installer.py',
    'tests/test_device_guard.py', 'tests/test_patcher.py', 'tests/test_template.py',
    'tests/test_vendor_installer.py',
}
forbidden=[
    (b'PRIVATE KEY-----', 'possible private key'),
    (b'-----BEGIN OPENSSH PRIVATE KEY', 'SSH private key'),
]
forbidden_names={ 'BTlink.exe','BTLink.exe','vc_redist.x86.exe','verified-bridge.log',
                  'print-communication.log','btlink-debug.log','user.reg','system.reg','userdef.reg'}
problems=[]
for f in root.rglob('*'):
    if any(p in excluded for p in f.relative_to(root).parts) or not f.is_file():continue
    if f.relative_to(root).as_posix() not in allowed:
        problems.append(f'Unexpected file (do not publish): {f.relative_to(root)}')
    if f.name in forbidden_names or f.suffix.lower() in {'.sys','.cat','.inf'}:
        problems.append(f'Forbidden file: {f.relative_to(root)}')
    data=f.read_bytes()
    for phrase,reason in forbidden:
        if f.resolve() != Path(__file__).resolve() and phrase.lower() in data.lower():problems.append(f'{f.relative_to(root)} contains {reason}')
    if re.search(rb'/home/[A-Za-z0-9_.-]+/',data) or re.search(rb'[A-Za-z]:\\Users\\[A-Za-z0-9_.-]+\\',data):
        problems.append(f'Absolute user home in {f.relative_to(root)}')
    # Catch potential literal credential assignments (not names of environment variables).
    if re.search(rb'(?:ghp_|github_pat_)[A-Za-z0-9_]{15,}',data):
        problems.append(f'Possible token in {f.relative_to(root)}')
if problems:
    for x in problems:print('FAIL:',x,file=sys.stderr)
    raise SystemExit(1)
print('PASS: no banned personal details, bundled proprietary installers, or credential patterns')
