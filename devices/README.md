# Device profiles

[← README](../README.md) · [Device pages](../docs/devices/README.md) · [Commands](../docs/commands.md) · [Versions](../docs/versions.md)

[📋 Profiles](#profiles) · [🧾 What a profile contains](#what-a-profile-contains) · [✏️ Changing a profile](#changing-a-profile) · [➕ Adding a profile](#adding-a-profile)

One small YAML file per device. A profile holds what the tool needs to turn an official Shelly package into yours: no pins and
no partition layout. Those are on the [device pages](../docs/devices/README.md) and in [`partitions/`](../partitions).
The file name without `.yaml` is the profile name you give to `fetch`, `build`, `send` and `restore`.

## Profiles

| Profile | Device | Chip | Revision | Device page |
| --- | --- | --- | --- | --- |
| `PlugMG3` | Shelly Plug M Gen3 | ESP32-C3 | 2 | [PlugMG3](../docs/devices/PlugMG3.md) |
| `PlugAZ` | Shelly AZ Plug | ESP32-C3 | 1 | [PlugAZ](../docs/devices/PlugAZ.md) |
| `PlugSG3` | Shelly Plug S Gen3 | ESP32-C3 | 2 | [PlugSG3](../docs/devices/PlugSG3.md) |
| `PlugPMG3` | Shelly Plug PM Gen3 | ESP32-C3 | 2 | [PlugPMG3](../docs/devices/PlugPMG3.md) |
| `HTG3` | Shelly H&T Gen3 | ESP32-C3 | 2 | [HTG3](../docs/devices/HTG3.md) |
| `RGBCCTBulbG3` | Shelly Multicolor Bulb E27 Gen3 | ESP32-C3 | 2 | [RGBCCTBulbG3](../docs/devices/RGBCCTBulbG3.md) |
| `DuoBulbG3` | Shelly Duo Bulb Gen3 | ESP32-C3 | 2 | [DuoBulbG3](../docs/devices/DuoBulbG3.md) |
| `PowerStrip` | Shelly Power Strip 4 Gen4 | ESP32-C6 | 2 | [PowerStrip](../docs/devices/PowerStrip.md) |
| `PowerStripZB` | Shelly Power Strip 4 Gen4 (Zigbee) | ESP32-C6 | 2 | [PowerStripZB](../docs/devices/PowerStripZB.md) |
| `PlusPlugS` | Shelly Plus Plug S | ESP32 | 2 | [PlusPlugS](../docs/devices/PlusPlugS.md) |
| `PlusPlugIT` | Shelly Plus Plug IT | ESP32 | 1 | [PlusPlugIT](../docs/devices/PlusPlugIT.md) |
| `Pill` | Shelly The Pill | ESP32-C3 | 2 | [Pill](../docs/devices/Pill.md) |
| `Mini1G3` | Shelly Mini 1 Gen3 | ESP32-C3 | 1 | [Mini1G3](../docs/devices/Mini1G3.md) |
| `Mini1PMG3` | Shelly Mini 1PM Gen3 | ESP32-C3 | 1 | [Mini1PMG3](../docs/devices/Mini1PMG3.md) |
| `MiniPMG3` | Shelly PM Mini Gen3 | ESP32-C3 | 1 | [MiniPMG3](../docs/devices/MiniPMG3.md) |
| `Mini1PMG4` | Shelly Mini 1PM Gen4 | ESP32-C6 | 2 | [Mini1PMG4](../docs/devices/Mini1PMG4.md) |
| `Mini1PMG4ZB` | Shelly Mini 1PM Gen4 (Zigbee) | ESP32-C6 | 2 | [Mini1PMG4](../docs/devices/Mini1PMG4.md#zigbee-variant) |
| `PlusUni` | Shelly Plus Uni | ESP32 | 1 | [PlusUni](../docs/devices/PlusUni.md) |
| `Pro3EM` | Shelly Pro 3EM | ESP32 | 1 | [Pro3EM](../docs/devices/Pro3EM.md) |

`python ota.py profiles` prints the same list with the revision and a content hash, `python ota.py list` also shows which
official firmware is cached.

## What a profile contains

```yaml
# OTA profile for HTG3, generated from the official 2.0.1 package.
display_name: "Shelly H&T Gen3"
platform: esp32c3
update_id: HTG3
app_ptn: app_0
app_slot_size: 0x280000
pt_offset: 0xf000
boot_min_version: "1.0.9"
revision: 2
```

| Key | Required | Default | What it does |
| --- | --- | --- | --- |
| `app_slot_size` | yes | | Size of the app slot the package's `app` part is written to. `build` checks that the image fits; with `--esphome-yaml` it also checks that the `partitions:` CSV of your config has the same size |
| `display_name` | no | file name | Name of the device as people know it |
| `platform` | no | `esp32c3` | Chip: `esp32`, `esp32c3` or `esp32c6`. `build` checks the chip id of your image against it |
| `update_id` | no | file name | Name in Shelly's update API, `https://updates.shelly.cloud/update/<update_id>`, where `fetch` finds the official package |
| `app_ptn` | no | `app_0` | Partition the `app` part of the package targets. `build` warns if the official package says otherwise |
| `parent` | no | none | Base device of a variant (for example the Zigbee firmware). The variant is listed under `alt` in the update reply of the parent |
| `pt_offset` | no | `0x10000` | Where the device keeps its partition table. Your ESPHome config must set `CONFIG_PARTITION_TABLE_OFFSET` to it (`build --esphome-yaml` checks); it is `0xf000` on `HTG3`, `Mini1PMG3` and `MiniPMG3`, `0x8000` on `PlusPlugS` |
| `boot_min_version` | no | none | Default for `--boot-min-version` when you ship ESPHome's bootloader. Without it the tool uses one patch above Shelly's loader version. See [Bootloader and slots](../docs/bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version) |
| `revision` | no | `1` | Counts the changes of the profile, see below |

## Changing a profile

Every profile has a `revision:`. When you change anything else in the file:

1. Raise `revision:` by one.
2. Run `python ota.py profiles --update-lock`.

> [!IMPORTANT]
> The test suite fails if a profile changed without a higher revision.

[`profiles.lock`](profiles.lock) stores the revision and a content hash of each profile (the `revision:` line is not part of
the hash). `python ota.py profiles` checks the lock. `build` writes the revision into the report next to the package, and `send`
prints it. More in [Versions](../docs/versions.md).

## Adding a profile

1. Create it from the official package: `python ota.py add-device <official.zip>` (`--parent <base device>` for a variant).
   The new profile starts at `revision: 1`.
2. Write the stock partition table for ESPHome: `python ota.py partition-csv <Profile> -o partitions/<Profile>-stock.csv`.
3. Run `python ota.py profiles --update-lock`.

> [!NOTE]
> To list the device publicly, also add a page under [`docs/devices/`](../docs/devices/README.md), a row to the table in the
> README and an entry to the device list in `.github/ISSUE_TEMPLATE/device-report.yml`.

---

> [!TIP]
> **No profile of your own?** [Request the device](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=new-device.yml); it helps most if you offer to test it.

[`add-device`](../docs/commands.md#add-device) · [`partition-csv`](../docs/commands.md#partition-csv) · [Bootloader and slots](../docs/bootloader-and-slots.md)
