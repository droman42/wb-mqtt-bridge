// Раздел для размещения правил управления освещением

try {
	var lampsList = require("convertJSON").jsonConvert(readConfig("/mnt/data/etc/wb-mqtt-setpoints.conf").slots[0].on_off);
	for (var l in lampsList) {
		lampsList[l].block = false;			// Добавить внутренний параметр работы со светильником
		lampsList[l].delay_timer = null;		// Добавить внутренний параметр работы со светильником
		lampsList[l].long_press_timer = null;		// Добавить внутренний параметр работы со светильником
//		log("LampList: {}", lampsList[l].name);
	  	lightAfterSensor(lampsList[l]);	// Вызов функции управления по датчику, если в настройках работы имеется датчик
	}
} catch (err) {
	log("Request 'jsonConvert(readConfig('/mnt/data/etc/wb-mqtt-setpoints.conf').slots[0].on_off'" + " executed with ERROR: ");
	log(err.message);
}
 
try {
	var dimmersList = require("convertJSON").jsonConvert(readConfig("/mnt/data/etc/wb-mqtt-setpoints.conf").slots[0].dimmer);
	for (var d in dimmersList) {
		dimmersList[d].block = false;			// Добавить внутренний параметр работы со светильником
		dimmersList[d].delay_timer = null;		// Добавить внутренний параметр работы со светильником
		dimmersList[d].long_press_timer = null;		// Добавить внутренний параметр работы со светильником
//		log("DimmerList (d={}): {}", d, dimmersList[d].name);
		lightAfterSensor(dimmersList[d]);	// Вызов функции управления по датчику, если в настройках работы имеется датчик
	}
} catch (err) {
	log("Request 'jsonConvert(readConfig('/mnt/data/etc/wb-mqtt-setpoints.conf').slots[0].dimmer'" + " executed with ERROR: ");
	log(err.message);
}

// ------------------Настройки автоматической подсветки-------------

lightSP= {}; //Создаем объект 
	
lightSP["home_permit_schedule"] = 	{	"type": "switch",
										"value": true};
	
lightSP["day_mode"] = 	{		"type": "text",
								"value": "День"}; 
	
lightSP["time_current"] = {		"type": "text",
								"value": "00:00"};  
	
lightSP["absence_duration"] = {		"type": "range",
									"value": 50,
									"max": 100};  
	
lightSP["blackout"] = 	{	"type": "pushbutton"}; 

//for (var d in dimmersList) {	
//	if(dimmersList[d].sensor) {		
//		var virt_control = dimmersList[d].mark + "_sensor_permit";	
//		lightSP[virt_control] = {}; //вложенный объект. Имя передаем переменной 
//		lightSP[virt_control]["type"] = "switch"; // добавляем свойства. Имя - тоже можно переменной
//		lightSP[virt_control]["readonly"] = false; //Или константой
//		lightSP[virt_control]["value"] = true; //И значение - можно переменной.
//	}
//}
//
//for (var l in lampsList) {	
//	if(lampsList[l].sensor) {
//		var virt_control = lampsList[l].mark + "_sensor_permit";	
//		lightSP[virt_control] = {}; //вложенный объект. Имя передаем переменной 
//		lightSP[virt_control]["type"] = "switch"; // добавляем свойства. Имя - тоже можно переменной
//		lightSP[virt_control]["readonly"] = false; //Или константой
//		lightSP[virt_control]["value"] = true; //И значение - можно переменной.
//	}
//}

var VDTitle = "Установки освещения";
//Создадим виртуальное устройство и добавим в него элементы 
  defineVirtualDevice("setpoints_light", {
    title: VDTitle,
    cells: lightSP
});

