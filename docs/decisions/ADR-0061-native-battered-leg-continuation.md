# ADR-0061: native Battered Leg с профилем Scenario и подтверждением журнала

Дата: 2026-11-03. Статус: **закрыт в принятой native границе; regression составной, installed audit завершён**. [Приёмка](../audits/m8-native-battered-leg-readiness.md).

Основа — закрытые [K1 ADR-0059](ADR-0059-battered-leg-endurance-test.md) и [ручной bridge ADR-0060](ADR-0060-battered-leg-owner-bridge.md). [Автоматический пример228d10](../examples/m8/battered_leg_native.py) исполняет native runner и mass APIs. [Finite probe39d10](../examples/m8/battered_leg_native_contract_probe.py), [его stdout](../examples/m8/battered_leg_native_contract_probe.output.txt) и [copied tests](../../tests/integration/test_m8_battered_leg_native_contract_probe.py) проверяют actual helpers/None refusals, без их эмуляции.

## Источники и граница

Наследуется сверка 59/60: BOOK-PLAYER-GUIDE 1.4, Abilities / Characteristics & Skills, стр. 68–70; Rules / Wounds & Conditions, стр. 121; Prone, стр. 123; Appendix / Wounds Table, стр. 190, строка 5. BOOK-GM-GUIDE 1.1, Allies and Antagonists / Champions, стр. 92. В этой подготовке книги заново не читались; новых версий, Rule IDs или house rules нет.

Первый native consumer сохраняет точную границу 60: первая canonical resolved/untreated/unhealed rolled5 от обычной вражеской wounding Attack, живой Wizard без Conditions и active effects, normal Toughness/Endurance без modifiers, unmounted. Повторная рана, Wound от двух Staggered, Miscast-origin, treatment/healing и смешанные injury sources остаются отдельными consumers. Test исполняется сразу после actual Attack, независимо от того, завершил ли Wizard собственный ход.

Провал Endurance создаёт sourced Prone. Это обязательное последствие, а не разрешение автоматически встать. Снятие Prone5 не входит в 61; существующие Miscast/standalone-Prone и Leg Spasm policies его не разрешают.

## Отдельное разрешение и authored profile

Frozen/slots `NpcMagicBatteredLegPolicy` содержит ровно одно поле:

| Поле | Контракт |
| --- | --- |
| `endurance_profile: InlineProfile` | Явно подготовленный профиль Wizard, без custom pool cap |

Последнее поле `NpcMagicScenario.battered_leg_continuation: NpcMagicBatteredLegPolicy | None = None` одновременно задаёт независимое разрешение и владельца профиля. `InlineProfile` не выводится из Casting, Athletics Protection, Willpower, Wizard Level или общего default. Профиль относится к единственному Wizard Scenario; не добавляется во все NPC definitions и не задаёт альтернативную Characteristic.

Факты для request60 берутся из **повторно проверенных** `scenario.facts.unmounted_combatants_only` и `no_external_condition_sources`. Новый policy не дублирует эти факты. Shared native admission проверяет оригинальные policy/profile/facts до normalization, equality, clone, RNG и worker dispatch; raw dict/string/bool вместо policy/profile, испорченные числа и nested facts отвергаются.

Разрешение независимо от Miscast, stationary, repeated и Crushed Rib. Прежнее требование repeated → stationary сохраняется; opt-in нескольких policies не разрешает их несовместимые injury combinations. Среди 32 on/off сочетаний пяти permissions допустимы 24. `None` не добавляет Endurance rolls и сохраняет точный прежний stop.

## Step и идентичность исполнителя

`NpcMagicStepResult` и закрытый `_RESULT_TYPES` расширяются **только** `NpcRosterBatteredLegResult`. Его result/request и исходные nested evidence повторно проходят admission. Generic `origin_witness` остаётся исключительно Miscast-полем: source60 уже содержит полный Attack.

- `before = result.source.state`, `after = result.state`;
- `id = result.source.id`, с обычным Scenario namespace и общей защитой от ID collision;
- **`actor_id = before.wizard.actor_id`**, потому что Endurance делает Wizard. Для этого типа нужен явный branch getter; остальная семантика `Step.actor_id` сохраняется;
- active turn и выполненный Attack slot по-прежнему принадлежат Minion. Completion не создаёт action slot, action receipt, free movement usage или новый Wound roll.

Request60 получает authored profile из Scenario; Test ID по-прежнему выводится из exact Wound follow-up. Проверка не расходует следующий слот Wizard.

## Собственный prefix и ограниченная история

Frozen/slots `NpcMagicBatteredLegHistory` вне battle root:

| Поле | Смысл |
| --- | --- |
| `state: NpcRosterCastingState` | Полный current owner собственного admitted prefix |
| `completion: NpcRosterBatteredLegResult | None = None` | Первый actual recorded completion60 целиком |

