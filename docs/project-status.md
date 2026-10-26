# Текущий статус проекта

Дата обновления: 2026-10-26.

## Текущий этап

**M8: production process backend ADR-0039 завершён.** Готовы [модуль](../src/towr/simulation/npc_magic_parallel.py), [контракт](decisions/ADR-0039-process-magic-simulations.md), [публичный пример](examples/m8/magic_parallel.py) и [аудит](audits/m8-process-readiness.md). 30 новых tests проверяют preflight/transport/bounded scheduling, ошибки и настоящий spawn. Public request/result/summary и single-run scope сохраняются; performance процессов пока не измерен.

Работа идёт небольшими последовательными шагами без запроса продолжения между ними; независимые тесты и ревью делегируются с раздельным владением файлами. Режим закреплён в [AGENTS.md](../AGENTS.md#автономная-работа-до-согласованной-вехи). Commit/push выполняет пользователь.

## Зафиксировано

| Область | Готовность и точная граница |
| --- | --- |
| R1 | PG 1.4 и GM 1.1 прочитаны, правила и каталоги проиндексированы; [аудит книг](audits/rulebooks-1.4-1.1.md) и [трассировка](rule-traceability.md) |
| K1 | Типизированные Basic/Opposed/Exacting Tests, Attack/Protection, Staggered, Wounds Table, все четыре injury policies, выбранные эффекты/Hazards, action/movement/healing/Fate/Casting boundaries; [аудит ядра](audits/k1-readiness.md). Это не полный каталог и не универсальный бой |
| M2–M5 | Неподвижный ranged Minion-сценарий, independent sequential/process trials, агрегаты, оценка/поэтапный подбор/генерация из заданного резерва и JSON/CLI; [аудит внешнего M5](audits/m5-external-readiness.md) |
| M6 | Неподвижный melee Minion-сценарий с динамическим outnumbering и теми же слоями simulation/balance/JSON/CLI; [аудит](audits/m6-external-readiness.md) |
| M7 | Неподвижный mixed melee/shooting Minion-сценарий, sequential/process, агрегаты/подбор/генерация и JSON/CLI; [аудит](audits/m7-external-readiness.md) |
| M8 single-run | Один authored Champion-Wizard, canonical Curse of Cowardly Flight, allied/enemy numeric Shooting Minions, explicit scene facts, полный owner/journal и обязательные continuations/end-turn; [аудит](audits/m8-encounter-readiness.md), [public пример](examples/m8/magic_scenario.py) |
| M8 simulation | Новые модули simulation сохраняют single-run scope; отдельная seed scheme, общий fresh input, новый RNG на trial, full-source compact records и четыре исхода. [Аудит готовности](audits/m8-simulation-readiness.md) завершён |
| M8 profiling | Два трёхакторных боевых case и отдельный zero-action control, 100 trials / seed 20261026 / budget 4; три wall repeats + отдельные trace/profile. [Аудит baseline](audits/m8-profiling-readiness.md); process performance ещё не измерен |
| M8 process | [ADR-0039](decisions/ADR-0039-process-magic-simulations.md): реализованы strict preflight/transport/source normalization, lazy bound 2W и fail-fast/cleanup. [Аудит готовности](audits/m8-process-readiness.md); исторический finite probe сохранён побайтно |

Публичные примеры и команды: [README](../README.md), [индекс документации](README.md), [примеры M8](examples/m8/README.md). Контракты и правила остаются в архитектуре, ADR и tests; история не заменяет актуальные источники.

## Известные ограничения

- PG 1.4 и GM 1.1 имеют приоритет над P1 и текущим кодом; игровые неоднозначности перечислены в [открытых вопросах](open-questions.md). Новых house rules в ADR-0038 нет.
- Готовые сценарии принимают ограниченные числовые профили и явные GM facts. Полные NPC/spell/Talent/item каталоги, PC-сценарии, универсальная тактика и общая battle orchestration ещё не реализованы.
- Первый magic runner поддерживает Curse, Broken Recover/Run и первый timed Wound consumer Stomach Blow → Drained expiry. Другие обязательные Wound/Miscast последствия, обычный Attack Give Ground, неизвестная scene/route и отдельная chronology остаются явными unsupported stops; pool/history/pending не очищаются для продолжения.
- Broken/уход в другую Zone не считаются defeat. UNSUPPORTED_PATH учитывается отдельно, не превращается в draw/loss/success и не исключается из trials.
- Magic process backend ADR-0039 реализован и проверен; автоматический выбор backend и обещание ускорения не добавлены. Метрика/assessment/balance, generation и JSON/CLI требуют дальнейших отдельных контрактов. Первый sequential profiling выполнен. ADR-0038 не добавляет public rates/means.
- 33 известных errors старых dataclasses assertions под Python 3.12 — отдельная задача; [подробности](open-questions.md#проверки-dataclasses-на-python-312). Полный набор текущей вехи: 3145 tests / те же 33 errors. Новые ошибки нельзя списывать на baseline.
- Baseline измерен на CPython 3.12.15 / macOS 26.5.1 arm64 только для двух authored боевых cases и control. Большие N, другие workloads/Python/ОС, process startup/serialization и RSS не измерены. Воспроизводимость требует тех же входа, правил и совместимого RNG/runtime; независимость произвольной RNG factory не доказывается.

## Исходный материал

Нормативные источники и локальные извлечения: [source-index.md](source-index.md), иерархия — [source-policy.md](source-policy.md). Для M8 непосредственно сверены PG 1.4 Rules / Combat, стр. 112; Conditions / Broken, стр. 122; Magic / Miscasts, стр. 157; Battle Magic / Curse, стр. 162; Wounds Table, стр. 190–191; GM 1.1 Allies and Antagonists / Minions, Champions, стр. 91–92. Seed и агрегаты — технический контракт, не новое игровое правило.

## Следующий шаг

Выполнить отдельный performance-срез sequential/process над текущими tools/m8_benchmark_fixtures: два боевых case и отдельный zero-action control, 100/1000 trials, workers 1/2, batch_size 32, три чередующихся повтора. Включить startup/serialization/normalization/shutdown, сравнить полные records/summary, сохранить source manifest и отдельные counters/unsupported. Прежде подтвердить ограниченную методику harness и покрыть её детерминированными tests; затем снять замеры без параллельных тяжёлых проверок. Timing не unittest threshold; cache, auto backend, assessment/balance/generation и JSON/CLI автоматически не расширять.

## Последняя проверка

macOS arm64 / Python 3.12.15. 30 новых tests — OK: 23 unit (0,037 с), 6 real-spawn (2,910 с) и 1 external-cwd example (1,760 с). Полная регрессия: **3145 tests / 33 прежних errors (97,011 с)**; Counter полных error headers и exception signatures точно совпал с contract baseline. Новых ошибок нет; полный suite не зелёный. Лог: `/private/tmp/towr-m8-parallel-tests.log`.

Installed wheel из отдельной временной копии, без repo egg-info мутаций/PDF/tests: трёхфайловый public example без PYTHONPATH вне repo дал тот же stdout и пустой stderr. Все 411 installed Python/Schema files побайтно равны src. В примере шесть public process calls / 24 spawned trials, полные sequential results/summary, parent scenario identity, четыре scripted outcomes и zero-action stop. Source/global RNG/active_children сохранены. Build/install/hash evidence — в [аудите](audits/m8-process-readiness.md).

```sh
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest discover -s tests -q
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m compileall -q src tests tools docs/examples/m8
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python docs/examples/m8/magic_parallel.py
git diff --check
```

## История

Compileall, public/layer imports, 2820 локальных Markdown-путей/входящие anchors и whitespace — OK. Новый process module меняет общий src/harness hash: исторический sequential baseline не переснимался и не является process benchmark. Оба архива содержат побайтно сохранённые исходные документы до вехи. Активный контекст сокращён без потери исторической evidence; прежние production/tests/tools не менялись.

[Полный прежний статус и команды проверок](project-status-history.md) и [закрытые вопросы/исторические boundaries](open-questions-history.md) сохранены целиком до текущей вехи. Архивы находятся на том же уровне docs, поэтому их относительные пути сохраняют смысл. Читать их при необходимости конкретной evidence, а не при каждом восстановлении контекста.

## Незакоммиченные файлы текущей вехи

На старте HEAD `7ca5362` (M8 P6) и 16 existing dirty/untracked файлов предыдущей контрактной вехи. Они учтены как исходные: три probe/.output/test сохранены побайтно, документация синхронизирована с реализацией. Прежние Python-файлы src/tests/tools не менялись. Всего сейчас 24 изменённых/новых файла, включая исходные 16. Commit/push не выполнялись.

```text
 M README.md
 M docs/README.md
 M docs/benchmarks/README.md
 M docs/contradictions.md
 M docs/decisions/ADR-0038-independent-magic-simulations.md
 M docs/examples/m8/README.md
 M docs/open-questions.md
 M docs/project-status.md
 M docs/roadmap.md
 M docs/rule-traceability.md
 M docs/source-index.md
 M docs/testing.md
?? docs/audits/m8-process-contract-readiness.md
?? docs/audits/m8-process-readiness.md
?? docs/decisions/ADR-0039-process-magic-simulations.md
?? docs/examples/m8/magic_parallel.output.txt
?? docs/examples/m8/magic_parallel.py
?? docs/examples/m8/process_contract_probe.output.txt
?? docs/examples/m8/process_contract_probe.py
?? src/towr/simulation/npc_magic_parallel.py
?? tests/integration/test_m8_magic_parallel_example.py
?? tests/integration/test_m8_magic_process_contract_probe.py
?? tests/integration/test_m8_npc_magic_parallel.py
?? tests/unit/test_m8_npc_magic_parallel.py
```
