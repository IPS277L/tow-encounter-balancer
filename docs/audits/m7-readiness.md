# Аудит одиночного смешанного боя M7

Дата: 2026-09-29. Рабочее дерево на старте чистое. Проверены [ADR-0028](../decisions/ADR-0028-mixed-minion-scenario.md), production admission/provider/runner/result, их K1/M2 зависимости и 59 существующих tests M7. Добавлены [самостоятельный пример](../examples/m7/mixed_scenario.py), [сохранённый вывод](../examples/m7/mixed_scenario.output.txt) и [subprocess integration test](../../tests/integration/test_m7_example.py). Production src не менялся.

**Одиночный неподвижный mixed Minion-сценарий готов в границах ADR-0028.** Наличие доступных целей на старте не гарантирует, что заданная тактика сможет закончить бой: потеря последней Close-цели может остановить Melee actor при живом удалённом враге. Это технический `unsupported_path`, не ничья, поражение или пропуск хода.

## Матрица контракта

| Обязанность | Реализация и проверенная граница | Свидетельства |
| --- | --- | --- |
| Неизменяемый вход и полный допуск | [Четыре модели](../../src/towr/domain/npc_mixed_scenario_models.py): fresh round 1, обычный порядок сторон, здоровые Minions, одна Attack, Athletics Protection, все enemy pairs/policies/решения, цель и бюджет. Nested NpcDefinition требует wound_limit=1; NpcRoundsRequest сверяет roster/round/spatial | [25 admission tests](../../tests/unit/test_m7_npc_mixed_scenario.py): типы, frozen/slots/копирование tuple, profiles/facts/equipment, Conditions/history/pending, orders/objective, zero RNG/execution |
| Дальности и роли | Полные supplied пары Close/Medium; Close в общей Zone, Medium в соседних. Любой Close-враг запрещает допущенный bow; у каждого actor есть начальная цель. Ни Zone, ни имя профиля не доказывают внешние факты | Admission: self/friendly/unknown/missing/reversed duplicates, несовместимость геометрии, обе роли и доступность; [candidate tests](../../tests/unit/test_m7_npc_mixed_candidates.py): lookup в обе стороны и actual range |
| Актуальные кандидаты | [mixed_scenario_candidates](../../src/towr/domain/npc_mixed_scenario_result_models.py) сохраняет полный приоритет, но пропускает defeated и недоступные по дальности цели. Подставляет Athletics options и can_leave_zone именно цели | 8 candidate tests; [cycle](../../tests/integration/test_m7_npc_mixed_scenario_cycle.py) и public пример: первая недоступная цель не блокирует следующую доступную |
| Численное преимущество | Подсчёт текущего roster в Zone атакующего: completed/Staggered считаются, defeated/Defenceless нет. +1d только Melee при большинстве и явном GM approval; удалённый союзник не помогает | Candidate tests: потеря бойца с обеих сторон, Defenceless, withholding; cycle: Shooting defeat меняет 2:2 на 2:1, следующая Melee Attack получает 4 вместо 3 dice, Shooting остаётся без бонуса |
| Attack/Protection и Conditions | [Runner](../../src/towr/engine/npc_mixed_scenario_runner.py) вызывает existing K1/M2. Close miss впервые даёт Staggered, повторный miss не эскалирует; Medium miss не даёт penalty. Успешный слабый удар по Staggered использует supplied SUFFER_WOUND | 9 cycle tests: обе ветви miss, repeated Staggered между раундами, точные traces/расход RNG; result tests отвергают другую легальную low-level StaggerChoice |
| Последствия и завершение | После Wound полное supplied GM decision, однократные acknowledgement/exclusion. Походившая цель не исключается. Terminal suffix завершает сценарий до следующего actor/advance; raw runner stop сохраняется | Cycle: все dispositions, обе perspective, реальная победа обеих сторон; kernel/ack/exclusion counts, повторное применение к current отвергается; public пример terminal pending 1 → 0 |
| Общий бюджет и продолжение | Каждый вызов runner посещает остаток одного раунда; resume после defeat не сбрасывает общий лимит. Advance сохраняет порядок выживших; выполненные раунды отличаются от посещённых | Cycle: бюджеты 1/2/3 после defeat/resume, точное число advance/calls/Attacks/RNG; public пример 2 посещённых/2 завершённых при лимите, 1/0 при terminal |
| Отчёт и источники | NpcMixedScenarioResult проверяет исходный сценарий, полные actual candidates/приоритет, decisions, StaggerChoice, порядок advance, бюджет и отсутствие runner после terminal. NpcRoundsChainSummary и NpcRoundResult проверяют непрерывность snapshots и выбранную execution_request | [17 result/runner tests](../../tests/unit/test_m7_npc_mixed_scenario_runner.py): изменённые range/escape/bonus/target/GM decision, недостающий suffix, duplicate transitions, ложный early limit и post-terminal observation отвергаются без повторного RNG |
| Технические остановки и ошибки | Реальный NO_CANDIDATE сохраняет диагностику и неисполненный slot; без Wait/движения/смены оружия. Неожиданные ошибки RNG/executor проходят наружу | Cycle/public пример: после единственной Close-цели остаётся enemy bow, 1 Attack/6 RNG; result tests: ложный пустой candidate list отвергается, source-consistent controller stop сохраняется, RuntimeError RNG не превращается в outcome |
| Публичное использование | Пример строит все модели через public APIs; не импортирует tests, private builders или probe provider. Domain импортирует только domain; engine — domain/rules/existing engine | Subprocess test запускает абсолютный script из временного каталога с одним src в PYTHONPATH и сравнивает сохранённые scripted наблюдения. Внутри примера проверены immutable inputs, глобальный RNG и повтор полного результата с отдельными Random(42) |

