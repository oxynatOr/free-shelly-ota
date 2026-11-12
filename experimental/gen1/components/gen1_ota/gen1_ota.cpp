#include "gen1_ota.h"

#include <Arduino.h>
#include <ESP8266WiFi.h>

#include <cstdint>
#include <cstring>
#include <new>

#include "esphome/core/hal.h"
#include "esphome/core/log.h"

// Flash layout defaults (the Shelly 1); the build overrides them, see below.
#ifndef GEN1_CFG
#define GEN1_CFG 0x1000u
#define GEN1_SLOT0 0x8000u
#define GEN1_SLOT1 0x108000u
#define GEN1_STAGE 0x70000u
#define GEN1_STAGE_END 0xFA000u
#define GEN1_MAX_IMAGE 0x68000u
#define GEN1_RFCAL_SECTOR 0xFCu
#endif

extern "C" {
#include <spi_flash.h>
// ROM routines, bound under private names so they cannot clash with SDK/core declarations
int gen1_rom_spi_read(uint32_t addr, void *dst, uint32_t size) __asm__("SPIRead");
int gen1_rom_spi_write(uint32_t addr, void *src, uint32_t size) __asm__("SPIWrite");
int gen1_rom_spi_erase(uint32_t sector) __asm__("SPIEraseSector");
int gen1_rom_spi_unlock(void) __asm__("SPIUnlock");
void gen1_rom_cache_off(void) __asm__("Cache_Read_Disable");

// SDK 2.2.x of the Arduino core puts the RF calibration at flash size - 0x4000 = 0x1FC000, which is where the stock firmware
// keeps its RF init data: after the first ESPHome boot the stock would boot-loop. The component adds
// -Wl,--wrap=user_rf_cal_sector_set; the core's function still runs (it arms the init data spoofing) but the calibration
// goes to GEN1_RFCAL_SECTOR (0xFC for the Shelly 1), in flash that the layout leaves unused.
uint32_t __real_user_rf_cal_sector_set(void);
uint32_t __wrap_user_rf_cal_sector_set(void) {
  __real_user_rf_cal_sector_set();
  return GEN1_RFCAL_SECTOR;
}
}

namespace esphome {
namespace gen1_ota {

static const char *const TAG = "gen1_ota";

// Flash layout, from the build (layout.py derives these from the layout CSV and passes them as defines). The defaults are the
// Shelly 1 (2 MB, rBoot "big flash"): boot config 0x1000, slot 0 at 0x8000 (ESPHome runs from here), slot 1 at 0x108000 (stock
// firmware, never touched); the new image is staged at 0x70000 up to 0xFA000, where the ESPHome preferences follow.
static const uint32_t CFG = GEN1_CFG;
static const uint32_t SLOT0 = GEN1_SLOT0;
static const uint32_t SLOT1 = GEN1_SLOT1;
static const uint32_t STAGE = GEN1_STAGE;
static const uint32_t STAGE_LIMIT = GEN1_STAGE_END;
static const uint32_t MAX_IMAGE = GEN1_MAX_IMAGE;  // the new image has to fit the staging area and not run into it
static const uint32_t SEC = 4096;
static const uint32_t MAX_SLOT = 0xB3000;  // size of an app slot in the Gen1 layouts (the stock image has to fit in it)
static_assert(STAGE + MAX_IMAGE <= STAGE_LIMIT, "staging area overlaps the ESPHome preferences");

static uint32_t crc32_update(uint32_t crc, const uint8_t *p, size_t n) {
  crc = ~crc;
  while (n--) {
    crc ^= *p++;
    for (int k = 0; k < 8; k++) crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
  }
  return ~crc;
}

static uint32_t le32(const uint8_t *p) { return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t) p[3] << 24); }

// rBoot config sector: [0]=0xE1 magic, [1]=version, [3]=current rom, [5]=rom count, [6]=previous rom, [7]=unconfirmed flag,
// [9]=set to 1 by the stock's updater (found on a real plug; the stock does not write a new package while it is 1; `revert` clears it),
// [8]=boot attempts, rom addresses at 0x0c and 0x10.
static bool layout_ok(uint32_t *buf) {
  const uint8_t *b = reinterpret_cast<const uint8_t *>(buf);
  if (spi_flash_read(CFG, buf, SEC) != SPI_FLASH_RESULT_OK) return false;
  return b[0] == 0xE1 && b[1] == 0x01 && b[5] == 2 && le32(b + 0x0c) == SLOT0 && le32(b + 0x10) == SLOT1;
}

