# ADR-0057: native Crushed Rib с подтверждением из собственного журнала

Дата: 2026-11-02. Статус: **ADR-0057 реализован и закрыт в принятой native границе**. [Приёмка](../audits/m8-native-crushed-rib-readiness.md).

Основа: [закрытый ручной bridge56](ADR-0056-source-bound-crushed-rib-owner-bridge.md), [его аудит](../audits/m8-crushed-rib-owner-readiness.md), [native53](ADR-0053-native-repeated-leg-spasm-continuation.md), [архитектура](../architecture/overview.md). Нужен отдельный native dispatcher/journal/permission поверх56; generation и JSON потребуют следующего контракта.

## Механика и граница

Нормативные источники прежние: BOOK-PLAYER-GUIDE1.4, гл.V Rules / Grim & Glorious108, Attack Tests118, Conditions / Drained123; гл.VIII Casting156–157; приложение Wounds Table190, Crushed Rib10. BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Champions92. Их сверка закреплена в55/56; в57 нового чтения страниц/PDF, версий, Rule IDs или house rules нет.

Ближайшая **фактическая Test Wizard**, в том числе incoming Protection до собственного Casting, расходует NEXT_TEST независимо от успеха. Drained UNTIL_TREATED сохраняется. Scheduling, end-turn без Test и проверки других actors не расходуют effect. Это прежние RULE-HEALTH-005/008, RULE-TEST-004 и RULE-MAGIC-004, а порядок dispatcher — технический контракт эксперимента.

Первый native scope ровно56: одна canonical resolved/untreated/unhealed rolled10, optional prior superficial1–3, только Drained; ordinary opposed Shooting Protection либо Casting. Несколько10,9/6/Wind coexistence, лечение/Fate/Lucky/Talents, Recover/другие Wizard Tests не добавляются. Новая рана/Condition после Test регистрируется полностью, затем ограничивает дальнейший context. После смерти выполняются прежние обязательные propagation/exclusion, без попытки построить context для живого Wizard.

## Отдельное разрешение и исправление admission

Добавить последним полем `NpcMagicScenario.crushed_rib_continuation: NpcMagicCrushedRibPolicy | None = None`. Enum имеет ровно `NEXT_TEST_WITH_JOURNAL_WITNESSES = 'next_test_with_journal_witnesses'`.

Разрешение независимо от Miscast/stationary/repeated. Прежняя зависимость repeated→stationary сохраняется: среди16on/off сочетаний четырёх permissions допустимы12, недопустимы4. Совместный opt-in не разрешает смешанные injury sources: текущий consumer выбирается по прежней точной injury/phase границе. Miscast permission не включает Crushed Rib и наоборот.

Shared native admission повторно проверяет original facts/все четыре permissions, включая nested Miscast facts, до clone/equality/RNG/worker dispatch. Raw string/bool/int вместо enum и испорченные nested facts отвергаются. Валидные прежние None runner traces/stops/RNG сохраняются; новая веха не сохраняет ошибочный допуск журналов.

Обнаруженный gap: после56 существующие Step types уже вмещают consuming result. Старые `validate_magic_step_policy` и `NpcMagicScenarioResult` могут принять вручную составленный continuous journal с consumer56 **без отдельного разрешения**, хотя runnerNone останавливается на10.57 обязуется закрыть это: explicit None-policy refusal для full context, lower preparation/completion и их pending descendants, в том числе после десериализации/удаления upper marker. Нельзя считать отсутствие нового Step type защитой от обхода.

## Минимальная история вне battle root

Новый frozen/slots `NpcMagicCrushedRibHistory` в `domain/npc_magic_crushed_rib_policy.py`:

| Поле | Тип и смысл |
| --- | --- |
| `state` | Полный текущий `NpcRosterCastingState` |
| `consumption` | `NpcCrushedRibConsumptionWitness \| None = None`, первый actual recorded consuming56 result и его K1 receipt |

Новых archive/history fields у battle root нет. История не копирует весь журнал и не является отдельным permission token или доказательством членства в журнале. Initial helper начинается строго с `scenario.initial_runtime_state`, а не исходного raw initial и не переданного caller текущего snapshot. При permissionNone история обязана быть None; при opt-in требуется корректная typed history даже до первой раны/расхода.

