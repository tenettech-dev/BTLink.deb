# Contributing

Before opening a pull request, run `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py' -v`, `python3 scripts/privacy_audit.py` and `bash packaging/build-deb.sh`.

Never commit manufacturer applications, Windows drivers, firmware, pre-personalized bridge DLLs, tester serial numbers, raw logs, local Wine prefixes, test reports, user profiles, or any credentials.

To propose support for another BTLink-listed model, report its **model name and USB VID/PID** without sharing serial numbers, and provide redacted read-only evidence of normal report transfers before requesting a supported status. Firmware programming is higher risk and should not be inferred from printing capability.
