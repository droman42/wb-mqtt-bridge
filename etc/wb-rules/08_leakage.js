// Раздел программы для размещения правил управления сигнализацией от утечек
var msg;
// Возврат реле защиты от протечек U15 в исходное состояние после снятия тревоги
defineRule("U15 Leakage Alarm Off", { 
  whenChanged: ["wb-mwac_46/Alarm"], // Коллектор, Гостиная, Спальня, Детская (Отопление)
  then: function (newValue, devName, cellName) {
	if (!newValue) {
		if(dev["seasonal_switch/heating"]) {
			dev["wb-mwac_46/K1"] = true; 
			dev["wb-mwac_46/K2"] = true; 
		}		
        dev["wb-msw-v3_206/Buzzer"] = false; // Sl01 - Прихожая
        dev["wb-msw-v3_206/Red LED"] = false; // Sl01 - Прихожая
        dev["wb-msw-v3_218/Buzzer"] = false; // Sl10, Sl11 - Гостиная
        dev["wb-msw-v3_218/Red LED"] = false; // Sl10, Sl11 - Гостиная
        dev["wb-msw-v3_225/Buzzer"] = false; // Sl13 - Спальня
        dev["wb-msw-v3_225/Red LED"] = false; // Sl13 - Спальня
        dev["wb-msw-v3_220/Buzzer"] = false; // Sl12 - Детская
        dev["wb-msw-v3_220/Red LED"] = false; // Sl12 - Детская
	}
  }
});

// Возврат реле защиты от протечек U16 в исходное состояние после снятия тревоги
defineRule("U16 Leakage Alarm Off", { 
  whenChanged: ["wb-mwac_54/Alarm"], // Туалет, Ванная, Кухня (ХВС, ГВС)
  then: function (newValue, devName, cellName) {
	if (!newValue) {
		dev["wb-mwac_54/K1"] = true; 
		dev["wb-mwac_54/K2"] = true; 
		
        dev["wb-msw-v3_231/Buzzer"] = false; // Sl04, Sl05, Sl05 - Туалет
        dev["wb-msw-v3_231/Red LED"] = false; // Sl04, Sl05, Sl05 - Туалет
        dev["wb-msw-v3_227/Buzzer"] = false; // Sl07, Sl08, Sl09 - Ванная
        dev["wb-msw-v3_227/Red LED"] = false; // Sl07, Sl08, Sl09 - Ванная
        dev["wb-msw-v3_207/Buzzer"] = false; // Sl02, Sl03 - Кухня
        dev["wb-msw-v3_207/Red LED"] = false; // Sl02, Sl03 - Кухня
        dev["wb-msw-v3_218/Buzzer"] = false; // Sl10, Sl11 - Гостиная
        dev["wb-msw-v3_218/Red LED"] = false; // Sl10, Sl11 - Гостиная
	}
  }
});

// Нажатие на кнопку в щите для снятия тревоги
defineRule("Manual Alarm Off", { 
  whenChanged: ["leakage_settings/alarm_off"],
  then: function (newValue, devName, cellName) {
		dev["wb-mwac_46/Alarm"] = false; 
		dev["wb-mwac_54/Alarm"] = false; 
  }
});

// Управление миганием лампочки на кнопке отключения тревоги
defineRule("Leakage Alarm Indication", { 
  whenChanged: ["wb-mwac_46/Alarm", "wb-mwac_54/Alarm"],
  then: function (newValue, devName, cellName) {
	if(dev["wb-mwac_46/Alarm"] || dev["wb-mwac_54/Alarm"]) {
		startTicker("alarm_ticker", 1000);
	}	
	if(!dev["wb-mwac_46/Alarm"] && !dev["wb-mwac_54/Alarm"]) {
		timers["alarm_ticker"].stop();
		dev["wb-gpio/EXT3_R3A7"] = false; // Выключить лампу сигнализации режима
	}
  }
});

defineRule({
  when: function () { return timers["alarm_ticker"].firing; },
  then: function () {
		dev["wb-gpio/EXT3_R3A7"] = !dev["wb-gpio/EXT3_R3A7"]; // Включить лампу сигнализации режима	в режим мигания
	}
});

