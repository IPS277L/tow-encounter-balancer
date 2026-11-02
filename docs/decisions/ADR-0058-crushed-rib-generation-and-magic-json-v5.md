# ADR-0058: Crushed Rib family assertion и Magic JSON/CLI v5

Дата: 2026-11-03. Статус: **generation шаг1 реализован; simulation/balance JSON5 и installed/full аудит впереди**. Основа: [native57](ADR-0057-native-crushed-rib-continuation.md), [его приёмка](../audits/m8-native-crushed-rib-readiness.md), [generation/JSON4](ADR-0054-repeated-leg-spasm-generation-and-magic-json-v4.md).

## Граница

Передать существующий `NpcMagicCrushedRibPolicy.NEXT_TEST_WITH_JOURNAL_WITNESSES` через bounded generation и versioned transport. Injury/phase scope57 не расширяется: одна canonical resolved/untreated/unhealed rolled10, optional prior superficial1–3, только Drained; первый actual Protection/Casting расходует NEXT_TEST, сохраняет Drained и полный consuming witness. Все новые последствия сначала регистрируются либо дают обязательный pending/death; следующий context проверяется отдельно. Несколько10, coexistence9/6/Wind, лечение/Fate/Lucky/Talent и другие Wizard Tests остаются вне scope.

Это контракт передачи полного свежего источника и разрешения. Он не переносит current battle state, journal, history cursor, receipt или pending и не предоставляет save/resume. Domain/engine не зависят от JSON/CLI/generation. Native57 runtime остаётся прежним; unsupported trials сохраняются в denominator.

Нормативная база не меняется: BOOK-PLAYER-GUIDE1.4, гл.V Rules / Grim & Glorious, стр.108; Attack Tests, стр.118; Conditions / Drained, стр.123; гл.VIII / Casting, стр.156–157; приложение Wounds Table / Crushed Rib, стр.190; BOOK-GM-GUIDE1.1, гл.VII / Champions, стр.92. Ссылки и адресная сверка55/56 закреплены в native57 и [индексе источников](../source-index.md). Для58 книги заново не читались, новых Rule IDs/house rules нет.

## Отдельное generation family assertion

Добавить **последним** поле `MagicCandidateGenerationRequest.crushed_rib_continuation: NpcMagicCrushedRibPolicy | None = None`. Source Scenario уже содержит собственное поле57. Family — отдельное явное утверждение для каждого generated subset и supplied frame; автоматически наследовать его из template запрещено. Omitted означает None. Старые positional constructors и явный None сохраняют смысл.

До collection traversal/materialization, count-vector enumeration, projection, equality или RNG проверить:

- Настоящие типы всех четырёх permissions и исходных facts на template/family; nested Miscast facts проверяются до equality. Raw same-value string, bool/int/dict и другой Enum не принимаются.
- Полное matching template/family для Miscast, stationary, repeated и Crushed Rib. Selected template с omitted/None family и обратный mismatch дают ValueError. Не подменять source/default для прохождения проверки.
- Repeated требует stationary `LEG_SPASM_STAND_AND_CONTINUE` на обеих сторонах. Crushed Rib и Miscast независимы: сохраняются **12valid/4invalid** on/off сочетания. Новый opt-in не включает других разрешений.
- Полная original source/template admission в factory, затем admission каждого реального subset. Удалённые actors не становятся внешними witnesses; supplied facts/frames не угадываются и не чинятся.

`_validate_generation_policy_types` сохраняет арифметический permissions/facts preflight. Не добавлять full Scenario construction, bootstrap или subset projection в Request/seed/trial-cost helpers. Огромные counts должны по-прежнему проверяться без materialization. Обновить каждый caller, включая staged/balance request preflight.

`_project_candidate` явно передаёт **family** Crushed Rib field вместе с тремя прежними. Enumeration, count vectors, C, ordered IDs/actors/definitions/policies/frames, objectives, retained sides, limits, upper trial cost, seeds, ranking и denominator остаются прежними. Обе CombatSide perspectives и положение Wizard относительно perspective сохраняются; обязательные friendly actors нельзя удалять ради размера примера.

