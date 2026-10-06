import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import pins
from esphome.const import CONF_CLOCK_PIN, CONF_DATA_PIN, CONF_ID

CODEOWNERS = ["@oxboxrox"]
# Every KP18058/KP18068 gets its own 2-wire bus, so several chips = several entries.
MULTI_CONF = True

CONF_RGB_CURRENT = "rgb_current"
CONF_CW_CURRENT = "cw_current"
CONF_RGB_DIMMING = "rgb_dimming"
CONF_CHOP_FREQUENCY = "chop_frequency"

kp18058_ns = cg.esphome_ns.namespace("kp18058")
KP18058Component = kp18058_ns.class_("KP18058Component", cg.Component)
RGBDimming = kp18058_ns.enum("RGBDimming")
ChopFrequency = kp18058_ns.enum("ChopFrequency")

RGB_DIMMING = {
    "analog": RGBDimming.RGB_DIMMING_ANALOG,
    "chop": RGBDimming.RGB_DIMMING_CHOP,
}
CHOP_FREQUENCY = {
    "4khz": ChopFrequency.CHOP_FREQ_4KHZ,
    "2khz": ChopFrequency.CHOP_FREQ_2KHZ,
    "1khz": ChopFrequency.CHOP_FREQ_1KHZ,
    "500hz": ChopFrequency.CHOP_FREQ_500HZ,
}



def _current(step, offset, lo, hi):
    """Validate a mA value and convert it to the 5-bit register value."""

    def validator(value):
        value = cv.float_range(min=lo, max=hi)(cv.float_(value))
        reg = (value - offset) / step
        if abs(reg - round(reg)) > 1e-6:
            raise cv.Invalid(f"Current must be a multiple of {step} mA (got {value})")
        return int(round(reg))

    return validator


# OUT1-3: 1.5 mA .. 48 mA in 1.5 mA steps (register = mA/1.5 - 1)
# OUT4-5: 0 mA .. 77.5 mA in 2.5 mA steps (register = mA/2.5)
# (scaling as used by the Espressif lightbulb_driver)
rgb_current = _current(1.5, 1.5, 1.5, 48.0)
cw_current = _current(2.5, 0.0, 0.0, 77.5)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(KP18058Component),
        cv.Required(CONF_DATA_PIN): pins.gpio_output_pin_schema,
        cv.Required(CONF_CLOCK_PIN): pins.gpio_output_pin_schema,
        cv.Optional(CONF_RGB_CURRENT, default=22.5): rgb_current,
        cv.Optional(CONF_CW_CURRENT, default=75.0): cw_current,
        cv.Optional(CONF_RGB_DIMMING, default="chop"): cv.enum(RGB_DIMMING, lower=True),
        cv.Optional(CONF_CHOP_FREQUENCY, default="500hz"): cv.enum(
            CHOP_FREQUENCY, lower=True
        ),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    data = await cg.gpio_pin_expression(config[CONF_DATA_PIN])
    clock = await cg.gpio_pin_expression(config[CONF_CLOCK_PIN])
    cg.add(var.set_pins(data, clock))
    cg.add(var.set_rgb_current(config[CONF_RGB_CURRENT]))
    cg.add(var.set_cw_current(config[CONF_CW_CURRENT]))
    cg.add(var.set_rgb_dimming(config[CONF_RGB_DIMMING]))
    cg.add(var.set_chop_frequency(config[CONF_CHOP_FREQUENCY]))