Root уже хранит bounded `battered_leg_receipt` из 60. Второй archive в root не нужен. History содержит конечное evidence, не копию всего журнала и не самостоятельный permission token. Initial helper начинает только с `scenario.initial_runtime_state`; None-policy требует history=None. При opt-in history обязательна, даже до первой раны.

Pure helpers в [отдельном domain module](../../src/towr/domain/npc_magic_battered_leg_policy.py):

- `initial_magic_battered_leg_history(scenario) -> History | None`;
- `advance_magic_battered_leg_history(scenario, history, step) -> History | None`;
- `magic_battered_leg_request(scenario, state, previous, history) -> NpcRosterBatteredLegRequest | None`;
- `validate_magic_battered_leg_step(scenario, step, history) -> None`;
- `validate_magic_battered_leg_predecessor(scenario, previous, step) -> None`.

`previous` — настоящий предыдущий `NpcMagicStep` собственного runner/result, не внешний ID. New completion требует непосредственного `NpcRosterChampionAttackResult`, причём **`result.source.attack == previous.result` целиком**, включая Attack/Protection/Wound traces, а `step.before == previous.after`. Проверка действует в обе стороны: при eligible pending и opt-in следующий шаг обязан быть exact completion60; хвост журнала без completion не может заявить unsupported stop там, где consumer применим. Для неподдержанной формы остаётся прежний WOUND_EFFECT stop.

Advance требует `history.state == step.before`, проверяет оригинальный step/result и получает next state из настоящего result. Первый completion заполняет слот один раз; повторный запрещён. На всех шагах root receipt до и после равен receipt, выведенному из собственного recorded completion, либо None до него. Нельзя заменить его другим совместимым Test, удалить, сбросить на round advance или подменить первый completion позже. Полный comparison включает profile, source Attack и K1 trace, а не только ID, successes или injury.

Storage admission истории не требует, чтобы текущая injury всё ещё была пригодна для следующего normal consumer60. Уже исполненные новые Conditions/Wounds, mandatory pending и смерть можно сохранить вместе с прежним witness; способность продолжить проверяется отдельно. History ничего не лечит и не удаляет.

Runner `publish` и `NpcMagicScenarioResult` выводят историю из своего prefix одинаковыми pure helpers. Result не принимает caller cursor, не вызывает executor/RNG и не переигрывает действия. Совместимый внешний history сам по себе не доказывает membership в журнале.

При None-policy запрещаются новый completion и receipt-bearing descendants, включая upper/lower source evidence. Pending первой Wound5 без completion остаётся допустимым stop. До61 closed Step union отвергал result60, хотя standalone policy принимала отдельный ordinary descendant ручного60. Теперь union расширен, а явный permission guard запрещает unpermissioned completion и descendants. Bounded чтение prepared/rolled Miscast ancestry не позволяет скрыть receipt удалением upper marker; opt-in сравнивает каждый такой receipt с собственным prefix-derived completion.

## Eligibility, dispatcher и честные остановки

Pure eligibility явно отделяет неподдержанную shape от повреждённого evidence. Неподдержанная корректная injury даёт отсутствие applicable request и прежний WOUND_EFFECT stop. Испорченные source/profile/facts/receipt дают admission error до RNG. Нельзя оборачивать конструктор60 или executor в общий `try/except ValueError` и превращать ошибки в unsupported.

1. Прежний приоритет mandatory Miscast preparation/roll/effect, Wound pending, Minion propagation, Curse movement и immediate lethal exclusion сохраняется. Battered Leg исполняется на точном месте своего eligible Champion pending, до end-turn, scheduling, terminal и budget completion. Несовместимые pending не стираются.
2. При None первая5 сохраняет `CONTINUATION / WOUND_EFFECT`, active Minion в `actor_id`, Wizard в `missing_actor_ids`, exact `attack.execution.request_id` в source, весь staged prefix и прежний RNG count. Результат без permission не выполняет Endurance.
3. При opt-in runner строит request60 из собственного preceding Attack и Scenario profile, один раз вызывает existing executor60, публикует actual result и сохраняет receipt/history. Не добавляет собственный kernel Test или повторный roll для проверки membership.
4. Success разрешает прежние normal consumers при точной injury границе60. Failure публикует actual Prone, гасит pending и сохраняет все histories. Можно завершить атакующего Minion и исполнять независимые действия, пока текущая branch не затрагивает неподдержанную injury Wizard. Wizard action/selected incoming target сохраняют честные ACTOR_INJURY/TARGET_INJURY stops; standalone self-stand не применяется.

### Новое последствие после completed Test

Manual60 глобально требует `current Wizard injury == completion.endurance.wound_result.state` при normal Casting/Attack/scheduling/end. После success новая actual Attack может добавить Wizard Staggered или другую Wound. Это законное последствие сохраняется, но следующий normal transition уже находится вне scope60. До61 diagnosis возвращал None, после чего end factory отвергал state. Native61 распознаёт mismatch и возвращает bounded stop; оба public примера проверяют actual reducers без правки snapshots.

