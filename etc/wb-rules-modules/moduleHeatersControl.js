//'use strict';   

//---------------------Модуль управления температурными режимами (обогревателями)---------------

exports.CreateSetpointsControls = function (params, heater_type) {  
	heatersList = params;
//	log("heatersList :\n", JSON.stringify(heatersList));
	tempSP= {}; //Создаем объект
	for (var h in heatersList) {	
		var virt_control_temp = heatersList[h].alias + " temp";	
		tempSP[virt_control_temp] = {}; //вложенный объект. Имя передаем переменной 
		tempSP[virt_control_temp]["type"] = "range"; // добавляем свойства. Имя - тоже можно переменной
//		tempSP[virt_control_temp]["readonly"] = true; //Или константой
		tempSP[virt_control_temp]["value"] = 26; //И значение - можно переменной.
		tempSP[virt_control_temp]["max"] = 35; //И значение - можно переменной.
		
		virt_control_schedule_on = heatersList[h].alias + " heat schedule";
		tempSP[virt_control_schedule_on] = {}; //вложенный объект. Имя передаем переменной
		tempSP[virt_control_schedule_on]["type"] = "switch"; // добавляем свойства. Имя - тоже можно переменной
		tempSP[virt_control_schedule_on]["value"] = false; //И значение - можно переменной.
		
		// Управление видимостью регулятора уставки температуры
		defineRule("Set readonly Schedule To Control " + heatersList[h].alias + " " + heater_type, { // Переключение в режим readonly 
			whenChanged: ["temperature_setpoints_" + heater_type + "/" + heatersList[h].alias + " heat schedule"],
			then: function(newValue, devName, cellName) {
				var rExp = new RegExp(" heat schedule", "g");
				var controlTemperature = "/devices/temperature_setpoints_" + heater_type + "/controls/" + cellName.replace(rExp, '') + " temp";
				if (newValue) {
					command = "mosquitto_pub -t '" + controlTemperature + "/meta/readonly' -m '1'";
					runShellCommand(command);			//Команда для установки writable 
				} else {
					command = "mosquitto_pub -t '" + controlTemperature + "/meta/readonly' -m '0'";
					runShellCommand(command);			//Команда для установки readonly
				}
			}
		});
//		log("heatersList: {}", heatersList[h].name);
	}
	var virt_control_eco_temp = "_" + heater_type + "_eco";
	tempSP[virt_control_eco_temp] = {}; //вложенный объект. Имя передаем переменной
	tempSP[virt_control_eco_temp]["type"] = "range"; // добавляем свойства. Имя - тоже можно переменной
//	tempSP[virt_control_eco_temp]["readonly"] = false; //Или константой
	tempSP[virt_control_eco_temp]["value"] = 15; //И значение - можно переменной.
	tempSP[virt_control_eco_temp]["max"] = 35; //И значение - можно переменной.
		
	var VDTitle = "Уставки температуры";
    switch (heater_type) {
        case "floor": // 
			VDTitle = "Уставки температуры для полов";
          break;

        case "radiator": //  
			VDTitle = "Уставки температуры для радиаторов";
          break;
    }
	//Создадим виртуальное устройство и добавим в него элементы 
	  defineVirtualDevice("temperature_setpoints_" + heater_type, {
	    title: VDTitle,
	    cells: tempSP
	  });
	  
	for (var h in heatersList) {	
		if (dev["temperature_setpoints_" + heater_type + "/" + heatersList[h].alias + " heat schedule"]) {
		command = "mosquitto_pub -t '/devices/temperature_setpoints_" + heater_type + "/controls/" + heatersList[h].alias + " temp/meta/readonly' -m '1'";
		runShellCommand(command);			//Команда для установки readonly
		} else {
		command = "mosquitto_pub -t '/devices/temperature_setpoints_" + heater_type + "/controls/" + heatersList[h].alias + " temp/meta/readonly' -m '0'";
		runShellCommand(command);			//Команда для установки writable
		}
	}
}

exports.HysteresisHeaterControl = function (params, heater_type) {	
	var roomName = params.alias; 
	var relay = params.ch1;
	var sensor;
	var setpoint = "temperature_setpoints_" + heater_type + "/" + roomName + " temp";
	var deviation = params.deviation;
	   
	switch (heater_type) { // Выбор датчика для измерения температуры в зависимости от типа обогревателя
        case "floor": // Теплый пол
			sensor = params.floorSensor;
          break;

        case "radiator": //  Радиатор отопления
			sensor = params.airSensor;
          break;
    }	
    
	defineRule("Control " + heater_type + " in " + roomName, { // Проверка разрешения на включение
		whenChanged: [sensor, setpoint],
		then: function(newValue, devName, cellName) {
			if (!dev["power_lvl_switch/long_absence"]) {
				if (dev[sensor] > (dev[setpoint] + deviation)) {  //если температура датчика больше уставки + гистерезис
					dev[relay] = false; //установи Реле в состояние 'выключено'
				}
				if (dev[sensor] < (dev[setpoint] - deviation)) {
					dev[relay] = true; //оставляем Реле в состояние 'выключено'
				} 
//				log("============ " + heater_type + " ==============");
//				log(setpoint);
//				log("cellName: " + cellName);
//				log(heater_type + " в " + roomName + ": " + dev[relay]);
//				log("Уставка температуры: " + dev[setpoint]);
//				log("Температура: " + dev[sensor]);
			} else {
				dev[relay] = false;
			}
		}
	});		
}
		