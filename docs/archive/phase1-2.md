# Phase 1 / Phase 2 task log (archived)

> **Archived 2026-05-20.** This is the original Russian Phase 1/2 checklist, kept
> for history. It is **no longer the live backlog** — the items that were still
> open when it was archived have been migrated to `docs/action_plan.md` §5.
> The Miele line was dropped (integration abandoned; `asyncmiele` dependency removed).

## PHASE 1
- [x] Доработка FastAPI - описательная часть (переход на схемы) + проверить все функции
- [x] BaseDevice - зачем вся конфига является частью state?
- [x] Проверить работу всех инфракрасных девайсов, добавить Play в Zappiti
- [x] BaseDevice - изменить логику 1 экшн = 1 топик. Яркий пример - Броадлинк
- [x] Вытяжка - додавить работу с выключателем
- [x] LG TV - доработать болванку
- [x] Доработать и проверить XMC-2
- [x] Сделать AppleTV
- [x] Разобраться с warnings по вытяжке
- [x] Для катушечника - проверить, нужна ли своя handle_message, сделать mqtt_client глобально доступным?
- [x] Проверить execute_action, если передаются параметры (см. [optional_params.md](optional_params.md))
- [x] Придумать как пускать вытяжку через FastAPI
- [ ] Запуск приложений на AppleTV
- [x] MQTT через FastAPI с payload
- [ ] Проверить катушечник после рефакторинга Варенборда
- [x] LgTv - запуск приложений и переключение входов. Не работает range по mqtt. MQTT через FastAPI не работает вообще
- [x] Сделать remote logging перед установкой контейнера docker на контроллер
- [x] Проверить необходимость WOL для eMotiva XMC-2 + set_volume и set_mute для zone2

## PHASE 2
- [x] Сделать сценарии управления AV-системой в стиле [Logitech Harmony](scenario_system_spec.md)
- [x] Продумать и сделать управление сценариями по MQTT
- [ ] Сделать/подобрать шаблоны SprutHub для новых девайсов и всех сценариев
- [ ] Восстановить работу SprutHub, соединить с Алисой
- [x] Сгенерить простую Веб-морду для управления AV-системой по FastAPI (?Vue.js?)
- [x] Инсталляция на контроллере через Docker
- [x] Инсталляция правил и виртуальных устройств в wb-rules с помощью скрипта
- [ ] Сделать пылесос [Roborock S8](https://github.com/Python-roborock/python-roborock?tab=readme-ov-file)
- [x] Сделать progress reporting на веб интерфейсе
- [x] Миграция на SVG Icons на веб интерфейсе
- [ ] Сделать страничку для обучения IR кодам с пультов
- [x] Продумать, как изолировать конфигурацию интерфейса от конфигурации устройств
- [x] Сделать интеграцию с [Auralic Altair G1](auralic_stragery.md)

