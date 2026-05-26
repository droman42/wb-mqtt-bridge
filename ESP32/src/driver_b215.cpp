// driver_b215.cpp — Revox B215 SERIAL LINK (ITT/Nokia baseband, device id 04).
// Output: open-collector on DIN pin 3 (DATA), referenced to pin 2 (floating GND).
// Idle HIGH (deck pull-up); assert by pulling LOW. NEVER drive HIGH.
// Optional: status read-back via a second opto on pin 3 → input pin.
//
// BENCH FILL-INS (from B205 scope captures on pin 3):
//   - LINK_INVERT, bit timing (T_START / T_BIT0 / T_BIT1 / T_REPEAT),
//   - per-function frame values (device id 04 + function code).
#include "device_driver.h"
#include "driver/gpio.h"
#include "esp_attr.h"
#include "esp_log.h"
#include "esp_rom_sys.h"     // esp_rom_delay_us
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <cstdint>
#include <cstring>

static const char* TAG = "b215";

static const gpio_num_t PIN_LINK    = GPIO_NUM_14;   // → open-collector LED (pulls pin3 LOW)
static const gpio_num_t PIN_STATUS  = GPIO_NUM_35;   // ← status opto (input-only OK); GPIO_NUM_NC to disable
static const bool       LINK_INVERT = true;          // set after scoping line polarity

// ---- bit timing (us) — REPLACE from captures (~15 µs-scale features) ----
static const uint16_t T_START   = 0;   // TODO start-bit width
static const uint16_t T_BIT0    = 0;   // TODO 0-bit period
static const uint16_t T_BIT1    = 0;   // TODO 1-bit period
static const uint16_t T_REPEAT  = 0;   // TODO inter-frame gap

// ---- command frames — REPLACE 0x0000 with captured values (device id 04 + fn) ----
struct Frame { const char* name; uint16_t frame; };
static const Frame FR[] = {
    {"standby", 0x0000},
    {"stop",    0x0000},
    {"play",    0x0000},
    {"ff",      0x0000},
    {"rewind",  0x0000},
    {"record",  0x0000},
    {"pause",   0x0000},
};

static IRAM_ATTR void link_assert(bool low) {
    // low==true → pull DATA low (asserted). Respect LINK_INVERT.
    bool pin_high = LINK_INVERT ? !low : low;
    gpio_set_level(PIN_LINK, pin_high ? 1 : 0);
}

// Bit-bang one frame. Exact framing (bit order, start, parity/stop) comes from
// YOUR captures; this is the structural skeleton.
static void IRAM_ATTR send_link_frame(uint16_t frame) {
    portDISABLE_INTERRUPTS();
    // start
    link_assert(true);  esp_rom_delay_us(T_START ? T_START : 1);
    // data bits (MSB-first assumed; confirm from capture)
    for (int b = 15; b >= 0; b--) {
        bool bit = (frame >> b) & 1;
        link_assert(true);
        esp_rom_delay_us(bit ? T_BIT1 : T_BIT0);
        link_assert(false);
        esp_rom_delay_us(T_BIT0 ? T_BIT0 : 1);
    }
    link_assert(false);
    portENABLE_INTERRUPTS();
}

static void b215_begin() {
    gpio_config_t out = {};
    out.mode         = GPIO_MODE_OUTPUT;
    out.pin_bit_mask = (1ULL << PIN_LINK);
    out.pull_up_en   = GPIO_PULLUP_DISABLE;
    out.pull_down_en = GPIO_PULLDOWN_DISABLE;
    out.intr_type    = GPIO_INTR_DISABLE;
    gpio_config(&out);
    link_assert(false);  // idle released; deck pull-up → high

    if (PIN_STATUS != GPIO_NUM_NC) {
        gpio_config_t in = {};
        in.mode         = GPIO_MODE_INPUT;
        in.pin_bit_mask = (1ULL << PIN_STATUS);
        in.pull_up_en   = GPIO_PULLUP_ENABLE;
        in.pull_down_en = GPIO_PULLDOWN_DISABLE;
        in.intr_type    = GPIO_INTR_DISABLE;
        gpio_config(&in);
    }
    ESP_LOGI(TAG, "begin: PIN_LINK=GPIO%d (inv=%d), PIN_STATUS=GPIO%d",
             (int)PIN_LINK, (int)LINK_INVERT, (int)PIN_STATUS);
}

static bool b215_do(const char* name) {
    if (!std::strcmp(name, "arm_record")) return true;
    if (!std::strcmp(name, "record") && !record_is_armed()) return false;

    for (const auto& f : FR) {
        if (std::strcmp(f.name, name) == 0) {
            send_link_frame(f.frame);
            if (!std::strcmp(name, "record")) record_consume_arm();
            return true;
        }
    }
    return false;
}

// Optional status read-back — parse the deck's return frames into MQTT value
// topics (play state, mm:ss counter). Skeleton; fill with decoding from
// captures.
static int64_t s_last_us = 0;
static void b215_poll() {
    if (PIN_STATUS == GPIO_NUM_NC) return;
    int64_t now = esp_timer_get_time();
    if ((now - s_last_us) < 250000) return;  // ≥250 ms cadence
    s_last_us = now;
    // TODO: implement frame capture/decoding from your status-string format.
    // When decoded, e.g.:
    //   wb_publish_value("state",   "play",  true);
    //   wb_publish_value("counter", "12:34", true);
}

static const Control B215_CTRLS[] = {
    {"standby",    CT_SWITCH,     false},
    {"stop",       CT_PUSHBUTTON, false},
    {"play",       CT_PUSHBUTTON, false},
    {"ff",         CT_PUSHBUTTON, false},
    {"rewind",     CT_PUSHBUTTON, false},
    {"pause",      CT_PUSHBUTTON, false},
    {"arm_record", CT_PUSHBUTTON, false},
    {"record",     CT_PUSHBUTTON, true},
};

extern const DeviceDriver DRIVER_B215 = {   // `extern` ↔ C++ namespace-scope const has internal linkage by default
    "revox_b215", "Revox B215",
    B215_CTRLS, sizeof(B215_CTRLS) / sizeof(B215_CTRLS[0]),
    b215_begin, b215_do, b215_poll
};