static void confirm_boot(uint32_t *buf) {
  uint8_t *b = reinterpret_cast<uint8_t *>(buf);
  if (!layout_ok(buf)) return;
  if (b[7] == 0 && b[8] == 0) return;  // already confirmed
  b[7] = 0;
  b[8] = 0;
  if (spi_flash_erase_sector(CFG / SEC) != SPI_FLASH_RESULT_OK) return;
  spi_flash_write(CFG, buf, SEC);
}

// Reads n bytes at a flash offset through the 4 kB buffer (spi_flash_read needs aligned words).
static bool flash_read(uint32_t addr, uint8_t *dst, uint32_t n, uint32_t *tmp) {
  uint8_t *t = reinterpret_cast<uint8_t *>(tmp);
  while (n) {
    uint32_t sec = addr / SEC * SEC, off = addr - sec;
    if (spi_flash_read(sec, tmp, SEC) != SPI_FLASH_RESULT_OK) return false;
    uint32_t c = SEC - off < n ? SEC - off : n;
    memcpy(dst, t + off, c);
    dst += c;
    addr += c;
    n -= c;
  }
  return true;
}

// An image in flash (at `base`, at most `limit` bytes) must be what rBoot expects: 0xEA 0x04 header, one irom segment, then a
// 0xE9 image whose segments are 4-byte multiples, ending with the XOR checksum (seed 0xEF) at the 16-byte boundary. *end gets the
// image size (the offset after the checksum byte).
static const char *walk_image(uint32_t base, uint32_t limit, uint32_t *tmp, uint32_t *end) {
  uint8_t h[8];
  uint8_t *t = reinterpret_cast<uint8_t *>(tmp);
  if (!flash_read(base, h, 8, tmp) || h[0] != 0xEA || h[1] != 0x04) return "not an rboot image";
  if (!flash_read(base + 8, h, 8, tmp)) return "read";
  uint32_t off = 16 + le32(h + 4);  // irom segment
  if (off + 8 > limit) return "irom segment";
  if (!flash_read(base + off, h, 8, tmp) || h[0] != 0xE9 || h[1] == 0 || h[1] > 8) return "no inner image";
  uint32_t count = h[1];
  off += 8;
  uint8_t cs = 0xEF;
  for (uint32_t i = 0; i < count; i++) {
    if (off + 8 > limit || !flash_read(base + off, h, 8, tmp)) return "segment header";
    uint32_t len = le32(h + 4);
    off += 8;
    if ((len & 3) || off + len > limit) return "segment length";
    for (uint32_t done = 0; done < len;) {  // XOR over the segment, one sector at a time
      uint32_t a = base + off + done, sec = a / SEC * SEC;
      if (spi_flash_read(sec, tmp, SEC) != SPI_FLASH_RESULT_OK) return "read";
      uint32_t from = a - sec, c = SEC - from < len - done ? SEC - from : len - done;
      for (uint32_t k = 0; k < c; k++) cs ^= t[from + k];
      done += c;
    }
    off += len;
  }
  uint32_t pos = off + (16 - ((off + 1) % 16)) % 16;
  uint8_t last;
  if (pos + 1 > limit || !flash_read(base + pos, &last, 1, tmp) || last != cs) return "checksum";
  *end = pos + 1;
  return nullptr;
}

// The staged image must be exactly the size that was announced, and nothing may follow the checksum.
static const char *check_image(uint32_t size, uint32_t *tmp) {
  uint32_t end = 0;
  const char *bad = walk_image(STAGE, size, tmp, &end);
  if (!bad && end != size) return "checksum";
  return bad;
}

