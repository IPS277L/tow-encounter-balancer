# ADR-0029: независимые последовательные mixed-прогоны и summary

Статус: принято и реализовано, 2026-09-29, в последовательной typed границе ниже. [Аудит последовательной simulation](../audits/m7-simulation-readiness.md) завершён; самостоятельный пример готового API проверен. Профилирование и эксперимент с continuation завершены (кеширование отклонено); контракт опционального mixed process runner ADR-0030 реализован; сравнение sequential/process — следующий шаг.

## Основание и граница

[Одиночный mixed-сценарий ADR-0028](ADR-0028-mixed-minion-scenario.md) закрыт [аудитом](../audits/m7-readiness.md). Повторять его независимо и проецировать результат в компактные записи и сводку можно поверх существующего run_npc_mixed_scenario. Допуск, выбранная тактика и игровые правила не меняются.

Напрямую перепроверены BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112 (round/turn/action), Attack Tests / Attack Modifiers, стр. 118–119, Failed Attacks / Successful Attacks, стр. 119; BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91 (Wound побеждает Minion, disposition отдельно). Seed, размер пакета и агрегирование — технические решения. Остальная книжная область и numeric profiles остаются в ADR-0028; новых Rule IDs/house rules нет.

Принципиальная граница mixed: NO_CANDIDATE возникает на реальном пути, когда очередной Melee actor потерял последнюю Close-цель, но удалённый враг жив. Пакет учитывает этот исход как unsupported_path. Он не меняет очередь, не пропускает ход, не выбирает Wait/Recover/движение/другое оружие и не продолжает бой за другого actor.

## Направление зависимостей и API

`towr.simulation` зависит от engine/domain и rules.RandomSource. Обратной зависимости нет. Узкие отдельные типы следуют структуре [ADR-0014](ADR-0014-independent-ranged-simulations.md) и [ADR-0022](ADR-0022-independent-melee-simulations.md), не наследуются от ranged/Melee и не принимают их Enum по равенству строк. Универсальный simulator/battle aggregate или общий параметризованный язык не создаётся.

Реализованные файлы и публичные имена:

| Модуль в src/towr/simulation | Содержимое |
| --- | --- |
| npc_mixed_models.py | SEED_SCHEME, npc_mixed_trial_seed, NpcMixedSimulationRequest, NpcMixedTrialSummary, NpcMixedOutcomeCounts, NpcMixedSimulationResult |
| npc_mixed_simulation.py | run_npc_mixed_trial, run_npc_mixed_simulation |
| npc_mixed_summary_models.py | NpcMixedSimulationSummary |
| npc_mixed_summary.py | summarize_npc_mixed_simulation |

## Вход и воспроизводимость

Frozen/slotted `NpcMixedSimulationRequest(scenario, master_seed, trials)` требует допущенный NpcMixedScenario, `master_seed` в `[0, 2**64)`, `trials` в `[1, 2**64)`. Только настоящий int, без bool, строк, float или преобразования значений. `request.seed_for(trial_index)` требует int `0 <= trial_index < trials`. Проверка request/index происходит до RNG factory и runner. Wrong request/scenario family или тип seed/index → TypeError, выход за диапазон → ValueError. Нулевой пакет отклоняется.

`npc_mixed_trial_seed(master_seed, trial_index)` принимает оба числа в `[0, 2**64)` и применяет схему **towr:npc-mixed-trial:v1**:

```text
SHA-256(ASCII("towr:npc-mixed-trial:v1") || 00 || uint64be(master_seed) || uint64be(trial_index))
```

Digest читается как unsigned big-endian integer. Нулевой байт — один byte 0, не текст `\\0`; оба числа кодируются ровно восемью байтами. Scheme не включает scenario ID, размер пакета, порядок выполнения или previous RNG state. Изменение encoding требует новой версии; старые ranged/Melee схемы и vectors сохраняются.

Golden vectors закреплены unit tests; probe сверил to_bytes и независимую упаковку struct `>QQ`:

| master_seed | trial_index | digest hex |
| --- | --- | --- |
| 0 | 0 | `31b5bc60517dc8c6ec3ebca91c0319881480062cc5353cee054661e8b5acae5c` |
| 42 | 7 | `ecbb86faf8c674f5ecc8b5aea0a13fe836004fecafbbd4ec7cf59e50a9165ed7` |
| 2**64-1 | 2**64-1 | `b55deeeb08ed8633fb362bb47dc3deff6d27b5fafc3e08d538c1c99486637f89` |

