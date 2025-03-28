// Обучение AV системы

var config = readConfig("/mnt/data/etc/wb-mqtt-avsystem.conf");

defineVirtualDevice("IR_Trainer", {
  title: "Обучение IR кодам",
  cells: {
    device: {
      type: "text",
      value: ""
    },
    function: {
      type: "text",
      value: ""
    },
    sensor: {
      type: "text",
      value: ""
    },
    bank: {
      type: "text",
      value: ""
    }
  }
});

defineVirtualDevice("IR_Trainer_Control", {
  title: "Контроль за обучением IR кодам",
  cells: {
    nextDevice: {
      type: "pushbutton",
      value: false
    },
    prevDevice: {
      type: "pushbutton",
      value: false
    },
    nextFunction: {
      type: "pushbutton",
      value: false
    },
    prevFunction: {
      type: "pushbutton",
      value: false
    },
    rom_size: {
      type: "value",
      value: ""
    },
    learn: {
      type: "switch",
      value: false
    },
    execute: {
      type: "pushbutton",
      value: false
    }
  }
});

var currentDevice = 0;
var currentFunction = 0;
UpdateIRControl();

defineRule("next_device", {
	whenChanged: "IR_Trainer_Control/nextDevice",
	then: function(newValue, devName, cellName) { //  Всё включено	
		if (currentDevice < config.avdevice.length - 1) {
			currentDevice++;
			currentFunction = 0;
			UpdateIRControl();
		}
	}
});

defineRule("prev_device", {
	whenChanged: "IR_Trainer_Control/prevDevice",
	then: function(newValue, devName, cellName) { //  Всё включено	
		if (currentDevice > 0) {
			currentDevice--;
			currentFunction = 0;
			UpdateIRControl();
		}
	}
});

defineRule("next_function", {
	whenChanged: "IR_Trainer_Control/nextFunction",
	then: function(newValue, devName, cellName) { //  Всё включено	
		if (currentFunction < config.avdevice[currentDevice].device.length - 1) {
			currentFunction++;
			UpdateIRControl();
		}
	}
});

defineRule("prev_function", {
	whenChanged: "IR_Trainer_Control/prevFunction",
	then: function(newValue, devName, cellName) { //  Всё включено	
		if (currentFunction > 0) {
			currentFunction--;
			UpdateIRControl();
		}
	}
});

defineRule("test_IR_code", {
	whenChanged: "IR_Trainer_Control/execute",
	then: function(newValue, devName, cellName) { //  Всё включено	
		var func = config.avdevice[currentDevice].device;
		var rom = func[currentFunction].location + "/Play from ROM" + func[currentFunction].rom;
	  	log(rom);
		dev[rom] = true;
	}
});

defineRule("learn_IR_code", {
	whenChanged: "IR_Trainer_Control/learn",
	then: function(newValue, devName, cellName) { //  Всё включено	
		var func = config.avdevice[currentDevice].device;
		var rom = func[currentFunction].location + "/Learn to ROM" + func[currentFunction].rom;
	  	log(rom);
      	if (dev["IR_Trainer_Control/learn"]) {
			dev[rom] = true;
        }
      	else {
			dev[rom] = false;
        }
	}
});

function UpdateIRControl() {
	dev["IR_Trainer"]["device"] = config.avdevice[currentDevice].name;
	var func = config.avdevice[currentDevice].device;
	dev["IR_Trainer"]["function"] = func[currentFunction].button + ": [" + func[currentFunction].text + "]";
	dev["IR_Trainer"]["sensor"] = func[currentFunction].location;
	dev["IR_Trainer"]["bank"] = "ROM" + func[currentFunction].rom;
  	var size = func[currentFunction].location + "/ROM" + func[currentFunction].rom + " size";
  	log(size + " = " + dev[size]);
  	dev["IR_Trainer_Control"]["rom_size"] = dev[size];
}

function ExecuteIR() {
}