Pure helper contracts:

- `initial_magic_crushed_rib_history(scenario) -> History | None`;
- `advance_magic_crushed_rib_history(scenario, history, step) -> History | None`;
- `magic_crushed_rib_context(scenario, state, actor_id, history) -> NpcCrushedRibContext | None`;
- `validate_magic_crushed_rib_step(scenario, step, history) -> None`.

Advance требует exact `history.state == step.before`, повторную admission original step/result и updated state из настоящего result. Первый consuming Casting/Protection step заполняет `consumption` только собственным outer result/actual55 receipt. Поздний normal step обновляет state, но не создаёт второй receipt. Второй nonNone consuming receipt при занятом slot — явный отказ, не ignore/overwrite. Witness нельзя сбрасывать или переписывать после round advance, новой раны, Wind, смены фазы или смерти. Нельзя при validation снова запускать executor, RNG или replay dispatcher.

Storage admission истории **не вызывает Context56(current)** и не навязывает его Wound/phase whitelist всему current owner. Current законно содержит pending Miscast/movement/Wound, новый неподдержанный injury или умершего Wizard. Прежние typed root/pending invariants и original forms проверяются без нормализующего обхода. Узкая совместимость56 применяется при запросе следующего соответствующего действия, после обязательных pending phases.

Пока receipt отсутствует, pending context получается из exact текущего owner собственного admitted prefix. После расхода context получает ровно derived first witness;56 проверяет exact current injury, first-result prefixes/day/clock. Неподдержанная injury/phase возвращает отсутствие применимого context и штатный stop, а испорченный source/history — явный admission error. Ошибки произвольного constructor нельзя скрывать общим `except ValueError: unsupported`.

Context helper всегда сначала проверяет policy/history/exact state и actor ID. Known non-Wizard actor возвращает None; unknown ID/неверный тип — error. Wizard без10 возвращает None; несовместимый, но корректно типизированный injury/phase — None. Original aliases/неполный или чужой history не превращаются в scope stop. Это позволяет использовать один helper для Wizard actor/selected target/end-turn без неявного opt-in у других actors.

Собственный continuous prefix от fresh initial и закрытый перечень допустимых Wizard Tests определяют ближайшую Test. Отдельный wound-attack archive для этого не нужен. Если добавится новый Wizard Test consumer, его порядок/consumption потребует явного расширения контракта.

## Publication и reconstruction

Runner ведёт второй cursor независимо от repeated history53. Перед публикацией: существующие predecessor guards → policy validation с **текущей derived history** → pure advance → публикация result/current. Нельзя выполнять следующий action до согласованного advancement или доверять history из request.

`NpcMagicScenarioResult` одним проходом заново выводит обе истории из собственных steps и fresh runtime initial. Cursor caller не заменяет reconstruction. Сравниваются полный first outer result, nested K1 trace/receipt и full source, а не только ID, consumed effect или current/post-state. Два действительных расходующих Test могут иметь одинаковые IDs/итоговый owner, но разные initial dice/rerolls; witness от другого такого прогона не относится к этому журналу.

`validate_magic_step_policy` и `diagnose_npc_magic_unsupported` получают keyword-only `crushed_rib_history=None` рядом с existing repeated history. Standalone diagnosis/history helpers проверяют local consistency, но сами не подтверждают prefix membership. Runner publication и reconstructed Result обязаны сравнивать с историей, выведенной ими самими.

`NpcMagicStepResult` union **не расширяется**: используются уже разрешённые Casting/ChampionAttack/WoundTurnEnd и существующие completion types. Step re-admission проверяет исходные56 fields/receipts, включая marker removal и pending lineage. Новая native action/специальный «consume» step не создаётся: effect расходуется внутри actual Test56.

## Dispatcher и приоритеты

