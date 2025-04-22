// Kitchen hood management

// ------------------Virtual device to support kitchen hood-------------

defineVirtualDevice("kitchen_hood", {
    title: "Контроль за вытяжкой",
    cells: {
      light: {
        type: "switch",
		readOnly: false,
        value: false
      },
      speed: {
        type: "range",
        readOnly: false,
        max: 4,
        value: 0
      }
    }
  });

// Kitchen hood light control with debounce
defineRule("Kitchen Light Switch Control", {
    whenChanged: ["wb-mr6c_47/K6"],
    then: function(newValue, devName, cellName) {
        // Process the signal immediately
        log("Rule triggered: " + newValue);
        // Action logic:
        // log("Before: " + dev["kitchen_hood/light"]);
        dev["kitchen_hood/light"] = dev["wb-mr6c_47/K6"];
	}
}); 

