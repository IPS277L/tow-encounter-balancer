# Аудит массовой mixed-симуляции M7

Дата: 2026-09-29. Проверены [ADR-0029](../decisions/ADR-0029-independent-mixed-simulations.md), [ADR-0030](../decisions/ADR-0030-process-mixed-simulations.md), пять production simulation модулей, существующие тесты и сохранённые измерения. Рабочее дерево на старте чистое, HEAD `9be28b2`. В этом срезе меняется только документация.

**Независимые sequential/process mixed-прогоны и aggregate summary готовы в границе неподвижных numeric Minions ADR-0028. Можно готовить контракт оценки mixed-кандидатов.** Это дополнение к [аудиту одиночного сценария](m7-readiness.md) и [аудиту последовательного слоя](m7-simulation-readiness.md). Готовность не распространяется на произвольную тактику, полный каталог NPC или балансировщик mixed-составов.

## Матрица контракта

| Обязанность | Реализация | Проверка |
| --- | --- | --- |
| Immutable input и границы семейства | [Request/models](../../src/towr/simulation/npc_mixed_models.py): admitted NpcMixedScenario, exact int uint64 seed/trials, N > 0; исходный scenario повторяется без переноса continuation | [12 simulation unit tests](../../tests/unit/test_m7_npc_mixed_simulation.py): request/index guards до RNG, frozen/slotted, чужие ranged/Melee types и равные строки Enum отклоняются |
| Стабильный seed и отдельный RNG | `towr:npc-mixed-trial:v1`: SHA-256 от имени, NUL и двух uint64 big-endian. [Trial](../../src/towr/simulation/npc_mixed_simulation.py) создаёт RNG по абсолютному индексу | Golden vectors; [4 sequential integration tests](../../tests/integration/test_m7_npc_mixed_simulation.py): повтор, обратный порядок, расширение префикса, отдельные RNG, дополнительные броски одного trial не сдвигают остальные; input/global RNG неизменны |
| Source до компактной проекции | Trial проверяет typed NpcMixedScenarioResult и полное равенство source_scenario, затем оставляет index/seed/outcome/Attack/visited | Simulation unit: тот же ID с другими facts/policies отклоняется; ошибка второго trial не запускает третий и не возвращает partial result |
| Четыре исхода и terminal suffix | Outcome берётся после terminal acknowledgement/exclusion; Attack и distinct visited rounds — из runner_report. Resume и acknowledgement не добавляют Attack/раунд | Sequential integration: четыре реальных исхода одного 2×2 input, counts 1/1/1/1, 17 Attack/6 visited, 24/24/48/6 RNG calls. NO_CANDIDATE сохраняет неисполненный slot; raw pending в terminal trial корректно завершён |
| Полнота compact result | Frozen result копирует tuple, сортирует index, проверяет все N записей, seeds, typed outcomes и bounds по actor/round budget | Simulation unit: missing/duplicate/foreign index/seed, ранний ROUND_LIMIT, невозможные counters. Summary не заменяет эти проверки и не доказывает историю после удаления журнала |
| Aggregate-only summary | [Model](../../src/towr/simulation/npc_mixed_summary_models.py) и [projection](../../src/towr/simulation/npc_mixed_summary.py): исходный request, четыре counts, две суммы; N/means производные | [9 summary tests](../../tests/unit/test_m7_npc_mixed_summary.py): sum=N, bounds Attack/rounds, source/type/replace guards, frozen; нет RNG/runner/pool и рекурсивного удержания result/records/journals |
| Preflight process | [Backend](../../src/towr/simulation/npc_mixed_parallel.py): typed request, positive exact int workers/batch_size, callable и pickle до pool; factory не вызывается в parent | [11 process unit tests](../../tests/unit/test_m7_npc_mixed_parallel.py): invalid options/families/serialization без создания pool. Успешный pickle не гарантирует импорт callable в child |
| Bounded spawn и порядок | Fresh ProcessPoolExecutor(spawn), ленивые абсолютные ranges, не более 2×workers futures; все returned done читаются до refill | Process unit: reverse completion, uneven tail, разные partitions; uint64-max request планирует только четыре диапазона перед injected failure. Parent result сохраняет исходный request, existing constructor сортирует и проверяет records |
| Ошибки и cleanup | Batch добавляет index/seed note к Exception; нет retries/fallback/partial success. Pending отменяются, pool ждёт начатую работу; BaseException не превращается в outcome | Process unit: startup, initial/refill submission, wait, future, invalid records, final constructor, interrupts. [6 real-spawn tests](../../tests/integration/test_m7_npc_mixed_parallel.py): child failure сохраняет исходную note и index/seed, input/global RNG неизменны, дети завершены |
| Равенство backend | Worker вызывает existing trial; parent возвращает тот же result contract, summary использует тот же source | Real spawn: 2×1/3×2/2×2, workers 1/2, partitions, repeat/prefix, workers > batches; workers=1 действительно работает в child. Четыре scripted исхода, dynamic outnumbering и GM withholding дают те же полные results/summaries |
| Проверяемые измерения | [Profiling](../../tools/profile_m7.py) и [comparison](../../tools/benchmark_m7_parallel.py) используют public APIs и сверяют полные records/summary, а не только числа исходов | [7 profiling tests](../../tests/unit/test_m7_profiling.py) и [6 comparison tests](../../tests/unit/test_m7_parallel_benchmark.py): равные агрегаты при разных records не проходят, tracing очищается, source hash включает untracked; смена sources не перезаписывает отчёт |

