# ADR-0077: Brigand Axe и Craven Opportunist

Дата: 2026-11-04. Статус: принято.

## Задача и граница

M21 допустила два книжных NPC с неактивными в сцене способностями. M22 добавляет первый профиль с применимым боевым эффектом: Brigand с явно выбранным Axe-only loadout и Craven Opportunist через тот же PC owner, trials/process, подбор и текущий JSON1.

Источники: BOOK-GM-GUIDE1.1, гл.VII Understanding NPC Profiles93 / Brigands & Footpads97; BOOK-PLAYER-GUIDE1.4, Rules / Attack Modifiers118–119. Нормализованный ID — [RULE-PROFILE-TALABEC-004](../rules/npc-profile-catalog.md#brigand-craven-m22), четвёртая запись Talabec, Footpad остаётся005.

## Выбор снаряжения и источник

`PcBookNpcProfile.BRIGAND_AXE` явно выбирает до боя Axe из карточки, содержащей Axe и Warbow. GM93 разрешает заранее определить carried weapons. Warbow сохранён в `unselected_attack_names`; battle definition и snapshot содержат только Axe. Это выбранный боевой подпрофиль, не полная карточка Brigand и не ranged-сценарий.

Точные printed значения: Axe Close3d/3 Damage3,1H; Athletics3d/2; Toughness3/Resilience4 armoured, Minion1Wound. ResilienceProfile(3,1) отражает броню, но NPC Axe не получает неуказанный PC armour-Damage Trait. Зарезервированные root/nested book identities проходят ту же exact/fresh canonical проверку M21.

Metadata использует общий `PcBookNpcAbility(name,scope,effect)` в раздельных active/inactive tuples. Это описание и источник, не исполняемый язык правил. У старых двух профилей active/unselected пусты; их combat definitions и поведение сохраняются.

## Исполнение способности

Явный pure helper [pc_npc_outnumbering_modifier](../../src/towr/domain/pc_npc_ability_models.py) возвращает `RULE-PROFILE-TALABEC-004:craven-opportunist` +2d только для canonical Brigand Axe; остальные допустимые NPC получают прежние +1d. Known source IDs участвуют в выборе книжной механики, поэтому нельзя сохранить их и подменить numeric definition. Полностью authored numeric copy остаётся обычным профилем, без неявного Craven.

Caller вычисляет актуальное превосходство перед каждой Attack по всем живым пригодным бойцам обеих сторон в Zone, а не только по числу Brigands. Defeated/Defenceless/noncombatants исключаются; завершивший ход или Staggered боец продолжает считаться. Если superiority отсутствует, helper не вызывается и бонуса нет. Если GM withheld outnumbering через явный fact, не применяется и замена Craven.

Способность **заменяет** +1d на +2d: обычный modifier не сохраняется вторым слагаемым. PC-side остаётся на обычном +1d; Footpad/Townsfolk и authored NPC не приобретают способность от союзника Brigand. Отдельный higher-ground modifier сохраняется. Последующий существующий Drained filter удаляет положительные bonuses, включая Craven. В нынешнем fresh physical Minion path canonical Brigand не получает Drained до defeat; этот случай проверяется как pure preparation boundary, не как нативно достигнутый prefix.

`no_additional_abilities` означает отсутствие неподдержанных применимых effects сверх заявленного среза. Реализованный Craven разрешён; остальные способности нельзя молча игнорировать. Active modifier хранится в actual TestRequest и полном journal proof; canonical replay проверяет условие, источник и однократную величину без повторного RNG.

## Публичная граница

Полные definition/source IDs, gear и числовые profiles уже выражаются текущим PC JSON1. Новых wire fields/version/метрик нет, старые request/result pairs не мигрируются. Book metadata расширена только в Python API; compatibility alias прежнего metadata class не поддерживается во время разработки. CLI-команды и schema shape прежние.

Count search фиксирует party/Fate/policies и exact book definitions, меняя только actor subsets/counts. Ability пересчитывается из фактического текущего состава при исполнении каждого кандидата. Статистика показывает actual observed outcomes/costs, не гарантированную трудность или оптимальную тактику.

## Альтернативы

- Добавление +2d поверх +1d нарушает буквальное «вместо» GM97.
- Постоянные5d в NPC definition теряют условие превосходства, GM approval и динамику потерь.
- Общие произвольные Ability поля/DSL не нужны для одного замкнутого книжного эффекта; metadata не интерпретируется как код.
- Полная карточка с неисполняемым Warbow скрывала бы выбор доступного оружия и неподдержанный ranged path.

## Проверка

[Printed catalog/loadout](../../tests/unit/test_m22_pc_brigand_catalog.py), [literal native/pure/forgery cases](../../tests/unit/test_m22_pc_craven_opportunist.py), [actual process/source JSON/search](../../tests/integration/test_m22_pc_brigand.py). Ближайшая регрессия — M21 source/provenance, PC source/Attack/Protection/party/trials/balance и K1 Protection/Attack execution. CLI mechanism/matrix, тяжёлые PC подсистемы и другие families не повторяются без влияющего изменения.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.unit.test_m22_pc_brigand_catalog tests.unit.test_m22_pc_craven_opportunist tests.integration.test_m22_pc_brigand tests.unit.test_m21_pc_npc_catalog tests.unit.test_m21_pc_book_encounters tests.unit.test_m21_pc_npc_protection_json tests.integration.test_m21_pc_book_npcs -q
```

Actual CLI примеры, full source echoes, прежние неизменённые JSON-пары и ссылки проверить адресно. Full/wheel — по контрольным точкам AGENTS, не автоматически для ADR. Фактические результаты — в [статусе](../project-status.md).
