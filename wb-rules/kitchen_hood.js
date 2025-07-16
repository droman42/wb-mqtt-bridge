// Kitchen hood management
// Kitchen hood light control with debounce
defineRule("Kitchen Light Switch Control", {
    whenChanged: ["wb-mr6c_47/K6"],
    then: function(newValue, devName, cellName) {
        // Process the signal immediately
        log("Rule triggered: " + newValue);
        // Action logic:
        // log("Before: " + dev["kitchen_hood/set_light"]);
        dev["kitchen_hood/set_light"] = dev["wb-mr6c_47/K6"];
	}
}); 

