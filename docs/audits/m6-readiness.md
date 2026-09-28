# Аудит первого Melee-сценария M6

Дата: 2026-09-28. Рабочее дерево на старте чистое. Проверены [ADR-0021](../decisions/ADR-0021-melee-minion-scenario.md), production admission/provider/runner/result, книжные фрагменты и тесты. Добавлены [полный typed пример](../examples/m6/README.md), сохранённый вывод и один subprocess integration test. Production src не менялся.

**Одиночный неподвижный Melee Minion-сценарий готов в границах ADR-0021.** Это допуск и исполнение заданной тактики до исхода/лимита, а не готовность Melee Monte Carlo, балансировщика или общего боя.

## Матрица контракта

| Обязанность | Public API и поведение | Проверка |
| --- | --- | --- |
| Допуск и неизменяемые источники | [NpcMeleeScenarioFacts/ActorPolicy/Scenario](../../src/towr/domain/npc_melee_scenario_models.py): fresh round 1, здоровые Minions, одна numeric Close Melee/Protection, полный roster/placements/policies, положительный общий budget, явный Close/awareness/LOS/отсутствие дополнительных правил | [17 admission unit tests](../../tests/unit/test_m6_npc_melee_scenario.py): Conditions/истории/equipment/типы/orders/цель/facts; [6 preflight integration tests](../../tests/integration/test_m6_npc_melee_scenario_preflight.py): handoff existing K1/M2, отказ до runner/RNG |
| Актуальные кандидаты и обычный бонус | [melee_scenario_candidates](../../src/towr/domain/npc_melee_scenario_result_models.py): surviving targets по policy; актуальный полный состав Zone, исключение defeated/Defenceless; completed/Staggered остаются; +1d только при большинстве и явном GM approval; stationary spatial guard | [6 candidate unit tests](../../tests/unit/test_m6_npc_melee_candidates.py): equality/majority/minority, withholding, cap/trace; [cycle integration](../../tests/integration/test_m6_npc_melee_scenario_cycle.py): 2:2→2:1 и 3→4 dice после defeat либо 3 при withholding |
| Close miss и повторный Staggered | [run_npc_melee_scenario](../../src/towr/engine/npc_melee_scenario_runner.py) вызывает existing K1 через one-round runner; Close miss впервые Staggered, повторный miss без эскалации; успешный слабый удар по Staggered → supplied SUFFER_WOUND | Preflight/cycle: промахи через несколько раундов, успешный слабый удар после собственного промаха, first/repeated Staggered, неизменность исходного input; [result unit](../../tests/unit/test_m6_npc_melee_scenario_runner.py): журнал с другим StaggerChoice отклоняется |
| Решения и однократные последствия | Полные MinionDefeatDecision для каждого attacker/target; existing acknowledgement/exclusion; terminal suffix до следующего actor/advance, уже походившая цель не исключается повторно | Cycle: все три disposition, оба perspective, смешанные решения и приоритеты, terminal на первой Attack; повтор apply Attack/acknowledgement отклоняется existing consumers |
| Общий бюджет и четыре исхода | Runner владеет advance, resume не сбрасывает budget; NpcMeleeScenarioResult отделяет objective_achieved/side_defeated/round_limit/unsupported_path | Cycle: budget 1/2/3 после defeat resume, все промахи до лимита, 20 повторяемых seeds; result unit: early limit, расширение/сокращение budget, post-terminal observation, unexpected exceptions |
| Цепочка источников и диагностика | [NpcMeleeScenarioResult](../../src/towr/domain/npc_melee_scenario_result_models.py) требует exact initial/steps/candidates/порядок/GM policy; current включает terminal suffix, исходный runner report сохраняется | [15 result unit tests](../../tests/unit/test_m6_npc_melee_scenario_runner.py): чужие/повторные переходы, отсутствие suffix, stale modifiers, changed facts/порядок, подмена даже пустых candidates; корректная имитация controller stop сохраняет диагностику без RNG |
| Внешний typed пример | [melee_scenario.py](../examples/m6/melee_scenario.py): public constructors → Random(42) → production runner → текстовый report источников/тактики/исхода/метрик/Attack IDs | [Subprocess test](../../tests/integration/test_m6_example.py): два одинаковых запуска вне repository cwd, абсолютный PYTHONPATH только к src; без imports tests/private API |

Всего M6 **54 теста: 38 unit и 16 integration**. Это 53 существующих теста сценария и один новый тест примера; прежние K1/M2 тесты повторно не посчитаны. Параметризованные subTests не считаются отдельными тестовыми методами. Defenceless в candidate test — синтетическая проверка формулы подсчёта, не допущенное начальное состояние. Аналогично synthetic Defence/2H/armour не меняет книжный Footpad.

## Непосредственная сверка источников

Перечитаны локальные extracted pages выбранных книг, не только changelog:

| Книга, глава, страница | Подтверждённое основание |
| --- | --- |
| BOOK-PLAYER-GUIDE 1.4, Rules / Rolling Dice / Dice Modifiers, 107 | Обычный cap — удвоенная Characteristic; outnumbering не обходит его |
| Та же книга, Rules / Combat и Ambush, 112 | Один ход/действие; обычный порядок сторон; surprise требует отдельной first-round модели |
| Та же книга, Rules / The Battlefield / Zones, Position, Range, 114 | Close отдельно от общей Zone, позицию утверждает GM |
| Та же книга, Rules / Attack Tests / Attack Modifiers, 118–119 | Melee/Protection, aware target, актуальный Zone count, обычный +1d и право GM удержать его; 7:6 не универсальный порог |
| Та же книга, Rules / Failed Attacks, Successful Attacks, Giving Ground, 119; Conditions / Staggered, Defenceless, Prone, 123 | Промах в Close, Damage/Resilience, repeated Staggered; возможность уйти и выбранная тактика независимы |
| BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, 91 | Одна Wound → defeat; disposition выбирает атакующий с одобрением GM |
| Та же книга, Allies and Antagonists / Understanding NPC Profiles, 93 | Numeric Attack/Protection, одна атака; автоматических PC weapon benefits нет |
| Та же книга, Allies and Antagonists / Brigands & Footpads, 97 | Footpad Dagger Close 3d/3 Dam2 1H, Athletics 3d/3, RES3; Lurker вне боя. Brigand Craven Opportunist требует отдельного +2d и не поддержан обычной проекцией |

