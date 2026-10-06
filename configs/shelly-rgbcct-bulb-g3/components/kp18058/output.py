import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import output
from esphome.const import CONF_CHANNEL, CONF_ID

from . import KP18058Component, kp18058_ns

DEPENDENCIES = ["kp18058"]

CONF_KP18058_ID = "kp18058_id"

KP18058Channel = kp18058_ns.class_("KP18058Channel", output.FloatOutput)

CONFIG_SCHEMA = output.FLOAT_OUTPUT_SCHEMA.extend(
    {
        cv.Required(CONF_ID): cv.declare_id(KP18058Channel),
        cv.GenerateID(CONF_KP18058_ID): cv.use_id(KP18058Component),
        cv.Required(CONF_CHANNEL): cv.int_range(min=1, max=5),
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_KP18058_ID])
    var = cg.new_Pvariable(config[CONF_ID])
    cg.add(var.set_parent(parent))
    cg.add(var.set_channel(config[CONF_CHANNEL] - 1))
    await output.register_output(var, config)
