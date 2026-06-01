# Contributing

This repository hosts the **binary Windows installer** for Seraphina AGI.
**Source code lives elsewhere** — please direct code contributions there:

- 🐍 Python engine + RWAST + Glyph CLI: <https://github.com/SynerGro-AI/Seraphina.AGIv1.0.8>
- 🛠️ Copilot LM tools (Grok planner): <https://github.com/SynerGro-AI/seraphina-grok-planner>

## What you can contribute *here*

- **Bug reports** about the Windows installer experience (run-as-admin,
  PATH setup, uninstaller, etc.)
- **Documentation improvements** to the README or release notes
- **Verification reports** — confirmed-good install logs from different
  Windows versions, especially Windows 11 ARM, Windows Server, etc.

## What you should *not* PR here

- Changes to the engine code (PR against `Seraphina.AGIv1.0.8`)
- New installer binaries (built and signed by maintainers via release
  pipeline)
- Changes to the [LICENSE](LICENSE) — this is proprietary and
  intentionally not OSS

## Reporting an installer bug

Open an issue with:

- Installer version (filename + SHA256 from `manifest.txt`)
- Windows version (`winver`) + architecture
- Exact error message or screenshot
- Whether SmartScreen was bypassed cleanly

## License

The installer and this repository are proprietary — see
[LICENSE](LICENSE). By submitting an issue or PR you grant SynerGro AI
Corp a perpetual right to use that contribution.
