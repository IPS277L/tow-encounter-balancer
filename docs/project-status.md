# Текущий статус проекта

Дата обновления: 2026-10-26.

## Текущий этап

**M8: независимые последовательные magic-прогоны по [ADR-0038](decisions/ADR-0038-independent-magic-simulations.md).** Веха завершена: pure seed/request/record/counts/result, trial/batch executor, aggregate-only summary, 49 новых tests, public пример и installed-wheel parity. [Аудит слоя](audits/m8-simulation-readiness.md) закрыт в текущем single-run scope.

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

Публичные примеры и команды: [README](../README.md), [индекс документации](README.md), [примеры M8](examples/m8/README.md). Контракты и правила остаются в архитектуре, ADR и tests; история не заменяет актуальные источники.

## Известные ограничения

- PG 1.4 и GM 1.1 имеют приоритет над P1 и текущим кодом; игровые неоднозначности перечислены в [открытых вопросах](open-questions.md). Новых house rules в ADR-0038 нет.
- Готовые сценарии принимают ограниченные числовые профили и явные GM facts. Полные NPC/spell/Talent/item каталоги, PC-сценарии, универсальная тактика и общая battle orchestration ещё не реализованы.
- Первый magic runner поддерживает Curse, Broken Recover/Run и первый timed Wound consumer Stomach Blow → Drained expiry. Другие обязательные Wound/Miscast последствия, обычный Attack Give Ground, неизвестная scene/route и отдельная chronology остаются явными unsupported stops; pool/history/pending не очищаются для продолжения.
- Broken/уход в другую Zone не считаются defeat. UNSUPPORTED_PATH учитывается отдельно, не превращается в draw/loss/success и не исключается из trials.
- Magic process backend, profiling, метрика/assessment/balance, generation и JSON/CLI требуют дальнейших отдельных контрактов. ADR-0038 не добавляет public rates/means.
- 33 известных errors старых dataclasses assertions под Python 3.12 — отдельная задача; [подробности](open-questions.md#проверки-dataclasses-на-python-312). Полный набор текущей вехи: 3080 tests / те же 33 errors. Новые ошибки нельзя списывать на baseline.
- Другие версии Python/ОС и скорость нового simulation-слоя пока не проверены. Воспроизводимость требует тех же входа, правил и совместимого RNG/runtime; независимость произвольной RNG factory не доказывается.

## Исходный материал

Нормативные источники и локальные извлечения: [source-index.md](source-index.md), иерархия — [source-policy.md](source-policy.md). Для M8 непосредственно сверены PG 1.4 Rules / Combat, стр. 112; Conditions / Broken, стр. 122; Magic / Miscasts, стр. 157; Battle Magic / Curse, стр. 162; Wounds Table, стр. 190–191; GM 1.1 Allies and Antagonists / Minions, Champions, стр. 91–92. Seed и агрегаты — технический контракт, не новое игровое правило.

## Следующий шаг

Подготовить отдельный контракт первого profiling-среза последовательных magic-пакетов: ограниченные workload inputs, counters/observations и исходные замеры для оценки необходимости process backend. ADR-0038 завершён; новый process, gameplay scope, метрику/подбор или CLI автоматически не добавлять.

## Последняя проверка

macOS arm64 / Python 3.12.15. 49 новых tests — OK: 40 unit (0,042 с), 9 integration/example (0,423 с). Полная регрессия: **3080 tests / 33 прежних errors (96,293 с)**; Counter полных error headers и exception signatures точно совпал с предыдущим полным audit log. Новых ошибок нет; полный suite не зелёный. Public two-file example из внешнего cwd и отдельного installed wheel без PYTHONPATH: stdout равен stored output, stderr пуст; все 410 установленных Python/Schema файлов равны src. Лог полного набора: /private/tmp/towr-adr0038-tests.log; build/install evidence — в [аудите](audits/m8-simulation-readiness.md).

```sh
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest discover -s tests -q
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m compileall -q src tests tools docs/examples/m8
git diff --check
```

## История

Compileall, границы импортов и public example imports, локальные Markdown-пути/входящие anchors и whitespace — OK. Оба архива содержат побайтно сохранённые исходные документы до вехи. Активный контекст сокращён без потери исторической evidence; прежние production/tests/tools не менялись.

[Полный прежний статус и команды проверок](project-status-history.md) и [закрытые вопросы/исторические boundaries](open-questions-history.md) сохранены целиком до текущей вехи. Архивы находятся на том же уровне docs, поэтому их относительные пути сохраняют смысл. Читать их при необходимости конкретной evidence, а не при каждом восстановлении контекста.

## Незакоммиченные файлы текущей вехи

На старте рабочее дерево было чистым; все 26 файлов ниже относятся к этой вехе. Commit/push не выполнялись.

```text
 M AGENTS.md
 M README.md
 M docs/README.md
 M docs/contradictions.md
 M docs/decisions/ADR-0038-independent-magic-simulations.md
 M docs/examples/m8/README.md
 M docs/open-questions.md
 M docs/project-status.md
 M docs/roadmap.md
 M docs/rule-traceability.md
 M docs/source-index.md
 M docs/testing.md
?? docs/audits/m8-simulation-readiness.md
?? docs/examples/m8/magic_simulation.output.txt
?? docs/examples/m8/magic_simulation.py
?? docs/open-questions-history.md
?? docs/project-status-history.md
?? src/towr/simulation/npc_magic_models.py
?? src/towr/simulation/npc_magic_simulation.py
?? src/towr/simulation/npc_magic_summary.py
?? src/towr/simulation/npc_magic_summary_models.py
?? tests/integration/test_m8_magic_simulation_example.py
?? tests/integration/test_m8_npc_magic_simulation.py
?? tests/unit/test_m8_npc_magic_simulation.py
?? tests/unit/test_m8_npc_magic_simulation_models.py
?? tests/unit/test_m8_npc_magic_summary.py
```
