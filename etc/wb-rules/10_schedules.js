//'use strict'; 
// Режим работы системы по расписаниям

var schedules = [];	
var rooms = [];	
var types = [];	
var names = [];	
var scheduledSetpoint = [];
var now;
var config = readConfig("mnt/data/etc/wb-mqtt-shedules.conf");
 
defineRule("Cron Every Minute", { // Проверяем каждую минуту совпадение времени с уставкой режима
	when: cron("0 * * * * *"),
	then: function() {
		now = new Date();
		dev["setpoints_light/time_current"] = now.getHours() + ":" + now.getMinutes();
//		log("Schedule Ticker: {}", dev["setpoints_light/time_current"]);
		for (var s = 0; s < config.schedule.length; s++) {
			rooms[s] = config.schedule[s].alias;
			types[s] = config.schedule[s].type;
			names[s] = config.schedule[s].name;
			schedules[s] = config.schedule[s][types[s]];
//			log("Schedule for {} ({} - {}): {}", names[s], rooms[s] ,types[s], JSON.stringify(schedules[s]));
			scheduledSetpoint[s] = ApplyScheduledSetpoints(rooms[s], types[s], schedules[s]);
			if(scheduledSetpoint[s]) {
				switch (types[s]) {
			        case "light":
			        	dev["setpoints_light/day_mode"] = scheduledSetpoint[s];
						log("Смена времени суток: {}", dev["setpoints_light/day_mode"]);
			          break;
			        case "curtain":
			        	dev["setpoints_curtain/" + rooms[s] + "_position"] = parseInt(scheduledSetpoint[s]);
      					log("Расписание штор {} на {}", rooms[s], parseInt(scheduledSetpoint[s])); 
			          break;
			        case "floor":
						dev["setpoints_floor/" + rooms[s] + "_temp"] = parseInt(scheduledSetpoint[s]);
			          break;
			        case "radiator":		        
						dev["setpoints_radiator/" + rooms[s] + "_temp"] = parseInt(scheduledSetpoint[s]);
			          break;
			        default:
			          log('Неопознанное расписание для {} - {}', types[s], rooms[s]);
			    }				
			}	
		}
	}  
});
 
function ApplyScheduledSetpoints(roomName, dev_type, schedule) {
	if(dev["power_lvl_switch/at_home"] && dev["setpoints_" + dev_type + "/" + roomName + "_permit_schedule"]) { // Разрешение работы по расписанию 
		for (var p = 0; p < schedule.length; p++) {
			var point = [];
			point[0] = parseInt(schedule[p].hour); // Выделение Час из выборки
			point[1] = parseInt(schedule[p].minute); // Выделение Минута из выборки
			switch (schedule[p].weekday) { // Выделение День недели из выборки
		        case "Понедельник":
					point[2] = 1;
		          break;
		        case "Вторник":
					point[2] = 2;
		          break;
		        case "Среда":
					point[2] = 3;
		          break;
		        case "Четверг": 
					point[2] = 4;
		          break;
		        case "Пятница": 
					point[2] = 5;
		          break;
		        case "Суббота":  
					point[2] = 6;
		          break;
		        case "Воскресенье": 
					point[2] = 0;
		          break;
		        case "==Ежедневно==": 
					point[2] = now.getDay();
		          break;
		        case "--Будни":  
			    	if(now.getDay() == 1 || now.getDay() == 2 || now.getDay() == 3 || now.getDay() == 4 || now.getDay() == 5) {
						point[2] = now.getDay();
					} else {
						point[2] = -1;
					}
		          break;
		        case "--Выходные":  
			    	if(now.getDay() == 0 || now.getDay() == 6) {
						point[2] = now.getDay();
					} else {
						point[2] = -1;
					}
		          break;
		        default:
		          log('Я таких значений не знаю: {}', point[2]);
		    }	    
			var sp = schedule[p].setpoint; // Выделение текстового Режима из выборки;
			if (point[0] == now.getHours() && point[1] == now.getMinutes() && point[2] == now.getDay()) {
                return sp;
			} 
		}	
		return;			
	}	
}


	
// Восстановление значения по расписанию после отключения режима "Отсутствие"
	