Исправлений production-кода аудит не потребовал. Новый test защищает самостоятельный пример и его запуск вне корня репозитория. Exact counts относятся к заданным броскам; seeded проверка не требует конкретного победителя или Monte Carlo-процента.

## Непосредственная сверка книг

Прочитаны локальные извлечённые страницы, не только нормализованные правила или changelog:

| Книга, глава и страницы | Проверено |
| --- | --- |
| BOOK-PLAYER-GUIDE 1.4, Equipment / Ranged Weapons, стр. 94 | Запрет bow при любом Close-враге, Optimum и заряжание без отдельного Test при отсутствии Reload |
| Та же книга, Rules / Combat и Ambush, стр. 112; The Battlefield / Range, стр. 114; Battlefield Features / Cover and Concealment, стр. 115; Combat Actions, стр. 116 | Обычный side order, явный Close и соседняя Zone для Medium, видимость/модификаторы и легальные варианты действий вне текущей тактики |
| Та же книга, Rules / Attack Tests / Attack Modifiers, стр. 118–119; Failed Attacks / Successful Attacks / Giving Ground, стр. 119; Conditions / Staggered, стр. 123 | Athletics opposition, актуальный zone-local +1d только Melee/Brawn, право GM удержать бонус, Close miss, Damage/Resilience и повторный Staggered |
| BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91; Understanding NPC Profiles, стр. 93; Brigands & Footpads, стр. 97 | Wound/defeat/GM disposition, numeric Attack/Protection и оружие; Footpad Dagger и Brigand Warbow в примере |

Полный Brigand Melee с Craven Opportunist сюда не входит: пример выбирает только Warbow, поэтому специальный +2d к Melee не применяется. Lurker Footpad действует вне боя. Athletics-only, неподвижность, SUFFER_WOUND и фиксированный порядок — ограничения выбранной тактики, не отмена других книжных действий. Новых Rule IDs, противоречий или house rules нет. Старый прототип не использован как приоритетный источник.

## Наблюдения и ограничения

Пять scripted запусков [примера](../examples/m7/README.md):

| Случай | Исход | Attack | Посещено/завершено раундов | RNG calls |
| --- | --- | --- | --- | --- |
| Выстрел → Melee с новым большинством | objective_achieved | 2 | 1/0 | 13 |
| Все промахи, бюджет 2 | round_limit | 10 | 2/2 | 60 |
| Побеждает opposition | side_defeated | 4 | 1/0 | 24 |
| Последняя Close-цель побеждена, удалённый враг жив | unsupported_path | 1 | 1/0 | 6 |
| Melee пропускает первую удалённую цель, bow завершает бой | objective_achieved | 2 | 1/0 | 12 |

Terminal acknowledgement/exclusion входят в итоговый current, но не добавляют фиктивный runner call или receipt. Последняя настоящая observation может иметь pending_follow_ups, когда итог сценария уже без pending. Automatic Recover после боя не исполняется: PG1.4, Rules / Recover, стр. 118 требует возможности перевести дух; результат фиксирует момент остановки.

Source guards защищают от несовместимых snapshots и повторного применения к возвращённому состоянию. Они не доказывают истинность внешних GM facts, происхождение RNG или отсутствие полного внешнего отката snapshots. Независимый повтор одного initial допустим.

Не входят: PC/Brutes/Champions/Monstrosities, движение, смена оружия, неатакующая тактика, Long/Extreme/Shooting Close, Defence/shields, special NPC Abilities, магия, auto awareness/approval, общий battle aggregate. Mixed Monte Carlo/process, подбор и JSON/CLI ещё не реализованы. Python 3.12/другие ОС, installed wheel и performance в этом аудите не проверялись.

## Следующий законченный шаг

Подготовить отдельный ADR независимых последовательных mixed-прогонов и aggregate summary по образцу ADR-0014/0022, до реализации нового simulation API. Зафиксировать typed request, отдельную версионированную seed scheme с vectors, новый RNG и исходный immutable сценарий на trial, exact source результата, compact records и полный пакет без partial success. Отдельно сохранить четыре исхода, Attack counts и distinct visited rounds, включая resume и terminal suffix.

Для будущего подбора оставить подтверждённую метрику: доля objective_achieved от всех trials; round_limit отдельно, наличие unsupported делает оценку непригодной. Реальная потеря целей в mixed требует явного учёта этого ограничения. Process, профилирование, balance/generation и JSON/CLI определять последующими срезами; ни seed scheme, ни ranged/Melee wire автоматически не переиспользуются как mixed.

Команды и окончательные результаты проверок — в [статусе](../project-status.md#последняя-проверка).

Проверка аудита: **60 tests M7 OK (1,220 с)**; полный набор **2358 tests OK (229,941 с)** на Windows / Python 3.14.5. Compileall, 1564 локальных Markdown-пути, границы импортов, diff --check и whitespace новых файлов успешны. Новые audit/example/output/test и изменения документации остаются незакоммиченными; commit/push не выполнялись.

Продолжение: [ADR-0029](../decisions/ADR-0029-independent-mixed-simulations.md) и [конечный simulation probe](../examples/m7/simulation_contract_probe.py) подготовлены. Production mixed simulation/summary реализованы с 25 новыми tests; [отдельный аудит этого слоя](m7-simulation-readiness.md) и самостоятельный пример готового API завершены. Вывод об одиночном сценарии выше сохраняется.
