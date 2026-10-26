# ADR-0036: состояние и обязательные продолжения первого боя с магом

Статус: принято как ограниченный технический контракт, 2026-09-29. Actor-bound Casting → roster consumer, Minion Attack → Champion bridge и их ограниченная передача актуальных состояний реализованы; самого encounter ещё нет. Направление «магия в боевой симуляции» уже выбрано пользователем. [ADR-0035](ADR-0035-cowardly-flight-casting-boundary.md) закрывает только одно Casting-действие; этот ADR определяет зависимости до первого runner.

## Проверенные источники

Непосредственно прочитан локальный извлечённый текст выбранных редакций:

| Источник | Следствие для интеграции |
| --- | --- |
| BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91; Champions, стр. 92 | Minion выбывает от одной Wound; Champion использует Wounds Table как персонаж. Единый счётчик Minion wounds для мага недопустим. |
| Та же книга, Allies and Antagonists / Hermit Witch, стр. 130 | Книжный пример — Champion, Level 2, со своим списком spells и opposition. Curse of Cowardly Flight в этом списке нет. Авторский Wizard со свободно заданными профилями не называется Hermit Witch. |
| BOOK-PLAYER-GUIDE 1.4, Rules / Combat Actions / Recover, стр. 118 | Удаление Condition заменяет стандартные преимущества Recover; нельзя одновременно бесплатно уменьшить Miscast Pool. |
| Та же книга, Rules / Attack Tests / Giving Ground, стр. 119 | Уход зависит от текущей позиции, препятствий, Conditions и истории раунда. При изменении позиции старые факты нельзя считать актуальными. |
| Та же книга, Rules / Wounds & Conditions, стр. 121; Wounds Table, стр. 190 | Wound требует броска с учётом untreated Wounds и обработки конкретных последствий. Staggered снимается при Wound; не всякая Wound означает defeat. |
| Та же книга, Rules / Conditions / Broken, стр. 122 | Broken тратит ход на максимально быстрый уход в Zone без врагов, включая Manoeuvres при необходимости; Recover возможен после достижения такой Zone. Broken не означает defeat. |
| Та же книга, Magic in the Old World / Casting a Spell / Interrupted Casting, стр. 156; Spell Potency / Miscasts and the Rule of Nine, стр. 157 | Casting переносит successes, Potency берётся из последнего roll; пропуск Casting и отказ от него имеют последствия. Miscast обязателен при pool > Level; допустимый desperate cast — отдельный выбор. Pool очищается после эффекта. |
| Та же книга, Magic in the Old World / Miscast Table, стр. 159 | Разные строки требуют пространственных, injury, inventory или GM consumers. Сам lookup таблицы не завершает эффект. |

Curse сохраняет правило BOOK-PLAYER-GUIDE 1.4, Battle Magic / Curse of Cowardly Flight, стр. 162, проверенное в ADR-0035: все враги в выбранной Zone сначала Give Ground, если могут, затем проходят Willpower против Potency, иначе Broken. Новых Rule IDs и house rules нет.

## Инвентаризация реализации

| Готовый код и проверка | Граница готовности / требуемая связь |
| --- | --- |
| [NpcRoster](../../src/towr/domain/npc_roster_models.py), [tests](../../tests/unit/test_m2_npc_roster.py), [ADR-0008](ADR-0008-npc-roster-boundary.md) | Хранит Champion с CharacterInjuryState и Minion с ProfileInjuryState; сам не владеет WizardMagicState, Casting receipts или автоматическим удалением погибших. |
| [Roster attack](../../src/towr/rules/npc_roster_attack_execution.py), [models](../../src/towr/domain/npc_roster_attack_models.py), [tests](../../tests/unit/test_m2_npc_roster_attack_execution.py) | Готовы source/replay guards для Minion → Minion. Champion как target этим API не поддерживается. |
| [Wound lifecycle](../../src/towr/rules/wound_lifecycle_resolution.py), [tests](../../tests/unit/test_k1_wound_lifecycle_resolution.py), [kernel cycle](../../tests/integration/test_k1_npc_attack_kernel_cycle.py) | K1 имеет отдельные Character/Champion injury и pending Wound phases. Нужна привязка к текущему roster, применение последствий и блокировка следующего действия до completion. |
| [Casting executor](../../src/towr/engine/cowardly_flight_casting.py), [integration tests](../../tests/integration/test_m8_cowardly_flight_casting.py) | Один action receipt и exact magic/target snapshots. Нет actor-bound владельца состояния и потребителя результата в NpcRoster. |
| [Free movement](../../src/towr/rules/free_movement_resolution.py), [Recover](../../src/towr/rules/recover_resolution.py), [tests](../../tests/unit/test_k1_recover_resolution.py) | Есть отдельные запросы/результаты; Recover запрещён Broken в Zone с врагом. Нет политики обязательного Broken turn, выбора быстрейшего пути и общего переноса результатов в roster/позиции. |
| [Miscast preparation/roll](../../src/towr/rules/miscast_resolution.py), [effect reducers](../../src/towr/rules/miscast_effect_resolution.py), [tests](../../tests/unit/test_k1_miscast_effect_resolution.py) | Отдельные reducers не образуют полного encounter consumer. Например, nausea возвращает application request; wounds, transport, objects, recent spells и rifts требуют своего контекста/применения. |

177 существующих tests из 13 модулей этой таблицы и M8 выполнены успешно. Это проверка существующих компонентов, не тест реализованного encounter.

## Первый планируемый состав и тактика

Один явно описанный Champion-Wizard на одной стороне, хотя бы один союзный Minion и хотя бы один вражеский Minion. Число, actor IDs, стороны, профили, порядок активаций и приоритет целей задаёт caller. Wizard — авторский профиль с source provenance, Wizard Level 1–4, Battle Magic и memorised Curse. Его NpcDefinition и CastingCasterDefinition остаются разными описаниями, связанными явным actor ID. Wizard может быть целью вражеской атаки на тех же основаниях, что остальные участники; фиктивной неуязвимости нет.

У Minions первоначально только обычные числовые Shooting profiles без reload, Aim и hidden preparation. У мага одна offensive policy CAST_WHEN_READY из ADR-0035, без weapon Attack; нет opposition, Mixing, Magic Resistance, armour/bulky casting modifiers, иных spells или способностей книжного NPC. Это область поддержки конкретного сценария, не изменение книжных профилей. Исходные injury/Conditions отсутствуют; полученные в бою состояния должны сохраняться и влиять на допуск следующих действий.

