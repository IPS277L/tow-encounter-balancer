# ADR-0037: первый scenario/runner с Champion-Wizard

Статус: принят как ограниченный технический контракт, 2026-10-26. Production scenario input/pure admission **реализованы**; result/runner ещё не реализованы. [ADR-0036](ADR-0036-magic-encounter-integration.md) задаёт владельцев отдельных действий и обязательных продолжений; этот ADR фиксирует их композицию. [Конечный probe](../examples/m8/encounter_contract_probe.py) проверяет admission, существующие API и оставшиеся стыки, без эмуляции будущего runner.

## Источники и граница

Локальные постраничные тексты прочитаны непосредственно, не только changelog:

| Книга, глава, страницы | Следствие |
| --- | --- |
| BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions и Champions, стр. 91–92 | Minion выбывает от одной Wound, Champion использует Wounds Table. Авторский маг не становится Minion ради старого runner. |
| BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112 | Полный ход одного actor, затем следующий; обычный порядок сторон сохраняется между раундами. Порядок внутри стороны выбирается явно. |
| Та же книга, Rules / The Battlefield / Zones and Range, стр. 114 | Zone и Close — разные факты; совпадение Zone не доказывает Close. Геометрия/обзор не выводятся из названий Zones. |
| Та же книга, Rules / Recover, стр. 118; Attack Tests / Giving Ground, стр. 118–119 | Protection и range modifiers проходят через K1; Give Ground один раз за раунд. Recover для удаления Condition заменяет standard benefits. |
| Та же книга, Rules / Conditions / Broken, стр. 122 | Broken требует ухода в безопасную Zone, с Manoeuvres при необходимости; сам по себе не является defeat. Неизвестный маршрут не разрешает ожидание. |
| Та же книга, Magic in the Old World / Casting a Spell / Interrupted Casting, стр. 156; Spell Potency / Miscasts, стр. 157; Miscast Table, стр. 159 | Successes/pool переносятся между ходами; skipped Casting имеет последствия; pool очищается после эффекта Miscast. Preparation/table lookup без consumer не завершают эффект. |
| Та же книга, Battle Magic / Curse of Cowardly Flight, стр. 162 | CV3, Long, цель Zone; сначала обязательный Give Ground, затем Willpower исходных целей против Potency. |

Wound/Drained expiry сохраняет уже проверенные PG1.4, Rules / Wounds & Conditions, стр. 121–123 и Wounds Table, стр. 190–191; контракт самого перехода — в ADR-0036. Новых игровых Rule IDs/house rules нет. Objective, лимит и тактика — явно выбранные параметры эксперимента, не новые книжные правила победы.

Первый состав: ровно один authored Champion-Wizard Level 1–4, Battle Magic/memorised Curse, хотя бы один союзный и один вражеский Minion. Wizard может быть на любой стороне, но порядок сторон обычный `PLAYERS_AND_ALLIES → OPPOSITION`, без ambush. Его числа имеют authored provenance; это не неполный профиль именованного книжного NPC. Wizard не имеет weapon Attack, armour/shield/bulky items. Каждый Minion имеет один обычный числовой Shooting profile и Athletics Protection; без reload, Aim, extra effects, shields и специальных Abilities. Скорость задаётся явно `MovementSpeed`, не выводится из имени. Начальные Wounds/Conditions, активный cast/pool и histories пусты.

Сцена замкнутая: все combatants находятся в roster, нет внешних Condition sources, hidden actors, изменения декораций, cover/concealment, terrain/obstacles, mounts, Fate/bonus slots, дополнительных spells, opposition/Mixing/Magic Resistance. Это проверяемый допуск первого сценария. Полученное в бою неподдержанное состояние сохраняется и останавливает исполнение, а не объявляется отсутствующим из-за начального допуска.

## Реализованный typed вход

[Scenario/facts/actor policies](../../src/towr/domain/npc_magic_scenario_models.py) и [scene models](../../src/towr/domain/npc_magic_scene_models.py) доступны как typed Python API. Это frozen/slotted domain models с ordered tuple copies и строгими enum/bool/int guards; domain не импортирует engine/rules/CLI/balance, не исполняет действия/Tests и не получает RNG. Сохраняются полные определения/факты, включая False в GM approvals, без нормализации в «всё разрешено». Step/result/unsupported/runner ниже остаются контрактом.

`NpcMagicScenario`:

