# Security and firmware safety

This adapter is experimental and cannot independently authenticate downloaded firmware, validate model firmware compatibility, or guarantee recovery from flash failures. Clicking the manufacturer's Check Update control can begin programming immediately.

The public binary is a generic PE32 DLL which must be personalized to the physical USB serial **locally**. Only connect a tester you own or are authorized to service. Do not run this software as root. USB disconnect monitoring does not terminate a firmware updater, which could damage a device mid-flash.

Report vulnerabilities with a minimal, sanitized reproducer. Do not upload private USB identifiers, credentials, proprietary binaries or unredacted logs to public issues.
