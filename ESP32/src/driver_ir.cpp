// driver_ir.cpp — baseband IR emit, shared by Pioneer CLD-D925 and
// Panasonic NV-FS90. Replays the deck's own remote codes WITHOUT the 38 kHz
// carrier, onto an open-collector stage driving the control jack (Pioneer
// CONTROL IN) or the tapped IR-receiver output node (Panasonic). Idle HIGH,
// assert LOW (active-low).
//
// CODES: lift from your Wirenboard IR-blaster captures — same mark/space
// timings, with the carrier stripped. Two equivalent shapes:
//   (A) decoded protocol+value → send via a library with carrier OFF.
//   (B) raw mark/space (µs) → replay directly (chosen here — simplest, no deps).
//
// FILL TABLES below with your captures.
#include "device_driver.h"
#include "driver/gpio.h"
#include "esp_attr.h"
#include "esp_log.h"
#include "esp_rom_sys.h"     // esp_rom_delay_us
#include "freertos/FreeRTOS.h"
#include <cstdint>
#include <cstring>

static const char* TAG = "ir";

static const gpio_num_t PIN_IR    = GPIO_NUM_14;   // open-collector stage → jack / IR-OUT net
static const bool       IR_INVERT = true;          // baseband IR active-low: mark → LOW

// ===================== CAPTURED CODES (FILL FROM YOUR BLASTER) =====================
// Each command = raw mark/space pairs in microseconds (CARRIER STRIPPED).
// REPLACE the placeholder timings with your exported blaster codes.
// (NEC-style header shown for shape only.)
struct RawCmd { const char* name; const uint16_t* t; uint8_t len; };

// --- Pioneer CLD-D925 ---
static const uint16_t pio_play[]  = { 9000, 4500, 560, 560 /* …REPLACE… */ };
static const uint16_t pio_pause[] = { 9000, 4500, 560, 560 /* …REPLACE… */ };
static const uint16_t pio_stop[]  = { 9000, 4500, 560, 560 /* …REPLACE… */ };
static const uint16_t pio_scanf[] = { 9000, 4500, 560, 560 /* …REPLACE… */ };
static const uint16_t pio_scanr[] = { 9000, 4500, 560, 560 /* …REPLACE… */ };
static const uint16_t pio_chapn[] = { 9000, 4500, 560, 560 /* …REPLACE… */ };
static const uint16_t pio_chapp[] = { 9000, 4500, 560, 560 /* …REPLACE… */ };
static const uint16_t pio_power[] = { 9000, 4500, 560, 560 /* …REPLACE… */ };

static const RawCmd PIO[] = {
    {"power",        pio_power, sizeof(pio_power) / 2},
    {"play",         pio_play,  sizeof(pio_play)  / 2},
    {"pause",        pio_pause, sizeof(pio_pause) / 2},
    {"stop",         pio_stop,  sizeof(pio_stop)  / 2},
    {"scan_fwd",     pio_scanf, sizeof(pio_scanf) / 2},
    {"scan_rev",     pio_scanr, sizeof(pio_scanr) / 2},
    {"chapter_next", pio_chapn, sizeof(pio_chapn) / 2},
    {"chapter_prev", pio_chapp, sizeof(pio_chapp) / 2},
};

// --- Panasonic NV-FS90 (Kaseikyo/"Panasonic" 48-bit family typically) ---
static const uint16_t pan_play[]  = { 3500, 1750, 440, 440 /* …REPLACE… */ };
static const uint16_t pan_stop[]  = { 3500, 1750, 440, 440 /* …REPLACE… */ };
static const uint16_t pan_pause[] = { 3500, 1750, 440, 440 /* …REPLACE… */ };
static const uint16_t pan_ff[]    = { 3500, 1750, 440, 440 /* …REPLACE… */ };
static const uint16_t pan_rew[]   = { 3500, 1750, 440, 440 /* …REPLACE… */ };
static const uint16_t pan_rec[]   = { 3500, 1750, 440, 440 /* …REPLACE… */ };
static const uint16_t pan_power[] = { 3500, 1750, 440, 440 /* …REPLACE… */ };

static const RawCmd PAN[] = {
    {"power",  pan_power, sizeof(pan_power) / 2},
    {"play",   pan_play,  sizeof(pan_play)  / 2},
    {"stop",   pan_stop,  sizeof(pan_stop)  / 2},
    {"pause",  pan_pause, sizeof(pan_pause) / 2},
    {"ff",     pan_ff,    sizeof(pan_ff)    / 2},
    {"rewind", pan_rew,   sizeof(pan_rew)   / 2},
    {"record", pan_rec,   sizeof(pan_rec)   / 2},  // gated by record-arming
};
// ==================================================================================