| Поле | Контракт |
| --- | --- |
| `id: str` | Непустой namespace для детерминированных request/receipt IDs. |
| `initial: NpcRosterCastingState` | Полный roster, Wizard, round/spatial и open `DailyWoundState` Champion. Round 1, без active/completed/excluded turns, pending, injuries и histories; исходные Resilience/equipment/availability совпадают с definitions. Champion owner обязателен. |
| `facts: NpcMagicScenarioFacts` | Явное подтверждение ограничений сцены/профилей выше; неподтверждённое ограничение отклоняется до RNG. GM approvals конкретных атак хранятся отдельно и могут быть False. |
| `activation_order: tuple[str, ...]` | Все actor IDs ровно один раз. При каждой активации берётся первый живой, ещё не завершивший ход actor текущей стороны; порядок внутри стороны сохраняется, чужая сторона не опережает scheduler. |
| `actors: tuple[NpcMagicActorPolicy, ...]` | Все и только участники, в порядке roster. Willpower profile, Speed, роли и следующие policies явно связаны с actor ID. |
| `scene_frames: tuple[NpcMagicSceneFrame, ...]` | Конечный набор явных пространственных контекстов; начальный frame обязателен. Непокрытое последующее положение приводит к точной остановке, не к догадке. |
| `perspective_side: CombatSide` | Независима от стороны Wizard и очередности ходов. |
| `objective: NpcDefeatObjective` | Полный ordered список всех противников perspective, каждый ровно один раз. Объект IDs переиспользуется; Minion-only assessment из M2 для Champion не вызывается. |
| `max_rounds: int` | Положительный int, bool запрещён; общий предел начатого сценария, не новый бюджет на каждое продолжение. |
| `repeated_stagger_choice: StaggerChoice` | Явный SUFFER_WOUND, отдельно от обязательного Give Ground Curse. |
| `spell: FormalSpellDefinition` | Полный canonical COWARDLY_FLIGHT_SPELL_DEFINITION; подмена Lore/CV/Range/Duration/Rule ID отклоняется. |

`NpcMagicActorPolicy` содержит actor_id, normal willpower_profile без custom cap, explicit MovementSpeed, target_actor_ids/defeat_decisions/attack_id либо casting_policy/zone_priorities. Политики идут точно в roster order; activation order, target priorities и Zone priorities независимы и сохраняют supplied порядок. Willpower мага совпадает с его CastingCasterDefinition. Facts явно подтверждают authored Wizard и знание/меморизацию spell; строка provenance сама не доказывает отсутствие иных правил. Все 20 scope flags типизированы; requires_reload_action обязано быть False, остальные — True.

Policy мага: `CAST_WHEN_READY`, полный приоритет Zones без повторов, со всеми graph Zone IDs. Выбирается первая Zone в Long или ближе, содержащая живого врага. Empty Zone/нулевая Potency не считаются победой. Если живые враги есть, но ни одна их Zone недоступна по явным фактам, остановка до Casting Test, без автоматического abandonment/перемещения/добавления skipped die.

Policy Minion: единственный attack ID, ordered приоритет **всех** противников, включая Wizard, и `MinionDefeatDecision` для каждого потенциального Minion-target. Decisions содержат explicit GM confirmation и выбранный disposition, без автоматического убийства. Цель — первая живая и доступная по текущим фактам. Живой Champion с неподдержанным Condition не пропускается ради следующей удобной цели: это остановка выбранного пути. Broken actor сначала исполняет свой обязательный ход, а не Shooting. Standard self-Recover вне Broken, Leadership, fallback weapon/tactics в первый контракт не входят.

На старте каждый Minion имеет хотя бы одну допустимую цель Shooting без любого Close-врага, а Wizard — хотя бы одну Zone с врагом в пределах Long. Эти начальные факты проверяются до RNG. После движения/выбывания отсутствие доступной цели уже является runtime stop; приоритеты не переписываются под оставшиеся удобные цели.

Repeated Staggered policy первого сценария — явно переданный `StaggerChoice.SUFFER_WOUND`, как допустимый выбор K1. Он не распространяется на обязательный уход Curse: для Curse `can_give_ground=True` всегда требует движения.

## Конечные frames вместо выдуманной геометрии

Frame key — полный ordered `SpatialEntityPlacement` для исходного roster, включая архивные entries, плюс ordered IDs живых actors. Живой Minion — не defeated, живой Champion — не dead. Same IDs/positions с иным составом живых — другой key. Side/Zone каждого placement сверяются с definitions/graph. Round и once-per-round histories не входят в key геометрии: берутся из текущего owner при каждом запросе, не из frame.

Публичный key — `NpcMagicSceneKey(placements, live_actor_ids)`. Placements сохраняют независимый исходный spatial order, live IDs — roster order. `initial_frame` находит единственный exact initial key; `frame_for(key)` возвращает supplied frame либо None, не генерирует факты. Дублированные keys запрещены; отсутствие будущих frames допустимо.

