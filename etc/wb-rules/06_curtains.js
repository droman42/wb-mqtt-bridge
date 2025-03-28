// Раздел программы для размещения правил управления шторами

// ------------------Настройки автоматической подсветки-------------

curtaintSP= {}; //Создаем объект 
	
var virt_control_livingroom = "livingroom_position";	
curtaintSP[virt_control_livingroom] = {}; //вложенный объект. Имя передаем переменной 
curtaintSP[virt_control_livingroom]["type"] = "range"; 
curtaintSP[virt_control_livingroom]["readonly"] = false; 
curtaintSP[virt_control_livingroom]["max"] = 100; 
curtaintSP[virt_control_livingroom]["value"] = 0; 
		
virt_control_livingroom_schedule_on = "livingroom_permit_schedule";
curtaintSP[virt_control_livingroom_schedule_on] = {}; //вложенный объект. Имя передаем переменной
curtaintSP[virt_control_livingroom_schedule_on]["type"] = "switch";
curtaintSP[virt_control_livingroom_schedule_on]["value"] = false; 
	
var virt_control_bedroom = "bedroom_position";	
curtaintSP[virt_control_bedroom] = {}; //вложенный объект. Имя передаем переменной 
curtaintSP[virt_control_bedroom]["type"] = "range"; 
curtaintSP[virt_control_bedroom]["readonly"] = false; 
curtaintSP[virt_control_bedroom]["max"] = 100; 
curtaintSP[virt_control_bedroom]["value"] = 0; 
		
virt_control_bedroom_schedule_on = "bedroom_permit_schedule";
curtaintSP[virt_control_bedroom_schedule_on] = {}; //вложенный объект. Имя передаем переменной
curtaintSP[virt_control_bedroom_schedule_on]["type"] = "switch";
curtaintSP[virt_control_bedroom_schedule_on]["value"] = false; 
	
var virt_control_cabinet = "cabinet_position";	
curtaintSP[virt_control_cabinet] = {}; //вложенный объект. Имя передаем переменной 
curtaintSP[virt_control_cabinet]["type"] = "range"; 
curtaintSP[virt_control_cabinet]["readonly"] = false; 
curtaintSP[virt_control_cabinet]["max"] = 100; 
curtaintSP[virt_control_cabinet]["value"] = 0; 
		
virt_control_cabinet_schedule_on = "cabinet_permit_schedule";
curtaintSP[virt_control_cabinet_schedule_on] = {}; //вложенный объект. Имя передаем переменной
curtaintSP[virt_control_cabinet_schedule_on]["type"] = "switch";
curtaintSP[virt_control_cabinet_schedule_on]["value"] = false; 

var VDTitle = "Установки штор";
//Создадим виртуальное устройство и добавим в него элементы 
  defineVirtualDevice("setpoints_curtain", {
    title: VDTitle,
    cells: curtaintSP
});
		
//// Управление видимостью регулятора положения шторы в Гостиной
//defineRule("Set readonly Schedule To Control Curtain In Livingroom", { // Переключение в режим readonly 
//	whenChanged: ["setpoints_curtain/livingroom_permit_schedule"],
//	then: function(newValue, devName, cellName) {
//		var controlCurtain = "/devices/setpoints_curtain/controls/livingroom_position";
//		if (newValue) {
//			command = "mosquitto_pub -t '" + controlCurtain + "/meta/readonly' -m '1'";
//			runShellCommand(command);			//Команда для установки writable 
//		} else {
//			command = "mosquitto_pub -t '" + controlCurtain + "/meta/readonly' -m '0'";
//			runShellCommand(command);			//Команда для установки readonly
//		}
//	}
//});
//		
//// Управление видимостью регулятора положения шторы в Спальне
//defineRule("Set readonly Schedule To Control Curtain In Bedroom", { // Переключение в режим readonly 
//	whenChanged: ["setpoints_curtain/bedroom_permit_schedule"],
//	then: function(newValue, devName, cellName) {
//		var controlCurtain = "/devices/setpoints_curtain/controls/bedroom_position";
//		if (newValue) {
//			command = "mosquitto_pub -t '" + controlCurtain + "/meta/readonly' -m '1'";
//			runShellCommand(command);			//Команда для установки writable 
//		} else {
//			command = "mosquitto_pub -t '" + controlCurtain + "/meta/readonly' -m '0'";
//			runShellCommand(command);			//Команда для установки readonly
//		}
//	}
//});
//		
//// Управление видимостью регулятора положения шторы в Кабинете
//defineRule("Set readonly Schedule To Control Curtain In Cabinet", { // Переключение в режим readonly 
//	whenChanged: ["setpoints_curtain/cabinet_permit_schedule"],
//	then: function(newValue, devName, cellName) {
//		var controlCurtain = "/devices/setpoints_curtain/controls/cabinet_position";
//		if (newValue) {
//			command = "mosquitto_pub -t '" + controlCurtain + "/meta/readonly' -m '1'";
//			runShellCommand(command);			//Команда для установки writable 
//		} else {
//			command = "mosquitto_pub -t '" + controlCurtain + "/meta/readonly' -m '0'";
//			runShellCommand(command);			//Команда для установки readonly
//		}
//	}
//});