// Функция управления светильником по датчику движения с блокировкой выключателя
function lightAfterSensor(lampParameters) {
	var switches = lampParameters.input.split(","); // Создание массива отдельных выключателей из строки с запятыми
	var sensors = lampParameters.sensor.split(","); // Создание массива отдельных датчиков из строки с запятыми
	var channels = lampParameters.ch2.split(","); // Создание массива дополнительных каналов из строки с запятыми
//	log("lightAfterSensor (" + lampParameters.mark + "): " + sensors);
	
	try {
		if(sensors != ""){
			defineRule(lampParameters.mark + " on", {
				whenChanged: sensors, // Вход от датчиков
				then: function(newValue, devName, cellName) { // Включить свет HL
					if (lampParameters.sensorInverse) {  	// Проверить тип датчика
						newValue = !newValue;						// Инвертирование сигнала от датчика
					}
//					log("newValue: " + newValue);
//					log("lampParameters.block: " + lampParameters.block);
					if (newValue && !lampParameters.block) { // Поступил сигнал от датчика и его работа разрешена				
//						log(lampParameters.mark + " включение по датчику " + cellName + "  ============");
						switch(dev["setpoints_light/day_mode"]) {
							case "День":
								if(lampParameters.ch1dimm) dev[lampParameters.ch1dimm] = lampParameters.day; 		// если лампа диммируемая, то установить уровень заданного свечения	 											
								if(lampParameters.day || lampParameters.day > 0) {									// дневное включение света "ведущей" лампы по движению
									dev[lampParameters.ch1] = true;
//									log(lampParameters.name + " - включился по датчику " + cellName + "  днем");
								}				
								break;
							case "Вечер":
								if(lampParameters.ch1dimm) dev[lampParameters.ch1dimm] = lampParameters.evening; 	// если лампа диммируемая, то установить уровень заданного свечения									
								if(lampParameters.evening  || lampParameters.evening > 0) {							// вечернее включение света "ведущей" лампы по движению
									dev[lampParameters.ch1] = true;
//									log(lampParameters.name + " - включился по датчику " + cellName + "  вечером");
								} 					
								break;
							case "Ночь":
								if(lampParameters.ch1dimm) dev[lampParameters.ch1dimm] = lampParameters.night;	 	// если лампа диммируемая, то установить уровень заданного свечения	
								if(lampParameters.night || lampParameters.night > 0) {								// ночное включение света "ведущей" лампы по движению
									dev[lampParameters.ch1] = true;
//									log(lampParameters.name + " - включился по датчику " + cellName + "  ночью");
								} 		
								break;
						}
					} 
					if (!newValue && !lampParameters.block) { // Сбросился сигнал от датчика и его работа разрешена
						if (lampParameters.delay_timer) clearTimeout(lampParameters.delay_timer);
						lampParameters.delay_timer = setTimeout(function() {
							dev[lampParameters.ch1] = false; 														// выключить освещение
							lampParameters.delay_timer = null;
//							log(lampParameters.name + " - отключился по датчику" + cellName);
						}, lampParameters.duration * 1000);
					}
				}
			});
		}
	} catch (err) {
		log("Rule " + lampParameters.mark + " Sensor on executed with ERROR: ");
		log(err.message);
	}

	try {
		if(switches != "" && sensors != "") {
			defineRule(lampParameters.name + " Sensors Block", {
				whenChanged: switches, // Выключатели
				then: function(newValue, devName, cellName) {
					if(lampParameters.block_timer) clearTimeout(lampParameters.block_timer);
					if(newValue){
						lampParameters.block_timer = setTimeout(function() {
//							log("---------------------------------------------------");
//							log("Кнопка: " + cellName + " нажата!");
//							log("Состояние лампы в '" + lampParameters.name + "': " + dev[lampParameters.ch1]);
							if (dev[lampParameters.ch1]) {
								lampParameters.block = true; // Блокировать отключение светильника по таймеру для датчика
//								log("------AAAAAAAAAAAAAAAAAAAAAAAA------");
//								log("Выключатель " + cellName + " включил свет");
							} else {
								lampParameters.block = false; // Снятие блокировки отключения светильника по таймеру для датчика
//								log("------VVVVVVVVVVVVVVVVVVVVVVVV------");
//								log("Выключатель " + cellName + " выключил свет");
							}
							lampParameters.block_timer = null;
						}, 500);					
					}
				}
			}); 
		}
	} catch (err) {
		log("Rule " + lampParameters.mark + " Sensors Block" + " executed with ERROR: ");
		log(err.message);
	}
	
	try {
		if(channels != "") {
						log("Channel: {}", lampParameters.ch2);
//			log(lampParameters.mark + " Additional Channels");
			defineRule(lampParameters.mark + " Additional Channels", {
				whenChanged: lampParameters.ch1, // Основной канал
				then: function(newValue, devName, cellName) { 
					for (var с in channels) {
						log("Channel: {}", lampParameters.ch1);
						dev[channels[с]] = dev[lampParameters.ch1];			// Повторить состояние основного светильника для дополнительных
//						log("Доп.канал для {}: {} >> {}", lampParameters.mark, channels[с], newValue);
					}
				}
			});			
		}
	} catch (err) {
		log("Rule " + lampParameters.mark + " For Additional Channel executed with ERROR: ");
		log(err.message);
	}
	
	try {
		if(switches != "") {
			defineRule(lampParameters.mark + " check", {
				whenChanged: switches, // Входы
				then: function(newValue, devName, cellName) { 
//					log("===================================");
//					log("Выключатель: " + lampParameters.input);
//					log("Обозначение: " + lampParameters.mark + " == " + dev[lampParameters.ch1]);
//					log("Светильник: " + lampParameters.name);
				}
			});			
		}
	} catch (err) {
		log("Rule " + lampParameters.mark + " Switch on executed with ERROR: ");
		log(err.message);
	}
}
 