Каждый trial получает новый Random(seed) по умолчанию либо отдельный RandomSource из внедрённой `rng_factory(seed)`. Произвольная фабрика отвечает за отдельные потоки; автоматического доказательства её независимости нет. Это воспроизводимые PRNG-потоки, не математическое доказательство независимости. Повторяемость предполагает одинаковые scenario/правила и совместимый RNG/runtime; глобальный random не используется.

## Исполнение и компактные записи

`run_npc_mixed_trial(request, trial_index, *, rng_factory=Random)` вызывает existing run_npc_mixed_scenario с неизменным `request.scenario`. Результат обязан быть NpcMixedScenarioResult с равным полным source_scenario, не просто совпадающим ID. Затем вернуть frozen/slotted `NpcMixedTrialSummary(trial_index, seed, outcome, executed_attack_count, visited_round_count)`.

Outcome берётся из **scenario result после terminal acknowledgement/exclusion**, не из raw runner stop. Счётчики — из runner_report: distinct visited rounds, не число resume calls и не completed rounds. Suffix не даёт дополнительную Attack, receipt или раунд. Full journal после проекции не удерживается записью. TrialSummary содержит только mixed outcome, uint64 index, seed `[0, 2**256)`, неотрицательные int counters без bool; visited > 0, terminal outcome требует хотя бы одну Attack.

`run_npc_mixed_simulation(request, *, rng_factory=Random)` последовательно исполняет `0..trials-1`, каждый раз с тем же initial; continuation/Conditions/defeats/used IDs между trials не переносятся. Ошибки RNG/factory/runner/type/source прерывают пакет и распространяются наружу; без retry, fallback или partial success. Ошибка после нескольких выполненных trials не даёт завершённый result. Реальный UNSUPPORTED_PATH от runner является записью, не исключением. Для диагностики отдельного индекса caller может повторить одиночный runner с его seed.

Frozen/slotted `NpcMixedSimulationResult(source_request, trials)` копирует records в tuple и сортирует по index. Требуются все индексы `0..N-1` ровно один раз, правильный derived seed, typed mixed records/outcomes. Для каждого record, при A начальных actors и B round budget: `1 <= visited <= B`, `attacks <= A*visited`; ROUND_LIMIT требует `visited == B`. Counter/seed значения без bool, неотрицательные, неправильные numeric значения отклоняются ValueError; чужие request/record/outcome типы — TypeError.

Result вычисляет `outcome_counts`, `total_attack_count`, `total_visited_round_count`, `mean_attack_count`, `mean_visited_round_count`. Frozen/slotted `NpcMixedOutcomeCounts(objective_achieved, side_defeated, round_limit, unsupported_path)` требует неотрицательные int без bool. Средние — float от integer totals/N, не новые метрики сложности. O(N) компактных записей заменяют удержание N журналов; во время каждого trial живёт его полный журнал.

Общий вычислительный предел пакета — не более `N*B` посещённых раундов и `N*A*B` Attack. Это производные верхние границы, не новый таймер или общий боевой round limit: каждый trial получает B раундов заново. uint64 — граница encoding, не практическая квота памяти/времени. В этом контракте нет дополнительного поля max_total_trials или произвольного скрытого cap; бюджеты будущего поиска будут отдельным контрактом.

## Сводка без records

`summarize_npc_mixed_simulation(result)` — чистая проекция полного typed result в frozen/slotted `NpcMixedSimulationSummary(source_request, outcome_counts, total_attack_count, total_visited_round_count)`. Она не вызывает runner/RNG и не сохраняет simulation result, trial records или battle journals. Точный source_request остаётся входом; `trials` и два mean свойства вычисляются.

Проверить типы и неотрицательные int totals без bool, сумму всех outcome counts = N. При L исходах ROUND_LIMIT и T terminal outcomes:

```text
L*B + (N-L) <= total_visited_round_count <= N*B
T <= total_attack_count <= A*total_visited_round_count
```

Нулевые Attack допустимы у технической остановки; не вводить более сильную гарантию по текущему fixture. Эти структурные границы не доказывают боевую историю, истинность GM facts или происхождение RNG после удаления журнала. Summary допускает ненулевой unsupported: она описывает наблюдения; пригодность для будущего подбора — отдельный assessment.

