# Текущий статус проекта

Дата обновления: 2026-10-28.

## Текущий этап

**M8: контракт JSON/CLI v1 подготовлен.** [ADR-0043](decisions/ADR-0043-magic-json-cli-v1.md) фиксирует отдельные simulation/balance families, полный fresh scenario/family mapper, strict versioned request/result/error, aggregate outputs и phase errors. [Полевая матрица и шесть JSON fixtures](examples/m8/json/README.md), [finite mapping probe](examples/m8/json_contract_probe.py) и subprocess test готовы. Production Schema/parser/encoder/commands/services/CLI ещё не реализованы.

Probe вручную отображает два известных входа в public typed APIs и обратно. Полные sequential/process results равны; simulation N4, balance C4/stages2/4 keep2/1, planned16/actual12 на backend. Есть13semantic constructor rejects и genuine generation failure counts(1,0) после успешного preflight. Saved rates/selection — наблюдение runtime, не preset/вероятность. Strict lexical/version/unknown/required fields и все enum/order варианты ещё требуют production tests.

Работа идёт до согласованной вехи небольшими шагами; независимые проверки делегируются с раздельным владением файлами. [Режим](../AGENTS.md#автономная-работа-до-согласованной-вехи). Commit/push выполняет пользователь. Все23исходно незакоммиченных пути сохранены; production и прежние tests/tools/examples/probes в этом срезе не менялись.

## Зафиксировано

| Слой | Готовность и граница |
| --- | --- |
| R1/K1 | PG1.4/GM1.1 — primary; [книги](audits/rulebooks-1.4-1.1.md), [ядро](audits/k1-readiness.md), [трассировка](rule-traceability.md); универсального боя/каталога нет |
| M2–M7 | Ограниченные numeric Minion ranged/melee/mixed encounters, sequential/process, assessment/stages/generation, JSON/CLI; [M5](audits/m5-external-readiness.md), [M6](audits/m6-external-readiness.md), [M7](audits/m7-external-readiness.md) |
| M8 encounter | Один authored Champion-Wizard/Curse и Shooting Minions с explicit facts/policies/frames; [аудит](audits/m8-encounter-readiness.md) |
| M8 simulation/process | Indexed fresh RNG, full-source records/summary, четыре outcomes/три totals, bounded spawn; [аудит](audits/m8-mass-simulation-readiness.md) |
| M8 performance | [Замеры](benchmarks/README.md#m8-sequential-и-spawn); локальное преимущество w2 для двух N1000 inputs, не auto backend |
| M8 bounded/staged | [ADR-0040 audit](audits/m8-evaluation-readiness.md), [ADR-0041 audit](audits/m8-staged-evaluation-readiness.md), public/installed examples |
| M8 generation | [ADR-0042 audit](audits/m8-generation-readiness.md), 41 implementation +3 example tests, late failures/installed parity |
| M8 JSON/CLI | Только контракт ADR-0043, матрица/fixtures/finite probe; production реализация начинается со simulation pure wire |

## Ограничения

- [Политика источников](source-policy.md): PG1.4/GM1.1 выше прототипа. В текущем срезе напрямую перечитаны PG1.4 Magic in the Old World / Casting / Interrupted Casting156, Potency/Miscasts157, Battle Magic / Curse162; GM1.1 Allies and Antagonists / Minions91. Другие ранее сверенные references сохранены в ADR-0042/0043. Новых игровых правил/house rules нет.
- Прежний magic scope: Curse, Broken Recover/Run, Stomach Blow → Drained expiry. Другие обязательные Wound/Miscast/chronology, ordinary Attack Give Ground, неизвестные scene/route дают exact unsupported stops. Broken/другая Zone не defeat; unsupported остаётся в N и исключает кандидата из continuation.
- Fresh-only wire не является сохранением произвольного текущего боя. Будущий encoder обязан reject неподдержанное state/history. External request ID, scenario ID и day ID независимы; definitions/roster/placements/activation/frames/routes/GM decisions сохраняют отдельные порядки.
- Полные повторные пакеты:10→100 оплачивает110, stages не независимы, prefix вычисляется заново. Intermediate eligible может продолжать вне окна, final selection требует window_match. Нельзя пропускать invalid generated subset или уменьшать заявленный C/budget после preflight.
- Нет PC/полных NPC/spell/Talent/item каталогов, универсальной тактики, auto facts/backend, prefix reuse/cache/persistent pool. [Открытые вопросы](open-questions.md) сохраняются. Source guards не доказывают происхождение manual aggregates, eligible/window_match — не гарантия полноты/истинной вероятности; budget не RSS cap.
- Cleanup ждёт running work; traceback может удерживать объекты, rollback/мгновенный kill не обещаются. Process caller требует importable main guard. JSON контракт не меняет RNG boundary/shared classes/шесть прежних команд.
- Installed проверка — CPython3.12.15/macOS arm64. Другие runtime/ОС/RSS не проверены; benchmarks не повторялись. Полный suite не зелёный:33 прежних dataclasses errors Python3.12 — [отдельная задача](open-questions.md#проверки-dataclasses-на-python-312).

## Следующий шаг

**Срез1 ADR-0043: simulation pure wire.** Реализовать три packaged simulation Schema/local registry, frozen MagicSimulationCommand с independent request_id/definition_order, shared scenario mapper/inverse, pure parser/summary encoder/input errors. Проверить strict lexical/required/unknown/nullable/version/uint64 boundaries, все field/enum/order mappings, обе стороны Wizard/perspective, fresh/spell/facts/frames/routes/archives/empty-live, round-trip/lossless refusal и exact source без RNG/runner/pool. Service, execution/error encoder и simulate-magic идут отдельным срезом2; balance — срезами3/4, затем общий аудит. Gameplay scope/roadmap не расширять.

## Последняя проверка

Новый subprocess test — **1 OK (2,035 с)**: four-file +six-fixture bundle из внешнего cwd, stored stdout/stderr parity и fixtures не меняются. Реальные sequential/process результаты сравниваются полностью; inputs/global RNG/children сохранены. Независимое read-only ревью ADR/fixtures/probe/public constructors/книг блокеров не выявило; сохранённые summaries/rates/status/catalog/totals согласованы с native моделями.

Installed reuse: все **423 Python/Schema files** равны текущему src и установленному пакету предыдущего audited wheel. Новый bundle без PYTHONPATH из external cwd прошёл реальный spawn, stdout совпал, fixtures неизменны; import path проверен из installed site. Fresh build не требовался: production не менялся. Wheel SHA-256 `b8a7a7bcf56edef488b2daab6b894e887a7ff50f5dfb4a071d16d416d2308f63`; report `/private/tmp/towr-m8-json-contract-installed-report.json`. Source/harness hash прежний `d4619ad9b4a7dda0464f2931161e95be3e3f5693a706af074ac38bd257afedd1`; performance не переизмерялся.

Полная регрессия: **3286 tests / 33 прежних errors (118,262 с)**. Точные Counters полных error headers/subtests и exception signatures равны предыдущим3285tests, новых ошибок нет. Лог `/private/tmp/towr-m8-json-contract-tests.log`. 32 frozen/slotted Aim .state и одна dataclasses.replace(init=False) — прежние Python3.12 assertions, полный suite не объявляется зелёным.

Файловые проверки: compileall, Markdown paths/selected anchors, import boundaries311core modules/purity5magic balance modules, SHA всех802исходных Python/JSON src/tests/tools и whitespace/diff. Подробный report `/private/tmp/towr-m8-json-contract-checks-report.json`.

```sh
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest tests.integration.test_m8_magic_json_contract_probe -v
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m compileall -q src tests tools docs/examples/m8/json_contract_probe.py
/private/tmp/towr-test-venv/bin/python /private/tmp/verify_m8_magic_json_installed.py
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python /private/tmp/check_m8_json_contract.py
git diff --check
```

Unix-команды отражают текущее окружение; portable запуск — [README](../README.md#локальная-проверка). Temporary evidence доступна только локально; воспроизводимые ADR/probe/test/fixtures находятся в репозитории.
