# Текущий статус проекта

Дата обновления: 2026-10-28.

## Текущий этап

**M8: simulation pure wire ADR-0043 реализован.** [Frozen command](../src/towr/application/magic_simulation_models.py), [общий mapper](../src/towr/adapters/_magic_scenario_json.py), [strict parser/summary encoder](../src/towr/adapters/magic_simulation_json.py), три packaged Schema, local registry и Magic input errors готовы. Service/execution errors/error encoder/CLI и balance wire ещё не реализованы.

Полный fresh source сохраняет независимые request/scenario/day IDs, definition/roster/placement/activation/scene orders, canonical spell, все facts/profiles/GM decisions/routes и archives/empty-live. Encoder сравнивает полный summary source и reconstruct-check command; нижние слои не менялись. Shared reader расширен только import/type union нового error family, все прежние function AST сохранены.

30 новых tests (28 unit +2 real-backend integration) проверяют strict admission, source/lossless/purity и sequential/spawn equality без Monte Carlo/winner assertions. [Матрица/примеры API](examples/m8/json/README.md), [ADR](decisions/ADR-0043-magic-json-cli-v1.md#реализованный-первый-срез). Работа идёт небольшими срезами до проверяемой вехи по [AGENTS.md](../AGENTS.md#автономная-работа-до-согласованной-вехи), с независимым review/tests. На старте дерево было чистым (`c229e97 M8 P12`); commit/push выполняет пользователь.

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
| M8 JSON/CLI | Simulation pure wire (срез1) готов; service/CLI (срез2), balance wire/execution (3/4) и общий аудит (5) следуют отдельно |

## Ограничения

- [Политика источников](source-policy.md): PG1.4/GM1.1 выше прототипа. В текущем срезе напрямую сверены PG1.4 Magic in the Old World / Casting / Interrupted Casting156, Potency/Miscasts157, Battle Magic / Curse162; GM1.1 Allies and Antagonists / Minions / Champions91–92. Другие ранее сверенные references сохранены в ADR-0042/0043. Новых игровых правил/house rules нет.
- Прежний magic scope: Curse, Broken Recover/Run, Stomach Blow → Drained expiry. Другие обязательные Wound/Miscast/chronology, ordinary Attack Give Ground, неизвестные scene/route дают exact unsupported stops. Broken/другая Zone не defeat; unsupported остаётся в N и исключает кандидата из continuation.
- Fresh-only wire не является сохранением произвольного текущего боя. Simulation encoder отклоняет неподдержанный source при lossless reconstruct-check. External request ID, scenario ID и day ID независимы; definitions/roster/placements/activation/frames/routes/GM decisions сохраняют отдельные порядки.
- Полные повторные пакеты:10→100 оплачивает110, stages не независимы, prefix вычисляется заново. Intermediate eligible может продолжать вне окна, final selection требует window_match. Нельзя пропускать invalid generated subset или уменьшать заявленный C/budget после preflight.
- Нет PC/полных NPC/spell/Talent/item каталогов, универсальной тактики, auto facts/backend, prefix reuse/cache/persistent pool. [Открытые вопросы](open-questions.md) сохраняются. Source guards не доказывают происхождение manual aggregates, eligible/window_match — не гарантия полноты/истинной вероятности; budget не RSS cap.
- Cleanup ждёт running work; traceback может удерживать объекты, rollback/мгновенный kill не обещаются. Process caller требует importable main guard. JSON контракт не меняет RNG boundary/shared classes/шесть прежних команд.
- Installed проверка — CPython3.12.15/macOS arm64. Другие runtime/ОС/RSS не проверены; benchmarks не повторялись. Полный suite не зелёный:33 прежних dataclasses errors Python3.12 — [отдельная задача](open-questions.md#проверки-dataclasses-на-python-312).

## Следующий шаг

**Срез2 ADR-0043: simulation execution/CLI.** Реализовать application execute_magic_simulation и MagicSimulationExecutionError с external request ID/cause/notes; dispatch existing sequential/process runner по прежним options, exact result/source до summary. Добавить error encoder и отдельную команду simulate-magic с existing UTF-8/I/O/exit0/2/3/4 boundary. Проверить все native outcomes как success, phase errors без raw cause/partial/retry/fallback, file/stdin/Unicode/usage/write/flush/closed streams, real spawn и installed module/console, регрессию шести прежних команд. Balance wire/execution идут срезами3/4, затем общий аудит. Gameplay scope/roadmap не расширять.

## Последняя проверка

**30 новых tests — OK**: 28 unit +2 integration, все прошли также в полной регрессии. Strict UTF-8/duplicate/nonfinite/float/exponent/version/required/unknown/nullable/type/uint64 и большие exact integers; независимые IDs/все orders, обе Wizard sides/perspectives, full canonical profiles/spell/facts/policies, Close/Short/Medium/Long/Extreme, three route fields/GM flags, archives/empty-live. Native четыре counts/три totals, same-ID foreign full source, UTF-8 lossless refusal, frozen/copy/pickle и запрет RNG/runner/pool при parse/encode проверены. Real sequential/spawn full results/summary одинаковы, global RNG/children сохранены. Независимое read-only ревью блокеров не выявило.

Offline wheel: все **431 Python/Schema files** совпали с src; из isolated extracted package (`-I`, external cwd, без PYTHONPATH) проверены import path, все3Schema и pure strict request/summary round-trip. Полный installed CLI audit относится к следующим срезам; новых команд пока нет. Build log `/private/tmp/towr-m8-simulation-wire-build.log`, report `/private/tmp/towr-m8-simulation-wire-wheel-report.json`.

Полная регрессия: **3316 tests / 33 прежних errors (118,879 с)**. Точные Counters полных error headers/subtests и exception signatures равны предыдущим3286tests, новых ошибок нет. Лог `/private/tmp/towr-m8-simulation-wire-tests.log`. 32 frozen/slotted Aim .state и одна dataclasses.replace(init=False) — прежние Python3.12 assertions; полный suite не объявляется зелёным.

Compileall, local Markdown paths/selected anchors, import boundaries311core modules и whitespace/diff — OK. Все **866 из867 исходных Python/JSON files** побайтно сохранены; единственное исключение — `_json_common.py` с прежним function AST. Все domain/engine/rules/simulation/balance, прежние tests/tools/examples/probes/fixtures неизменны. Source/harness hash теперь `d0755ccc5313aa5ddc100ae12dc2233a0aef595896b5a66d99ace0ce068e649b` вследствие нового wire слоя; performance не переизмерялся. Report `/private/tmp/towr-m8-simulation-wire-checks-report.json`.

```sh
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m compileall -q src tests tools
/private/tmp/towr-test-venv/bin/python /private/tmp/verify_m8_simulation_wire_wheel.py
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python /private/tmp/check_m8_simulation_wire.py --regression
git diff --check
```

Окружение: CPython3.12.15/macOS arm64. Portable команды — [README](../README.md#локальная-проверка). Temporary evidence доступна локально; воспроизводимые Schema/ADR/tests/examples находятся в репозитории.
