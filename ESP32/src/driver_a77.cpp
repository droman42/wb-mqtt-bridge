// driver_a77.cpp — Revox A77 remote contacts via opto-MOSFETs across WIST-10
// pin-pairs. Each function = close a pin-pair for a momentary press.
// RECORD = PLAY+REC together, gated by record-arming + reel-motion interlock
// (the A77 has no motion sensor of its own; one is added per the build doc).
//
// BENCH FILL-INS:
//   - Confirm GPIO ↔ pin-pair mapping against actual WIST-10 wiring.
//   - Tune PRESS_MS, MOTION_WINDOW_MS, POST_STOP_DELAY.
//   - Set PIN_MOTION to the actual motion-sensor GPIO.
#include "device_driver.h"
#include "driver/gpio.h"
#include "esp_attr.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <cstring>

static const char* TAG = "a77";

// ---- opto-MOSFET drive pins (TODO: confirm against WIST-10 wiring) ----
static const gpio_num_t PIN_STOP   = GPIO_NUM_14;  // closes pins 1<->2
static const gpio_num_t PIN_PLAY   = GPIO_NUM_27;  // closes pins 4<->5
static const gpio_num_t PIN_FF     = GPIO_NUM_26;  // closes pins 10<->3
static const gpio_num_t PIN_REW    = GPIO_NUM_25;  // closes pins 8<->9
static const gpio_num_t PIN_REC    = GPIO_NUM_33;  // closes pin 6 (asserted WITH play)
static const gpio_num_t PIN_MOTION = GPIO_NUM_34;  // reel-motion sensor (input-only OK)

static const uint16_t PRESS_MS         = 200;
static const uint32_t MOTION_WINDOW_MS = 400;   // "moving" if a pulse seen within
static const uint32_t POST_STOP_DELAY  = 500;   // B77-style settle after stop

static volatile int64_t s_last_pulse_us = 0;

static void IRAM_ATTR motion_isr(void* /*arg*/) {
    s_last_pulse_us = esp_timer_get_time();
}

static bool reels_moving() {
    return (esp_timer_get_time() - s_last_pulse_us) < (int64_t)MOTION_WINDOW_MS * 1000LL;
}

static void press(gpio_num_t pin) {
    gpio_set_level(pin, 1);
    vTaskDelay(pdMS_TO_TICKS(PRESS_MS));
    gpio_set_level(pin, 0);
}

static void a77_begin() {
    // 5 outputs (STOP/PLAY/FF/REW/REC)
    gpio_config_t out_cfg = {};
    out_cfg.mode         = GPIO_MODE_OUTPUT;
    out_cfg.pull_up_en   = GPIO_PULLUP_DISABLE;
    out_cfg.pull_down_en = GPIO_PULLDOWN_DISABLE;
    out_cfg.intr_type    = GPIO_INTR_DISABLE;
    out_cfg.pin_bit_mask =
        (1ULL << PIN_STOP) | (1ULL << PIN_PLAY) | (1ULL << PIN_FF) |
        (1ULL << PIN_REW)  | (1ULL << PIN_REC);
    gpio_config(&out_cfg);
    gpio_set_level(PIN_STOP, 0); gpio_set_level(PIN_PLAY, 0);
    gpio_set_level(PIN_FF,   0); gpio_set_level(PIN_REW,  0);
    gpio_set_level(PIN_REC,  0);

    // motion sensor input (any edge → ISR timestamp)
    gpio_config_t in_cfg = {};
    in_cfg.mode         = GPIO_MODE_INPUT;
    in_cfg.pull_up_en   = GPIO_PULLUP_DISABLE;   // sensor module usually has its own pull
    in_cfg.pull_down_en = GPIO_PULLDOWN_DISABLE;
    in_cfg.intr_type    = GPIO_INTR_ANYEDGE;
    in_cfg.pin_bit_mask = (1ULL << PIN_MOTION);
    gpio_config(&in_cfg);

    static bool s_isr_installed = false;
    if (!s_isr_installed) {
        gpio_install_isr_service(0);
        s_isr_installed = true;
    }
    gpio_isr_handler_add(PIN_MOTION, motion_isr, nullptr);

    ESP_LOGI(TAG, "begin: outputs ready; motion ISR on GPIO%d", (int)PIN_MOTION);
}

// Wait for reels to stop (with timeout) before engaging play/record.
static bool wait_reels_stopped(uint32_t timeout_ms = 8000) {
    if (reels_moving()) press(PIN_STOP);
    int64_t t0_us = esp_timer_get_time();
    while (reels_moving()) {
        if ((esp_timer_get_time() - t0_us) > (int64_t)timeout_ms * 1000LL) {
            ESP_LOGW(TAG, "reels still moving after %u ms — refusing play/record", (unsigned)timeout_ms);
            return false;
        }
        vTaskDelay(pdMS_TO_TICKS(20));
    }
    vTaskDelay(pdMS_TO_TICKS(POST_STOP_DELAY));
    return true;
}

static bool a77_do(const char* name) {
    if (!std::strcmp(name, "arm_record")) return true;  // core handles the window

    if (!std::strcmp(name, "stop"))   { press(PIN_STOP); return true; }
    if (!std::strcmp(name, "ff"))     { press(PIN_FF);   return true; }
    if (!std::strcmp(name, "rewind")) { press(PIN_REW);  return true; }

    if (!std::strcmp(name, "play")) {
        if (!wait_reels_stopped()) return false;
        press(PIN_PLAY);
        return true;
    }
    if (!std::strcmp(name, "record")) {
        if (!record_is_armed())      return false;
        if (!wait_reels_stopped())   return false;
        // REC = PLAY + REC asserted together for the press window
        gpio_set_level(PIN_REC,  1);
        gpio_set_level(PIN_PLAY, 1);
        vTaskDelay(pdMS_TO_TICKS(PRESS_MS));
        gpio_set_level(PIN_PLAY, 0);
        gpio_set_level(PIN_REC,  0);
        record_consume_arm();
        return true;
    }
    return false;
}

// publish reels_moving as a read-only value (bonus feedback)
static int64_t s_pub_us = 0;
static bool    s_last_moving = false;
static void a77_poll() {
    int64_t now = esp_timer_get_time();
    if ((now - s_pub_us) < 300000) return;  // ≥300 ms cadence
    s_pub_us = now;
    bool m = reels_moving();
    if (m != s_last_moving) {
        wb_publish_value("reels_moving", m ? "1" : "0", true);
        s_last_moving = m;
    }
}

static const Control A77_CTRLS[] = {
    {"stop",       CT_PUSHBUTTON, false},
    {"play",       CT_PUSHBUTTON, false},   // gated by motion interlock
    {"ff",         CT_PUSHBUTTON, false},
    {"rewind",     CT_PUSHBUTTON, false},
    {"arm_record", CT_PUSHBUTTON, false},
    {"record",     CT_PUSHBUTTON, true},    // PLAY+REC; armed + interlocked
};

// `extern` is required: a `const` at namespace scope has INTERNAL linkage in
// C++ (unlike C). Without `extern` the symbol can't be referenced from
// drivers.cpp's registry.
extern const DeviceDriver DRIVER_A77 = {
    "revox_a77", "Revox A77",
    A77_CTRLS, sizeof(A77_CTRLS) / sizeof(A77_CTRLS[0]),
    a77_begin, a77_do, a77_poll
};
