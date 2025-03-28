//'use strict';   

//---------------------Модуль управления температурными режимами (кулеров)---------------

exports.CreateSetpointsControls = function (params, cooler_type) {  
	coolersList = params;
//	log("coolersList :\n", JSON.stringify(coolersList));
	tempSP= {}; //Создаем объект
	for (var с in coolersList) {	
		var virt_control_temp = coolersList[с].alias + " temp";	
		tempSP[virt_control_temp] = {}; //вложенный объект. Имя передаем переменной 
		tempSP[virt_control_temp]["type"] = "range"; // добавляем свойства.
//		tempSP[virt_control_temp]["readonly"] = true;
		tempSP[virt_control_temp]["value"] = 26; 
		tempSP[virt_control_temp]["max"] = 35; 
		
//		virt_control_schedule_on = coolersList[с].alias + " cooler schedule";
//		tempSP[virt_control_schedule_on] = {}; //вложенный объект. Имя передаем переменной
//		tempSP[virt_control_schedule_on]["type"] = "switch"; // добавляем свойства.
//		tempSP[virt_control_schedule_on]["value"] = false;
//		
//		virt_control_force = coolersList[с].alias + " force";
//		tempSP[virt_control_force] = {}; //вложенный объект. Имя передаем переменной
//		tempSP[virt_control_force]["type"] = "switch"; // добавляем свойства.
//		tempSP[virt_control_force]["value"] = false; 
//		tempSP[virt_control_force]["readonly"] = true; 
		
		// Управление видимостью регулятора уставки температуры
		defineRule("Set readonly Schedule To Control " + coolersList[с].alias + " " + cooler_type, { // Переключение в режим readonly 
			whenChanged: ["temperature_setpoints_" + cooler_type + "/" + coolersList[с].alias + " cooler schedule"],
			then: function(newValue, devName, cellName) {
				var rExp = new RegExp(" cooler schedule", "g");
				var controlTemperature = "/devices/temperature_setpoints_" + cooler_type + "/controls/" + cellName.replace(rExp, '') + " temp";
				if (newValue) {
					command = "mosquitto_pub -t '" + controlTemperature + "/meta/readonly' -m '1'";
					runShellCommand(command);			//Команда для установки writable 
				} else {
					command = "mosquitto_pub -t '" + controlTemperature + "/meta/readonly' -m '0'";
					runShellCommand(command);			//Команда для установки readonly
				}
			}
		});
		log("coolersList: {}", coolersList[с].name);
	}
	var virt_control_eco_temp = "_" + cooler_type + "_eco";
	tempSP[virt_control_eco_temp] = {}; //вложенный объект. Имя передаем переменной
	tempSP[virt_control_eco_temp]["type"] = "range"; // добавляем свойства. Имя - тоже можно переменной
//	tempSP[virt_control_eco_temp]["readonly"] = false; //Или константой
	tempSP[virt_control_eco_temp]["value"] = 15; //И значение - можно переменной.
	tempSP[virt_control_eco_temp]["max"] = 35; //И значение - можно переменной.
		
	var VDTitle = "Уставки температуры";
    switch (cooler_type) {
        case "cooler": // 
			VDTitle = "Уставки температуры для охлаждения";
          break;

        case "humidifyer": //  
			VDTitle = "Уставки температуры для осушения";
          break;
    }
	//Создадим виртуальное устройство и добавим в него элементы 
	  defineVirtualDevice("temperature_setpoints_" + cooler_type, {
	    title: VDTitle,
	    cells: tempSP
	  });
	  
	for (var с in coolersList) {	
		if (dev["temperature_setpoints_" + cooler_type + "/" + coolersList[с].alias + " cooler schedule"]) {
		command = "mosquitto_pub -t '/devices/temperature_setpoints_" + cooler_type + "/controls/" + coolersList[с].alias + " temp/meta/readonly' -m '1'";
		runShellCommand(command);			//Команда для установки readonly
		} else {
		command = "mosquitto_pub -t '/devices/temperature_setpoints_" + cooler_type + "/controls/" + coolersList[с].alias + " temp/meta/readonly' -m '0'";
		runShellCommand(command);			//Команда для установки writable
		}
	}
}

exports.HysteresisCoolerControl = function (params, cooler_type) {	
	var roomName = params.alias; 
	var hvac_sp = params.temperatureSP;
	var hvac_on = params.ch1;
	var sensor;
	var setpoint = "temperature_setpoints_" + cooler_type + "/" + roomName + " temp";
	var deviation;
	   
	switch (cooler_type) { // Выбор датчика для измерения температуры в зависимости от типа вентилятора
        case "cooler": // Охлаждение 
			sensor = params.temperatureSensor;
			deviation = params.deviationT;
          break;

        case "humidifyer": //  Осушение
			sensor = params.humiditySensor;
			deviation = params.deviationH;
          break;
    }	
    
	defineRule("Control " + cooler_type + " in " + roomName, { // Проверка разрешения на включение
		whenChanged: [setpoint],
		then: function(newValue, devName, cellName) {
			if (!dev["power_lvl_switch/long_absence"] && dev["seasonal_switch/cooling"]) {
					dev[hvac_sp] = dev[setpoint];
					dev[hvac_on] = true;
//					log("============ " + cooler_type + " ==============");
//					log("Power: " + dev["hvac_livingroom/power"]);
//					log("hvac_on: " + params.ch1);
//					log(cooler_type + " в " + roomName + ": " + dev[hvac_sp]);
//					log("Уставка температуры: " + dev[setpoint]);
	//				log("Отклонение температуры: " + deviation);
//					log("Температура: " + dev[sensor]);		
			} else {
				
			}
		}
	});	
	
	
//---------------------Блок управления вентиляторами вытяжки по выключателю---------------

	defineRule("Force control for " + cooler_type + " in " + roomName, {
	  whenChanged: params.forceInput, //при изменении состояния датчика или уставки
	  then: function (newValue, devName, cellName) {
		if (newValue) {
			dev["temperature_setpoints_" + cooler_type + "/" + roomName + " force"] = !dev["temperature_setpoints_" + cooler_type + "/" + roomName + " force"];
			log("Force switch in " + roomName + ": " + dev["temperature_setpoints_" + cooler_type + "/" + roomName + " force"]);
		}
	  }
	});	
}
		