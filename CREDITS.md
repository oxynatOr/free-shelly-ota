# Credits

[← README](README.md#credits) · [Documentation](docs/README.md) · [Device pages](docs/devices/README.md) · [Roadmap](ROADMAP.md)

[🙌 People](#people) · [🧩 Projects](#projects) · [🧱 Third parties](#third-parties) · [❓ Missing from this list?](#missing-from-this-list)

This tool builds on the research of other projects, and much of what it knows about single devices comes from the people who tested them. The rest was worked out here and on real devices: the loader's boot state, the slot rule, `min_version`, the pin tables, the DevKit. This page says who contributed what. The short version is in the [README](README.md#credits).

## People

People are listed once, in the highest of these groups they reached. Newest first inside a group. The device page links the details of each report.

<table width="100%">
<thead><tr><th align="left" width="150">Group</th><th align="left">Who is in it</th></tr></thead>
<tbody>
<tr><td><b>🛠 Contributors</b></td><td>Something from them went into the tool or the docs: a check, a fix, an idea, a finding</td></tr>
<tr><td><b>🔬 Testers</b></td><td>They checked more than that it worked: pins, calibration, later OTAs, several devices, a diagnosis on the hardware</td></tr>
<tr><td><b>📋 Reporters</b></td><td>The first report for a device or a profile</td></tr>
<tr><td><b>✅ Confirmations</b></td><td>A later report for a device that is already confirmed</td></tr>
</tbody></table>

### Contributors

<table width="100%">
<thead><tr>
<th align="left" width="150">Who</th>
<th align="left" width="330">Device</th>
<th align="left">What</th>
</tr></thead>
<tbody>
<tr><td valign="top"><a href="https://github.com/tilenkranjc"><b>Tilen (tilenkranjc)</b></a></td><td valign="top"><a href="docs/devices/PlugAZ.md"><img src="https://img.shields.io/badge/-AZ_Plug-0969da?style=flat-square" alt="AZ Plug"></a></td><td valign="top">First and later OTA reports · Relay after power cycle · Required filesystem-part finding · Stale UDP destination diagnosis and fix verification</td></tr>
<tr><td valign="top"><a href="https://github.com/onkelfarmor"><b>onkelfarmor</b></a></td><td valign="top"><a href="docs/devices/PlugMG3#beta-layout.md"><img src="https://img.shields.io/badge/-Plug_M_Gen3_beta-0969da?style=flat-square" alt="Plug M Gen3 beta"></a> <a href="https://github.com/oxynatOr/free-shelly-ota/issues/102"><img src="https://img.shields.io/badge/-%23102-6e7781?style=flat-square" alt="#102"></a> <a href="https://github.com/oxynatOr/free-shelly-ota/issues/122"><img src="https://img.shields.io/badge/-%23122-6e7781?style=flat-square" alt="#122"></a></td><td valign="top">Layout finding · Two-run path · Second OTA · BL0942 measurement</td></tr>
<tr><td valign="top"><a href="https://github.com/aanban"><b>aanban</b></a></td><td valign="top"><a href="docs/devices/MiniPMG3.md"><img src="https://img.shields.io/badge/-PM_Mini_Gen3-0969da?style=flat-square" alt="PM Mini Gen3"></a> <a href="https://github.com/oxynatOr/free-shelly-ota/issues/113"><img src="https://img.shields.io/badge/-%23113-6e7781?style=flat-square" alt="#113"></a></td><td valign="top">Silent-device diagnosis · Old-updater finding · layout_since check</td></tr>
<tr><td valign="top"><a href="https://github.com/imsandli"><b>imsandli</b></a></td><td valign="top"><a href="docs/devices/MiniPMG3.md"><img src="https://img.shields.io/badge/-PM_Mini_Gen3-0969da?style=flat-square" alt="PM Mini Gen3"></a></td><td valign="top">First external report · RX pull-up · Voltage calibration · Reach-check idea</td></tr>
</tbody></table>

### Testers

<table width="100%">
<thead><tr>
<th align="left" width="150">Who</th>
<th align="left" width="330">Device</th>
<th align="left">What</th>
</tr></thead>
<tbody>
<tr><td valign="top"><a href="https://github.com/sipe"><b>sipe</b></a></td><td valign="top"><a href="docs/research/gen1.md"><img src="https://img.shields.io/badge/-Plug_S_Gen1-0969da?style=flat-square" alt="Plug S Gen1"></a> <a href="https://github.com/oxynatOr/free-shelly-ota/issues/47"><img src="https://img.shields.io/badge/-%2347-6e7781?style=flat-square" alt="#47"></a></td><td valign="top">First run on a real Plug S Gen1 · Button and relay work, lamp lights · rBoot config · Power-cycle check · Flash readout (2 MB) · Second update and revert on a real plug · Diagnosis of the failed reinstall (byte 9) · UART fix confirmed · Full circle without UART · LEDs and meter pins confirmed, first meter readings</td></tr>
<tr><td valign="top"><a href="https://github.com/andrewagner86"><b>andrewagner86</b></a></td><td valign="top"><a href="docs/devices/S2PMG3.md#220-layout"><img src="https://img.shields.io/badge/-2PM_Gen3-0969da?style=flat-square" alt="2PM Gen3"></a> <a href="docs/devices/PlugSG3.md#220-layout"><img src="https://img.shields.io/badge/-Plug_S_Gen3-0969da?style=flat-square" alt="Plug S Gen3"></a></td><td valign="top">2.2.0 layout (S2PMG3-v2, PlugSG3-v2) · Update paths from 1.4.99 and 1.7.3 · Flash dump of 2.2.0 · Plain packages into slot 0 · Way back without UART</td></tr>
<tr><td valign="top"><a href="https://github.com/CzarofAK"><b>CzarofAK</b></a></td><td valign="top"><a href="docs/devices/S1G4.md"><img src="https://img.shields.io/badge/-1_Gen4-0969da?style=flat-square" alt="1 Gen4"></a> <a href="https://github.com/oxynatOr/free-shelly-ota/issues/130"><img src="https://img.shields.io/badge/-%23130-6e7781?style=flat-square" alt="#130"></a> <a href="docs/devices/PlusRGBWPM.md"><img src="https://img.shields.io/badge/-Plus_RGBW_PM-0969da?style=flat-square" alt="Plus RGBW PM"></a> <a href="https://github.com/oxynatOr/free-shelly-ota/issues/133"><img src="https://img.shields.io/badge/-%23133-6e7781?style=flat-square" alt="#133"></a></td><td valign="top">Four units · Pins · Pad-hold finding · Config · LED pin · Second device, no slot log · 3 PWM outputs checked</td></tr>
<tr><td valign="top"><a href="https://github.com/niki11euro"><b>niki11euro</b></a></td><td valign="top"><a href="docs/devices/PlusI4.md"><img src="https://img.shields.io/badge/-Plus_i4_DC-0969da?style=flat-square" alt="Plus i4 DC"></a> <a href="https://github.com/oxynatOr/free-shelly-ota/issues/106"><img src="https://img.shields.io/badge/-%23106-6e7781?style=flat-square" alt="#106"></a></td><td valign="top">Device request · First OTA run · Loader and PCB notes</td></tr>
<tr><td valign="top"><a href="https://github.com/chusovich"><b>chusovich</b></a></td><td valign="top"><a href="docs/devices/S1G3.md"><img src="https://img.shields.io/badge/-1_Gen3-0969da?style=flat-square" alt="1 Gen3"></a> <a href="https://github.com/oxynatOr/free-shelly-ota/issues/98"><img src="https://img.shields.io/badge/-%2398-6e7781?style=flat-square" alt="#98"></a></td><td valign="top">Two devices · Full log · Later ESPHome OTA · Config</td></tr>
<tr><td valign="top"><a href="https://github.com/WulffTech"><b>WulffTech</b></a></td><td valign="top"><a href="docs/devices/S1PMG3.md"><img src="https://img.shields.io/badge/-1PM_Gen3-0969da?style=flat-square" alt="1PM Gen3"></a> <a href="docs/devices/S2PMG3.md"><img src="https://img.shields.io/badge/-2PM_Gen3-0969da?style=flat-square" alt="2PM Gen3"></a></td><td valign="top">Three devices, own tooling · Later OTA · pt part finding · Shelly CA finding · CA file idea (--cafile) · Slot swap (table at a new address) · Real-device test of `--pt-addr` and the way back (2PM Gen3)</td></tr>
<tr><td valign="top"><a href="https://github.com/pienovi"><b>pienovi</b></a></td><td valign="top"><a href="docs/devices/Mini1PMG3.md"><img src="https://img.shields.io/badge/-Mini_1PM_Gen3-0969da?style=flat-square" alt="Mini 1PM Gen3"></a> <a href="https://github.com/oxynatOr/free-shelly-ota/issues/82"><img src="https://img.shields.io/badge/-%2382-6e7781?style=flat-square" alt="#82"></a> <a href="docs/devices/Mini1G3.md"><img src="https://img.shields.io/badge/-Mini_1_Gen3-0969da?style=flat-square" alt="Mini 1 Gen3"></a> <a href="docs/devices/PlusPlugIT.md"><img src="https://img.shields.io/badge/-Plus_Plug_IT-0969da?style=flat-square" alt="Plus Plug IT"></a> <a href="https://github.com/oxynatOr/free-shelly-ota/issues/83"><img src="https://img.shields.io/badge/-%2383-6e7781?style=flat-square" alt="#83"></a></td><td valign="top">Four devices · Pins on hardware · Power calibration · Tasmota to ESPHome</td></tr>
<tr><td valign="top"><a href="https://github.com/jjanssen95"><b>jjanssen95</b></a></td><td valign="top"><a href="docs/devices/Mini1G3.md"><img src="https://img.shields.io/badge/-Mini_1_Gen3-0969da?style=flat-square" alt="Mini 1 Gen3"></a> <a href="https://github.com/oxynatOr/free-shelly-ota/issues/69"><img src="https://img.shields.io/badge/-%2369-6e7781?style=flat-square" alt="#69"></a></td><td valign="top">Pins on hardware · NTC finding · Weak-Wi-Fi timeout · Later OTA</td></tr>
<tr><td valign="top"><a href="https://github.com/815rx1"><b>815rx1</b></a></td><td valign="top"><a href="docs/devices/PlugMG3.md"><img src="https://img.shields.io/badge/-Plug_M_Gen3-0969da?style=flat-square" alt="Plug M Gen3"></a></td><td valign="top">First run on 1.8.99 · Bootloader swap · Two later OTAs · Power-cycle finding</td></tr>
<tr><td valign="top"><a href="https://github.com/yasdfgr"><b>yasdfgr</b></a></td><td valign="top"><a href="docs/devices/PlusUni.md"><img src="https://img.shields.io/badge/-Plus_Uni-0969da?style=flat-square" alt="Plus Uni"></a> <a href="https://github.com/oxynatOr/free-shelly-ota/issues/46"><img src="https://img.shields.io/badge/-%2346-6e7781?style=flat-square" alt="#46"></a></td><td valign="top">Full log · Loader 1.0.3 seen · UART fix · Pin table</td></tr>
</tbody></table>

### Reporters

<table width="100%">
<thead><tr>
<th align="left" width="150">Who</th>
<th align="left" width="330">Device</th>
<th align="left">What</th>
</tr></thead>
<tbody>
<tr><td valign="top"><a href="https://github.com/ceburos"><b>ceburos</b></a></td><td valign="top"><a href="docs/research/gen1.md"><img src="https://img.shields.io/badge/-Shelly_1_Gen1-0969da?style=flat-square" alt="Shelly 1 Gen1"></a> <a href="https://github.com/oxynatOr/free-shelly-ota/issues/47"><img src="https://img.shields.io/badge/-%2347-6e7781?style=flat-square" alt="#47"></a></td><td valign="top">Gen1 request (Shelly 1) · /shelly output · Offer to test</td></tr>
<tr><td valign="top"><a href="https://github.com/majoto85"><b>majoto85</b></a></td><td valign="top"><a href="docs/devices/S2PMG3.md"><img src="https://img.shields.io/badge/-2PM_Gen3-0969da?style=flat-square" alt="2PM Gen3"></a> <a href="https://github.com/oxynatOr/free-shelly-ota/issues/92"><img src="https://img.shields.io/badge/-%2392-6e7781?style=flat-square" alt="#92"></a></td><td valign="top">OTA from 1.4.99 · Later OTA · eFuse lines</td></tr>
</tbody></table>

### Confirmations

<table width="100%">
<thead><tr>
<th align="left" width="150">Who</th>
<th align="left" width="330">Device</th>
<th align="left">What</th>
</tr></thead>
<tbody>
<tr><td valign="top"><a href="https://github.com/ABotond"><b>ABotond</b></a></td><td valign="top"><a href="docs/devices/PlugMG3#beta-layout.md"><img src="https://img.shields.io/badge/-Plug_M_Gen3_beta-0969da?style=flat-square" alt="Plug M Gen3 beta"></a> <a href="https://github.com/oxynatOr/free-shelly-ota/issues/102"><img src="https://img.shields.io/badge/-%23102-6e7781?style=flat-square" alt="#102"></a></td><td valign="top">Two runs from 2.0.1 · Days of uptime</td></tr>
<tr><td valign="top"><a href="https://github.com/jumoog"><b>jumoog</b></a></td><td valign="top"><a href="docs/devices/PlugMG3#beta-layout.md"><img src="https://img.shields.io/badge/-Plug_M_Gen3_beta-0969da?style=flat-square" alt="Plug M Gen3 beta"></a> <a href="https://github.com/oxynatOr/free-shelly-ota/issues/102"><img src="https://img.shields.io/badge/-%23102-6e7781?style=flat-square" alt="#102"></a></td><td valign="top">OTA without UART · Relay after power cycle</td></tr>
</tbody></table>

## Projects

Software this tool learned from.

> [!TIP]
> Please visit and support these projects.

<table width="100%">
<thead><tr>
<th align="left" width="300">Project</th>
<th align="left" width="90">License</th>
<th align="left">What we learned from it</th>
</tr></thead>
<tbody>
<tr><td valign="top"><a href="https://github.com/tasmota/mgos32-to-tasmota32">tasmota/mgos32-to-tasmota32</a></td><td valign="top">GPL-3.0</td><td valign="top">Converting a Shelly OTA ZIP so the stock updater accepts third-party firmware</td></tr>
<tr><td valign="top"><a href="https://github.com/inventor7777/ESPHome-Shelly-Plus-Plug-US">inventor7777/ESPHome-Shelly-Plus-Plug-US</a></td><td valign="top">MIT</td><td valign="top">Replacing only the app image in Shelly's ZIP; the partition table at <code>0x10000</code>; the follow-up bootloader step (see <a href="docs/bootloader-and-slots.md">Bootloader and slots</a>)</td></tr>
<tr><td valign="top"><a href="https://github.com/automatous-io/shelly-gen4-esphome">automatous-io/shelly-gen4-esphome</a></td><td valign="top">Apache-2.0</td><td valign="top">Gen4 (ESP32-C6) partition layout, the A/B slot rule, install documentation</td></tr>
</tbody></table>

## Third parties

Sources and tools from outside this project. Their work is not redistributed here. Where a device page uses another person's page, such as an ESPHome device page, it names the source there.

<table width="100%">
<thead><tr>
<th align="left" width="300">Who</th>
<th align="left">What</th>
</tr></thead>
<tbody>
<tr><td valign="top">Shelly / Allterco Robotics</td><td valign="top">The official OTA packages and the update API (not redistributed here)</td></tr>
<tr><td valign="top"><a href="https://devices.esphome.io/devices/shelly-plug-s/">ESPHome device page for the Shelly Plug S</a>: <a href="https://github.com/gieljnssns">gieljnssns</a> (tested the configuration), Tasmota (blakadder's template for the BlitzWolf SHP6) and <a href="https://community.home-assistant.io/u/tijmen/summary">Tijmen</a></td><td valign="top">The pins and the first meter values of the Plug S Gen1 in <code>experimental/gen1</code> (facts only; the page is GPL-3.0, its configuration text is not copied)</td></tr>
<tr><td valign="top"><a href="https://esphome.io">ESPHome</a>, Espressif (esptool, ESP-IDF)</td><td valign="top">The firmware framework and tooling everything builds on</td></tr>
</tbody></table>

## Missing from this list?

> [!TIP]
> If this project uses something you found out and you are not named, or you would rather not be, please
> [open an issue](https://github.com/oxynatOr/free-shelly-ota/issues/new). If you flashed a device with the tool, a
> [device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml) puts you on this list, also when it worked.
