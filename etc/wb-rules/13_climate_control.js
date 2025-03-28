defineVirtualDevice("seasonal_switch", {
  title: "Подключение отопления и кондиционеров",
  cells: {
    heating: {
      type: "switch",
      value: true,
	readonly: false
    },
    cooling: {
      type: "switch",
      value: false,
	readonly: false
    }
  }
});

defineRule("set_heating_on", {
	whenChanged: "seasonal_switch/heating",
	then: function(newValue, devName, cellName) { //  Всё включено	
		if (newValue) {
			// Кондиционер выключаем
			dev["seasonal_switch"]["cooling"] = false;
			// Разрешаем расписания
			runShellCommand("mosquitto_pub -t '/devices/setpoints_radiator/controls/bedroom_permit_schedule/meta/readonly' -m 0");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_radiator/controls/cabinet_permit_schedule/meta/readonly' -m 0");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_radiator/controls/children_permit_schedule/meta/readonly' -m 0");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_radiator/controls/livingroom_permit_schedule/meta/readonly' -m 0");			
			runShellCommand("mosquitto_pub -t '/devices/setpoints_floor/controls/kitchen_permit_schedule/meta/readonly' -m 0");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_floor/controls/entrance_permit_schedule/meta/readonly' -m 0");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_floor/controls/cabinet1_permit_schedule/meta/readonly' -m 0");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_floor/controls/cabinet2_permit_schedule/meta/readonly' -m 0");
			// Разрешаем менять уставки температуры полов
			runShellCommand("mosquitto_pub -t '/devices/setpoints_floor/controls/kitchen_temp/meta/readonly' -m 0");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_floor/controls/entrance_temp/meta/readonly' -m 0");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_floor/controls/cabinet1_temp/meta/readonly' -m 0");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_floor/controls/cabinet2_temp/meta/readonly' -m 0");
          	// Разрешаем включение тёплых полов и конвекторов на панели
			runShellCommand("mosquitto_pub -t '/devices/wb-mr6cu_31/controls/K5/meta/readonly' -m 0");  // пол
			runShellCommand("mosquitto_pub -t '/devices/wb-gpio/controls/EXT3_R3A5/meta/readonly' -m 0");  // подоконник
			runShellCommand("mosquitto_pub -t '/devices/wb-mr6cu_31/controls/K6/meta/readonly' -m 0"); // конвектор
			runShellCommand("mosquitto_pub -t '/devices/wb-gpio/controls/EXT3_R3A3/meta/readonly' -m 0"); // конвектор детская
			runShellCommand("mosquitto_pub -t '/devices/wb-gpio/controls/EXT3_R3A4/meta/readonly' -m 0"); // конвектор спальня
			runShellCommand("mosquitto_pub -t '/devices/wb-mr6cu_31/controls/K4/meta/readonly' -m 0"); // пол кухня
			runShellCommand("mosquitto_pub -t '/devices/wb-gpio/controls/EXT3_R3A2/meta/readonly' -m 0"); // конвектор гостиная
			runShellCommand("mosquitto_pub -t '/devices/wb-mr6cu_31/controls/K1/meta/readonly' -m 0"); // пол прихожая
          	// Включаем тёплые полы
			dev["setpoints_floor"]["kitchen_temp"] = 25;
			dev["setpoints_floor"]["entrance_temp"] = 25;
			dev["setpoints_floor"]["cabinet1_temp"] = 25;
			dev["setpoints_floor"]["cabinet2_temp"] = 25;
			// Разрешаем менять уставки температуры радиаторов
			runShellCommand("mosquitto_pub -t '/devices/setpoints_radiator/controls/livingroom_temp/meta/readonly' -m 0");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_radiator/controls/bedroom_temp/meta/readonly' -m 0");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_radiator/controls/children_temp/meta/readonly' -m 0");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_radiator/controls/cabinet_temp/meta/readonly' -m 0");
          	// Включаем отопление
			dev["setpoints_radiator"]["livingroom_temp"] = 25;
			dev["setpoints_radiator"]["bedroom_temp"] = 25;
			dev["setpoints_radiator"]["children_temp"] = 25;
			dev["setpoints_radiator"]["cabinet_temp"] = 25;
          	// Включаем конвекторы
			dev["wb-mwac_46"]["K1"] = true; //  Кран 03 открыть (Обогрев)
			dev["wb-mwac_46"]["K2"] = true; //  Кран 04 открыть (Обогрев)
			log('heating - on');
		}
	}
});

