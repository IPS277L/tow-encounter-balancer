# ADR-0035: первая граница Casting-действия для M8

Статус: принято как ограниченный технический контракт, 2026-09-29. Production models/executor ещё не реализованы. Пользователь выбрал **магию в боевой симуляции** после закрытия ADR-0034. Этот ADR задаёт первый необходимый узел интеграции, а не обещает завершённый бой с магами.

## Основание и инвентаризация

| Готовый слой | Что можно переиспользовать | Чего он не делает |
| --- | --- | --- |
| [Magic models](../../src/towr/domain/magic_models.py) | WizardMagicState, CastingTest/Decision, Miscast requests, formal spell/target/Potency contracts | Не связывает состояние с актуальным roster/ходом, не выбирает spell/target |
| [Casting action](../../src/towr/rules/casting_action_execution.py) | Один reserved spell Improvise, один Casting Test/receipt, проверенный post-Test и Miscast preparation | Caller отдельно собирает решение по post-pool state; target/effect не исполняется |
| [Casting decision](../../src/towr/rules/casting_decision_resolution.py) | CAST/WAIT, сброс накопленных successes после CAST, Potency последнего roll | Не задаёт тактику мага |
| [Spell preflight](../../src/towr/rules/spell_target_preflight.py), [targets](../../src/towr/rules/spell_cast_execution.py) | Тип subject, supplied Range, отдельные affected targets и Potency | Не обнаруживает существ в Zone, не применяет конкретный эффект |
| [Curse of Cowardly Flight](../../src/towr/rules/cowardly_flight_resolution.py) | Canonical definition, psychological preflight, Zone batch, Give Ground completion gate, ordered Willpower/Broken | Требует внешние snapshots/пути/решения; не исполняет следующие ходы Broken |
| [Miscast](../../src/towr/rules/miscast_resolution.py), [effects](../../src/towr/rules/miscast_effect_resolution.py) | Preparation/roll и отдельные reducers строк таблицы | Не имеет общего владельца spatial/injury/object/campaign effects, recent spells и GM choices |
| [Раунды/слоты](../../src/towr/rules/turn_resolution.py) | Actor/side/action slots/receipt, исполненные действия и смена раунда | Сам по себе scheduler не запрещает caller проигнорировать обязательный magic follow-up |
| M2/M7 NPC orchestration | Minion Attack, defeat, rounds, сценарии/summary/баланс | Нет Casting action dispatch или полноценной поддержки Champion-мага |

Книжные Hermit Witch и Daemonologist — **Champions**, а не Minions. Нельзя подменять их тип, Wounds Table или abilities ради текущего admission. Полный новый spell catalogue тоже не следует из наличия 42 нормализованных записей. Поэтому сначала связываем готовые K1 фазы одного действия; дальнейший battle runner получает отдельный контракт.

## Непосредственно проверенные источники

| Книга, глава, страница | Основание |
| --- | --- |
| BOOK-PLAYER-GUIDE 1.4, Rules / Combat Actions, стр. 116–117 | Casting использует spell Improvise; дополнительное действие не возникает из завершения spell |
| Та же книга, Magic in the Old World / The Anatomy of a Spell, стр. 155 | Wizard/Lore, CV, subject/Range/Duration |
| Та же книга, Casting a Spell / Interrupted Casting, стр. 156 | Exacting Willpower, одно действие за отдельный Test, Lore до Test, CAST после достаточных successes; armour/bulky item даёт Grim; skipped Casting и abandonment имеют последствия |
| Та же книга, Spell Potency / Miscasts and the Rule of Nine, стр. 157 | Potency последнего roll, неперебрасываемые 9, pool > Level, а не >=; обязательный Miscast, опциональный spell перед ним с +1d, очистка только после эффекта |
| Та же книга, Mixing the Winds / Disposing of Miscast Dice / Miscast Table, стр. 158–159 | Mixing — отдельный выбор, Recover/end-battle не бесплатный переход после каждого cast; разнообразные последствия таблицы |
| Та же книга, Formal Spells, стр. 160 | Memorised spell/свой grimoire; чужой grimoire даёт Grim |
| Та же книга, Battle Magic / Curse of Cowardly Flight, стр. 162 | CV 3, Zone, Long, Instant; все враги в Zone Give Ground если могут, затем Willpower против Potency, иначе Broken |
| Та же книга, Rules / Conditions / Broken, стр. 122 | Broken не равен defeat: следующий ход обязан учитывать уход/Recover |
| BOOK-GM-GUIDE 1.1, Allies and Antagonists / Champions, стр. 92; Hermit Witch и Daemonologist, стр. 130–131 | Champion injury model; Level 2, явные списки spells и отдельное once-per-round противодействие |

