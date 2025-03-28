var lights = [
//	"wb-mr6c_47/K3", 	// торшер в Гостиной
//	"wb-mr6c_52/K2",	// подсветка в Ванной
	"wb-mr6c_51/K6",	// бра справа в Спальне
	"wb-mr6c_52/K1"		//бра слева в Спальне
];

exports.restoreLights = function() {
	lights.forEach(function(item, i, arr) {
		dev[item] = true;
//		log("Initial: " + item + " = true");
	});
    return;
}