defineRule("Curtain Livingroom Position", { 
  	whenChanged: "setpoints_curtain/livingroom_position", // Виртуальная уставка положения
    then: function (newValue, devName, cellName) { 
      	dev["dooya_0x0101/Position"] = newValue;	
//      	dev["dooya_0x0102/Position"] = newValue;	
      	dev["dooya_0x0103/Position"] = newValue;	
//      	dev["dooya_0x0104/Position"] = newValue;	 
      	log("Изменение положения штор в Гостиной на {}", newValue); 
    }
});

defineRule("Curtain Bedroom Position", { 
  	whenChanged: "setpoints_curtain/bedroom_position", // Виртуальная уставка положения
    then: function (newValue, devName, cellName) { 
//      	dev["dooya_0x0107/Position"] = newValue;	
      	dev["dooya_0x0108/Position"] = newValue;	  
      	log("Изменение положения штор в Спальне на {}", newValue); 
    }
});

defineRule("Curtain Cabinet Position", { 
  	whenChanged: "setpoints_curtain/cabinet_position", // Виртуальная уставка положения
    then: function (newValue, devName, cellName) { 
      	dev["dooya_dm35eq_x_0x0106/Position"] = newValue;	
      	dev["dooya_dm35eq_x_0x0105/Position"] = newValue;	  
      	log("Изменение положения штор в Кабинете на {}", newValue); 
    }
});

var switch05_pressed = false;		
// Ручное управление положением правой роллшторы в Кабинете по нажатию на настенный выключатель
defineRule("Cabinet Shader 05 Wall Switch Control", {
	whenChanged: ["wb-gpio/EXT1_IN7", "wb-gpio/EXT1_IN8"],
	then: function(newValue, devName, cellName) {
		var controlCurtain = "dooya_dm35eq_x_0x0105/Position";
		var stopCurtain = "dooya_dm35eq_x_0x0105/Stop";
		var buttonUp = "EXT1_IN7";
		var buttonDown = "EXT1_IN8";
		if (newValue) {
			log("Нажата кнопка {}  (повторно: {})", cellName, switch05_pressed);
			if (cellName == buttonUp && !switch05_pressed) {
	 			dev[controlCurtain] = 100;
	 			switch05_pressed = true;
	 			startTimer("next_press05", 60 * 1000);
			} else if (cellName == buttonDown && !switch05_pressed) {
	 			dev[controlCurtain] = 0;
	 			switch05_pressed = true;
	 			startTimer("next_press05", 60 * 1000);
			} else {
				dev[stopCurtain] = true;
			    switch05_pressed = false;
			    timers.next_press05.stop();
			}	
		}
	}
}); 

defineRule("Stop Curtain 05", {
  when: function () {return  timers.next_press05.firing},
  then: function () {
      switch05_pressed = false;
      timers.next_press05.stop();
    }
});
		
var switch06_pressed = false;
// Ручное управление положением левой роллшторы в Кабинете по нажатию на настенный выключатель
defineRule("Cabinet Shader 06 Wall Switch Control", {
	whenChanged: ["wb-gpio/EXT1_IN9", "wb-gpio/EXT1_IN10"],
	then: function(newValue, devName, cellName) {
		var controlCurtain = "dooya_dm35eq_x_0x0106/Position";
		var stopCurtain = "dooya_dm35eq_x_0x0106/Stop";
		var buttonUp = "EXT1_IN9";
		var buttonDown = "EXT1_IN10";
		if (newValue) {
			log("Нажата кнопка {}  (повторно: {})", cellName, switch06_pressed);
			if (cellName == buttonUp && !switch06_pressed) {
	 			dev[controlCurtain] = 100;
	 			switch06_pressed = true;
	 			startTimer("next_press06", 60 * 1000);
			} else if (cellName == buttonDown && !switch06_pressed) {
	 			dev[controlCurtain] = 0;
	 			switch06_pressed = true;
	 			startTimer("next_press06", 60 * 1000);
			} else {
				dev[stopCurtain] = true;
			    switch06_pressed = false;
			    timers.next_press06.stop();
			}	
		}
	}
});

defineRule("Stop Curtain 06", {
  when: function () {return  timers.next_press06.firing},
  then: function () {
      switch06_pressed = false;
      timers.next_press06.stop();
    }
});

log("added in 06_curtains.js");