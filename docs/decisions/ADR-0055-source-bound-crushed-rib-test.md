# ADR-0055: source-bound Crushed Rib next-Test в K1

Дата: 2026-11-02. Статус: **K1 consumer реализован и закрыт [итоговым аудитом](../audits/m8-crushed-rib-test-readiness.md)**.

Основа: [закрытый transport54](ADR-0054-repeated-leg-spasm-generation-and-magic-json-v4.md), [инвентаризация continuations](../audits/m8-continuation-inventory.md), [правила ран](../rules/wounds-and-conditions.md), [проверки](../rules/core-tests.md).

## Нормативная граница

BOOK-PLAYER-GUIDE1.4, приложение Wounds Table, стр.190, строка10 Crushed Rib задаёт два независимых эффекта: ближайшая Test становится Grim; Drained действует до treatment этой Wound. BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Champions, стр.92 распространяет Wounds Table на Champions.

BOOK-PLAYER-GUIDE1.4, гл.V Rules / Grim & Glorious, стр.108: Grim обязательно перебрасывает первоначальные успехи один раз, повторные Grim не складываются, Grim/Glorious взаимно отменяются. Drained (гл.V Conditions, стр.123) удаляет bonus dice и обычный Glorious, сохраняя penalties/Grim; исключение Glorious от Fate требует отдельного действительного spend/proof.

Test не равна action. Protection в incoming Attack может случиться раньше собственного Casting: гл.V Attack Tests, стр.118; отдельные Casting rolls являются Tests в Exacting sequence: гл.VIII Casting a Spell, стр.156. Rule of Nine и Miscast Pool используют actual Casting Test/final dice (стр.157). Wound-table dice, damage arithmetic, action declaration, preparation, end-turn без Test и проверки других персонажей не расходуют next-Test effect.

Провал или отсутствие первоначальных успехов всё равно означают состоявшуюся Test. Число rerolls не определяет расход: already-Grim Test не становится дважды Grim, но pending effect относится к ней. Общая алгебра Grim/Glorious сохраняется; Fate и cancellation не включаются в первый injury-bound срез автоматически.

Это адресная сверка указанных страниц, не новое полное чтение книг. Новых house rules или нормативных Rule IDs нет: RULE-HEALTH-005/008, RULE-TEST-004 и RULE-MAGIC-004 прежние. Canonical effect source остаётся `RULE-WOUND-TABLE:crushed_rib`.

## Почему сначала K1

`wound_effect_resolution.py` создаёт `Drained / UNTIL_TREATED` и `NEXT_TEST_IS_GRIM / NEXT_TEST`. До55 consumer срока NEXT_TEST отсутствовал. `resolve_test`, `prepare_drained_test` и `resolve_casting_test` исполняют нужные Test semantics, но сами не меняют Wound lifecycle; реализованный55 добавляет эту отдельную границу.

M8 отдельно реконструирует normal/no-rerolls Casting trace; Champion Protection запрещает Wound10/её effects и использует normal-Test guards. После расхода Grim остаётся Drained, что требует собственного post-consumption admission. Поэтому55 создаёт только **injury-bound K1 primitive**. Full-owner pre/post-Test binding и подключение к M8 требуют следующего контракта; нельзя убрать restriction из roster и провести бой через старый validator.

K1 не доказывает, что переданный Test хронологически первый среди всех действий мира. Authoritative caller выбирает actual next Test и связывает actor с injury. Будущий M8 bridge обязан доказать это по собственному полному current owner и реальному handoff. Standalone receipt не доказывает journal membership/actor ownership в M8.

## Первый поддержанный source

Перед RNG и до equality принять только явно типизированные исходники:

