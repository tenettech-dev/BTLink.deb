# Building the bridge DLL

The `.deb` includes a **generic** 32-bit Windows DLL (12 zero-digit serial placeholder). The public DLL contains no per-device serial. Setup replaces the placeholder in a copy stored only on the user's computer.

To rebuild the DLL on Debian/Ubuntu with MinGW-w64:

```bash
sudo apt install gcc-mingw-w64-i686 binutils-mingw-w64-i686
cd src
i686-w64-mingw32-gcc -Os -s -shared -o BTVERIFY-template.dll btverify.c BTVERIFY.def -Wl,--out-implib,BTVERIFY.lib
file BTVERIFY-template.dll
```

Check the new DLL exports `SetupDiGetClassDevsA`, `SetupDiEnumDeviceInfo`, `SetupDiGetDeviceRegistryPropertyA`, `SetupDiGetDeviceInstanceIdA` and `SetupDiDestroyDeviceInfoList` and imports Windows DLLs. Verify it has exactly one `000000000000` ASCII marker. Compiling on a different toolchain may change the constant-pooling behavior; the packaging/tests **must fail** if the marker count changes. Validate on real hardware before replacing a known-good release DLL.
