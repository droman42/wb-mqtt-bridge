exports.sunRiseDown = function sunRise(date, minutesAfterSunrise, minutesAfterSunset, lat, lng) {

	/*
	 (c) 2011-2015, Vladimir Agafonkin
	 SunCalc is a JavaScript library for calculating sun/moon position and light phases.
	 https://github.com/mourner/suncalc
	*/

	// shortcuts for easier to read formulas

	var PI = Math.PI,
		sin = Math.sin,
		cos = Math.cos,
		tan = Math.tan,
		asin = Math.asin,
		atan = Math.atan2,
		acos = Math.acos,
		rad = PI / 180;

	// sun calculations are based on http://aa.quae.nl/en/reken/zonpositie.html formulas


	// date/time constants and conversions

	var dayMs = 1000 * 60 * 60 * 24,
		J1970 = 2440588,
		J2000 = 2451545;

	function toJulian(date) { return date.valueOf() / dayMs - 0.5 + J1970; }
	function fromJulian(j) { return new Date((j + 0.5 - J1970) * dayMs); }
	function toDays(date) { return toJulian(date) - J2000; }


	// general calculations for position

	var e = rad * 23.4397; // obliquity of the Earth

	function rightAscension(l, b) { return atan(sin(l) * cos(e) - tan(b) * sin(e), cos(l)); }
	function declination(l, b) { return asin(sin(b) * cos(e) + cos(b) * sin(e) * sin(l)); }

	function azimuth(H, phi, dec) { return atan(sin(H), cos(H) * sin(phi) - tan(dec) * cos(phi)); }
	function altitude(H, phi, dec) { return asin(sin(phi) * sin(dec) + cos(phi) * cos(dec) * cos(H)); }

	function siderealTime(d, lw) { return rad * (280.16 + 360.9856235 * d) - lw; }

	function astroRefraction(h) {
		if (h < 0) // the following formula works for positive altitudes only.
			h = 0; // if h = -0.08901179 a div/0 would occur.

		// formula 16.4 of "Astronomical Algorithms" 2nd edition by Jean Meeus (Willmann-Bell, Richmond) 1998.
		// 1.02 / tan(h + 10.26 / (h + 5.10)) h in degrees, result in arc minutes -> converted to rad:
		return 0.0002967 / Math.tan(h + 0.00312536 / (h + 0.08901179));
	}

	// general sun calculations

	function solarMeanAnomaly(d) { return rad * (357.5291 + 0.98560028 * d); }

	function eclipticLongitude(M) {

		var C = rad * (1.9148 * sin(M) + 0.02 * sin(2 * M) + 0.0003 * sin(3 * M)), // equation of center
			P = rad * 102.9372; // perihelion of the Earth

		return M + C + P + PI;
	}

	function sunCoords(d) {

		var M = solarMeanAnomaly(d),
			L = eclipticLongitude(M);

		return {
			dec: declination(L, 0),
			ra: rightAscension(L, 0)
		};
	}


	var SunCalc = {};


	// calculates sun position for a given date and latitude/longitude

	SunCalc.getPosition = function(date, lat, lng) {

		var lw = rad * -lng,
			phi = rad * lat,
			d = toDays(date),

			c = sunCoords(d),
			H = siderealTime(d, lw) - c.ra;

		return {
			azimuth: azimuth(H, phi, c.dec),
			altitude: altitude(H, phi, c.dec)
		};
	};


	// sun times configuration (angle, morning name, evening name)

	var times = SunCalc.times = [
		[-0.833, 'sunrise', 'sunset'],
		[-0.3, 'sunriseEnd', 'sunsetStart'],
		[-6, 'dawn', 'dusk'],
		[-12, 'nauticalDawn', 'nauticalDusk'],
		[-18, 'nightEnd', 'night'],
		[6, 'goldenHourEnd', 'goldenHour']
	];

	// adds a custom time to the times config

	SunCalc.addTime = function(angle, riseName, setName) {
		times.push([angle, riseName, setName]);
	};


	// calculations for sun times

	var J0 = 0.0009;

	function julianCycle(d, lw) { return Math.round(d - J0 - lw / (2 * PI)); }

	function approxTransit(Ht, lw, n) { return J0 + (Ht + lw) / (2 * PI) + n; }
	function solarTransitJ(ds, M, L) { return J2000 + ds + 0.0053 * sin(M) - 0.0069 * sin(2 * L); }

	function hourAngle(h, phi, d) { return acos((sin(h) - sin(phi) * sin(d)) / (cos(phi) * cos(d))); }

	// returns set time for the given sun altitude
	function getSetJ(h, lw, phi, dec, n, M, L) {

		var w = hourAngle(h, phi, dec),
			a = approxTransit(w, lw, n);
		return solarTransitJ(a, M, L);
	}


	// calculates sun times for a given date and latitude/longitude

	SunCalc.getTimes = function(date, lat, lng) {

		var lw = rad * -lng,
			phi = rad * lat,

			d = toDays(date),
			n = julianCycle(d, lw),
			ds = approxTransit(0, lw, n),

			M = solarMeanAnomaly(ds),
			L = eclipticLongitude(M),
			dec = declination(L, 0),

			Jnoon = solarTransitJ(ds, M, L),

			i, len, time, Jset, Jrise;


		var result = {
			solarNoon: fromJulian(Jnoon),
			nadir: fromJulian(Jnoon - 0.5)
		};

		for (i = 0, len = times.length; i < len; i += 1) {
			time = times[i];

			Jset = getSetJ(time[0] * rad, lw, phi, dec, n, M, L);
			Jrise = Jnoon - (Jset - Jnoon);

			result[time[1]] = fromJulian(Jrise);
			result[time[2]] = fromJulian(Jset);
		}

		return result;
	};

	/**
	 * Adds time to a date. Modelled after MySQL DATE_ADD function.
	 * Example: dateAdd(new Date(), 'minute', 30)  //returns 30 minutes from now.
	 *
	 * @param date  Date to start with
	 * @param interval  One of: year, quarter, month, week, day, hour, minute, second
	 * @param units  Number of units of the given interval to add.
	 */
	function dateAdd(date, interval, units) {
		var ret = new Date(date); //don't change original date
		var checkRollover = function() { if (ret.getDate() != date.getDate()) ret.setDate(0); };
		switch (interval.toLowerCase()) {
			case 'year': ret.setFullYear(ret.getFullYear() + units); checkRollover(); break;
			case 'quarter': ret.setMonth(ret.getMonth() + 3 * units); checkRollover(); break;
			case 'month': ret.setMonth(ret.getMonth() + units); checkRollover(); break;
			case 'week': ret.setDate(ret.getDate() + 7 * units); break;
			case 'day': ret.setDate(ret.getDate() + units); break;
			case 'hour': ret.setTime(ret.getTime() + units * 3600000); break;
			case 'minute': ret.setTime(ret.getTime() + units * 60000); break;
			case 'second': ret.setTime(ret.getTime() + units * 1000); break;
			default: ret = undefined; break;
		}
		return ret;
	}

	times = SunCalc.getTimes(date, lat, lng);
	var sunrise = times.sunrise;
	var sunriseCorrected = dateAdd(times.sunrise, 'minute', minutesAfterSunrise);
	var sunset = times.sunset;
	var sunsetCorrected = dateAdd(times.sunset, 'minute', minutesAfterSunset);


//	log("-------------------------------------");

	var day_begin = [sunriseCorrected.getHours(), sunriseCorrected.getMinutes()], evening_begin = [sunsetCorrected.getHours(), sunsetCorrected.getMinutes()];
	var hours_now = date.getHours(), minutes_now = date.getMinutes();
//	dev["time_mode_control/time_current"] = hours_now + ":" + minutes_now;
	if (((parseInt(day_begin[0]) * 60 + parseInt(day_begin[1])) < (hours_now * 60 + minutes_now)) &&
		((hours_now * 60 + minutes_now) < (parseInt(evening_begin[0]) * 60 + parseInt(evening_begin[1])))) {
//		log("Time: " + hours_now + ":" + minutes_now + " --DAY--");
		return true;
	} else {
//		log("Time: " + hours_now + ":" + minutes_now + " --EVENING--");
		return false;
	}



	//	now = new Date();
	//	//now = new Date("2017-01-20 23:22:30.719+03:00");
//	log("-------------------------------------");
//	log("Заданная дата\t", date);
//	log("Восход\t\t", sunrise);
//	log("Закат\t\t", sunset);
//	log("От Восхода смещено\t\t", sunriseCorrected);
//	log("От Заката смещено\t\t", sunsetCorrected);

}
