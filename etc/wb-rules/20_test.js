// ------------------Настройки системы вентиляции и кондиционирования-------------

defineVirtualDevice("HVAC_set_points", {
  title: "Уставки вентиляции",
  cells: {
    season_auto: {
      type: "switch",
      value: true
    },
    heat: {
      type: "switch",
      value: true,
	  readonly: true
    },
    cool: {
      type: "switch",
      value: false,
	  readonly: true
    },
    ventilation: {
      type: "switch",
      value: false,
	  readonly: true
    },
    humidity_01: {
      type: "range",
      value: 45,
      max : 100
    },
    humidifier: {
      type: "switch",
      value: false,
	  readonly: true
    },
    CO2_01: {
      type: "range",
      value: 450,
      max : 1000
    },
    air_conditioner: {
      type: "switch",
      value: false,
	  readonly: true
    }
  }
});


defineRule("HVAC control", {
	whenChanged: ["HVAC_set_points/season_auto"],
	then: function(newValue, devName, cellName) {
		var command;
		if (dev["HVAC_set_points/season_auto"]) {
			log.debug ("Сезонный режим 'Auto' включен!");
			command = "mosquitto_pub -t '/devices/HVAC_set_points/controls/cool/meta/readonly' -m 1";
			runShellCommand(command);			//Команда для установки readonly
			command = "mosquitto_pub -t '/devices/HVAC_set_points/controls/heat/meta/readonly' -m 1";
			runShellCommand(command);			//Команда для установки readonly
			command = "mosquitto_pub -t '/devices/HVAC_set_points/controls/ventilation/meta/readonly' -m 1";
			runShellCommand(command);			//Команда для установки readonly

			if (dev["Sc01/Temperature"] > (dev["HVAC/SP temperature"] + tempDeviation)) { // Температура воздуха в Гостиной больше уставки - охладить
				if(dev["HVAC/outdoor temperature"] > (dev["HVAC/SP temperature"] - 2 + tempDeviation)) { // Кондиционер включить, если внутри жарче чем уставка более чем на 2 градуса
					dev["HVAC_set_points/cool"] = true;
					dev["HVAC/Set unit heat-cool mode"] = 4;
					log.debug("'Охлаждение'!");
				}
				if(dev["HVAC/outdoor temperature"] < (dev["HVAC/SP temperature"] - 2 - tempDeviation)){ // Кондиционер выключен. Используем наружную температуру для охлаждения
					dev["HVAC_set_points/ventilation"] = true;
					dev["HVAC/Set unit heat-cool mode"] = 1;
					log.debug("'Вентиляция'!");
				}
			}

			if (dev["Sc01/Temperature"] < (dev["HVAC/SP temperature"] - tempDeviation)) { // Температура воздуха в Гостиной меньше уставки - нагреть
				if(dev["HVAC/outdoor temperature"] < (dev["HVAC/SP temperature"] + 2 - tempDeviation)) { // Нагреватель включить
					dev["HVAC_set_points/heat"] = true;
					dev["HVAC/Set unit heat-cool mode"] = 2;
					log.debug("'Нагрев'!");
				}
				if(dev["HVAC/outdoor temperature"] > (dev["HVAC/SP temperature"] + 2 + tempDeviation)) { // Нагреватель выключен. Используем наружную температуру для нагрева
					dev["HVAC_set_points/ventilation"] = true;
					dev["HVAC/Set unit heat-cool mode"] = 1;
					log.debug("'Вентиляция'!");
				}
			}
		} else {
//			log ("Сезонный режим 'Auto' отключен!");
			command = "mosquitto_pub -t '/devices/HVAC_set_points/controls/cool/meta/readonly' -m 0";
			runShellCommand(command);			//Команда для установки readonly
			command = "mosquitto_pub -t '/devices/HVAC_set_points/controls/heat/meta/readonly' -m 0";
			runShellCommand(command);			//Команда для установки readonly
			command = "mosquitto_pub -t '/devices/HVAC_set_points/controls/ventilation/meta/readonly' -m 0";
			runShellCommand(command);			//Команда для установки readonly
		}
	}
});

// Переключение режима работы ПВУ в зависимости от положения переключателей

defineRule("season", {
	whenChanged: ["HVAC_set_points/ventilation", "HVAC_set_points/heat", "HVAC_set_points/cool"],
	then: function(newValue, devName, cellName) {
		if (newValue) {
			if (cellName == "heat") {  // Нагрев
				dev["HVAC_set_points/cool"] = false;
				dev["HVAC_set_points/ventilation"] = false;
				if (newValue) {
					dev["HVAC/Set unit heat-cool mode"] = 2;
				}
				log(" - Сезонный режим 'Нагрев': " + dev["HVAC_set_points/heat"]);
				return;
			}
			if (cellName == "cool") { // Охлаждение
				dev["HVAC_set_points/heat"] = false;
				dev["HVAC_set_points/ventilation"] = false;
				if (newValue) { 
					dev["HVAC/Set unit heat-cool mode"] = 4;
				}
				log(" - Сезонный режим 'Охлаждение': " + dev["HVAC_set_points/cool"]);
				return;
			} 
			if (cellName == "ventilation") { // Вентиляция
				dev["HVAC_set_points/cool"] = false;
				dev["HVAC_set_points/heat"] = false;
				if (newValue) {
					dev["HVAC/Set unit heat-cool mode"] = 1;
				}
				log(" - Сезонный режим 'Вентиляция': " + dev["HVAC_set_points/ventilation"]);
				return;
			}
		}
	}
});