// Kitchen hood management

// ------------------Virtual device to support kitchen hood-------------

defineVirtualDevice("Kitchen_Hood_Control", {
    title: "Контроль за вытяжкой",
    cells: {
      light: {
        type: "switch",
        value: false
      },
      fanPower: {
        type: "range",
        readOnly: false,
        max: 4,
        value: 0
      }
    }
  });

var switch_pressed = false;
// Ручное управление положением правой роллшторы в Кабинете по нажатию на настенный выключатель
defineRule("Kitchen Light Switch Control", {
	whenChanged: ["wb-gpio/EXT2_IN1", "wb-gpio/EXT2_IN2"],
	then: function(newValue, devName, cellName) {
		if (newValue) {
			log("Нажата кнопка {}  (повторно: {})", cellName, switch_pressed);
			if (!switch_pressed) {
	 			dev["Kitchen_Hood_Control/light"] = true;
	 			switch_pressed = true;
	 			startTimer("next_press_hood", 60 * 1000);
			} else {
				dev["Kitchen_Hood_Control/light"] = false;
			    switch_pressed = false;
			    timers.next_press_hood.stop();
			}	
		}
	}
}); 

