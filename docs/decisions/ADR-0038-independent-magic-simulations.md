# ADR-0038: независимые последовательные magic-прогоны и summary

Статус: реализован и проверен в ограниченной последовательной границе, 2026-10-26; [аудит](../audits/m8-simulation-readiness.md). Models/seed/trial/batch/summary и public production-пример готовы. Первоначальный [конечный probe](../examples/m8/simulation_contract_probe.py) сохранён как историческая проверка контракта; constructors/error guards проверены отдельными production tests.

## Основание и граница

[Single-run ADR-0037](ADR-0037-magic-scenario-runner.md) закрыт [аудитом](../audits/m8-encounter-readiness.md). Независимые повторения получают тот же immutable NpcMagicScenario и вызывают existing run_npc_magic_scenario. Состав, диапазон допустимых фактов/Conditions, тактика, pending priorities и общий max_rounds одного боя сохраняются.

Книги определяют игровые переходы, а не seeds или пакет trials. Прямо проверены BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112; Conditions / Broken, стр. 122; Magic in the Old World / Miscasts, стр. 157; Battle Magic / Curse of Cowardly Flight, стр. 162; Wounds Table, стр. 190–191; BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions и Champions, стр. 91–92. Broken/другая Zone не становятся defeat; обязательный pending и end-turn не исчезают при агрегации. Новых Rule IDs/house rules нет.

Заимствуется направление зависимостей [ADR-0029](ADR-0029-independent-mixed-simulations.md), без reuse Minion-only record/result/summary types. Magic result имеет собственный enum, считает все executed actions и различает started/completed rounds. NpcMixedOutcomeCounts и равные строки старых Enum не заменяют magic types.

## API и зависимости

Только towr.simulation зависит от engine/domain и rules.RandomSource. Обратных зависимостей нет; application/balance/CLI не входят в этот контракт. Общий simulator abstraction/event bus/язык правил не вводится.

| Модуль в src/towr/simulation | Public имена |
| --- | --- |
| npc_magic_models.py | SEED_SCHEME, npc_magic_trial_seed, NpcMagicSimulationRequest, NpcMagicTrialRecord, NpcMagicOutcomeCounts, NpcMagicSimulationResult |
| npc_magic_simulation.py | run_npc_magic_trial, run_npc_magic_simulation |
| npc_magic_summary_models.py | NpcMagicSimulationSummary |
| npc_magic_summary.py | summarize_npc_magic_simulation |

Все records/request/result/counts/summary — frozen/slotted. Ordered inputs принимаются только как tuple/list и копируются в tuple. Wrong type/family/Enum или bool вместо int → TypeError; неверный диапазон/полнота/согласованность → ValueError. Преобразования строк/float/int-like объектов, исправление counters или молчаливый выбор другой семьи не допускаются.

## Request, seed и независимость

`NpcMagicSimulationRequest(scenario, master_seed, trials)` хранит полный допущенный NpcMagicScenario, uint64 master_seed `[0, 2**64)` и положительный uint64 trials `[1, 2**64)`. N=0 отклоняется. Scenario не заменяется live/final owner и не переписывается с новым round limit на каждом trial. До любого вызова фабрики RNG/runner проверяются request и index.

`request.seed_for(trial_index)` требует настоящий int `0 <= trial_index < request.trials`. Отдельный `npc_magic_trial_seed(master_seed, trial_index)` допускает оба uint64 и использует scheme **towr:npc-magic-trial:v1**:

```text
SHA-256(ASCII("towr:npc-magic-trial:v1") || 00 || uint64be(master_seed) || uint64be(trial_index))
```

00 — один нулевой byte, не текстовая escape-последовательность. Оба числа кодируются ровно восемью byte big-endian. Digest интерпретируется как unsigned big-endian integer `[0, 2**256)`. Изменение encoding потребует новой версии; ranged/Melee/mixed schemes не меняются.