61 обязан проверять этот mismatch **после обязательных tails и до normal factory**. Сначала проверяются exact prefix-derived receipt и сохранность owner histories: удалённый/чужой witness является admission error, а не безопасным unsupported stop. Затем определяется выход законного нового injury consequence за scope. Для достигнутого native post-Attack состояния active slot уже executed: stop имеет `phase=END_TURN`, `reason=END_TURN`, active Minion как `actor_id`, Wizard в `missing_actor_ids`, last actual step ID как source. Не нужны новый reason или ложная CHRONOLOGY; текущие 13 reason labels сохраняются. Нельзя продолжить ветвь только потому, что активный Minion здоров.

Pending новой неподдержанной раны сначала сохраняет WOUND_EFFECT stop. Existing completed lethal Attack получает обязательный exclusion44, если он owed;61 не меняет этот порядок и **не** ослабляет gate для dead Wizard. Actual death после единственной first5 в этой native границе не достигается: второй Wound использует2d10, максимум20, и уже останавливает scope до третьей раны. Продолжение после иных injury/death sources потребует отдельного consumer/изменения контракта60; actual death61 не заявляется проверенной ветвью. Если обнаружится иной законный reachable phase mismatch, его точный диагноз нужно определить отдельно, не скрывать ошибкой конструктора.

Failure с current Prone, точно равным completion.state, не является mismatch; его последующая остановка определяется прежними action/target правилами.

## Native mass API, generation и wire

Direct runner, trial, sequential/process simulation и explicit-candidate/staged evaluation сохраняют полный Scenario/profile, seed prefix, общий budget и denominator. UNSUPPORTED_PATH не исключается из trials. Parent preflight отвергает повреждённые policies до worker pool; workers/results повторяют admission. Real spawn проверяется на scripted streams и compact records/summary parity, а не на точном Monte Carlo percentage.

До отдельного transport контракта generation обязана рано отвергать любой валидный nonNone61 до enumeration/projection, поскольку matching family permission ещё нет. Permissions-only generation preflight сохраняет свой узкий смысл и не становится full scene admission.

Все magic JSON1–5 encoders/source gates должны рано и losslessly отвергать nonNone61; decoders сохраняют закрытый отказ новому полю даже null. None сохраняет прежний wire без нового поля. Новых schemas, registry versions, CLI options или save/resume здесь нет. Profile в свежем native Scenario не означает поддержку serialized current owner/history.

## Исполняемая finite проверка

Probe использует actual native first5 stop и existing manual60. Он исполняет **39 scripted d10**, проверяет:

- exact legacy stop7d10, отдельного Wizard Test actor и source follow-up ID;
- два success traces с одинаковыми ID/successes/injury, failure Prone и once-only apply;
- другую authored profile с той же injury и manual oracle full-result refusal;
- новый Step с Wizard actor, actual None refusals completion/descendants и непрерывность Result при попытке пропустить completion;
- failure tail при Miscast=None и при standalone-Prone opt-in;
- actual WAIT → ally miss → round advance → новая Attack/Staggered и закрытый diagnosis/factory gap;
- обе child projections, daily/roll/action histories, неизменность sources/global RNG и pending-stripping refusal.

Manual oracle сравнивает полный recorded result и не подтверждает произвольную достижимость. Production helpers61 используются отдельно; автоматическое исполнение runner проверяет public228d10 пример.

## Реализация и критерии приёмки

1. **Выполнено:** policy/profile admission и exports; history, Step и pure journal/predecessor guards.21unit проверяют None/raw policies/facts/profile, foreign Attack/completion, stripped receipt, replay, actual traces/actors, detached child rosters/daily Wounds и finite Miscast ancestry.
2. **Выполнено:** diagnosis/runner integration через60. Success/failure, completed Wizard turn, scope mismatch после Staggered/Wound с mandatory tails и неизменный None prefix проверены actual native integrations. Death scope ограничен описанной выше достижимостью.
3. **Выполнено:** native trial/sequential/real spawn и explicit/staged evaluation; early generation/JSON1–5 refusal, сохранность profile/source/seeds/denominator. Всего15integration/boundary tests OK.
4. **Выполнено:** independent review, два copied public tests, свежий offline489file/source/wheel/installed audit,57installed checks и обе public examples прошли. Полный4292run дал2устаревших metadata assertion failures; после их исправления21affected checks OK и все4292IDs закрыты составно. Первоначальный full не объявляется зелёным, production после него не менялся. Следом — отдельный ADR для generation и versioned transport; Prone5 removal отдельно.

Усилено original-data admission shared `_owner60`: читаются обе исходные child rosters и original daily receipt/Wound records до equality. Игровая механика60 прежняя; validators не делают RNG/replay. Schemas/registry остаются прежними, generation/wire новое разрешение не теряют молча. Итоговый regression/installed результат записывается в [приёмке](../audits/m8-native-battered-leg-readiness.md).
