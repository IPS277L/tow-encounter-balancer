# ADR-0046: opt-in Miscast runner и ограниченная поддержка Prone

Статус: принят ограниченный технический контракт, 2026-10-28. Production opt-in/journal/Prone adapters ещё не реализованы. [ADR-0045](ADR-0045-source-bound-unnatural-wind.md) закрыт [low-level аудитом](../audits/m8-unnatural-wind-readiness.md). Этот ADR подключает его готовые фазы и необходимые Prone adapters в прежний authored Champion-Wizard/Shooting Minions scope; универсального боя или каталога effects нет.

## Источники и граница

Непосредственно перечитаны локальные тексты выбранных книг:

| Книга, глава, страницы | Нормативное следствие |
| --- | --- |
| BOOK-PLAYER-GUIDE1.4, гл.VIII Magic in the Old World / Casting / Interrupted Casting, стр.156; Miscasts157–158; Miscast Table159 | Один полный roll triggered Pool; explicit decline допустим, desperate cast имеет свои prerequisites/+1d и сюда не входит. Pool0 только после actual effect. Wind21–22 включает caster и allies within Short. Другие rows остаются pending. |
| Та же книга, гл.V Rules / Range114; Combat Actions / Free Actions116 | Same Zone — Short, но не доказательство Close. Вставание вместо free move допустимо только без enemies Close; ресурс расходуется один раз за turn. |
| Та же книга, Recover118 / Conditions122 | Standard benefits (включая Prone/Staggered removal и Pool−1) и alternative condition Test — разные режимы, не суммируются. Ongoing cause должен быть устранён до снятия Condition. |
| Та же книга, Attack Modifiers119 / Dropping Prone120 / Prone123 | Shooting/Throwing по Prone−1d, Melee/Brawn получает higher ground+1d. Prone не может Give Ground/покинуть Zone. Собственные Casting/Shooting/Protection не получают общего Prone penalty; end-turn upkeep нет. Повторный Staggered при уже Prone ведёт к Wound в принятой SUFFER_WOUND policy. |
| Та же книга, Broken122 | Требуется уход в Zone без enemy как можно быстрее, затем возможен Recover. Нельзя произвольно выбрать standard Recover в unsafe Zone вместо обязательного escape. |
| BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Minions91 / Champions92 | Injury policies, defeated archive и полный Champion owner сохраняются; Monstrosities не добавляются. |

Новых normative Rule IDs/house rules нет. Derived Shooting modifier использует `RULE-COMBAT-009:prone-target`, stand — существующий `RULE-COMBAT-014:free-move-prone-removal`. Выбор stand-when-safe — явная техническая policy симуляции, а не обязательная тактика книги. Неоднозначности других Miscast rows не решаются этим ADR.

## Явный opt-in и совместимость источника

В domain планируются frozen/slotted:

- `NpcMagicPronePolicy`: единственный admitted value `SELF_STAND_WHEN_SAFE`.
- `NpcMagicMiscastContinuationPolicy(choice, facts, prone_policy)`: все поля required, без defaults; choice — существующий `NpcRosterMiscastPolicy.DECLINE_CAST_BEFORE_MISCAST`, facts — существующие пять required `NpcRosterMiscastFacts`, prone_policy — typed enum выше.
- В конец `NpcMagicScenario` добавляется `miscast_continuation: NpcMagicMiscastContinuationPolicy | None = None`. Старые positional calls остаются допустимыми. `None` сохраняет прежние exact trace/IDs/draws/stops и не выбирает decline.

Opt-in admission проверяет все типы/facts и совместимость с existing scenario facts. `no_cross_zone_close=True` также несовместим с supplied hostile CLOSE pair через границу Zones: противоречивый frame отвергается до bootstrap/RNG. No external Short creatures не выводится из all-combatants или no-external-scene-changes; это отдельное подтверждение caller. Все пять assertions сохраняют границу ADR-0045. Existing no_other_test_modifiers/no_additional_rules исключают неописанные источники; известный state-derived Prone modifier принадлежит этому adapter и не отменяется таким подтверждением. Fresh admission по-прежнему требует healthy actors, empty magic/history/round и отсутствия всех pending; opt-in не превращает input в saved battle.

Native trial/sequential/process и aggregate-only reports сохраняют полное opted scenario в source; outcomes/seed scheme/denominator прежние. Число draws opted trial закономерно меняется из-за table roll; legacy `None` — нет. Подлинность произвольных manually forged DTO не обещается.