| master_seed | trial_index | digest hex |
| --- | --- | --- |
| 0 | 0 | `fd32be1af91a33565dc651e426c0293ce371728db87f9147b0ea927de35fa60e` |
| 42 | 7 | `0b95a33629128179ab8ff2862038f7c1331078d98dcb552fce2037bf90581dac` |
| 2**64-1 | 2**64-1 | `ce26ddf15185ed7cbff2fb2e86929fe80c7eb0f531eacc02a59430860ceebb34` |

Scheme не включает scenario ID, размер пакета, порядок исполнения или состояние предыдущего RNG. Поэтому repeat/reverse/расширение prefix сохраняют соответствующие seeds. Смена ID меняет trace IDs и source, но не физические counters/outcome при остальных равных входах и RNG.

Default factory — `Random(seed)`; injectable `rng_factory(seed)` обязана возвращать новый отдельный RandomSource при каждом вызове. Проверяется последовательность вызовов/сохранение global RNG; математическая независимость PRNG или произвольной фабрики не доказывается. Повторяемость предполагает те же scenario/правила и совместимый RNG/runtime, не межверсионную гарантию Python Random.

## Compact record с полным source

`NpcMagicTrialRecord(source_scenario, trial_index, seed, outcome, executed_action_count, started_round_count, completed_round_count)` содержит одну ссылку на полный immutable **input** и scalar observation. Record не удерживает NpcMagicScenarioResult, final current owner, journal/steps, pending result, RNG или factory.

Полный source нужен в самом record: одинаковые scenario.id/master_seed/index не доказывают равенство профилей, facts, policies/frames или max_rounds. Parent result сверяет `record.source_scenario == request.scenario`, не только ID. Sequential executor передаёт один и тот же исходный объект во все records, без deepcopy на trial: память input разделяется ссылками. Допустимы равные immutable copies при ручном построении. Request целиком в record не хранится — N не должен нарушать equality prefix при расширении пакета.

Индекс — uint64, seed — int `[0, 2**256)`, outcome — только NpcMagicScenarioOutcome. Три counters — неотрицательные int без bool. При A исходных actors и B=scenario.max_rounds:

```text
1 <= started_round_count <= B
0 <= completed_round_count <= started_round_count
started_round_count - completed_round_count <= 1
completed_round_count <= executed_action_count <= A * started_round_count
```

OBJECTIVE_ACHIEVED/PERSPECTIVE_DEFEATED требуют хотя бы одного executed action; оба исхода выводятся из full single-run result после закрытия обязательных последствий/end-turn. ROUND_LIMIT_REACHED требует `started == completed == B`. Для UNSUPPORTED_PATH допустимы ноль actions и `started=1, completed=0`: slot уже зарезервирован, но отсутствует departure fact до Attack Test. Не требовать положительный action count у любой технической остановки.

Fresh admission всегда позволяет первый scheduler start; начатый раунд означает настоящий turn start, а не только номер round state или advance. Completed round появляется после полного bound end-turn. Между trials нельзя переносить magic pool, Conditions, defeats, IDs, daily/expiry histories или текущие позиции. Будущая поддержка иной initial/resume boundary потребует пересмотра этих bounds.

## Исполнение одного trial и пакета

`run_npc_magic_trial(request, trial_index, *, rng_factory=Random)`:

1. Проверить typed request/index и вывести seed до factory/runner.
2. Получить отдельный RNG и один раз вызвать existing run_npc_magic_scenario с **request.scenario**.
3. До любой scalar projection проверить typed NpcMagicScenarioResult и равенство полного result.source исходному scenario. Foreign result с тем же ID отклоняется.
4. Скопировать outcome/executed_actions/started_rounds/completed_rounds из публичных properties; source_scenario record — исходный input. Полный result не сохраняется после projection.

