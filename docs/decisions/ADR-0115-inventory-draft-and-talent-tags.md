# ADR-0115: списки инвентаря и теги талантов

Дата: 2026-11-15. Статус: реализовано по запросу пользователя. Уточняет вход из [ADR-0114](ADR-0114-character-facts-and-automatic-generator-input.md).

## Решение

В dynamic JSON1 `equipment` содержит массивы `weapons` и `armour`. Каждый предмет имеет уникальный внутри персонажа instance `id`, тип и начальное `location`. Два одинаковых меча — два предмета. Оружие может быть `left_hand`, `right_hand`, `both_hands` или `carried`; положение определяет начальную активность. Броня/обычный шлем — `worn` либо `carried`, щит — рука либо `carried`. Старые scalar weapon/armour/shield fields удалены без compatibility-ветки.

Отдельный массив `consumables` хранит id/kind/quantity/characteristic. В редакторе доступны Healing Potion и Enhancement Potion; для второго обязательна одна из восьми Characteristics. Таланты остаются массивом строк, редактируются тегами с добавлением/удалением, без checkbox на каждый талант. Lucky имеет подсказку; неизвестный симуляции талант остаётся видимым тегом. Дубликаты тегов не добавляются UI, duplicate IDs/некорректные potion parameters отвергаются на входе расчёта.

Это описание инвентаря, а не исполняемый язык правил. `application.encounter_inventory` хранит typed facts и явно компилирует поддержанный loadout в существующий `EncounterCharacter`/participant. Не выбирает произвольно один меч из двух активных и не теряет содержимое инвентаря. Полный введённый инвентарь сохраняется в source_request; исполняемый replay хранит разрешённый loadout/backup policy.

## Сохранение и расчёт

Редактор/JSON/schema могут представлять более полный инвентарь, чем текущий исполнитель: например два меча в руках, глефу за спиной и зелья. В UI видны ограничения. Сохранение или переключение вида не запускает бой. `parse_dynamic_encounter_request` дополнительно проверяет исполнимость перед любыми trials и возвращает structured input error с путём к предметам/талантам. Расходники, неизвестные таланты, dual wield, общая смена оружия/брони, перегруз и Heavy Armour не игнорируются.

Рабочий путь: одно активное melee-оружие, none/light body armour, отдельно обычный шлем, optional щит в другой руке. Также разрешены прежний2H primary и один carried1H backup, без shield, с уже реализованным односторонним переходом при недоступном хвате. Новая общая тактика смены оружия этим изменением не вводится.

Источники: PG1.4 IV Equipment92–93 — carry/dual wield;97–98 — armour/shield/helmet. Количество weapons>Strength либо больше одного2H вызывает Burdened, поэтому текущая compilation останавливается, а не объявляет такой инвентарь запрещённым книгой. Для обычного шлема не придуман отдельный+1 поверх Light Armour; он описан как часть комплекта. Магические шлемы не маскируются этим kind. GM1.1, Magic Items89–90, RULE-MAGIC-ITEM-007 — Healing/Enhancement Potions; их consumers пока не подключены. Таланты кроме Lucky требуют собственных effect consumers. Прежние Damage/Resilience/hand/drop/Fate owners не переписаны.

## Проверка

Typed inventory tests: instance IDs, положение/руки,1H/2H, carry admission, body+helmet+shield без лишнего бонуса, existing backup, potion fields. JSON tests: полный source/replay, draft schema и explicit preflight отказ до MC. Browser: добавление двух мечей/глефы, отдельные body/helmet/shield, quantity/Characteristic potion, add/remove/duplicate talent tags, lossless JSON switch, прежние Run/Cancel/seed. Адресно также existing backup и shield core; full regression/wheel не нужны. Фактические команды и результаты — в статусе.