**Generation/wire первого scope:** native generation family с non-None opt-in отклоняется на request preflight до enumeration/materialization — вручную создаваемый projection не должен молча терять новое поле. Ни один subset не пропускается. Explicit opted candidates/native simulations допустимы, где full source уже сохраняется. JSON/CLI v1 поля не добавляются; encoder явно lossless-reject opted source, parser старого v1 создаёт None. Нельзя стереть policy ради сериализации. Вывод ошибок сохраняет текущую command/phase boundary; расширение wire/generation policy — отдельный следующий контракт.

## Фазы Miscast и полный journal witness

Runner обслуживает recognized mandatory continuation до generic unsupported/end-turn/terminal/round limit:

1. Raw Casting/interruption origin + opted policy → существующий `prepare_npc_roster_miscast`.
2. Prepared prefix → один `roll_npc_roster_miscast` с тем же caller RNG и canonical prepared roll ID.
3. Rolled canonical Wind21–22 → `resolve_npc_roster_unnatural_wind` без RNG, actual applications до cleanup.
4. Другой row → точный CONTINUATION/MISCAST_EFFECT с actual effect ID, full rolled trace/Pool, без cleanup/reroll/fallback.

После Wind runner идёт в scoped Prone end-turn/action flow ниже; missing scene/route или другие неподдержанные injuries остаются stops. Для mandatory prep/roll/Wind frame не нужен: five facts и полный root уже задают admitted effect scope. Отсутствующий следующий action frame не может прервать начатый mandatory effect. Exception reducer/RNG прерывает выполнение напрямую, без игрового outcome, retry или partial result; RNG не откатывается.

`NpcMagicStepResult`/точный `_RESULT_TYPES` расширяются тремя настоящими result types ADR-0045. Общие before/after/id/actor_id берутся из full bound result. Добавляется только узкое typed поле `origin_witness: NpcRosterCastingResult | NpcBrokenRecoverResult | NpcBrokenRunResult | None = None` у `NpcMagicStep`:

- Required только для `NpcRosterMiscastPreparationResult`; для каждого другого result оно обязано быть None.
- Witness `.state` полностью равен prep.source.state, raw Casting proof либо skipped-Test/action proof совпадает с witness result, actor/execution receipt — current origin.
- Scenario-aware immediate predecessor guard требует **полное** `origin_witness == previous.result`, не только одинаковые IDs/post-state. Нельзя заменить Recover trace на другой с тем же исходом.
- После preparation следующий roll.source.state.pending содержит именно previous PreparationResult; после roll следующий Wind.source.state.pending содержит именно previous RollResult. Все сравнения полные, без повторных rules/RNG.

ADR-0045 preparation сохраняет raw interruption/skipped-Test proof, но не весь Recover/Run result: два реальных Recover могут иметь разные dice traces при равном post-state/interruption. Поэтому witness хранится на journal boundary; старый low-level API не расширяется ради trace которого у него нет. Это закрытый typed слот для одной конкретной фазы, не generic event payload.

Добавляется отдельный scenario-aware Miscast predecessor/tail helper рядом с действующим ADR-0044 death guard. Оба вызываются из runner publication и result chain/tail validation. При opt-in нельзя пропустить prep/roll/Wind или закончить журнал перед поддержанной mandatory фазой; raw tail без opt-in и rolled other-row tail остаются допустимыми exact stops. Existing lethal Attack → immediate matching dead Champion exclusion остаётся обязательным. После расширения union старые tests с TypeError от NpcMagicStep(roll/WindResult) заменяются scenario-aware rejection без opt-in; прежняя гарантия — отсутствие неразрешённых phases в legacy journal, не вечный старый vocabulary. Global step IDs/namespace/collisions проверяются и для новых phases; roll/Wind IDs canonical по ADR-0045, новые action/execution receipts не создаются.

## Prone self-stand: один полный bound transition

В `domain/npc_roster_prone_models.py` планируются:

- `NpcRosterProneStandRequest(id, state, actor_id, actor_has_enemy_in_close_range, underlying_cause_allows_removal)`;
- `NpcRosterProneStandResult(source, stand: FreeMoveProneRemovalResult)`;
- pure `stand_npc_roster_prone(request)` и exact-source `apply_npc_roster_prone_stand(state, result)` в rules.

