// driver_ir.cpp — baseband IR emit, shared by Pioneer CLD-D925 and Panasonic NV-FS90.
// Replays the deck's own remote codes WITHOUT the 38 kHz carrier, onto an
// open-collector stage driving the control jack (Pioneer CONTROL IN) or the
// tapped IR-receiver output node (Panasonic). Idle HIGH, assert LOW (active-low).
//
// CODES: reuse the codes you already proved with the Wirenboard IR blaster.
// Two ways to fill the tables below:
//   (A) decoded protocol+value -> use a send library with carrier OFF, OR
//   (B) raw mark/space timings (us) -> replay directly as below (simplest, no deps).
// Only change vs a blaster: NO CARRIER. Data/timing/repeat are identical.
#include <Arduino.h>
#include "device_driver.h"

// ---- output pin (open-collector stage onto the jack/IR-OUT net) ----
static const int PIN_IR    = 14;     // GPIO -> open-collector (pull LOW = mark)
static const bool IR_INVERT = true;  // baseband IR active-low: mark => LOW

// ===================== CAPTURED CODES (FILL FROM YOUR BLASTER) =====================
// Each command = raw mark/space pairs in microseconds (carrier stripped).
// Example placeholder timings — REPLACE with your exported blaster codes.
// (NEC-style header shown for shape only.)
struct RawCmd { const char* name; const uint16_t* t; uint8_t len; };

// --- Pioneer CLD-D925 ---
static const uint16_t pio_play[]  = { 9000,4500, 560,560 /* ...REPLACE... */ };
static const uint16_t pio_pause[] = { 9000,4500, 560,560 /* ...REPLACE... */ };
static const uint16_t pio_stop[]  = { 9000,4500, 560,560 /* ...REPLACE... */ };
static const uint16_t pio_scanf[] = { 9000,4500, 560,560 /* ...REPLACE... */ };
static const uint16_t pio_scanr[] = { 9000,4500, 560,560 /* ...REPLACE... */ };
static const uint16_t pio_chapn[] = { 9000,4500, 560,560 /* ...REPLACE... */ };
static const uint16_t pio_chapp[] = { 9000,4500, 560,560 /* ...REPLACE... */ };
static const uint16_t pio_power[] = { 9000,4500, 560,560 /* ...REPLACE... */ };

static const RawCmd PIO[] = {
  {"power",   pio_power, sizeof(pio_power)/2},
  {"play",    pio_play,  sizeof(pio_play)/2},
  {"pause",   pio_pause, sizeof(pio_pause)/2},
  {"stop",    pio_stop,  sizeof(pio_stop)/2},
  {"scan_fwd",pio_scanf, sizeof(pio_scanf)/2},
  {"scan_rev",pio_scanr, sizeof(pio_scanr)/2},
  {"chapter_next", pio_chapn, sizeof(pio_chapn)/2},
  {"chapter_prev", pio_chapp, sizeof(pio_chapp)/2},
};

// --- Panasonic NV-FS90 (Kaseikyo/"Panasonic" 48-bit family typically) ---
static const uint16_t pan_play[]  = { 3500,1750, 440,440 /* ...REPLACE... */ };
static const uint16_t pan_stop[]  = { 3500,1750, 440,440 /* ...REPLACE... */ };
static const uint16_t pan_pause[] = { 3500,1750, 440,440 /* ...REPLACE... */ };
static const uint16_t pan_ff[]    = { 3500,1750, 440,440 /* ...REPLACE... */ };
static const uint16_t pan_rew[]   = { 3500,1750, 440,440 /* ...REPLACE... */ };
static const uint16_t pan_rec[]   = { 3500,1750, 440,440 /* ...REPLACE... */ };
static const uint16_t pan_power[] = { 3500,1750, 440,440 /* ...REPLACE... */ };

static const RawCmd PAN[] = {
  {"power", pan_power, sizeof(pan_power)/2},
  {"play",  pan_play,  sizeof(pan_play)/2},
  {"stop",  pan_stop,  sizeof(pan_stop)/2},
  {"pause", pan_pause, sizeof(pan_pause)/2},
  {"ff",    pan_ff,    sizeof(pan_ff)/2},
  {"rewind",pan_rew,   sizeof(pan_rew)/2},
  {"record",pan_rec,   sizeof(pan_rec)/2},   // gated by record-arming in doCommand
};
// =================================================================================

static void emitBaseband(const uint16_t* t, uint8_t len) {
  // mark = even index (would-be carrier burst) -> pull LOW; space -> release HIGH
  noInterrupts();
  for (uint8_t i = 0; i < len; i++) {
    bool mark  = (i % 2 == 0);
    bool level = IR_INVERT ? !mark : mark;     // mark => LOW
    digitalWrite(PIN_IR, level ? HIGH : LOW);
    delayMicroseconds(t[i]);
  }
  digitalWrite(PIN_IR, IR_INVERT ? HIGH : LOW); // idle released HIGH
  interrupts();
}

static const RawCmd* findCmd(const RawCmd* tab, uint8_t n, const char* name) {
  for (uint8_t i = 0; i < n; i++) if (!strcmp(tab[i].name, name)) return &tab[i];
  return nullptr;
}

// ---------- begin ----------
static void ir_begin() {
  pinMode(PIN_IR, OUTPUT);
  digitalWrite(PIN_IR, IR_INVERT ? HIGH : LOW); // idle
}

// ---------- doCommand (Pioneer) ----------
static bool pio_do(const char* name) {
  const RawCmd* c = findCmd(PIO, sizeof(PIO)/sizeof(PIO[0]), name);
  if (!c) return false;
  emitBaseband(c->t, c->len);
  // Pioneer: some commands want a repeat frame; replay once more if needed:
  // emitBaseband(c->t, c->len);
  return true;
}

// ---------- doCommand (Panasonic) ----------
static bool pan_do(const char* name) {
  if (!strcmp(name, "record") && !record_is_armed()) return false; // record safety
  const RawCmd* c = findCmd(PAN, sizeof(PAN)/sizeof(PAN[0]), name);
  if (!c) return false;
  emitBaseband(c->t, c->len);
  if (!strcmp(name, "record")) record_consume_arm();
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
  {"arm_record", CT_PUSHBUTTON, false},   // press to arm, then record within window
  {"record",     CT_PUSHBUTTON, true },
};

const DeviceDriver DRIVER_PIONEER = {
  "pioneer_cld_d925", "Pioneer CLD-D925",
  PIO_CTRLS, sizeof(PIO_CTRLS)/sizeof(PIO_CTRLS[0]),
  ir_begin, pio_do, nullptr
};
const DeviceDriver DRIVER_PANASONIC = {
  "panasonic_nv_fs90", "Panasonic NV-FS90",
  PAN_CTRLS, sizeof(PAN_CTRLS)/sizeof(PAN_CTRLS[0]),
  ir_begin, pan_do, nullptr
};
