# M8: инвентаризация обязательных продолжений

2026-11-03: [delivery ADR-0062](../decisions/ADR-0062-battered-leg-generation-and-magic-json-v6.md) реализован: профиль Endurance передаётся целиком через independent matching family и JSON6, native61 injury scope/stop прежние. [Production239d10](../examples/m8/battered_leg_transport_contract_probe.py) сверяет98actual JSON6 parses/full echoes,97matching candidates и5None controls с независимыми oracles; native/realspawn и full-five Wizard-opposite сохранены. [Приёмка](m8-battered-leg-transport-readiness.md). JSON1–5 не представляют новое разрешение; Prone5 removal остаётся отдельным consumer.

2026-11-03: native Battered Leg реализован в [ADR-0061](../decisions/ADR-0061-native-battered-leg-continuation.md), [приёмка](m8-native-battered-leg-readiness.md). [Actual228d10](../examples/m8/battered_leg_native.py) проверяет автоматический Endurance, success/failure, completed Wizard turn и scope stop при новых последствиях. [Finite39d10](../examples/m8/battered_leg_native_contract_probe.py) обновлён на actual None refusals вместо прежнего closed Step refusal. Diagnosis gap после success → новой Staggered закрыт bounded END_TURN stop до factory, после mandatory tails. Generation/JSON1–5 новое разрешение не представляют.

2026-11-03: [ADR-0060](../decisions/ADR-0060-battered-leg-owner-bridge.md) реализует ручной full-owner Battered Leg Test с explicit profile и bounded completion receipt; [приёмка](m8-battered-leg-owner-readiness.md). Current pending/source связываются до RNG; child owners/histories сохраняются. Native runner/journal, scenario-owned profile и transport ещё не подключены.

2026-11-03, после закрытия ADR-0058: адресно перепроверен следующий простой Wound-кандидат — **Wound5 Battered Leg**. Player’s Guide 1.4, Appendix / Wounds Table, p.190: после этой записи делается Endurance Test, провал даёт Prone; дальнейшее снятие Prone выполняется по стандартному правилу Condition. Та же таблица относит рану к Catch Your Breath. Player’s Guide p.70 описывает Endurance; обычная пара Toughness/Endurance и разрешённый GM выбор иной Characteristic указаны в p.67–72; правила Prone находятся на p.123. Этот текст не задаёт числовые значения Endurance профиля персонажа и не называет отдельный action/round cost для непосредственного wound follow-up.

K1 scope закрыт в [ADR-0059](../decisions/ADR-0059-battered-leg-endurance-test.md), [приёмка](k1-battered-leg-readiness.md): одна resolved/untreated/unhealed rolled5, без Conditions/active effects, explicit unmounted actor, полный effect witness и normal Test без modifiers. Profile остаётся authored caller input. Проверяется совместимость полного trace с параметрами Test; success сохраняет injury, failure добавляет sourced Prone. Это локальная согласованность источника, не journal membership. Ручной bridge реализован в0060; далее native runner/journal, затем transport. Сочетания Conditions требуют отдельных consumers.

2026-11-03: [generation step ADR-0058](../decisions/ADR-0058-crushed-rib-generation-and-magic-json-v5.md) реализован: matching family, source/cache admission и explicit permission projection. [Finite proof](../examples/m8/crushed_rib_transport_contract_probe.py) проверяет actual3/4-actor generator и spawn/stages. Native injury consumer57 прежний; JSON1–4 отказывают Crushed Rib, schema5/codec/install аудит ещё впереди.

2026-11-02: реализован [ADR-0057](../decisions/ADR-0057-native-crushed-rib-continuation.md), [actual274d10/приёмка](m8-native-crushed-rib-readiness.md). Independent permission и derived cursor закрывают unpermissioned manual journal bypass, сохраняют runnerNone7d10 и mandatory pending/death priority. Existing Step union/root не расширены; [исторический59d10](../examples/m8/crushed_rib_native_contract_probe.py) обновлён на None refusal. Generation/JSON1–4 ещё не поддерживают новый opt-in; следующим нужен отдельный matching-family/transport контракт.

