# ADR-0058: Crushed Rib family assertion и Magic JSON/CLI v5

Требования поддержки прежних wire formats и накопления версий заменены [ADR-0063](ADR-0063-single-current-magic-contract.md): Magic поддерживает только текущий JSON6. Ниже сохранены исторические решения и фактические результаты приёмки; игровые границы этим не меняются.

Дата: 2026-11-03. Статус: **все четыре шага завершены**. [Итоговый installed/full audit](../audits/m8-crushed-rib-transport-readiness.md). Основа: [native57](ADR-0057-native-crushed-rib-continuation.md), [его приёмка](../audits/m8-native-crushed-rib-readiness.md), [generation/JSON4](ADR-0054-repeated-leg-spasm-generation-and-magic-json-v4.md).

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

Каждая family5 имеет три собственные schemas. Request5 имеет собственный закрытый список Scenario properties с `additionalProperties:false`; расширять закрытый Scenario4 через `allOf` нельзя. Неизменённые fragments1–4 переиспользуются только локальными refs. Balance request5 ссылается на Scenario5 и требует независимые reserve/family fields. Result5 сохраняет полное request5 echo и прежнюю форму агрегатов; error5 — прежнюю форму ошибок с version5. Завершённый registry: **30magic/48package schemas, validator cache30, 507refs**, все refs разрешаются offline.

Проверена полная closure после Balance5: 48 schemas, 507 локальных refs. Целевые unit/schema tests валидируют весь package registry и независимость двух matching assertions.

## Lossless gates и полный источник

JSON1–4 продолжают запрещать новый key даже null. Encoding native nonNone57 в1–4 отказывает **до definitions/actors/source projection**. При None старые документы/echo/bytes сохраняются на одинаковом runtime. Старые gates Miscast1, stationary1/2 и repeated1/2/3 сохраняются; selected Crushed Rib допускается только5.

Shared mapper разделяет strict typed/source admission и versioned lossless gate. Для5 parser явно строит четвёртый typed permission, encoder явно пишет required field. Balance отдельно читает/пишет reserve и family, не выводя одно из другого. Нельзя временно снять flag, собрать legacy view или заменить full native source урезанной копией.

Request/result echo сохраняет все четыре permissions, порядок definitions/actors/frames, полный generation/staged/report source и requested version. Parser/encoder не исполняют generation/simulation, не создают RNG/pool и не нормализуют повреждённые sources/caches. Native history остаётся внутри native run; wire передаёт только fresh source permission.

## Версии команд, ошибок и CLI

Обе magic families явно поддерживают1–5 через family-specific `magic_versions`; совместимый `magic_v2=True` сохраняет только1/2. Шесть nonmagic routes остаются только1. Неизвестная version6 отвергается.

Обе command families и соответствующие input/generation/evaluation errors поддерживают5 при default1. Base `MagicInputError` может сохранить1/2. CLI help для `simulate-magic` и `balance-magic` отражает5; mode/workers/batch_size, exit statuses, stdin/file/output paths и closed-pipe поведение не меняются.

- После полной strict decode известная версия5 сохраняется в success/shape/semantic error envelopes обеих families вместе с decoded nonblank string request_id.
- Lexical/UTF-8/duplicate-key/nonfinite/float/surrogate/trailing-data failures до полной decode дают fallback1/null request_id; metadata не берётся из частично прочитанного текста.
- Unknown6 или missing/non-string version дают fallback1; полностью decoded nonblank request_id сохраняется. Для6 code/path — `unsupported_version`/`/schema_version`.
- Runtime phase errors используют собственную command5, а не metadata чужой cause; privacy и отсутствие traceback/notes/partial result сохраняются для обеих families.

## Конечный public contract proof

[Probe](../examples/m8/crushed_rib_transport_contract_probe.py), [stdout](../examples/m8/crushed_rib_transport_contract_probe.output.txt), [copied test](../../tests/integration/test_m8_crushed_rib_transport_contract_probe.py) должны проверять контракт существующими public native57 APIs без зависимости от private book extracts или test helpers.

До реализации JSON5 proposed wire использовался как ограниченный oracle полного fixture, не production codec. Сейчас production parsers проверяют12 valid permission combinations каждой family; обе CLI исполняют public v5 requests. Balance parser проверяет независимое reserve/family matching до генерации. Generation58 строит реальные кандидаты; wire1–4 отказывают nonNone57.

Manual subsets3/4actors и explicit-list staged seq/spawn проверяют сохранение полного native source, permissions, order, budgets/seeds/records/summary. Они **не называются generated58**. Отдельная current-generation proof строит3/4-actor subsets из matching Crushed Rib family. Actual57 Casting-first/Protection-first, следующий normal Test и новый mandatory Wound stop подтверждают неизменный gameplay. Generation unit cases покрывают обе CombatSide perspectives и положения Wizard при сохранённых objectives/обязательных actors. Exact scripted d10 — конечные paths, не Monte Carlo probabilities.

Шаги2–3 production parsers/encoders5, полные typed echoes и real CLI сверены целевыми unit/schema/integration checks. Обновлённый copied stdout включает actual Simulation5 и Balance5 parser paths; installed audit и полная регрессия завершают шаг4.

Подготовительный finite proof выполнен:24manual JSON5 round-trips,48manual subsets (12valid×2CombatSide perspectives×2sizes) и отдельный full-five Wizard-opposite control. Actual native исполняет4selected manual subsets, не все48.647scripted d10 =54measured genuine None simulation +193direct native (152основные и25/16new4 stops) +120seq/spawn +280explicit-list stages. Genuine None balance отдельно выполняется с indexed seeded RNG; его draws в647не входят. Copied public bundle сверяет exact stdout, empty stderr, SHA6source/copied files и original inputs/global RNG. Отдельные generation58 tests проверяют matching/projection, first/last source refusals, actual3/4-actor candidates и balance reports.

## Реализация до проверяемой вехи

1. **Выполнено:** generation field, strict4policy matching/dependency, arithmetic/full-source split, оригинальные source/cache guards и explicit projection. Unit cases покрывают12valid/4invalid, malformed first/last до enumeration, huge arithmetic и обе perspectives. Integration проверяет actual3/4-actor candidates, native57 runner и source-preserving spawned/staged reports с прежними seeds/budgets. Matching/mismatch и JSON1–4 refusals покрыты integration/public probe checks.
2. **Выполнено:** Simulation5 — schemas, strict typed/version gates, command/error metadata, parser/encoder/service/CLI и public request.
3. **Выполнено:** Balance5 — schemas, independent reserve/family fields, source/report/cache guards, phase errors, CLI и full echo. Финальный registry30magic/48total/cache30/507refs; целевые sequential/process integration checks прошли.
4. **Выполнено:** source/wheel/fresh installed/module/console/spawn audit, copied public bundles, offline schema refs и полная регрессия. 4223 tests: те же33 Python3.12 expectation errors baseline, 0 новых errors/failures/skipped; обе v5 families exact source/module/console sequential/process parity. [Итоговый отчёт](../audits/m8-crushed-rib-transport-readiness.md).

Текущие ограничения и следующий планируемый шаг после ADR-0058 собраны в [статусе проекта](../project-status.md); новых rulebook-вопросов этот transport-срез не добавил.