Итого **56 tests** массового слоя: 12 simulation unit + 9 summary + 4 sequential integration + [1 subprocess example](../../tests/integration/test_m7_simulation_example.py) + 11 process unit + 6 process integration + 7 profiling + 6 comparison. Вместе с 60 tests одиночного сценария — **116 M7 tests**, без повторного счёта одноимённых unit/integration файлов. Новых tests не добавлено: исправления production не потребовались.

AST-проверка подтверждает направление импортов: simulation не зависит от application/adapters/CLI/balance/tools/tests; domain/engine/rules не зависят от simulation/balance. Process orchestration не переносится в domain/engine/rules/balance. Типы Melee/ranged не объединяются с mixed.

## Непосредственная книжная сверка

Локальный извлечённый текст перечитан; прототип не служит основанием правил:

| Источник | Проверенное основание |
| --- | --- |
| BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112 | Раунд, ход, действие и порядок сторон. Каждый trial начинает исходный сценарий заново |
| Та же книга, Rules / Attack Tests / Attack Modifiers, стр. 118–119; Failed Attacks / Successful Attacks, стр. 119 | Opposed Attack, текущий Zone outnumbering и право GM удержать бонус; Close miss, Damage/Resilience. Их исполняет existing K1/M2, а не статистический слой |
| BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91 | Wound побеждает Minion; disposition остаётся решением attacker/GM, acknowledgement не новая Attack |
| Та же книга, Allies and Antagonists / Brigands & Footpads, стр. 97 | Numeric Dagger/Warbow и Athletics Protection в fixtures; Brigand не делает Melee, поэтому его Craven Opportunist здесь не применяется |

RULE-COMBAT-001/005/006/007/008/009 и RULE-NPC-002 сохраняются. Seed encoding, ограничение очереди и агрегирование — технические решения. Неподвижность, роли и Attack-only policy — граница ADR-0028, не запрет иных действий в книге. Новых Rule IDs, противоречий или house rules нет.

## Сохранённые измерения и их пределы