2026-11-02: после закрытого55 реализован [ADR-0056](../decisions/ADR-0056-source-bound-crushed-rib-owner-bridge.md) — ручной typed full-owner bridge, [actual63d10/приёмка](m8-crushed-rib-owner-readiness.md). Actual Protection/Casting, private kernel handoff после Test, pending follow-ups и remaining Drained с первым consuming witness проверены targeted/installed. [Probe25d10](../examples/m8/crushed_rib_owner_contract_probe.py) сохранён отдельно. Automatic runner/journal/policy ещё не изменены; следующий контракт57 должен связывать context с actual native prefix до любой generation/JSON family.

Дата: 2026-11-02. Технически актуализирована после реализации ADR-0044–0054: native stationary/repeated policies, matching generation family и обе JSON3/4 families подключены;13continuation labels сверены с текущим enum, новый wire не добавляет gameplay consumers. Это карта ограничений для выбора следующего отдельного контракта, не объявление полного боя готовым. Новых Rule IDs/house rules или чтения книг при этой технической актуализации нет.

## Уже закрытые prerequisites

- [ADR-0044](m8-dead-champion-readiness.md): completed lethal Attack → исключение ещё ожидающего хода погибшего Champion. Completed target пропускается; архив/полный Attack witness сохранены.
- [ADR-0045](m8-unnatural-wind-readiness.md): full-owner preparation → один Miscast roll → actual Unnatural Wind21–22, effect прежде Pool0.
- [ADR-0046](m8-opt-in-miscast-readiness.md): explicit opt-in, full-origin journal, standalone Prone self-stand/end, Casting/Curse и Shooting/Protection modifiers, scoped safe Broken alternative Recover. Ongoing Prone Wounds не включены.
- [ADR-0047](m8-opt-in-transport-readiness.md): explicit family opt-in, simulation/balance JSON v2, installed parity. Это доставка прежнего поведения, не новые Miscast/Wound consumers.
- [ADR-0048](m8-leg-spasm-stand-readiness.md): source-bound Leg Spasm self-stand, canonical Prone effects removal, сохранение terrain/history и обеих child refs; public/installed/full audit завершён.
- [ADR-0049](m8-stationary-leg-spasm-readiness.md): explicit full-owner context, Casting/Protection/end и actual6 expiry с persisted typed sources; ручная mixed chain закрыта аудитом.
- [ADR-0050](m8-native-stationary-wound-readiness.md): независимая native policy, journal/diagnosis/automatic runner, trial/sequential/spawn.
- [ADR-0051](m8-stationary-wound-transport-readiness.md) закрыт: explicit matching family opt-in, simulation/balance JSON3 и общий source/wheel/installed audit.1/2 явно отвергают stationary permission. Это transport готового scope, не расширение Wound/Miscast правил; последний full suite указан в актуальном статусе.

## Что останавливает текущий runner

Сверены [enum](../../src/towr/domain/npc_magic_step_models.py), [diagnosis](../../src/towr/domain/npc_magic_scenario_result_models.py), [journal policy](../../src/towr/domain/npc_magic_journal_policy.py), [runner](../../src/towr/engine/npc_magic_scenario_runner.py). Сейчас13labels; количество labels не измеряет полноту правил.

| Причина | Фактическая граница |
| --- | --- |
| `missing_scene` | Нет exact supplied frame live/spatial key, в том числе после движения/смерти. Геометрия не достраивается. |
| `missing_route` | Нет нужного Curse route либо ordinary Attack departure fact; adjacency недостаточно. |
| `no_legal_target` | Explicit policy/range не дают цели; нет автоматического wait/другой тактики. |
| `unsupported_broken_route` | Нет допустимого supplied plan; unsafe Broken+Prone и Run-after-spent-free-move не закрыты. |
| `unsupported_actor_injury` | Canonical first9/post-stand9+6 требуют stationary permission; один repeated stand52 требует дополнительной policy53 и recorded witnesses. Unsafe/repeated-after-consumption, history6 при stand и другие ongoing effects остаются stop. |
| `unsupported_target_injury` | Target adapter не поддерживает injury. Incoming canonical9+6 получает context только по новой policy; остальные Champion restrictions остаются stop, target нельзя заменить более удобным. |
| `pending_wound_effect` | Любой `champion_attack.pending`: Endurance/choice/consequence либо ordinary Champion Give Ground. Label шире своего имени. Resolved Wound9 без follow-ups сюда не относится. |
| `attack_give_ground` | Give Ground в pending Minion Attack. Ordinary Attack movement обоих owners не подключён к magic runner; Curse movement не заменяет его. |
| `miscast_preparation` | Raw trigger без принятого opt-in останавливается; opted decline обслуживается ADR-0046. |
| `miscast_roll` | Prepared prefix без разрешённого continuation остаётся stop; opted path исполняет один roll. |
| `miscast_effect` | Rolled non-Wind row остаётся pending с Pool; только opted canonical21–22 исполняется. |
| `unsupported_end_turn` | Нет consumer текущих ongoing effects/Conditions. Standalone Prone и scoped9+6 поддержаны со своими permissions; Wind Prone на retained terrain9 не является новым разрешённым stand/end. |
| `unsupported_chronology` | Неподдержанный или просроченный owner/clock/order. Закрыт только witnessed dead-awaiting gap ADR-0044, не все виды смерти. |