- Живой `CharacterInjuryState`, ровно одна resolved/untreated/unhealed Crushed Rib10; optional предыдущие resolved/untreated/unhealed Superficial Injuries1–3 без effects. Записи имеют contiguous sequence и canonical table total/entry, настоящий `TABLE_ROLL` с сохранёнными целочисленными d10 и суммой; FIXED_ENTRY в этот срез не входит.
- Condition snapshot содержит только Drained. Active Wound effects — ровно canonical Drained/UNTIL_TREATED и NEXT_TEST_IS_GRIM/NEXT_TEST той же10, в техническом canonical порядке actual K1 emission: Drained→NEXT_TEST, без перестановок. Это source-admission правило, не новая игровая очередность эффектов. Никаких missing/duplicate/foreign Wound effects, других Conditions,9/6, лечения, healing или Combat Surgeon suppression. Скрытые внешние причины того же Drained по aggregate Condition не выводятся и не устраняются: Condition и все его sources сохраняются, source suppression этот consumer не выполняет.
- Stable nonblank request/actor/Test IDs, настоящий TestProfile/InlineProfile и typed modifiers/locks; числовые поля без bool aliases, настоящие enums и strict boolean flags. Original nested source повторно проходит admission без молчаливой нормализации transported/pickled объектов.
- Ordinary Test и Casting Test — две явные typed ветки. Casting actor совпадает с caster_id, сохраняются lore/state/профиль и existing Rule-of-Nine ownership. Не подставлять Casting result в ordinary completion или наоборот.

Первый срез не принимает Fate/Lucky/Talent quality proofs, reroll decisions после initial roll или automatic outcomes без TestResult. Ordinary rule-sourced Grim/Glorious и modifiers проходят existing Drained preparation: penalties/fixed successes/locks сохраняются, bonus dice/обычный Glorious удаляются. Это явно ограниченный API, не новое правило о допустимости Fate по книге.

Несколько pending10 не расходуются серийно на последующие Tests: их coexistence пока отклоняется целиком, без частичного эффекта. Другие Wounds и дополнительные consumers требуют расширения контракта.

## Подготовка, выполнение и completion

Две явные typed ветки K1 имеют следующий публичный shape:

| Модель | Поля |
| --- | --- |
| `CrushedRibTestPreparationRequest` | `id`, `actor_id`, `state: CharacterInjuryState`, `test: TestRequest` |
| `CrushedRibCastingPreparationRequest` | `id`, `actor_id`, `state: CharacterInjuryState`, `casting: CastingTestRequest` |
| `CrushedRibTestPreparationResult` | `source_request`, `effect: WoundRestrictionEffect`, `drained: DrainedTestPreparationResult`, `test: TestRequest` |
| `CrushedRibCastingPreparationResult` | `source_request`, `effect: WoundRestrictionEffect`, `drained: DrainedTestPreparationResult`, `casting: CastingTestRequest` |
| `CrushedRibTestResult` | `source: CrushedRibTestPreparationResult`, `test: TestResult`, `consumed_effect`, `state: CharacterInjuryState` |
| `CrushedRibCastingResult` | `source: CrushedRibCastingPreparationResult`, `casting: CastingTestResult`, `consumed_effect`, `state: CharacterInjuryState` |

Все модели frozen/slots, exact effect и конечное state вычисляются/сверяются с полным source. Preparation Result не содержит уже consumed injury. `drained.source_request` связан с тем же actor/conditions; `drained.source_request.test` равен исходному Test плюс canonical Grim **до** suppression. `drained.test` равен resulting `preparation.test`, для Casting — `preparation.casting.test`, **после** suppression bonus dice/обычного Glorious. Casting preparation сохраняет исходные parent ID/caster/lore/magic state и заменяет только nested Test.

Pure `prepare_crushed_rib_test`/`prepare_crushed_rib_casting` принимают соответствующие request. `resolve_crushed_rib_test`/`resolve_crushed_rib_casting` принимают preparation result и RNG. `complete_crushed_rib_test`/`complete_crushed_rib_casting` связывают preparation с уже выполненным соответствующим K1 result, без повторного исполнения. `apply_crushed_rib_test_result(actor_id, current_injury, result)` возвращает проверенное resulting injury для обеих веток. Shape не превращается в универсальный язык effects.

