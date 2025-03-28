defineVirtualDevice("weather", { //Виртуальное устройство для записи данных и отправки их в MQTT
	title: "Погода Садовые Кварталы",
	cells: {
		temperature: {
			type: "temperature",
			value: -12.0,
		},
		humidity: {
			type: "rel_humidity",
			value: 75,
		},
		wind: {
			type: "wind_speed",
			value: 3,
		}
	}
});

defineRule("weather_call", {	// регулярный запрос к серверу погоды
  when: cron("@every 30m"),
  then: function() {
	var waitResponce = null;
		runShellCommand("wget -qO /mnt/data/etc/wb-weather.conf 'https://api.openweathermap.org/data/2.5/weather?id=524901&lang=ru&appid=770d628cc0ab19fc6b89bb025f50bf1d&units=metric'");
		waitResponce = startTimer("wait_weather", 5 * 1000);  		// запустили таймер на задержку для получения данных погоды	
    	log("Request sent");
  }
}); 

defineRule("parse_weather", {	// чтение полученных от сервера данных погоды
  when: function() { 
    return timers.wait_weather.firing;
  },
  then: function() {
  	weather_data = readConfig("/mnt/data/etc/wb-weather.conf");
    dev["weather/temperature"] = weather_data.main.temp;
    dev["weather/humidity"] = weather_data.main.humidity;
    dev["weather/wind"] = weather_data.wind.speed;
    log("Time: {}".format(weather_data.dt));
    log("Temperature is: {}".format(weather_data.main.temp));
    log("Humidity is: {}".format(weather_data.main.humidity));
    log("Wind speed is: {}".format(weather_data.wind.speed));
   waitResponce = null;
  }
});
log("12_weather.js updated!");