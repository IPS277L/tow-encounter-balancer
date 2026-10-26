# Текущий статус проекта

Дата обновления: 2026-10-26.

## Текущий этап

**M8: первый profiling baseline последовательных magic-пакетов завершён.** Готовы [контракт](benchmarks/m8-profiling-contract.md), [authored fixtures](../tools/m8_benchmark_fixtures.py), [harness](../tools/profile_m8.py), [сырой отчёт](benchmarks/m8-baseline-2026-10-26.md) и [аудит](audits/m8-profiling-readiness.md). Production src и игровые правила не менялись; 34 новых deterministic tests проверяют фикстуры и методику.

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
| M8 profiling | Два трёхакторных боевых case и отдельный zero-action control, 100 trials / seed 20261026 / budget 4; три wall repeats + отдельные trace/profile. [Аудит baseline](audits/m8-profiling-readiness.md); process ещё не реализован |

Публичные примеры и команды: [README](../README.md), [индекс документации](README.md), [примеры M8](examples/m8/README.md). Контракты и правила остаются в архитектуре, ADR и tests; история не заменяет актуальные источники.

## Известные ограничения

- PG 1.4 и GM 1.1 имеют приоритет над P1 и текущим кодом; игровые неоднозначности перечислены в [открытых вопросах](open-questions.md). Новых house rules в ADR-0038 нет.
- Готовые сценарии принимают ограниченные числовые профили и явные GM facts. Полные NPC/spell/Talent/item каталоги, PC-сценарии, универсальная тактика и общая battle orchestration ещё не реализованы.
- Первый magic runner поддерживает Curse, Broken Recover/Run и первый timed Wound consumer Stomach Blow → Drained expiry. Другие обязательные Wound/Miscast последствия, обычный Attack Give Ground, неизвестная scene/route и отдельная chronology остаются явными unsupported stops; pool/history/pending не очищаются для продолжения.
- Broken/уход в другую Zone не считаются defeat. UNSUPPORTED_PATH учитывается отдельно, не превращается в draw/loss/success и не исключается из trials.
- Magic process backend, метрика/assessment/balance, generation и JSON/CLI требуют дальнейших отдельных контрактов. Первый sequential profiling выполнен. ADR-0038 не добавляет public rates/means.
- 33 известных errors старых dataclasses assertions под Python 3.12 — отдельная задача; [подробности](open-questions.md#проверки-dataclasses-на-python-312). Полный набор текущей вехи: 3114 tests / те же 33 errors. Новые ошибки нельзя списывать на baseline.
- Baseline измерен на CPython 3.12.15 / macOS 26.5.1 arm64 только для двух authored боевых cases и control. Большие N, другие workloads/Python/ОС, process startup/serialization и RSS не измерены. Воспроизводимость требует тех же входа, правил и совместимого RNG/runtime; независимость произвольной RNG factory не доказывается.

## Исходный материал

Нормативные источники и локальные извлечения: [source-index.md](source-index.md), иерархия — [source-policy.md](source-policy.md). Для M8 непосредственно сверены PG 1.4 Rules / Combat, стр. 112; Conditions / Broken, стр. 122; Magic / Miscasts, стр. 157; Battle Magic / Curse, стр. 162; Wounds Table, стр. 190–191; GM 1.1 Allies and Antagonists / Minions, Champions, стр. 91–92. Seed и агрегаты — технический контракт, не новое игровое правило.

## Следующий шаг

Подготовить отдельный контракт опционального magic process transport/spawn и конечный probe нескольких indexed trials с настоящим spawn round-trip. Определить payload, проверку полного source после pickle и нормализацию равных worker copies к общему исходному scenario родителя; сохранить seeds/order/четыре исхода/fail-fast/cleanup. Production process executor и cache не добавлять в контрактный срез. Выгодность процессов затем проверять отдельным большим N с полными startup/serialization/shutdown costs: baseline сам по себе не доказывает ускорения.

## Последняя проверка

macOS arm64 / Python 3.12.15. 34 новых tests — OK: 10 fixture tests (0,025 с), 24 harness tests (0,315 с). После benchmark полный набор: **3114 tests / 33 прежних errors (100,078 с)**; Counter полных error headers и exception signatures точно совпал с baseline ADR-0038. Новых ошибок нет; полный suite не зелёный. Лог: `/private/tmp/towr-m8-profiling-tests.log`.

Baseline: 1509 trials с прогревом, 15 полных measured batches; все records/summary каждого case равны между тремя wall repeats и отдельными trace/profile. Медианы 100-trial боевых пакетов — 0,184446 и 0,215089 с, peak traced Python — 773,7/953,2 KiB. Unsupported 20/11 сохранены в N. Control имеет 100 unsupported, ноль actions/dice и показывается отдельно. Manifest до/после: `2d2444c68b9152843ea92f1048c41881e0f76fcceb561012c372509591736bc4`. Никакой production оптимизации или process backend в этом срезе нет.

```sh
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m tools.profile_m8 --trials 100 --master-seed 20261026 --round-budget 4 --repeats 3 --top 16 --output docs/benchmarks/m8-baseline-2026-10-26.md
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest discover -s tests -q
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m compileall -q src tests tools
git diff --check
```

## История

Compileall, public imports новых tools, 2738 локальных Markdown-путей/входящие anchors и whitespace — OK; source/harness manifest совпал с baseline после всех проверок. Оба архива содержат побайтно сохранённые исходные документы до вехи. Активный контекст сокращён без потери исторической evidence; прежние production/tests/tools не менялись.

[Полный прежний статус и команды проверок](project-status-history.md) и [закрытые вопросы/исторические boundaries](open-questions-history.md) сохранены целиком до текущей вехи. Архивы находятся на том же уровне docs, поэтому их относительные пути сохраняют смысл. Читать их при необходимости конкретной evidence, а не при каждом восстановлении контекста.

## Незакоммиченные файлы текущей вехи

На старте HEAD `908bb28` (M8 P5), рабочее дерево чистое: прежние 26 файлов пользователь закоммитил. Все 17 файлов ниже относятся к profiling-вехе. Commit/push не выполнялись.

```text
 M docs/README.md
 M docs/benchmarks/README.md
 M docs/contradictions.md
 M docs/decisions/ADR-0038-independent-magic-simulations.md
 M docs/open-questions.md
 M docs/project-status.md
 M docs/roadmap.md
 M docs/rule-traceability.md
 M docs/source-index.md
 M docs/testing.md
?? docs/audits/m8-profiling-readiness.md
?? docs/benchmarks/m8-baseline-2026-10-26.md
?? docs/benchmarks/m8-profiling-contract.md
?? tests/unit/test_m8_benchmark_fixtures.py
?? tests/unit/test_m8_profiling.py
?? tools/m8_benchmark_fixtures.py
?? tools/profile_m8.py
```