1. Pure preparation сохраняет полный original injury/Test source, добавляет один canonical rule-sourced Grim modifier и применяет existing Drained preparation. Existing other Grim сохраняются: новый modifier доказывает Wound provenance, quality не складывается. Reserved canonical modifier в исходном Test заранее не допускается. Подготовка не бросает dice, не удаляет restriction, не лечит Wound и не меняет conditions.
2. Executor ordinary ветки вызывает existing `resolve_test` один раз; Casting ветки — existing `resolve_casting_test` один раз. RandomSource внедряется, global RNG не используется. Casting wrapper не внедряет второй Rule-of-Nine lock и не повторяет броски/подсчёт successes собственным алгоритмом.
3. Completion принимает только состоявшийся **полный canonical Test result** этого preparation. Успех/провал не влияет на факт расхода. Чистая проверка trace не вызывает RNG/runner/rules execution и не считает совпавший request_id достаточным доказательством.
4. Result injury отличается от исходного только удалением одного exact NEXT_TEST effect. Drained и его UNTIL_TREATED cause, все Wound records/flags/order/rolls/origin, остальные участники внешнего owner и прочие histories не меняются. Их M8 projection этим K1 result не выполняется.

При exception до полного TestResult готовый completion/новое injury не публикуются. Pending source остаётся пригодным для явного повторного выполнения с управляемым caller RNG; API не обещает откат случайности. Completion случается до post-Test consequences: actual Rule-of-Nine pool increase/Miscast follow-up сохраняется и не превращает уже завершённую Test в «не состоявшуюся».

## Строгий Test witness

`TestResult`/`RollTrace` не являются самодостаточно проверенным source. Completion повторно проверяет profile/pool/minimum rule/threshold, actual prepared request, modifier order/source, initial/final values, quality, reroll indices/originals/replacements, rolled/fixed/total successes и rule IDs. Values и все trace fields типизированы строго, `1 == True` не скрывает порчу. Grim требует ровно все eligible initial successes в canonical порядке, каждый die не более одного reroll; locked values остаются.

Casting completion сравнивается с ровно той effective Test, которую создаёт existing Casting executor с одним canonical9lock. Строго проверяются также parent IDs/caster/lore/previous magic state/latest successes/miscast count и exact pool follow-ups по final values. Missing/duplicate/foreign locks, forged successes, чужой parent с тем же Test ID или не соответствующий source magic snapshot отвергаются без RNG. Existing private Fate validator может служить образцом, но не вызывается с фиктивным Fate effect.

Typed apply получает explicit actor_id, **актуальный полный injury snapshot** и completion result; actor/source/весь current injury должны совпасть. Stale injury, повторное применение и совпадение только номера Wound отвергаются. Это once-only относительно current state, не защита от намеренного восстановления старого immutable snapshot. Внешний actor↔injury mapping и порядок различных Tests остаются обязанностью authoritative owner.

Новая Wound10, полученная после Protection, не может быть израсходована этой уже завершённой Test: consumed effect всегда выбирается из **pre-Test** preparation source. Повторная10 пока не поддержана; будущий bridge обязан сохранить её новое pending состояние либо честно остановиться после регистрации, не удаляя его вместе со старым.

## Finite proof перед реализацией

[Probe](../examples/m8/crushed_rib_test_contract_probe.py), [stdout](../examples/m8/crushed_rib_test_contract_probe.output.txt), [copied test](../../tests/integration/test_m8_crushed_rib_test_contract_probe.py). Bundle: probe, `stationary_wound_runner.py`, `magic_scenario.py`. Только существующие public APIs, без fictional future consumer/result/validator.

