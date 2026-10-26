# Текущий статус проекта

Дата обновления: 2026-10-27.

## Текущий этап

**M8: модели списка второго среза ADR-0040 реализованы.** [Magic evaluation models](../src/towr/balance/magic_evaluation_models.py) содержат frozen candidates/request/rows/result, полный preflight бюджета, derived simulation requests, полный aggregate report и stable Fraction ranking. [Pure assessment](../src/towr/balance/magic_assessment.py) готов; application service ещё не реализован.

[ADR-0040](decisions/ADR-0040-magic-candidate-assessment.md) сохраняет exact full source, все N в знаменателе, явное окно и unsupported guard. Контрактный [probe](examples/m8/assessment_contract_probe.py) остаётся исторической проверкой арифметики и existing simulation, не заменяет production guards моделей. Новые модели не исполняют RNG/runner/pool.

Работа до согласованной вехи идёт небольшими шагами без подтверждения между ними; независимые tests/review делегируются с раздельным владением файлами. [Режим](../AGENTS.md#автономная-работа-до-согласованной-вехи). Commit/push выполняет пользователь.

## Зафиксировано

| Слой | Готовность и граница |
| --- | --- |
| R1/K1 | PG1.4/GM1.1 — primary sources; [аудит книг](audits/rulebooks-1.4-1.1.md), [ядро](audits/k1-readiness.md), [трассировка](rule-traceability.md). Полного каталога и универсального боя нет |
| M2–M7 | Ограниченные stationary numeric Minion ranged/melee/mixed encounters, sequential/process, summary/assessment/stages/generation и JSON/CLI; [M5](audits/m5-external-readiness.md), [M6](audits/m6-external-readiness.md), [M7](audits/m7-external-readiness.md) |
| M8 single-run | Один authored Champion-Wizard/Curse и numeric Shooting Minions, explicit scene facts/policies, полный owner/journal; [аудит](audits/m8-encounter-readiness.md) |
| M8 simulation | ADR-0038/0039, typed request/records/result/summary, indexed fresh RNG, четыре outcomes/три totals и bounded spawn; [общий аудит](audits/m8-mass-simulation-readiness.md) |
| M8 performance | [Замеры](benchmarks/README.md#m8-sequential-и-spawn): N100 spawn медленнее, N1000 w2 локально быстрее двух боевых inputs в 1,506/1,547 раза; zero-action control быстрее sequential. Auto backend нет |
| M8 balance | Pure assessment и list models/preflight/report/ranking ADR-0040 готовы; service/errors/integration — следующий срез |

## Ограничения

- [Политика источников](source-policy.md): PG1.4/GM1.1 выше прототипа. Прямые книжные ссылки ADR-0040: PG1.4 Rules / Combat112, Conditions / Broken122, Magic in the Old World / Potency / Miscasts157, Battle Magic / Curse162, Wounds Table190–191; GM1.1 Allies and Antagonists / Minions / Champions91–92. Новых извлечений/правил в list-срезе нет; метрика/window/top_k — принятый продуктовый контракт M5–M7.
- Magic scope прежний: Curse, Broken Recover/Run и Stomach Blow → Drained expiry. Другие обязательные Wound/Miscast/chronology, обычный Attack Give Ground и неизвестные scene/route — явные unsupported stops. Их не фильтруют и не считают defeat/draw; Broken/другая Zone сами по себе не defeat.
- Полный NPC/spell/Talent/item catalogue, PC-сценарии и универсальная тактика/battle orchestration не готовы. [Открытые вопросы](open-questions.md) сохраняются; новых игровых неоднозначностей этот технический срез не выявил.
- List models проверяют input/report и ранжируют уже заданные агрегаты, но ещё не исполняют список. Ranking tests используют synthetic observations; ELIGIBLE не доказывает полноту сценария или истинную вероятность. Бюджет — число trials, не RSS quota.
- Staged/generation/JSON/CLI M8, новые consumers/cache/framework/persistent pool и auto backend не добавлены. Shared application options сохраняют workers1..61; прямой process API не меняется.
- Performance локален для прежних двух workloads и control на CPython3.12.15/macOS26.5.1 arm64. Другие workloads/runtime/ОС, память/RSS, workers/batch search и installed-wheel performance не измерены. Общий manifest меняется при добавлении balance modules; simulation/engine/tools неизменны, повторных замеров нет.
- 33 прежних dataclasses errors Python3.12 — отдельная задача; [подробности](open-questions.md#проверки-dataclasses-на-python-312). Полный suite не зелёный; новые ошибки сверяются отдельно.

## Следующий шаг

Реализовать третий срез ADR-0040: application/magic_evaluation_service.py и magic_evaluation_errors.py, evaluate_magic_candidates и MagicBalanceEvaluationError. Typed request/execution до runner; один полный existing sequential/process run на кандидата в исходном порядке, typed result/full source до summary, затем assessment/row. Освобождать full result до следующего runner; successful report aggregate-only. Ordinary candidate failures сохраняют ID/cause/worker notes без следующих кандидатов/partial/retry/fallback; preflight/final-constructor и BaseException проходят напрямую. Добавить deterministic unit и real-backend integration tests; default RNG остаётся на simulation boundary. Затем отдельный аудит/public production example; staged/generation/JSON/CLI и новые consumers не расширять.

## Последняя проверка

15 новых deterministic tests — OK (0,040 с). Проверены strict tuple/list/IDs/int и common-field guards, полный budget до исполнения и big product >uint64, rebuild derived requests, complete ordered source/window/report, Fraction ranking/ties/reorder/rename/large-N/empty selection, other-family rejection и immutable/pickle aggregate-only ownership. RNG/runner/pool не исполнялись. Независимое read-only ревью production/tests — блокеров нет.

Полная регрессия: **3190 tests / 33 прежних errors (99,608 с)**. Counter полных error headers и exception signatures точно совпал с предыдущим baseline; новых ошибок нет, полный suite не зелёный. Лог `/private/tmp/towr-m8-list-tests.log`. Compileall, 2956 локальных Markdown-путей, 68 anchors, границы импортов 311 modules, purity трёх balance modules и whitespace — OK.

Текущий source/harness hash `0ca9c7391e83006e90c9fb84ae05f2d29a2462f08e95bc0d11e4374c47e3716a` отличается от historical reports из-за новых balance modules. Simulation/engine/fixtures/tools и прежние Python sources не менялись; семь первоначальных Python/probe output файлов сохранены побайтно. Performance/installed wheel нового list API в этом срезе не проверялись.

```sh
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest tests.unit.test_m8_magic_evaluation -q
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest discover -s tests -q
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m compileall -q src tests tools docs/examples/m8
git diff --check
```

## История и изменения

[Архив статуса](project-status-history.md) и [история вопросов](open-questions-history.md) — исторические evidence, не текущая очередь. Прежние readiness reports — через [индекс](README.md), книги — [source-index](source-index.md).

На старте HEAD `9674d1f` (M8 P8) и 20 existing dirty/untracked файлов предыдущих контрактного и assessment-срезов; они учтены как исходные. Добавлены один production module и один test-файл, общие документы синхронизированы. Прежние Python-файлы и contract probe/output/test сохранены побайтно; commit/push не выполнялись. Всего 22 незакоммиченных файла, включая исходные 20. Точный diff — `git status --short`.
