exports.shortLongDoublePress = function shortLongDoublePress(name,
															trigger,
															timeToNextPress,
															timeOfLongPress,
															actionLongPress,
															actionDoublePress,
															actionSinglePress) {
	var buttonPressedCounter = 0;
	var timerWaitNextShortPress = null;
	var timerLongPress = null;
	var isLongPress = false;

	defineRule(name, {
		whenChanged: trigger,
		then: function(newValue, devName, cellName) {

			// If button is pressed, wait for a long press
			if (newValue) {

				if (timerWaitNextShortPress)
					clearTimeout(timerWaitNextShortPress);

				timerLongPress = setTimeout(function() { // Длинное нажатие приводит к отключению всего света
					actionLongPress();
					log(">>>>>>> long press <<<<<<  : " + trigger);
					isLongPress = true;  // Long press identified, we will skip short press
					buttonPressedCounter = 0;
					timerLongPress = null;
				}, timeOfLongPress);

			}

			// If button is released, then it is not a "long press", start to count clicks
			else {
				if (!isLongPress) {
					if (timerLongPress) clearTimeout(timerLongPress);
					buttonPressedCounter += 1;
					timerWaitNextShortPress = setTimeout(function() {
						switch (buttonPressedCounter) {
							// Counter equals 1 - it's a single short press
							case 1:
								actionSinglePress();
								log(">>>>>> short press - single <<<<<<  : " + trigger);
								break;
							// Counter equals 2 - it's a double short press
							case 2:
								actionDoublePress();
								log(">>>>>> short press - double <<<<<<  : " + trigger);
								break;
						}
						// Reset the counter
						buttonPressedCounter = 0;
						timerWaitNextShortPress = null;
					}, timeToNextPress);
				}
				isLongPress = false;
			}

		}
	});

}

// Оставить последнюю строку пустой.