Новых Rule IDs/house rules нет. [ADR-0002](ADR-0002-book-first-resolution-kernel.md) и [ADR-0004](ADR-0004-round-turn-and-action-slots.md) сохраняются. Ограничения ниже — область технической поддержки и выбранная caller policy, а не запрет иных книжных действий.

## Первый поддерживаемый срез

Один уже активированный caster, одно зарезервированное **STANDARD spell Improvise** того же Battle Magic Lore и одно исполнение Curse of Cowardly Flight, если после Test достаточно successes. Результат возвращается **до end-turn/следующего действия**. Не строим battle loop, новый encounter objective или Monte Carlo summary.

Caster — явно заданный Wizard actor; неизменяемые source/Level/Willpower profile отделены от WizardMagicState. Этот узел не назначает caster injury policy и не объявляет его Minion. Caller подтверждает возможность Casting, знание Battle Magic и memorised Curse, отсутствие armour/bulky items, opposition, Mixing the Winds и дополнительных modifiers. Поддерживаются normal unopposed Tests, Wizard Level 1–4 и состояние с pool <= Level. Иной active Lore, уже обязательный Miscast, неготовый actor/slot или неподдержанные facts отклоняются **до RNG**.

Policy задаётся явно: **CAST_WHEN_READY** — если после нормального Test накоплено >=3 successes, немедленно CAST; иначе WAIT. Это разрешённая книгой стратегия, не обязательное поведение всех магов. Свежий вход и продолжение активного Battle Magic Casting допустимы, в том числе supplied накопленные successes >=3 после ранее выбранного WAIT. Последний roll с нулём successes может завершить такой cast с Potency 0.

Subject — существующая Zone с явным `target_zone_within_long_range=True`. Ordered target snapshots охватывают всех живых врагов в этой Zone; caller подтверждает полноту состава. Тип цели первого среза — healthy Minion, ProfileInjuryState(0,1), без исходных Conditions, Magic Resistance, Potency modifiers или psychological immunity. У всех affected enemies **can_give_ground=False**, задано по фактическому состоянию. Это условие допуска, не разрешение удержать способную уйти цель. Пустая Zone допустима.

Spatial snapshot сохраняет caster/участников и выбранную Zone. Сопоставляются actor IDs, стороны, размещения и target order; targets берутся в порядке round participants после фильтрации живых врагов выбранной Zone, а не из set. Все такие враги должны иметь ровно один target snapshot, союзники/caster не попадают в affected targets. Достоверность внешних фактов о доступности ухода/дальности не выводится из названия Zone. Первый срез не перемещает существ и не выбирает за GM.

Почему именно этот spell: его конкретный effect reducer уже готов, источник не наносит Damage и не требует добавить ещё один kernel или трактовать spell как weapon Attack. Изолированная граница позволяет получить точные состояния Broken, не притворяясь, что текущий M7 умеет следующий ход такой цели.

## Планируемые typed APIs

Новые узкие модули `domain/cowardly_flight_casting_models.py` и `engine/cowardly_flight_casting.py`; CLI/adapters/balance не импортируются.

- `CastingCasterDefinition(id, source_rule_id, wizard_level, casting_profile: InlineProfile)` — immutable описание мага, без injury/round state.
- `CowardlyFlightCastingTarget(actor_id, willpower_profile: InlineProfile, injury: ProfileInjuryState, can_give_ground)` — текущий target snapshot с указанным выше допуском.
- `CowardlyFlightCastingFacts` — обязательные bool `caster_can_cast`, `knows_battle_magic`, `spell_memorised`, `caster_unarmoured`, `no_bulky_items`, `no_casting_opposition`, `no_mixing_winds`, `no_other_test_modifiers`, `no_potency_modifiers`, `no_effect_immunities`, `all_zone_enemies_included`, `target_zone_within_long_range`; в первом срезе все true.
- `CowardlyFlightCastingRequest(id, caster, actor_id, round_state, slot_index, magic_state, spatial_state, selected_zone_id, targets, facts, policy)` — полный admitted source; создание CastingTest/Action requests и стабильных derived IDs принадлежит executor.
- `CowardlyFlightCastingResult` — exact source, единственный CastingAttemptExecutionResult, CastingActionPostTestResult, returned round/magic/target/spatial snapshots, optional preflight/target execution/Zone batch/Willpower batch, typed status и источник обязательного Miscast при остановке.
- `execute_cowardly_flight_casting(request, rng)` — один вызов с внедряемым RNG, без global random, retry или выбора нового spell. Generic effect dispatcher/DSL не добавляется.

Все модели frozen/slotted; ordered snapshots копируются в tuple. Result проверяет источники и соответствие ветки вложенным данным, а не только IDs. Wrong types, duplicate/missing/foreign actor/target, несовпадающие состояния и forged branch combinations отвергаются. Изменяемое состояние боя остаётся отдельным от caster definition.