Не пересчитывать counters из длины steps: Casting completion, defeat acknowledgement, end-turn и advance не новые actions. Miscast/Wound pending не заменяются пустым результатом. Полные diagnostics/required scene/staged prefix можно получить повтором single-run по source/indexed seed с той же RNG factory и совместимым runtime; одного seed недостаточно для произвольной иной фабрики. Compact record сохраняет отдельный UNSUPPORTED_PATH, а не весь pending graph.

`run_npc_magic_simulation(request, *, rng_factory=Random)` последовательно исполняет `0..N-1` с тем же fresh input, возвращая NpcMagicSimulationResult. Каждый trial получает собственный B; предел пакета — не более N*B начатых раундов и N*A*B actions. uint64 — encoding bound, а не практическая квота. В первом API нет скрытого cap, нового таймера или max_total_trials; будущий bounded search будет отдельным контрактом.

Factory/RNG/runner/constructor/type/source errors прерывают пакет; тот же exception и BaseException проходят наружу, без retry, fallback, третьего trial после ошибки второго или выдачи partial batch как полного result. Настоящий UNSUPPORTED_PATH от single-run — нормальный record, а не exception. Массовый слой не выбирает новые GM facts, routes, targets или Miscast effects ради завершения.

## Result и aggregate-only summary

`NpcMagicSimulationResult(source_request, trials)` требует typed request и все N typed records; копирует ordered input в tuple и сортирует по trial_index. Ровно индексы `0..N-1`, exact derived seed и полный source каждого record обязательны. Missing/duplicate/foreign index/seed/source, чужие семьи и premature ROUND_LIMIT отклоняются. Result вычисляет `outcome_counts`, `total_action_count`, `total_started_round_count`, `total_completed_round_count`.

`NpcMagicOutcomeCounts(objective_achieved, perspective_defeated, round_limit_reached, unsupported_path)` хранит четыре неотрицательных int без bool. Ни один outcome не отфильтровывается и не переименовывается в соседний.

`summarize_npc_magic_simulation(result)` — чистая проекция полного typed result в `NpcMagicSimulationSummary(source_request, outcome_counts, total_action_count, total_started_round_count, total_completed_round_count)`. Summary не вызывает runner/RNG, не хранит result/records/journals/diagnostics, но сохраняет полный request. `summary.trials` выводится из request. Эти input+агрегаты будут доступны следующему balance-слою; он не получает records или боевые журналы.

Сумма counts равна N. При L=round_limit_reached, T=objective_achieved+perspective_defeated и totals S/C/E для started/completed/actions:

```text
L*B + (N-L) <= S <= N*B
L*B <= C <= S
0 <= S-C <= N-L
max(C, T + L*B) <= E <= A*S
```

Это необходимые арифметические bounds проекции, не восстановление боевой истории и не доказательство происхождения dice. Без journals невозможно удостоверить каждую underlying причину; source/seed/count guards не являются подписью observations.

Public rates/means/window/evaluator и новая метрика сложности в этот срез не входят. Counts описывают все N trials; если caller показывает долю исхода, denominator — N, включая unsupported. Unsupported не поражение/ничья/успех и не удаляется как неудобный trial. Подбор, доверительные интервалы и правила пригодности кандидата требуют отдельного решения после simulation boundary.

## Конечный probe и evidence

[simulation_contract_probe.py](../examples/m8/simulation_contract_probe.py) использует public builder standalone [magic_scenario.py](../examples/m8/magic_scenario.py) и existing single-run API. Только локальные illustrative Observation/seed/aggregation; production API выше не эмулируется в src и его constructors не объявляются проверенными.

На **одном immutable input** с B=4 четыре scripted calls дают:

| Outcome | Actions | Started/completed | d10 |
| --- | --- | --- | --- |
| OBJECTIVE_ACHIEVED | 2 | 1/1 | 9 |
| PERSPECTIVE_DEFEATED | 9 | 4/4 | 48 |
| ROUND_LIMIT_REACHED | 12 | 4/4 | 60 |
| UNSUPPORTED_PATH / Miscast | 1 | 1/0 | 3 |

