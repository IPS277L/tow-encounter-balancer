# ADR-0062: Battered Leg family permission и Magic JSON/CLI v6

Требования поддержки прежних wire formats и накопления версий заменены [ADR-0063](ADR-0063-single-current-magic-contract.md): Magic поддерживает только текущий JSON6. Ниже сохранены исторические решения и фактические результаты приёмки; игровые границы этим не меняются.

Дата: 2026-11-03. Статус: **завершён в принятой generation/JSON6 границе**. [Приёмка](../audits/m8-battered-leg-transport-readiness.md).

Основа — закрытый [native61](ADR-0061-native-battered-leg-continuation.md), [его приёмка](../audits/m8-native-battered-leg-readiness.md) и прежний [generation/JSON5 контракт58](ADR-0058-crushed-rib-generation-and-magic-json-v5.md). [Finite probe](../examples/m8/battered_leg_transport_contract_probe.py), [stdout](../examples/m8/battered_leg_transport_contract_probe.output.txt), [copied test](../../tests/integration/test_m8_battered_leg_transport_contract_probe.py).

## Граница и источники

Передать существующий `NpcMagicBatteredLegPolicy(endurance_profile: InlineProfile)` через bounded generation и обе magic JSON families. Это передача полного свежего источника и разрешения, не новый игровой consumer. Native61 сохраняет первую canonical resolved/untreated/unhealed rolled5 от ordinary wounding enemy Attack, normal Toughness/Endurance, отсутствие других Conditions/effects, explicit unmounted/no-external-Conditions facts. Failure сохраняет sourced Prone; его снятие, повторные/смешанные injuries, лечение и current-state/save-resume не входят в62. Новые последствия сохраняются и ограничивают continuation по прежнему scope60/61. UNSUPPORTED_PATH остаётся в знаменателе trials.

Наследуются BOOK-PLAYER-GUIDE1.4, Abilities / Characteristics & Skills68–70; Rules / Wounds & Conditions121, Prone123; Appendix / Wounds Table190/5; BOOK-GM-GUIDE1.1, Allies and Antagonists / Champions92. Книги и извлечения для этого engineering контракта заново не читались; версий/hash, Rule IDs или house rules не добавляется. Domain/engine61 не зависят от generation/JSON/CLI и не меняются ради transport.

## Полный authored profile

NonNone permission содержит весь Endurance InlineProfile. Число кубов и порог нельзя выводить из Casting, Athletics Protection, Willpower, Wizard Level или default.

- `dice`: strict integer ≥1; общего maximum10 у этого native profile нет.
- `threshold`: strict integer от1 до10.
- `pool_cap` отсутствует: native61 запрещает custom cap.

Перед equality проверяются исходные typed policy и nested profile, включая unpickled/raw-mutated объекты. Raw bool/float/string/dict и профили с cap отвергаются. Различные допустимые `2d/5` и `2d/4` не совпадают, даже если дают равный результат конкретного Test.

Transport не меняет minimum-die rule kernel: normal authored `1d/5` может дать успех на5. Threshold1 применяется при уменьшении пула ниже1, а не к любому одному кубу. Prototype-only ограничения не возвращаются через JSON Schema. В finite proof проверены1d/5 и11d/5, а реальный native Test1d/5 успешен на5.

## Отдельное generation family assertion

Последнее поле `MagicCandidateGenerationRequest.battered_leg_continuation: NpcMagicBatteredLegPolicy | None = None`. Omitted означает None, не наследование из template. Прежние positional constructors сохраняют смысл. Family является отдельным подтверждением для всех generated subsets и supplied frames.

Все пять permissions template/family проверяются до equality, collection traversal/materialization, count vectors, projection и RNG. Полное совпадение Battered Leg policy включает `dice` и `threshold`. NonNone template с omitted/None family, обратный mismatch и два различных валидных профиля дают ValueError. Dependency repeated→stationary сохраняется; среди32on/off сочетаний допустимы24. Сочетание разрешений не открывает смешанный injury scope.

`_validate_generation_policy_types` и `_validate_generation_policies` получают последний optional Battered Leg аргумент. Текущий безусловный отказ nonNone61 заменяется строгой проверкой обоих original policy/profile и matching. Обновить каждый caller, включая `_validate_generation_source`, GenerationResult и source validation в balance models.