1. Прежний порядок mandatory Miscast preparation/roll/effect, pending Wound effect, Minion defeat/Give Ground, Curse movement/Willpower и immediate lethal exclusion сохраняется. Context56 не должен блокировать регистрацию уже состоявшегося последствия или стирать pending. Unsupported follow-up сохраняет exact first stop/source/staged prefix и все receipts. Terminal/round-budget checks не пропускают обязательный tail.
2. Scheduling не расходует effect. Wizard может получить10 на ходе E1, затем подвергнуться E2 Shooting до своего хода. Контекст для этой Protection строится по **selected target Wizard и реальному current E2 slot**, а не по предположению, что следующим будет Casting. Атаки по другим actors не расходуют Wizard effect.
3. Existing frame/target/awareness/departure policies остаются авторитетными. Factory Shooting получает derived56 context для Wizard target, factory Casting — для Wizard actor, Wizard end-turn — тот же current context без Test.56 отвергает pending10 при unopposed attack до RNG; в валидном native source этот случай уже исключён `targets_aware=True` и selected Athletics. Испорченный native fact даёт admission error, а не новый runtime stop/reason. Новые scene facts/тактика не выводятся.
4. Explicit «Wound10 requires context» gate применяется к соответствующим actor/action/end-turn/selected-target paths даже при spent Drained-only форме, которую legacy `_injury_supported` может считать обычной. Если56 несовместим, старый normal path не является fallback. Broken/Prone/Recover/другая Test у Wizard с10 не обходят этот gate.
5. Actual Test56 и ровно один completion происходят в прежнем bridge. После consuming Casting pending сохраняет nested receipt; movement completion выполняет normal target Willpower без повторной Casting. Miscast опционален только своим permission и сохраняет фактическую pool/receipt chronology. Wind/new Wound сначала исполняется или честно останавливается по прежнему consumer, затем проверяется возможность следующего context. Смешанный injury scope не расширяется.

None controls: actual first10→ACTOR_INJURY либо TARGET_INJURY после7d10; нет extra roll, consumption или изменения owner. Только ручной unpermissioned56 journal gap теперь закрывается явным отказом.

## Native mass API и границы transport

Sequential/process simulations, explicit-candidate и staged evaluation принимают native scenario57, сохраняют full source, общий seed prefix/round budget и denominator. Unsupported trials остаются в знаменателе. Shared parent preflight отвергает повреждённые policies/facts до pool/worker/RNG; worker/result повторяют admission. Журналы сравниваются отдельно у direct runner; sequential/process возвращают compact trial records и агрегаты, не полный journal каждого trial. Real spawn, records/summary parity и обе perspectives проверяются на одних scripted streams, не на точном Monte Carlo percentage.

Generation пока отвергает **любой валидный nonNone57** до enumeration/projection/pool: отсутствие нового matching family assertion не позволяет неявно унаследовать opt-in через `replace(template, ...)`. Arithmetic request admission остаётся arithmetic; `_validate_generation_policy_types` сохраняет permissions-only preflight, не полную проверку template scenes/facts. Factory/result full-source checks остаются отдельной границей. Никакого нового generation поля/family assertion в57.

Все magic JSON1–4 encoders/source gates через ранний `validate_scenario_wire_permissions` отвергают native nonNone57 до потери поля, в том числе version4. Decoders отвергают новое поле даже `null` по закрытым existing contracts. Native None не добавляет поле в старый wire и сохраняет прежние bytes. Новых schemas/registry entries/CLI options, wire5 или permissive fallback нет:42schemas/444refs прежние. Domain/engine не импортируют adapters.

## Finite proof и реализация

Ниже сохранены факты contract-only подготовки: положительный manual journal bypass относился к границе до57. При реализации control обновлён на фактический None refusal; actual native execution проверяется отдельным274d10 примером и аудитом в конце документа.

[Probe](../examples/m8/crushed_rib_native_contract_probe.py), [stdout](../examples/m8/crushed_rib_native_contract_probe.output.txt), [copied test](../../tests/integration/test_m8_crushed_rib_native_contract_probe.py) используют существующие public APIs/ручной bridge56. Нет fictional57 history/permission/helper или ручного stripping injury.

Проверить actual Casting-first и Protection-first, later normal Test, equal-current/different-trace foreign first witness. Standalone56 compatibility честно отделяется от явно помеченного manual full-record membership oracle. Current None runner stop и найденный **положительный** current journal bypass показывают фактическую границу до реализации57.

