#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VER="${BTLINK_DEB_VERSION:-1.2.0}"
case "$VER" in *[!a-zA-Z0-9.+~:-]*|'') echo 'Invalid version' >&2; exit 1;; esac
python3 "$ROOT/scripts/privacy_audit.py"
PYTHONPATH="$ROOT/src" python3 -m unittest discover -s "$ROOT/tests" -p 'test_*.py' -v
DEST="$ROOT/dist"
mkdir -p "$DEST"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/DEBIAN" "$STAGE/usr/share/btlink-wine" "$STAGE/usr/bin" "$STAGE/usr/share/applications" "$STAGE/usr/share/doc/btlink-wine"
for f in main.py device_guard.py patch_import.py vendor_installer.py btverify.c BTVERIFY.def BTVERIFY-template.dll; do
  install -m 644 "$ROOT/src/$f" "$STAGE/usr/share/btlink-wine/$f"
done
cat > "$STAGE/usr/bin/btlink-wine" <<'EOF'
#!/bin/sh
exec python3 /usr/share/btlink-wine/main.py "$@"
EOF
chmod 755 "$STAGE/usr/bin/btlink-wine"
cat > "$STAGE/usr/share/applications/btlink-wine.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=BTLink (KONNWEI via Wine)
GenericName=Battery Tester Utility
Comment=Run an individually installed KONNWEI BTLink application under Wine
Exec=btlink-wine
Terminal=true
Categories=Utility;
EOF
cp "$ROOT/README.md" "$STAGE/usr/share/doc/btlink-wine/README.md"
cp "$ROOT/LICENSE" "$STAGE/usr/share/doc/btlink-wine/LICENSE"
cat > "$STAGE/DEBIAN/control" <<EOF
Package: btlink-wine
Version: $VER
Section: utils
Priority: optional
Architecture: all
Maintainer: BTLink Community Contributors <noreply@github.com>
Depends: python3 (>= 3.8)
Recommends: wine, usbutils, zenity, 7zip
Description: Linux Wine bridge for KONNWEI BTLink battery tester tools
 Includes the original open-source compatibility shim, a generic Windows
 SetupAPI adapter DLL, a local-only device authorization step, launcher,
 and USB serial checks. Offers vendor link discovery, direct URL or local file chooser; supports ZIP/7z/RAR with consent.
 Requires vendor BTLink, obtained directly by the user at setup.
 Does not ship KONNWEI programs, drivers, firmware or tester identities.
EOF
OUT="$DEST/btlink-wine_${VER}_all.deb"
dpkg-deb --build --root-owner-group "$STAGE" "$OUT"
dpkg-deb --info "$OUT"
dpkg-deb --contents "$OUT" | tail -n 15
printf '\nBuilt: %s\n' "$OUT"
sha256sum "$OUT"
