# Privacy policy for this open-source adapter

The adapter needs to read USB vendor/product IDs, the connected tester's USB serial and sysfs/tty paths **locally** so it can verify the real device and construct the local Wine adapter. The device's serial is placed only into a **local generated DLL** inside the user's Wine prefix; it is not included in the public package.

No telemetry, accounts, advertising, analytics or application-side network calls are added by this bridge. The proprietary KONNWEI application may communicate with the manufacturer's update server independently; this project does not control that traffic.

**Never publish:** any test result, USB serial, device photo showing identifying numbers, Wine registry or installed-prefix files, a customized DLL, IP addresses, personal paths, or raw debug logs. The included privacy-audit script checks common mistakes, but it is not a guarantee against every secret. Review all files and commit diffs before making a GitHub repo public.

The installation wizard’s Browse action opens a **local** file picker; it does not upload the selected installer. Automatic or URL downloads are saved locally in a private cache directory and are never copied to GitHub.
