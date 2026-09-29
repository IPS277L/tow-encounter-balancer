# ADR-0035: первая граница Casting-действия для M8

Статус: принято как ограниченный технический контракт, 2026-09-29. Input/preflight, result models и executor реализованы и закрыты [аудитом](../audits/m8-casting-readiness.md) в указанной границе одного действия. Standalone production-пример проверен; следующий шаг — контракт magic encounter. Пользователь выбрал **магию в боевой симуляции** после закрытия ADR-0034. Этот ADR задаёт первый необходимый узел интеграции, а не обещает завершённый бой с магами.

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

## Typed APIs

Узкие модули `domain/cowardly_flight_casting_models.py`, `domain/cowardly_flight_casting_result_models.py` и `engine/cowardly_flight_casting.py`; CLI/adapters/balance не импортируются. Result/guards отделены от input для читаемости.

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

1. Pure frozen input models и preflight нового boundary реализованы; без executor/RNG.
2. Result models и один executor по указанным трём веткам реализованы; 24 unit и 2 integration tests с существующим scheduler/K1 прошли.
3. Аудит boundary и public production example завершены. **Следующий срез:** отдельный контракт перехода к magic encounter: caster injury model, action dispatch, следующие ходы Broken и обязательные Miscast outcomes, с инвентаризацией необходимых consumers до реализации runner.

Miscast effects, desperate spell до таблицы, Recover/interruption/abandonment, Mixing/opposition/Dispeller, spell damage, длительные эффекты, движение, PC/Champion wounds в encounter, массовые прогоны, метрика и JSON/CLI магии здесь не реализуются. Это последующие зависимости M8, не отмена выбранного пользователем направления. **Нельзя выдавать этот первый boundary за поддержку полного боя с магами или подавлять Miscast для получения оценок баланса.**

`AMBIGUITY-002` о Magic Resistance и открытые вопросы recent spell/пустой истории Spell Recast, objects/ranges таблицы Miscast остаются открытыми. Текущий допуск их не использует и не выбирает house rule. При подключении соответствующих последствий потребуется отдельное решение по существенной неоднозначности.

## Реализованный input/preflight

[Модели](../../src/towr/domain/cowardly_flight_casting_models.py) проверяют допуск в constructors; отдельного executor или вызовов K1/RNG нет. `CowardlyFlightCastingPolicy.CAST_WHEN_READY` обязателен без default. `CastingCasterDefinition.id` — ID повторно используемого определения, не actor ID; только request связывает definition, actor и caller-supplied WizardMagicState. Последний не содержит actor ID, поэтому история его принадлежности остаётся ответственностью caller. Профили — InlineProfile без custom pool cap, facts охватывают также target Willpower.

Уточнения технической границы: требуется ровно один зарезервированный, неисполненный standard slot 1 с Battle Magic spell Improvise без признака Attack. Spatial round совпадает с CombatRoundState; placements охватывают ровно всех участников и сохраняют стороны. Это не admission промежуточного battle snapshot с удалёнными defeated участниками. Completed/excluded turn IDs сами по себе не исключают врага из эффекта: такой ID описывает доступность хода, не injury. Все враги выбранной Zone обязаны иметь healthy target snapshot в порядке round participants; spatial order произволен. Пустая Zone допустима. Spatial turn history сохраняется, не очищается. Range и can_give_ground не выводятся из графа.

[23 deterministic tests](../../tests/unit/test_m8_cowardly_flight_casting_models.py) покрывают свежий/WAIT input, pool == Level и обязательный Miscast, slot/actor/Lore, настоящий K1 executed receipt, полный target состав/порядок/стороны, пустую Zone, обе стороны caster, сохранение spatial history, wrong types/facts, immutable tuple-copy и отсутствие исполнения/RNG. Вместе с 177 связанными K1 tests — 200 OK. Книжные правила не менялись; result/executor добавлены следующим срезом ниже, full encounter ещё отсутствует.

## Реализованный result/executor