[Методика](../benchmarks/README.md#mixed-sequential-и-spawn), отчёты [100](../benchmarks/m7-parallel-100-2026-09-29.md) и [1000](../benchmarks/m7-parallel-1000-2026-09-29.md) trials: seed=20260929, budget=5, workers=1/2, batch_size=32, три чередующихся повтора. End-to-end время включает fresh spawn startup, serialization, исполнение, сбор/валидацию, summary и shutdown. Все 54 timed batches равны внутри соответствующего входа. Повторный benchmark в этом аудите не выполнялся.

Текущий SHA-256 sources/harness **`a7598993f8153e00c0d5b25b230a86f11d33df559407ce9ca75944acbf34ce59` совпал с обоими отчётами**. Более новый HEAD не отменяет измерения неизменного содержимого: hash включает все src/**/*.py, tools/profile_m7.py и tools/benchmark_m7_parallel.py. Исторический baseline использует другую область hash; напрямую сравниваются только его trial digests/counts/Attack/visited, совпавшие для 100 trials.

На 100 trials spawn медленнее; на 1000 один worker также медленнее, два workers дали локальные 1,298× для 3×2 и 1,196× для 2×2. В 2×1 диапазоны времени перекрываются. Нагрузка ОС/частота CPU не контролировались; результаты Windows 11 / CPython 3.14.5 не задают универсальный порог, optimal batch size или auto backend. Измерения не устанавливают RSS/общую память процессов и не распространяются на другие Python/ОС или installed wheel. Отклонённый [cache continuation](../benchmarks/m7-round-continuation-review.md) остаётся историческим экспериментом.

В 1000-trial отчёте achieved/defeated/limit/unsupported: 875/0/0/125, 852/0/0/148, 32/136/1/831 соответственно 2×1/3×2/2×2. Это наблюдения, не оценка баланса: реальные unsupported есть во всех трёх составах. Их нельзя объявлять поражениями, исключать из знаменателя, заменять новым trial или автоматически продолжать иной тактикой.

Память исполнения — O(N) compact records плюс in-flight задачи/копии входа и текущие журналы workers. Bounded queue не является streaming или hard memory cap; uint64 admission не задаёт практическую квоту ресурсов. Cleanup ждёт running/уже отправленные задачи, не обещает мгновенное прекращение и не откатывает side effects custom factory. Независимость произвольной factory и истинность supplied GM facts остаются ответственностью вызывающего кода.

## Следующий законченный шаг

Подготовить отдельный контракт оценки mixed-кандидатов по принятой метрике M5/M6: `objective_achieved / все N trials`, точные Fraction, явное окно minimum/target/maximum и отдельные round_limit/unsupported. Любой наблюдавшийся unsupported делает кандидата непригодным; отсутствие unsupported в конечной выборке не доказывает полноту тактики.

Определить pure assessment одного кандидата и ограниченную оценку явного списка: exact input/summary source, общий preflight бюджета, stable ranking, полный aggregate-only report и явный sequential/process внутри одного кандидата. Проверить минимальное переиспользование ObjectiveRateWindow и execution options без смешения mixed/ranged/Melee requests/outcomes. Balance получает только вход и сводку, без journals/records; errors сохраняют контекст кандидата и не дают partial success. Контракт и конечный probe — следующий срез; реализация assessment/evaluator, staged/generation и JSON/CLI следуют отдельно.

Новых движений, смены оружия, неатакующих действий, магии, PC-сценариев, auto awareness/GM approvals, persistent pool, caches или общего battle aggregate этот аудит не добавляет. Повторное согласование уже принятой метрики не требуется; новая существенная неоднозначность книги по-прежнему требует вопроса пользователю.

## Проверки

Полная регрессия: **2414 tests OK (248,047 с)**, Windows / Python 3.14.5, включая реальные spawn процессы и прежние ranged/Melee/CLI. Compileall src/tests/tools/docs/examples/m7, 1794 локальных Markdown-пути, AST test counts/import boundaries, source/harness hash, git diff --check и whitespace нового аудита успешны. Команды — в [статусе проекта](../project-status.md#последняя-проверка). Production src/tests/tools не менялись; новых tests и benchmark запусков нет, commit/push не выполнялись. Python 3.12/другие ОС и installed wheel не проверялись.

## Следующий контракт подготовлен

[ADR-0031](../decisions/ADR-0031-mixed-candidate-assessment.md) фиксирует pure assessment и bounded list evaluation с прежней метрикой, Fraction window и unsupported guard. [Конечный probe](../examples/m7/assessment_contract_probe.py) и [вывод](../examples/m7/assessment_contract_probe.output.txt) проверены: синтетическая арифметика отдельно от реальных scripted mixed summaries, равных в sequential/spawn. Это не реализация assessment/list/service; следующий срез — pure assessment одного кандидата.
