# Special cases

[← README](../README.md) · [Documentation](README.md) · [Step-by-step guide](guide.md) · [Device pages](devices/README.md) · [Commands](commands.md) · [Troubleshooting](troubleshooting.md)

Situations the [Step-by-step guide](guide.md) does not cover in its main path.

## A device without a profile

A profile is made from the official package and takes minutes. [Request it](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=new-device.yml) (offer to test it),
or make it yourself with `python ota.py add-device <official.zip>` and follow [Device profiles](../devices/README.md#adding-a-profile) and the [Developer guide](guide-developers.md#6-add-a-new-device).
Nobody can say it works until someone flashed one; treat it as 🧪.

## A device with no Wi-Fi (Zigbee firmware)

Some Zigbee firmware has no network and opens no access point. Give it a Wi-Fi over Bluetooth, then use the printed address:

```
pip install bleak
python ota.py ble scan
python ota.py ble wifi MyNetwork -
python ota.py send <Profile> out/<file>.zip --ip <printed address> --dry-run
```

`-` asks for the password without echoing. Seen on a dev board only, not yet on a real device ([`ble`](commands.md#ble)).

## Battery device (H&T Gen3)

Charge or replace the battery (30 % or more) and keep the device awake. The stock updater answers `Battery below 30 percent` otherwise, and `send` does not retry.
The official H&T package may not be listed for current firmware; use `fetch HTG3 --from-version 1.4.4` ([`fetch`](commands.md#fetch)). Its page: [HTG3](devices/HTG3.md).

## Classic ESP32 (Gen2) and ESP32-C6 (Gen4)

The steps are the same; the differences are in the profile: partition table at `0x8000` for Gen2, an 8 MB layout on Gen4. The bootloader header must match Shelly's
(flash frequency 80 MHz on classic ESP32 and C6, see the [fix table](troubleshooting.md#build-refuses-to-replace-the-bootloader)). Gen4 packages may be verified with a signature on some firmware; if the
device rejects the package, check the log and use UART ([disputed](background.md#gen4-signature-check-disputed)).

## Beta firmware

Do not send a package of the wrong layout. Check [Beta firmware with another flash layout](bootloader-and-slots.md#beta-firmware-with-another-flash-layout). Shelly can pull a beta, so cache the package with `fetch` before you need it.

## Devices that measure only

The Plug PM Gen3 and PM Mini Gen3 have no relay. A config for them must not have one.

## Settings you want to keep

The package wipes NVS. `--drop nvs` leaves it out of the package, but it is **untested on devices**; only use it if you know why.

## Password on the Shelly

`--user admin --password '<pw>'` for `send`, `restore` and `log`. A password on the command line stays in the shell history.

## Several devices

Repeat steps 5 to 9 per device, with its own profile, its own CSV and its own YAML. A package built for one model is refused by another.
