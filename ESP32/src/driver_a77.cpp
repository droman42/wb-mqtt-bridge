// driver_a77.cpp — Revox A77 remote contacts via opto-MOSFETs across WIST-10 pin-pairs.
// Each function = close a pin-pair for a momentary press. RECORD = PLAY+REC together,
// gated by record-arming. Rewind-safety: refuse PLAY/RECORD until reels have stopped
// (added reel-motion sensor; the A77 has none of its own).
#include <Arduino.h>
#include "device_driver.h"

// ---- opto-MOSFET drive pins (one per function) ----
static const int PIN_STOP   = 14;   // closes pins 1<->2
static const int PIN_PLAY   = 27;   // closes pins 4<->5
static const int PIN_FF     = 26;   // closes pins 10<->3
static const int PIN_REW    = 25;   // closes pins 8<->9
static const int PIN_REC    = 33;   // closes pin 6 (asserted WITH play)
static const int PIN_MOTION = 34;   // <- reel-motion sensor (input-only pin OK)

static const uint16_t PRESS_MS = 200;     // momentary press width (tune)

// ---- reel-motion interlock constants (TUNE on bench) ----
static const uint32_t MOTION_WINDOW_MS = 400;   // "moving" if a pulse seen within this
static const uint32_t POST_STOP_DELAY  = 500;   // B77-style settle after reels stop
static volatile uint32_t s_last_pulse  = 0;

static void IRAM_ATTR motionISR() { s_last_pulse = millis(); }
static bool reelsMoving() { return (millis() - s_last_pulse) < MOTION_WINDOW_MS; }

static void press(int pin) {
  digitalWrite(pin, HIGH);
  delay(PRESS_MS);
  digitalWrite(pin, LOW);
}

static void a77_begin() {
  for (int p : {PIN_STOP, PIN_PLAY, PIN_FF, PIN_REW, PIN_REC}) {
    pinMode(p, OUTPUT); digitalWrite(p, LOW);
  }
  pinMode(PIN_MOTION, INPUT);                 // sensor module usually has its own pull
  attachInterrupt(PIN_MOTION, motionISR, CHANGE);
}

// Wait for reels to stop (with timeout) before engaging play/record.
static bool waitReelsStopped(uint32_t timeout_ms = 8000) {
  if (reelsMoving()) press(PIN_STOP);          // assert STOP if still winding
  uint32_t t0 = millis();
  while (reelsMoving()) {
    if (millis() - t0 > timeout_ms) return false;   // gave up; refuse to play
    delay(20);
  }
  delay(POST_STOP_DELAY);                      // settle
  return true;
}

static bool a77_do(const char* name) {
  if (!strcmp(name, "arm_record")) return true; // core sets arm window

  if (!strcmp(name, "stop"))   { press(PIN_STOP); return true; }
  if (!strcmp(name, "ff"))     { press(PIN_FF);   return true; }
  if (!strcmp(name, "rewind")) { press(PIN_REW);  return true; }

  if (!strcmp(name, "play")) {
    if (!waitReelsStopped()) return false;     // interlock blocked it
    press(PIN_PLAY);
    return true;
  }
  if (!strcmp(name, "record")) {
    if (!record_is_armed()) return false;      // record safety
    if (!waitReelsStopped()) return false;     // interlock
    // REC = PLAY + REC asserted together
    digitalWrite(PIN_REC, HIGH);
    digitalWrite(PIN_PLAY, HIGH);
    delay(PRESS_MS);
    digitalWrite(PIN_PLAY, LOW);
    digitalWrite(PIN_REC, LOW);
    record_consume_arm();
    return true;
  }
  return false;
}

// publish reels_moving as a read-only value (bonus feedback)
static uint32_t s_pub = 0; static bool s_last_moving = false;
static void a77_poll() {
  if (millis() - s_pub < 300) return;
  s_pub = millis();
  bool m = reelsMoving();
  if (m != s_last_moving) { wb_publish_value("reels_moving", m ? "1":"0", true); s_last_moving = m; }
}

static const Control A77_CTRLS[] = {
  {"stop",       CT_PUSHBUTTON, false},
  {"play",       CT_PUSHBUTTON, false},   // gated by motion interlock
  {"ff",         CT_PUSHBUTTON, false},
  {"rewind",     CT_PUSHBUTTON, false},
  {"arm_record", CT_PUSHBUTTON, false},
  {"record",     CT_PUSHBUTTON, true },   // PLAY+REC, armed + interlocked
};

const DeviceDriver DRIVER_A77 = {
  "revox_a77", "Revox A77",
  A77_CTRLS, sizeof(A77_CTRLS)/sizeof(A77_CTRLS[0]),
  a77_begin, a77_do, a77_poll
};
