# ADR-0023: опциональные Melee-прогоны в процессах

Статус: принято, 2026-09-28. **Реализовано; 8 unit и 5 real-spawn integration tests.**

## Основание и граница

[ADR-0022](ADR-0022-independent-melee-simulations.md) реализует независимый последовательный Melee simulation и aggregate-only summary. [Профилирование и первый performance-срез](../benchmarks/README.md#однократная-minion-defeat-continuation) завершены. Следующий шаг — отдельный опциональный process backend с тем же seed/result контрактом. Основание композиции — реализованный [ranged backend ADR-0015](ADR-0015-process-ranged-simulations.md), а не новый общий исполнитель боя.

Игровые правила и допуск [ADR-0021](ADR-0021-melee-minion-scenario.md) сохраняются. Непосредственно перечитаны BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112 (раунд/ход/действие) и BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91 (defeat и решение attacker/GM). Process scheduling — технический контракт, не новое правило. Не добавляются движение, PC, смешанный бой, NPC abilities, balance/evaluator/generator или CLI/JSON.

## Публичный API и зависимости

Модуль [towr.simulation.npc_melee_parallel](../../src/towr/simulation/npc_melee_parallel.py):

```python
run_npc_melee_simulation_parallel(
    request: NpcMeleeSimulationRequest, *, workers: int,
    batch_size: int = 32, rng_factory: Callable[[int], RandomSource] = Random,
) -> NpcMeleeSimulationResult
```

API реализован. Вход/выход и `summarize_npc_melee_simulation` остаются прежними; новый result wrapper не требуется. Sequential API самостоятельный, выбор process явный. Backend не меняет master_seed/trials/round budget/facts/policies и не конвертирует ranged request в Melee. Ranged backend, seeds и wire v1 не меняются.

Процессы принадлежат simulation; domain/engine/rules/balance не импортируют multiprocessing. Реализация использует существующий `run_npc_melee_trial`, не дублирует scenario loop, kernel, terminal consequences или summary. Не вводится generic scheduler/rules engine ради общего кода двух backend.

## Preflight и запуск

До создания pool проверяются typed NpcMeleeSimulationRequest, callable factory, положительные integer workers/batch_size без bool/строк/float; затем сериализуемость `(request, rng_factory)` через pickle. Неверный тип даёт TypeError, неположительное значение — ValueError. Ошибка сериализации распространяется в исходной категории. Дополнительные платформенные ограничения выполняет ProcessPoolExecutor; на проверенном Windows runtime workers > 61 отклоняются до запуска детей. Это предел стандартной библиотеки, не новый domain cap.

Каждый вызов создаёт собственный ProcessPoolExecutor с `get_context("spawn")`, независимо от глобального start method. Даже workers=1 выполняет trials в ребёнке. Число CPU и выгодность параллелизма автоматически не определяются; workers может превышать число пакетов без смены API/результата. Значение batch_size=32 — технический default, не доказанный оптимум Melee.

Caller запускается из импортируемого Python-модуля с `if __name__ == "__main__":`. REPL/stdin/notebook как entry point этим контрактом не обещаны. Custom factory должна быть импортируемой/picklable top-level callable (либо partial такой функции) и создавать новый RNG только по supplied seed. Lambda/local closure не поддерживаются; успешный parent pickle не гарантирует успешный импорт callable в ребёнке. Pickle здесь внутренний транспорт доверенных Python объектов, не формат пользовательского ввода.

## Пакеты, очередь и воспроизводимость

1. Диапазоны абсолютных trial indices выдаются лениво: `range(start, min(start + batch_size, request.trials))`. Неполный хвост допустим; batch_size больше trials даёт один пакет. Seed вычисляется по прежней `towr:npc-melee-trial:v1`, не по локальному номеру внутри пакета, PID или порядку завершения.
2. Каждый worker batch получает тот же immutable request, свой диапазон и factory. Для каждого индекса вызывает `run_npc_melee_trial`, который проверяет typed/full scenario source и строит compact record. Full battle journals и continuation не передаются родителю или следующему trial; используются исходный scenario и свежий RNG.
3. Одновременно outstanding не более `2 * workers` futures (с учётом фактического числа пакетов). После получения completed futures добавляются следующие диапазоны, без заранее материализованного списка всех задач. Workers не создают вложенные pools.
4. Порядок получения completed пакетов произвольный. После успешного получения всех записей родитель создаёт NpcMeleeSimulationResult **со своим исходным request**. Existing constructor сортирует по index и проверяет полноту, отсутствие дубликатов, seed/outcome/counter bounds. Его отказ — ошибка выполнения, не unsupported outcome.
5. Returned result и чистая summary должны совпадать с sequential для тех же input/RNG/runtime независимо от workers/batch_size/порядка завершения. Новый seed version, дополнительные броски и seed для worker не вводятся. Нельзя обещать это для factory, зависящей от глобального состояния, PID, счётчика вызовов или внешних side effects.

Граница памяти: O(trials) compact records и bounded in-flight пакеты; это не streaming, hard memory quota или предел размера исходного request. Request передаётся заново на каждый batch, pool запускается/закрывается на каждый вызов. Параллельность не гарантирует ускорения малых пакетов.

## Melee outcome и terminal suffix

Worker использует existing trial projection: outcome берётся из NpcMeleeScenarioResult после terminal acknowledgement/exclusion; Attack/visited rounds — из runner_report. Последний raw runner stop может быть pending_follow_ups при уже достигнутой цели. Процесс не добавляет наблюдение, Attack или раунд, чтобы искусственно завершить очередь. Все четыре исхода остаются отдельными: objective_achieved, side_defeated, round_limit, unsupported_path.

Технический unsupported сохраняется как observation. Для штатного admitted Melee цикла он не ожидается; тест протокола требует source-consistent controller block. Нельзя переносить ranged fixture с пустой подменой candidates: Melee result по ADR-0021 отвергает это как ошибку источника. Остальные policy/GM/outnumbering проверки выполняются прежним scenario runner.

## Ошибки и закрытие pool

Worker batch перехватывает обычное Exception только для добавления note `M6 trial index=<index>, seed=<seed>`, затем пробрасывает его. RNG/source/executor ошибки не превращаются в поражения/unsupported и не исключаются из знаменателя. Сериализуемая ошибка доходит родителю через standard Future transport; если её нельзя сериализовать, распространяется ошибка транспорта. Import failures/BrokenProcessPool/ошибки submission/result construction также не скрываются.

На ошибке не возвращается partial complete result; retries, sequential fallback и автоматический повтор trial отсутствуют. Оставшиеся ещё не начатые pending futures получают cancel; pool закрывается context manager, уже выполняющаяся работа ожидается. Отмена может не остановить уже отправленную в process queue задачу. Поэтому ошибка не обещает мгновенного завершения или прерывания всех остальных trials. Hard kill/timeout/checkpoint/persistent pool не включены.

KeyboardInterrupt/SystemExit не преобразуются в игровые исходы и не оборачиваются worker-обработчиком Exception. Cleanup всё равно проходит через finally/context manager. Immutable parent input не меняется; внешние side effects произвольной factory не откатываются. JSON/CLI никогда не получает callable или pickle через этот ADR.

## Матрица реализации и проверки

| Обязанность | Готовое основание | Проверяемые обязанности backend |
| --- | --- | --- |
| Immutable request и seed | [Melee models](../../src/towr/simulation/npc_melee_models.py), ADR-0022 | Типы/options/callable/pickle до pool; ranged request отвергается |
| Один trial и terminal outcome | [Melee trial](../../src/towr/simulation/npc_melee_simulation.py) | Абсолютные indices; terminal suffix/dynamic bonus без повторного kernel/RNG |
| Bounded spawn orchestration | [Ranged backend](../../src/towr/simulation/npc_ranged_parallel.py) | Новый отдельный модуль; max 2×workers, reverse completion, uneven tail, workers=1 всё ещё spawn |
| Полнота и source/result | Existing NpcMeleeSimulationResult | Parent source identity; missing/duplicate/foreign seed/untyped outcome/counters отклоняются; workers не возвращают full journal |
| Summary | [Чистая проекция](../../src/towr/simulation/npc_melee_summary.py) | Полное равенство sequential/process summaries, без trial records в aggregate |
| Ошибки | [Melee unit tests](../../tests/unit/test_m6_npc_melee_parallel.py) | Child index/seed notes, submission/wait/result failures, cancellation/exit без partial result, сохранение source |
| Настоящие процессы | [Melee integration tests](../../tests/integration/test_m6_npc_melee_parallel.py) | Melee 1×1/2×2/3×2, workers 1/2, batch 1/3 и больше trials; equality всех records/summary, расширение prefix, child PID/global RNG/input/cleanup, child failure |

Тесты детерминированные: заданные d10 для точных outcomes/counters и seed replay без требования конкретного Monte Carlo процента. Четыре outcomes проверяются отдельно; малый real-seed набор не обязан естественно породить unsupported. Инъекция test-only controller stop находится в импортируемом RNG factory helper теста: он устанавливает одноразовый selector с исходными candidates и восстанавливает его перед возвратом решения. Это проверка транспорта unsupported, не production factory policy; основной replay использует Random(seed).

## Проверка совместимости до реализации

[process_contract_probe.py](../examples/m6/process_contract_probe.py) использует прежний 2×2 Footpad builder из runnable примера, existing public Melee trial/result/summary и стандартный spawn pool. Проверяет pickle round trip request/factory, три trial при workers 1/2 с переставленной подачей/сбором, parent source identity, равенство records/summary sequential, настоящий child PID, неизменные input/global RNG, передачу child exception и закрытие детей.

Это конечный probe совместимости объектов и trial, **не production parallel runner**: он не реализует batch scheduler, bounded queue, error notes или матрицу отказов нового API. Успех probe не считается закрытием критериев backend; src/tests не меняются контрактным шагом. Production проверки теперь перечислены ниже; актуальные команды/результат — в [project-status.md](../project-status.md#последняя-проверка).

## Реализация и проверка

[Backend](../../src/towr/simulation/npc_melee_parallel.py) использует existing trial executor и result constructor. [8 unit tests](../../tests/unit/test_m6_npc_melee_parallel.py) проверяют preflight/pickle до pool, bounded queue с обратным завершением, абсолютные indices/хвост, compact records, отказ worker/initial submission/refill/wait, cancellation/exit, guards result и необёрнутые BaseException. Тип outcome проверяется existing trial constructor по ADR-0022.

[5 integration tests](../../tests/integration/test_m6_npc_melee_parallel.py) запускают настоящий spawn: 1×1/2×2/3×2, workers 1/2, batch 1/2/3 и больше trials, records/summary equality и prefix. Заданные d10 проверяют три игровых исхода и terminal suffix с динамическим бонусом (2 Attack/1 visited round на trial); source-consistent controller stop даёт отдельный unsupported без RNG. Child PID, parent source identity, input/global RNG, передача exception с index/seed и закрытие процессов проверены. Производительность этим набором не измеряется.

## Сравнение sequential/process

[Harness и отчёты](../benchmarks/README.md#melee-sequential-и-spawn) готовы: прежние 1×1/2×2/3×2, seed 20260928, budget 5, 100/1000 trials, workers 1/2, batch_size 32 и три повтора. Сравниваются все records/summary, wall включает startup/serialization/shutdown; hash sources/двух harness modules проверяется до/после. На 100 trials spawn медленнее, на 1000 два workers дают локальное отношение sequential/process 1,317/1,347 для 2×2/3×2, для 1×1 — 1,045 с перекрывающимися диапазонами повторов. Это не гарантия скорости или автоматический порог; RSS не измерен. Добавлены [6 tests harness](../../tests/unit/test_m6_parallel_benchmark.py); production API не менялся.

## Следующий законченный шаг

[Конечный аудит независимых Melee-прогонов и summary](../audits/m6-simulation-readiness.md) выполнен: 46 tests массового среза, 100 M6 tests суммарно, полная регрессия 2074 OK. Source/harness hash прежних измерений совпал; production API не менялся. [Контракт оценки Melee-кандидатов ADR-0024](ADR-0024-melee-candidate-assessment.md) подготовлен: pure input/summary assessment и ограниченный явный список с бюджетом по принятой метрике. Pure assessment одного Melee-кандидата реализован по ADR-0024; модели ограниченного списка с бюджетом и application service исполнения списка тоже реализованы; [аудит bounded evaluation](../audits/m6-evaluation-readiness.md) и самостоятельный typed пример завершены. [Контракт поэтапной оценки ADR-0025](ADR-0025-staged-melee-evaluation.md) реализован: pure helper, frozen staged models и application service/error; следующий шаг — аудит staged evaluation и самостоятельный пример. Генератор и CLI/JSON остаются отдельными срезами.