GenerationResult проверяет permissions/facts/matching **всех** original candidate.scenario до первого `_count_vectors`/projection/equality; malformed last candidate должен отвергаться так же рано, как first. Затем сравнивается полный точный projection. Проверки original source повторяются на factory/result, staged/report/assessment/summary/encoder edges, включая восстановленные/unpickled объекты. Исходный `compare=False simulation_requests` cache проверяется до equality; нельзя заменить повреждённый cache recomputed значением и скрыть порчу.

## Обязательные nullable поля JSON5

Новая версия только для `simulate-magic` и `balance-magic`; ruleset остаётся `towr-pg1.4-gmg1.1`. Default wire version —1. Выбранная5 остаётся5 даже при четырёх null permissions.

| Место | Required поле5 |
| --- | --- |
| simulation `scenario.crushed_rib_continuation` | null либо точная строка `next_test_with_journal_witnesses` |
| balance `reserve.scenario.crushed_rib_continuation` | То же, собственное значение native Scenario |
| balance `generation.crushed_rib_continuation` | То же, отдельное family assertion, matching reserve |

Все три прежних permissions также required: `miscast_continuation` формы2, `stationary_wound_continuation` формы3, `repeated_leg_spasm_continuation` формы4. Nullable не означает optional. Schema проверяет shape/types/enums; typed semantic admission проверяет dependency repeated→stationary и reserve/family matching до materialization/RNG. Изолированный новый family mismatch имеет path `/generation/crushed_rib_continuation`. При нескольких ошибках сохраняются прежние приоритеты; новая dependency для Crushed Rib не вводится.

Добавить6 schemas `magic-{simulation,balance}-{request,result,error}-v5.schema.json`: **30magic/48package**, validator cache30. Каждый request5 имеет собственный закрытый список Scenario/generation properties с `additionalProperties:false`; расширять закрытый Scenario4 через `allOf` нельзя. Неизменённые bundled fragments1–4 переиспользуются локальными refs; balance5 ссылается на собственный Scenario5 simulation schema. Result5 сохраняет полное request5 echo и прежнюю форму статистики; error5 — прежнюю форму ошибок с version5. Все refs разрешаются offline из wheel.

При буквальном append-only построении ожидаются63новых refs и507всего (baseline42schemas/444refs); это проектный расчёт, **не результат проверки отсутствующих schemas5**. Фактические counts и offline resolution подтвердить после реализации.

## Lossless gates и полный источник

JSON1–4 продолжают запрещать новый key даже null. Encoding native nonNone57 в1–4 отказывает **до definitions/actors/source projection**. При None старые документы/echo/bytes сохраняются на одинаковом runtime. Старые gates Miscast1, stationary1/2 и repeated1/2/3 сохраняются; selected Crushed Rib допускается только5.

Shared mapper разделяет strict typed/source admission и versioned lossless gate. Для5 parser явно строит четвёртый typed permission, encoder явно пишет required field. Balance отдельно читает/пишет reserve и family, не выводя одно из другого. Нельзя временно снять flag, собрать legacy view или заменить full native source урезанной копией.

Request/result echo сохраняет все четыре permissions, порядок definitions/actors/frames, полный generation/staged/report source и requested version. Parser/encoder не исполняют generation/simulation, не создают RNG/pool и не нормализуют повреждённые sources/caches. Native history остаётся внутри native run; wire передаёт только fresh source permission.

## Версии команд, ошибок и CLI

Обе magic families явно поддерживают1–5 через family-specific `magic_versions`; совместимый `magic_v2=True` сохраняет только1/2. Шесть nonmagic routes остаются только1. Неизвестная следующая версия6 отвергается.

`MagicSimulationCommand`, `MagicBalanceCommand`, их input subtypes и phase errors поддерживают5 при default1. Base `MagicInputError` может сохранить1/2. CLI help отражает5; mode/workers/batch_size, exit statuses, stdin/file/output paths и closed-pipe поведение не меняются.

