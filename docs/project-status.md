# Текущий статус проекта

Дата обновления: 2026-10-28.

## Текущий этап

**M8: simulation JSON/CLI ADR-0043 реализован (срезы1/2).** Готовы command/mapper/strict parser/native summary encoder/три Schema, [application service](../src/towr/application/magic_simulation_service.py), [execution error](../src/towr/application/magic_simulation_errors.py), [error encoder](../src/towr/adapters/magic_simulation_json.py) и `simulate-magic INPUT`. Balance wire/команда и общий аудит ещё впереди.

Service исполняет existing sequential/process runner с exact options/default indexed RNG и проверяет полный result/source до summary и полный summary/source после неё. Ошибка привязана к external command.request_id, Python cause/notes сохраняются; JSON/stderr содержат generic simulation_failed. Все native outcomes — success/exit0. CLI использует прежний byte I/O/exit0/2/3/4; encoder errors/BaseException проходят напрямую, partial output/retry/fallback отсутствуют.

38 новых tests (11 service +16 unit CLI/error +11 subprocess integration) проверяют source/dispatch/errors/I/O и real spawn. Вместе с30tests первого среза —68. [Формат/API/CLI примеры](examples/m8/json/README.md), [ADR](decisions/ADR-0043-magic-json-cli-v1.md#реализованный-второй-срез). На старте дерево было чистым (`84d0374 M8 P13`); работа небольшими срезами с независимыми tests/review по [AGENTS.md](../AGENTS.md#автономная-работа-до-согласованной-вехи). Commit/push выполняет пользователь.

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
| M8 JSON/CLI | Simulation wire/service/error encoder/CLI (срезы1/2) готовы; balance wire/execution (3/4) и общий аудит (5) следуют отдельно |

## Ограничения

- [Политика источников](source-policy.md): PG1.4/GM1.1 выше прототипа. В текущем срезе напрямую сверены PG1.4 Magic in the Old World / Potency / Miscasts157, Battle Magic / Curse162; GM1.1 Allies and Antagonists / Minions / Champions91–92. Прежний Casting/Interrupted Casting reference156 сохраняется. Другие ранее сверенные references сохранены в ADR-0042/0043. Новых игровых правил/house rules нет.
- Прежний magic scope: Curse, Broken Recover/Run, Stomach Blow → Drained expiry. Другие обязательные Wound/Miscast/chronology, ordinary Attack Give Ground, неизвестные scene/route дают exact unsupported stops. Broken/другая Zone не defeat; unsupported остаётся в N и исключает кандидата из continuation.
- Fresh-only wire не является сохранением произвольного текущего боя. Simulation encoder отклоняет неподдержанный source при lossless reconstruct-check. External request ID, scenario ID и day ID независимы; definitions/roster/placements/activation/frames/routes/GM decisions сохраняют отдельные порядки.
- Полные повторные пакеты:10→100 оплачивает110, stages не независимы, prefix вычисляется заново. Intermediate eligible может продолжать вне окна, final selection требует window_match. Нельзя пропускать invalid generated subset или уменьшать заявленный C/budget после preflight.
- Нет PC/полных NPC/spell/Talent/item каталогов, универсальной тактики, auto facts/backend, prefix reuse/cache/persistent pool. [Открытые вопросы](open-questions.md) сохраняются. Source guards не доказывают происхождение manual aggregates, eligible/window_match — не гарантия полноты/истинной вероятности; budget не RSS cap.
- Cleanup ждёт running work; traceback может удерживать объекты, rollback/мгновенный kill не обещаются. Process caller требует importable main guard. JSON контракт не меняет RNG boundary/shared classes/шесть прежних команд.
- Installed проверка — CPython3.12.15/macOS arm64. Другие runtime/ОС/RSS не проверены; benchmarks не повторялись. Полный suite не зелёный:33 прежних dataclasses errors Python3.12 — [отдельная задача](open-questions.md#проверки-dataclasses-на-python-312).

## Следующий шаг

**Срез3 ADR-0043: balance pure wire.** Реализовать три packaged balance Schema/local registry, frozen MagicBalanceCommand(request_id,generation_request,execution,definition_order) и MagicBalanceResult(generation_result,evaluation_result), pure parser/result encoder с готовым shared scenario mapper. Проверить independent IDs/orders, separate exact family facts/frames, groups без Wizard/обе perspective, C/caps/полный staged budget/все stages, Fraction normalization, полный source chain и catalog без ID parsing, early/final/unsupported semantics. Parse/encode не запускают generation service/RNG/runner/pool. Balance service/errors/error encoder/CLI — отдельный срез4; затем общий аудит5. Gameplay scope/roadmap не расширять.

## Последняя проверка

**38 новых tests — OK**:11service unit (0,104с) и27CLI/error unit/integration (12,749с); два усиленных существующих случая отдельно0,406с. Все38 прошли и в полной регрессии. Exact dispatch/default RNG/options, full same-ID foreign result/summary/source, all native outcomes success, externalID/cause/notes/BaseException, late real trial failure/no-next/partial/fallback и input/global RNG/children guards проверены. CLI покрывает file/stdin/Unicode, malformed/version/admission, pool failure, usage/read/write/flush/closed Python streams/pipes, typed encoder errors direct и все7error families. Независимое read-only ревью блокеров не выявило.

Fresh offline wheel установлен в отдельный venv; все **433 Python/Schema files** равны src/wheel/installed site. Schema dependencies скопированы offline из проверочного окружения (versions в report); package import paths проверены. Без PYTHONPATH из external cwd прошли installed module (`-I -m towr`) и console entrypoint, sequential/process полное wire/summary parity, relative file/Unicode stdin/input/I/O exits, late failure после первого real trial и все6прежних commands success/error families. Report `/private/tmp/towr-m8-simulation-cli-installed-report.json`; wheel SHA-256 `3ff5665bf6c1271e1d68b6d82ebe80cc22ec79297f3e8aa4b8860d195508a20c`. Совместный magic simulation/balance audit остаётся срезом5.

Полная регрессия: **3354 tests / 33 прежних errors (135,207 с)**. Точные Counters полных error headers/subtests/exception signatures равны предыдущим3316tests, новых ошибок нет. Лог `/private/tmp/towr-m8-simulation-cli-tests.log`. 32 frozen/slotted Aim .state и одна dataclasses.replace(init=False) — прежние Python3.12 assertions; полный suite не объявляется зелёным.

Compileall, local Markdown paths/selected anchors, import boundaries311core modules и whitespace/diff — OK. Все **875 из877 исходных Python/JSON files** сохранены; исключения cli.py (новый route/diagnostic code) и magic_simulation_json.py (новый error encoder/import). Все прежние pure adapter functions,6dispatch paths, read/write byte I/O и stream helper AST равны HEAD. Domain/engine/rules/simulation/balance, прежние tests/tools/examples/probes/fixtures неизменны. Source/harness hash `0c5800b5c686206a8c9e545427effc0f3097bc3868e177cb08275635ddbfd7aa`; новый внешний слой не является performance-замером. Report `/private/tmp/towr-m8-simulation-cli-checks-report.json`.

```sh
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m compileall -q src tests tools
/private/tmp/towr-test-venv/bin/python /private/tmp/verify_m8_simulation_cli_installed.py
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python /private/tmp/check_m8_simulation_cli.py --regression
git diff --check
```

Окружение: CPython3.12.15/macOS arm64. Portable команды — [README](../README.md#локальная-проверка). Temporary evidence доступна локально; воспроизводимые Schema/ADR/tests/examples находятся в репозитории.
