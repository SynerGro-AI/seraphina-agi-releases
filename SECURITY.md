# Security Policy

This repository distributes the **Windows installer binary** for
Seraphina AGI. Source code lives at
[Seraphina.AGIv1.0.8](https://github.com/SynerGro-AI/Seraphina.AGIv1.0.8).

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email: **security@synergroaicorp.com**
(or open a [private security advisory](https://github.com/SynerGro-AI/seraphina-agi-releases/security/advisories/new))

Please include:

- A clear description of the vulnerability and its impact
- Steps to reproduce
- Installer version (see `Seraphina-AGI-Setup.manifest.txt`)
- Windows version + architecture

We aim to acknowledge within 3 business days.

## Integrity check

Every release ships a SHA256 manifest. Always verify before running:

```powershell
Get-FileHash .\Seraphina-AGI-Setup.exe -Algorithm SHA256
# Compare to the hash in Seraphina-AGI-Setup.manifest.txt
```

## SmartScreen warning

Until our code-signing certificate is issued, Windows shows a
SmartScreen warning on first run. This is **expected** for unsigned
installers from small publishers — it is not evidence of tampering.
Use the SHA256 verification above to confirm integrity.

## Scope

In scope: anything in `Seraphina-AGI-Setup.exe` (installer logic, what
gets dropped on disk, what runs on first launch).

Out of scope: vulnerabilities in the Python `seraphina-agi` package
itself — report those at the [main repo's security
policy](https://github.com/SynerGro-AI/Seraphina.AGIv1.0.8/security/policy).