Флаги required strict bool: enemy Close обязан быть False, cause-removal confirmation — True. Известные ongoing Prone/Wound restrictions нельзя обойти подтверждением caller. Живой active actor имеет один ещё не исполненный standard slot, Prone, свободный ресурс и ни одного mandatory pending. Request выводит K1 SELF removal с actual actor Conditions/full round/spatial; reducer вызывается ровно один раз без RNG. Result проверяет все recorded metadata/Conditions/rule IDs/source/usage, не только ID.

Projection удаляет только actor Prone, обновляет root/оба child roster references и spatial free-move usage. Placements/Zone, round/slot, magic, consumed execution IDs и все histories не меняются. Apply требует полного source equality; replay/new-ID при used resource отклоняется. Нельзя имитировать stand временным удалением Condition в чужом request или публиковать неполный child owner.

В opted runner policy применяется **до unexecuted action**, после наличия current exact scene frame. `actor_has_enemy_in_close_range` выводится из всех live hostile pair facts этого frame (каждая pair уже обязательна), а не из same Zone/graph. Eligible self-stand обязателен для этой выбранной policy: journal не принимает пропуск stand перед обычным action. Missing frame → MISSING_SCENE до stand/RNG. Stand не повторяется после action и не даёт второй free move. Если normal actor не может встать из-за enemy Close/used resource, он остаётся Prone и может выполнить только прежнее допустимое stationary действие с корректными Prone adapters.

Порядок diagnosis для unexecuted action после mandatory phases: invalid chronology/неподдержанный actor injury или ongoing cause → current frame/MISSING_SCENE → unsafe Broken+Prone/BROKEN_ROUTE → eligible self-stand → target/action checks. Поэтому при одновременно missing frame и unsafe Broken+Prone выбирается MISSING_SCENE, без stand/RNG. Для completed action/end-turn frame не требуется; действуют прежние chronology/expiry checks и scoped Prone end adapter.

## Scoped action/target/end-turn adapters

Prone как standalone Condition допускается ровно в новых безопасных contexts. **Condition whitelist и Wound-effect whitelist разделяются:** нынешние разрешённые active Wound effects остаются Staggered/Drained с прежними chronology/expiry guards. Prone от ongoing Wound, `REMOVING_PRONE_CAUSES_CRITICAL`, unresolved Wound и другие restrictions остаются unsupported даже при opt-in. Не добавлять PRONE сразу в shared set, используемый также для Wound effects.

| Контекст | Поведение |
| --- | --- |
| Собственный normal Casting/Shooting/Protection | Нет нового penalty или Glorious/Grim. Bound admission сохраняет полный injury/source и остальные ограничения; no_other_test_modifiers=True не отменяет известный target-Prone modifier. |
| Shooting по Prone Champion/Minion | В existing `NpcAttackPreparationRequest.dice_modifiers` выводится ровно один `DiceModifier('RULE-COMBAT-009:prone-target', -1)`. Bound handoff и journal сверяют его с actual target injury; отсутствие/дублирование/плюс/foreign modifier отклоняются. Existing range/Staggered modifiers и normal pool limits сохраняются. |
| Curse по Prone | Normal Willpower остаётся прежним. Effective can_give_ground = supplied plan.can_leave_zone AND NOT impossible_confirmed AND NOT actual Prone. Не переписывать scene plan. У already-Prone target нет Give Ground follow-up. |
| Ordinary Attack по Prone | Effective kernel.can_target_leave_zone=False независимо от authored departure, без изменения authored fact. Повторный Staggered следует existing SUFFER_WOUND policy; второй Prone/Give Ground не выбирается. |
| Scoped Prone end-turn | Новый `NpcRosterProneTurnEndRequest/Result` и pure end/apply соединяют existing scheduler и прежнюю expiry/receipt projection. Prone сохраняется, новых RNG/upkeep нет. Due Stomach Blow/Drained expiry и independent Conditions sources прежние. Нельзя удалять Prone из временного snapshot ради вызова старого end request. |

Старый `NpcWoundTurnEndRequest` не ослабляется; новый end wrapper отделяет admitted Prone context, когда обычный guard отвергает его. Общую узкую projection/expiry логику можно переиспользовать, но не вызывать scheduler дважды. `completed_rounds` должен учитывать обе реальные end result classes, ровно один раз; actions по-прежнему считаются по consumed execution IDs. `None` scenario сохраняет старую diagnosis/runner границу, включая Prone stops для ручных snapshots; низкоуровневые normal action checks расширяются только на явно перечисленные безопасные Prone contexts с детерминированными tests.