Сценарий явно задаёт graph, placements, pair facts и target priorities. При изменении состава или позиции facts перепроверяются; незаданные новые отношения не выводятся из названий Zones. Нет автоматической осведомлённости или универсального поиска тактики. Любая цель Curse, способная Give Ground, требует completion соответствующего ухода: ограничение ADR-0035 нельзя превращать в постоянный запрет движения для боя.

## Владелец состояния и порядок исполнения

Неизменяемые определения отделены от текущего состояния. Узкая M8 orchestration хранит NpcRoster, actor-bound WizardMagicState, RoundState, SpatialState, историю потреблённых execution IDs и одно текущее обязательное продолжение. Это состояние только данного сценария, без общего battle aggregate или шины событий.

1. Проверить полное текущее состояние и pending continuation до выбора actor/action. Pending не исчезает при смене раунда или достижении лимита.
2. Из актуального roster построить snapshots выбранного действия. История завершённых/исключённых ходов не служит фильтром живых участников.
3. Исполнить ровно один соответствующий узел с внедрённым RNG: Casting, Attack, Recover или обязательное движение. Не преобразовывать spell в weapon Attack.
4. Применить результат к тому же source snapshot ровно один раз: magic, injury, Conditions, позиции, action receipt и continuation переносятся согласованно. Не делать повторный бросок при применении.
5. Закрыть обязательные последствия, затем завершать ход/менять раунд и проверять objective/round limit.

Планируемый dispatch: обязательное continuation → Broken turn → действие выбранной тактики. Defenceless/ограничения injury проверяются до действия. Если Wizard из-за другого действия пропустил Casting или отказался от накопленного cast, применяются существующие interruption/abandonment правила; successes/pool не обнуляются произвольно.

## Остановка и обязательные продолжения

Неверный исходный запрос отклоняется до RNG. Законный, но ещё не поддержанный путь после исполнения возвращает отдельный `unsupported_path`: phase/reason, actor/source IDs, последний согласованный snapshot и полный pending payload/уже полученные traces. Это не победа, defeat, round_limit или повод повторить бросок. Исключение/ошибка реализации не маскируется этим статусом.

- **Champion Wound:** сохранять точный Wound request/roll/completion и все нерешённые последствия. Пока невозможно применить требуемые Tests, dropped items, Conditions или ограничения профиля, обычный бой не продолжается. Смерть учитывается только после нужных completion; Minion one-Wound policy сюда не переносится.
- **Broken:** требуется конкретное исполнение ухода и, в безопасной Zone, допустимого Recover. Если маршрут/Manoeuvre либо ситуация без доступного выхода не поддержаны, остановиться перед неподдержанным действием. Не придумывать ожидание или Recover среди врагов. Уход в другую Zone сам по себе не удаляет участника из боя.
- **Miscast:** первый runner может останавливаться на точном MISCAST_REQUIRED до preparation, сохраняя pool/successes и доступный desperate choice. Поддержка полного encounter без таких остановок потребует отдельного policy для этого выбора, preparation → optional spell → table roll → effect application. Пока эффект не закрыт, очищенное промежуточное состояние reducer нельзя выдавать за завершённый encounter. Недостающий GM/context не заменять пустым эффектом.
- **Повторный Curse и выбывшие:** допуск ADR-0035 ограничен healthy targets и полным spatial набором round participants. Нужна отдельная адаптация актуальных Conditions/live projection до повторного применения в меняющемся roster. Старые target snapshots не переиспользуются.

Открытые вопросы Miscast `recently`, нехватки объектов и self-inclusion остаются в [open-questions](../open-questions.md). Их разрешение требуется при реализации затрагивающей их ветви, а не для безопасной остановки перед ней. Книжных неоднозначностей этим ADR не решаем.

Будущий objective задаётся отдельно от magic rules. На первом runner нужен явный objective и round limit; Broken, завершение spell или пустая target Zone не объявляют успех автоматически. Обработка pending имеет приоритет перед обоими terminal checks. Массовые прогоны, метрика баланса, JSON/CLI и генерация составов в этот ADR не входят.

## Порядок следующих срезов

1. **Actor-bound Casting → roster consumer.** Сначала frozen input/state/result и pure application одного существующего CowardlyFlightCastingResult. Один явный Champion actor, его CastingCasterDefinition и WizardMagicState; точное соответствие source roster/round/spatial, magic state и target injury snapshots. Применять target Conditions/magic/receipt атомарно, хранить consumed execution IDs, сохранять MISCAST_REQUIRED как блокирующий pending. Reject stale/replay/чужой actor без RNG. Пока только допуск ADR-0035, без loop, нового cast или расширения целей.
2. **Minion Attack → Champion bridge.** Подключить готовый kernel и Wound lifecycle к тому же roster; определить обработанные ветви и точные pending/unsupported для остальных. Сохранить действующий Minion → Minion API.
3. **Casting из актуального roster.** Live projection после defeat, повторные targets с Conditions, legality/effect modifiers и Give Ground completion. Неподдержанные состояния обнаруживать до следующего roll; source chain для всех переходов.
4. **Обязательный ход Broken и magic interruptions.** Узкий явный маршрут/Manoeuvre и Recover с обновлением фактов; полный запрет обычного dispatch при незакрытом продолжении. Нет автоматического выбора GM.
5. **Scenario/runner contract и реализация.** Собрать поддержанные переходы, objective/round limit и typed stop results. На Miscast и иных пока неисполняемых обязательных ветвях — exact unsupported; никаких summary об успешном завершении такого боя. Проверить scripted end-to-end победу, лимит и каждую остановку.
6. **Расширение обязательных Miscast continuations.** Вводить owners/effect consumers отдельными ограниченными срезами; до включения неоднозначных ветвей получить решение пользователя. После покрытия заявленных путей — самостоятельный пример и аудит encounter; затем отдельный план массовой симуляции.

Критерии первого consumer: WAIT/CAST/MISCAST_REQUIRED, обе стороны caster, caster definition ID != actor ID, несколько целей/пустая Zone, exact before/after, сохранение неучаствующих бойцов, replay/stale/source rejection и неизменность входа. Tests используют готовый executor и scripted RNG только для получения исходного результата; сам consumer не получает RNG. Конкретные имена новых классов уточняются при реализации, перечисленная граница является контрактом.

## Реализованный первый consumer

Модели находятся в [npc_roster_casting_models.py](../../src/towr/domain/npc_roster_casting_models.py); pure application — в [npc_roster_casting_resolution.py](../../src/towr/rules/npc_roster_casting_resolution.py).