Подтверждённая метрика M5 сохраняется: objective_achieved / **все N trials**. Round_limit не ничья, unsupported не поражение и не исключается из знаменателя. Для будущей оценки любой unsupported делает кандидата непригодным. Отсутствие unsupported в конечной выборке не доказывает, что этот путь невозможен. Evaluator/window/presets, доверительные интервалы и conditional win rate этим ADR не реализуются.

## Конечный probe и матрица следующей реализации

[simulation_contract_probe.py](../examples/m7/simulation_contract_probe.py) использует публичный builder [одиночного примера](../examples/m7/mixed_scenario.py), existing runner и локальные иллюстративные records. Он не импортирует tests/private builders и не создаёт production simulation models. [Сохранённый вывод](../examples/m7/simulation_contract_probe.output.txt): на одном immutable 2×2 input с B=2 четыре scripted trial дают по одному каждому исходу, 17 Attack и 6 visited rounds суммарно, 24/24/48/6 RNG calls. Это заданные броски, не Monte Carlo-оценка.

Ещё 22 вызова с отдельными seeded RNG проверяют повтор, обратный порядок индексов, расширение 4→6 и отсутствие влияния дополнительных бросков trial 0 на records 1..3. Seed vectors отличаются от ranged/Melee, initial/global RNG неизменны; terminal suffix и реальная потеря Close-цели проецируются правильно. Probe не проверяет production constructors/error guards/summary API; их tests указаны в разделе реализации ниже.

| Граница | Обязательные deterministic tests следующего среза |
| --- | --- |
| Seed/request/index | Все golden vectors, family separation, uint64 границы, bool/float/string/negative/zero trials, индекс вне пакета до RNG/runner |
| Immutable result | Frozen/slotted, копия ordered input в tuple, sorting, missing/duplicate/foreign index/seed, чужие ranged/Melee типы и равные строки Enum, zero visited/terminal attacks, превышение бюджета, premature ROUND_LIMIT |
| Исполнение | Те же immutable sources, новая RNG на trial, exact result type/source; четыре реальных исхода на одном fixture, включая NO_CANDIDATE; error второго trial без запуска третьего/partial/retry, interrupts не поглощаются |
| Счётчики | Сuffix не Attack/раунд; resume не новый раунд; visited не completed; dynamic outnumbering через defeat, сохранение GM policies/pair ranges |
| Повторяемость | Repeat/reverse/expanded prefix, extra draws только в своём trial, неизменный global RNG; никаких ожидаемых Monte Carlo-процентов |
| Summary | Pure projection без runner/RNG и без records/result/journals, точный source, четыре counts и обе суммы/means; invalid types/count sum/total bounds и ошибочные cross-family inputs |

Четыре production модуля и unit/integration tests реализованы. Аудит simulation и самостоятельный пример готового API завершены. Следующий законченный шаг — воспроизводимое профилирование перед решением об оптимизации/process. Balance/generation, JSON/CLI, новые роли/действия, движение, магия и общий battle aggregate остаются вне этого контракта.

Проверка контрактного среза: probe из корня и временного каталога успешен; **103 existing tests OK (2,751 с)** на Windows/Python 3.14.5. Compileall, 1594 локальных Markdown-пути, diff --check и whitespace новых файлов успешны. Src/tests/tools не менялись, полный набор повторно не запускался (последняя полная проверка 2358 OK). Все 16 исходных dirty/untracked файлов сохранены; добавлены ADR/probe/output и обновления документации. Commit/push не выполнялись.

## Реализация последовательного слоя

[Модели](../../src/towr/simulation/npc_mixed_models.py), [исполнитель](../../src/towr/simulation/npc_mixed_simulation.py), [summary models](../../src/towr/simulation/npc_mixed_summary_models.py) и [чистая проекция](../../src/towr/simulation/npc_mixed_summary.py) реализованы. Existing mixed admission/engine/K1 и ranged/Melee simulation/seed schemes не менялись. Проверки не пытаются восстановить боевую историю после компактной проекции.

