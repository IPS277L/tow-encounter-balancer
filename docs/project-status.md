# Текущий статус проекта

Дата обновления: 2026-10-28.

## Текущий этап

**M8: контракт ADR-0046 и finite proof готовы; production opt-in/Prone integration ещё не реализована.** [ADR](decisions/ADR-0046-opt-in-miscast-runner-and-prone.md) задаёт optional explicit policy/None legacy, пять facts и self-stand-when-safe. Closed journal получает полный origin witness, scoped Prone adapters сохраняют actual injuries/usage/expiry, own Tests без общего Prone penalty и Shooting target−1d. Unsafe Broken+Prone, ongoing Wound causes и Run-after-spent-free-move остаются honest stops. Generation/wire opt-in отвергается явно, без policy loss.

[Finite probe](examples/m8/miscast_runner_contract_probe.py) / [stdout](examples/m8/miscast_runner_contract_probe.output.txt) использует existing public APIs:12scripted d10, current actual Wind/END_TURN, отдельные K1 stand/Recover/target modifier и full trace witness proof. K1 results остаются внешними, future full owner/opt-in/journal/resumed battle не имитируются. Независимые source/API/journal review блокеров не выявили; missing-frame/Broken stop priority закреплена явно. [Low-level ADR-0045](audits/m8-unnatural-wind-readiness.md) остаётся закрытым.

На старте22незакоммиченныхпути при HEAD `d774d23 M8 P15`; предыдущие изменения сохранены и не считаются новой работой. Добавлены ADR-0046, probe/stdout и1subprocess test, документация синхронизирована. Production/все прежние Python/JSON/tests/probes/CLI/runner не менялись. Commit/push выполняет пользователь.

## Зафиксировано

