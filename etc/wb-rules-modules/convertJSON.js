exports.jsonConvert = function JSONConvert(json_io) {
 	var obj  = {};  // набор
	obj  = json_io;
	for (i = 0; i < obj.length; i++) {
	  key = obj[i].mark; // выделение ключей
	  obj[key] = obj[i]; // сопоставление элементов ключам
	  delete obj[i]; // удаление элемента
	}
	return obj; // возврат модифицированного массива
};

// Оставить последнюю строку пустой.