Новых Rule IDs, противоречий или house rules не выявлено. Фиксированные Attack/SUFFER_WOUND и orders — выбранная легальная тактика, не отмена прочих вариантов книги. Числовой definition не доказывает истинность `no_additional_rules`.

## Наблюдение примера и границы результата

В [сохранённом запуске](../examples/m6/melee_scenario.output.txt) 2×2 Footpad, seed 42, budget 3: objective_achieved, 6 Attack, 3 посещённых и 2 завершённых runner раунда, 3 подтверждения defeat, включая terminal suffix. Итоговый current не имеет pending, хотя последняя настоящая runner observation остановилась на pending_follow_ups. Подмена её исходом сценария потеряла бы диагностический источник. Итог не исполняет автоматический Recover после боя: PG 1.4, Rules / Recover, стр. 118 требует возможности перевести дух.

В этом seed все исполненные Attack имеют 3 dice: временное преимущество не доживает до следующей атаки большинства. Реальный переход 3→4 отдельно воспроизводит сохранённый [contract_probe.py](../examples/m6/contract_probe.py), а production path покрыт cycle tests. Один пример не является оценкой вероятности победы или доказательством баланса сторон.

Immutable state и consumed histories защищают от повторного применения к возвращённому snapshot. Они не защищают от намеренного полного отката всех caller snapshots, не подтверждают внешние GM facts и не удостоверяют происхождение произвольного RNG. Повторный независимый запуск одного initial/seed допустим. Технический unsupported stop проверен с корректными sources через имитацию controller block; он не ожидается в обычном допущенном цикле и не выдаёт ошибку источника за игровой исход.

Не входят: PC/Brutes/Champions/Monstrosities, движение/Charge/Brawn/Recover, меняющиеся GM policies, shield/equipment changes, surprise/awareness inference, special NPC Abilities, смешанный ranged/Melee бой, полный каталог. Нет нового CLI/JSON, process runner, Monte Carlo, confidence policy, подбора Melee или общего battle aggregate. Python 3.12/другие ОС, установленный wheel и performance benchmark в этом аудите не проверялись; используется текущий src на Windows / CPython 3.14.5.

## Минимальное продолжение: независимые прогоны и summary

Следующий законченный срез — отдельный typed последовательный Melee simulation/summary по образцу [ADR-0014](../decisions/ADR-0014-independent-ranged-simulations.md), с новым ADR перед реализацией. Ниже требования к этому будущему контракту, **ещё не реализованный API**:

1. Frozen request содержит допущенный NpcMeleeScenario, explicit master_seed и trials. До RNG проверяются типы/положительный размер пакета, bool не допускается. Каждый trial начинает с того же immutable initial, не с continuation прошлого боя.
2. Отдельное версионированное имя seed scheme для Melee, фиксированное SHA-256 encoding master_seed/index и golden vectors; результат не зависит от размера пакета/порядка исполнения. Новый внедряемый RNG на каждый trial, по умолчанию Random. Scheme ranged v1 и её vectors сохраняются. Это воспроизводимые PRNG-потоки, не доказательство статистической независимости.
3. Исполнение вызывает только run_npc_melee_scenario и проверяет exact typed source результата. Compact trial содержит index/seed, **scenario outcome** (с учётом terminal suffix), executed_attack_count и visited_round_count. Нельзя брать raw runner stop за исход, суммировать resume calls как раунды или превращать visited в completed. Full battle journal освобождается после проекции.
4. Полный result требует все индексы ровно один раз, сортирует их по index, проверяет seeds и пределы counters по admitted составу/общему budget. Четыре outcome counts сохраняются отдельно; round_limit не ничья, unsupported не поражение. Exceptions RNG/executor/source пробрасываются, без retry, fallback или partial result под видом завершённого пакета.
5. Pure aggregate summary сохраняет source request, четыре counts и суммы Attack/visited rounds без trial records или battle journals. Balance в дальнейшем получает только этот input/aggregate. Подтверждённая метрика M5 сохраняется: denominator = все trials, round_limit отдельно, unsupported делает оценку непригодной для подбора. Реализация evaluator/generator/CLI Melee — отдельные последующие шаги.
6. Детерминированные проверки: distinct RNG, immutable initial, repeat/reverse/expanded batch, четыре outcomes и точные counters, terminal suffix, отсутствие утечки global random state, seed/source/index guards и ошибки без partial result. Статистический тест не требует конкретного процента побед. Сначала последовательный путь; профилирование и process backend отдельно при необходимости.

Проверки текущего аудита записаны в [project-status.md](../project-status.md#последняя-проверка). Правила/production APIs и ranged wire v1 не менялись.

Продолжение после этого аудита: [ADR-0022](../decisions/ADR-0022-independent-melee-simulations.md) реализует описанный последовательный simulation/summary. Добавлены 22 tests; игровой контракт и результаты исходного аудита одиночного сценария выше сохраняются. Профилирование, оптимизация continuation и process backend теперь закрыты [аудитом массовой Melee-симуляции](m6-simulation-readiness.md). Melee balance/CLI/JSON ещё отсутствуют; следующий шаг — контракт оценки кандидатов.
