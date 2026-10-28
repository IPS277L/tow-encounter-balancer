# Текущий статус проекта

Дата обновления: 2026-10-28.

## Текущий этап

**M8: второй production срез ADR-0045 — one-roll Miscast — реализован.** [Контракт](decisions/ADR-0045-source-bound-unnatural-wind.md#реализованный-второй-срез) задаёт low-level Unnatural Wind21–22. Готовы explicit DECLINE/five facts, preparation с reset Casting progress, canonical bound RollRequest/Result, однократный existing K1 roll с внедряемым RNG и exact-source apply. Root хранит настоящий prepared либо rolled pending; actual dice/total/entry/effect request/Pool сохраняются до отдельного effect consumer. Rolled projection меняет только prefix, весь остальной owner неизменен.

[18 unit](../tests/unit/test_m8_npc_roster_miscast_roll.py) и [7 integration](../tests/integration/test_m8_npc_roster_miscast_roll.py) tests проверяют Wind21/22 и другие20/23/30, реальный fresh2d10, Casting/bound Recover/Run origins, archives/все histories, strict weak DTO/trace, Wind iffcanonical, stale/repeat/new-ID/replace/frozen, exact RNG count и частичный сбой без retry/partial state. Независимое read-only ревью core/root/diagnosis блокеров не выявило. Bound interruption fixtures не доказывают fresh runner reachability.

На старте было69незакоммиченныхпутей при HEAD `11ca95b M8 P14`. Прежняя работа сохранена: в этом срезе изменены5existing production modules (Miscast models/rules, root, diagnosis/enum), добавлены2test modules. Прежние tests/probes/JSON/CLI/runner не менялись; документация синхронизирована. Commit/push выполняет пользователь.

## Зафиксировано

| Слой | Готовность и граница |
| --- | --- |
| R1/K1 | PG1.4/GM1.1 — primary; [книги](audits/rulebooks-1.4-1.1.md), [ядро](audits/k1-readiness.md), [трассировка](rule-traceability.md); полного каталога/универсального боя нет |
| M2–M7 | Numeric Minion ranged/melee/mixed: encounters, sequential/process, assessment/stages/generation, JSON/CLI; [M5](audits/m5-external-readiness.md), [M6](audits/m6-external-readiness.md), [M7](audits/m7-external-readiness.md) |
| M8 encounter/simulation | Один authored Champion-Wizard/Curse и Shooting Minions, explicit scene/GM facts; [encounter](audits/m8-encounter-readiness.md), [mass simulation](audits/m8-mass-simulation-readiness.md). [Замеры](benchmarks/README.md#m8-sequential-и-spawn) не выбирают auto backend |
| M8 assessment/stages/generation | [ADR-0040](audits/m8-evaluation-readiness.md), [ADR-0041](audits/m8-staged-evaluation-readiness.md), [ADR-0042](audits/m8-generation-readiness.md) закрыты аудитами |
| M8 JSON/CLI | [ADR-0043](audits/m8-external-readiness.md) закрыт: simulation/balance wire/service/errors/CLI |
| Dead Champion exclusion | [ADR-0044](audits/m8-dead-champion-readiness.md): pure/journal/runner/propagation закрыты аудитом; installed parity442files относится к тому срезу |
| Unnatural Wind21–22 | [ADR-0045](decisions/ADR-0045-source-bound-unnatural-wind.md): preparation/one-roll/exact-source apply готовы; Wind application ещё впереди |

## Ограничения

- [Иерархия источников](source-policy.md): PG1.4/GM1.1 выше прототипа. Источники ADR-0045: PG1.4, гл.VIII Magic156–159 и гл.V Range114/Recover118/Prone123; GM1.1, гл.VII Minions91/Champions92. При реализации прямо перечитаны Miscasts157 и Miscast Table159. Новых Rule IDs/house rules/книжных ambiguities нет.
- Fresh runner по-прежнему останавливается на raw MISCAST_PREPARATION; decline автоматически не выбирается, новый result не входит в closed journal. Manual prepared state останавливается на MISCAST_ROLL, rolled — на MISCAST_EFFECT с canonical effect ID. Bound effect/Pool0 ещё не реализованы; [исторический probe](examples/m8/unnatural_wind_contract_probe.py) остаётся отдельной композицией existing K1 и ручной final projection.
- Required assertions: complete combat roster/no external Short creatures, unmounted/noimmunity/no cross-Zone Close. Они не доказывают полноту именованного NPC. Desperate cast, abandonment, другие effect consumers, mounts/Monstrosities/immunities и saved battle не подключаются. Prone END_TURN/ACTOR_INJURY/TARGET_INJURY и ranged/stand/Recover/Broken interplay ждут отдельного контракта.
- Existing Curse/Broken/Drained/dead-Champion consumers сохраняют прежние границы. Неизвестные scene/route facts и mandatory Wound/Miscast дают unsupported; trials остаются в N. Aggregate eligibility не доказывает полноту тактики или истинную вероятность сложности.
- Полные staged reruns, большие exact budgets/Fraction и отсутствие wall-time/RSS caps прежние. Нет universal engine/auto GM facts/backend/cache/persistent pool; process callers требуют importable main guard.
- CPython3.12.15/macOS arm64; другие runtime/ОС не проверялись.33прежние dataclasses assertions — [отдельный вопрос](open-questions.md#проверки-dataclasses-на-python-312), suite не зелёный. Wheel/installed parity нового среза пока не проверены; прежние442files не считаются current parity.

## Следующий шаг

**Третий срез ADR-0045: bound Wind request/result/pure consumer/apply.** Только canonical rolled Wind21–22; ordered live Short targets (caster первым, затем roster order) в рамках пяти подтверждённых facts. Через existing resolve_unnatural_wind применить actual Prone ко всем scoped targets, включая allies/already-Prone; outside/archive не затрагивать. Проверить полные source/injury/Condition/application metadata; только после всех applications — Pool0 и очистка prefix. Сохранить placements/round/оба child roster references/все histories. Deterministic tests обоих origins, archives/outside/already-Prone, other-row rejection, stale/replay/partial failure и прежних Prone END_TURN/ACTOR_INJURY/TARGET_INJURY stops. Automatic runner/journal/Prone adapters/JSON не добавлять. Затем общий low-level audit/public example/installed parity. [Последовательность](decisions/ADR-0045-source-bound-unnatural-wind.md#последовательность-реализации-и-проверки).

## Последняя проверка

25новых roll tests — OK (0,031с); вместе с25preparation tests —50OK (0,058с). Отдельные33preparation/K1 tests — OK (0,028с). Полная регрессия **3521tests/33прежнихerrors (160,449с)**. Точные Counters полных error headers/subtests/exception signatures равны предыдущим3496tests; новых ошибок нет, suite не зелёный.

Из911исходных Python/JSON906сохранены побайтно,5production modules изменены в рамках этого среза; добавлены2test modules. Compile7changed/new Python files, Markdown paths/selected anchors, import boundaries315core modules, whitespace/diff и HEAD preservation — OK. Source/harness hash `2b2b7dd0ea82a2a979093087542f70ec5dd49ab163a60f07ddaf7f9e452473a9`. Rebuild/installed/performance отложены до итогового аудита ADR-0045.

```sh
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest tests.unit.test_m8_npc_roster_miscast_roll tests.integration.test_m8_npc_roster_miscast_roll -v
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python /private/tmp/check_m8_miscast_roll.py
git diff --check
```

Логи `/private/tmp/towr-m8-miscast-roll-final-new-tests.log`, `/private/tmp/towr-m8-miscast-roll-agent-tests.log`, `/private/tmp/towr-m8-miscast-roll-tests.log`; snapshot `/private/tmp/towr-m8-miscast-roll-initial.json`, report `/private/tmp/towr-m8-miscast-roll-report.json`. Temporary evidence локальна; правила/ADR/tests достаточны для продолжения. Portable команды — [README](../README.md#локальная-проверка). Commit/push не выполнялись.
