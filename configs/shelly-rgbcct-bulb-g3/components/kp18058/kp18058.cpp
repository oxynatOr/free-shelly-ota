#include "kp18058.h"
#include "esphome/core/log.h"
#include "esphome/core/hal.h"

namespace esphome {
namespace kp18058 {

static const char *const TAG = "kp18058";

static const uint8_t FRAME_LEN = 14;
static const uint8_t MAX_RETRIES = 3;
static const uint32_t HALF_BIT_US = 2;

// Working modes (byte 0, bits 6-5)
static const uint8_t MODE_STANDBY = 0b00;
static const uint8_t MODE_RGBCW = 0b11;

/// Every frame byte carries 7 data bits (7..1) plus a parity flag in bit 0
/// that makes the number of set data bits even.
static uint8_t with_parity(uint8_t b) {
  b &= 0xFE;
  return b | (__builtin_popcount(b) & 1);
}

void KP18058Channel::write_state(float state) {
  state = clamp(state, 0.0f, 1.0f);
  this->parent_->set_channel_value(this->channel_, static_cast<uint16_t>(roundf(state * 1023.0f)));
}

void KP18058Component::set_channel_value(uint8_t channel, uint16_t value) {
  if (channel >= NUM_CHANNELS || this->values_[channel] == value)
    return;
  this->values_[channel] = value;
  this->dirty_ = true;
}

void KP18058Component::setup() {
  this->data_pin_->setup();
  this->clock_pin_->setup();
  this->bus_ready_ = this->bus_reset_();
  this->dirty_ = true;
}

void KP18058Component::dump_config() {
  ESP_LOGCONFIG(TAG, "KP18058 LED driver:");
  LOG_PIN("  Data Pin: ", this->data_pin_);
  LOG_PIN("  Clock Pin: ", this->clock_pin_);
  ESP_LOGCONFIG(TAG, "  RGB current: %.1f mA", (this->rgb_current_ + 1) * 1.5f);
  ESP_LOGCONFIG(TAG, "  CW current: %.1f mA", this->cw_current_ * 2.5f);
  ESP_LOGCONFIG(TAG, "  RGB dimming: %s", this->rgb_dimming_ == RGB_DIMMING_CHOP ? "chop" : "analog");
  ESP_LOGCONFIG(TAG, "  Bus: %s", this->bus_ready_ ? "ok" : "FAILED");
}

void KP18058Component::loop() {
  if (!this->dirty_)
    return;
  if (!this->bus_ready_)
    this->bus_ready_ = this->bus_reset_();
  if (!this->bus_ready_) {
    ESP_LOGE(TAG, "Bus reset failed (SDA stuck low?)");
    this->status_set_warning();
    return;
  }
  if (this->send_frame_()) {
    this->dirty_ = false;
    this->status_clear_warning();
  } else {
    this->bus_ready_ = false;  // reset the bus and retry on the next loop
    this->status_set_warning();
  }
}

bool KP18058Component::send_frame_() {
  bool all_zero = true;
  for (auto v : this->values_)
    all_zero = all_zero && v == 0;

  uint8_t f[FRAME_LEN] = {};
  // Byte 0: [7]=1 address id, [6:5] mode, [4:1] start address (0), [0] parity
  f[0] = (1 << 7) | ((all_zero ? MODE_STANDBY : MODE_RGBCW) << 5);
  // Byte 1: line compensation disabled
  f[1] = 0;
  // Byte 2: [7:6] chop frequency, [5:1] OUT1-3 current
  f[2] = (this->chop_frequency_ << 6) | ((this->rgb_current_ & 0x1F) << 1);
  // Byte 3: [7] chop dimming OUT1-3, [6] RC filter off, [5:1] OUT4-5 current
  f[3] = ((this->rgb_dimming_ == RGB_DIMMING_CHOP ? 1 : 0) << 7) | (1 << 6) | ((this->cw_current_ & 0x1F) << 1);
  if (all_zero)
    f[2] = 1 << 1;  // minimal current in standby
  // Bytes 4-13: per channel upper 5 bits, then lower 5 bits of the 10 bit value
  for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
    f[4 + i * 2] = ((this->values_[i] >> 5) & 0x1F) << 1;
    f[5 + i * 2] = (this->values_[i] & 0x1F) << 1;
  }
  for (auto &b : f)
    b = with_parity(b);

  this->bus_start_();
  bool ok = true;
  for (uint8_t i = 0; i < FRAME_LEN && ok; i++) {
    ok = false;
    for (uint8_t attempt = 0; attempt < MAX_RETRIES && !ok; attempt++)
      ok = this->bus_write_byte_(f[i]);
    if (!ok)
      ESP_LOGE(TAG, "No ACK for byte %u (0x%02X)", i, f[i]);
  }
  this->bus_stop_();
  return ok;
}

// ---- bit-banged bus ---------------------------------------------------------

void KP18058Component::bus_release_(GPIOPin *pin) { pin->pin_mode(gpio::FLAG_INPUT | gpio::FLAG_PULLUP); }

void KP18058Component::bus_drive_low_(GPIOPin *pin) {
  pin->pin_mode(gpio::FLAG_OUTPUT);
  pin->digital_write(false);
}

bool KP18058Component::bus_reset_() {
  this->bus_release_(this->data_pin_);
  for (int i = 0; i < 9; i++) {
    this->bus_release_(this->clock_pin_);
    delayMicroseconds(HALF_BIT_US);
    this->bus_drive_low_(this->clock_pin_);
    delayMicroseconds(HALF_BIT_US);
    if (this->data_pin_->digital_read())
      break;
  }
  if (!this->data_pin_->digital_read())
    return false;
  // A start/stop pair keeps the chip from misreading the first real start condition.
  this->bus_start_();
  this->bus_stop_();
  return this->data_pin_->digital_read() && this->clock_pin_->digital_read();
}

void KP18058Component::bus_start_() {
  this->bus_release_(this->clock_pin_);
  this->bus_release_(this->data_pin_);
  delayMicroseconds(HALF_BIT_US);
  this->bus_drive_low_(this->data_pin_);
  delayMicroseconds(HALF_BIT_US);
  this->bus_drive_low_(this->clock_pin_);
}

void KP18058Component::bus_stop_() {
  delayMicroseconds(HALF_BIT_US);
  this->bus_drive_low_(this->data_pin_);
  delayMicroseconds(HALF_BIT_US);
  this->bus_release_(this->clock_pin_);
  delayMicroseconds(HALF_BIT_US);
  this->bus_release_(this->data_pin_);
}

bool KP18058Component::bus_write_byte_(uint8_t value) {
  for (uint8_t mask = 0x80; mask != 0; mask >>= 1) {
    if (value & mask)
      this->bus_release_(this->data_pin_);
    else
      this->bus_drive_low_(this->data_pin_);
    this->bus_release_(this->clock_pin_);
    delayMicroseconds(HALF_BIT_US);
    this->bus_drive_low_(this->clock_pin_);
    delayMicroseconds(HALF_BIT_US);
  }
  // 9th clock: the chip pulls SDA low as ACK
  this->bus_release_(this->data_pin_);
  this->bus_release_(this->clock_pin_);
  delayMicroseconds(HALF_BIT_US);
  bool ack = !this->data_pin_->digital_read();
  delayMicroseconds(HALF_BIT_US);
  this->bus_drive_low_(this->clock_pin_);
  return ack;
}

}  // namespace kp18058
}  // namespace esphome
