# Developer guide

[← README](../README.md) · [Documentation](README.md) · [Contributing](../CONTRIBUTING.md) · [User guide](guide.md) · [Device profiles](../devices/README.md) · [Commands](commands.md) · [Roadmap](../ROADMAP.md)

[1 Orientation](#1-orientation) · [2 Set up](#2-set-up) · [3 Tests](#3-tests-and-ci) · [4 Rules](#4-rules-of-the-project) · [5 Branches](#5-branches-commits-and-pull-requests) · [6 New device](#6-add-a-new-device) · [7 Hardware](#7-find-out-what-a-device-does) · [8 Test ladder](#8-the-test-ladder) · [9 Reports](#9-handle-a-device-report) · [10 Profile change](#10-change-a-profile) · [11 Code](#11-change-the-tool) · [12 Release](#12-release) · [13 Related](#13-related-repositories-and-tools) · [Checklists](#checklists)

For people who add devices, test them, answer reports or change the tool. Someone who only wants to flash a device reads the [User guide](guide.md).

## 1. Orientation

The tool is a Python command-line program (3.10 or newer, one dependency: PyYAML; `bleak` only for Bluetooth). It runs from a checkout as `python ota.py`; it reads
profiles, partitions and the firmware cache from there and is not meant to be installed as a package.

| Path | What is in it |
| --- | --- |
| `ota.py` | Entry point and the command line (arguments, the help text, the command functions) |
| `shelly_ota/` | The modules, one topic each (below) |
| `devices/*.yaml`, `devices/profiles.lock` | One profile per device, plus the revision and content hash of each |
| `partitions/<Profile>-stock.csv` | Shelly's partition table as an ESPHome `partitions:` CSV, one per profile |
| `docs/` | User docs, `docs/devices/<Profile>.md` one page per device |
| `fw/` | Cache of the official Shelly packages (git-ignored, never committed) |
| `out/`, `logs/`, `devkit-configs/` | Built ZIPs, send logs, DevKit configs (git-ignored; `out/` can hold credentials) |
| `tests/` | `unittest` suite, `fixtures/` |
| `.github/` | Issue forms (`ISSUE_TEMPLATE/`), the test workflow, `labels.yml` and `sync_labels.py` |
| `CHANGELOG.md`, `ROADMAP.md`, `CREDITS.md`, `NOTICE`, `LICENSE` | Project files (Apache 2.0) |
| `_todo/` | Local notes and drafts (git-ignored, not part of the project) |

Modules in `shelly_ota/`:

| Module | Job |
| --- | --- |
| `firmware.py` | Update API, download, cache layout in `fw/shelly/<Device>/<version>/`, `meta.json` |
| `profile.py` | Reads and checks the profile YAML, the lock, the revision |
| `builder.py` | `build`: replace the app part, size and SHA-256, the manifest, the report, the bootloader swap checks |
| `bootswap.py` | Takes ESPHome's bootloader and a clean `otadata` out of a factory image; header and partition table checks |
| `compile.py` | `build --compile`: `esphome` or Docker runner, the cache volume, `packages:` resolution |
| `lint.py` | Checks an ESPHome YAML: partition table, offset, `allow_partition_access` |
| `secrets_check.py` | Looks for your credentials inside the image |
| `sender.py` | `send` / `restore`: model check, slot check, local web server, `Shelly.Update`, waits, retries |
| `rpc.py` | Shelly RPC client (HTTP, digest auth) |
| `logwatch.py`, `logview.py` | Reads the UDP debug log, shows progress; `log --replay` |
| `ble.py` | Bluetooth LE RPC (`ble` command) |
| `devicegen.py` | `add-device`: builds a profile from an official ZIP |
| `devkit.py` | Flash image of a package for a dev board |
| `buildinfo.py` | Tool version for logs and reports |
| `ui.py` | Messages, colors, prompts |

## 2. Set up

1. Python 3.10 or newer, Git, and (for compile tests and device work) the `esphome` command or Docker.
2. Clone, then:

   ```
   git clone https://github.com/oxynatOr/free-shelly-ota
   cd free-shelly-ota
   pip install -r requirements.txt
   pip install -e .[ble]        # optional: editable install with Bluetooth
   ```

3. Run `python ota.py -h`, `python ota.py profiles` and `python ota.py list`.
4. **Fill the firmware cache** for the devices you work on: `python ota.py fetch <Profile> --insecure`. The official packages are Shelly's property and are not in the
   repository; many tests need them.
5. Check your Git identity before the first commit: `git config user.name` and `git config user.email`. Use your own, or GitHub's noreply address.
6. Docker users: Docker has to be running for compile tests; the cache volume is `free-shelly-esphome-cache`.

## 3. Tests and CI

```
python -m unittest discover tests
```

- The suite runs from the repository root. `pytest` also works (`python -m pytest -q`).
- Tests that need the official ZIPs use `tests/needs_fw.py` and are skipped without `fw/shelly`. A fresh checkout and CI therefore run less than your machine does.
  Run the suite with the cache before you open a pull request.
- `tests/test_readme.py` keeps the README table and the overview in `docs/devices/README.md` in step with the profiles (counts, rows, symbols). If you add or change a
  profile, this test tells you what to update.
- The profile revision test fails if a profile changed without a higher `revision:` ([step 10](#10-change-a-profile)).
- CI (`.github/workflows/tests.yml`) runs `unittest` on Python 3.10 and 3.12 for pushes to `main` and for pull requests, without the firmware cache.
- New code needs a test. Prefer small synthetic inputs over copies of Shelly firmware.

## 4. Rules of the project

The rules are in [CONTRIBUTING.md](../CONTRIBUTING.md): evidence for every hardware claim (and *not confirmed* for unmeasured pins), no private data, no dumps, ZIPs or firmware in the repository, credits for reporters, the breaking-change statement, opt-in for risky behavior, English docs, and the rule for AI-assisted work. Read it before your first pull request. What follows is what needs project context.

- **States.** ✅ means the whole chain ran on real hardware, 🟡 flashed but part unchecked, 🔬 ran on a dev board, 🧪 builds only. Do not raise a state without a report or log that shows it. The README and the device overview must agree (`test_readme.py`).
- **Observed or assumed.** Separate what was seen ("seen on one unit") from what was read from firmware or assumed. Name the number of units.
- **Results go in their tables:** dev-board runs in `docs/devkit.md#seen-on-a-board`, field results on the device page, each with date, device or board, and what the log showed.
- **Other people's devices.** Before you build or recommend a package, compare the installed loader with the package's `boot_min_version` ([Bootloader and slots](bootloader-and-slots.md)). A package that skips the bootloader looks fine and fails later. Be stricter for devices you cannot reach.
- **Never make a refusal pass silently.** A refusal that was too strict or too loose is a bug: write a test, then fix it.

## 5. Branches, commits and pull requests

1. `main` is the release line. Work on a branch: `feature/…`, `fix/…`, `docs/…`, `device/…`, `chore/…`, `release/x.y.z`.
2. Small commits, one topic each. End the message with the attribution lines your tooling requires.
3. Update the CHANGELOG under `## [Unreleased]` (Added / Changed / Fixed, and the breaking statement).
4. Run the tests with the firmware cache.
5. Open a pull request against `main`. Describe what changed, what you tested (device, board or tests only) and the breaking/visible statement.
6. Issue labels live in `.github/labels.yml`; `python .github/sync_labels.py` prints what would change (dry run; `--apply` needs `gh auth login`; it never deletes).
7. Pushing, merging, releases, comments and issue changes are decisions of the maintainer. Ask before you do any of them on someone's behalf.

## 6. Add a new device

Goal: a profile, its partition table, a device page, a place in the lists, and an honest state. Takes minutes; the hardware test is the long part.

1. **Get the official package** of the model. Either `fetch` with a profile (if the update id is known) or download the ZIP from Shelly's update API / a device. A package
   is a ZIP with `manifest.json`, the parts (`boot`, `pt`, `app`, `fs`, ...) and their sizes and hashes.
2. **Read the manifest.** Note `app` size, the partition names (`ptn`), `boot` min version, whether `otadata` is in the package.
3. **Create the profile:**

   ```
   python ota.py add-device <official.zip>
   python ota.py add-device <variant.zip> --parent <BaseProfile>      # a variant, e.g. Zigbee
   ```

   Check the generated `devices/<Profile>.yaml` against [What a profile contains](../devices/README.md#what-a-profile-contains): `app_slot_size`, `pt_offset`, `platform`,
   `update_id`, `app_ptn`. The profile starts at `revision: 1`.
4. **Check the bootloader value.** Set `boot_min_version: "1.0.9"` unless a report shows the device needs another value. Reason: devices that already run loader 1.0.3
   would otherwise skip the new bootloader ([min_version](bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)).
5. **Write the partition CSV:** `python ota.py partition-csv <Profile> -o partitions/<Profile>-stock.csv`. Check that the offset of the table matches `pt_offset` and that the app slot size
   equals `app_slot_size`.
6. **Run `python ota.py profiles --update-lock`** and commit `devices/profiles.lock` with the profile.
7. **Build a test package** with a minimal ESPHome config (copy the structure of a similar device page) and run `inspect --device`. It must verify.
8. **Write the device page** `docs/devices/<Profile>.md`. Copy a similar page (for example `PlugMG3.md`) and keep its sections: facts table, state badges, *Before you start*,
   *ESPHome config*, *Pins*, *Flash it*, *What to expect*, *Way back*, the warning block. Mark the state 🧪 and every unmeasured pin "not confirmed". Do not copy log lines from
   another device.
9. **Add the device to the lists:**
   - the overview table in `docs/devices/README.md` (profile, chip, table offset, slot size, state, note),
   - `devices/README.md` (profile table),
   - the README only when the state is ✅ or 🟡, and the count line,
   - `.github/ISSUE_TEMPLATE/device-report.yml` (device list),
   - `docs/devkit.md` (board table) and `docs/commands.md` only if they list profiles by name,
   - `CHANGELOG.md` (Added, with the requester's thanks and the breaking statement: a new profile is not breaking),
   - `CREDITS.md` if someone asked for it.
10. **Run the tests.** `test_readme.py` names what is still out of step.
11. **Offer a devkit run** (step 8) if a suitable board exists.
12. **Open the pull request.** In the description: source package version and its date, the checks done, what is untested.

A variant (Zigbee, beta layout) uses `--parent` or a separate profile with its own CSV; it appears as its own row. For a beta layout, see `PlugMG3-beta` and the
[Beta firmware](bootloader-and-slots.md#beta-firmware-with-another-flash-layout) section; `build` and `send` refuse a package or a device that does not fit a profile's layout.

## 7. Find out what a device does

Profiles hold no pins. Pins come from three sources, in order of trust: a measurement on the board, a flash dump read with the stock firmware's strings, a dump analysis.

1. **Dump the stock flash over UART** (the device off mains): `esptool read-flash 0x0 <size> dump.bin`, then check flash encryption and secure boot with `espefuse summary`
   ([Recovery over UART](recovery-uart.md)). The dump holds device secrets: keep it local.
2. **Find the layout** with the `analyze-shelly-dump` skill in the project folder (`parse_partitions.py`): partition table, offset, flash size, chip hints, firmware version.
3. **Read the stock app** for pin names, drivers (BL0942, relay, LED, NTC, button) and calibration. Decompiling is covered by the `reverse-engineering` skill; write down the
   source of every finding.
4. **Verify on hardware** with a small ESPHome config that only switches a pin or reads a sensor. A pin is "confirmed" only when seen working on a real unit.
5. **Put the results on the device page** with their source. Longer write-ups (stock behavior, a bootloader analysis) belong in the notes area, not in the user docs.
6. **If a datasheet or stock behavior surprised you** (for example the BL0942 RX pull-up on the PM Mini, the multiplexed CF/ZX pin, active-low RGB LED), note it on the page; others
   will hit it.

## 8. The test ladder

Each rung proves more and costs more. State the rung in the PR and on the device page.

| Rung | What you do | What it proves | State |
| --- | --- | --- | --- |
| 1 | `build` + `inspect --device` | The package is well formed and fits | 🧪 |
| 2 | [DevKit](devkit.md): `ota.py devkit <Profile>`, flash a spare board, `send` | The installer, the bootloader swap, the slot logic and the log run | 🔬 |
| 3 | Real device over OTA | The chain works on the hardware | 🟡 |
| 4 | Real device: relay, meter, button, LED, a second OTA | The device really works | ✅ |

DevKit rules:

- Use a spare board that matches the chip and flash size (see the table in [devkit.md](devkit.md#which-board)). Never a device.
- `python -m esptool --port COMx flash-id` first; `espefuse summary` before and after the first update (the updater may burn BLOCK3).
- Take the log from `send --log-file`; the first run needs `restore` if the target slot is 1.
- Add a row to [Seen on a board](devkit.md#seen-on-a-board) with date, board, profile and what the serial monitor and `send --watch` showed. Then set the profile to 🔬.
- The board has no relay, meter or button; do not report those as checked.

## 9. Handle a device report

1. **Read the whole form and the log.** Check `ota.py --version` of the report, the profile revision, the stock version, and the installed loader (`Boot: cur ...`).
2. **Classify** what happened: ran through / refused by a tool check / device did not download / wrong slot / bootloader skipped (`update? 0`) / silent after the update / hardware quirk.
3. **Compare with the device page** and with similar reports. Look for the known causes first: slot not 0, `min_version`, power cycle, layout, signal strength, VLAN.
4. **Reproduce** on a DevKit board when you can (the same stock version as the report: `devkit --zip` or `--version`).
5. **Update the docs:**
   - state symbol and the *Note* column (README and `docs/devices/README.md`),
   - the device page: what the reporter saw, versions, loader, quirks,
   - the CHANGELOG (`Changed`), **with the reporter's name and issue link** and the "not breaking" reason for a docs-only change,
   - `CREDITS.md`.
6. **Answer** in the issue in the reporter's language when you can, in plain words, with the next step. Ask for a log if missing (clean of passwords, keys and MACs). Do not post
   from someone else's account or change issues without the maintainer's go-ahead.
7. **If the tool was wrong,** write a failing test first, then fix. A refusal that was too strict or too loose is a bug of the tool.

## 10. Change a profile

1. Edit `devices/<Profile>.yaml`.
2. Raise `revision:` by one.
3. `python ota.py profiles --update-lock`.
4. Update `partitions/<Profile>-stock.csv` if the layout changed (`partition-csv`), and the device page.
5. CHANGELOG: this is visible (the build report shows the new revision). Say if it is breaking: a changed `boot_min_version` or `app_slot_size` can make `build` refuse an old command.
6. Run the tests; the revision test fails if you skip step 2 or 3.

## 11. Change the tool

1. Find the module in the table above. The command line lives in `ota.py`, the behavior in `shelly_ota/`.
2. **Write the test first** in `tests/test_<topic>.py`. Use fixtures in `tests/fixtures/`, no real firmware.
3. Keep refusals specific: say what is wrong, the values, and a `Fix:` line. See the messages in `builder.py` and `bootswap.py`.
4. New options: add them to the argument group in `ota.py`, to `python ota.py <command> -h`, to [Commands](commands.md) (table, default, description), and to the CHANGELOG.
   `tests/test_help.py` checks that the help text is in order.
5. New behavior that risks a device is **opt-in**.
6. Messages use the helpers in `ui.py` (`WARNING:`, `NOTE:`, `Error:`, `OK:` stay in the text so logs read the same).
7. Update the docs that mention the behavior: the device pages, [Troubleshooting](troubleshooting.md), [Bootloader and slots](bootloader-and-slots.md).
8. Do not commit anything from `fw/`, `out/` or `logs/`.
9. Run `python -m unittest discover tests` with and without `fw/` populated.

Where the real tool behavior is subtle, read these before changing it: the `send` flow in `sender.py` (model check → slot check → reachability → update → watch), the bootloader
swap in `bootswap.py`, and the reasons in [Bootloader and slots](bootloader-and-slots.md).

## 12. Release

Semantic Versioning; 0.x is experimental. The version is `__version__` in `shelly_ota/__init__.py`; `python ota.py --version` prints it with the git state.

1. Create `release/x.y.z` from `main`.
2. Move `[Unreleased]` in `CHANGELOG.md` to `## [x.y.z] - YYYY-MM-DD` and add a **Summary** with the breaking and visible changes, even when there are none. Update the counts
   in the README (`N profiles: ✅ … 🟡 … 🔬 … 🧪 …`) and `ROADMAP.md` state line.
3. Raise `__version__`.
4. Run the whole suite with the firmware cache, then `python ota.py profiles` (the lock must be clean).
5. Update `docs/versions.md` only if the version format changed.
6. Open the pull request; the maintainer merges it.
7. The maintainer tags `vx.y.z` and creates the GitHub release with the CHANGELOG entry. Do not tag, push or release on your own.
8. Announcement drafts (forum, Reddit, Discord) are written separately in the notes area and posted by the maintainer.
9. After the release: delete merged branches only when the maintainer says so.

## 13. Related repositories and tools

- **`oxynatOr/esphome-configs`**: ready-made ESPHome configs for devices (strips, bulbs, plugs), built to work with this tool. It has its own rules and checks; configs for
  a device belong there, not in the docs here.
- **`oxynatOr/esphome-kp18058`**: the KP18058 light component used by the Multicolor Bulb.
- **ESPHome devices database (devices.esphome.io)**: device pages for the community. Pages drafted for the Plug M, Plug PM and a Plug S correction are kept as drafts; they
  have not been submitted.
- **Tasmota's `mgos32-to-tasmota32`** and the **Plug US** and **Gen4** projects: the work this tool builds on; see [Credits](../README.md#credits).
- **Skills in the project folder**: `analyze-shelly-dump` (partition table and layout from a dump) and the reverse-engineering skill (for stock firmware and loader analysis).

## Checklists

**New device (PR)**

- [ ] Profile from the official package, `revision: 1`, `boot_min_version` decided
- [ ] `partitions/<Profile>-stock.csv`, offset and slot size match
- [ ] `profiles.lock` updated
- [ ] Test package builds, `inspect --device` clean
- [ ] Device page with 🧪, pins "not confirmed" unless measured
- [ ] Lists updated (devices overview, profile table, issue form, README if ✅/🟡, devkit table)
- [ ] CHANGELOG entry with the breaking statement and thanks
- [ ] Tests pass with the firmware cache; no secrets, dumps or ZIPs in the diff

**Report handled**

- [ ] State, note and counts updated in README and overview
- [ ] Device page, CHANGELOG and `CREDITS.md` name the reporter
- [ ] Reply drafted; no personal data in anything public
- [ ] Tool bug? A test first

**Release**

- [ ] CHANGELOG with the Summary and breaking/visible statement
- [ ] Version, README counts and ROADMAP date set
- [ ] Suite green with the cache; lock clean
- [ ] PR open; tag and release left to the maintainer

---

> [!TIP]
> **Not sure where something belongs?** Open an issue or ask in the pull request. Small fixes to the docs are always welcome.

[User guide](guide.md) · [Device profiles](../devices/README.md) · [Test on a dev board](devkit.md) · [Versions](versions.md)
