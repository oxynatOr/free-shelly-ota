"""Self-update for ESPHome on a Shelly Gen1 (ESP8266, rBoot layout), replacing the eboot OTA that does not exist there.

Adds the receiver (gen1_ota.cpp), the boot confirmation for rBoot, the linker script for the slot the layout names and
the wrapper that keeps the SDK RF calibration away from the stock firmware's RF init data.

The flash layout (rBoot config sector, the two slots, the staging area) is not hard-coded: it comes from a partition CSV in the
format of the stock partition tables of the Gen2+ profiles: `partitions: SHSW-1-stock.csv` (one of the files shipped in
partitions/, one per Gen1 model) or a file of your own next to the configuration, see layout.py.
"""
import importlib.util
import sys
from pathlib import Path

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID, CONF_PASSWORD, CONF_PORT, PLATFORM_ESP8266
from esphome.core import CORE
from esphome.helpers import copy_file_if_changed, write_file_if_changed

_spec = importlib.util.spec_from_file_location("gen1_ota_layout", Path(__file__).parent / "layout.py")
gen1_layout = importlib.util.module_from_spec(_spec)  # pure Python, shared with tools/gen1_ota.py
sys.modules["gen1_ota_layout"] = gen1_layout  # the dataclass needs its module registered
_spec.loader.exec_module(gen1_layout)

DEPENDENCIES = ["wifi"]

LD_INSTALL_SCRIPT = """\
Import("env")
import os
import shutil

framework = env.PioPlatform().get_package_dir("framework-arduinoespressif8266")
shutil.copy(
    os.path.join(env["PROJECT_DIR"], "gen1_slot.ld"),
    os.path.join(framework, "tools", "sdk", "ld", "gen1_slot.ld"),
)
"""

CONF_CONFIRM_AFTER = "confirm_after"
CONF_PARTITIONS = "partitions"
PARTITIONS_DIR = Path(__file__).parent / "partitions"


def _partitions_path(value):
    """A partition CSV next to the configuration, or one of the shipped ones (partitions/<name>)."""
    value = cv.string_strict(value)
    candidates = [Path(value) if Path(value).is_absolute() else Path(CORE.relative_config_path(value)), PARTITIONS_DIR / value]
    for path in candidates:
        if path.is_file():
            return str(path)
    shipped = ", ".join(sorted(p.name for p in PARTITIONS_DIR.glob("*.csv")))
    raise cv.Invalid(f"partition file {value!r} not found (next to the configuration, or one of: {shipped})")


def _load_partitions(value):
    path = _partitions_path(value)
    try:
        gen1_layout.parse_csv(Path(path).read_text(encoding="utf-8"))
    except gen1_layout.LayoutError as e:
        raise cv.Invalid(f"{value}: {e}") from None
    return path


gen1_ota_ns = cg.esphome_ns.namespace("gen1_ota")
Gen1OTAComponent = gen1_ota_ns.class_("Gen1OTAComponent", cg.Component)

CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(Gen1OTAComponent),
            cv.Required(CONF_PASSWORD): cv.All(cv.string_strict, cv.Length(min=8)),
            cv.Optional(CONF_PORT, default=8267): cv.port,
            cv.Optional(CONF_CONFIRM_AFTER, default="10s"): cv.positive_time_period_milliseconds,
            cv.Optional(CONF_PARTITIONS, default="SHSW-1-stock.csv"): _load_partitions,
        }
    ).extend(cv.COMPONENT_SCHEMA),
    cv.only_on([PLATFORM_ESP8266]),
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_password(config[CONF_PASSWORD]))
    cg.add(var.set_port(config[CONF_PORT]))
    cg.add(var.set_confirm_after(config[CONF_CONFIRM_AFTER]))
    lay = gen1_layout.parse_csv(Path(config[CONF_PARTITIONS]).read_text(encoding="utf-8"))
    for name, value in gen1_layout.defines(lay).items():
        cg.add_define(name, cg.RawExpression(value))
    # RF calibration to the layout's sector instead of flash size - 0x4000 (see gen1_ota.cpp)
    cg.add_build_flag("-Wl,--wrap=user_rf_cal_sector_set")
    # Sketch linked for the rBoot slot 0 of the layout; ESPHome preferences / EEPROM from the partition CSV. Both builders only take a
    # bare script name that is found on the linker search path: the native build searches <build>/.pioenvs/<name>/ld, the
    # PlatformIO build the framework's ld folder (copied there by a pre-build script).
    ld = Path(CORE.relative_build_path("gen1_slot.generated.ld"))
    write_file_if_changed(ld, gen1_layout.render_ld(lay))
    native_ld_dir = Path(CORE.relative_pioenvs_path(CORE.name, "ld"))
    native_ld_dir.mkdir(parents=True, exist_ok=True)
    copy_file_if_changed(ld, native_ld_dir / "gen1_slot.ld")
    copy_file_if_changed(ld, Path(CORE.relative_build_path("gen1_slot.ld")))
    write_file_if_changed(CORE.relative_build_path("gen1_ld_install.py"), LD_INSTALL_SCRIPT)
    cg.add_platformio_option("extra_scripts", ["pre:gen1_ld_install.py"])
    cg.add_platformio_option("board_build.ldscript", "gen1_slot.ld")
