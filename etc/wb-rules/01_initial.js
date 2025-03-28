// Раздел программы для размещения начальных установок

// ------------------Настройки выбора режима подключения розеток-------------

defineVirtualDevice("power_lvl_switch", {
  title: "Подключение розеток",
  cells: {
    short_absence: {
      type: "switch",
      value: true
    },
    at_home: {
      type: "switch",
      value: true
    }
  }
});

// ------------------Настройки режима протечки воды-------------

defineVirtualDevice("leakage_settings", {
  title: "Протечка воды",
  cells: {
    alarm_off: {
      type: "pushbutton"
    },
    cleaning: {
      type: "pushbutton"
    },
    cleaning_on: {
      type: "switch",
      value: false,
	  readonly: true
    },
    arm_delay: {
      type: "range",
      value: 5,
      max : 60
    }
  }
});

// ------------------Виртуальные устройства для программирования сценариев-------------

defineVirtualDevice("scenarios", {
  title: "Сценарии автоматизации",
  cells: {
    scene01: {
      type: "switch",
      value: false,
	  readonly: true
    },
    scene02: {
      type: "switch",
      value: false,
	  readonly: true
    },
    scene03: {
      type: "switch",
      value: false,
	  readonly: true
    },
    scene04: {
      type: "switch",
      value: false,
	  readonly: true
    },
    scene05: {
      type: "switch",
      value: false,
	  readonly: true
    },
  }
});

// ------------------Первоначальные установки после перезагрузки-------------
var rd = require("moduleRestore");

var initializationTimer = setTimeout(function() {
	if (dev["power_lvl_switch"]["at_home"] || dev["power_lvl_switch"]["short_absence"]) {
		if(dev["seasonal_switch/heating"]) {
			dev["wb-mwac_46/K1"] = true;  //  Кран 01 открыть после перезагрузки (Обогрев)
			dev["wb-mwac_46/K2"] = true;  //  Кран 02 открыть после перезагрузки (Обогрев)
		}
		dev["wb-mwac_54"]["K1"] = true; //  Кран 03 открыть после перезагрузки (ХВС)
		dev["wb-mwac_54"]["K2"] = true; //  Кран 04 открыть после перезагрузки (ГВС)
	} 
	if (dev["power_lvl_switch"]["at_home"]) {
		rd.restoreLights();
	}
	initializationTimer = null;
}, 30000); 

// ------------------Виртуальные устройства для датчиков движения Wirenboard-------------

defineVirtualDevice("motion_trigger", {
  title: "Регистрация движения",
  cells: {
    sc07: {
      type: "switch",
      value: true,
	  readonly: false
    },
    sc07_treshold: {
      type: "range",
      value: 40,
      max : 600
    },    
    sc09: {
      type: "switch",
      value: true,
	  readonly: false
    },
    sc09_treshold: {
      type: "range",
      value: 40,
      max : 600
    }
  }
});

var motion_sc07_timer = null;
defineRule("Sc07 triggered", {
	whenChanged: ["wb-msw-v3_227/Current Motion"],
	then: function(newValue, devName, cellName) {
		if (newValue >= dev["motion_trigger/sc07_treshold"]) {
			if (motion_sc07_timer != null) clearTimeout(motion_sc07_timer);	
		  	// Взведение флага "Движение обнаружено!"
			dev["motion_trigger/sc07"] = false;
			motion_sc07_timer = setTimeout(function () {
				dev["motion_trigger/sc07"] = true;
				motion_sc07_timer = null;
			}, 400);
		}
	}
});

var motion_sc09_timer = null;
defineRule("Sc09 triggered", {
	whenChanged: ["wb-msw-v3_231/Current Motion"],
	then: function(newValue, devName, cellName) {
		if (newValue >= dev["motion_trigger/sc09_treshold"]) {
			if (motion_sc09_timer != null) clearTimeout(motion_sc09_timer);	
		  	// Взведение флага "Движение обнаружено!"
			dev["motion_trigger/sc09"] = false;
			motion_sc09_timer = setTimeout(function () {
				dev["motion_trigger/sc09"] = true;
				motion_sc09_timer = null;
			}, 400);
		}
	}
});

log("added in 01_initial.js");