- `NpcCastingWizardState(actor_id, caster, magic_state)` явно связывает отдельное CastingCasterDefinition и WizardMagicState с участником. ID actor, NPC definition и Casting definition могут различаться.
- `NpcRosterCastingState(roster, wizard, round_state, spatial_state, consumed_execution_ids=(), pending_miscast=None)` — frozen/slotted снимок только этого среза. Допускается один здоровый Champion без Wounds/Conditions и живые Minions; полученный Broken у Minion сохраняется. Injured Champion, Brute, второй Champion и defeated/live projection пока не поддержаны. Ordered roster participants и spatial sides/round/coverage должны совпадать с round snapshot.
- `NpcRosterCastingRequest(state, casting)` создаётся **до исполнения** и связывает полный снимок с конкретным CowardlyFlightCastingRequest. Проверяет actor/definition/magic/round/spatial, target injury, историю исполнения и отсутствие pending. Профили Willpower и facts остаются явно заданными входами ADR-0035; roster не содержит такого каталога и не вычисляет их автоматически.
- `NpcRosterCastingResult(source, casting)` связывает исходный запрос с уже полученным CowardlyFlightCastingResult; сравнивается весь Casting request. `.state` — вычисляемая read-only проекция, отдельный произвольный post-state передать нельзя.
- `apply_npc_roster_casting_result(state, result)` сверяет **весь** текущий state с source, включая нетронутых участников и histories; отклоняет повторный execution ID. Возвращает один согласованный снимок с magic/target injury/receipt/consumed ID, сохраняя definitions, equipment/resilience и остальных бойцов. Не вызывает executor, resolver или RNG.

Порядок вызова: bound request → existing `execute_cowardly_flight_casting(bound.casting, rng)` → `NpcRosterCastingResult(bound, casting_result)` → apply к актуальному `bound.state`. Caller сохраняет возвращённое состояние; чистая функция не может запретить намеренно восстановить старую копию вместе с её историей.

`pending_miscast` хранит **полный Casting result**, а не только roll request: доступны исходный snapshot, traces, накопленные successes, pool и pending source. Поля проверяются против текущего actor/magic/round/spatial/target injury и consumed history. Этот pending блокирует создание нового bound Casting request; consumer не выбирает desperate cast и не очищает pool. Для будущего общего dispatch понадобится собственная обработка продолжения. Наличие consumer не означает реализацию ходов Broken, Champion attack или full runner.

[11 unit tests](../../tests/unit/test_m8_npc_roster_casting.py) и [3 integration tests](../../tests/integration/test_m8_npc_roster_casting.py) проверяют frozen/type/source/replay/stale guards, несовпадение IDs, сохранность pending, отсутствие RNG, обе стороны, WAIT/CAST/MISCAST_REQUIRED, empty Zone/zero Potency и WAIT → CAST через реальные K1 turn/round transitions. Следующий срез — Minion Attack → Champion bridge с обязательным Wound lifecycle/pending.

## Реализованный Minion Attack → Champion bridge

2026-09-30. [Модели](../../src/towr/domain/npc_champion_attack_models.py) и [executor/application](../../src/towr/rules/npc_champion_attack_execution.py) связывают existing protected NPC preparation, один Attack slot, kernel и Character Wound lifecycle. Действующий Minion → Minion API не менялся.

`NpcChampionAttackState` хранит полный NpcRoster, CombatRoundState, DailyWoundState одного Champion, consumed execution/roll IDs и необязательный полный pending result. `NpcChampionAttackRequest` связывает state, NpcProtectedAttackPreparationResult и AttackActionExecutionRequest. `NpcChampionAttackResult` сохраняет source, исходное исполнение (включая pending Wound roll), завершённый ResolutionResult и optional CharacterWoundLifecycleCompletionResult; `.state` — вычисляемая проекция, `.pending_follow_ups` — ещё не применённые запросы.

Перед RNG проверяются: враждебные Minion/Champion, живые actor/target, точный порядок roster/round, один unexecuted STANDARD Attack slot, текущая доступность attack, Resilience/Protection/equipment, исходные injury, открытый actor-scoped daily ledger и histories. Допуск initial Conditions — только Staggered; Wounds допускаются, если эффект уже resolved и нет active wound effects/restrictions. Иные состояния требуют отдельного адаптера текущих профилей; они не игнорируются. Дополнительные attack effects, negation, Fate и особые NPC abilities исключены. Numeric preparation и явные modifiers/GM range facts сохраняются как вход существующего API; новые правила их расчёта не вводятся.

`execute_npc_champion_attack(request, rng, decisions=None)` вызывает existing `execute_attack_action` один раз. Если kernel вернул Wound, вызываются existing completion и `apply_kernel_character_wound_completion`: регистрация в переданном дневном ledger, эффекты раны и source chain сохраняются. Второго Attack/Wound roll нет. У Champion нет Player Near Miss. Повторный Staggered использует existing injectable kernel decisions; Give Ground не исполняется пространственно этим адаптером.

`apply_npc_champion_attack_result(state, result)` не принимает RNG и проверяет весь актуальный source state, в том числе остальных участников. Проекция переносит current injury, один receipt, daily/consumption histories и непосредственно применяет только AttackerStaggerRequest от Close miss. Остальные follow-ups, например Give Ground, Endurance/drop/random body-part requests, остаются в полном pending result и блокируют новый attack request. Смерть из завершённой Wounds Table сохраняется как `dead`, без encounter victory/удаления участника. Существующие injury restrictions и Conditions после completion остаются в roster; отсутствие immediate pending не означает допуск такого бойца к любому следующему действию.

При ошибке callback/RNG/completion исключение распространяется без retry/fallback; полного результата не выдаётся. Pure consumer не защищает от намеренного восстановления старого state вместе с историей. Полное объединение владельцев magic/spatial/attack ещё не реализовано: caller сохраняет WizardMagicState и SpatialState вне данного адаптера. В частности, старый NpcRosterCastingState пока требует здорового Champion и не принимает автоматически раненого мага.

[13 unit tests](../../tests/unit/test_m8_npc_champion_attack.py) и [3 integration tests](../../tests/integration/test_m8_npc_champion_attack.py) проверяют miss/Stagger/Wound, Drained, pending effects/Give Ground, Close miss, source/replay/stale/history guards, untreated/treated dice, повторные раны и смерть. Integration использует supplied activations, а не новый encounter runner.

Непосредственные источники: BOOK-PLAYER-GUIDE 1.4, Rules / Attack Tests, стр. 118–119; Wounds & Conditions, стр. 121; Wounds Table, стр. 190–191. BOOK-GM-GUIDE 1.1, Allies and Antagonists / Champions, стр. 92. Новых Rule IDs/house rules нет. Следующий срез — Casting из актуального roster: совместимая граница injured caster/текущих target Conditions, live projection и обязательных продолжений, с отдельной проверкой разрешённых профилей; затем Give Ground и Broken/interruptions по плану.