## Broken/Recover: закрытая часть и явные stops

- Broken **без Prone** следует прежним complete scene routes/Recover/Run без изменений.
- Уже safe Broken+Prone при available free move/no enemy Close сначала self-stand, затем прежний alternative Willpower Recover. Если free move уже использована, scoped safe Broken Recover может исполнять только alternative Test оставаясь Prone; standard benefits не добавляются. Никакого Prone/Staggered removal/Pool−1 из standard режима в этой ветви нет. Existing action-sourced skipped Casting die остаётся обязательным.
- Broken+Prone **в unsafe Zone** даёт BROKEN_ROUTE **до stand/RNG**, даже если enemies не Close. Existing BrokenRun требует полный free-move маршрут, которого после stand уже нет; повторно расходовать ресурс запрещено. Новый Run-after-spent-free-move route/fastest proof этим ADR не вводится.
- Enemy Close не разрешает self-stand. Standard Recover в unsafe Broken Zone не используется как выдуманная escape policy. Ally help/standing, normal actor standard-Recover fallback, mounts и общая Prone recovery AI остаются отдельным контрактом. Наличие K1 primitive не означает новый full-owner route consumer.

Это сознательные технические границы admitted simulation, не утверждение о невозможности иных книжных действий и не house rule. Другие unsupported injuries сохраняют соответствующие ACTOR_INJURY/TARGET_INJURY/END_TURN stops; нельзя скрывать их выбором target или пропуском trial.

## Конечный proof и обязательные проверки

[Finite probe](../examples/m8/miscast_runner_contract_probe.py) / [stdout](../examples/m8/miscast_runner_contract_probe.output.txt) использует только existing public APIs и bundle с соседним unnatural_wind.py. Он показывает actual raw→bound Wind/current END_TURN, отдельные K1 stand/shared resource/Close rejection, actual Shooting3d→2d, standard vs alternative Recover/unsafe Broken и разные Recover traces при равном post-state. K1 projections остаются внешними: будущий full owner/opt-in/journal/работающий resumed runner не имитируются. [Subprocess test](../../tests/integration/test_m8_miscast_runner_contract_probe.py) проверяет two-file external cwd/stored stdout.

Production tests должны дополнительно доказать: typed explicit policy/None exact legacy; opt-in frame contradictions/facts; full origin witness substitution при equal post-state; все missing/skipped/tail/replay/ID/DTO cases; другой row retainedPool; source/action/death order; self-stand no double free move/action; no own Prone penalty/target−1d exactly once/effective Give Ground=False; safe Broken alternative против unsafe stop; ongoing Wound restrictions; actual Wind в последнем budget round до end/outcome; missing scene после effect; failures без retry; native sequential/process full-source equality и unsupported denominator; generation/wire rejects вместо policy loss. Статистические exact Monte Carlo assertions не нужны.

## Последовательность реализации

1. **Точный следующий срез:** frozen policy/Prone enum, optional scenario field и полный admission; explicit preflight rejection opted native generation family и lossless wire rejection. Deterministic constructor/replace/types/facts/None-legacy tests. Runner dispatch/Prone/journal в этом первом срезе ещё не подключать; существующие stops остаются честной промежуточной границей.
2. Bound self-stand/scoped Prone end-turn и перечисленные normal action/target/safe Broken adapters: contract/models → pure execution → integration tests. Whole-owner/history preservation, strict DTO/ongoing cause guards и0RNG вне существующих action Tests. Automatic opt-in loop пока не объявлять готовым.
3. Closed journal/witness/predecessor/tail/policy и runner dispatch как один законченный интеграционный срез: сначала models/guards, затем publication/diagnosis/counters, полный deterministic аудит сцепления. Не оставлять опубликованный runner несовместимым с новым result validator. Обе origin kinds, other-row, unsafe Broken/scene и legacy None controls.
4. Native simulation/sequential/process/assessment source propagation и общий аудит/public opted example/installed parity. Native generation/wire opt-in остаются отвергнутыми до собственного контракта; generic engine/другие effects не добавлять. Полная регрессия на границе вехи с отдельным exact учётом известных33dataclasses errors.
