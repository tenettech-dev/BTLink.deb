## 1.1.0 — 2026-10-27 — Manufacturer installer wizard

- Added on-demand setup choices: automatic KONNWEI HTTPS download discovery, user-supplied direct HTTPS URL, or graphical file picker for a local Windows installer.
- Windows installer is obtained and run **locally with user consent**; it is not included in the public package or repository.
- Added 8 tests for vendor-domain restrictions, fallback paths, Windows EXE format verification, and local-file handling.
- Added Zenity as a recommended desktop dependency. Automatic download fails safely when no official vendor-hosted installer can be verified.
- Retained tested COM3 shim and manufacturer firmware safety warnings.

# Changelog (earlier releases)

## 1.0.0 — 2026-10-27

- Initial Debian package for an independent KONNWEI BTLink/Wine SetupAPI compatibility bridge.
- Real USB sysfs identity and Wine COM3 checks; no unconditional fake device.
- Generic compiled 32-bit DLL, with local-only personalization at setup.
- Read-only preflight, safe failure behavior, USB disconnect warning.
- Proprietary application and firmware excluded.
- KW650 normal report transfer and a complete firmware update observed on Linux Mint with a prototype of this bridge. The generalized `.deb` installer itself still requires field verification.
