// Грузим конфигурацию устройств
module.static.devices = readConfig("mnt/data/etc/wb-mqtt-avsystem.conf");

// Грузим конфигурацию сценариев
module.static.scenarios = readConfig("mnt/data/etc/wb-mqtt-avscenario.conf");

exports.devices = function() {
	return module.static.devices;
};

exports.scenarios = function() {
	return module.static.scenarios;
};

exports.executeIR = function(device, func) {
	var deviceID = -1;
	for(i = 0; i < module.static.devices.avdevice.length; i++) (
		if(module.static.devices.avdevice[i].name == device) {
			deviceID = i;
			break;
		}
	)
	if(deviceID < 0 ) {
		log("Unknown device " + device);
		return;
	}
	
	var funcID = -1;
	var functions = module.static.devices.avdevice[deviceID].device;
	for(j = 0; j < functions.length; j++) (
		if(functions[j].text == func) {
			funcID = j;
			break;
		}
	)
	if(funcID < 0 ) {
		log("Unknown function " + func + " for device " + device);
		return;
	}
	
	exports.executeIRDirect(deviceID, funcID);
};

exports.executeIRDirect = function(deviceNum, funcNum) {
		var func = module.static.devices.avdevice[deviceNum].device;
		var rom = func[funcNum].location + "/Play from ROM" + func[funcNum].rom;
	  	log(rom);
		dev[rom] = true;
};

exports.updateIRControl = function(currentDevice, currentFunction) {
	dev["IR_Trainer"]["device"] = module.static.devices.avdevice[currentDevice].name;
	var func = module.static.devices.avdevice[currentDevice].device;
	dev["IR_Trainer"]["function"] = func[currentFunction].button + ": [" + func[currentFunction].text + "]";
	dev["IR_Trainer"]["sensor"] = func[currentFunction].location;
	dev["IR_Trainer"]["bank"] = "ROM" + func[currentFunction].rom;
  	var size = func[currentFunction].location + "/ROM" + func[currentFunction].rom + " size";
  	log(size + " = " + dev[size]);
  	dev["IR_Trainer_Control"]["rom_size"] = dev[size];
}