## Casting из актуального roster и передача атаки

2026-10-02. Расширение снимает healthy-only ограничение состояния; прежние описания первого среза выше и аудит ADR-0035 относятся к прежнему допуску. Общего battle runner/dispatch не добавлено.

### Хранение и допуск

`NpcRosterCastingState` хранит текущий injury Champion, в том числе раны или смерть, и полный roster Minions, включая defeated. Хранение такого снимка не разрешает Casting. `NpcRosterCastingRequest` допускает живого caster с Conditions из множества **Staggered/Drained**, resolved Wounds и только соответствующими активными WoundConditionEffect. Другие active effects/restrictions и unresolved Wounds отклоняются до RNG. В частности, NEXT_TEST_IS_GRIM не теряется и не превращается в обычный roll. Known shield и положительный текущий Resilience bonus также отклоняются: первый normal boundary не интерпретирует происхождение bonus и не поддерживает armour/bulky Casting. Явные facts ADR-0035 по-прежнему обязательны.

BOOK-PLAYER-GUIDE 1.4, Rules / Conditions, стр. 122–123: Staggered сам по себе не меняет Test; Drained запрещает bonus dice и Glorious, но не мешает уже normal немодифицированному Test этого boundary. Это не общее игнорирование Drained. Caster Broken должен уходить/Recover, Defenceless не может действовать; они и прочие пока не поддержанные Conditions отклоняются. BOOK-PLAYER-GUIDE 1.4, Wounds Table, стр. 190: Stomach blow даёт Drained до конца следующего хода; Casting consumer сохраняет эффект и не завершает ход/не истекает его длительность.

Цели Curse теперь допускают **Staggered/Drained/Broken**, сохраняя все Conditions. У уже Broken цели Willpower всё равно исполняется; неудача возвращает `was_already_present=True`, успех не снимает Broken. BOOK-PLAYER-GUIDE 1.4, Rules / Conditions, стр. 122–123; Battle Magic / Curse of Cowardly Flight, стр. 162. Только живые Minions с wound_limit=1, по-прежнему фактически неспособные Give Ground, normal Willpower без bonus dice/Glorious/immunity/modifiers. Прочие Conditions отклоняются; иммунитет/осведомлённость не вычисляются.

### Проекции и подготовка

`state.casting_round_state` и `state.casting_spatial_state` фильтруют **injury.dead/defeated**, сохраняя порядок оставшихся участников, стороны, graph, round number и актуальные placements. Completed/excluded turn IDs сами по себе не удаляют живую цель. IDs погибших убираются только из проекций, включая их completed/excluded IDs. Если live round теряет сторону или active actor, запрос не допускается; это техническая граница текущего combat round, не automatic victory или новый objective.

`NpcRosterCastingTargetContext(actor_id, willpower_profile, can_give_ground)` содержит явно заданные profile/факт движения, без копии injury. Pure `prepare_npc_roster_casting(request_id=..., state=..., selected_zone_id=..., targets=..., facts=..., policy=...)` в [существующем модуле](../../src/towr/rules/npc_roster_casting_resolution.py) берёт injuries из roster и строит bound request по live projections. Все живые враги выбранной Zone должны иметь context в стабильном round order; пропуски, дубли и мёртвые цели отклоняются. Это не каталог Willpower и не автоматическое определение доступности движения.

После Casting проекция результата переносит только исполненный active-turn receipt в полный исходный round. Full roster, defeated entries, полный spatial snapshot и исходные histories исключённых/завершённых участников остаются у caller; effect применяется только к живым целям. Pending Miscast сверяется с live projection, но не удаляет архивные snapshots из state.

### Связь двух владельцев

Опциональный `NpcRosterCastingState.champion_attack` — existing NpcChampionAttackState того же caster/day, с точно такими же полными roster/round. Его consumed execution IDs должны сохраняться в общей истории этого Casting owner. Это связь двух конкретных адаптеров ADR-0036, без универсального event/aggregate API.

[Типизированная передача](../../src/towr/domain/npc_roster_champion_attack_models.py):

1. До RNG создать `NpcRosterChampionAttackRequest(state, attack)`: проверить attached owner, полный source, pending Miscast и execution ID.
2. Исполнить уже существующий `execute_npc_champion_attack(bound.attack, rng, decisions=...)`.
3. Создать `NpcRosterChampionAttackResult(bound, attack_result)`; full attack source должен совпасть.
4. Pure [apply_npc_roster_champion_attack_result](../../src/towr/rules/npc_roster_champion_attack_resolution.py) проверяет актуальный полный state/replay и возвращает согласованный снимок. Roster/round/daily/pending/attack histories приходят из результата атаки; WizardMagicState и SpatialState сохраняются. ID атаки добавляется в общую историю; отдельная attack history остаётся у Champion owner.

Подготовка следующего Casting блокируется при attached pending attack. После Casting attached owner обновляется теми же roster/round, сохраняя daily ledger, roll IDs и attack history. Для следующей активации caller использует K1 turn transitions и передаёт одинаковый round обоим owners; сам wrapper не завершает ходы и не пропускает эффекты. Простое попадание по магу не считается пропущенным им Casting-действием и не очищает накопленные successes/pool (PG1.4, Magic in the Old World / Interrupted Casting, стр. 156).

Опциональный owner оставлен для первоначального standalone Casting API. Полная передача/блокировка attack pending гарантируется при использовании нового bound пути; ручное пересоздание состояния с отброшенными owners/histories находится вне чистого API, как и восстановление старой копии. Старые low-level executors сами по себе не становятся encounter dispatcher.

[12 unit tests](../../tests/unit/test_m8_current_roster_casting.py) и [7 integration tests](../../tests/integration/test_m8_champion_casting_handoff.py) покрывают injuries/Conditions, real Wound → Casting, повторный Broken, live/archive projections, полный pending обоих направлений, общую и отдельную histories, текущую броню/щит, stale/replay/purity и одинаковый round обоих owners. Два прежних negative admission tests обновлены под расширенный допуск. Всего 99 M8 tests проходят.

Следующий срез — Give Ground для Curse: source-bound movement completion с актуальным spatial snapshot, затем Willpower по всем исходным affected targets, включая ушедших. До этого `can_give_ground=True` остаётся отказом до Casting RNG. Следующие ходы Broken/interruptions и end-turn Wound effect lifecycle ещё не интегрированы в runner.


## Двухфазное Casting с Give Ground

2026-10-02. Реализован самостоятельный контракт одного Curse-действия и его completion; перенос движений в NpcRosterCastingState — следующий срез. Непосредственно перечитаны BOOK-PLAYER-GUIDE 1.4, Rules / Attack Tests / Giving Ground, стр. 119; Conditions / Broken, стр. 122; Drained / Prone / Defenceless, стр. 123; Battle Magic / Curse of Cowardly Flight, стр. 162. Новых игровых Rule IDs или house rules нет.