- После полной strict decode известная5 сохраняется во всех success/shape/semantic error envelopes вместе с decoded nonblank string request_id.
- Lexical/UTF-8/duplicate-key/nonfinite/float/surrogate/trailing-data failures до полной decode дают fallback1/null request_id; metadata не берётся из частично прочитанного текста.
- Unknown6 или missing/non-string version дают fallback1; полностью decoded nonblank request_id сохраняется. Для6 code/path — `unsupported_version`/`/schema_version`.
- Runtime phase errors используют собственную command5, а не metadata чужой cause. Сохраняются generation/evaluation classification, exit codes, stage/candidate/count context и privacy; нет traceback/notes/private paths/partial reports.

## Конечный public contract proof

[Probe](../examples/m8/crushed_rib_transport_contract_probe.py), [stdout](../examples/m8/crushed_rib_transport_contract_probe.output.txt), [copied test](../../tests/integration/test_m8_crushed_rib_transport_contract_probe.py) должны проверять контракт существующими public native57 APIs без зависимости от private book extracts или test helpers.

До реализации JSON5 proposed wire используется как **ограниченный oracle полного fixture**, не production parser/encoder5. Canonical JSON сравнение различает bool/int; fresh inverse явно восстанавливает четыре typed permissions и проверяет matching/dependency. Genuine None1–4 документы создаются отдельно; opted-in source не понижается удалением flag. Current parser отвергает unknown5. Generation58 принимает matching typed field и строит кандидаты; старые JSON1–4 отказывают nonNone57. Эти границы отдельно показаны в probe.

Manual subsets3/4actors и explicit-list staged seq/spawn проверяют сохранение полного native source, permissions, order, budgets/seeds/records/summary. Они **не называются generated58**. Отдельная current-generation proof строит3/4-actor subsets из matching Crushed Rib family. Actual57 Casting-first/Protection-first, следующий normal Test и новый mandatory Wound stop подтверждают неизменный gameplay. Generation unit cases покрывают обе CombatSide perspectives и положения Wizard при сохранённых objectives/обязательных actors. Exact scripted d10 — конечные paths, не Monte Carlo probabilities.

После реализации oracle сверяется с настоящими parser5/encoder5/generator; production proof и installed audit выделяются отдельно. Исторический contract-only stdout не должен задним числом называться production proof.

Подготовительный finite proof выполнен:24manual JSON5 round-trips,48manual subsets (12valid×2CombatSide perspectives×2sizes) и отдельный full-five Wizard-opposite control. Actual native исполняет4selected manual subsets, не все48.647scripted d10 =54measured genuine None simulation +193direct native (152основные и25/16new4 stops) +120seq/spawn +280explicit-list stages. Genuine None balance отдельно выполняется с indexed seeded RNG; его draws в647не входят. Copied public bundle сверяет exact stdout, empty stderr, SHA6source/copied files и original inputs/global RNG. Отдельные generation58 tests проверяют matching/projection, first/last source refusals, actual3/4-actor candidates и balance reports.

## Реализация до проверяемой вехи

1. **Выполнено:** generation field, strict4policy matching/dependency, arithmetic/full-source split, оригинальные source/cache guards и explicit projection. Unit cases покрывают12valid/4invalid, malformed first/last до enumeration, huge arithmetic и обе perspectives. Integration проверяет actual3/4-actor candidates, native57 runner и source-preserving spawned/staged reports с прежними seeds/budgets. Matching/mismatch и JSON1–4 refusals покрыты integration/public probe checks.
2. **Следующий шаг:** Simulation5 —3schemas, shared typed/version gates, command/error metadata, parser/encoder/service/CLI. Промежуточно simulation1–5 и balance1–4 различаются явно:27magic/45package/cache27; balance5 ещё отказывает.
3. Balance5:3schemas, полный registry30/48/cache30, independent reserve/family fields, source/report/cache guards, phase errors и CLI; полный echo и counters/denominator.
4. Source/wheel/fresh installed/module/console/spawn audit, copied public bundles и полная регрессия на границе вехи. Old1–4 snapshots/null-key refusals,5matching/error paths/strict lexical fallback/unknown6, nonmagic routes и privacy проверяются отдельно. Известные33 Python3.12 expectation errors сверяются exact ERROR headers; новых errors/failures быть не должно.

Для шага1 и finite probe не требуется повтор full4201tests или installed audit57. Окончательный installed/full аудит остаётся за общей границей шага4. Точный результат generation шага и следующий этап фиксируются в [текущем статусе](../project-status.md).