Missing facts, unsupported rules и исключения исполнения не смешиваются. Неподдержанная ветвь остаётся в знаменателе trials, а исключение не превращается в игровой outcome.

## Сравнение следующих кандидатов

2026-11-02: подготовлен [ADR-0055](../decisions/ADR-0055-source-bound-crushed-rib-test.md) для K1 injury-bound Crushed Rib next-Test. Адресно прочитаны локальные извлечения PG1.4 Rules107–108/118/123, Casting156–157/Wounds190 и GM1.1 Champions92. [Proof40d10](../examples/m8/crushed_rib_test_contract_probe.py) сохранён, consumer55 реализован; [actual33d10/installed audit](m8-crushed-rib-test-readiness.md) проверен, full4110tests/33known errors/0failures завершён,55 закрыт. M8 сохраняет stop. Выбран prerequisite K1 preparation/completion/apply, поскольку полного lifecycle NEXT_TEST ещё нет. M8 full-owner binding и remaining-Drained admission остаются следующим отдельным контрактом.

2026-11-02: [ADR-0054](../decisions/ADR-0054-repeated-leg-spasm-generation-and-magic-json-v4.md) реализует matching generation family и versioned JSON4 для существующего native53. [Production proof96d10](../examples/m8/repeated_leg_spasm_transport_contract_probe.py) проверен direct и copied unittest; [итоговый аудит](m8-repeated-leg-spasm-transport-readiness.md) закрыт:474files/42schemas/444refs,52backend cases/486commands;540integration +3538unit,33known errors без новых failures. Это доставка текущего scope, не выбор нового Wound/Miscast consumer и не новая книжная сверка.

Native integration52 закрыта в [ADR-0053](../decisions/ADR-0053-native-repeated-leg-spasm-continuation.md): отдельная permission, bounded derived cursor/full membership и strict admission. [Итоговый audit](m8-native-repeated-leg-spasm-readiness.md): automatic330d10/installed/spawn,468package parity, full4044/33known/0failures без новых errors. Одна repeated9 поддержана только новым opt-in; третья9/несовместимые6/Wind scopes сохраняют stop. Wound10/Wind consumers не добавлены, generation/JSON4 подключены ADR-0054 с отдельным matching family assertion.

2026-11-01: выбран и реализован отдельный low-level **повторный Leg Spasm после одного подтверждённого stand48 и одной новой rolled9**, без6/Wind. [ADR-0052](../decisions/ADR-0052-source-bound-repeated-leg-spasm-stand.md), [actual-bound пример34d10 и аудит](m8-repeated-leg-spasm-stand-readiness.md); [исходный finite proof](../examples/m8/repeated_leg_spasm_contract_probe.py) остаётся K1-only. Адресная сверка PG1.4 Rules108/116/119/122–123/Wounds190 и GM1.1 Champions92 выполнена при контракте; новых страниц/полного чтения при реализации нет. Сам52 не включал runner; отдельная native интеграция53 описана выше, Wound10/Wind не добавляются автоматически.