Frame содержит:

- Все и только неупорядоченные hostile live пары с явным `RangedWeaponRange`, без self/friendly/duplicate/unknown пар. Close/Short требуют той же Zone в первом допуске; Medium/Long совместимы с заданными соединениями, но graph сам не назначает Range. Extreme может явно исключать Shooting/Curse; отсутствие строки не означает «слишком далеко». Для Shooting проверяются **все** Close-враги стрелка, а не только выбранная цель; –1d outside optimum остаётся за existing preparation.
- Дальность от текущей Zone мага до каждой Zone в его policy, включая пустые. Полнота/GM факты не подменяются количеством живых целей.
- Explicit departure/route facts и выбор Give Ground для каждого потенциального живого target: соседняя destination либо подтверждённая фактическая невозможность. Missing route не равен `can_give_ground=False`. Conditions, once-per-round usage и враги на пути проверяются по текущему owner. После каждого ухода используется актуальный spatial; новый frame нужен для следующего зависящего от позиции решения.
- Для каждого actor допустимый Broken plan: safe self-Recover; полный legal free move до первой безопасной Zone + Recover; либо полный Normal/Fast free move + одна Run Zone. Routes/Speed/fastest confirmation сохраняются явно, без pathfinding. При отсутствии подходящего плана — unsupported, без фиктивного ожидания. Slow free move допускается, Slow Run — нет (готовый ADR-0036 boundary).

Из frame и текущего owner строятся source-bound запросы existing API. Совпавший frame не разрешает действие при неподдержанных injuries/Conditions. После нового Wound/defeat/движения старый snapshot не переиспользуется. Полное покрытие всех случайно достижимых frames заранее не требуется; неполное покрытие отражается в `UNSUPPORTED_PATH`. Это конечные факты одной сцены, не язык правил, event bus или универсальный тактический provider.

Реализованные concrete values: `NpcMagicPairRange(first_actor_id, second_actor_id, target_range, first_range_approved_by_gm, second_range_approved_by_gm)`; `NpcMagicZoneRange(zone_id, target_range)`; `NpcMagicRouteFacts(path_entity_ids, crosses_obstacle, crosses_difficult_terrain)`. Pair ranges симметричны, два approvals направлены от соответствующего actor. True разрешён только там, где existing preparation требует GM approval для two-handed Shooting beyond Optimum; False сохраняет отказ. Для Extreme/Aim и Wizard approval не применим. Начальная доступность проверяется с учётом отказа, any Close enemy и текущего Optimum; –1d не вычисляется admission повторно.

Give Ground plan содержит actor_id, can_leave_zone, destination/route либо explicit impossible_confirmed. Missing destination без подтверждения невозможности отклоняется. Broken plan содержит actor_id, один из SAFE_RECOVER/FREE_MOVE_RECOVER/FREE_MOVE_RUN, ordered free_move_zone_ids/route, optional Run destination/route и fastest_route_confirmed. Проверяются adjacency/away, Speed, first safe Zone/full unsafe free route, safe Run destination, path actors и отсутствие terrain/obstacles. Fastest choice остаётся supplied фактом; distance traversal только сверяет совместимость graph/range и away, не выбирает маршрут. Broken plans можно не задавать для неподдержанных ситуаций. Every supplied frame проверяется по тем же definitions/graph, архивные entries не становятся живыми blockers/route actors; сама проверка frame не авторизует текущий injury/turn.

Для многотаргетного Curse вся ordered Give Ground chain сначала строится existing pure movement reducers, с lookup frame для каждого промежуточного spatial. До полной chain root остаётся в MOVEMENT_REQUIRED; движения не публикуются по одному как будто уже завершённый spell. Missing frame/route сохраняет этот root pending, точный required scene key и typed staged movement prefix в диагностике. После полной chain bound completion выполняет Willpower Tests и один атомарный перенос результата. Ни одно движение, reducer или Test не исполняется повторно ради application.

## Единый владелец и недостающие стыки

Сохраняется узкий `NpcRosterCastingState` ADR-0036. Планируется добавить optional `minion_attack: NpcRosterAttackState` и полный `pending_minion_attack: NpcRosterAttackExecutionResult | None`, по аналогии с attached Champion owner. Pure admission первого среза принимает существующий начальный substrate без этого расширения. Отдельный runtime initializer второго среза один раз присоединяет пустой ledger до первого действия; initial runtime state выводится точно из сохранённого scenario source, без action receipt/RNG. Во всех переходах ordered roster один и тот же; общая root execution history содержит обе attack families/Casting/Broken actions, семейные ledgers сохраняют свои subsequences. Нельзя заново создать пустой `NpcRosterAttackState` при каждой атаке. Любой pending одной семьи блокирует остальные до completion.