[Executor](../../src/towr/engine/cowardly_flight_casting.py) принимает admitted request и RNG. CastingAttempt исполняется один раз; pure post-pool projection нужна для явного CAST_WHEN_READY, затем post-Test проверяет исходный Casting result. WAIT и mandatory Miscast возвращаются без target Tests. В normal CAST выполняются canonical preflight → target Potency → Curse Zone batch → ordered Willpower. Пустая Zone и Potency 0 сохраняют полноценные фазовые результаты без дополнительных бросков. End-turn/Recover/Miscast preparation не выполняются.

[Result](../../src/towr/domain/cowardly_flight_casting_result_models.py) хранит `source`, `execution`, `post_test`, `status` и optional `preflight`, `spell`, `zone`, `willpower`. Для SPELL_RESOLVED обязательны все четыре spell-фазы; для WAITING/MISCAST_REQUIRED они запрещены. `round_state`, `magic_state`, `spatial_state`, `targets` и `pending_miscast` — вычисляемые read-only свойства из проверенных вложенных данных, без второго независимо передаваемого снимка. `targets` — tuple из `CowardlyFlightCastingTargetState(actor_id, injury)`: выход допускает Broken и потому не переиспользует healthy-only входной тип. Target order и unchanged/no-effect цели сохраняются.

Guards связывают action/source round, профиль и normal RollTrace, accumulated/latest successes, Rule-of-Nine pool, decision/CV/Potency, canonical definition/subject, каждый target effect/context и Willpower/Broken/spatial state. Проверка trace только сверяет записанные значения d10/профиль/итоги, не вызывает resolver или RNG. Same-ID splice другого состояния, профиля, уровня, цели, порядка, ветки или pending Miscast отклоняется. Full source не удостоверяет внешние GM facts или исторического владельца actor-agnostic WizardMagicState. Старый immutable input остаётся воспроизводимым; returned executed slot повторно не допускается.

Canonical `COWARDLY_FLIGHT_SPELL_DEFINITION` хранится в domain/magic_models.py; прежний `towr.rules.cowardly_flight_resolution` реэкспортирует тот же объект. Значения и Rule ID не изменились. Это позволяет domain guards проверять полное определение без обратного импорта rules. Stable derived IDs: request ID для action receipt; `:casting`, `:willpower`, `:post-test`/`:decision`, `:preflight`, `:zone`, `:willpower-batch` для соответствующих фаз. Вложенные target IDs формируются existing K1. Исключения проходят без retry/partial result и без отката RNG.

[24 unit tests](../../tests/unit/test_m8_cowardly_flight_casting.py) и [2 integration tests](../../tests/integration/test_m8_cowardly_flight_casting.py) проверяют три ветки, trace/source guards, latest Potency, pool == Level / > Level, отсутствие rerolls, нулевую Potency, пустую Zone, natural single die, Willpower 9 без влияния на pool мага, повторяемость, ошибки и реальные scheduler transitions. В integration остальные участники явно выполняют Recover со своим пустым magic state; pool ожидающего мага не очищается между раундами. Это проверка нескольких действий, не готовый battle runner. Следующий шаг — аудит и standalone production example, затем отдельный контракт полноценного magic encounter.

Проверка реализации 2026-09-29: 226 связанных tests и полный набор 2713 tests — OK (395,812 с); `compileall`, public K1 probe и `git diff --check` успешны. Последующий аудит и standalone production example описаны ниже.

## Завершённый аудит

[Аудит](../audits/m8-casting-readiness.md) подтвердил текущий контракт без production-исправлений. [Самостоятельный пример](../examples/m8/casting_action.py) и [сохранённый вывод](../examples/m8/casting_action.output.txt): шесть supplied activations, 24 scripted d10, все три ветки, latest Potency/Broken, нулевая Potency и empty Zone, запрет повторного returned slot/чужого actor/pending Miscast до RNG. Новый subprocess test проверяет запуск вне cwd; 50 tests M8, 227 вместе со связанным K1 — OK. Offline wheel собран/установлен в отдельный build target, происхождение импортированного engine проверено, вывод совпал. Полный suite последней реализации остаётся 2713 OK; в аудите добавлен один test и production не менялся. Следующий этап — отдельный контракт magic encounter, не автоматическое подключение к M7.
