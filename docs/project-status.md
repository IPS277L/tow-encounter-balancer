# Текущий статус проекта

Дата обновления: 2026-10-27.

## Текущий этап

**M8: первый production-срез генерации ADR-0042 реализован.** [Frozen group/request](../src/towr/application/magic_candidate_generation_models.py) проверяют typed reserve/partition без Wizard, full definitions, explicit family facts/ordered frames, все stages/seed/window и арифметические C/budget caps до enumeration/materialization. [15 tests](../tests/unit/test_m8_magic_candidate_generation_models.py) подтверждают guards, обе perspective, immutable sources и огромный C без исполнения.

[ADR-0042](decisions/ADR-0042-magic-composition-generation.md) и [finite probe](examples/m8/generation_contract_probe.py) сохраняются. Group/request не обещает допустимость каждого subset; construction/result/error/полная проекция и integration ещё не реализованы. Прежние staged/bounded/simulation APIs и single-run scope не менялись.

Работа до согласованной вехи идёт небольшими шагами без подтверждения между ними; независимые tests/review делегируются с раздельным владением файлами. [Режим](../AGENTS.md#автономная-работа-до-согласованной-вехи). Commit/push выполняет пользователь.

## Зафиксировано

| Слой | Готовность и граница |
| --- | --- |
| R1/K1 | PG1.4/GM1.1 — primary sources; [аудит книг](audits/rulebooks-1.4-1.1.md), [ядро](audits/k1-readiness.md), [трассировка](rule-traceability.md). Полного каталога и универсального боя нет |
| M2–M7 | Ограниченные numeric Minion ranged/melee/mixed encounters, sequential/process, summary/assessment/stages/generation и JSON/CLI; [M5](audits/m5-external-readiness.md), [M6](audits/m6-external-readiness.md), [M7](audits/m7-external-readiness.md) |
| M8 single-run | Один authored Champion-Wizard/Curse и numeric Shooting Minions, explicit scene facts/policies, полный owner/journal; [аудит](audits/m8-encounter-readiness.md) |
| M8 simulation | ADR-0038/0039, indexed fresh RNG, full-source records/summary, четыре outcomes/три totals и bounded spawn; [общий аудит](audits/m8-mass-simulation-readiness.md) |
| M8 performance | [Замеры](benchmarks/README.md#m8-sequential-и-spawn): N100 spawn медленнее, N1000 w2 локально быстрее двух боевых inputs в 1,506/1,547 раза; control быстрее sequential. Auto backend нет |
| M8 bounded evaluation | [ADR-0040](decisions/ADR-0040-magic-candidate-assessment.md) закрыт общим аудитом, public example и installed parity |
| M8 staged evaluation | [Аудит ADR-0041](audits/m8-staged-evaluation-readiness.md) завершён: 33 implementation + 2 example tests, public example, late failure и installed parity |
| M8 generation | ADR-0042/finite probe и frozen group/request готовы; construction/result/error — следующий срез |

## Ограничения

- [Политика источников](source-policy.md): PG1.4/GM1.1 выше прототипа. Прямые references ADR-0042: PG1.4 Equipment94, Combat112, Range/Speed114–115, Giving Ground119, Broken122, Casting156, Potency/Miscasts157, Curse162, Wounds190–191; GM1.1 Minions/Champions91–92; главы/выводы — в ADR. Контракт генерации не добавляет игровых правил или house rules; книжные ссылки сверены напрямую.
- Magic scope прежний: Curse, Broken Recover/Run и Stomach Blow → Drained expiry. Другие обязательные Wound/Miscast/chronology, обычный Attack Give Ground и неизвестные scene/route — unsupported stops; их не фильтруют и не считают defeat/draw. Broken/другая Zone не defeat.
- Переход 10→100 оплачивает 110 trials, stages не независимы, prefix вычисляется заново. N строго растёт; keep может расти/убывать без возвращения отсеянных. Intermediate ELIGIBLE вне окна может продолжать, финал требует window_match=True. Любой unsupported исключает целого кандидата из следующих этапов, но сохраняется в N текущего report.
- Полные NPC/spell/Talent/item каталоги, PC-сценарии и универсальная тактика/battle orchestration не готовы. [Открытые вопросы](open-questions.md) сохраняются. Source guards не доказывают происхождение manual aggregates, ELIGIBLE/window_match — не гарантия полноты или истинной вероятности; budget не RSS cap.
- Materialization generation/JSON/CLI M8, prefix reuse, confidence presets, новые consumers/cache/framework/persistent pool и auto backend не добавлены. Shared classes/options и simulation RNG boundary прежние. Process caller использует importable main guard; default RNG не становится новым параметром staged service.
- Cleanup ждёт running work; traceback может удерживать объекты, rollback side effects/мгновенный kill не обещаются. Успешный result содержит inputs/aggregate reports без trial records/journals.
- Общий src/harness hash меняется при добавлении application modules; simulation/engine/tools неизменны, новых performance-замеров нет. Прежний installed wheel staged API проверен на CPython3.12.15/macOS arm64; новый generation models API, другие runtime/ОС/RSS в этом срезе не проверены.
- 33 прежних dataclasses errors Python3.12 — отдельная задача; [причина](open-questions.md#проверки-dataclasses-на-python-312). Полный suite не зелёный; новые ошибки сверяются отдельно.

## Следующий шаг

Реализовать второй срез ADR-0042: application/magic_candidate_generation.py, MagicCandidateGenerationResult в models и magic_candidate_generation_errors.py. Ordered count vectors/IDs; full fresh roster/round/spatial/Champion daily с прежним Wizard/caster/day_id; полные projections policies/objective/всех supplied scene frames/route entities. Equal-key collapse только при полном равенстве, conflict и invalid Broken route прерывают всё семейство; каждый subset проходит existing admission. Общая внутренняя projection function для construction/result guards, exact source, error ID/counts/cause/notes без skip/partial/retry; BaseException/final constructors напрямую. Deterministic tests; integration/public production example/аудит затем, без новых gameplay consumers/JSON/CLI/prefix reuse.

## Последняя проверка

15 новых tests — **OK (0,024 с)**: strict types/containers, четыре Wizard-side/perspective сочетания, exact partition/full definitions/family frames, budgets240/250/110/1140/4×uint64max, все stages/seed/caps, frozen/replace/pickle и источники. C=2**40−1 проверен без enumeration/candidate/staged/projection/RNG/runner/pool с одной seed admission. Будущий invalid Broken subset не проецируется при preflight. Независимое read-only ревью production/tests блокеров не выявило.

Полная регрессия: **3256 tests / 33 прежних errors (105,847 с)**. Точные Counters полных error headers/subtests и exception signatures равны предыдущему прогону 3241 tests, новых ошибок нет. 32 прежние frozen/slotted Aim .state и одна dataclasses.replace(init=False) на Python3.12 остаются отдельной задачей; полный suite не зелёный. Лог `/private/tmp/towr-m8-generation-models-tests.log`. Новый source/harness hash `8db7068c27e521d8fec8959bf7198ccd563bbd42fd90c81d856ac75181e818b4` изменился только из-за нового application module; simulation/engine/tools прежние, новых performance-измерений нет. Installed API нового файла в этом срезе не проверялся.

Файловые проверки — OK: compileall, 3144 локальных Markdown-пути/83 anchors, import boundaries 311 core modules, purity пяти magic balance modules и imports нового preflight module, SHA всех 794 исходных Python/JSON файлов src/tests/tools, whitespace. Прежние probe/output/test сохранены побайтно.

```sh
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest tests.unit.test_m8_magic_candidate_generation_models -q
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest discover -s tests -q
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m compileall -q src tests tools docs/examples/m8
git diff --check
```

## История и изменения

[Архив статуса](project-status-history.md) и [история вопросов](open-questions-history.md) — исторические evidence, не текущая очередь. Прежние readiness reports — через [индекс](README.md), книги — [source-index](source-index.md).

На старте HEAD a422d25 (M8 P10) и 28 dirty/untracked файлов прежних срезов. Исходные src/tests/tools сохранены побайтно; добавлены generation models и один файл с 15 tests, общие документы синхронизированы. Всего 30 dirty/untracked файлов, включая 28 исходных. Commit/push не выполнялись; точный diff — git status --short.