[12 unit simulation tests](../../tests/unit/test_m7_npc_mixed_simulation.py), [9 summary tests](../../tests/unit/test_m7_npc_mixed_summary.py) и [4 integration tests](../../tests/integration/test_m7_npc_mixed_simulation.py) прошли. Unit проверяют три golden vectors, uint64/index guards до RNG, frozen/slotted state, полноту/сортировку, seed/counter/outcome/source и cross-family отказы. После первого успешного trial ошибка фабрики, executor, чужой source, неверный тип или interrupt останавливают пакет без третьего trial/partial result. Summary не исполняет RNG/runner/pool и не удерживает trial/result/боевые журналы.

Реальные scripted 2×2 trials одного input дали четыре разных исхода, counts 1/1/1/1, 17 Attack/6 distinct visited rounds и RNG calls 24/24/48/6. NO_CANDIDATE сохраняет неисполненный slot; terminal suffix снимает pending без новых Attack/раундов. Другой 3×2 input проверяет +1d после defeat и GM withholding (13/12 RNG calls). Repeat/reverse/expanded prefix и отдельные RNG подтверждены без фиксированного Monte Carlo-процента.

[Краткий Python API](../examples/m7/README.md#python-api-независимых-прогонов) использует готовые модули; исторический contract probe продолжает проверять собственную конечную проекцию и не заменяет production tests. Аудит simulation и отдельный исполняемый production-пример завершены (см. ниже); performance/process/balance/CLI в этот шаг не добавлены.

Проверка implementation-среза: **25 новых tests OK (0,182 с)**; полный набор **2383 tests OK (231,801 с)**, Windows/Python 3.14.5. Compileall, 1611 локальных Markdown-путей, AST import boundaries, diff --check и whitespace новых файлов успешны. Все 19 исходных dirty/untracked файлов сохранены; новые четыре production-модуля, три test-файла и документация не закоммичены. Commit/push не выполнялись.

## Аудит последовательной реализации

[Матрица](../audits/m7-simulation-readiness.md) закрывает контракт последовательных прогонов/summary; исправлений production src не потребовалось. Добавлены [mixed_simulation.py](../examples/m7/mixed_simulation.py), [вывод](../examples/m7/mixed_simulation.output.txt) и [subprocess test](../../tests/integration/test_m7_simulation_example.py). Всего 26 tests слоя simulation. Два состава с 8 trials каждый повторяют полные result/summary, сохраняют input/global RNG; unsupported входит в знаменатель и остаётся отдельным исходом. В сохранённом 2×2 наблюдении 7/8 trials остановились технически; это не метрика семи поражений и не допустимый результат будущего подбора. Статистический процент не используется как test oracle. Следующий шаг — воспроизводимое профилирование fixed mixed-пакетов; process/balance/CLI ещё отсутствуют.

## Исходное профилирование

[Отчёт и методика](../benchmarks/README.md#m7-исходное-профилирование-mixed-simulation) фиксируют неизменённый sequential на трёх составах, 100 trials, seed=20260929, budget=5. Полные results/summaries совпадают во всех измерительных режимах; source hash сохранён. Unsupported counts 16/14/89 не фильтруются. По повторным чтениям NpcRoundResult.continuation выбран следующий эксперимент: однократное построение validated immutable continuation с прежними source/replay guards и проверкой пользы по тем же пакетам. Это ещё не оптимизация и не решение о process backend; новые игровые правила не вводятся.

## Итог эксперимента continuation

[Проверка кандидата](../benchmarks/m7-round-continuation-review.md) сохранила records/summary/source/seed semantics, но не дала убедительного общего ускорения. Кеширование NpcRoundResult.continuation отклонено, исходный production восстановлен. Новой архитектурной гарантии identity getter или сериализации cache нет. Следующий ADR должен определить отдельный опциональный mixed process runner; ADR-0029 по-прежнему закрывает последовательные trials/summary, auto backend не вводится.

## Контракт опционального process backend

[ADR-0030](ADR-0030-process-mixed-simulations.md) и [transport probe](../examples/m7/process_contract_probe.py) готовы. Existing sequential request/trial/result/summary сохраняются; probe проверяет полное равенство результатов и четыре реальные mixed outcomes в дочерних процессах. Production process orchestration и её tests — следующий срез, не часть реализованного ADR-0029.

[Production mixed process API](../../src/towr/simulation/npc_mixed_parallel.py) по ADR-0030 реализован с 17 новыми tests. Existing request/result/summary и seed scheme ADR-0029 сохранены; последующий performance-срез не меняет правила агрегации.
