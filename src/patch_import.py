#!/usr/bin/env python3
"""Patch a COPY of BTLink.exe's import name, SETUPAPI.DLL -> BTVERIFY.DLL.

Fails closed for unsupported PE architecture or missing/unexpected imports.
No changes to the original executable.
"""
from pathlib import Path
import argparse
import hashlib
import os
import struct
import sys

SUPPORTED = {
    'SetupDiGetClassDevsA', 'SetupDiEnumDeviceInfo',
    'SetupDiGetDeviceRegistryPropertyA', 'SetupDiGetDeviceInstanceIdA',
    'SetupDiDestroyDeviceInfoList',
}


def get_u16(buf, offset): return struct.unpack_from('<H', buf, offset)[0]
def get_u32(buf, offset): return struct.unpack_from('<I', buf, offset)[0]


def inspect_and_patch(blob):
    b = bytearray(blob)
    if len(b) < 512 or b[:2] != b'MZ':
        raise ValueError('Not a PE executable')
    pe = get_u32(b, 0x3c)
    if pe + 248 > len(b) or b[pe:pe+4] != b'PE\0\0':
        raise ValueError('Invalid PE header')
    if get_u16(b, pe+4) != 0x14c:
        raise ValueError('Expected 32-bit x86 (IMAGE_FILE_MACHINE_I386) executable')
    section_count = get_u16(b, pe+6)
    opt_size = get_u16(b, pe+20)
    opt = pe + 24
    if get_u16(b, opt) != 0x10b or opt_size < 112:
        raise ValueError('Expected PE32 optional header')
    if get_u32(b, opt+92) < 2:
        raise ValueError('No import data directory')
    import_rva = get_u32(b, opt+104)
    import_size = get_u32(b, opt+108)
    if not import_rva or not import_size:
        raise ValueError('Import directory missing')
    sec = opt + opt_size
    sections = []
    for i in range(section_count):
        p = sec + i*40
        if p + 40 > len(b): raise ValueError('Truncated sections')
        vsz, va, rawsz, rawptr = struct.unpack_from('<IIII', b, p+8)
        sections.append((va, max(vsz, rawsz), rawptr, rawsz))

    def offset(rva):
        for va, vsize, raw, rawsz in sections:
            if va <= rva < va+vsize and rva-va < rawsz:
                result = raw + rva - va
                if result >= len(b): raise ValueError('Invalid RVA')
                return result
        raise ValueError('RVA not backed by raw PE section: 0x%x' % rva)

    def read_z(o):
        end = b.find(b'\0', o, min(o+512, len(b)))
        if end < 0: raise ValueError('Unterminated string')
        return bytes(b[o:end]).decode('ascii')

    found = []
    for i in range(min(import_size//20, 512)):
        p = offset(import_rva + i*20)
        if p+20 > len(b): raise ValueError('Truncated import descriptor')
        original_first_thunk, _stamp, _forwarder, name_rva, first_thunk = struct.unpack_from('<IIIII', b, p)
        if not any((original_first_thunk, name_rva, first_thunk)):
            break
        name_off = offset(name_rva)
        name = read_z(name_off)
        if name.lower() != 'setupapi.dll': continue
        thunk = original_first_thunk or first_thunk
        imports = []
        for j in range(256):
            val = get_u32(b, offset(thunk + j*4))
            if not val: break
            if val & 0x80000000:
                raise ValueError('SetupAPI ordinal import unsupported')
            imports.append(read_z(offset(val)+2))
        unknown = set(imports) - SUPPORTED
        if unknown:
            raise ValueError('Unimplemented SetupAPI imports: ' + ', '.join(sorted(unknown)))
        if not imports: raise ValueError('No SetupAPI function imports')
        found.append((name_off, imports))
    if len(found) != 1:
        raise ValueError('Expected exactly one SETUPAPI.DLL import; found %d' % len(found))
    name_off, imports = found[0]
    replacement = b'BTVERIFY.DLL\0'
    if len(replacement) != len('SETUPAPI.DLL')+1:
        raise AssertionError('Unexpected replacement size')
    b[name_off:name_off+len(replacement)] = replacement
    return b, imports


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('original', type=Path)
    ap.add_argument('output', type=Path)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    if not args.original.is_file(): sys.exit('Missing original: ' + str(args.original))
    if args.original.resolve() == args.output.resolve(): sys.exit('Refusing to overwrite original')
    if args.output.exists() and not args.dry_run: sys.exit('Refusing to overwrite existing output')
    raw = args.original.read_bytes()
    patched, names = inspect_and_patch(raw)
    print('Original SHA256:', hashlib.sha256(raw).hexdigest())
    print('Original SetupAPI imports:', ', '.join(names))
    print('Patched bytes:', sum(a != b for a, b in zip(raw, patched)))
    if args.dry_run:
        print('DRY RUN: original unchanged; no output written')
    else:
        args.output.write_bytes(patched)
        os.chmod(args.output, args.original.stat().st_mode & 0o777)
        print('Test executable:', args.output)

if __name__ == '__main__': main()