### Первая фаза

CowardlyFlightCastingTarget теперь допускает явное can_give_ground=True. Доступность по-прежнему задаёт caller как факт, а не как выбор отказаться от обязательного ухода. Известная gave_ground_entity_ids запрещает заявлять повторный уход этого участника в том же раунде уже при подготовке запроса. Остальной normal admission не расширен: только living Minions со Staggered/Drained/Broken, прежние profiles/facts; Prone и другие неподдержанные Conditions отклоняются.

[Executor](../../src/towr/engine/cowardly_flight_casting.py) после единственного Casting roll/receipt готовит spell/Zone как прежде. Если положительный эффект потребовал хотя бы один Give Ground, возвращается MOVEMENT_REQUIRED с полными preflight/spell/Zone, неизменными spatial/target snapshots и ordered pending_movements. Willpower ещё не исполняется, включая цели без движения. WAITING, MISCAST_REQUIRED и нулевая Potency не создают такие движения. Текущий action уже потрачен; completion не требует другого слота, не заканчивает ход и не повторяет Casting.

### Движения и completion

Caller явно задаёт destination, path_entity_ids и route facts для каждого pending item, по исходному порядку целей. Existing resolve_give_ground исполняет движение без RNG; complete_cowardly_flight_movement связывает результат с конкретным follow-up. Все движения образуют одну цепочку: первый previous_state равен исходному Casting spatial, каждый следующий использует результат предыдущего. При изменении положения факты маршрута должны соответствовать актуальному снимку.

[CompletionRequest/Result](../../src/towr/domain/cowardly_flight_casting_completion_models.py) сохраняют полный pending Casting и требуют полный GiveGround source_request для каждого движения. Проверяются точные follow-ups/цели/порядок/число, Conditions, исходная Zone, направление от actor мага, история раунда, route restrictions, текущий пространственный снимок и итог цепочки. Нельзя пропустить уход, подтвердить чужое движение, заменить graph/round/history или передать только совпадающий ID. Полный результат Casting также проверяет эти связи и normal Willpower traces без обращения к RNG/resolvers.

complete_cowardly_flight_casting(request, rng) исполняет только ordered Willpower исходных affected targets, включая ушедших. Изменения Conditions от Give Ground переносятся до Test. В K1 устранён CODE-CONFLICT-003: Broken, полученный во вражеской destination Zone, сохраняется при успешном сопротивлении Curse; неудача повторного применения возвращает was_already_present=True. Иные Conditions и injury не теряются. Batch сохраняет movement chain, итоговый spatial и трассировку движения.

apply_cowardly_flight_casting_completion(current, result) заменяет только точный текущий MOVEMENT_REQUIRED result; повторное применение к завершённому result запрещено. Применение не двигает и не бросает кубы. Caller обязан сохранять возвращённое состояние: намеренное восстановление старого pending с историей находится вне чистого API. Ошибки RNG/completion распространяются без retry/fallback и без завершённого результата; pending source остаётся неизменным. Некорректные/неполные движения отклоняются до Willpower RNG; они не превращаются в разрешение пропустить уход.

### Граница этого среза

На 2026-10-02 NpcRosterCastingRequest ещё отклонял can_give_ground=True до Casting RNG. Эта граница снята срезом 2026-10-25 ниже. Standalone completion и интеграция roster не добавляют автоматического выбора укрытия, маршрута или доступности движения, общей battle aggregate, runner, Broken turn policy либо Miscast completion.

[19 unit tests](../../tests/unit/test_m8_cowardly_flight_casting_movement.py), [5 integration tests](../../tests/integration/test_m8_cowardly_flight_casting_movement.py) и 2 новых [K1 tests](../../tests/unit/test_k1_cowardly_flight_zone_batch.py) проверяют оба этапа, исходный порядок/состав целей, remote caster, движение во вражескую Zone, Conditions/history, pending/source/replay/route guards и чистое применение. Прежний negative admission test обновлён под расширенный standalone допуск. Всего 123 M8 tests проходят.

Следующий на тот момент шаг — подключение MOVEMENT_REQUIRED к NpcRosterCastingState и bound Champion handoff — реализован ниже. Далее Broken/interruptions и end-turn Wound lifecycle по прежнему плану.

## Give Ground completion в roster/Champion owner

2026-10-25: MOVEMENT_REQUIRED интегрирован в существующий actor-bound owner. Непосредственно перечитаны BOOK-PLAYER-GUIDE 1.4, Rules / Giving Ground, стр. 119; Conditions / Broken, стр. 122; Drained / Prone / Defenceless, стр. 123; Battle Magic / Curse of Cowardly Flight, стр. 162. Книжные правила и Rule IDs не меняются.

`NpcRosterCastingState.pending_movement` хранит полный low-level `CowardlyFlightCastingResult` только со статусом MOVEMENT_REQUIRED. Проверяются actor/caster, exact magic/live round/spatial/target injury и наличие уже consumed Casting ID. Pending не сосуществует с Miscast/незавершённой Champion attack. Подготовка нового Casting, прямой bound Casting request и bound Champion attack request блокируются до RNG. Новый can_give_ground=True admission сохраняет explicit movement facts и все существующие ограничения normal Casting/target Conditions.

Initial `NpcRosterCastingResult` переносит единственный action receipt и magic, записывает Casting ID один раз и сохраняет pending. Пространственный переход ещё не публикуется в owner; Willpower не выполняется. Полностью completed low-level result с выполненными движениями нельзя передать вместо initial result: требуется отдельная completion boundary.

[Completion models](../../src/towr/domain/npc_roster_casting_completion_models.py):

- `NpcRosterCastingCompletionRequest(state, completion)` связывает весь current owner до Willpower RNG с existing `CowardlyFlightCastingCompletionRequest`. Нужен тот же полный pending movement, а low-level request проверяет все ordered Give Ground sources и точный spatial chain.
- Caller исполняет existing `complete_cowardly_flight_casting(bound.completion, rng)` — только Willpower исходных affected targets, включая ушедших. Движения, Casting, receipt и решение о маршруте не повторяются.
- `NpcRosterCastingCompletionResult(source, completion)` требует точный полный low-level source. Derived `.state` переносит injury/Conditions всех исходных целей, обновляет live placements в полном spatial в прежнем порядке и добавляет только новые Give Ground IDs к полной history. Архивные placements и все прежние usage IDs сохраняются. Wizard magic, round/receipt, общая execution history и Champion daily/roll/attack histories не расходуются повторно; attached Champion roster синхронизируется. Pending movement очищается.
- [Pure application](../../src/towr/rules/npc_roster_casting_completion_resolution.py) `apply_npc_roster_casting_completion(current, result)` требует exact current owner, включая не затронутых spell бойцов, archived entries, attached owner и history. Completed/no-pending, stale/foreign source и повтор completion отклоняются; равные immutable копии допустимы. Новый RNG или движение отсутствуют.

