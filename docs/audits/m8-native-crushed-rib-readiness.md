# Native Crushed Rib: приёмка ADR-0057

Дата: 2026-11-02. Статус: **ADR-0057 закрыт в принятой native границе**. [Контракт57](../decisions/ADR-0057-native-crushed-rib-continuation.md), [предыдущий bridge56](m8-crushed-rib-owner-readiness.md). Один полный актуальный run завершён;33прежние errors учитываются отдельно, набор не объявляется зелёным.

## Реализация и граница

[Scenario](../../src/towr/domain/npc_magic_scenario_models.py) получает последнее nullable `crushed_rib_continuation` с enum `NpcMagicCrushedRibPolicy.NEXT_TEST_WITH_JOURNAL_WITNESSES`. Permission независимо от Miscast/stationary; repeated→stationary остаётся:12valid/4invalid сочетания. Shared parent/worker native admission проверяет original facts и четыре permissions до RNG/equality. Старые positional Scenario constructors сохранены; два прежних metadata assertions обновлены на tail4. GenerationRequest сохраняет tail3: новой family permission нет.

[NpcMagicCrushedRibHistory](../../src/towr/domain/npc_magic_crushed_rib_policy.py) frozen/slots и содержит только current state и первый consuming witness. Initial helper использует `initial_runtime_state`. Advance проверяет exact source, получает receipt из actual outer result и никогда не очищает/заменяет первый witness; повторный расход отклоняется. История допускает pending, новые unsupported injuries и dead owner без глобального Context56 gate. Узкий helper строит контекст только для совместимого Wizard action/target/end-turn; known other actor даёт None, damaged source/history — error. Spent canonical10 без consumption history не становится разрешённым fallback.

[Runner](../../src/towr/engine/npc_magic_scenario_runner.py), [journal policy](../../src/towr/domain/npc_magic_journal_policy.py) и [Result/diagnosis](../../src/towr/domain/npc_magic_scenario_result_models.py) выводят историю из собственного непрерывного prefix. Standalone cursor не объявляется journal proof; полные consuming parent/receipt/trace сравниваются с recorded result, а не только ID/final owner. Старый manual56 journal без отдельного permission теперь отвергается. Удаление upper marker, чужой equal-current/different-trace witness и обход через Broken/Prone consumers не проходят validation.

Existing Step union и battle root не расширены. Runner передаёт derived56 context в actual Casting/Shooting factories и Wizard end-turn. Mandatory Miscast, Wound-effect, movement/Willpower, Minion defeat и immediate lethal exclusion сохраняют порядок. История обновляется после policy validation и до публикации следующего шага. Ближайшая реальная Protection до своего Casting расходует effect один раз; провал/нулевые successes этого не отменяют. После consuming Casting сохраняется actual pending receipt; completion не повторяет Casting Test и выполняет normal target Willpower. Новые раны/Wind сначала регистрируются либо останавливаются своим существующим consumer, затем ограничивается следующий context.

Native sequential/process, explicit-list/staged evaluation сохраняют full source, общий seed prefix/round budget и denominator. Direct runner хранит journal, массовые trials — compact records/aggregate. Parent preflight отвергает испорченные facts/policies до worker/RNG. [Generation gate](../../src/towr/application/magic_candidate_generation_models.py) отказывает nonNone57 в permissions-only admission до enumeration/projection; arithmetic/full-source boundaries прежние. [Wire gate](../../src/towr/adapters/_magic_scenario_json.py) отказывает valid nonNone57 для всех JSON1–4 до silent loss; raw enum отвергается как invalid source, новое поле даже null запрещено closed decoder schemas. None сохраняет прежнюю wire projection.42schemas/444refs не расширяются; wire5/CLI flags не добавлены.

Scope ровно56: одна canonical resolved/untreated/unhealed rolled10, optional prior superficial1–3 и только Drained. Несколько10,9/6/Wind coexistence, treatment/Fate/Lucky/Talents/Recover/другие Wizard Tests не добавлены. При новой Wound обязательные последствия полностью сохраняются, а узкий следующий context прекращается. Книга прежняя: BOOK-PLAYER-GUIDE1.4 Rules108/Attack Tests118/Drained123, Casting156–157, Wounds190; BOOK-GM-GUIDE1.1 Champions92. Новые страницы/PDF не читались, новые Rule IDs/house rules не вводились.

## Детерминированные проверки

- [17 pure policy tests](../../tests/unit/test_m8_native_crushed_rib_policy.py): permission12/4, fresh runtime/current, first full witness, pending/Miscast/dead storage, reset/overwrite/refusal, original aliases и forbidden Broken/Prone paths.
- [5 journal tests](../../tests/unit/test_m8_native_crushed_rib_journal.py): full Result membership до EOF, None manual gap, stripped upper context, first consumption→new4 pending, unchanged48d10 stationary journals при дополнительном permission.
- [11 native integrations](../../tests/integration/test_m8_native_crushed_rib.py): actual Casting/Protection first, subsequent normal Tests, pending/death/movement/Wind boundaries, equal-current foreign actual receipt, native sequential/spawn/explicit-list/staged source/seed/denominator.
- [8 gen/wire refusal tests](../../tests/integration/test_m8_crushed_rib_native_refusals.py) и old huge-arithmetic case: ранние отказы до materialization/workers, обе families1–4, unknown key/null и None compatibility.104прежних Scenario/runner/Result/Miscast/stationary/repeated checks пройдены отдельно.

