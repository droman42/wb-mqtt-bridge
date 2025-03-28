var bot = require("moduleTelegram2wb");

var allowedUsers = ["Prefixx","droman42","ryshkus"];
//var setpoints_conf = readConfig("mnt/data/etc/wb-mqtt-setpoints.conf");

//	for (var u = 0; u < setpoints_conf.telegram.length; u++) {
//		allowedUsers[u] = setpoints_conf.telegram[u].userName; 
//	}
//	allowedUsers[0] = "Prefixx"; 
//	log(allowedUsers);
token = "5948180288:AAFNO5pX8D9qtUUQtClYCjSqc6DhCglohaU"; // Укажите токен бота, можно узнать у @BotFather
deviceName = "telegram2wb";
cmdTopic = "{}/{}".format(deviceName, bot.mqttCmd);
msgTopic = "{}/{}".format(deviceName, bot.mqttMsg);
rawMsgTopic = "{}/{}".format(deviceName, bot.mqttRawMsg);
callbackTopic = "{}/{}".format(deviceName, bot.mqttCallback);

bot.init(token, allowedUsers, deviceName);

defineRule("bot_cmd_controller", {
    whenChanged: cmdTopic,
    then: function (newValue, devName, cellName) {

        cmd = JSON.parse(newValue);
        dev[devName][cellName] = "{}";

        if (!isEmptyJson(cmd)) { // Проверяем, что команда не пустая
            botname = bot.getUserName();

            // Если сообщение групповое, то проверяем адресата. Если адресовано не нам, то игнорируем.
            if (cmd.chatType === "group"
                && cmd.mentions.indexOf(bot.getUserName()) === -1) {
                return;
            }

            switch (cmd.command) {
                case "/start":
                case "/help":
                    cmdHelp(cmd)
                    break;
                case "/getfile":
                    cmdGetFile(cmd)
                    break;
                case "/lightOn":
                    cmdLightOn(cmd)
                    break;
                case "/kbd":                
                    cmdKbd(cmd)
                    break;
                case "/rst":                
                    cmdReset(cmd)
                    break;  
                case "Освещение":   
                    cmdLight(cmd)
                    break; 
                case "Подогрев":   
                    cmdChangeMode(cmd)
                    break; 
                case "Измерения":   
                    cmdParameters(cmd)
                    break;             
                case "Закрыть": 
                    cmdCloseKeyboard(cmd)
                    break;
                default:
                    cmdUnknown(cmd);
                    break;
            } 
        }
    }
});

defineRule("bot_callback_controller", {
    whenChanged: callbackTopic,
    then: function (newValue, devName, cellName) {

        callback = JSON.parse(newValue);
        dev[devName][cellName] = "{}";
       
        switch (callback.data) {
            case "lightOn":
                cmdLightOn(callback)
                break;
            case "lightOff":
                cmdLightOff(callback)
                break;
            case "changeMode":
                cmdChangeMode(callback)
                break;
            case "startTime":
                cmdStartTime(callback)
                break;
            case "play":
                cmdPlay(callback)
                break;
            case "standby":
                cmdStandby(callback)
                break;
            case "params":
                cmdParameters(callback)
                break;
            case "resetProcess":
                cmdReset(callback)
                break;
            case "deleteMessage":
                cmdDeleteMessage(callback)
                break;
            default:
                break;
        }

    }
});

function cmdHelp(cmd) {
    text = "Привет, я бот контроллера Wiren Board \nЯ знаю команды:\n"
    text += "/start или /help — справка\n"
//    text += '/getfile "/path/filename.txt" — пришлю указанный файл\n'
//    text += '/cputemp — температура процессора\n'
    text += '/kbd — клавиатура\n'

    sendMsg(cmd.chatId, text, cmd.messageId);
}

function cmdUnknown(cmd) {
    text = "Я не знаю команду `{}`. \n".format(cmd.command);
    text += "Список команд смотрите в справке: /help";
    sendMsg(cmd.chatId, text, cmd.messageId);
}

