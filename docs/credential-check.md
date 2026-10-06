# Credential check

[Back to the README](../README.md)

An ESPHome image stores Wi-Fi SSID/password, API keys and similar values **in plain text**, and so does every package built
from it.

`build` therefore compares the image (and the `--esphome-factory` image) with the values from your ESPHome config and its
`secrets.yaml`: `wifi.ssid`, `wifi.password`, `wifi.ap.password`, `api.encryption.key`, `api.password`, `ota[].password`,
`web_server.auth.password`, `mqtt.password` and every other value in `secrets.yaml`.

- On a hit it prints a warning with the **names** of the matches (never the values), writes them to `<zip>.report.json` as
  `contains_secrets`, and `send`/`inspect` warn again.
- `--fail-on-secrets` turns the warning into an error.
- Without `--esphome-yaml` or `--secrets` nothing can be compared; the build says so.
- `build` also warns if the output file lies in a git work tree where it is not ignored.

> [!CAUTION]
> Never share, upload or commit such a ZIP. A package for others should come from a config without credentials (for example a
> Wi-Fi setup config).