Arithmetic Request/count/trial-cost helpers по-прежнему проверяют permissions/facts и bounds, без bootstrap, полного Scenario construction или enumeration огромных резервов. Factory отдельно readmits полный original template, затем каждый actual subset. `_project_candidate` явно передаёт **family** policy, а не полагается на случайное наследование `replace(template, ...)`.

GenerationResult проверяет оригинальные facts/permissions/profile всех candidate.scenario до первого `_count_vectors`/projection/equality: malformed последний candidate отвергается так же рано, как первый. После этого сравнивается exact full projection. Counts/C, ordered actors/definitions/policies/frames/objectives, кандидатские ID, общий round budget, seeds, ranking и denominator прежние.

Stage/report/assessment/summary/encoder sources повторно проверяются до нормализации. Исходный `compare=False simulation_requests` cache readmits полные profiles до пересоздания: same-ID candidate с другим profile или испорченный поздний cache нельзя скрыть recomputed значением.

Обе `CombatSide` perspectives сохраняются. При Wizard на стороне, противоположной perspective, friendly Minions perspective остаются fixed; нельзя удалять их, чтобы искусственно получить3/4actor пример. Отдельный full-five control использует группу только для opposing `ally`, сохраняя Wizard иE1–E3.

## Required nullable JSON6

Новая версия только для `simulate-magic` и `balance-magic`. Ruleset остаётся `towr-pg1.4-gmg1.1`; default wire version —1. Явно выбранная6 остаётся6 даже при пяти null permissions.

| Место | Required поле6 |
| --- | --- |
| simulation `scenario.battered_leg_continuation` | null либо закрытый object с authored profile |
| balance `reserve.scenario.battered_leg_continuation` | То же, собственное значение Scenario |
| balance `generation.battered_leg_continuation` | То же, независимый matching family assertion |

NonNone форма:

```json
{"endurance_profile": {"dice": 2, "threshold": 5}}
```

Policy и profile — закрытые objects (`additionalProperties:false`); поля required. `actor_id`, Skill/Characteristic, `pool_cap`, facts, current injury, journal и receipts не передаются. Четыре прежних permissions также required nullable, со своими прежними shapes/semantics2–5. Nullable не означает optional.

Parser строит native policy явно; encoder пишет nullable object явно. Balance независимо читает reserve и generation: family не выводится из reserve. Isolated mismatch, включая иной threshold при том же dice, сообщает `/generation/battered_leg_continuation`; прежние приоритеты нескольких ошибок сохраняются.

Schema `integer` сопровождается существующим strict lexical reader: JSON floats, включая2.0, не становятся допустимыми integers. Nested profile mapper и native readmission отдельно отвергают bool/int aliases и custom cap до equality.

## Версии, schemas и error identity

Добавлены шесть собственных schemas: simulation/balance × request/result/error. Измерено54package/36magic schemas,573transitive bundled refs, validator cache36; все refs разрешаются offline.

Request6 имеет собственный закрытый Scenario property list с пятью required nullable permissions. Не расширять закрытый Scenario5 через `allOf`. Неизменные fragments1–5 используются только через bundled local refs; balance6 ссылается на Scenario6. Result6 сохраняет full request6 echo; error6 — прежнюю форму ошибок с version6. Все refs разрешаются offline.

Shared strict reader явно получает magic-only versions1–6. Legacy `magic_v2` option остаётся1/2, nonmagic —1. Обе command metadata classes, typed simulation/balance input/execution/generation errors и application service version checks поддерживают6; generic base MagicInputError со старым1/2 контрактом не расширять без нужды.

После успешного strict decode известной6 shape/semantic/runtime errors сохраняют6 и доверенный request ID. UTF-8/lexical/float/duplicate-key failures сохраняют прежний fallback1/null; неизвестная7 не становится известной6 и сохраняет прежние правила fallback/decoded ID. Native61 не знает wire version.

## Lossless gates, полный echo и compatibility

