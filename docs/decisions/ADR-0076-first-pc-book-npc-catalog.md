# ADR-0076: первые книжные NPC для PC balance

Дата: 2026-11-04. Статус: принято.

## Задача и конечная граница

PC-сценарии принимали авторские numeric Minion/Brute snapshots с Defence. M21 добавляет два точных книжных боевых подпрофиля: Footpad и Empire Townsfolk, явный NPC Protection Skill и полный путь factory → native бой → trials/process → count search → текущий JSON1/CLI.

Источники: BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists, Minions91, Understanding NPC Profiles93, Citizens & Subjects96, Brigands & Footpads97. [Нормализованные правила](../rules/npcs.md#исполняемый-каталог-pc-m21) хранят точные значения и условия неприменимости способностей. Это боевые подпрофили для указанной сцены, не полные NPC-карточки и не весь бестиарий.

## Выбор профилей

Footpad имеет Dagger Close3d/3, Damage2,1H и Athletics3d/3; Townsfolk — Dagger Close2d/2, Damage2,1H и напечатанную Athletics2d/2. Оба Minion с Toughness3/Resilience3 без брони. Protection не пересчитывается из Characteristics, даже если общий способ вывода дал бы другое значение. NPC не получает Traits одноимённого PC-оружия без прямого основания GM93.

Lurker Footpad делает Awareness для обнаружения скрывающегося NPC Grim **вне боя**. Streetwise Townsfolk даёт +1d Awareness против pickpocket. Нынешняя сцена начинается в бою с aware targets, без ambush и таких взаимодействий. Эти способности сохраняются в catalog metadata с условием/эффектом, но не активируются. `no_additional_abilities` означает отсутствие дополнительных **применимых** effects в заявленном encounter, а не отсутствие у NPC способностей вообще. Удалять реально применимые способности ради numeric допуска нельзя.

Brigand, Town Watch и другие просмотренные профили добавляют иные loadouts, дальности или применимые Abilities. Они не входят автоматически в M21.

## Источник и владение

Новый [pc_npc_catalog](../../src/towr/domain/pc_npc_catalog.py) содержит typed ID/metadata и свежие фабрики. `get_pc_book_npc_entry` возвращает книгу/версию/главу/страницу, боевое definition и неактивные способности. `create_pc_book_npc` создаёт независимого здорового вооружённого opposition Minion с0Wounds. Каталог не управляет RNG, боем, CLI или балансировщиком.

Вход native/JSON сохраняет полный `NpcDefinition` и snapshot. Зарезервированные `pc-book-npc:` identities и известные книжные root/attack/protection source IDs проверяются против точного независимого canonical definition. Нельзя изменить Damage/Skill/броню или переименовать лишь root IDs, сохранив ложное вложенное книжное происхождение. Авторские numeric profiles с собственными identifiers остаются допустимыми, включая явно заданные Athletics и Defence.

Фабрики не делят изменяемый посредством bypass граф с проверочным образцом: canonical definition создаётся независимо. Exact nested types не принимают равные bool/string-enum aliases. Для обычных authored источников проверка принадлежности каталогу завершается до построения canonical graphs, чтобы не добавлять ненужную работу в каждый replay.

## Protection и текущий JSON1

NPC Protection допускает Athletics либо Defence. Реальный выбранный Skill передаётся общему Protection preparation и сохраняется в source; числовой Test не переименовывается ради старого ограничения.

`enemy.definition.protection.skill` обязательно присутствует и равно `athletics` либо `defence`. Parser больше не подставляет Defence, serializer не теряет Skill. Пропуск/alias/другие Skills отклоняются. Все24прежние request/result pairs M9–M20 мигрируются с явным `defence` без изменения прежних игровых значений/counters. Нового wire version/compatibility слоя и новых метрик нет.

Full-source factory input проходит нынешний native owner и count search. Поиск меняет только числа/actor subsets, сохраняя exact book definitions, Protection Skill, party/Fate/policies. Подмена cached source/result не становится observation. CLI использует прежние команды и полные числовые requests; нового короткого формата, скрытого resolve по имени оружия или обязательного сервиса каталога нет.

## Альтернативы

- Подстановка Defence вместо Athletics и пересчёт напечатанных2d из Agility искажали бы источник.
- Определение Skill по source ID теряло бы его в authored numeric profiles и делало формат неоднозначным.
- Полные NPC-карточки, универсальный Ability language и весь каталог не нужны для двух замкнутых боевых профилей.
- Числовая копия с книжной подписью без защиты происхождения позволяла бы выдавать изменённые данные за canonical profile.

## Проверка

[Точность каталога/factories/provenance](../../tests/unit/test_m21_pc_npc_catalog.py), [literal native Protection/Attack/source admission](../../tests/unit/test_m21_pc_book_encounters.py), [wire](../../tests/unit/test_m21_pc_npc_protection_json.py), [actual process/search/cache](../../tests/integration/test_m21_pc_book_npcs.py).

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.unit.test_m21_pc_npc_catalog tests.unit.test_m21_pc_book_encounters tests.unit.test_m21_pc_npc_protection_json tests.integration.test_m21_pc_book_npcs tests.unit.test_m9_pc_melee_models tests.unit.test_m9_pc_melee_json tests.unit.test_m9_pc_melee_json_schemas -q
```

Ближайшая регрессия — PC source/execution/party/Minion-Brute trials/balance/CLI, representative weapon/backup interactions и K1 Protection/Attack execution. Успешные не затронутые M12–M20 подсистемы, M8 callers, full/wheel автоматически не повторяются. Actual CLI examples, offline schema refs и сохранение всех прежних JSON values проверяются отдельно. Фактические результаты — в [статусе](../project-status.md).