```python
bound = NpcRosterCastingCompletionRequest(current, movement_completion_request)
completed = complete_cowardly_flight_casting(bound.completion, rng)
result = NpcRosterCastingCompletionResult(bound, completed)
current = apply_npc_roster_casting_completion(current, result)
```

Live spatial projection теперь фильтрует по living participants также gave_ground/free_move_used/difficult_terrain_tested IDs: SpatialBattleState не допускает history ссылок на отсутствующие placements. Полный source хранит эти архивные IDs; completion сохраняет их исходный порядок. Это исправление допуска архивного снимка, а не сброс once-per-round. Defeated архивный entry не становится активным врагом в destination Zone.

При ошибке/неполной movement chain или исключении Willpower RNG source owner остаётся pending; partial movements caller хранит отдельно и не выдаёт за завершённый roster. API не повторяет броски и не выбирает retry/маршрут. Pure snapshots по-прежнему не удостоверяют намеренное пересоздание owner с отброшенными pending/history или восстановление старой копии. Полного battle dispatcher, Broken turn и Miscast completion здесь нет.

[15 unit tests](../../tests/unit/test_m8_npc_roster_casting_completion.py) и [5 integration tests](../../tests/integration/test_m8_npc_roster_casting_completion.py): pending/dispatch/source/replay/type guards, обе стороны Wizard, одна/две перемещаемые цели, original Willpower order, enemy destination/Broken, once-per-round, архивные placements и все usage histories, неизменность inputs/global RNG и ошибка второго target Test. Real Champion Wound → Casting → Give Ground → Willpower сохраняет Drained, daily receipt, один Casting receipt и обе execution histories. Два прежних negative tests обновлены под новый допуск; всего 143 M8 tests проходят.

Первый срез Broken turn/Casting interruptions реализован ниже; далее Broken Run, end-turn Wound effects и отдельный scenario/runner. Никаких автоматических GM решений или универсального aggregate.

## Первый Broken Recover и Casting interruption

2026-10-25. Непосредственно перечитаны BOOK-PLAYER-GUIDE 1.4, Rules / Combat Actions, стр. 116; Manoeuvre / Run, стр. 117; Recover, стр. 118; Conditions / Broken, стр. 122; Magic in the Old World / Interrupted Casting, стр. 156; Miscasts and the Rule of Nine, стр. 157. Первый законченный переход поддерживает две ситуации: действующий Broken уже в Zone без живых врагов либо достигает её одним legal free move. После этого исполняется self Recover / Willpower. Обязательный Run, terrain/obstacle traversal, отсутствие выхода и произвольные другие действия в этот допуск не входят и отклоняются до RNG; они не заменяются ожиданием или Recover среди врагов.

[Модели](../../src/towr/domain/npc_broken_recover_models.py): `NpcBrokenRecoverRequest(id, state, actor_id, willpower_profile, movement, fastest_route_confirmed, underlying_cause_allows_removal)`. State — полный NpcRosterCastingState, actor — Wizard-Champion либо living Minion. Нужны Broken и только поддержанные дополнительные Staggered/Drained, один зарезервированный unexecuted STANDARD Recover slot. Resolved Champion Wounds допустимы только с согласованными Staggered/Drained WoundConditionEffect; underlying Broken от активной Wound и другие ограничения не игнорируются. Normal InlineProfile без modifiers/Grim/Glorious задаёт caller; отсутствие этих modifiers — технический scope, не отмена книжных penalties.

`movement` — None для уже безопасного actor либо полный `FreeMovementRequest` с derived ID `request.id + ':free-move'`, exact actor/round/spatial/Conditions и актуальными path facts. Поддерживаются Slow/Normal/Fast free routes в их existing лимите. Slow может использовать обычный free move и Recover, но не может Run (PG1.4 Rules / Speed / Combat Actions / Manoeuvre, стр. 115–117). Предыдущее описание запрета Slow/free move было неточностью документации, исправленной с regression test 2026-10-26. Route должен закончиться на первой безопасной Zone, не пересекать препятствия/terrain/врагов и не использовать уже потраченный free move. Враждебность destination/intermediate Zones определяется по текущему roster: defeated/dead архивные entries не становятся врагами. Graph не доказывает Close/blocked route. Caller явно подтверждает быстрейший допустимый уход и возможность снять Condition; эти два bool обязательны и не имеют defaults. Движок не сравнивает альтернативные маршруты, не назначает GM facts и не вычисляет actor Speed из имени/числовых профилей.

[Executor/application](../../src/towr/engine/npc_broken_recover.py):

1. `execute_npc_broken_recover(request, rng)` исполняет existing `resolve_free_movement`, если нужно, затем один `execute_recover_action` в режиме REMOVE_CONDITION / BROKEN / WILLPOWER. Движение не создаёт receipt; успех и провал Recover создают один action receipt. Снятие Broken заменяет все standard Recover benefits: Staggered/Prone не снимаются, Miscast Pool не уменьшается, предметы/лечение не добавляются.
2. Только если actor — bound Wizard и `casting_lore_id is not None`, existing `resolve_skipped_casting_test_after_action` получает ровно этот Recover receipt и добавляет один action-sourced Miscast die. Free move сам по себе не пропускает Casting Test; ход другого actor не меняет магию Wizard. Девятки ordinary Recover Willpower не запускают Rule of Nine. После завершённого spell при неактивном Casting дополнительного die нет, даже если остался Miscast Pool.
3. `NpcBrokenRecoverResult(source, movement, recover, interruption)` сохраняет все lower-level results и проверяет exact sources, normal d10 trace/profile, движение и source-bound skipped-Test result. Derived `.state` переносит Conditions, spatial usage, round/receipt и одну запись общего execution ID; синхронизирует attached Champion roster/round, сохраняя Wounds, active effects, daily ledger и отдельные attack/roll histories. Не завершает ход, не истекает Wound effects, не выбирает следующего actor и не вызывает Cast/Miscast table.
4. `apply_npc_broken_recover_result(current, result)` принимает только весь exact current owner/history; repeated ID и stale/foreign snapshots отклоняются. Pure projection/application не двигают и не бросают повторно. При ошибке RNG source owner остаётся неизменным, partial move/Recover state не публикуется как завершённый owner; rollback RNG или автоматический retry не выполняются.

