// Define virtual devices for AV equipment control

// Musical Fidelity M6si Integrated Amplifier
defineVirtualDevice("amplifier", {
    title: "Musical Fideliy M6si",
    cells: {
      // Power control
      power_toggle: {
        type: "pushbutton",
        value: false
      },
      // Volume controls
      volume_up: {
        type: "pushbutton",
        value: false
      },
      volume_down: {
        type: "pushbutton",
        value: false
      },
      // Mute function
      mute: {
        type: "pushbutton",
        value: false
      },
      // Input selection controls
      cd: {
        type: "pushbutton",
        value: false
      },
      usb: {
        type: "pushbutton",
        value: false
      },
      phono: {
        type: "pushbutton",
        value: false
      },
      tuner: {
        type: "pushbutton",
        value: false
      },
      aux1: {
        type: "pushbutton",
        value: false
      },
      aux2: {
        type: "pushbutton",
        value: false
      },
      balanced: {
        type: "pushbutton",
        value: false
      }
    }
  });

  // Pioneer CLD-D925 Laserdisc Player
  defineVirtualDevice("ld_player", {
    title: "Pioneer CLD-D925",
    cells: {
      // Power control
      power_toggle: {
        type: "pushbutton",
        value: false
      },
      // Disc tray control
      tray: {
        type: "pushbutton",
        value: false
      },
      // Playback controls
      play: {
        type: "pushbutton",
        value: false
      },
      stop: {
        type: "pushbutton",
        value: false
      },
      pause: {
        type: "pushbutton",
        value: false
      },
      // Chapter navigation
      chapter_plus: {
        type: "pushbutton",
        value: false
      },
      chapter_minus: {
        type: "pushbutton",
        value: false
      },
      // Audio track selection
      audio: {
        type: "pushbutton",
        value: false
      }
    }
  });

  // DVDO Edge Green Video Processor
  defineVirtualDevice("upscaler", {
    title: "DVDO Edge Green",
    cells: {
      // Power controls
      power_on: {
        type: "pushbutton",
        value: false
      },
      power_off: {
        type: "pushbutton",
        value: false
      },
      // Input selection
      input_video: {
        type: "pushbutton",
        value: false
      },
      input_s_vhs: {
        type: "pushbutton",
        value: false
      },
      // Aspect ratio controls
      ratio_4_3: {
        type: "pushbutton",
        value: false
      },
      ratio_16_9: {
        type: "pushbutton",
        value: false
      },
      letterbox: {
        type: "pushbutton",
        value: false
      },
      // Menu navigation controls
      menu: {
        type: "pushbutton",
        value: false
      },
      menu_exit: {
        type: "pushbutton",
        value: false
      },
      menu_up: {
        type: "pushbutton",
        value: false
      },
      menu_down: {
        type: "pushbutton",
        value: false
      },
      menu_left: {
        type: "pushbutton",
        value: false
      },
      menu_right: {
        type: "pushbutton",
        value: false
      },
      ok_enter: {
        type: "pushbutton",
        value: false
      }
    }
  });

  // Zappiti Neo Media Player
  defineVirtualDevice("video", {
    title: "Zappiti Neo",
    cells: {
      // Power controls
      power_on: {
        type: "pushbutton",
        value: false
      },
      power_off: {
        type: "pushbutton",
        value: false
      },
      // Playback controls
      play_pause: {
        type: "pushbutton",
        value: false
      },
      chapter_plus: {
        type: "pushbutton",
        value: false
      },
      chapter_minus: {
        type: "pushbutton",
        value: false
      },
      stop: {
        type: "pushbutton",
        value: false
      },
      // Navigation controls
      up: {
        type: "pushbutton",
        value: false
      },
      down: {
        type: "pushbutton",
        value: false
      },
      left: {
        type: "pushbutton",
        value: false
      },
      right: {
        type: "pushbutton",
        value: false
      },
      ok_enter: {
        type: "pushbutton",
        value: false
      },
      // Media controls
      audio: {
        type: "pushbutton",
        value: false
      },
      subtitles: {
        type: "pushbutton",
        value: false
      },
      // System controls
      home : {
        type: "pushbutton",
        value: false
      },
      settings: {
        type: "pushbutton",
        value: false
      },
      back: {
        type: "pushbutton",
        value: false
      },
      zappiti: {
        type: "pushbutton",
        value: false
      },
      explorer: {
        type: "pushbutton",
        value: false
      }
    }
  });

  // Auralic Altair G1 Streamer
  defineVirtualDevice("streamer", {
    title: "Auralic Altair G1",
    cells: {
      // Power control
      power_toggle: {
        type: "pushbutton",
        value: false
      },
      // Input selection
      input_stream: {
        type: "pushbutton",
        value: false
      }
    }
  });