// Way back to the stock firmware without UART: point the rBoot config at slot 1 (the stock). The config sector is not part of the
// running image, so this can use the normal flash calls. The stock image in slot 1 is walked first (structure and checksum), so an
// empty or damaged slot is never booted. The unconfirmed flag stays 0 on purpose: the stock reads a set flag as "I was just updated",
// tries to take over the old file system of the other slot (which holds nothing of the stock) and reverts to this app. So there is
// no automatic fallback; the slot check above is the protection.
static const char *revert_to_stock(uint32_t *buf) {
  uint8_t *b = reinterpret_cast<uint8_t *>(buf);
  uint32_t end = 0;
  const char *bad = walk_image(SLOT1, MAX_SLOT, buf, &end);
  if (bad) {
    ESP_LOGE(TAG, "slot 1 holds no valid image: %s", bad);
    return "ERR stock (no valid image in the other slot)\n";
  }
  if (!layout_ok(buf)) return "ERR layout (not a Shelly Gen1 rBoot layout)\n";
  if (b[3] != 0) return "ERR state (not running from slot 0)\n";
  b[3] = 1;
  b[6] = 0;
  b[7] = 0;
  b[8] = 0;
  b[9] = 0;  // the stock sets this byte when it installs an update; while it is 1 the stock downloads a new package but does not write it
  if (spi_flash_erase_sector(CFG / SEC) != SPI_FLASH_RESULT_OK) return "ERR flash\n";
  if (spi_flash_write(CFG, buf, SEC) != SPI_FLASH_RESULT_OK) return "ERR flash\n";
  return nullptr;
}

// Runs from IRAM only: the flash (and with it the running image) is overwritten, so nothing in here may call into flash code.
static void __attribute__((section(".iram.text"), noinline, used)) install(uint32_t len, uint32_t *buf) {
  uint8_t *b = reinterpret_cast<uint8_t *>(buf);
  noInterrupts();
  gen1_rom_cache_off();
  gen1_rom_spi_unlock();
  // power-loss safety: boot the stock slot while slot 0 is being rewritten
  gen1_rom_spi_read(CFG, buf, SEC);
  b[3] = 1;
  b[7] = 0;
  b[8] = 0;
  gen1_rom_spi_erase(CFG / SEC);
  gen1_rom_spi_write(CFG, buf, SEC);
  for (uint32_t off = 0; off < len; off += SEC) {
    *reinterpret_cast<volatile uint32_t *>(0x60000914) = 0x73;  // feed the hardware watchdog
    gen1_rom_spi_read(STAGE + off, buf, SEC);
    gen1_rom_spi_erase((SLOT0 + off) / SEC);
    gen1_rom_spi_write(SLOT0 + off, buf, SEC);
  }
  // new app: slot 0, previous = slot 1, unconfirmed (it has to confirm itself, see confirm_boot)
  gen1_rom_spi_read(CFG, buf, SEC);
  b[3] = 0;
  b[6] = 1;
  b[7] = 1;
  b[8] = 0;
  gen1_rom_spi_erase(CFG / SEC);
  gen1_rom_spi_write(CFG, buf, SEC);
  for (;;) {
  }  // the hardware watchdog resets the chip
}

void Gen1OTAComponent::setup() {
  if (this->password_.empty()) this->mark_failed();
}

void Gen1OTAComponent::dump_config() {
  ESP_LOGCONFIG(TAG, "Gen1 OTA:");
  ESP_LOGCONFIG(TAG, "  Port: %u", this->port_);
  ESP_LOGCONFIG(TAG, "  Boot confirmation after: %u ms", this->confirm_after_ms_);
}

void Gen1OTAComponent::loop() {
  uint32_t now = millis();
  if (!this->confirmed_ && now >= this->confirm_after_ms_) {
    this->confirmed_ = true;
    uint32_t *buf = new (std::nothrow) uint32_t[SEC / 4];
    if (buf) {
      confirm_boot(buf);
      delete[] buf;
    }
  }
  if (!this->server_) {
    if (now < 5000) return;
    this->server_ = new WiFiServer(this->port_);
    this->server_->begin();
    ESP_LOGI(TAG, "listening on %u", this->port_);
    return;
  }
  WiFiClient c = this->server_->accept();
  if (!c) return;
  this->handle_(c);
  c.stop();
}

static bool read_exact(WiFiClient &c, uint8_t *dst, size_t n) { return c.readBytes(dst, n) == n; }

