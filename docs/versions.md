# Versions

[Back to the README](../README.md)

Everything that can end up in a log, a package or a bug report says which state of the tool made it. The version numbers follow
[Semantic Versioning](https://semver.org); while the version is 0.x the tool is experimental and minor releases may change
behaviour. Changes are listed in the [CHANGELOG](../CHANGELOG.md).

- **The tool.** `python ota.py --version` prints for example `0.2.0 (feature/x, v0.2.0-4-gb225e1f-dirty, 2026-10-06)`: the
  version, in a git checkout also the branch, `git describe` (last tag, commits since it, commit, `-dirty` = uncommitted
  changes) and the commit date. Outside a git checkout it is just the version number. Every command starts with a line
  `free-shelly-ota <that>`, so a pasted log shows which state produced it (`partition-csv` without `-o` leaves it out, its
  output is data).
- **The package.** `build` writes `<zip>.report.json` with the same tool information, the profile name and revision, the
  options used (ESPHome bootloader or not, resulting `boot_min_version`, dropped parts, tag; flags only, no paths) and the
  build time. `send` reads it and prints `Package: built ... by free-shelly-ota ..., profile ... revision N`, and a note if the
  profile has changed since.
- **The profiles.** Each `devices/<Device>.yaml` has a `revision:` that counts its changes. Raise it whenever you change anything
  else in the file, then run `python ota.py profiles --update-lock`; `devices/profiles.lock` stores revision and content hash,
  and the test suite fails if a profile changed without a higher revision. `python ota.py profiles` lists them and checks the
  lock; `list` shows the revision too.
