// Раздел программы для размещения скриптов управления отключением групп розеток

defineRule("set_at_home", {
	whenChanged: "power_lvl_switch/at_home",
	then: function(newValue, devName, cellName) { //  Всё включено	
		if (newValue) {
			dev["power_lvl_switch"]["short_absence"] = false;
			dev["wb-mr6c-nc_25"]["K1"] = true; // Розетки (включить)
			dev["wb-mr6c-nc_25"]["K2"] = true; // Печь (включить)
			dev["wb-mwac_54"]["K1"] = true; //  Кран 01 (ХВС) открыть
			dev["wb-mwac_54"]["K2"] = true; //  Кран 02 (ГВС) открыть
			dev["wb-mr6c_47/K3"] = true; // Питание торшера в Гостиной (включить)
			msg = "Возврат системы в режим 'Дома'";
			log(msg);
			dev["telegram2wb/Msg"] = '{"chatId": -1001837041484,"text":"' + msg + '"}'; // Отправка сообщения
			var buzzerPulse = null;
			if (!dev["set_security/secure_on"]) {
				dev["wb-msw-v3_206/Buzzer"] = true;   // Звуковой сигнал 
				buzzerPulse = setTimeout(function() {
					dev["wb-msw-v3_206/Buzzer"] = false;
					buzzerPulse = null;
				}, 400); 
				dev["wb-msw-v3_206/LED Period (s)"] = 3; // Отключить мигание оранжевым в режиме "Краткое отсутствие"
				dev["wb-msw-v3_206/Green LED"] = false; // Sc07 Passage
				dev["wb-msw-v3_206/Red LED"] = false; // Sc07 Passage
			}
		}
	}
}); 

defineRule("set_short_absence", {
	whenChanged: "power_lvl_switch/short_absence",
	then: function(newValue, devName, cellName) { //  Всё включено	
		if (newValue) {
			dev["power_lvl_switch"]["at_home"] = false;
			dev["wb-mr6c-nc_25"]["K1"] = false; // Розетки (отключить)
			dev["wb-mr6c-nc_25"]["K2"] = false; // Печь (отключить)
			dev["wb-mwac_54"]["K1"] = false; //  Кран 01 (ХВС) закрыть
			dev["wb-mwac_54"]["K2"] = false; //  Кран 02 (ГВС) закрыть
			dev["wb-mr6c_47/K3"]  = false; // Питание торшера в Гостиной (отключить)
			msg = "Система переведена в режим 'Ушёл'";
			log(msg);
			dev["telegram2wb/Msg"] = '{"chatId": -1001837041484,"text":"' + msg + '"}'; // Отправка сообщения
			var buzzerPulse = null;
			if (!dev["set_security/secure_on"]) {
				dev["wb-msw-v3_206/Buzzer"] = true;   // Звуковой сигнал 
				buzzerPulse = setTimeout(function() {
					dev["wb-msw-v3_206/Buzzer"] = false;
					buzzerPulse = null;
				}, 400);
				dev["wb-msw-v3_206/LED Period (s)"] = 3; // Мигание оранжевым в режиме "Краткое отсутствие"
				dev["wb-msw-v3_206/Green LED"] = true; // Sc07 Passage
				dev["wb-msw-v3_206/Red LED"] = true; // Sc07 Passage
			}
		} else {
			dev["power_lvl_switch/at_home"] = true;
		}
	}
});


// ---------------------Проверка  отключения основного питания----------------------

defineRule("Check Main Power", {
  whenChanged: ["wb-gpio/A2_IN"],
  then: function (newValue, devName, cellName) {
	  if (newValue) { 
		msg = "Отключение питания контроллера от сети ~220в!";
		log(msg);
		dev["telegram2wb/Msg"] = '{"chatId": -1001837041484,"text":"' + msg + '"}'; // Отправка сообщения
	  } else {
		msg = "Питание контроллера возвращено на сеть ~220в!";
		log(msg);
		dev["telegram2wb/Msg"] = '{"chatId": -1001837041484,"text":"' + msg + '"}'; // Отправка сообщения		
		if (dev["power_lvl_switch"]["at_home"]) {
			audioVideoON();
		}	  
	  }
  }
});

function audioVideoON() {
	
	return;
}

log("added in 03_power.js");