// Protocol: the device sends a 16-byte random nonce; the client answers with "G1OT", u32 size, u32 crc32 (zlib) and
// HMAC-SHA256(password, nonce + those 12 header bytes). The device replies "READY\n" (or "ERR ...\n" and closes), the client
// then sends the image, the final reply is "OK\n" (installing, the device resets itself) or "ERR ...\n".
// Way back: the same handshake with "G1RV" (size and crc 0) instead of "G1OT"; the reply is "OK\n" (the device boots the
// stock firmware from the other slot) or "ERR ...\n", no image follows.
void Gen1OTAComponent::handle_(WiFiClient &c) {
  c.setTimeout(5000);
  uint8_t nonce[16], hdr[12], mac[32], want[32];
  for (int i = 0; i < 4; i++) {
    uint32_t r = ESP.random();
    memcpy(nonce + 4 * i, &r, 4);
  }
  c.write(nonce, sizeof(nonce));
  c.flush();
  if (!read_exact(c, hdr, sizeof(hdr)) || !read_exact(c, mac, sizeof(mac))) {
    c.print("ERR header\n");
    return;
  }
  br_hmac_key_context kc;
  br_hmac_context hc;
  br_hmac_key_init(&kc, &br_sha256_vtable, this->password_.data(), this->password_.size());
  br_hmac_init(&hc, &kc, 0);
  br_hmac_update(&hc, nonce, sizeof(nonce));
  br_hmac_update(&hc, hdr, sizeof(hdr));
  br_hmac_out(&hc, want);
  uint8_t diff = 0;
  for (int i = 0; i < 32; i++) diff |= mac[i] ^ want[i];
  if (diff != 0) {
    ESP_LOGW(TAG, "authentication failed");
    c.print("ERR auth\n");
    delay(1000);  // slow down guessing
    return;
  }
  if (memcmp(hdr, "G1RV", 4) == 0) {
    uint32_t *rb = new (std::nothrow) uint32_t[SEC / 4];
    if (!rb) {
      c.print("ERR memory\n");
      return;
    }
    const char *e = revert_to_stock(rb);
    delete[] rb;
    if (e) {
      ESP_LOGE(TAG, "revert rejected");
      c.print(e);
      return;
    }
    ESP_LOGW(TAG, "reverting to the stock firmware");
    c.print("OK\n");
    c.flush();
    delay(300);
    ESP.restart();
    return;
  }
  if (memcmp(hdr, "G1OT", 4) != 0) {
    c.print("ERR header\n");
    return;
  }
  uint32_t size = le32(hdr + 4), want_crc = le32(hdr + 8);
  if (size < 1024 || size > MAX_IMAGE) {
    c.print("ERR size\n");
    return;
  }
  uint32_t *buf = new (std::nothrow) uint32_t[SEC / 4];
  if (!buf) {
    c.print("ERR memory\n");
    return;
  }
  uint8_t *b = reinterpret_cast<uint8_t *>(buf);
  const char *err = nullptr;
  if (!layout_ok(buf)) err = "ERR layout (not a Shelly Gen1 rBoot layout)\n";
  if (!err) {  // header, password and layout are fine: the client may send the image now
    c.print("READY\n");
    c.flush();
  }
  if (!err) {
    ESP_LOGI(TAG, "receiving %u bytes", size);
    uint32_t crc = 0;
    for (uint32_t off = 0; off < size && !err; off += SEC) {
      uint32_t n = size - off < SEC ? size - off : SEC;
      memset(b, 0xFF, SEC);
      if (!read_exact(c, b, n)) {
        err = "ERR receive\n";
        break;
      }
      crc = crc32_update(crc, b, n);
      if (spi_flash_erase_sector((STAGE + off) / SEC) != SPI_FLASH_RESULT_OK ||
          spi_flash_write(STAGE + off, buf, SEC) != SPI_FLASH_RESULT_OK)
        err = "ERR flash\n";
    }
    if (!err && crc != want_crc) err = "ERR crc\n";
  }
  if (!err) {  // read back what the flash holds, not what was sent
    uint32_t back = 0;
    for (uint32_t off = 0; off < size; off += SEC) {
      uint32_t n = size - off < SEC ? size - off : SEC;
      spi_flash_read(STAGE + off, buf, SEC);
      back = crc32_update(back, b, n);
    }
    if (back != want_crc) err = "ERR verify\n";
  }
  if (!err) {
    const char *bad = check_image(size, buf);
    if (bad) ESP_LOGE(TAG, "image check failed: %s", bad);
    if (bad) err = "ERR image\n";
  }
  if (err) {
    ESP_LOGE(TAG, "update rejected");
    c.print(err);
    delete[] buf;
    return;
  }
  ESP_LOGI(TAG, "staged and verified, installing");
  c.print("OK\n");
  c.flush();
  delay(300);
  install(size, buf);
}

}  // namespace gen1_ota
}  // namespace esphome
