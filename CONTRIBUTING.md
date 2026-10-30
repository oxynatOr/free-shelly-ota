# Contributing

[← README](README.md) · [Developer guide](docs/guide-developers.md) · [User guide](docs/guide.md) · [Roadmap](ROADMAP.md) · [Credits](CREDITS.md)

Thank you for helping. The most valuable contribution is a **report from a real device**, also when everything worked: nobody can say a device works until someone has flashed one.

## Ways to help

| You want to | Do this |
| --- | --- |
| Use the tool on a device | Follow the [Step-by-step guide](docs/guide.md), then [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml) |
| Get a device that has no profile | [Request it](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=new-device.yml); it helps most if you offer to test it |
| Report a wrong message or a crash | [Report a bug](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=bug.yml) with the output of `python ota.py --version` |
| Improve the docs | Open a pull request; small fixes need no issue |
| Add a device or change the code | Read the [Developer guide](docs/guide-developers.md), then open a pull request |

## Rules

- **Say how you know it.** A pin, a log line or a state (✅ 🟡 🔬 🧪) needs real evidence or a named source. Something read from firmware and not measured is written as *not confirmed*. Say what you did not check.
- **Keep private data out.** No MAC addresses, SSIDs, passwords, keys, cloud keys or LAN addresses of real devices in files, issues, logs or commit messages.
- **Never attach or commit** flash dumps, built ZIPs, DevKit images, Shelly firmware or a real `secrets.yaml`. They can hold credentials and per-device secrets.
- **Credit people.** Reporters and testers are named in `CREDITS.md`, on the device page and in the CHANGELOG.
- **State what your change breaks.** Say in the pull request and the CHANGELOG whether it is breaking or visible, and also when it is not, with the reason.
- **Risky behavior is opt-in** (a flag), never a new default.
- **Language:** docs, comments, commits and issues are in English.

## AI-assisted contributions

AI tools are welcome for code, tests, docs and translations, as long as the result is checked.

- **You own every line you submit.** Read it, understand it and run the tests yourself.
- **Hardware claims need real evidence.** Pins, log lines, measurements and device states come from a real device or a named source, never from a model's memory or a guess that sounds right.
- **Do not give secrets to AI services.** No flash dumps, ZIPs, `secrets.yaml` or logs with passwords, keys or MAC addresses.
- **Marking:** a `Co-Authored-By:` line in the commit is enough; individual lines need no mark.
- **Reports:** the wording of an issue may come from an AI, the logs must be real and unaltered.
- Contributions that are not checked or cannot be verified may be declined.

## Sending a pull request

1. Work on a branch (`feature/…`, `fix/…`, `docs/…`, `device/…`), one topic per branch.
2. Run `python -m unittest discover tests`. Tests that need the official packages are skipped without the local `fw/` cache; run them with it if you can ([Tests and CI](docs/guide-developers.md#3-tests-and-ci)).
3. Add a line under `## [Unreleased]` in the [CHANGELOG](CHANGELOG.md), with the breaking statement.
4. Describe in the pull request what you changed, what you tested (device, dev board or tests only) and what you did not.
5. Check `git status` before you commit: nothing from `fw/`, `out/` or `logs/`.

Adding a device step by step: [Add a new device](docs/guide-developers.md#6-add-a-new-device).

---

[Developer guide](docs/guide-developers.md) · [Device profiles](devices/README.md) · [Versions](docs/versions.md)
