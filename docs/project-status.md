# Текущий статус проекта

Дата обновления: 2026-11-05.

## Текущий этап

**M25 завершена: Empire State Trooper с Halberd и фиксированной Defence.** Пятый книжный combat loadout PC family: Minion1, Toughness3/Resilience4 armoured, Close3d/3 Damage5,2H и Defence3d/4. [Правило и контракт loadout](rules/npc-profile-catalog.md#state-trooper-m25), [factory/JSON/CLI-примеры](examples/m25/README.md).

Напечатанная Athletics3d/3 сохранена числовым unselected Protection; Spear/Crossbow/Handgun явно не выбраны. Полный Supporting Action trigger сохранён в inactive metadata: нынешние PC уже находятся в Close и не перемещаются, внешних участников нет. Будущая движущаяся сцена потребует исполнения способности. NPC не получает PC Halberd armour bonus автоматически; обычный PC Axe bonus против его брони сохраняется.

Использованы существующие catalog/factory, armed2H Defence, native/trials/count search и current JSON1. Engine/clock/схемы/CLI/метрики не менялись; отдельный ADR для добавления по принятому образцу не нужен. У Python catalog entry добавлен descriptive unselected_protection tuple, у прежних четырёх записей пустой. Прежние definitions/snapshots и все32request/result pairs M9–M24 неизменны.

## Последняя проверка

После независимой адресной сверки GM1.1 pp93/100 и PG1.4 pp68/118 source review не оставило замечаний; production заморожен. При PYTHONPATH=src **72tests OK/3.818s**, единый адресный unittest-прогон10модулей: новые unit/integration M25; M21 npc_catalog/npc_protection_json/book_encounters; M22 brigand_catalog/craven_opportunist; M23 official_catalog/official_wounds; M24 npc_exit. Проверены literal Protection3d/4, Damage5 без PC trait, PC Axe armour bonus, exact source/alias/replay admission, свежие независимые factory graphs, прежние Craven и Broken/exit paths, JSON/trials/aggregate-only search. Новых12tests.

Адресная команда новой функции:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.unit.test_m25_pc_state_trooper tests.integration.test_m25_pc_state_trooper -v
```

Оба M25 requests исполнены настоящим CLI: simulation6objective/0other outcomes, без PC deaths;24actions,11started/5completed rounds. Balance проверил4состава по3trials: все observed objective,actions7/12/16/26; top_k2 выбрал1Trooper/0Footpad и1Trooper/1Footpad. Optional/support/exit costs нулевые. Это малая воспроизводимая выборка, не истинная вероятность или оптимум.

Проверка документов/schema/source echo охватывает34current request/result pairs M9–M25;64старыхJSON documents M9–M24 byte-unchanged against HEAD. Сравнение со старой фабрикой подтверждает неизменность всех четырёх definitions/snapshots и прежних metadata fields. Markdown/local links/UTF-8/whitespace и git diff --check проверены.

Это адресная проверка новой функции, не full regression проекта. Full/wheel и повторная module/console×sequential/process матрица не запускались: механизм исполнения/сборки/ресурсов/dependencies/entry points не менялся. M24 уже проверила process передачу актуальных source/summary fields; M25 добавляет данные по существующему формату. .cache helpers локальны и не входят в репозиторий.

## Ограничения

Пять registered combat loadouts: State Trooper Halberd/Defence, Footpad, Townsfolk, Brigand Axe, Official Dagger. Нет переключения Trooper на Athletics или другие weapons, Supporting Action/Charge/ranged reactions не исполняются вне выбранной сцены. Armor и Protection не пересчитываются из generic PC weapon Traits.

Сохраняется M24: Broken Official с явной policy выполняет один clear/fastest adjacent safe exit, сохраняя W1/Broken/not defeated; objective — все NPC побеждены или ушли, уход считается отдельно. При null policy — stop перед Broken turn. Нет преследования, возврата, общего pathfinding или Recover после выхода; снятие Broken при сохраняющейся profile Wound остаётся открытым.

Aware Close arena/fixed orders/priorities, здоровая initial party,13Close primary weapons/optional1H backup, Wounds1–23/lethal24+, source-aware Conditions и mandatory Critical/Defenceless end phases сохраняются. Невозможная повторная анатомия/недоступный хват сохраняют точные stops. Общие inventory/Brawn/лечение/campaign/optimal AI отсутствуют; Greatsword требует уточнения бонуса. Costs/losses при stop/limit относятся к исполненному prefix.

## Следующий шаг

Рекомендация — ещё один книжный противник, можно из раздела существ/монстров: адресно сверить полную карточку и все применимые Abilities, затем выбрать конечный loadout/continuation. M26 не выбрана; не расширять автоматически spatial/AI/весь бестиарий. Для продолжения Broken/Recover сначала разрешить отдельный ongoing-cause вопрос. [Очередь](roadmap.md), [индекс вопросов](open-questions.md).

Перед M25 рабочее дерево было чистым: пользователь сохранил M24. Изменения M25 незакоммичены; commit/push выполняет пользователь.