function cmdGetFile(cmd) {
    text = "Запрошенный файл";
    sendDoc(cmd.chatId, text, cmd.messageId, cmd.args);
}

function cmdLightOff(cmd) {
//	dev["wb-mr3_58/K1"] = false;
//	dev["wb-mr3_58/K2"] = false;
    text = "--Освещение выключено--";
    sendMsg(cmd.chatId, text, cmd.messageId);
}

function cmdParameters(cmd) {
    text = "Температура на улице: {}".format(dev["wb-w1/28-3ccaf6492832"] + " °C");
    text = text + "%0A" + "Ветер на улице: {}".format(dev["wind/Speed"] + " m/s");
    text = text + "%0A" + "Температура внутри: {}".format(dev["air_sensor/Temperature"] + " °C");
    text = text + "%0A" + "Влажность внутри: {}".format(dev["air_sensor/Humidity"] + " %,RH");
    text = text + "%0A" + "Давление купола: {}".format(dev["es_a300_1/Pressure Difference"] + " Pa");
    sendMsg(cmd.chatId, text, cmd.messageId);
}

function cmdReset(cmd) {
//	runShellCommand("service wb-rules restart");
    text = "Сброс в начальное состояние";
    sendMsg(cmd.chatId, text, cmd.messageId);
}

/* Примеры клавиатур */

function cmdKbd(cmd) {
    text =  "Главное меню";
    kbdCode = {
        keyboard: [
            ["Свет Выкл"],
            ["Измерения"],
            ["Закрыть"]],
        "resize_keyboard": true,
        "one_time_keyboard": false
    };

    sendKbd(cmd.chatId, text, cmd.messageId, JSON.stringify(kbdCode));
}

function cmdCloseKeyboard(cmd) {
    text = "Закрыл клавиатуру";
    kbdCode = {
        "keyboard": [],
        'remove_keyboard': true
    };

    sendKbd(cmd.chatId, text, cmd.messageId, JSON.stringify(kbdCode));
}

function cmdLight(cmd) {
//	var HL1 = dev[hl1] ? "ВКЛ":"ВЫКЛ";
//	var HL2 = dev[hl2] ? "ВКЛ":"ВЫКЛ";
    text = "Свет";
    kbdCode = {
        "inline_keyboard": [[
            { "text": "Выключить", "callback_data": "lightOff" }
        ]],
        "resize_keyboard": true,
        "one_time_keyboard": false
    };

    sendKbd(cmd.chatId, text, cmd.messageId, JSON.stringify(kbdCode));
}

function cmdDeleteMessage(cmd) {

    rawMsg = {
        "method": "deleteMessage",
        "chat_id": cmd.chatId,
        'message_id': cmd.messageId
    };
    
    sendRawMsg(rawMsg);
}

/* Отправка сообщений, документов и клавиатур */
function sendMsg(chatId, text, replyTo) {
    log("{} {} {}", chatId, text, replyTo)
    msg = {
        chatId: chatId,
        text: text,
        messageId: replyTo
    }

    writeMsgToMqtt(msg);
}

function sendRawMsg(rawMsg) {
    log("{}", rawMsg)

    writeRawMsgToMqtt(rawMsg);
}

function sendDoc(chatId, text, replyTo, document) {
    msg = {
        chatId: chatId,
        messageId: replyTo,
        text: text,
        document: document
    }

    writeMsgToMqtt(msg);
}

function sendKbd(chatId, text, replyTo, kbdCode) {
    log("{} {} {} {}", chatId, text, replyTo, kbdCode);

    msg = {
        chatId: chatId,
        text: text,
        messageId: replyTo,
        keyboard: kbdCode
    }

    writeMsgToMqtt(msg);
}


/* Прочее */
function isEmptyJson(jsonString) {
    return !Object.keys(jsonString).length;
}

function writeMsgToMqtt(msg) {
    dev[msgTopic] = JSON.stringify(msg);
}

function writeRawMsgToMqtt(rawMsg) {
    dev[rawMsgTopic] = JSON.stringify(rawMsg);
}

log("added to 09_telegrm.js");