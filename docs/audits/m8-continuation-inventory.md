# M8: инвентаризация обязательных продолжений

Дата: 2026-11-01. Актуализирована после закрытых ADR-0044–0050. Это карта текущих ограничений и выбор следующего узкого consumer, не объявление полного боя готовым. Native stationary policy подключена; список13 continuation labels не изменён.

## Уже закрытые prerequisites

- [ADR-0044](m8-dead-champion-readiness.md): completed lethal Attack → исключение ещё ожидающего хода погибшего Champion. Completed target пропускается; архив/полный Attack witness сохранены.
- [ADR-0045](m8-unnatural-wind-readiness.md): full-owner preparation → один Miscast roll → actual Unnatural Wind21–22, effect прежде Pool0.
- [ADR-0046](m8-opt-in-miscast-readiness.md): explicit opt-in, full-origin journal, standalone Prone self-stand/end, Casting/Curse и Shooting/Protection modifiers, scoped safe Broken alternative Recover. Ongoing Prone Wounds не включены.
- [ADR-0047](m8-opt-in-transport-readiness.md): explicit family opt-in, simulation/balance JSON v2, installed parity. Это доставка прежнего поведения, не новые Miscast/Wound consumers.
- [ADR-0048](m8-leg-spasm-stand-readiness.md): source-bound Leg Spasm self-stand, canonical Prone effects removal, сохранение terrain/history и обеих child refs; public/installed/full audit завершён.
- [ADR-0049](m8-stationary-leg-spasm-readiness.md): explicit full-owner context, Casting/Protection/end и actual6 expiry с persisted typed sources; ручная mixed chain закрыта аудитом.
- [ADR-0050](m8-native-stationary-wound-readiness.md): независимая native policy, journal/diagnosis/automatic runner, trial/sequential/spawn. Generation/JSON1/2 пока отвергают новую policy.

## Что останавливает текущий runner

Сверены [enum](../../src/towr/domain/npc_magic_step_models.py), [diagnosis](../../src/towr/domain/npc_magic_scenario_result_models.py), [journal policy](../../src/towr/domain/npc_magic_journal_policy.py), [runner](../../src/towr/engine/npc_magic_scenario_runner.py). Сейчас13labels; количество labels не измеряет полноту правил.

| Причина | Фактическая граница |
| --- | --- |
| `missing_scene` | Нет exact supplied frame live/spatial key, в том числе после движения/смерти. Геометрия не достраивается. |
| `missing_route` | Нет нужного Curse route либо ordinary Attack departure fact; adjacency недостаточно. |
| `no_legal_target` | Explicit policy/range не дают цели; нет автоматического wait/другой тактики. |
| `unsupported_broken_route` | Нет допустимого supplied plan; unsafe Broken+Prone и Run-after-spent-free-move не закрыты. |
| `unsupported_actor_injury` | Action adapter не поддерживает current injury. Canonical first9 и post-stand9+6 обслуживаются только новой policy; unsafe/repeated9 и другие ongoing effects остаются stop. |
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

| Кандидат | Готово | Недостаёт / решение |
| --- | --- | --- |
| Wound9 Leg Spasm | Stand48/context49/native policy50 и source/installed/spawn/full audit завершены | Следующий этап — generation family/versioned transport. Повторная9 с уже удалённым Prone cause не поддержана даже без6; history6/Wind Prone также требуют нового stand consumer. |
| Wound10 Crushed Rib | Drained/UNTIL_TREATED + декларация NEXT_TEST_IS_GRIM | Нужен source-bound first-Test consumption, включая Protection до Casting. Это не Prone-рана и не часть9. |
| Wound5 Battered Leg | Endurance follow-up; при провале Prone | Нет authored Endurance profile/full-owner follow-up consumer. Новый Test/source contract шире9. |
| Wound13 Torn Leg /17 Shattered Knee | K1 Conditions/restrictions | Critical-on-stand или ongoing Critical/Burdened, затем Endurance/death. Нельзя обойти общей Prone whitelist. |
| Wounds4/7/11 | K1 Endurance effects | Endurance profile, hand/item/teeth либо Blinded/Deafened и последующие consumers. |
| Wounds8/12/14–16/18–23 | K1 typed effects/choices/restrictions | Inventory/hand, action costs, Critical, дополнительные Tests/длительные источники. Нельзя считать руки пустыми. |
| Ordinary Attack Give Ground | K1/M2 movement primitives | Full owner, live projection + archive merge, arbitrary attacker routes/policy; Wizard-anchored Curse plans недостаточны. |
| Other Miscasts | K1 typed boundaries | Narrative confirmation, unresolved self-inclusion, inventory/campaign/targets либо Wounds/death. Catastrophic Death39+ требует нового active-Wizard death/turn consumer; ADR-0044 действует только после lethal Attack по ожидающей цели. |
| Standard Recover/unsafe Broken+Prone | K1 primitives | Explicit action/fastest route policy, shared free movement, source-bound whole owner. Не подставлять standard Recover вместо обязательного escape. |

Wounds1–3 и6 уже поддержаны в ограниченном flow; повторная реализация не нужна. Наличие K1 primitive не означает поддержку полного сценария.

## Книжная сверка и выбранный срез

Непосредственно перечитаны локальные PG1.4: гл.V Rules / Difficult Terrain115, Free Actions116, Recover118, Conditions122/Prone123; приложение Wounds Table190–191. Для актуализации Miscast карты — гл.VIII / Miscast Table159. GM1.1: гл.VII Allies and Antagonists / Champions92. Это выбранные страницы, не новое полное чтение книг.

Строка9 явно разрешает снять Prone free move/Recover, сохранив Difficult Terrain до лечения. Общая ongoing-cause норма страницы122 не отменяет специальное разрешение9; она всё ещё запрещает произвольное снятие других Wound causes. Снятие Condition не лечит Wound и не стирает её daily/roll provenance. Stand выполняется вместо crossing, не создаёт Athletics Test. Другие движения с restriction этим контрактом не разрешаются.

[ADR-0048](../decisions/ADR-0048-source-bound-leg-spasm-stand.md) фиксирует **низкоуровневый source-bound self-stand** с exact canonical wound/effect checks, одной free move и полной сохранностью owner. [Finite proof](../examples/m8/leg_spasm_contract_probe.py) / [stdout](../examples/m8/leg_spasm_contract_probe.output.txt) / [test](../../tests/integration/test_m8_leg_spasm_contract_probe.py) показывают реальную Wound9 и текущий ACTOR_INJURY stop, отдельный K1 stand, controls10/13 и неизменность источников. Future full-owner result не имитируется.

Request/result, canonical projection, один K1 executor и exact-source apply ADR-0048 реализованы и проверены. [Public/installed/full audit](m8-leg-spasm-stand-readiness.md) завершён. [ADR-0049](../decisions/ADR-0049-stationary-leg-spasm-continuation.md) и [finite proof](../examples/m8/stationary_wound_contract_probe.py) подготовлены; low-level stationary continuation и mixed9→6 manual chain реализованы, [аудит](m8-stationary-leg-spasm-readiness.md) завершён. Automatic runner, treatment, Difficult Terrain traversal и wire policy остаются за границей нового low-level контракта. None и обе magic wire versions сохраняют существующее поведение. Новых книжных ambiguities/house rules не выявлено.

[ADR-0050](../decisions/ADR-0050-native-stationary-wound-policy.md) закрыт [native аудитом](m8-native-stationary-wound-readiness.md): первый canonical stand и context49 включены отдельной policy; обе permissions независимы, None сохранён. Следующий ADR-0051 — явная family propagation и versioned wire/CLI, без расширения игровых consumers.
