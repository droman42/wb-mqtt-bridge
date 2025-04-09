// Define virtual device for Musical Fidelity M6si integrated amplifier
defineVirtualDevice("amplifier", {
    title: "Musical Fideliy M6si",
    cells: {
      // Toggle power state of the amplifier
      power_toggle: {
        type: "pushbutton",
        value: false
      },
      // Increase volume level
      volume_up: {
        type: "pushbutton",
        value: false
      },
      // Decrease volume level
      volume_down: {
        type: "pushbutton",
        value: false
      },
      // Toggle mute state
      mute: {
        type: "pushbutton",
        value: false
      },
      // Select CD input source
      cd: {
        type: "pushbutton",
        value: false
      },
      // Select USB input source
      usb: {
        type: "pushbutton",
        value: false
      },
      // Select phono input source
      phono: {
        type: "pushbutton",
        value: false
      },
      // Select tuner input source
      tuner: {
        type: "pushbutton",
        value: false
      },
      // Select AUX 1 input source
      aux1: {
        type: "pushbutton",
        value: false
      },
      // Select AUX 2 input source
      aux2: {
        type: "pushbutton",
        value: false
      },
      // Select balanced input source
      balanced: {
        type: "pushbutton",
        value: false
      }
    }
  });

  // Define virtual device for Pioneer CLD-D925 Laserdisc player
  defineVirtualDevice("ld_player", {
    title: "Pioneer CLD-D925",
    cells: {
      // Toggle power state of the player
      power_toggle: {
        type: "pushbutton",
        value: false
      },
      // Open/close disc tray
      tray: {
        type: "pushbutton",
        value: false
      },
      // Start playback
      play: {
        type: "pushbutton",
        value: false
      },
      // Stop playback
      stop: {
        type: "pushbutton",
        value: false
      },
      // Pause/resume playback
      pause: {
        type: "pushbutton",
        value: false
      },
      // Skip to next chapter
      chapter_plus: {
        type: "pushbutton",
        value: false
      },
      // Skip to previous chapter
      chapter_minus: {
        type: "pushbutton",
        value: false
      },
      // Toggle audio mode
      audio: {
        type: "pushbutton",
        value: false
      }
    }
  });

  // Define virtual device for DVDO Edge Green video processor/upscaler
  defineVirtualDevice("upscaler", {
    title: "DVDO Edge Green",
    cells: {
      // Turn on the upscaler
      power_on: {
        type: "pushbutton",
        value: false
      },
      // Turn off the upscaler
      power_off: {
        type: "pushbutton",
        value: false
      },
      // Select video input
      input_video: {
        type: "pushbutton",
        value: false
      },
      // Select S-VHS input
      input_s_vhs: {
        type: "pushbutton",
        value: false
      },
      // Set aspect ratio to 4:3
      ratio_4_3: {
        type: "pushbutton",
        value: false
      },
      // Set aspect ratio to 16:9
      ratio_16_9: {
        type: "pushbutton",
        value: false
      },
      // Toggle letterbox mode
      letterbox: {
        type: "pushbutton",
        value: false
      },
      // Open main menu
      menu: {
        type: "pushbutton",
        value: false
      },
      // Exit menu
      menu_exit: {
        type: "pushbutton",
        value: false
      },
      // Navigate menu up
      menu_up: {
        type: "pushbutton",
        value: false
      },
      // Navigate menu down
      menu_down: {
        type: "pushbutton",
        value: false
      },
      // Navigate menu left
      menu_left: {
        type: "pushbutton",
        value: false
      },
      // Navigate menu right
      menu_right: {
        type: "pushbutton",
        value: false
      },
      // Confirm menu selection
      ok_enter: {
        type: "pushbutton",
        value: false
      }
    }
  });
