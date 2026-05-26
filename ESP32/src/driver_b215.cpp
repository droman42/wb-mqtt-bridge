// driver_b215.cpp — Revox B215 SERIAL LINK (ITT/Nokia baseband, device id 04).
// Output: open-collector on DIN pin 3 (DATA), referenced to pin 2 (floating GND).
// Idle high (deck pull-up); assert by pulling LOW. NEVER drive high.
// Optional: status read-back via a second opto on pin 3 -> input pin.
//
// FILL FROM YOUR SCOPE CAPTURES of the B205 remote on pin 3:
//   - LINK_INVERT, bit timing, and the per-function frame values (device id 04 + fn).
#include <Arduino.h>
#include "device_driver.h"

static const int  PIN_LINK   = 14;     // -> open-collector LED (pull pin3 LOW)
static const int  PIN_STATUS = 35;     // <- status opto (input-only pin OK); -1 to disable
static const bool LINK_INVERT = true;  // set after scoping line polarity

// ---- bit timing (us) — REPLACE from captures (~15 us-scale features) ----
static const uint16_t T_START   = 0;   // TODO start-bit width
static const uint16_t T_BIT0    = 0;   // TODO 0-bit period
static const uint16_t T_BIT1    = 0;   // TODO 1-bit period
static const uint16_t T_REPEAT  = 0;   // TODO inter-frame gap

// ---- command frames — REPLACE 0x0000 with captured values (device id 04 + fn) ----
struct Frame { const char* name; uint16_t frame; };
static Frame FR[] = {
  {"standby", 0x0000},
  {"stop",    0x0000},
  {"play",    0x0000},
  {"ff",      0x0000},
  {"rewind",  0x0000},
  {"record",  0x0000},
  {"pause",   0x0000},
};

static void linkAssert(bool low) {
  // low==true => pull DATA low (asserted). Respect LINK_INVERT at the pin.
  bool pinHigh = LINK_INVERT ? !low : low;
  digitalWrite(PIN_LINK, pinHigh ? HIGH : LOW);
}

// Bit-bang one frame. NOTE: exact framing (bit order, start, parity/stop) comes
// from YOUR captures; this is the structural skeleton.
static void sendLinkFrame(uint16_t frame) {
  noInterrupts();
  // start
  linkAssert(true);  delayMicroseconds(T_START ? T_START : 1);
  // data bits (MSB-first assumed; confirm from capture)
  for (int b = 15; b >= 0; b--) {
    bool bit = (frame >> b) & 1;
    linkAssert(true);                                   // leading edge
    delayMicroseconds(bit ? T_BIT1 : T_BIT0);
    linkAssert(false);                                  // release between bits
    delayMicroseconds(T_BIT0 ? T_BIT0 : 1);
  }
  linkAssert(false);
  interrupts();
}

static void b215_begin() {
  pinMode(PIN_LINK, OUTPUT);
  linkAssert(false);                 // idle (released; deck pull-up -> high)
  if (PIN_STATUS >= 0) pinMode(PIN_STATUS, INPUT_PULLUP);
}

static bool b215_do(const char* name) {
  if (!strcmp(name, "record") && !record_is_armed()) return false; // record safety
  for (auto& f : FR) if (!strcmp(f.name, name)) {
    sendLinkFrame(f.frame);
    if (!strcmp(name, "record")) record_consume_arm();
    return true;
  }
  if (!strcmp(name, "arm_record")) return true; // handled in core (sets arm window)
  return false;
}

// ---- optional status read-back ----
// Parse the deck's return frames on PIN_STATUS into MQTT value topics
// (play state, mm:ss counter). Skeleton: sample edges, decode, publish on change.
static uint32_t s_last = 0;
static void b215_poll() {
  if (PIN_STATUS < 0) return;
  if (millis() - s_last < 250) return;            // light cadence
  s_last = millis();
  // TODO: implement frame capture/decoding from your status-string format.
  // When decoded, e.g.:
  //   wb_publish_value("state", "play", true);
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
  {"record",     CT_PUSHBUTTON, true },
};

const DeviceDriver DRIVER_B215 = {
  "revox_b215", "Revox B215",
  B215_CTRLS, sizeof(B215_CTRLS)/sizeof(B215_CTRLS[0]),
  b215_begin, b215_do, b215_poll
};