При добавлении Minion owner потребуется синхронизировать его также в существующих Casting/completion, Champion attack, Broken и expiry projections. Обновлять только attack handoff недостаточно: изменение Condition цели в Curse тоже меняет общий roster. Это часть второго среза и его regression tests, без изменения RNG/правил прежних consumers.

| Компонент | Что уже есть | Что требуется перед loop |
| --- | --- | --- |
| Casting и Curse movement | Bound request/result/application, MOVEMENT_REQUIRED и source-bound completion | Scene facts/zone policy и вызов continuation до end-turn. |
| Minion → Champion | Bound attack, daily ledger, Wound registration/effects и full pending | Точный pre-dispatch admission по текущим Conditions. Bridge сейчас допускает только Staggered и resolved Wounds без active effects; Drained/Broken target нельзя тихо атаковать без этого допуска. |
| Minion → Minion | M2 request/result/application; отдельно acknowledgement и exclusion | **Нового bound handoff к magic owner пока нет.** Нужны source/replay guards, синхронизация roster/round/attached ledgers и полный pending, затем bound acknowledgement/exclusion без второго Attack. |
| Broken | Bound safe/free-move Recover, Run и skipped Casting | Выбор explicit plan из текущего frame; unsupported для иных маршрутов. |
| End-turn | Bound Stomach Blow expiry, phase receipts, pending guards | Применение после завершения on-action последствий. Другие Conditions/effects сохраняются и останавливают путь. При closed scene source snapshots выводятся из оставшихся известных Wounds, без внешней причины. |
| Start/advance/archive | K1 turn/slot/round и spatial reducers | Отдельные full-owner wrappers с проверкой полного source и результата; raw scheduler result сам по себе не доказательство корректного переноса owner. |

Minion defeat сначала подтверждается supplied decision, затем исключается из ещё ожидающих ходов. Если уже завершил ход, второй completed/excluded marker не создаётся. Dead Champion также исключается; Defenceless/Prone/Broken не приравниваются к смерти. Архивные roster/placements сохраняются и не становятся живыми combatants. При advance используются полный roster/round participants и исключения dead/defeated, а live projections готовятся отдельно; иначе существующий root invariant roster/round нарушится. Spatial usage обновляется existing `start_next_spatial_round`, все action/daily/roll/expiry/phase histories сохраняются. Новый день/Infection/healing автоматически не открываются.

## Исполнение, остановки и результат

Планируемая сигнатура: `run_npc_magic_scenario(scenario: NpcMagicScenario, rng: RandomSource) -> NpcMagicScenarioResult`. Один внедрённый RNG на вызов; сценарий/глобальный RNG не меняются. Непредвиденные исключения и BaseException проходят наружу, без retry/fallback или partial success.

Порядок исполнения:

1. Проверить typed scenario до любого RNG. До выбора следующего actor закрыть имеющееся обязательное continuation. Полный pending приоритетнее Broken, normal policy и любого terminal check. Неподдержанный continuation даёт stop с точным owner.
2. Если есть уже исполненный action, сначала его end-turn/terminal checks из п. 5. Иначе выбрать actor текущей стороны и ровно один STANDARD slot, с детерминированными IDs в namespace сценария; новый actor не опережает обязательное завершение предыдущего.
3. Из текущих live actors/placements выбрать frame, затем Broken plan либо Casting/Shooting policy. Сверить supporting admission **до** вызова narrow constructor. Известный unsupported не ловится общим `except ValueError` от произвольного кода.
4. Исполнить один существующий action executor. Применить result к exact полному source один раз; выполнить поддержанные Give Ground/Willpower/Minion acknowledgement continuations. Если выбранный путь не поддержан, сохранить весь уже полученный post-roll state, receipts и pending, без новых Tests.
5. Завершить ход bound end-turn, включая due expiry. Если оно не поддержано, stop раньше outcome/лимита. Затем проверить objective, поражение perspective и только затем завершённый round limit. Для следующего раунда выполнить bound round/spatial advance.

Четыре **будущих**, отдельных от M7 enum outcomes:

| Outcome | Условие |
| --- | --- |
| `OBJECTIVE_ACHIEVED` | Все objective targets defeated (Minion) или dead (Champion), все обязательные последствия и текущий end-turn закрыты. |
| `PERSPECTIVE_DEFEATED` | Все actors perspective defeated/dead; objective ещё не достигнут. |
| `ROUND_LIMIT_REACHED` | Оба предыдущих условия false; завершён последний допустимый раунд, нет обязательного pending. |
| `UNSUPPORTED_PATH` | Точный обязательный continuation/admission/scene/tactical path не поддержан. Outcome не считается победой, поражением или обычным лимитом. |