JSON1–5 отвергают новое поле даже null. Encoding native nonNone61 в1–5 отказывает до definitions/actors/source projection. Текущий native61 gate сохраняется для старых версий; только6 снимает отказ. При None старые документы/echo/bytes не получают нового поля и сохраняют прежний смысл. Прежние gates Miscast1, stationary1/2, repeated1/2/3 и Crushed Rib1–4 не ослабляются.

Нельзя временно снимать permission/profile, использовать legacy view выбранного source или чинить source для прохождения mapper. Full command reconstruct-check включает version, definition order, native profile/facts и весь source. Simulation summary, balance generation→staged chain, cached requests и result echo сохраняют exact policy. Error identity остаётся связанной с исходным command/phase, без утечки worker exceptions/private rulebook content.

## Production proof и независимый finite oracle

[Probe](../examples/m8/battered_leg_transport_contract_probe.py) явно разделяет:

- 96production JSON6 parses/full echoes и96actual3/4actor candidates сверены с независимыми manual JSON6/projection oracles по24valid policies/обеим CombatSide;
- 4genuine None candidates настоящего генератора58, сверенные с независимым manual projection;
- отдельный full-five Wizard-opposite control:actual None и matching-family candidates,2production JSON6 parses и full-source oracle;
- actual native61 success/failure на8manual3/4actor sources, normal1d/5 success на5 и полный Wizard-opposite native path;
- actual native sequential/real spawn со своими seeds/full source/summary, denominator2 для round-limit и unsupported;
- настоящий early отказ generation при missing family/profile assertion и все oldwire1–5 refusals;
- production отказы raw/bool/float/cap и reserve/family profile mismatches; full-fixture oracle отдельно отвергает чужой source/missing-required. Oracle не подменяет production validators;
- actual simulation summary/result и seeded balance generation/stage/report encoding с exact command reconstruction и version6 echo.

Baseline JSON5 авторится независимо с None с самого начала; opted source не раздевается для старого encoder. Full fixture equality сохраняет ordered arrays и весь остальной source. Используются actual request62/generator/codecs6; manual fixture oracle остаётся независимым. Всего239scripted d10:138на8subset-native paths,17на1d/5,30наfull-five control и54наsequential/spawn. Дополнительный seeded balance2trials проверяется отдельно от239draws. Copied production public test:1test OK,25.558s; sources/global RNG неизменны. Старый contract-only stdout обновлён на actual production APIs.

## Реализация до следующей проверяемой вехи

1. **Выполнено:** generation field, строгий5policy/profile matching, явная projection, original source/cache guards и arithmetic/full-source split.9new unit +5native/staged/cache integration и47legacy generation checks прошли;24valid/8invalid, huge arithmetic, malformed first/last/cached sources, обе perspectives/full-five и old positional fields проверены.
2. **Выполнено:** Simulation6 schemas, strict mapper/version gates, command/error metadata, parser/encoder/service/CLI и [публичный request](../examples/m8/json/magic-simulation-v6.request.json). None6/source/error identity и oldwire refusals проверены.
3. **Выполнено:** Balance6 schemas, independent reserve/family profile, exact mismatch path, source/report/cache echo, phase errors/CLI и [публичный request](../examples/m8/json/magic-balance-v6.request.json). Обе families module/console × sequential/process проверены14wire unit и9integration; schema closure42targeted checks OK.
4. **Выполнено:** independent review/copy proof, offline wheel/pip check/495file parity,54schemas/573refs, installed47new checks и финальные11CLI/help/legacy checks, public proof и8CLI commands прошли. Full4340:4339passed/1old probe ERROR, после unknown6→7 fix этот test OK; все4340IDs закрыты составно. Две поздние help строки проверены отдельно и AST сравнением wheels; нового зелёного full финального tree не заявляется. Native injury scope и Prone5 removal не расширяются ради transport.

Production generation/adapters/application metadata и6schemas расширены по контракту; domain/engine61 не менялись. Full/installed результат зафиксирован в [приёмке](../audits/m8-battered-leg-transport-readiness.md). Старые1–5 docs/echo не получают нового поля при None; explicit6 не понижается автоматически. Следующая веха требует отдельного full-owner контракта sourced Prone5 removal.