// ------------------Блок "Выключить ВСЁ"---------------------------
var rd = require("moduleRestore");
var blackout = function blackout() {
	for (var l in lampsList) {
		dev[lampsList[l].ch1] = false;
	}
	for (var d in dimmersList) {
		dev[dimmersList[d].ch1] = false;
	}
	log("-----------------Total Blackout---------------");
	rd.restoreLights();
	return;
};

defineRule("Leave Home Blackout", { // Покидание дома выключает весь свет
  whenChanged: "power_lvl_switch/at_home",
    then: function (newValue, devName, cellName) {
      if(!newValue) {
        blackout(); //  Вызов функции отключения всех светильников

        log("Leave Home Blackout");
      } else { // Возврат света после возврата
			
	  }
    }
});

var virtTotalBlackout = require("shortLongDoublePress").shortLongDoublePress( // Кнопка в Прихожей
	"Virtual Total Blackout",
	"setpoints_light/blackout",
	300, 2000,
	blackout,  // "Длительное нажатие" - Вызов функции отключения всех светильников
	function() { return },   // "Двойное нажатие" - ничего
	function() { return }    // "Одиночное нажатие" - Ничего
);

var m1TotalBlackout = require("shortLongDoublePress").shortLongDoublePress( // Кнопка в Прихожей
	"Total Blackout", // Name
	"wb-gpio/EXT1_IN1", // Switch
	500, 1000, // Duration
	blackout,  // "Длительное нажатие" - Вызов функции отключения всех светильников
	function() { return },   // "Двойное нажатие" - ничего
	function() { return }    // "Одиночное нажатие" - Ничего
);

// ------------------Блок "Выключить светильники в зоне"---------------------------

//var m2Blackout = require("shortLongDoublePress").shortLongDoublePress( // Кнопка в Гостиной
//	"M2 Blackout",  // Name
//	"wb-gpio/EXT1_IN2", // Switch
//	500, 1000, // Duration
//	function m2SwitchOff() { // "Длительное нажатие" - Вызов функции отключения зоны светильников
//		var lightsList = [dimmersList["HL03"].ch1, lampsList["HL03.1"].ch1, lampsList["HL03.2"].ch1, lampsList["HL03.3"].ch1, lampsList["HL03.4"].ch1, 
//							dimmersList["HL04"].ch1, lampsList["HL04.1"].ch1, lampsList["HL04.2"].ch1];
//		for (var l in lightsList) {
//			dev[lightsList[l]] = false;
//		}
//		log("-----------------M2 Blackout---------------");
//		return;
//	}, 
//	function() { return },   // "Двойное нажатие" - ничего
//	function() { return }    // "Одиночное нажатие" - Ничего
//); 