static IRAM_ATTR void emit_baseband(const uint16_t* t, uint8_t len) {
    // even index = mark (would-be carrier burst → pull LOW); odd = space (release HIGH)
    portDISABLE_INTERRUPTS();
    for (uint8_t i = 0; i < len; i++) {
        bool mark  = (i % 2 == 0);
        bool level = IR_INVERT ? !mark : mark;       // mark → LOW
        gpio_set_level(PIN_IR, level ? 1 : 0);
        esp_rom_delay_us(t[i]);
    }
    gpio_set_level(PIN_IR, IR_INVERT ? 1 : 0);       // idle released HIGH
    portENABLE_INTERRUPTS();
}

static const RawCmd* find_cmd(const RawCmd* tab, uint8_t n, const char* name) {
    for (uint8_t i = 0; i < n; i++) {
        if (std::strcmp(tab[i].name, name) == 0) return &tab[i];
    }
    return nullptr;
}

static void ir_begin() {
    gpio_config_t out = {};
    out.mode         = GPIO_MODE_OUTPUT;
    out.pin_bit_mask = (1ULL << PIN_IR);
    out.pull_up_en   = GPIO_PULLUP_DISABLE;
    out.pull_down_en = GPIO_PULLDOWN_DISABLE;
    out.intr_type    = GPIO_INTR_DISABLE;
    gpio_config(&out);
    gpio_set_level(PIN_IR, IR_INVERT ? 1 : 0);       // idle
    ESP_LOGI(TAG, "begin: PIN_IR=GPIO%d (inv=%d)", (int)PIN_IR, (int)IR_INVERT);
}

// ---------- doCommand (Pioneer) ----------
static bool pio_do(const char* name) {
    const RawCmd* c = find_cmd(PIO, sizeof(PIO) / sizeof(PIO[0]), name);
    if (!c) return false;
    emit_baseband(c->t, c->len);
    // Pioneer: some commands want a repeat frame; replay once more if needed:
    //   emit_baseband(c->t, c->len);
    return true;
}

// ---------- doCommand (Panasonic) ----------
static bool pan_do(const char* name) {
    if (!std::strcmp(name, "arm_record")) return true;
    if (!std::strcmp(name, "record") && !record_is_armed()) return false;
    const RawCmd* c = find_cmd(PAN, sizeof(PAN) / sizeof(PAN[0]), name);
    if (!c) return false;
    emit_baseband(c->t, c->len);
    if (!std::strcmp(name, "record")) record_consume_arm();
    return true;
}

// ---------- control tables ----------
static const Control PIO_CTRLS[] = {
    {"power",        CT_SWITCH,     false},
    {"play",         CT_PUSHBUTTON, false},
    {"pause",        CT_PUSHBUTTON, false},
    {"stop",         CT_PUSHBUTTON, false},
    {"scan_fwd",     CT_PUSHBUTTON, false},
    {"scan_rev",     CT_PUSHBUTTON, false},
    {"chapter_next", CT_PUSHBUTTON, false},
    {"chapter_prev", CT_PUSHBUTTON, false},
};
static const Control PAN_CTRLS[] = {
    {"power",      CT_SWITCH,     false},
    {"play",       CT_PUSHBUTTON, false},
    {"stop",       CT_PUSHBUTTON, false},
    {"pause",      CT_PUSHBUTTON, false},
    {"ff",         CT_PUSHBUTTON, false},
    {"rewind",     CT_PUSHBUTTON, false},
    {"arm_record", CT_PUSHBUTTON, false},  // arm, then `record` within window
    {"record",     CT_PUSHBUTTON, true},
};

extern const DeviceDriver DRIVER_PIONEER = {   // `extern` so drivers.cpp's registry can find us (C++ rule)
    "pioneer_cld_d925", "Pioneer CLD-D925",
    PIO_CTRLS, sizeof(PIO_CTRLS) / sizeof(PIO_CTRLS[0]),
    ir_begin, pio_do, nullptr
};
extern const DeviceDriver DRIVER_PANASONIC = {
    "panasonic_nv_fs90", "Panasonic NV-FS90",
    PAN_CTRLS, sizeof(PAN_CTRLS) / sizeof(PAN_CTRLS[0]),
    ir_begin, pan_do, nullptr
};
