# Текущий статус проекта

Дата обновления: 2026-10-27.

## Текущий этап

**M8: контракт staged evaluation ADR-0041 и synthetic probe подготовлены.** [ADR](decisions/ADR-0041-staged-magic-evaluation.md) фиксирует full reruns, общий верхний budget, outside-window continuation против final selection, strict typed models, exact stage source/report chain и stage/candidate errors. **Production staged helper/models/service ещё не реализованы.**

[Probe](examples/m8/staged_contract_probe.py) собирает синтетические агрегаты через existing bounded models, проверяет конечную арифметику и не исполняет бой/RNG/pool. Прежний [bounded evaluator ADR-0040](audits/m8-evaluation-readiness.md) и его public example/installed audit остаются готовы; runtime код в текущем срезе не менялся.

Работа до согласованной вехи идёт небольшими шагами без подтверждения между ними; независимые probe/tests/review делегируются с раздельным владением файлами. [Режим](../AGENTS.md#автономная-работа-до-согласованной-вехи). Commit/push выполняет пользователь.

## Зафиксировано

| Слой | Готовность и граница |
| --- | --- |
| R1/K1 | PG1.4/GM1.1 — primary sources; [аудит книг](audits/rulebooks-1.4-1.1.md), [ядро](audits/k1-readiness.md), [трассировка](rule-traceability.md). Полного каталога и универсального боя нет |
| M2–M7 | Ограниченные numeric Minion ranged/melee/mixed encounters, sequential/process, summary/assessment/stages/generation и JSON/CLI; [M5](audits/m5-external-readiness.md), [M6](audits/m6-external-readiness.md), [M7](audits/m7-external-readiness.md) |
| M8 single-run | Один authored Champion-Wizard/Curse и numeric Shooting Minions, explicit scene facts/policies, полный owner/journal; [аудит](audits/m8-encounter-readiness.md) |
| M8 simulation | ADR-0038/0039, indexed fresh RNG, full-source records/summary, четыре outcomes/три totals и bounded spawn; [общий аудит](audits/m8-mass-simulation-readiness.md) |
| M8 performance | [Замеры](benchmarks/README.md#m8-sequential-и-spawn): N100 spawn медленнее, N1000 w2 локально быстрее двух боевых inputs в 1,506/1,547 раза; control быстрее sequential. Auto backend нет |
| M8 bounded evaluation | [ADR-0040](decisions/ADR-0040-magic-candidate-assessment.md): assessment/list/service/error закрыты общим аудитом, public example и installed parity |
| M8 staged contract | ADR-0041/probe готовы; pure helper/models, service и их аудит — последующие срезы |

## Ограничения

- [Политика источников](source-policy.md): PG1.4/GM1.1 выше прототипа. Для ADR-0041 прямо сверены PG1.4 Combat112, Broken122, Casting156, Potency/Miscasts157, Curse162, Wounds190–191 и GM1.1 Minions/Champions91–92; главы/выводы — в ADR. Новых Rule IDs/house rules нет, стадии/окно/бюджет/ranking — технический контракт по образцу M7.
- Magic scope прежний: Curse, Broken Recover/Run и Stomach Blow → Drained expiry. Остальные обязательные Wound/Miscast/chronology, обычный Attack Give Ground и неизвестные scene/route — unsupported stops. Их не фильтруют и не считают defeat/draw; Broken/другая Zone сами по себе не defeat.
- Synthetic probe не реализует staged admission/chain/error guards и не доказывает достижимость observations. Переход 10→100 оплачивает 110 full rerun trials; stages не независимы, prefix вычисляется заново. Intermediate ELIGIBLE вне окна может продолжать, но финал требует window_match=True. Любой unsupported исключает целого кандидата из следующих этапов, сохраняя все N текущего report.
- Полные NPC/spell/Talent/item каталоги, PC-сценарии и универсальная тактика/battle orchestration не готовы. [Открытые вопросы](open-questions.md) сохраняются. ELIGIBLE/window_match не доказывают полноту тактики или истинную вероятность; budget не RSS quota.
- Generation/JSON/CLI M8, prefix reuse, confidence presets, новые consumers/cache/framework/persistent pool и auto backend не добавлены. Shared class paths/options и simulation RNG boundary прежние; stages не добавляются в seed encoding.
- Performance локален для прежних workloads/runtime. Новых замеров/installed-wheel performance нет. Runtime package соответствует предыдущему wheel, но его README metadata исторический; для нового probe wheel не пересобирался.
- 33 прежних dataclasses errors Python3.12 — отдельная задача; [причина](open-questions.md#проверки-dataclasses-на-python-312). Полный suite не зелёный; новые ошибки сверяются отдельно.

## Следующий шаг

Реализовать первый срез ADR-0041: balance/magic_staged_evaluation.py (magic_continuation_candidate_ids) и magic_staged_evaluation_models.py (MagicBalanceStage, MagicStagedEvaluationRequest/Result/Status) с общей private _stage_request. Strict tuple/list/int/type guards, полный upper budget, строго возрастающий N и положительный keep (он может меняться в обе стороны), полный input и exact report chain, early-exhaust/final-empty semantics, derived fields и aggregate-only ownership. Добавить deterministic tests без runner/RNG/pool. Затем отдельно application service/error и real-backend integration, далее аудит/public production example. Generation/prefix reuse/JSON/CLI и новые consumers не расширять автоматически.

## Последняя проверка

Root synthetic probe и external-cwd three-file bundle дают stored stdout/empty stderr; новый subprocess test — **1 OK (0,259 с)**. Проверены continuation/final selection/order/ties/point windows/all-limit/all-unsupported/zero-action, budgets240/140/40/2240 против excluded incremental220, large Fraction и seed prefix. Inputs/global RNG/children сохранены; battles не запускались.

Тот же probe вне repo без PYTHONPATH прошёл на прежнем installed wheel обычным и guarded запуском (RNG/runner/evaluator/pool calls запрещены). Все 416 Python/Schema files равны src/wheel/installed package. Evidence `/private/tmp/towr-m8-staged-contract-installed-report.json`; fresh build не требовался, runtime unchanged. Независимое read-only ревью источников/контракта/probe — блокеров нет.

Полная регрессия: **3205 tests / 33 прежних errors (101,004 с)**. Counter полных error headers/signatures точно равен предыдущему baseline; новых ошибок нет, полный suite не зелёный. Compileall, 3040 локальных Markdown-путей, 77 anchors, public imports и whitespace — OK. Лог `/private/tmp/towr-m8-staged-contract-tests.log`. Current source/harness manifest 401 files / `ac055c19711c8d2f124931f3b07c3ff7dbadeb51829bf785544980cbaebb0ec1` не менялся; benchmark не повторялся. Прежние Python-файлы и source boundaries сохраняются побайтно.

```sh
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest tests.integration.test_m8_magic_staged_contract_probe -q
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest discover -s tests -q
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m compileall -q src tests tools docs/examples/m8
git diff --check
```

## История и изменения

[Архив статуса](project-status-history.md) и [история вопросов](open-questions-history.md) — исторические evidence, не текущая очередь. Прежние readiness reports — через [индекс](README.md), книги — [source-index](source-index.md).

На старте HEAD c8f1f84 (M8 P9) и 21 existing dirty/untracked файл предыдущих срезов. Они учтены как исходные; runtime/examples/tests/output сохраняются побайтно, общая документация синхронизирована. Добавлены ADR-0041, synthetic probe/output и один subprocess test. Commit/push не выполнялись. Всего 25 незакоммиченных файлов, включая исходные 21; новые пути этого среза — ADR-0041, probe/output и один test. Точный diff — `git status --short`.