var m3Blackout = require("shortLongDoublePress").shortLongDoublePress( // Кнопка в Спальне при входе
	"M3 Blackout",  // Name
	"wb-gpio/EXT1_IN3", // Switch
	500, 1000, // Duration
	function m3SwitchOff() { // "Длительное нажатие" - Вызов функции отключения зоны светильников
		var lightsList = [dimmersList["HL08.1"].ch1, dimmersList["HL09"].ch1, dimmersList["HL09.1"].ch1, dimmersList["HL09.5"].ch1,lampsList["HL08"].ch1, lampsList["HL09.3.1"].ch1, lampsList["HL09.4.1"].ch1];
		for (var l in lightsList) {
			dev[lightsList[l]] = false;
		}
		log("-----------------M3 Blackout---------------");
		return;
	}, 
	function() { return },   // "Двойное нажатие" - ничего
	function() { return }    // "Одиночное нажатие" - Ничего
);

var m4Blackout = require("shortLongDoublePress").shortLongDoublePress( // Кнопка в Спальне слева от кровати
	"M4 Blackout",  // Name
	"wb-gpio/EXT1_IN4", // Switch
	500, 1000, // Duration
	function m4SwitchOff() { // "Длительное нажатие" - Вызов функции отключения зоны светильников
		var lightsList = [dimmersList["HL08.1"].ch1, dimmersList["HL09"].ch1, dimmersList["HL09.1"].ch1, dimmersList["HL09.5"].ch1,lampsList["HL08"].ch1, lampsList["HL09.3.1"].ch1, lampsList["HL09.4.1"].ch1];
		for (var l in lightsList) {
			dev[lightsList[l]] = false;
		}
		log("-----------------M4 Blackout---------------");
		return;
	}, 
	function() { return },   // "Двойное нажатие" - ничего
	function() { return }    // "Одиночное нажатие" - Ничего
);
 
var m5Blackout = require("shortLongDoublePress").shortLongDoublePress( // Кнопка в Спальне справа от кровати
	"M5 Blackout",  // Name
	"wb-gpio/EXT1_IN5", // Switch
	500, 1000, // Duration
	function m5SwitchOff() { // "Длительное нажатие" - Вызов функции отключения зоны светильников
		var lightsList = [dimmersList["HL08.1"].ch1, dimmersList["HL09"].ch1, dimmersList["HL09.1"].ch1, dimmersList["HL09.5"].ch1,lampsList["HL08"].ch1, lampsList["HL09.3.1"].ch1, lampsList["HL09.4.1"].ch1];
		for (var l in lightsList) {
			dev[lightsList[l]] = false;
		}
		log("-----------------M5 Blackout---------------");
		return;
	}, 
	function() { return },   // "Двойное нажатие" - ничего
	function() { return }    // "Одиночное нажатие" - Ничего
);

var m6Blackout = require("shortLongDoublePress").shortLongDoublePress( // Кнопка в Детской при входе
	"M6 Blackout",  // Name
	"wb-gpio/EXT1_IN6", // Switch
	500, 1000, // Duration
	function m6SwitchOff() { // "Длительное нажатие" - Вызов функции отключения зоны светильников
		var lightsList = [lampsList["HL07"].ch1, dimmersList["HL07.1"].ch1, dimmersList["HL06"].ch1, dimmersList["HL06.1"].ch1, dimmersList["HL07.1"].ch1, lampsList["HL06.2"].ch1, lampsList["HL06.3"].ch1, lampsList["HL07"].ch1];
		for (var l in lightsList) {
			dev[lightsList[l]] = false;
		}
		log("-----------------M6 Blackout---------------");
		return;
	}, 
	function() { return },   // "Двойное нажатие" - ничего
	function() { return }    // "Одиночное нажатие" - Ничего
);

