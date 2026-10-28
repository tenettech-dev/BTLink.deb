# Changelog

## 1.0.0 — 2026-10-27

- Initial Debian package for an independent KONNWEI BTLink/Wine SetupAPI compatibility bridge.
- Real USB sysfs identity and Wine COM3 checks; no unconditional fake device.
- Generic compiled 32-bit DLL, with local-only personalization at setup.
- Read-only preflight, safe failure behavior, USB disconnect warning.
- Proprietary application and firmware excluded.
- KW650 normal report transfer and a complete firmware update observed on Linux Mint with a prototype of this bridge. The generalized `.deb` installer itself still requires field verification.