| Слой | Готовность и граница |
| --- | --- |
| R1/K1 | PG1.4/GM1.1 — primary; [книги](audits/rulebooks-1.4-1.1.md), [ядро](audits/k1-readiness.md), [трассировка](rule-traceability.md); полного каталога/универсального боя нет |
| M2–M7 | Numeric Minion ranged/melee/mixed: encounters, sequential/process, assessment/stages/generation, JSON/CLI; [M5](audits/m5-external-readiness.md), [M6](audits/m6-external-readiness.md), [M7](audits/m7-external-readiness.md) |
| M8 encounter/simulation | Один authored Champion-Wizard/Curse и Shooting Minions, explicit scene/GM facts; [encounter](audits/m8-encounter-readiness.md), [mass simulation](audits/m8-mass-simulation-readiness.md). [Замеры](benchmarks/README.md#m8-sequential-и-spawn) не выбирают auto backend |
| M8 assessment/stages/generation | [ADR-0040](audits/m8-evaluation-readiness.md), [ADR-0041](audits/m8-staged-evaluation-readiness.md), [ADR-0042](audits/m8-generation-readiness.md) закрыты аудитами |
| M8 JSON/CLI | [ADR-0043](audits/m8-external-readiness.md) закрыт: simulation/balance wire/service/errors/CLI |
| Dead Champion exclusion | [ADR-0044](audits/m8-dead-champion-readiness.md): pure/journal/runner/propagation закрыты аудитом; installed parity442files относится к тому срезу |
| Unnatural Wind21–22 | [ADR-0045](audits/m8-unnatural-wind-readiness.md): low-level consumer закрыт, public example/installed parity444files |
| Opt-in runner/Prone | [ADR-0046](decisions/ADR-0046-opt-in-miscast-runner-and-prone.md): contract/proof готовы; production впереди |

## Ограничения

- [Иерархия источников](source-policy.md): PG1.4/GM1.1 выше прототипа. Источники ADR-0045: PG1.4, гл.VIII Magic156–159 и гл.V Range114/Recover118/Prone123; GM1.1, гл.VII Minions91/Champions92. При реализации прямо перечитаны PG1.4 Miscasts157/Miscast Table159/Range114/Prone123 и GM1.1 Minions91/Champions92. Новых Rule IDs/house rules/книжных ambiguities нет.
- Fresh runner по-прежнему останавливается на raw MISCAST_PREPARATION; decline автоматически не выбирается, новый result не входит в closed journal. Manual prepared state останавливается на MISCAST_ROLL, rolled — на MISCAST_EFFECT с canonical effect ID. Bound Wind очищает Pool после actual applications, сохраняя Prone END_TURN stop; [исторический probe](examples/m8/unnatural_wind_contract_probe.py) остаётся отдельной композицией existing K1 и ручной final projection.
- Required assertions: complete combat roster/no external Short creatures, unmounted/noimmunity/no cross-Zone Close. Они не доказывают полноту именованного NPC. Desperate cast, abandonment, другие effect consumers, mounts/Monstrosities/immunities и saved battle не подключаются. Prone END_TURN/ACTOR_INJURY/TARGET_INJURY пока прежние; ADR-0046 планирует scoped adapters, не общий Broken/Recover dispatcher.
- Existing Curse/Broken/Drained/dead-Champion consumers сохраняют прежние границы. Неизвестные scene/route facts и mandatory Wound/Miscast дают unsupported; trials остаются в N. Aggregate eligibility не доказывает полноту тактики или истинную вероятность сложности.
- Полные staged reruns, большие exact budgets/Fraction и отсутствие wall-time/RSS caps прежние. Нет universal engine/auto GM facts/backend/cache/persistent pool; process callers требуют importable main guard.
- CPython3.12.15/macOS arm64; другие runtime/ОС не проверялись.33прежние dataclasses assertions — [отдельный вопрос](open-questions.md#проверки-dataclasses-на-python-312), suite не зелёный. Installed parity444files подтверждена; прежние442files относятся к ADR-0044.

## Следующий шаг

**Первый production срез ADR-0046: opt-in models/admission и защита от policy loss.** Добавить frozen NpcMagicPronePolicy/NpcMagicMiscastContinuationPolicy с required choice/five facts/prone policy; optional scenario.miscast_continuation=None в конце контракта. Проверить types/facts/contradictory cross-Zone CLOSE frames до RNG и точное legacy поведение None. Native generation family с opt-in отклонять в model preflight до enumeration/materialization; v1 encoder не должен молча терять policy. Детерминированные constructor/replace/None/source tests и docs. В этом срезе runner dispatch/Prone adapters/journal ещё не подключать; [последовательность](decisions/ADR-0046-opt-in-miscast-runner-and-prone.md#последовательность-реализации).

## Последняя проверка

**114focused tests — OK (0,324с)**:75existing M8 Miscast/Wind+38existing K1 stand/Recover/NPC preparation+1new probe. Полная регрессия **3548tests/33прежнихerrors (157,820с)**. Точные Counters полных error headers/subtests/exception signatures равны предыдущим3547tests; новых ошибок нет, suite не зелёный.

Все917исходных Python/JSON и production сохранены побайтно; добавлены2Python files (probe/test), stdout и ADR. Compile новых файлов, Markdown paths/selected anchors, import boundaries315core modules, whitespace/diff и HEAD preservation — OK. Source/harness hash прежний `5c2e50aafba116c13f6b1b6ffffc6eb819cc0a86cc90dea8bbcf53824587f52b`.

Повторно сверена byte parity444current source/wheel/site files. Новый two-file bundle прошёл из external cwd без PYTHONPATH/PYTHONHOME:12scripted d10, import paths подтверждены, stdout точный/stderr пустой. Reused wheel SHA-256 `a92370976f44c315118b1dca2615e7222b8daa2b41104ab642f646f2cf7f7d3e`; README metadata относится к предыдущему аудиту. Rebuild/CLI/performance не повторялись: production source прежний. Runtime/dependency versions — [аудит ADR-0045](audits/m8-unnatural-wind-readiness.md#установленный-пакет).

```sh
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest tests.unit.test_k1_free_move_prone_removal tests.unit.test_k1_recover_resolution tests.unit.test_k1_npc_attack_preparation tests.unit.test_m8_npc_roster_miscast_preparation tests.integration.test_m8_npc_roster_miscast_preparation tests.unit.test_m8_npc_roster_miscast_roll tests.integration.test_m8_npc_roster_miscast_roll tests.unit.test_m8_npc_roster_unnatural_wind tests.integration.test_m8_npc_roster_unnatural_wind tests.integration.test_m8_miscast_runner_contract_probe -v
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python /private/tmp/check_m8_prone_contract.py
git diff --check
```

Логи `/private/tmp/towr-m8-prone-contract-focused.log`, `/private/tmp/towr-m8-prone-contract-tests.log`; snapshot `/private/tmp/towr-m8-prone-contract-initial.json`, reports `/private/tmp/towr-m8-prone-contract-report.json`, `/private/tmp/towr-m8-prone-contract-installed-report.json`. Temporary evidence локальна; ADR/source/tests/probe достаточны для первого production среза. Portable команды — [README](../README.md#локальная-проверка). Commit/push не выполнялись.
