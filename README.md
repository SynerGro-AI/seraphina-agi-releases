# Seraphina AGI

**Free download. Closed source. Honest pricing.**

[![Latest release](https://img.shields.io/github/v/release/synergroaicorp/seraphina-agi-releases?label=download&color=blue)](https://github.com/synergroaicorp/seraphina-agi-releases/releases/latest)

Seraphina AGI is a personal AGI runtime for Windows — voice control, local
mining (opt-in), background automation, secure mesh networking between
your own machines. It runs entirely on your own hardware.

---

## Download

**[⬇ Download the latest installer](https://github.com/synergroaicorp/seraphina-agi-releases/releases/latest)**

Pick `Seraphina-AGI-Setup.exe` from the **Assets** section of the latest
release.

### "Windows protected your PC" / SmartScreen warning

Until our code-signing certificate is issued, Windows will show a blue
SmartScreen warning the first time you run the installer:

1. Click **More info**
2. Click **Run anyway**

You can verify the file's integrity against the SHA256 hash published in
`Seraphina-AGI-Setup.manifest.txt` (also in the release assets):

```powershell
Get-FileHash .\Seraphina-AGI-Setup.exe -Algorithm SHA256
```

The output must match the hash in the manifest. If it doesn't, **do not
run the installer** and please file an issue.

---

## What you get for free

- The full Seraphina AGI desktop app
- Local voice control + wake-word
- Background mining (opt-in, off by default — your hardware, your call)
- Secure mesh networking between your installs

## What requires a subscription

Subscriptions are managed at
[**synergroaicorp.com**](https://synergroaicorp.com) via Stripe:

| Tier                  | Price                                    |
|-----------------------|------------------------------------------|
| **Founder Monthly**   | **$1.00 / month** (first 100,000 only)   |
| **Founder Annual**    | **$88.88 / year** (first 100,000 only)   |
| **Regular Monthly**   | $8.88 / month (after Founders fill)      |

Founders who cancel can re-subscribe at any time and keep the $1 rate
for life — as long as they originally joined within the first 100,000
seats.

Subscriptions unlock cloud-side features (model routing, sync, premium
tools). The base app keeps working without one.

---

## System requirements

- **OS**: Windows 10 (1903+) or Windows 11, x64
- **RAM**: 8 GB minimum, 16 GB recommended
- **Disk**: ~2 GB for the installer payload, more for model cache
- **GPU**: Optional. NVIDIA GTX 1060 / RX 580 or better for mining.

The installer takes ~5 minutes (Python + Node + Inno-bundled binaries).

---

## Privacy & security

- The installer **does not** phone home during setup.
- The runtime contacts `synergroaicorp.com` **only** if you enter a
  license key (for entitlement verification).
- Mining (if enabled) connects to public pools you configure.
- The mesh networking module binds UDP/47720 on your LAN and signs every
  packet with an Ed25519 keypair sealed via Windows DPAPI (machine
  scope) — it does **not** reach outside your network unless you
  configure bootstrap peers.

---

## Support

- Bug reports: open an issue on this repo
- Subscription / billing: `founders@synergroaicorp.com`
- General: `hello@synergroaicorp.com`

## Other SynerGro AI tools

- 🐍 [seraphina-agi](https://pypi.org/project/seraphina-agi/) — Python engine, RWAST semantic translator, Glyph CLI
- 🛠️ [seraphina-grok-planner](https://github.com/SynerGro-AI/seraphina-grok-planner) — Copilot LM tools (verifier, planner, repo grep)
- 🌐 <https://synergroaicorp.com>

---

## License

Proprietary. See [LICENSE](LICENSE). Free to download and run for
personal use. Commercial redistribution, reverse engineering, or
extracting components requires written permission.

© 2026 SynerGro AI Corp. All rights reserved.