defineRule("Track floor mode", { // Отслеживание изменения режима присутствия и применение нужных уставок 
//	whenChanged: ["wb-gpio/D1_OUT"],
	whenChanged: ["power_lvl_switch/at_home"],
	then: function(newValue, devName, cellName) {
		if(dev["setpoints_" + dev_type + "/" + roomName + "_permit_schedule"]) {
			now = new Date();		
			for (var s = 0; s < config.schedule.length; s++) {
				if (newValue) {
					rooms[s] = config.schedule[s].alias;
					types[s] = config.schedule[s].type;
					names[s] = config.schedule[s].name;
					schedules[s] = config.schedule[s][types[s]];
		//			log("Schedule for {} ({} - {}): {}", names[s], rooms[s] ,types[s], JSON.stringify(schedules[s]));
					scheduledSetpoint[s] = RestoreScheduledSetpoints(rooms[s], types[s], schedules[s]);
					if(scheduledSetpoint[s]) {
						switch (types[s]) {
					        case "light":
					        	dev["setpoints_light/day_mode"] = scheduledSetpoint[s];
								log("Смена времени суток: {}", dev["setpoints_light/day_mode"]);
					          break;
					        case "curtain":
					        	dev["setpoints_curtain/" + rooms[s] + "_position"] = parseInt(scheduledSetpoint[s]);
					          break;
					        case "floor":
								dev["setpoints_floor/" + rooms[s] + "_temp"] = parseInt(scheduledSetpoint[s]);
					          break;
					        case "radiator":		        
								dev["setpoints_radiator/" + rooms[s] + "_temp"] = parseInt(scheduledSetpoint[s]);
					          break;
					        default:
					          log('Неопознанное расписание для {} - {}', types[s], rooms[s]);
					    }				
					}	
				} else {
					log("Ушел!");
					switch (types[s]) {
				        case "light":
				        
				          break;
				        case "curtain":
				        
				          break;
				        case "floor":
							dev["setpoints_floor/" + rooms[s] + "_temp"] = dev["setpoints_" + types[s] + "/_" + types[s] + "_eco"];
				          break;
				        case "radiator":		        
							dev["setpoints_radiator/" + rooms[s] + "_temp"] = dev["setpoints_" + types[s] + "/_" + types[s] + "_eco"];
				          break;
				        default:
				          log('Неопознанное расписание для {} - {}', types[s], rooms[s]);
				    }
				}
			}			
		} else {
			log("Восстановление уставок при возвращении отменено, так как расписание отключено.");
		}	
	}
});	
		
function RestoreScheduledSetpoints(roomName, dev_type, schedule) {
	var nowMinutes = now.getHours() * 60 + now.getMinutes();
	var currentDaySchedule = {};
	var min = 24 * 60, min_negative = 0, p_min = null, p_min_negative = null;

	log("Now: {}:{} ({})", now.getHours(), now.getMinutes(), nowMinutes);
	for (var p = 0; p < schedule.length; p++) {
		var point = [];
		point[0] = parseInt(schedule[p].hour); // Выделение Час из выборки
		point[1] = parseInt(schedule[p].minute); // Выделение Минута из выборки
		switch (schedule[p].weekday) {
	        case "Понедельник":
				point[2] = 1;
	          break;
	        case "Вторник":
				point[2] = 2;
	          break;
	        case "Среда":
				point[2] = 3;
	          break;
	        case "Четверг": 
				point[2] = 4;
	          break;
	        case "Пятница": 
				point[2] = 5;
	          break;
	        case "Суббота":  
				point[2] = 6;
	          break;
	        case "Воскресенье": 
				point[2] = 0;
	          break;
	        case "==Ежедневно==": 
				point[2] = now.getDay();
	          break;
	        case "--Будни":  
		    	if(now.getDay() == 1 || now.getDay() == 2 || now.getDay() == 3 || now.getDay() == 4 || now.getDay() == 5) {
					point[2] = now.getDay();
				} else {
					point[2] = -1;
				}
	          break;
	        case "--Выходные":  
		    	if(now.getDay() == 0 || now.getDay() == 6) {
					point[2] = now.getDay();
				} else {
					point[2] = -1;
				}
	          break;
	        default:
	          log('Я таких значений не знаю: {}', point[2]);
        }
		if (point[2] == now.getDay()) {
			currentDaySchedule[p] = schedule[p];
			currentDaySchedule[p].hoursAndMinutesDifference = nowMinutes - schedule[p].hour * 60 + schedule[p].minute;
			if (currentDaySchedule[p].hoursAndMinutesDifference < 0 && currentDaySchedule[p].hoursAndMinutesDifference < min_negative) {
				min_negative = currentDaySchedule[p].hoursAndMinutesDifference;
				p_min_negative = p;
			}
			if (currentDaySchedule[p].hoursAndMinutesDifference >= 0 && currentDaySchedule[p].hoursAndMinutesDifference < min) {
				min = currentDaySchedule[p].hoursAndMinutesDifference;
				p_min = p;
			}
			log("schedule in {} for {} today: {} ({})", roomName, dev_type, JSON.stringify(currentDaySchedule[p]), p);
		} 
	}
	if (p_min == null) {		// Если нет предыдущих значений в этом дне, то подставляем ближайшее в предыдущем дне
		min = min_negative;
		p_min = p_min_negative;		
	}
	if (schedule[p_min].setpoint) { // Проверить, есть ли хоть одно значение для текущей даты
		log("Дома!");
		log("schedule min {} ({}): {}", min , p_min, schedule[p_min].setpoint);
		return schedule[p_min].setpoint;
	} else {
		log("Data is absent!");
		return;
	}
}	


log("added in 10_schedules.js");