Objective-first при совпадении terminal predicates — явный технический приоритет оценки, как у прежних bounded scenarios. Broken, уход в другую Zone и пустая target Zone сами не удовлетворяют defeat objective. Проверка лимита не запускает новый turn/slot/каст. Post-battle Recover/treatment/healing — отдельная opportunity, не часть combat result.

`NpcMagicScenarioResult` сохраняет полный `source`, ordered closed-union `steps`, derived `current` owner, outcome и optional `unsupported`. `current` вычисляется по непрерывной chain, не принимается независимо от неё. Каждый step связывает полный before/after owner и конкретный typed reducer result; foreign source/actor/round, дубликат receipt/phase ID, пропуск pending, заменённый order/facts/policy и незаконный terminal suffix отклоняются без нового RNG. Будут отдельные counters начатых/завершённых раундов и исполненных actions: начало раунда не выдаётся за его завершение.

`NpcMagicUnsupported` имеет typed `phase`, `reason`, actor ID (None только до выбора actor), точный source ID и ordered missing actor/Zone IDs. Для missing scene хранится `required_scene_key`; только для staging Give Ground разрешён проверенный `staged_movements` prefix, принадлежащий текущему pending. Полный pending result остаётся в `current` и соответствующем step, не заменяется строкой. Минимальные причины: missing scene/range/route facts, no legal target, unsupported Broken route, unsupported actor/target injury, pending Wound effect, attack Give Ground, Miscast preparation/effect, unsupported end-turn/chronology. Зарезервированный, но не исполненный slot сохраняется. В ветви Miscast первый runner останавливается **до preparation**: сохраняет pool/successes и desperate choice, не бросает таблицу и не очищает pool. Неизвестные GM decisions не выбираются автоматически.

Этот result не подставляется в существующий Minion-only `NpcRoundsChainSummary`, simulation/balance или JSON/CLI. Массовые прогоны, seed scheme, новая метрика, подбор и полный каталог требуют отдельных контрактов после одиночного runner.

## Probe и порядок реализации

[encounter_contract_probe.py](../examples/m8/encounter_contract_probe.py), [вывод](../examples/m8/encounter_contract_probe.output.txt): три authored actor IDs и public API. Production scenario admission расходует 0 d10, сохраняет fresh initial owner и допускает отсутствие будущего frame. Из принятого initial owner исполняется реальный Curse; после движения lookup нового key возвращает None. Прежние цепочки используют 32 scripted d10: real Stomach Blow → Casting → expiry, pending Wound stop, Curse → Give Ground → Willpower/Broken → end-turn, pending Miscast stop и отсутствие bound Minion handoff. Все supplied активации начинают существующий scheduler; промежуточных неисполненных ходов нет. Четыре outcomes и общий loop пока не проверяются — таких API нет.

[31 deterministic admission test](../../tests/unit/test_m8_npc_magic_scenario.py): обе Wizard/perspective стороны, independent orders, scope/type/tuple/frozen/source guards, canonical spell, definitions/equipment/health/daily/history, complete hostile pairs/Zone facts, directed True/False approvals, fresh availability, Give Ground/Slow/free Recover/Normal/Fast Run, archive/path/first-safe guards, optional future frames и отсутствие scheduler/Test/global RNG mutations. Вместе с прежними тестами проходят все 238 M8 tests.

Реализация разделяется на законченные срезы:

1. Frozen `NpcMagicScenario`/actor policies/facts/frame models и pure admission реализованы, 31 новый test. Runner/RNG не добавлены; полнота будущих frames не требуется.
2. **Следующий законченный срез:** bound Minion → Minion handoff к magic owner с typed state/request/result, exact source/replay/pending guards и синхронизацией всех projections с attached Minion ledger. Сначала перенос одного existing Attack и сохранение полного pending, без runner и повторного Attack. Затем отдельные bound acknowledgement/exclusion и full-owner start/advance wrappers. Проверить unchanged magic/daily/Wound timers, обе attack histories и межсемейные pending/replay guards.
3. Frozen steps/result/unsupported и single-run executor с current-state projections и точными stops. Не расширять Champion/Conditions admission для обхода законной остановки; дополнительный consumer — отдельный срез.
4. Аудит одиночной границы и самостоятельный production-пример; затем отдельно решать дальнейшие consumers и массовые прогоны.