`NpcRosterCastingState.pending_interruption` — отдельный optional `SkippedCastingTestAfterActionResult` только для triggered Miscast. Он сохраняет exact Recover receipt, action-sourced increase, pool/successes/Lore и исходный MiscastRollRequest до preparation/desperate choice. Проверяются owner/magic/round/receipt/history и roll source/count; запрещено совмещать с другим обязательным pending. Normal bound Casting/preparation, Champion attack и ещё один Broken Recover блокируются. При pool == Level pending нет; при pool > Level successes/pool не очищаются и таблица не бросается. Это очередная честная остановка, не реализованный полный Miscast effect consumer. Ручное пересоздание owner с отброшенными pending/history остаётся вне гарантий pure snapshot API.

```python
result = execute_npc_broken_recover(request, rng)
current = apply_npc_broken_recover_result(current, result)
# current.pending_interruption requires its own continuation before dispatch.
```

[20 unit tests](../../tests/unit/test_m8_npc_broken_recover.py) и [3 integration tests](../../tests/integration/test_m8_npc_broken_recover.py) покрывают safe/moving actor, Normal/Fast routes, success/failure, обе стороны/Wizard/Minion, free/action usage, existing Conditions, shared histories, frozen/source/type/replay/stale guards и RNG failure. Real Curse → Broken Minion → free move → Recover проходит реальные K1 turns. Real Champion Wound/daily history сохраняется при Wizard Recover; Broken у мага в этом fixture задаётся явно, тест не объявляет поддержку Curse по Champion. Активный cast переносит successes, +1 die и pending при превышении Level; обычные Willpower 9 дают только один skipped die. Всего 166 M8 tests проходят; прежние 143 tests сохраняются.

Следующий на тот момент срез Broken Run реализован ниже. Terrain/Athletics/нет выхода требуют отдельного допуска или exact unsupported будущего runner. Далее end-turn Wound lifecycle и отдельный scenario/runner. Новых игровых Rule IDs или house rules нет.

## Broken Run в безопасную Zone

2026-10-26. Непосредственно перечитаны BOOK-PLAYER-GUIDE 1.4, Rules / Zones and Range, стр. 114; Speed, стр. 115; Combat Actions, стр. 116; Manoeuvre / Run, стр. 117; Recover, стр. 118; Conditions / Broken, стр. 122; Magic in the Old World / Interrupted Casting и Miscasts, стр. 156–157. Slow имеет обычный free move, но не может использовать Run. Normal/Fast Run добавляет одну Zone к свободному перемещению. Эти правила не меняются.

[NpcBrokenRunRequest](../../src/towr/domain/npc_broken_run_models.py) принимает `id, state, actor_id, movement, run_destination_zone_id, run_path_entity_ids, run_crosses_obstacle, run_crosses_difficult_terrain, fastest_route_confirmed`. State — прежний полный owner, movement — полный FreeMovementRequest с актуальными Speed/round/spatial/Conditions и derived ID `id + ':free-move'`. Все run route flags/fastest confirmation обязательны; ordered path копируется в tuple.

Первый допуск — живой Broken Champion/Minion с поддержанными Staggered/Drained и resolved Wounds без иных restrictions; один unexecuted STANDARD Manoeuvre/RUN slot. Нужен ещё не использованный полный Normal/Fast free move (1/2 Zones). Starting и все free-route Zones должны содержать живого врага, а одна соседняя Run Zone — быть безопасной. Так действие Run не подменяет уже доступное достижение безопасности по supplied free route. Dead/defeated архивные entries не становятся живыми врагами. Любой pending Miscast/movement/interruption/Champion attack блокирует вход до исполнения. Source, adjacency, Speed, route facts и once-per-turn usage проверяются до движения.

Caller подтверждает быстрейший допустимый маршрут; graph не доказывает геометрию Close/obstacles или отсутствие другого маршрута. Automatic pathfinding/GM choices не добавлены. Already-used free move, неполный Fast allowance, Slow Run, enemy/obstacle/terrain traversal, недостижимая за одну Run Zone безопасность, Athletics extension и случай без выхода остаются вне этого ограниченного контракта, без ожидания или фиктивного Recover.

`request.run_request` — pure projected RunActionExecutionRequest: full spatial после free move, тот же reserved slot/actor/Conditions/Speed и explicit Run route facts. Это проекция источника, не второй вызов movement resolver.

[Executor/application](../../src/towr/engine/npc_broken_run.py):

1. `execute_npc_broken_run(request)` вызывает existing `resolve_free_movement` и `execute_run_action` ровно по одному разу. В этой ветви нет Tests или RNG-параметра. Один receipt принадлежит Run, free move остаётся incidental.
2. Действующий Wizard с active Casting получает один skipped-Test die от существующего reducer по Run receipt; other actor/inactive Casting не меняют магию. Новый [общий validator](../../src/towr/domain/npc_action_interruption.py) проверяет exact receipt/pool/source/history у Recover и Run; прежний Recover API и алгоритм не меняются. Это проверка двух конкретных consumers, не общий dispatcher.
3. `NpcBrokenRunResult(source, movement, run, interruption)` проверяет exact source, непрерывность full spatial/round, canonical traces/receipt и interruption. Derived state переносит Run spatial/round и одну запись execution history; roster/Conditions/Wounds остаются прежними, attached Champion получает тот же round. Daily ledger, attack/roll histories, архивные placements и usage IDs сохраняются.
4. `apply_npc_broken_run_result(current, result)` принимает полный exact current source/history; stale/foreign/repeated results отвергаются. Projection/application не выполняют reducer/Test повторно. Ошибка исполнения не публикует partial owner; исходные frozen snapshots сохраняются.

```python
result = execute_npc_broken_run(request)
current = apply_npc_broken_run_result(current, result)
```

После Run actor достиг безопасности, но всё ещё Broken: стандартное действие потрачено, дополнительный Recover/Willpower или второй слот автоматически не выдаются. Staggered/Drained не снимаются. End-turn/expiry не вызываются; финальный active turn содержит исполненный Run slot. При pool > Level сохраняется прежний полный pending_interruption с Run receipt, исходным Miscast request и накопленными successes/Lore; normal dispatch блокируется до отдельного продолжения. Pool не очищается, desperate choice не выбирается, таблица не бросается.

