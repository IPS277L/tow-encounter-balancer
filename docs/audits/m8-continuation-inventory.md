# M8: инвентаризация обязательных продолжений

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

2026-11-02: [ADR-0054](../decisions/ADR-0054-repeated-leg-spasm-generation-and-magic-json-v4.md) реализует matching generation family и versioned JSON4 для существующего native53. [Production proof96d10](../examples/m8/repeated_leg_spasm_transport_contract_probe.py) проверен direct и copied unittest; [итоговый аудит](m8-repeated-leg-spasm-transport-readiness.md) закрыт:474files/42schemas/444refs,52backend cases/486commands;540integration +3538unit,33known errors без новых failures. Это доставка текущего scope, не выбор нового Wound/Miscast consumer и не новая книжная сверка.

Native integration52 закрыта в [ADR-0053](../decisions/ADR-0053-native-repeated-leg-spasm-continuation.md): отдельная permission, bounded derived cursor/full membership и strict admission. [Итоговый audit](m8-native-repeated-leg-spasm-readiness.md): automatic330d10/installed/spawn,468package parity, full4044/33known/0failures без новых errors. Одна repeated9 поддержана только новым opt-in; третья9/несовместимые6/Wind scopes сохраняют stop. Wound10/Wind consumers не добавлены, generation/JSON4 подключены ADR-0054 с отдельным matching family assertion.

2026-11-01: выбран и реализован отдельный low-level **повторный Leg Spasm после одного подтверждённого stand48 и одной новой rolled9**, без6/Wind. [ADR-0052](../decisions/ADR-0052-source-bound-repeated-leg-spasm-stand.md), [actual-bound пример34d10 и аудит](m8-repeated-leg-spasm-stand-readiness.md); [исходный finite proof](../examples/m8/repeated_leg_spasm_contract_probe.py) остаётся K1-only. Адресная сверка PG1.4 Rules108/116/119/122–123/Wounds190 и GM1.1 Champions92 выполнена при контракте; новых страниц/полного чтения при реализации нет. Сам52 не включал runner; отдельная native интеграция53 описана выше, Wound10/Wind не добавляются автоматически.

| Кандидат | Готово | Недостаёт / решение |
| --- | --- | --- |
| Wound9 Leg Spasm | Stand48/context49/policy50/transport51, low-level52 и native repeated policy53 с полными journal witnesses | Один repeat только по новому opt-in; consumed/third9/history6/Wind Prone при stand остаются неподдержаны. Generation/JSON4 реализованы в ADR-0054; legacy1/2/3 явно отвергают новое поле. |
| Wound10 Crushed Rib | Drained/UNTIL_TREATED + декларация NEXT_TEST_IS_GRIM | Нужен source-bound first-Test consumption, включая Protection до Casting. Это не Prone-рана и не часть9. |
| Wound5 Battered Leg | Endurance follow-up; при провале Prone | Нет authored Endurance profile/full-owner follow-up consumer. Новый Test/source contract шире9. |
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
