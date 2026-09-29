# ADR-0030: опциональные mixed-прогоны в процессах

Статус: контракт принят в согласованном направлении M7, 2026-09-29. **Production backend реализован; 11 unit и 6 real-spawn integration tests.** Измерения и [общий аудит массовой mixed-симуляции](../audits/m7-mass-simulation-readiness.md) завершены. Конечный transport probe сохранён как исторический пример; проверки готового API описаны в конце.

## Основание и граница

[ADR-0029](ADR-0029-independent-mixed-simulations.md) реализует независимые последовательные mixed trials и summary. [Исходное профилирование](../benchmarks/README.md#m7-исходное-профилирование-mixed-simulation) и [эксперимент continuation](../benchmarks/m7-round-continuation-review.md) завершены; последний отклонён без изменения production. Опциональный process backend следует существующей модели [Melee ADR-0023](ADR-0023-process-melee-simulations.md) и [ranged ADR-0015](ADR-0015-process-ranged-simulations.md). Это возможность явного выбора способа исполнения, не обещание ускорения и не автоматический выбор backend.

Непосредственно перечитаны BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112 (round/turn/action и порядок сторон), BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91 (Wound побеждает Minion, disposition остаётся решением attacker/GM). Игровые правила, fixed-role admission и явные facts/policies [ADR-0028](ADR-0028-mixed-minion-scenario.md) сохраняются; scheduling является техническим контрактом. Новых Rule IDs/house rules нет.

## Публичный API

Новый отдельный модуль `towr.simulation.npc_mixed_parallel`:

```python
run_npc_mixed_simulation_parallel(
    request: NpcMixedSimulationRequest, *, workers: int,
    batch_size: int = 32, rng_factory: Callable[[int], RandomSource] = Random,
) -> NpcMixedSimulationResult
```

API реализован в [npc_mixed_parallel.py](../../src/towr/simulation/npc_mixed_parallel.py). Existing request/result/trial/summary и `summarize_npc_mixed_simulation` не меняются; нового wrapper результата или общего семейства simulator types нет. Sequential API остаётся самостоятельным. Workers/batch_size не входят в source_request и не влияют на seed scheme, размер выборки, цель, round budget или GM facts.

Process orchestration принадлежит simulation. Domain/engine/rules/balance не импортируют multiprocessing/executors. Worker вызывает существующий [run_npc_mixed_trial](../../src/towr/simulation/npc_mixed_simulation.py); не дублирует mixed runner, kernel, terminal acknowledgement/exclusion или summary. Ranged/Melee APIs, seed schemes и wire contracts не меняются. Generic scheduler, общий battle aggregate, дополнительный cache не вводятся.

## Preflight и запуск

До создания pool:

1. Проверить NpcMixedSimulationRequest; чужие ranged/Melee requests и нетипизированный input отклонять TypeError.
2. `workers` и `batch_size` — положительные exact int: bool/float/str/None дают TypeError, zero/negative дают ValueError.
3. Factory должна быть callable; иначе TypeError. Проверить `pickle.dumps((request, rng_factory))`; ошибка сериализации распространяется без запуска детей, смены категории или fallback.

Не делать пробный вызов factory/RNG/trial в parent. Успешный pickle не гарантирует импорт callable в child; ошибки импорта/transport остаются ошибками исполнения. Платформенные пределы workers проверяет ProcessPoolExecutor; доменный cap или auto CPU count не вводятся. `batch_size=32` — технический default прежних backend, не измеренный optimum mixed.

Каждый вызов создаёт свой ProcessPoolExecutor с явным `get_context("spawn")`, независимо от глобального start method. Даже workers=1 исполняет trial в ребёнке. Workers может превышать число пакетов. Caller должен запускаться из импортируемого Python-модуля с `if __name__ == "__main__":`; stdin/REPL/notebook entry point не обещаны.

Custom factory — импортируемая/picklable top-level callable или partial такой функции. Она создаёт новый независимый RNG из supplied seed при каждом вызове. Factory, зависящая от PID, порядка вызовов, общей изменяемой памяти или внешних side effects, не получает гарантии равенства sequential. Локальные lambda/closures не поддерживаются. Pickle служит внутренним транспортом доверенных объектов, не внешним JSON/CLI форматом.

## Пакеты, очередь и результат

- Ленивые абсолютные диапазоны `range(start, min(start + batch_size, request.trials))`. Неполный хвост допустим; batch_size > trials даёт один пакет. Не создавать весь список tasks/futures заранее.
- Каждый пакет получает тот же request, свой диапазон и factory. Для каждого индекса вызывается existing mixed trial: первоначальный immutable scenario, свежий RNG, исходный бюджет раундов. Conditions/defeats/continuations/used IDs между trials не переносятся.
- Seed вычисляется только existing `towr:npc-mixed-trial:v1` по master_seed и абсолютному trial_index. Нет worker seed, локального индекса пакета, PID или arrival-order seed.
- Одновременно outstanding не более `min(2 * workers, число ещё доступных пакетов)` при первоначальном заполнении, затем не более `2 * workers` futures в целом. После получения completed пакетов добавлять очередные диапазоны; сначала прочитать все futures из returned done, затем refill. Workers не запускают вложенные pools.
- Worker возвращает tuple компактных NpcMixedTrialSummary. Боевые журналы, текущие snapshots/continuations, PID и копии source_request не входят в returned batch. PID допустим только как диагностика probe/tests.
- После успешного получения всех records parent строит NpcMixedSimulationResult со **своим исходным request**. Existing constructor сортирует по index, проверяет полноту/уникальность, seeds, typed outcomes и counter/budget bounds. Отказ constructor — ошибка, не игровой исход. Result и summary должны полностью совпадать с sequential при одинаковом input/factory/runtime независимо от workers/partition/порядка получения.

Exact source проверяется внутри existing trial до удаления полного scenario journal. Компактный record не содержит полный source: проверки родителя структурные и сами по себе не доказывают происхождение бросков или истинность внешних GM facts. Worker — доверенная часть simulation, не произвольный удалённый сервис.

Граница памяти: O(trials) компактных records плюс ограниченные in-flight задачи и их транспортные копии. Bounded queue не является streaming или жёсткой квотой памяти. Request сериализуется заново на каждый batch; pool создаётся/закрывается на каждый вызов. Практический предел времени/памяти не следует из uint64 admission.

## Четыре исхода и реальный unsupported

Outcome берётся из полного mixed scenario result **после terminal suffix**, Attack/visited — из runner_report. Pending defeat в последнем raw runner stop не создаёт лишние trial/Attack/round. Resume того же раунда не считается новым посещённым раундом.

Все `objective_achieved`, `side_defeated`, `round_limit`, `unsupported_path` сохраняются отдельно. Mixed отличается от минимального Melee тем, что реальный NO_CANDIDATE получается без подмены контроллера: после поражения последней Close-цели живой Melee actor может не иметь доступной Attack по оставшемуся дальнему врагу. Worker возвращает такой observation, не пропускает ход и не меняет тактику. Это не exception, поражение или ничья.

Знаменатель — все N trials; unsupported не фильтруется и не заменяется повторным trial. Summary остаётся описанием наблюдений, а не заявлением о пригодности для подбора. Future assessment должен отдельно учитывать неподдержанность. Новых метрик/presets/conditional win rate нет.

## Ошибки и cleanup

Batch перехватывает обычное Exception только для note `M7 trial index=<index>, seed=<seed>` и немедленно пробрасывает его. Следующий индекс того же batch после ошибки не запускается. Serializable child error доходит через Future с типом/message/notes; при невозможности сериализации распространяется transport error. Source/factory/RNG/executor/import/BrokenProcessPool/submission/wait/result-construction ошибки не становятся unsupported или проигрышем.

Не возвращать partial complete result, не выполнять retries или sequential fallback. В finally отменить outstanding futures, которые ещё допускают cancel; context manager закрывает pool с ожиданием уже выполняющейся работы. Уже отправленный в process queue batch может продолжиться. Контракт не обещает немедленной остановки всех trials при первой ошибке; completed/running/queued работу нельзя считать атомарно отменённой.

KeyboardInterrupt/SystemExit не оборачиваются worker-обработчиком Exception и не конвертируются в игровые исходы; cleanup всё равно проходит через finally/context manager. Immutable parent request не меняется, внешние side effects custom factory не откатываются. Hard kill/timeout, persistent pool, checkpoint, streaming и remote execution сюда не входят.

## Конечный probe и честная граница проверки

[process_contract_probe.py](../examples/m7/process_contract_probe.py) использует public builder из соседнего mixed_scenario.py, existing mixed trial/result/summary и стандартный ProcessPoolExecutor(spawn). [Вывод](../examples/m7/process_contract_probe.output.txt) сохранён. Это **не реализация предлагаемого backend**: передаются заранее заданные крошечные partitions, без lazy refill/admission/cancellation scheduler.

Два состава 3×2/2×2, 5 trials, master_seed=42, budget=2: sequential сравнивается с fixed partitions 3+2 (workers=1), 2+2+1 (workers=2), один пакет 5 (workers=2). Пакеты собираются в обратном submission порядке; полные result/summary равны, parent source identity сохраняется. Отдельные четыре scripted 2×2 trials дают counts 1/1/1/1, 17 Attack и 6 visited rounds, включая реальную потерю Close-цели. Factory failure на индексе 1 сохраняет type/message/index/seed note, batch не возвращает частичный result; pool закрывается. Проверены pickle round-trip, child PID, parent/child input/global RNG и отсутствие оставшихся детей. Всего 49 завершённых trials и один отказ factory.

Probe не проверяет будущие public options/preflight, ленивое пополнение/общую bound очереди, submission/wait/refill/cancel failures, interrupts или чужие worker records. Это обязательства implementation tests ниже; факт успешного probe не закрывает их. Старые Melee/ranged tests подтверждают основу подхода, не являются тестами отсутствующего mixed backend. Benchmark скорости процессов не проводился.

## Матрица следующей реализации

| Группа | Проверки |
| --- | --- |
| Preflight | Mixed typed request, чужие families, workers/batch_size exact positive int, callable/pickle failures до pool и без factory/RNG calls |
| Планирование | Явный spawn; lazy absolute ranges, bounded 2×workers, reverse completion, initial/refill, uneven tail, batch > N, workers > batches |
| Worker | Existing trial, отсутствие повторного kernel, новое initial/RNG; compact tuple; index/seed note; остановка внутри batch; BaseException без игрового wrapper |
| Результат | Parent request identity; sorted complete unique records, seed/outcome/counters; missing/duplicate/invalid records отвергаются; summary equality |
| Ошибки | initial/refill submit, wait, Future.result, final constructor; отмена pending и выход из pool без partial result; no retry/fallback |
| Real spawn | 2×1/3×2/2×2, workers 1/2 и разные partitions; полная equality sequential/summary, repeat/expanded prefix, child PID, input/global RNG/cleanup |
| Mixed semantics | Четыре реальные scripted outcomes на одном input, NO_CANDIDATE без подмены, terminal suffix, visited/resume и актуальный локальный outnumbering с GM flags |

Числовые RNG scripts допускают точные outcome/counters expectations. Seeded Monte Carlo-тесты проверяют воспроизводимость/equality, не фиксированный процент побед и не порог скорости.

Модуль `npc_mixed_parallel.py` и unit/real-spawn integration tests реализованы. Следующий отдельный performance-срез сравнит sequential/process с учётом startup/serialization/shutdown, сохраняя records/summary. Balance/generation, JSON/CLI, движение, смена оружия, магия и общий battle aggregate не входят ни в текущий контрактный шаг, ни автоматически в process backend.

Проверка контрактного среза: Windows / Python 3.14.5, **47 existing tests OK (29,509 с)**. Probe из корня и временного каталога прошёл с одинаковым stdout/пустым stderr. Compileall, 1716 локальных Markdown-путей, import boundaries, diff/whitespace успешны. Src/tests/tools не менялись; новый backend и unittest tests не добавлены. Последняя полная регрессия остаётся 2391 OK (223,864 с), в этом документационном срезе не повторялась. Все 14 исходных dirty/untracked файлов сохранены, commit/push не выполнялись.

## Реализация и проверка

[Backend](../../src/towr/simulation/npc_mixed_parallel.py) сохраняет архитектуру existing Melee runner без общего scheduler. [11 unit tests](../../tests/unit/test_m7_npc_mixed_parallel.py) проверяют admission до pool, pickle, absolute indices, bounded initial/refill, reverse completion и uneven tail, invalid records, batch failure note, interrupts/cancellation, startup/submission/wait/result/final-constructor failures без partial result/retry. Вход с trials=2**64−1 планирует только четыре первые трёхэлементные диапазона до injected failure; весь список задач не материализуется.

[6 integration tests](../../tests/integration/test_m7_npc_mixed_parallel.py) запускают настоящие spawn workers для трёх составов и сравнивают полные result/summary с sequential. Workers=1 действительно исполняет в child; workers больше пакетов, хвост, repeat/expanded prefix проверены. Четыре реальные scripted outcomes (включая NO_CANDIDATE) сохраняют counts 1/1/1/1 и 17 Attack/6 visited. Отдельно проверены динамический локальный bonus с True/False GM approval, terminal counts, дополнительные броски только одного stream, source/global RNG/cleanup, исходная note и новый index/seed note при ошибке child factory.

17 новых tests прошли (17,551 с), Windows/Python 3.14.5. Производительность не является test expectation; сравнение startup/serialization/shutdown — следующий срез. Полная проверка и ограничения среды фиксируются в project-status.md. Domain/engine, sequential API, seed schemes, Melee/ranged process и wire contracts не менялись.

Итог implementation-среза: **2408 tests OK (255,257 с)**, Windows/Python 3.14.5; отдельно 17 новых tests OK (17,551 с). Compileall, 1735 локальных Markdown-путей, AST import boundaries, diff/whitespace успешны. Готовый Python API snippet проверен из отдельного временного каталога. Все 21 исходный dirty/untracked файл сохранены; добавлены backend и два test-файла, обновлена документация. Commit/push не выполнялись; performance/другие ОС/Python 3.12/installed wheel не проверялись.

## Измерения sequential/process — 2026-09-29

[Сравнение](../benchmarks/README.md#mixed-sequential-и-spawn) выполнено для прежних mixed fixtures 2×1/3×2/2×2, 100/1000 trials, master_seed=20260929, budget=5, workers=1/2, batch_size=32, три чередующихся повтора. Все 54 полных результата и summary равны внутри соответствующего входа; canonical digests и четыре outcomes сохранены. Source/harness hash совпадает до/после, 100-trial digests совпали с baseline.

На 100 trials spawn медленнее; на 1000 один worker также медленнее, два workers дают локальные 1,298×/1,196× для 3×2/2×2. В 2×1 диапазоны перекрываются. Измерения включают fresh pool startup/serialization/shutdown; памяти процессов, других платформ и универсального порога полезности они не устанавливают. Auto backend/persistent pool не добавлены. Шесть новых tests проверяют корректность harness, не скорость. Production API и правила не менялись; [общий аудит ADR-0029/0030](../audits/m7-mass-simulation-readiness.md) завершён; текущий hash совпал с отчётами. Следующий срез — контракт оценки mixed-кандидатов.