// Возврат реле защиты от протечек U15 и U16 в исходное состояние после нажатия на кнопку "Уборка"
var disarm;
var disarmTimer = null;
dev["leakage_settings/cleaning_on"] = false;
defineRule("Arm Leakage protection", {
  whenChanged: ["leakage_settings/cleaning", "wb-mwac_46/S3"], // При нажатии на кнопку сигнализация деактивируется на 30-60 мин.
  then: function (newValue, devName, cellName) {
	if(newValue && !dev["wb-mwac_46/Alarm"] && !dev["wb-mwac_54/Alarm"]) {
		disarm = true; 
		dev["wb-gpio/EXT3_R3A7"] = true; // Включить лампу сигнализации режима
		dev["leakage_settings/cleaning_on"] = true;
		msg = "Отключение защиты от протечек на " + dev["leakage_settings/arm_delay"] + " мин. для уборки.";
		log(msg);
		dev["telegram2wb/Msg"] = '{"chatId": -1001837041484,"text":"' + msg + '"}'; // Отправка сообщения
		if(disarmTimer) clearTimeout(disarmTimer);
	  	disarmTimer = setTimeout(function() {
			disarm = false;
			dev["wb-gpio/EXT3_R3A7"] = false; // Выключить лампу сигнализации режима
			dev["leakage_settings/cleaning_on"] = false;
			msg = "Возврат защиты от протечек в дежурный режим после уборки.";
			log(msg);
			dev["telegram2wb/Msg"] = '{"chatId": -1001837041484,"text":"' + msg + '"}'; // Отправка сообщения
			disarmTimer = null;
		}, dev["leakage_settings/arm_delay"] * 60 * 1000)		
	}
  }
})

// Обеспечение открытых клапанов при срабатывании тревоги в период уборки
defineRule("leakage_disarmed", { 
  whenChanged: ["wb-mwac_46/Alarm", "wb-mwac_54/Alarm"],
  then: function (newValue, devName, cellName) {
	if (newValue && disarm) {      
		dev["wb-mwac_46/Alarm"] = false; 
		dev["wb-mwac_54/Alarm"] = false;
    }
  }
});

//------------------------Блок формирования сигналов и оповещений-------------------------

/* 	206- 	Прихожая
	207- 	Гостиная
	218- 	Кухня	(43-	м1w2)
	219-	Кабинет	(56-	м1w2)
	220- 	Детская	
	225- 	Спальня	
	227-	Ванная	(173-	м1w2)
	231-	Туалет	(114-	м1w2)
	229- 	Резерв	(37-	м1w2) */
	
defineRule("Leak Detected U15", { // Поступление сигнала от датчика модуля U15
  whenChanged: ["wb-mwac_46/F1", "wb-mwac_46/F2", "wb-mwac_46/F3", "wb-mwac_46/S1", "wb-mwac_46/S2"],
  then: function (newValue, devName, cellName) {
	  if (newValue) {
	  	      switch (cellName) {
                case "F1": //  Коллектор
                    dev["wb-msw-v3_206/Buzzer"] = true; // Sl01
                    dev["wb-msw-v3_206/Red LED"] = true;  // Sl01
					// Отправка сообщения
                    msg = "Протечка воды в коллекторе отопления!";
					log(msg);
					dev["telegram2wb/Msg"] = '{"chatId": -1001837041484 ,"text":"' + msg + '"}'; // Отправка в Telegram
                  break;
                case "F2": //  Радиатор 1 Гостиная
                    dev["wb-msw-v3_207/Buzzer"] = true; //  Sl10
                    dev["wb-msw-v3_207/Red LED"] = true;  // Sl10
					// Отправка сообщения
                    msg = "Протечка воды в Радиаторе 1 Гостиной!";
					log(msg);
					dev["telegram2wb/Msg"] = '{"chatId": -1001837041484 ,"text":"' + msg + '"}'; // Отправка в Telegram
                  break;
                case "F3": //  Радиатор 2 Гостиная
                    dev["wb-msw-v3_207/Buzzer"] = true; // Sl11
                    dev["wb-msw-v3_207/Red LED"] = true;  // Sl11
					// Отправка сообщения
                    msg = "Протечка воды в Радиаторе 2 Гостиной!";
					log(msg);
					dev["telegram2wb/Msg"] = '{"chatId": -1001837041484 ,"text":"' + msg + '"}'; // Отправка в Telegram
                  break;
                case "S1": //  Радиатор Детская
                    dev["wb-msw-v3_220/Buzzer"] = true; // Sl12
                    dev["wb-msw-v3_220/Red LED"] = true;  // Sl12
					// Отправка сообщения
                    msg = "Протечка воды в Радиаторе Детской!";
					log(msg);
					dev["telegram2wb/Msg"] = '{"chatId": -1001837041484 ,"text":"' + msg + '"}'; // Отправка в Telegram
                  break;
                case "S2": //  Радиатор Спальня
                    dev["wb-msw-v3_225/Buzzer"] = true; // Sl13
                    dev["wb-msw-v3_225/Red LED"] = true;  // Sl13
					// Отправка сообщения
                    msg = "Протечка воды в Радиаторе Спальни!";
					log(msg);
					dev["telegram2wb/Msg"] = '{"chatId": -1001837041484 ,"text":"' + msg + '"}'; // Отправка в Telegram
                  break;
                default:
                  log('Неверное значение датчика утечки: {}', cellName);     
        }
	  } 
  }
});
	 