Новые targeted группы проверены по шагам; agent pure17 включает focused rerun исправленного fixture, native11 также набраны из последовательных запусков после добавления cases. Это не выдаётся за единый полный regression. Независимое read-only review runner/gates/public example блокеров не оставило; найденный manual Broken/Prone fallback закрыт до финальной фиксации production.

[Actual274d10](../examples/m8/crushed_rib_native.py), [stdout](../examples/m8/crushed_rib_native.output.txt), [copied test](../../tests/integration/test_m8_crushed_rib_native_example.py).184direct d10: Casting32, Protection29, два None7, new4 pending16, Miscast pending10, actual movement22, death61. Ещё45seq+45real-spawn: limit и unsupported не исключаются из denominator2; source/seed/records/summary совпадают. Worker PID проверяется без нестабильных PID в stdout; source/global RNG/children неизменны. Copied test **1OK/17,072с**; added movement integration **1OK/1,663с**.

[Исторический59d10 proof](../examples/m8/crushed_rib_native_contract_probe.py) обновлён на actual None-policy refusal вместо прежнего ошибочного journal admission; RNG-счётчик и manual membership oracle сохранены. Его copied test прошёл после обновления; standalone56 compatibility корректно отделяется от native membership. Новая реализация не оставляет требование воспроизводить исправленный bypass.

## Установленный пакет

Новый [audit helper](../../tools/audit_crushed_rib_native_install.py) проверяет source/wheel/installed py/json paths+SHA, site paths native modules, enum/append-last Scenario и2field history,42schemas/444offline refs. Native M8 типы импортируются из своих модулей, как прежние policies; root `towr.domain.__all__` не меняется.

Installed audit прошёл:478source/wheel/site py/json paths+SHA,3native module site paths, enum/append-last field и2field history,42schemas/444refs. Bundle9Python files: native274, native-contract59, owner63, owner-contract25, K1actual33, K1contract40 и3fixtures. Все12source/installed child commands из внешнего cwd дали exact saved stdout; native274 выполнил настоящий spawn. Source/copied hashes прежние, PDF/private references в wheel отсутствуют, working `.venv` не менялась.

Evidence `.cache/adr0057-installed-audit/checks/evidence.json`, log `.cache/adr0057-installed-checks.log`; wheel SHA256 `265e0ba200b101f36d6b5ea50e70871e82b894b8c2abf34295080164be819e11`. Production scope относительно56:1new policy module,6changed paths,0removed, `.cache/adr0057-production-scope.json`. Simulation/balance modules, Step union, battle root и schema files не менялись; gen/encoder changes — только ранние lossless guards.

```powershell
$env:PIP_NO_INDEX = '1'
$env:PIP_FIND_LINKS = "$PWD/.cache/adr0054-build-dependencies"
& ./tools/prepare_m8_transport_audit.ps1 -Repository $PWD -AuditDirectory "$PWD/.cache/adr0057-installed-audit"
.cache/adr0057-installed-audit/installed/Scripts/python.exe -I tools/audit_crushed_rib_native_install.py --repository . --wheel .cache/adr0057-installed-audit/wheels/towr_encounter_balancer-0.1.0-py3-none-any.whl --work-dir .cache/adr0057-installed-audit/checks
```

Для повторения нужны fresh audit/work dirs и доступный локальный build cache. Это команды завершённого офлайн запуска.

## Финальная регрессия

`.cache/adr0057-full-regression.log`: **4201tests/1207,032с,33known errors,0failures/0skipped**. Все572integration прошли;3629unit входят в этот же полный run. Это единый актуальный прогон, без составления из прежних успешных частей или исправления fixtures после suite. Два старых positional metadata expectations обновлены до него и проверены targeted.

Exact sorted33ERROR headers совпали с `.cache/adr0056-full-regression.log`; baseline56 содержал также исправленный ранее message assertion failure, который здесь не повторился. Новых errors/failures нет.32старых subcase errors — Python3.12 frozen/slotted `.state` assignment expectation, ещё1 — M5 TypeError/ValueError expectation для `replace(init=False simulation_requests)`. Они остаются отдельной задачей; весь набор не называется зелёным.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Evidence `.cache/adr0057-regression-comparison.json` содержит durations/counts, exact headers и full log SHA256 `5faa00fafc5b358662b01a72e7e9121d5d2bf736cf84669d0fb6a295af09102f`. После suite478package paths+SHA вновь совпали с source/wheel/installed evidence; все101public example py/json/txt hashes прежние. Только исторические native59 probe/stdout были обновлены до full run под закрытый gap;97examples до57 не менялись. Current source/wheel не менялись после build.

После синхронизации проверены1804local Markdown paths/15изменённых документов, broken paths0 (anchors не проверялись). Diff и whitespace14untracked text files чистые; Git предупреждает о возможном LF→CRLF для двух обновлённых старых test fixtures, текущие package bytes от этого не менялись.35dirtyfiles включают17предшествующих. Evidence `.cache/adr0057-implementation-doc-checks.json`. Старые contract-only checks остаются историческими и не заменяют этот аудит.

Следующий шаг после закрытия57 — отдельный контракт generation matching-family/transport для нового opt-in. Автоматически наследовать permission в generation или добавлять JSON5 нельзя. Commit/push, `.gitignore` и книги не менялись.