defineRule("set_heating_off", {
	whenChanged: "seasonal_switch/heating",
	then: function(newValue, devName, cellName) { //  Всё включено	
		if (!newValue) {
			// Отключаем расписания
			dev["setpoints_radiator"]["livingroom_permit_schedule"] = false;
			dev["setpoints_radiator"]["bedroom_permit_schedule"] = false;
			dev["setpoints_radiator"]["children_permit_schedule"] = false;
			dev["setpoints_radiator"]["cabinet_permit_schedule"] = false;
			runShellCommand("mosquitto_pub -t '/devices/setpoints_radiator/controls/bedroom_permit_schedule/meta/readonly' -m 1");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_radiator/controls/cabinet_permit_schedule/meta/readonly' -m 1");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_radiator/controls/children_permit_schedule/meta/readonly' -m 1");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_radiator/controls/livingroom_permit_schedule/meta/readonly' -m 1");
          	dev["setpoints_floor"]["kitchen_permit_schedule"] = false;
			dev["setpoints_floor"]["entrance_permit_schedule"] = false;
			dev["setpoints_floor"]["cabinet1_permit_schedule"] = false;
			dev["setpoints_floor"]["cabinet2_permit_schedule"] = false;
			runShellCommand("mosquitto_pub -t '/devices/setpoints_floor/controls/kitchen_permit_schedule/meta/readonly' -m 1");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_floor/controls/entrance_permit_schedule/meta/readonly' -m 1");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_floor/controls/cabinet1_permit_schedule/meta/readonly' -m 1");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_floor/controls/cabinet2_permit_schedule/meta/readonly' -m 1");
          	// Отключаем тёплые полы
			dev["setpoints_floor"]["kitchen_temp"] = 10;
			dev["setpoints_floor"]["entrance_temp"] = 10;
			dev["setpoints_floor"]["cabinet1_temp"] = 10;
			dev["setpoints_floor"]["cabinet2_temp"] = 10;
			// Запрещаем менять уставки температуры полов
			runShellCommand("mosquitto_pub -t '/devices/setpoints_floor/controls/kitchen_temp/meta/readonly' -m 1");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_floor/controls/entrance_temp/meta/readonly' -m 1");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_floor/controls/cabinet1_temp/meta/readonly' -m 1");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_floor/controls/cabinet2_temp/meta/readonly' -m 1");
          	// Физически выключаем и запрещаем включение тёплых полов и конвекторов на панели
			dev["wb-mr6cu_31"]["K5"] = false;
			runShellCommand("mosquitto_pub -t '/devices/wb-mr6cu_31/controls/K5/meta/readonly' -m 1"); // пол
			dev["wb-gpio"]["EXT3_R3A5"] = false;
			runShellCommand("mosquitto_pub -t '/devices/wb-gpio/controls/EXT3_R3A5/meta/readonly' -m 1"); // подоконник
			runShellCommand("mosquitto_pub -t '/devices/wb-mr6cu_31/controls/K6/meta/readonly' -m 1"); // конвектор
			runShellCommand("mosquitto_pub -t '/devices/wb-gpio/controls/EXT3_R3A3/meta/readonly' -m 1"); // конвектор детская
			runShellCommand("mosquitto_pub -t '/devices/wb-gpio/controls/EXT3_R3A4/meta/readonly' -m 1"); // конвектор спальня
			dev["wb-mr6cu_31"]["K4"] = false;
			runShellCommand("mosquitto_pub -t '/devices/wb-mr6cu_31/controls/K4/meta/readonly' -m 1"); // пол кухня
			runShellCommand("mosquitto_pub -t '/devices/wb-gpio/controls/EXT3_R3A2/meta/readonly' -m 1"); // конвектор гостиная
			dev["wb-mr6cu_31"]["K1"] = false;
			runShellCommand("mosquitto_pub -t '/devices/wb-mr6cu_31/controls/K1/meta/readonly' -m 1"); // пол прихожая
          	// Отключаем отопление
			dev["setpoints_radiator"]["livingroom_temp"] = 10;
			dev["setpoints_radiator"]["bedroom_temp"] = 10;
			dev["setpoints_radiator"]["children_temp"] = 10;
			dev["setpoints_radiator"]["cabinet_temp"] = 10;
			// Запрещаем менять уставки температуры радиаторов
			runShellCommand("mosquitto_pub -t '/devices/setpoints_radiator/controls/livingroom_temp/meta/readonly' -m 1");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_radiator/controls/bedroom_temp/meta/readonly' -m 1");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_radiator/controls/children_temp/meta/readonly' -m 1");
          	runShellCommand("mosquitto_pub -t '/devices/setpoints_radiator/controls/cabinet_temp/meta/readonly' -m 1");
			// Закрываем краны
			dev["wb-mwac_46"]["K1"] = false; //  Кран 03 закрыть (Обогрев)
			dev["wb-mwac_46"]["K2"] = false; //  Кран 04 закрыть (Обогрев)
			log('heating - off');
		}
	}
});

defineRule("set_cooling_on", {
	whenChanged: "seasonal_switch/cooling",
	then: function(newValue, devName, cellName) { //  Всё включено	
		if (newValue) {
			// Отопление выключаем
			dev["seasonal_switch"]["heating"] = false;
			// Правило пока пустое, дописать после подключения кондиционеров
			log('cooling - on');
		}
	}
});

defineRule("set_cooling_off", {
	whenChanged: "seasonal_switch/cooling",
	then: function(newValue, devName, cellName) { //  Всё включено	
		if (!newValue) {
			// Правило пока пустое, дописать после подключения кондиционеров
			log('cooling - off');
		}
	}
});