defineRule("leak_detected_U16", { // Поступление сигнала от датчика модуля U16
  whenChanged: ["wb-mwac_54/F1", "wb-mwac_54/F2", "wb-mwac_54/F3"],
  then: function (newValue, devName, cellName) {
	  if (newValue) { 
	  	      switch (cellName) {
                case "F1": //  Кухня
                    dev["wb-msw-v3_218/Buzzer"] = true; // Sl02, Sl03
                    dev["wb-msw-v3_218/Red LED"] = true;  // Sl02, Sl03
					// Отправка сообщения
                    msg = "Протечка воды в Кухне!";
					log(msg);
					dev["telegram2wb/Msg"] = '{"chatId": -1001837041484 ,"text":"' + msg + '"}'; // Отправка в Telegram
                  break;
                case "F2": //  Туалет 
                    dev["wb-msw-v3_231/Buzzer"] = true; //  Sl04, Sl05, Sl06
                    dev["wb-msw-v3_231/Red LED"] = true;  //  Sl04, Sl05, Sl06
					// Отправка сообщения
                    msg = "Протечка воды в Туалете!";
					log(msg);
					dev["telegram2wb/Msg"] = '{"chatId": -1001837041484 ,"text":"' + msg + '"}'; // Отправка в Telegram
                  break;
                case "F3": //  Ванная
                    dev["wb-msw-v3_227/Buzzer"] = true; //  Sl07, Sl08, Sl09
                    dev["wb-msw-v3_227/Red LED"] = true;  //  Sl07, Sl08, Sl09
					// Отправка сообщения
                    msg = "Протечка воды в Ванной!";
					log(msg);
					dev["telegram2wb/Msg"] = '{"chatId": -1001837041484 ,"text":"' + msg + '"}'; // Отправка в Telegram
                  break;
                default:
                  log('Неверное значение датчика утечки: {}', cellName);     
        }
	  } 
  }
});

// ---------------------Профилактическое включение/выключение запорной арматуры-------------------------

defineRule("check_water_tap", {
  when: cron("0 0 13 1 * *"),
  then: function () {
	  if(dev["seasonal_switch/heating"]) {
      	dev["wb-mwac_46/K1"] = false;
	  	dev["wb-mwac_46/K2"] = false;
      	} else {
      	dev["wb-mwac_46/K1"] = true;
	  	dev["wb-mwac_46/K2"] = true;
      }
	  dev["wb-mwac_54/K1"] = false;
	  dev["wb-mwac_54/K2"] = false;
	  startTimer("timerWaterTapCheck", 30 * 1000);  		// запустили таймер на задержку отключения крана
		SendTelegramMsg('Профилактическое закрытие крана.');
  }
});

defineRule("restoreWaterTap", {
	when: function () { return timers.timerWaterTapCheck.firing; }, // отследили срабатывание таймера для обратного включения кранов
	then: function () {
	  if(dev["seasonal_switch/heating"]) {
      	dev["wb-mwac_46/K1"] = true;
	  	dev["wb-mwac_46/K2"] = true;
      	} else {
      	dev["wb-mwac_46/K1"] = false;
	  	dev["wb-mwac_46/K2"] = false;
      }
	  dev["wb-mwac_54/K1"] = true;
	  dev["wb-mwac_54/K2"] = true;
	  SendTelegramMsg('Профилактическое открытие крана.');
	}
});

log("added in 08_leakage.js");