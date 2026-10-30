# Documentation

[← README](../README.md) · [CHANGELOG](../CHANGELOG.md) · [Roadmap](../ROADMAP.md) · [Credits](../CREDITS.md)

[🚀 Where to start](#where-to-start) · [📚 Pages](#pages) · [🩺 Something went wrong](#something-went-wrong) · [🗂️ Outside this folder](#outside-this-folder)

How to get your own ESPHome firmware onto a Shelly with `ota.py`, why the tool does what it does, and what to do when it does
not work. The README has the short version; these pages have the details.

## Where to start

0. **New here?** Read the [Step-by-step guide](guide.md).
1. **Find your device** on the [device pages](devices/README.md): the ESPHome config it needs, the exact commands and the log
   lines to look for.
2. **Run the three steps** `fetch`, `build`, `send` ([Commands](commands.md)).
3. **If something stops or looks wrong,** look it up below or in [Troubleshooting](troubleshooting.md).
4. **Before you share a package,** read the [Credential check](credential-check.md): it can contain your Wi-Fi password.

## Pages

| Page | What is in it |
| --- | --- |
| [Step-by-step guide](guide.md) | The whole way for a user: check, prepare, config, build, send, afterwards, way back |
| [Developer guide](guide-developers.md) | Adding devices, testing, reports, profiles, tool changes, release |
| [Device pages](devices/README.md) | One page per device: config, pins, commands, log lines, pitfalls |
| [Commands](commands.md) | `fetch`, `build`, `send`, `restore`, `ble`, `log` and the rest, with all options |
| [Bootloader and slots](bootloader-and-slots.md) | Why ESPHome's bootloader is shipped, `min_version`, why the app must land in slot 0 |
| [Troubleshooting](troubleshooting.md) | Header errors, empty log, battery devices, eFuse, power cycle |
| [Recovery over UART](recovery-uart.md) | Back to Shelly OS with `esptool` |
| [Test on a dev board](devkit.md) | A flash image of a package for a board: play the whole update through, for any device |
| [Credential check](credential-check.md) | Secrets inside images and packages |
| [Versions](versions.md) | Tool version, build report, profile revisions |

## Something went wrong

> [!TIP]
> Always run `send` with `--watch`: the log answers most questions.

| What you see | Where to look |
| --- | --- |
| `send` refuses: update target slot is not 0 | [Troubleshooting](troubleshooting.md#send-refuses-update-target-slot-is-not-0), [The app must land in slot 0](bootloader-and-slots.md#the-app-must-land-in-slot-0) |
| `send` warns: "this firmware does not reveal the update target slot" | [Troubleshooting](troubleshooting.md#send-warns-this-firmware-does-not-reveal-the-update-target-slot) |
| `send` cannot reach the device: no Wi-Fi, no access point (Zigbee firmware) | [Troubleshooting](troubleshooting.md#the-device-has-no-wi-fi-and-opens-no-access-point), [`ble`](commands.md#ble) |
| `build` stops with "differs from Shelly's in ..." | [Build refuses to replace the bootloader](troubleshooting.md#build-refuses-to-replace-the-bootloader) |
| No progress or confirmation from the device log | [No progress, no device log](troubleshooting.md#no-progress-no-device-log) |
| H&T Gen3: HTTP 500, "Battery below 30 percent" | [Battery devices](troubleshooting.md#battery-devices-ht-gen3) |
| ESPHome does not start after the update | [ESPHome does not start after the update](troubleshooting.md#esphome-does-not-start-after-the-update) |
| ESPHome OTAs "work", but the version does not change | [Troubleshooting](troubleshooting.md#esphome-otas-work-but-the-version-does-not-change), [`min_version`](bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version) |
| `build` warns about credentials in the image | [Credential check](credential-check.md) |
| You want Shelly OS back and Shelly firmware still runs | [`restore`](commands.md#restore) |
| You want Shelly OS back and the device runs ESPHome | [Recovery over UART](recovery-uart.md) |
| A log or package needs to say which tool state made it | [Versions](versions.md) |

## Outside this folder

| Where | What is in it |
| --- | --- |
| [`devices/`](../devices/README.md) | The device profiles (one YAML each) and `profiles.lock` |
| [`partitions/`](../partitions) | Stock partition tables as ESPHome `partitions:` CSV, one per profile |
| [CHANGELOG](../CHANGELOG.md) | What changed |
| [Roadmap](../ROADMAP.md) | What is planned, and where testers can help |
| [Credits](../CREDITS.md) | Whose work this tool builds on, and who tested it |
| [Contributing](../CONTRIBUTING.md) | How to help: reports, rules, AI-assisted work, pull requests |
