# Текущий статус проекта

Дата обновления: 2026-11-05.

## Текущий этап

**M30 завершена: Empire Knight/Lance, Knight of the White Wolf/Wolf Hammer и Big ’Un/Choppas.** Это три совместимых пеших Brute2 loadouts с W1Drained/W2defeat; всего в PC каталоге19записей. [Правило и книжные источники](rules/npc-profile-catalog.md#brute-chunk-m30), [factory/JSON/CLI-примеры и фактические результаты](examples/m30/README.md).

Все используют printed Defence, Normal Speed, armoured Resilience5. Щиты Empire Knight/Big ’Un не выбраны, их +1 вычтен; mounted бонусов нет. Big ’Un сохраняет WS3/Melee4 и получает только Strength-derived Damage4→5. Lance допускает обычную пешую Close-атаку. Полные mounted/Charge/Help triggers сохранены вне условий текущей сцены.

W1Drained применяется на existing actual Profile Wound ACK, включая первую рану от repeated-Staggered. Отдельный конечный helper охватывает три новых профиля и прежний White Wolf; обычный собственный ход продолжается, положительные bonus dice подавляются только у фактически Drained NPC. W2 defeat/GM disposition и full replay сохранены. Нового owner/ADR/wire поля/version/метрик нет. Все84прежних JSON documents и16старых catalog entries/definitions/snapshots/metadata сохранены.

M29 source-aware on-hit Drained Giant Spider сохраняется независимо от раны/Near Miss/W6expiry. Пользователь выбрал Attack/standard Recover; альтернативный Endurance Recover не добавлен. Current PC JSON1 требует secondary_effects[] либо единственный unclassified on-hit Drained descriptor; остальные families прежние. Стратегии Fate/Help/Recover/запасного оружия не менялись.

## Последняя проверка

Составная адресная приёмка M30: **18 новых tests и122 ближайших зависимых tests**,140уникальных проверок. Это не единый full regression. Production после независимого source/code review заморожен.

При PYTHONPATH=src выполнены:

```powershell
.venv/Scripts/python.exe -m unittest tests.unit.test_m30_pc_brute_catalog -v
.venv/Scripts/python.exe -m unittest tests.unit.test_m30_pc_brute_wounds tests.integration.test_m30_pc_brute_chunk -v
.venv/Scripts/python.exe -m unittest tests.unit.test_m9_pc_melee_execution tests.unit.test_m11_pc_melee_brutes tests.unit.test_m23_pc_official_wounds tests.unit.test_m26_pc_merchant_wounds tests.unit.test_m29_pc_hit_conditions tests.unit.test_m29_pc_drained_catalog tests.unit.test_m28_pc_beast_orc_catalog tests.unit.test_m28_pc_beast_orc_modifiers tests.unit.test_m27_pc_creatures tests.unit.test_m25_pc_state_trooper -q
.venv/Scripts/python.exe -m unittest tests.unit.test_m27_pc_creatures -q
.venv/Scripts/python.exe -m unittest tests.unit.test_m21_pc_npc_catalog tests.unit.test_m22_pc_brigand_catalog tests.unit.test_m23_pc_official_catalog tests.unit.test_m26_pc_catalog_chunk tests.unit.test_m27_natural_attack_models -q
```

Новые8catalog OK/0.006s и10runtime+integration OK/7.600s. Первый зависимый прогон86tests/1.942s:85OK, один M27 test требовал отсутствия variants у всех будущих каталоговых записей. Проверка ограничена собственными Wolf/Boar; весь модуль8tests OK/0.164s. Дополнительные36catalog/admission tests OK/0.066s. Успешные дорогие проверки не повторялись.

Проверены direct/repeated-Staggered W1, exact ACK/once-only/replay, ordinary NPC turns с wounded/unwounded outnumbering comparison, W2 defeat, canonical source/type/cache guards, старые Official/Merchant/White Wolf/Spider и generation8составов. Старый M29 контрольный прогон604tests относился к завершённой M29; он не выдаётся за новый результат M30.

Оба M30 requests исполнены настоящим CLI. Simulation seed42/6trials/budget5rounds:0objective/4party defeated/2limit/0unsupported,109actions; balance8составов по2trials —16наблюдений. Таблица результатов и параметры стратегии находятся в примере. Проверены44current PC request/result pairs M9–M30, полные source echo, локальные ссылки/UTF-8/whitespace; git diff --check чистый.84старых JSON побайтово совпадают с pre-M30 snapshot,16старых каталоговых записей — с прежней factory. Старые Monte Carlo не пересчитывались.

Full проекта/wheel/новая process-матрица не запускались: механизм исполнения/поставки/контракт не менялись. Историческая M29 process-проверка сохраняет прежнее основание; она не считается вновь выполненной. Локальные .cache helpers/logs не входят в репозиторий.

## Ограничения

Aware fixed Close arena, healthy initial party, fixed activation/target priorities,13Close primary weapons/optional1H backup, Wounds1–23/lethal24+, PC Critical/Defenceless end phases сохраняются. Natural бойцы самостоятельные unmounted; Charge/terrain/riders не исполняются. Невозможная повторная анатомия/недоступный хват имеют прежние точные stops. Costs/losses при stop/limit относятся к исполненному combat prefix.

On-hit поддержан только unclassified Drained без общей системы иммунитетов/DSL; hit sources не снимаются выбранной стандартной Recover стратегией. Будущая альтернативная recovery требует собственного удаления причин. То же открыто для NPC Recover при сохраняющейся profile Wound: Official Broken, Merchant Staggered, White Wolf и три Brutes M30 Drained. Текущие NPC Recover не делают. Погоня/возврат/spatial/общий AI/inventory/лечение/campaign/save-resume не добавлены; Greatsword требует уточнения бонуса.

## Следующий шаг

Адресная сверка Goblin Warrior/Nasty Skulker/Night Goblin как возможного следующего чанка: repeated-Staggered defeat, unopposed Damage, Weighted Net/Burdened. До реализации установить timing/removal и согласовать расширение supported descriptors, если оно понадобится. M31 пока не выбрана; альтернативный Endurance Recover без нового решения пользователя не включать. [Очередь](roadmap.md), [индекс вопросов](open-questions.md).

До текущего шага оставались незакоммичены M26–M29 и политика чанков; они сохранены. Сейчас изменения включают завершённые M26–M30. Commit/push выполняет пользователь.