Проверено59 scripted d10: Casting-first7+4; два независимых Protection prefixes7+7 и consuming Tests7/6 с одинаковым final owner, но разными full results/receipts; later E3 normal Protection6; отдельный prefix7+Protection/new4 pending8. Actual old Step/policy/continuous Result принимают последний consumer без permission и сохраняют WOUND_EFFECT tail/daily/roll histories. Manual oracle сравнивает полный recorded first parent+receipt и отвергает foreign B при принятом A; standalone56 совместимость B с equal current честно остаётся допустимой.

Bundle5Python files: probe, `crushed_rib_owner.py`, `stationary_wound_runner.py`, `generation_contract_probe.py`, `magic_scenario.py`. Copied test прошёл **1test OK/1,356с**, CPython3.12.4, outside-sandbox runner; exact saved stdout/empty stderr, source/copied/expected SHA до/после. Sources/current owners/global RNG неизменны. Исходный sandbox запуск имел WinError5 TemporaryDirectory; финальный вне sandbox прошёл, блокера окружения не осталось.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.integration.test_m8_crushed_rib_native_contract_probe -v
```

Порядок реализации до проверяемой вехи:

При закрытии permission gap обновить воспроизводящий control этого probe на фактический None-policy отказ и синхронизировать stdout/copied test. Нельзя оставлять ожидание старого ошибочного допуска или менять его на фиктивный future result; actual native execution проверяется отдельным production примером57.

1. Append-last permission,12valid/4invalid combinations, bounded history/pure admission и explicit None marker refusals. Deterministic tests raw aliases/foreign first receipt/reset/overwrite и pending-compatible history; не открывать consumers56 шире.
2. Diagnosis/policy/runner/Result derive из собственного prefix,56 factories и Wizard end-turn. Actual Casting/Protection first, zero successes, subsequent normal Tests, foreign equal-current/different-trace, mandatory pending/death/unsupported priority, новая10/другая Wound без stripping. Legacy None/native stationary/repeated controls сохраняют traces/RNG.
3. Native sequential/spawn/explicit-list/staged full-source parity/seed/denominator и parent no-worker refusals. Generation и JSON1–4 lossless refusal tests;42schemas прежние.
4. Public actual native example и fresh installed/source/wheel manifests, copied bundles/real spawn, затем предусмотренный full regression с отдельным33known-error baseline. Исправленные expectation fixtures и составное покрытие при необходимости описывать честно; не объявлять известные errors зелёным набором. Закрыть57 только после итогового аудита.

Историческая contract-only подготовка не повторяла полный suite/installed wheel. Тогда действовал закрытый56 baseline4158составной:551integration OK +3607final unit с33known errors/0failures. Это свидетельство подготовки, не результаты последующей реализации57.

Исторический scope подготовки: независимый read-only review блокеров не оставил; уточнены роли helper, second-receipt refusal, native awareness и отличие journals от compact records.477package py/json и97прежних examples сохраняли SHA256 закрытого56;1764local Markdown paths/14документов, broken paths0 (без anchors).17dirtyfiles и отсутствие production изменений относятся к contract-only шагу, evidence `.cache/adr0057-contract-checks.json`. Исходный HEAD `3b79a43`; commit/push, `.gitignore` и книги не менялись.

## Реализация и приёмка

Пункты1–3 реализованы в [pure policy/history](../../src/towr/domain/npc_magic_crushed_rib_policy.py), existing runner/journal/Result и ранних gen/wire gates. Original battle root/Step union и schemas прежние;1new module/6changed package files.17pure+5journal unit,11native integrations,8gen/wire refusals и2copied checks проверены по шагам;104old native checks также прошли. Native M8 типы импортируются из своих модулей по существующему паттерну, root domain exports не расширены.

[Actual274d10](../examples/m8/crushed_rib_native.py) и [installed478files/12commands](../audits/m8-native-crushed-rib-readiness.md) прошли, включая настоящий spawn и6отдельных source/installed stdout hashes. Исторический59d10 probe обновлён на None refusal, его manual membership oracle не подменяет production validators. Полный4201tests/1207,032с завершён:33known errors/0failures/0skipped, все572integration прошли;3629unit входят в тот же run. Exact33ERROR headers прежние, после suite478package/101examples hashes неизменны.57 закрыт итоговым аудитом; набор с33старыми errors не объявляется зелёным. Generation/JSON1–4 новое permission по-прежнему отвергают.
