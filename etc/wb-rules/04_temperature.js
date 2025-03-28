//'use strict';   
// Раздел программы для размещения правил управления температурой помещений

var temperatureConfig = readConfig("/mnt/data/etc/wb-mqtt-setpoints.conf").slots[1];

//  раздел управления теплыми полами
var floorsList = temperatureConfig["floor"];
//log("FLOORS_List: {} ", JSON.stringify(floorsList));
CreateSetpointsControls(floorsList, "floor");			// Создать виртуальное устройство панели управления полами 
for (var f in floorsList) { 
	HysteresisHeaterControl(floorsList[f], "floor");	// Включение/выключение нагрева в зависимости от уставки
}
 
//  раздел управления радиаторами
radiatorsList = temperatureConfig["radiator"];
//log("RADIATORS_List: {} ", JSON.stringify(radiatorsList));
CreateSetpointsControls(radiatorsList, "radiator");			// Создать виртуальное устройство панели управления радиаторами  
for (var r in radiatorsList) { 
	HysteresisHeaterControl(radiatorsList[r], "radiator");	// Включение/выключение нагрева в зависимости от уставки
}

var coolersControl = require("moduleCoolersControl");

var fanConfig = readConfig("/mnt/data/etc/wb-mqtt-setpoints.conf").slots[2];
//  раздел управления вентиляторами
coolersList = fanConfig["fan"];
log("coolersList: {}", JSON.stringify(coolersList));
coolersControl.CreateSetpointsControls(coolersList, "cooler");			// Создать виртуальное устройство панели управления вентиляторами  
for (var c in coolersList) { 
	coolersControl.HysteresisCoolerControl(coolersList[c], "cooler");	// Включение/выключение охлаждения в зависимости от уставки
}
 
//---------------------Модуль виртуального устройства панели управления обогревателями и полами---------------

function CreateSetpointsControls(params, heater_type) {  
	heatersList = params;
//	log("heatersList :\n", JSON.stringify(heatersList));
	tempSP= {}; //Создаем объект
	for (var h in heatersList) {	
		var virt_control_temp = heatersList[h].alias + "_temp";	
		tempSP[virt_control_temp] = {}; //вложенный объект. Имя передаем переменной 
		tempSP[virt_control_temp]["type"] = "range"; // добавляем свойства.
//		tempSP[virt_control_temp]["readonly"] = true;
		tempSP[virt_control_temp]["value"] = 26;
		tempSP[virt_control_temp]["max"] = 35;
		
		virt_control_schedule_on = heatersList[h].alias + "_permit_schedule";
		tempSP[virt_control_schedule_on] = {}; //вложенный объект. Имя передаем переменной
		tempSP[virt_control_schedule_on]["type"] = "switch";
		tempSP[virt_control_schedule_on]["value"] = false; 
		
		// Управление видимостью регулятора уставки температуры
		defineRule("Set readonly Schedule To Control " + heatersList[h].alias + " " + heater_type, { // Переключение в режим readonly 
			whenChanged: ["setpoints_" + heater_type + "/" + heatersList[h].alias + "_permit_schedule"],
			then: function(newValue, devName, cellName) {
				var rExp = new RegExp("_permit_schedule", "g");
				var controlTemperature = "/devices/setpoints_" + heater_type + "/controls/" + cellName.replace(rExp, '') + "_temp";
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
	tempSP[virt_control_eco_temp]["type"] = "range"; // добавляем свойства.
//	tempSP[virt_control_eco_temp]["readonly"] = false;
	tempSP[virt_control_eco_temp]["value"] = 15; 
	tempSP[virt_control_eco_temp]["max"] = 35;
		
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
	  defineVirtualDevice("setpoints_" + heater_type, {
	    title: VDTitle,
	    cells: tempSP
	  });
	  
	for (var h in heatersList) {	
		if (dev["setpoints_" + heater_type + "/" + heatersList[h].alias + "_permit_schedule"]) {
		command = "mosquitto_pub -t '/devices/setpoints_" + heater_type + "/controls/" + heatersList[h].alias + "_temp/meta/readonly' -m '1'";
		runShellCommand(command);			//Команда для установки readonly
		} else {
		command = "mosquitto_pub -t '/devices/setpoints_" + heater_type + "/controls/" + heatersList[h].alias + "_temp/meta/readonly' -m '0'";
		runShellCommand(command);			//Команда для установки writable
		} 
	} 
}

//---------------------Модуль управления обогревателями и полами---------------

function HysteresisHeaterControl(params, heater_type) {	
	var roomName = params.alias; 
	var relay = params.ch1;
	var sensor;
	var setpoint = "setpoints_" + heater_type + "/" + roomName + "_temp";
	var deviation = params.deviation;
	   
	switch (heater_type) { // Выбор датчика для измерения температуры в зависимости от типа обогревателя
        case "floor": // Теплый пол
			sensor = params.floorSensor;
          break;
        case "radiator": //  Радиатор отопления
			sensor = params.airSensor;
          break;
    }	
    
// Начальная установка состояния реле
	if (dev[sensor] > (dev[setpoint])) {  //если температура датчика больше уставки
		dev[relay] = params.ch1inversion? false : true; //Реле в состояние 'выключено' (false для НЗ, true для НО)
	} else {
		dev[relay] = params.ch1inversion? true : false; //Реле в состояние 'включено' (true для НЗ, false для НО)
	} 
	
// Функция оценки температуры и установки состояния реле    
	defineRule("Control " + heater_type + " in " + roomName, { // Проверка разрешения на включение
		whenChanged: [sensor, setpoint],
		then: function(newValue, devName, cellName) {
			if (!dev["power_lvl_switch/long_absence"]) {
				if (dev[sensor] > (dev[setpoint] + deviation)) {  //если температура датчика больше уставки + гистерезис
					dev[relay] = params.ch1inversion? false : true; //Реле в состояние 'выключено' (false для НЗ, true для НО)
				}
				if (dev[sensor] < (dev[setpoint] - deviation)) {
					dev[relay] = params.ch1inversion? true : false; //Реле в состояние 'включено' (true для НЗ, false для НО)
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

//---------------------Модуль управления кондиционерами---------------



log("added in 04_temperature.js");