| Кандидат | Готово | Недостаёт / решение |
| --- | --- | --- |
| Wound9 Leg Spasm | Stand48/context49/policy50/transport51, low-level52 и native repeated policy53 с полными journal witnesses | Один repeat только по новому opt-in; consumed/third9/history6/Wind Prone при stand остаются неподдержаны. Generation/JSON4 реализованы в ADR-0054; legacy1/2/3 явно отвергают новое поле. |
| Wound10 Crushed Rib | K1 consumer55 и ручной full-owner bridge56 реализованы, actual63d10/installed проверены | Automatic dispatcher/journal/policy требуют отдельного57; automatic M8 пока сохраняет stop на10. |
| Wound5 Battered Leg | K1 consumer59 и manual full-owner bridge60 с profile/request, bounded receipt и history preservation | Native scenario profile/permission/journal ещё не подключены; Conditions/modifiers/mounts и Prone5 removal требуют отдельных consumers. |
| Wound13 Torn Leg /17 Shattered Knee | K1 Conditions/restrictions | Critical-on-stand или ongoing Critical/Burdened, затем Endurance/death. Нельзя обойти общей Prone whitelist. |
| Wounds4/7/11 | K1 Endurance effects | Endurance profile, hand/item/teeth либо Blinded/Deafened и последующие consumers. |
| Wounds8/12/14–16/18–23 | K1 typed effects/choices/restrictions | Inventory/hand, action costs, Critical, дополнительные Tests/длительные источники. Нельзя считать руки пустыми. |
| Ordinary Attack Give Ground | K1/M2 movement primitives | Full owner, live projection + archive merge, arbitrary attacker routes/policy; Wizard-anchored Curse plans недостаточны. |
| Other Miscasts | K1 typed boundaries | Narrative confirmation, unresolved self-inclusion, inventory/campaign/targets либо Wounds/death. Catastrophic Death39+ требует нового active-Wizard death/turn consumer; ADR-0044 действует только после lethal Attack по ожидающей цели. |
| Standard Recover/unsafe Broken+Prone | K1 primitives | Explicit action/fastest route policy, shared free movement, source-bound whole owner. Не подставлять standard Recover вместо обязательного escape. |

Wounds1–3 и6 уже поддержаны в ограниченном flow; повторная реализация не нужна. Наличие K1 primitive не означает поддержку полного сценария.

## Историческая книжная сверка при выборе ADR-0048

При выборе ADR-0048 непосредственно перечитаны локальные PG1.4: гл.V Rules / Difficult Terrain115, Free Actions116, Recover118, Conditions122/Prone123; приложение Wounds Table190–191. Для актуализации Miscast карты — гл.VIII / Miscast Table159. GM1.1: гл.VII Allies and Antagonists / Champions92. Это выбранные страницы, не полное чтение книг; техническая актуализация после ADR-0051 не добавляет нового чтения.

Строка9 явно разрешает снять Prone free move/Recover, сохранив Difficult Terrain до лечения. Общая ongoing-cause норма страницы122 не отменяет специальное разрешение9; она всё ещё запрещает произвольное снятие других Wound causes. Снятие Condition не лечит Wound и не стирает её daily/roll provenance. Stand выполняется вместо crossing, не создаёт Athletics Test. Другие движения с restriction этим контрактом не разрешаются.

[ADR-0048](../decisions/ADR-0048-source-bound-leg-spasm-stand.md) фиксирует **низкоуровневый source-bound self-stand** с exact canonical wound/effect checks, одной free move и полной сохранностью owner. [Finite proof](../examples/m8/leg_spasm_contract_probe.py) / [stdout](../examples/m8/leg_spasm_contract_probe.output.txt) / [test](../../tests/integration/test_m8_leg_spasm_contract_probe.py) показывают реальную Wound9 и текущий ACTOR_INJURY stop, отдельный K1 stand, controls10/13 и неизменность источников. Future full-owner result не имитируется.

Request/result, canonical projection, один K1 executor и exact-source apply ADR-0048 реализованы и проверены. [Public/installed/full audit](m8-leg-spasm-stand-readiness.md) завершён. [ADR-0049](../decisions/ADR-0049-stationary-leg-spasm-continuation.md) и [finite proof](../examples/m8/stationary_wound_contract_probe.py) подготовлены; low-level stationary continuation и mixed9→6 manual chain реализованы, [аудит](m8-stationary-leg-spasm-readiness.md) завершён. Automatic runner, treatment, Difficult Terrain traversal и wire policy остаются за границей нового low-level контракта. None и обе magic wire versions сохраняют существующее поведение. Новых книжных ambiguities/house rules не выявлено.

[ADR-0050/0051](m8-stationary-wound-transport-readiness.md) сохраняют прежние first9/context49/transport permissions. Low-level repeated52 подключён отдельной native policy53, [аудит](m8-native-repeated-leg-spasm-readiness.md). Доставка нового opt-in через generation/wire требует следующего контракта54; Wound10/Wind не получают consumers автоматически.
