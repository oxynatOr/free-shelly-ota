# Shelly PM Mini Gen3

[← README](../../README.md) · [All devices](README.md) · [Commands](../commands.md)

![State: confirmed](https://img.shields.io/badge/state-confirmed-brightgreen.svg?style=flat-square)
![Generation: 3](https://img.shields.io/badge/gen-3-lightgrey.svg?style=flat-square)
![Chip: ESP32-C3](https://img.shields.io/badge/chip-ESP32--C3-blue.svg?style=flat-square)
![Relay: none](https://img.shields.io/badge/relay-none-lightgrey.svg?style=flat-square)

[🧰 Before you start](#before-you-start) · [⚙️ Config](#esphome-config) · [📍 Pins](#pins) · [⚡ Flash it](#flash-it) · [👀 What to expect](#what-to-expect) · [↩️ Way back](#way-back)

The first device that was flashed and reported by someone else: thanks to [imsandli](https://github.com/imsandli) for the device report (October 2026) and the notes on this page. This device **only measures**: there is no relay in it. Do not confuse it with the [Mini 1PM Gen3](Mini1PMG3.md), which has one and is a different application in Shelly's update API (`Mini1PMG3`).

| Fact | Value |
| --- | --- |
| Profile | `MiniPMG3` |
| Model | S3PM-001PCEU16 (device id `shellypmminig3-...`) |
| Flash | 8 MB |
| Official package | 2.1.0 (the reported flash started from stock 2.0.1, see the notes) |
| Partition table | **`0xf000`** (not `0x10000`) |
| App slot size | `0x280000` |
| Bootloader `min_version` | `1.0.9` (set in the profile) |
| ESPHome device page | [Shelly PM Mini Gen3](https://devices.esphome.io/devices/shelly-pm-mini-gen3/) |

> [!NOTE]
> **Confirmed:** the whole chain ran on a real device: `send` from stock 2.0.1 with `--esphome-factory`; ESPHome boots, six and more ESPHome OTAs took effect, BLE, Wi-Fi and the power meter work.

## Before you start

Check first:

- [ ] the device runs Shelly's own firmware, not ESPHome yet, and it is **1.3.3 or newer** (better 2.x): `send` refuses older ones ([why](#notes-for-this-device))
- [ ] you know its IP address (`--ip`), or this PC is on the device's own access point (default `192.168.33.1`)
- [ ] the device can reach this PC: same network, port 8000 (`--port`) not blocked
- [ ] your ESPHome config uses the partition table below and is compiled
- [ ] a UART adapter is at hand as your way back ([Recovery over UART](../recovery-uart.md))

Also:

- [ ] The device is a PM Mini Gen3 (`MiniPMG3`, S3PM-001PCEU16), not the Mini 1PM Gen3 (that one has a relay).

## ESPHome config

> [!IMPORTANT]
> `build` refuses a config without Shelly's partition table. Copy `partitions/MiniPMG3-stock.csv` from this repository next to your
> YAML and keep `CONFIG_PARTITION_TABLE_OFFSET: "0xf000"`.

```yaml
esp32:
  variant: ESP32C3
  board: esp32-c3-devkitm-1
  flash_size: 8MB
  flash_mode: dio
  partitions: MiniPMG3-stock.csv        # copy from partitions/ in this repository
  framework:
    type: esp-idf
    sdkconfig_options:
      CONFIG_PARTITION_TABLE_OFFSET: "0xf000"
    advanced:
      enable_ota_rollback: false

ota:
  - platform: esphome
    allow_partition_access: true
```

The `esp32:` block is the tester's working one (the report did not include the `ota:` block, this is the usual one). Like the [H&T Gen3](HTG3.md), the device keeps its partition table at `0xf000`, so a default ESPHome build does not match and `build` refuses it.

> [!TIP]
> The [ESPHome device page](https://devices.esphome.io/devices/shelly-pm-mini-gen3/) has the pins and an example config. Replace its `esp32:` block with the one above, or `build` refuses it.

## Pins

From the running ESPHome config of the report:

| Function | Pin |
| --- | --- |
| BL0942 power meter (UART, 9600 baud, 8N1) | ESP **TX GPIO6**, ESP **RX GPIO7** |
| Relay | none |

```yaml
uart:
  tx_pin: GPIO6
  rx_pin:
    number: GPIO7
    mode:
      input: true
      pullup: true
  baud_rate: 9600
  stop_bits: 1
```

- **The RX pin needs the internal pull-up.** Without it every 23-byte reply of the BL0942 arrives with stray bytes around it (`00` before the `55` header, `00:FE:00:FE` after the checksum), so every checksum fails and
  all values stay `nan`. With the pull-up the packets are clean.
- **Voltage calibration:** with ESPHome's default `voltage_reference` (15883) the voltage reads about 10 % low. `voltage_reference: 14357` was correct against the electricity meter on this one unit; the stock firmware
  read about 2 % low. Compare with a reference on your unit.
- Button and LED pins were not read.

## Flash it

1. **Install the requirements** (once):

   ```
   pip install -r requirements.txt
   ```

2. **Fetch** the official package:

   ```
   python ota.py fetch MiniPMG3 --insecure
   ```

3. **Build:** put your app into it; the ZIP goes to `out/`:

   ```
   python ota.py build MiniPMG3 app.ota.bin --esphome-factory app.factory.bin --esphome-yaml app.yaml
   ```

4. **Check the device** first. Nothing is sent:

   ```
   python ota.py send MiniPMG3 out/MiniPMG3-app-<date>.zip --ip <device IP> --dry-run
   ```

5. **Flash it** (the log goes to a file with `--log-file`):

   ```
   python ota.py send MiniPMG3 out/MiniPMG3-app-<date>.zip --ip <device IP> --log-file
   ```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

`send` shows these lines at the default log level, in this order:

| # | Log line | Meaning |
| --- | --- | --- |
| 1 | `Update target slot: 0 ...` | The slot check of `send`. Anything else: run `python ota.py restore MiniPMG3` first |
| 2 | `Device: The bootloader will be replaced ...` (raw log: `Boot: cur ... min ... update? 1`) | The installer will write ESPHome's bootloader. `WARNING: ESPHome's bootloader was NOT written` (`update? 0`) means it will not: build again with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)) |
| 3 | The progress (`Update: ... %`, one line that updates in place) up to 100 %, then `Done: update installed, the device confirmed it` | The device restarts into ESPHome |

The reported run, from stock 2.0.1 (the first line comes from `send`, the rest from the device):

```
Update target slot: 0 (the slot ESPHome's bootloader starts).
  log| shelly_update.cpp:511   Incoming fw signatures: 00
  log| 2xx_ota_backend.cpp:409 Will write to slot 0
  log| 2xx_ota_backend.cpp:689 Boot: cur 010002ff, new 00000000, min 010009ff, update? 1
  log| 2xx_ota_backend.cpp:171 Installing BL 20960@app_0(0x20000) -> boot(0)...
  log| shelly_update.cpp:631   EFUSE write error bit[1]: 5636
  log| shos_system.c:66        Rebooting in 1000 ms
```

The `EFUSE write error` line also appeared on the [H&T Gen3](HTG3.md); the update still succeeded ([eFuse note](../troubleshooting.md#efuse)).

## Notes for this device

- **Old stock firmware (1.1.x to 1.3.2):** `send` refuses the package. One unit on stock **1.1.99** (loader `00040405`) accepted the ESPHome package without an error and then stayed silent, also after a power cycle, until it was flashed over UART/USB ([#113](https://github.com/oxynatOr/free-shelly-ota/issues/113), thanks to [aanban](https://github.com/aanban)). Its log lacks the lines `BS is being moved`, `PT is being moved` and `Installing BL`, which the updater of 1.3.3 prints on a dev board; so the old updater most likely changes neither the layout nor the bootloader. This is inferred from the log: the 1.1.99 package is not available (Shelly's update API names 1.3.3 as the next step for it). Update such a device with Shelly's own update first (the web interface or app), then send.
- **Stock 1.3.3 on a dev board:** the updater moves the partition table (`0x8000` to `0xf000`) and boot state (`0x10000` to `0x11000`) and replaces the bootloader, but it does not name its update target slot beforehand, so `send` cannot check it. In the test it wrote to slot 1 and the old firmware came back; `restore` first (see the Slot note below) is the way: on a dev board, `restore` put 2.1.1 in slot 1 and replaced the bootloader (`010000ff` to `010003ff`), the next `send --dry-run` named slot 0, and `send` then worked (ESPHome's access point appeared).
- The installed loader was 1.0.2, which is why the profile sets `boot_min_version: 1.0.9`: a lower value would have been skipped by the installer.
- **Slot:** the first `send --dry-run` refused because the installer would have written to slot 1. `python ota.py restore MiniPMG3` fixed that (the device then ran from slot 1, and the next dry run reported slot 0). The restore kept
  Wi-Fi and settings on this unit (2.0.1 to 2.0.1).
- **Network:** the tester's Shelly sat in an IoT VLAN that could reach nothing on the PC's network, while the PC could reach the Shelly. The device's own RPC finds this before anything is sent:
  `http://<Shelly IP>/rpc/HTTP.GET?url="http://<PC IP>:8000/"` answered `Connection error: -13`. Any HTTP status in the answer (a 404 is fine) means the way is open.
- **Package versions:** the profile and `MiniPMG3-stock.csv` were made from the 2.1.0 package; the flash on the tester's unit was done with the 2.0.1 table. The two tables were not compared.
- Check the app name (`MiniPMG3`) and the model (S3PM-001PCEU16) before you use this page. The Mini 1PM Gen3 (`Mini1PMG3`) has a relay, another partition layout (app slot `0x2a0000`) and was not tested.

## Way back

`python ota.py restore MiniPMG3` sends the official firmware back while Shelly firmware still runs.

---

> [!WARNING]
> - **Wipes Wi-Fi and settings.** ESPHome opens its own access point or joins the Wi-Fi from your config; if nothing comes up, power-cycle the device ([help](../troubleshooting.md#esphome-does-not-start-after-the-update)).
> - **No way back over the network** once ESPHome's bootloader runs: `restore` gets no answer, only UART brings Shelly OS back ([Recovery over UART](../recovery-uart.md)). Take a flash backup first if you can.
> - **Flashed it? Tell us,** also when it worked: [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).

[Bootloader and slots](../bootloader-and-slots.md) · [Troubleshooting](../troubleshooting.md) · [Recovery over UART](../recovery-uart.md)