Actual fresh M8 получает10 после обычной Protection и останавливается с целыми owner/daily/roll histories. Отдельные K1 Tests показывают подготовленный Grim/Drained, ordinary Defence-first и Casting-first, failed/zero-success/already-Grim traces и actual Casting Rule-of-Nine behaviour. Ручное удаление exact effect — помеченный injury-only oracle; он не выдаётся за production consumer и не проецируется в M8 owner. Cancellation — отдельная K1 quality-algebra проверка вне первого injury-bound среза.

До реализации actual M8 stop остаётся обязательным negative control; отсутствие нового runtime не маскируется удалением flag/effect или legacy view. Exact full sources и global RNG должны остаться неизменными. Direct/copy результаты и command фиксируются после исполнения; полная регрессия для contract-only шага не повторяется.

Direct proof прошёл:40scripted d10. После независимого read-only review уточнены исходный/выходной Drained Test в API и порядок manual completion oracle перед pool follow-up. Последняя проверка финальной версии:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.integration.test_m8_crushed_rib_test_contract_probe -v
```

Результат: **1test OK/2,027с**, CPython3.12.4, outside-sandbox runner. Copied bundle из3files проверяет exact saved stdout/empty stderr и SHA256 всех source/copied files до/после исполнения. Review блокеров/новых книжных неоднозначностей в выбранной границе не оставило. Ручные injury views не входят в M8 owner; строгий completed witness пока только задан контрактом. Production и прежние fixtures не менялись, full suite не повторялся; baseline54 остаётся4078tests составного покрытия с33known errors, этот baseline не включает новый proof test.

Финальная проверка scope относительно чистого HEAD `3a0f87b`:474package py/json и89прежних versioned examples сохранили SHA256. Проверены1667local Markdown paths/14documents, broken paths0 (anchors не проверялись); `git diff --check` и whitespace четырёх новых файлов чистые.17незакоммиченных файлов:13документов изменены, ADR/probe/stdout/copied test добавлены. Commit/push, `.gitignore` и книги не менялись.

## Реализация и приёмка

Пункты1–2 реализованы и проверены targeted tests. [Actual33d10](../examples/m8/crushed_rib_test.py), [copied test](../../tests/integration/test_k1_crushed_rib_example.py) и [installed audit](../audits/m8-crushed-rib-test-readiness.md) прошли; финальная полная регрессия пункта3 завершена:4110tests/949,557с,33known errors/0failures/0skipped. Exact33ERROR headers прежние; этап55 закрыт. Историческая contract-only проверка выше не выдаётся за её результат.

1. Frozen typed requests/results, canonical injury/effect admission и pure preparation двух веток. Strict original nested guards до equality; отсутствие consumption/RNG. Deterministic tests raw aliases, missing/duplicate/foreign effects, treated/healed/dead, другой actor/source и неподдержанные сочетания.
2. Один existing K1 executor на ветку, strict completed witness и exact-injury apply. Подлинные rolled10 и следующие Defence/Casting Tests; zero success, rerolls, already-Grim, Drained bonus/Glorious suppression,9lock/pool/follow-ups. Source immutability, no partial result, stale/repeated apply, чужой полный trace при совпавшем ID. Post-consumption injury сохраняет Drained и не открывает M8.
3. Public actual-consumer example, copied installed package proof, source/wheel/installed manifests и финальная регрессия с отдельным exact known-error baseline. Не повторять успешные проверки без нового изменения/сбоя/неразрешённого риска. Закрыть55 только после проверяемого результата.

После low-level55 нужен отдельный M8 full-owner контракт: actual Protection/Casting ordering, normal-Test validators, atomic pre/post-Test injury projection, pending follow-ups, remaining Drained admission и полные consumed witnesses. Automatic runner/policy, coexistence9/6/Wind, Recover/другие Tests, generation/JSON и wire5 в55 не входят. None/native53/JSON1–4 и их RNG/stop behaviour сохраняются.