[18 unit](../../tests/unit/test_m8_npc_broken_run.py) и [4 integration tests](../../tests/integration/test_m8_npc_broken_run.py): Normal/Fast, Wizard/Minion, один free move/Run, отсутствие RNG/Recover, source/type/path/replay/stale/receipt/pending guards, canonical trace, archived histories и отказ Run без partial state. Real Curse → Broken Minion → free move → Run и real Champion Wound/daily → Wizard Run сохраняют оба источника. Broken мага по-прежнему задаётся initial fact, не объявлением Curse по Champion. Дополнительный [Slow/free-move regression](../../tests/unit/test_m8_npc_broken_recover.py) закрепляет существующее корректное поведение; исправлена только прежняя неточная фраза документации. Всего 189 M8 tests проходят (23 новых проверки, включая regression); прежние 166 сохраняются.

Следующий срез — actor-bound end-turn Wound lifecycle: перенос нужных expiry/Condition transitions с source/turn guards и блокировкой при обязательном pending, затем отдельный scenario/runner. Terrain/Athletics и full Miscast effects остаются отдельными consumers. Новых игровых Rule IDs или house rules нет.

## Первый end-turn Wound lifecycle

2026-10-26. Непосредственно перечитаны BOOK-PLAYER-GUIDE 1.4, Rules / Wounds & Conditions, стр. 121–123; Wounds Table, стр. 190–191. Stomach Blow (6) даёт Drained до конца следующего хода цели (стр. 190). Condition существует в одном экземпляре, но ongoing cause не позволяет снять её до устранения причины (стр. 122). Истечение временного эффекта не лечит Wound, не выполняет Recover и не уменьшает untreated count (стр. 121).

[Source/clock records](../../src/towr/domain/npc_wound_turn_models.py) дополняют полный Casting owner двумя immutable ordered histories:

- `wound_expiries: tuple[NpcStomachBlowExpiry, ...]`. Bound Champion attack projection автоматически регистрирует полный accepted/resolved Stomach Blow result. Actor, exact historical Wound identity, effect, action ID, daily receipt и consumed roll history сверяются с текущим owner. Deadline получается из исходного attack round: текущий раунд, если цель ещё не завершила ход; следующий раунд, если завершила. Обычная внешняя атака не происходит в ходе цели. Caller не передаёт произвольный deadline.
- `wound_turn_end_receipts: tuple[NpcWoundTurnEndReceipt, ...]`. Phase ID, actor/round и expired attack IDs предотвращают повторный end-turn и возвращение уже истёкшего источника. Action history остаётся отдельной и не получает фиктивного действия.

Excluded target сохраняет законно полученный effect/source: accepted attack не отменяется из-за отсутствия будущей хронологии. Попытка завершить ход такой цели требует отдельного контракта и отклоняется. Own-turn Wounds и прочие источники timed effects не получают выдуманный clock.

[NpcWoundTurnEndRequest](../../src/towr/domain/npc_wound_turn_end_models.py) принимает `id, state, actor_id, condition_sources`. Первый допуск — живой активный Champion/Minion, один исполненный STANDARD slot, Conditions только Staggered/Drained/Broken. Wizard action уже должен пройти bound consumer с зарегистрированным receipt, чтобы end-turn не обходил skipped Casting. Все четыре pending (Miscast, movement, interruption, Champion attack) блокируют вход до scheduler. Unresolved Wounds, restrictions и другие Conditions, в том числе Ablaze/Critically Injured с обязательными end-turn Tests, отклоняются до исполнения.

У действующего Wizard каждый END_OF_NEXT_TURN effect должен иметь exact зарегистрированный источник и быть due именно в этом ходе; ранние, просроченные и untracked timers отклоняются. Для каждой истекающей Condition требуется ровно один `WoundConditionSourceSnapshot`. `has_other_active_source=False` запрещён, если остаётся известный Wound source; `True` сохраняет Condition от другой Wound или явно заданной внешней причины. Поддержанные неистекающие Staggered/Drained effects остаются. Завершение хода другого actor не меняет эффекты мага.

[End/application](../../src/towr/rules/npc_wound_turn_end.py):

```python
request = NpcWoundTurnEndRequest(
    'end:wizard', current, current.wizard.actor_id,
    (WoundConditionSourceSnapshot(Condition.DRAINED, False),),
)
result = end_npc_wound_turn(request)
current = apply_npc_wound_turn_end_result(current, result)
```

Executor вызывает existing `end_combat_turn` один раз. Result проверяет весь scheduler transition: source, completed actor/turn, round participants/order/history, next side, round-complete bool и Rule ID. Derived state атомарно переносит истёкшие effects/Conditions, full roster/round/attached Champion и phase receipt. Wound records/flags, WizardMagicState, spatial/usage, daily ledger и action/roll histories сохраняются. Pure application требует exact текущий snapshot и не исполняет scheduler/Tests повторно. RNG в этом переходе отсутствует.

[14 unit tests](../../tests/unit/test_m8_npc_wound_turn_end.py) и [4 integration tests](../../tests/integration/test_m8_npc_wound_turn_end.py) проверяют source/clock до и после хода цели, независимые sources, чужой actor, типы/immutable/replay/stale/pending guards, точный scheduler result и real Wound → Casting/Broken Recover/Broken Run → expiry. У Wizard Broken остаётся explicit initial fact; Curse по Champion этим не объявляется. Все 207 M8 tests проходят; прежние 189 сохранены.

Это первый timed transition, без общего lifecycle dispatcher. Gashed Brow/Blinded, прочие timed effects, многослотовые turns, terrain/Athletics и полные Miscast effects требуют своих consumers. Следующий срез — отдельный scenario/runner contract и finite probe с полным unsupported_path, objective и лимитом; production runner следует после контракта. Новых игровых Rule IDs/house rules нет.

## Отдельный scenario/runner contract

2026-10-26: [ADR-0037](ADR-0037-magic-scenario-runner.md) и [finite probe](../examples/m8/encounter_contract_probe.py) подготовлены после первого end-turn. Зафиксированы authored состав/политики, finite scene frames, objective/лимит, full source-bound steps/result и exact unsupported. Inventory выявил обязательный bound Minion → Minion handoff/acknowledgement/exclusion к magic owner и start/advance wrappers; готовый M2 executor их не заменяет. Probe проверяет 32 scripted d10 существующих API без общего loop; новые scenario constructors/четыре outcomes им не объявляются реализованными. Следующий срез — frozen scenario input/pure admission по ADR-0037, затем недостающие стыки и runner.

2026-10-26: первый implementation-срез [ADR-0037](ADR-0037-magic-scenario-runner.md#реализованный-typed-вход) завершён: typed frozen scenario/actor policies/facts/scene frames и pure admission. 31 новый deterministic test, 238 M8 суммарно. Probe начинает с production constructor без RNG; прежние 32 d10 и action chains сохранены. Следующий шаг — bound перенос одного Minion Attack к magic owner с full pending/двумя histories; acknowledgement/exclusion/start/advance и runner идут отдельно.
