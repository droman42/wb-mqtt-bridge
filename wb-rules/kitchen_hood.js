// Kitchen hood management

// ------------------Virtual device to support kitchen hood-------------

defineVirtualDevice("kitchen_hood", {
    title: "Контроль за вытяжкой",
    cells: {
      light: {
        type: "switch",
		readOnly: false,
        value: false
      },
      speed: {
        type: "range",
        readOnly: false,
        max: 4,
        value: 0
      }
    }
  });

// Debounce configuration
var THROTTLE_TIME = 10000; // 10 seconds in milliseconds
var lastSwitchState = false;
var throttleLock = false;

// Kitchen hood light control with debounce
defineRule("Kitchen Light Switch Control", {
    whenChanged: ["wb-gpio/EXT2_IN1"],
    then: function(newValue, devName, cellName) {
		if (newValue) {
			if (throttleLock) {
				// Игнорируем, если блокировка активна
				log("Throttle: сигнал проигнорирован");
				return;
			}            
			// Обрабатываем сигнал сразу
			log("Throttle: обрабатываем значение: " + newValue);
			// Здесь логика твоего действия:
			// log("Было: " + dev["kitchen_hood/light"]);
			dev["kitchen_hood/light"] = !lastSwitchState;
			lastSwitchState = !lastSwitchState;
			// log("Стало: " + dev["kitchen_hood/light"]);
			// Устанавливаем блокировку на THROTTLE_TIME
			throttleLock = true;
			setTimeout(function () {
				throttleLock = false;
				log("Throttle: снова готов к приёму событий");
			}, THROTTLE_TIME); // Время throttle в мс
		}
	}
}); 