var m7Blackout = require("shortLongDoublePress").shortLongDoublePress( // Кнопка в Детской за колонной
	"M7 Blackout",  // Name
	"wb-mr6c_51/Input 2", // Switch
	500, 1000, // Duration
	function m7SwitchOff() { // "Длительное нажатие" - Вызов функции отключения зоны светильников
		var lightsList = [lampsList["HL07"].ch1, dimmersList["HL07.1"].ch1, dimmersList["HL06"].ch1, dimmersList["HL06.1"].ch1, dimmersList["HL07.1"].ch1, lampsList["HL06.2"].ch1, lampsList["HL06.3"].ch1, lampsList["HL07"].ch1];
		for (var l in lightsList) {
			dev[lightsList[l]] = false;
		}
		log("-----------------M7 Blackout---------------");
		return;
	}, 
	function() { return },   // "Двойное нажатие" - ничего
	function() { return }    // "Одиночное нажатие" - Ничего
);

var m8Blackout = require("shortLongDoublePress").shortLongDoublePress( // Кнопка в Детской у Гардероба
	"M8 Blackout",  // Name
	"wb-mr6c_51/Input 3", // Switch
	500, 1000, // Duration
	function m8SwitchOff() { // "Длительное нажатие" - Вызов функции отключения зоны светильников
		var lightsList = [lampsList["HL07"].ch1, dimmersList["HL07.1"].ch1, dimmersList["HL06"].ch1, dimmersList["HL06.1"].ch1, dimmersList["HL07.1"].ch1, lampsList["HL06.2"].ch1, lampsList["HL06.3"].ch1, lampsList["HL07"].ch1];
		for (var l in lightsList) {
			dev[lightsList[l]] = false;
		}
		log("-----------------M8 Blackout---------------");
		return;
	}, 
	function() { return },   // "Двойное нажатие" - ничего
	function() { return }    // "Одиночное нажатие" - Ничего
);
 
// -----------------Контроль за включенным светом в течение длительного отсутствия движения -------------
var mswSensors = ["wb-msw-v3_206/Max Motion", // Прихожая
				 "wb-msw-v3_207/Max Motion",  // Гостиная
				 "wb-msw-v3_218/Max Motion",  // Гостиная
				 "wb-msw-v3_219/Max Motion",  // Кабинет
				 "wb-msw-v3_220/Max Motion",  // Детская
				 "wb-msw-v3_225/Max Motion",  // Спальня
				 "wb-msw-v3_227/Max Motion",  // Ванная
				 "wb-msw-v3_231/Max Motion",  // Санузел
				 "setpoints_light/absence_duration"];
var motion_timer = null;
var rd = require("moduleRestore");
defineRule("motion_detector", {
	whenChanged: mswSensors, // Движение
	then: function (newValue, devName, cellName) {
//		 log("Max Motion: " + newValue);
//		 log("Timer: " + motion_timer);
//		if (newValue >= dev["set_security/motion_threshold"]) {
		if (newValue >= 500) {
			if (motion_timer) {
				clearTimeout(motion_timer);
//				 log("Сброс таймера: " + motion_timer);
//				 log("Движение! " + cellName + " : " + newValue);
			}
			motion_timer = setTimeout(function () {
				blackout;
				log("--------------Auto Blackout!-----------------");
				rd.restoreLights();
				motion_timer = null;
			}, dev["setpoints_light/absence_duration"] * 60 * 1000);			
		}
	}
});

// Блокировка действия датчиков при условии достаточной освещенности от Sc07
var enough_illuminance;
defineRule("low_illuminance", { 
  	whenChanged: "wb-msw-v3_111/Illuminance", // Датчик освещенности в коридоре
    then: function (newValue, devName, cellName) { 
      	if(newValue < 35 || !dev["setpoints_light/sc_07"]) {     
          	enough_illuminance =  false; //  Не блокировать включение HL12, HL13, HL16
			 // log("Блокировка выключилась! enough_illuminance: " + enough_illuminance);
      	} else {   
          	enough_illuminance = true; // Блокировать включение HL12, HL13, HL16
			 // log("Блокировка выключилась! enough_illuminance: " + enough_illuminance);
      	}		  
    }
});

log("added in 02_illuminance.js");