Итого 120 заданных d10, counts=1/1/1/1, actions=24, started=10, completed=9. Enemy priority сначала ally, затем Wizard; supplied archive frame сохраняет defeated ally, два Superficial Wounds и следующий lethal Wounds Table roll обрабатывает существующий runner. Это не новая death/chronology реализация. Отдельный zero-action missing-departure call имеет прежний ID/seed, но иной полный source; смешивать его record с первым input нельзя.

Ещё 26 seeded calls проверяют repeat/reverse/expanded prefix, extra draws только в своём trial и rename-ID counters. Три golden vectors сопоставлены с независимым struct >QQ encoding и существующими ranged/Melee/mixed schemes. [Вывод](../examples/m8/simulation_contract_probe.output.txt) сохраняет observations, а не Monte Carlo-проценты. Вход/global RNG неизменны. Всего probe вызывает существующий runner 31 раз; будущие simulation models/summary/error guards пока не исполняются.

## Реализованные срезы и обязательные tests

| Срез | Что сделать и проверить |
| --- | --- |
| **Seed/request/record/counts/result models — готово** | Frozen request/record/counts/result, golden vectors/uint64/uint256 guards, strict bool/type/family/Enum отказ, full source и parent seed/index binding, сортировка/полнота, нулевой action unsupported, разные started/completed, premature limit и bounds. Без RNG factory/engine calls |
| Trial/sequential + summary — готово | Один RNG и existing run на trial, source check до projection, полный batch либо тот же exception, без новых вызовов после ошибки; pure aggregate projection/count sum/bounds, отсутствие records/result/journals в summary |
| Integration и воспроизводимость — готово | Четыре real outcomes одного input, реальная Wound/death/defeat chain и archive, Miscast pending/zero-action stop, repeat/reverse/prefix/rename/extra-draw isolation, input/global RNG unchanged; никакого фиксированного Monte Carlo-процента |
| Аудит слоя и standalone production example — готово | После реализации сопоставить публичные модели/runner/summary и tests, проверить пакет из внешнего cwd/installed wheel. Только затем отдельные profiling/process/assessment contracts |

Новый generic framework, процессы, изменение gameplay admission/consumers, балансировщик, generation, JSON/CLI и performance в этот контракт не включены. Эти ограничения не обходятся прямой передачей нового initial snapshot или отбрасыванием unsupported.


## Проверенная реализация

Четыре отдельных simulation-модуля реализуют API выше без изменений domain/engine/rules. 40 новых unit tests и 9 integration tests проверяют strict type/source/bounds, source до scalar projection, один fresh RNG на trial, отказ без retry/partial, четыре реальных outcomes, Wound/death/archive, zero-action unsupported, repeat/reverse/prefix/rename и изоляцию дополнительных бросков. Aggregate-only summary не удерживает records/results/journals.

[Production-пример](../examples/m8/magic_simulation.py) использует соседний public magic_scenario.py; вывод проверен из внешнего cwd и установленного wheel без PYTHONPATH. Его 32 single-run calls и scripted totals не являются Monte Carlo-метрикой. Полный suite и ограничения окружения перечислены в [аудите](../audits/m8-simulation-readiness.md) и [актуальном статусе](../project-status.md#последняя-проверка).

Первый profiling-срез завершён без изменения этого API: [контракт](../benchmarks/m8-profiling-contract.md), [baseline](../benchmarks/m8-baseline-2026-10-26.md), [аудит](../audits/m8-profiling-readiness.md). [Magic process transport/spawn contract ADR-0039](ADR-0039-process-magic-simulations.md) и конечный probe готовы; [production backend](../audits/m8-process-readiness.md) теперь реализован и проверен отдельными tests. Его performance остаётся следующим срезом; контрактный probe сам по себе не заменяет эти проверки.
