#pragma once

#include <string>

#include "esphome/core/component.h"

class WiFiServer;
class WiFiClient;

namespace esphome {
namespace gen1_ota {

class Gen1OTAComponent : public Component {
 public:
  void set_password(const std::string &password) { this->password_ = password; }
  void set_port(uint16_t port) { this->port_ = port; }
  void set_confirm_after(uint32_t ms) { this->confirm_after_ms_ = ms; }

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::AFTER_WIFI; }

 protected:
  void handle_(WiFiClient &client);

  std::string password_;
  uint16_t port_{8267};
  uint32_t confirm_after_ms_{10000};
  bool confirmed_{false};
  WiFiServer *server_{nullptr};
};

}  // namespace gen1_ota
}  // namespace esphome
