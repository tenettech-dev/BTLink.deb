# Third-party components and redistribution

KONNWEI BTLink, the original Windows installer, the ArteryTek driver package, Windows runtime libraries, firmware binaries and all manufacturer assets are **not included**, **not sublicensed** and **not covered by this repository's MIT license**. Users obtain them from the manufacturer under applicable terms.

Official vendor download page: https://www.konnwei.com/capabilities/Download-Update-Tool.html

Wine is a separate open-source compatibility project governed by its own licenses; it is not bundled in this package. This repo is independently developed and is not affiliated with KONNWEI or ArteryTek.

The v1.2.0 installer wizard downloads and extracts the manufacturer installer only on user request. The HTTP option requires explicit approval; PE format alone does not establish authenticity. It never adds it to this repository or Debian package. The user is responsible for selecting a trusted download source and accepting any vendor license.