## Порядок исполнения и состояния результата

1. Проверить весь input/слот/known scope до RNG. Выполнить `execute_casting_attempt` ровно один раз; он сохраняет Casting trace, Rule of Nine и единственный action receipt.
2. По готовому Casting result подготовить точный post-pool snapshot для решения через existing pure pool resolver. `resolve_casting_action_post_test` заново проверяет тот же source; это чистая проверка, не повторный бросок или второе накопление пула. Не передавать ему уже изменённый initial Casting result.
3. **WAITING**: CV не достигнуто. Сохранить накопленные successes/Lore/latest roll и pool. Нет spell/target Tests; действие уже потрачено. Следующий ход создаёт caller из возвращённого состояния.
4. **MISCAST_REQUIRED**: pool > Level. Решения CAST/WAIT нет. Сохранить exact post-Test state, receipt и исходный MiscastRollRequest из post-test result. Не терять successes вручную, не выбирать отказ от desperate cast, не бросать таблицу и не очищать pool. До `prepare_casting_action_miscast` ещё предстоит отдельное обязательное решение/исполнение. Повторный normal casting с этим состоянием запрещён admission.
5. **SPELL_RESOLVED**: normal CAST. Existing decision сбрасывает Casting successes/Lore/latest roll, но сохраняет pool; затем schema/Range preflight → target Potency → Curse Zone batch → Willpower batch. Все операции имеют точные источники; движение пусто по допуску. Willpower Tests идут в стабильном target order тем же RNG. Возвращаются реальные Condition transitions. При Potency 0 или пустой Zone дополнительных Tests нет.

Статусы описывают **действие**, не победу/поражение/round_limit. MISCAST_REQUIRED — остановка на неподдержанном обязательном пути, а не успешное завершение магии. Будущий encounter adapter обязан либо разрешить pending фазу, либо выдать unsupported_path; игнорировать её и продолжить бой нельзя. Broken сохраняется как Condition и не конвертируется в defeat или achieved objective.

Result не завершает ход/бой и не делает end-battle Recover. Единственный receipt остаётся исполненным и при WAIT/Miscast. Передача returned round state запрещает повтор того же слота; воспроизведение из прежнего immutable input с тем же scripted RNG является replay вычисления, а не доказательством актуальности устаревшего состояния. Владение текущим состоянием и future result consumption остаются у battle orchestration. Исключения сохраняют причину, RNG не откатывается; частичный нормальный result не возвращается.

## Проверочный пример и границы доказательства

[Finite probe](../examples/m8/casting_contract_probe.py) соединяет только **existing public K1 APIs**. Два supplied activations передают returned magic state: 1 success → WAIT, затем 2 successes → CAST CV3/Potency2, одна цель сопротивляется, другая получает Broken. Дополнительно проверены zero-Potency cast, empty Zone, pool == Level / > Level, исполненный slot и чужой actor до RNG. Всего 24 scripted d10; глобальный RNG не меняется. Это не новый M8 executor, admission validator или сценарий полного боя. Переход между активациями задаёт caller, probe не симулирует промежуточные ходы.

До реализации отдельно проверить deterministic source/type/facts admission, все branch invariants, exact target order, пустые/no-effect ветки, trace/receipt/replay и несколько активаций с возвращённым WizardMagicState. Ошибки запроса не должны расходовать RNG. Existing K1 tests остаются источником evidence для отдельных reducers, но не заменяют будущие tests нового composition boundary.

## Что отложено и порядок следующих шагов

1. **Следующий срез:** pure frozen input models и preflight нового boundary; без executor/RNG.
2. Result models и один executor по указанным трём веткам; deterministic unit/integration с существующим scheduler/K1.
3. Аудит boundary и public production example. Затем отдельный контракт перехода к полноценному magic encounter: caster injury model, action dispatch, следующие ходы Broken и обязательные Miscast outcomes.

Miscast effects, desperate spell до таблицы, Recover/interruption/abandonment, Mixing/opposition/Dispeller, spell damage, длительные эффекты, движение, PC/Champion wounds в encounter, массовые прогоны, метрика и JSON/CLI магии здесь не реализуются. Это последующие зависимости M8, не отмена выбранного пользователем направления. **Нельзя выдавать этот первый boundary за поддержку полного боя с магами или подавлять Miscast для получения оценок баланса.**

`AMBIGUITY-002` о Magic Resistance и открытые вопросы recent spell/пустой истории Spell Recast, objects/ranges таблицы Miscast остаются открытыми. Текущий допуск их не использует и не выбирает house rule. При подключении соответствующих последствий потребуется отдельное решение по существенной неоднозначности.
