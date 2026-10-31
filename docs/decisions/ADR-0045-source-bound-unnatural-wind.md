# ADR-0045: source-bound Miscast prefix и Unnatural Wind 21–22

Статус: принят ограниченный технический контракт, 2026-10-28. Production preparation, one-roll и Wind application реализованы; [общий low-level аудит](../audits/m8-unnatural-wind-readiness.md) завершён. [Предыдущий consumer](ADR-0044-dead-champion-turn-exclusion.md) закрыт аудитом; [inventory](../audits/m8-continuation-inventory.md) отличает готовые K1 reducers от отсутствующего full-owner Miscast continuation. Этот ADR задаёт один low-level consumer, не автоматическое продолжение runner.

## Источники и выбор границы

Непосредственно прочитаны локальные постраничные тексты:

| Книга, глава, страницы | Нормативное следствие |
| --- | --- |
| BOOK-PLAYER-GUIDE 1.4, гл.VIII Magic in the Old World / Casting a Spell / Interrupted Casting, стр.156; Miscasts and the Rule of Nine, стр.157–158 | Triggered/interrupted Miscast сохраняет весь Pool. Есть явный выбор cast-before/decline; preparation теряет accumulated successes/Lore. Desperate spell исполняется до таблицы и добавляет1d. Pool очищается после разрешения эффекта, не после одного lookup. |
| Та же книга, Miscast Table, стр.159 | Unnatural Wind21–22 заставляет всех within Short, включая caster, упасть Prone; Monstrosities исключены. Allies не исключаются. |
| Та же книга, гл.V Rules / The Battlefield / Range, стр.114 | Short — same Zone, но Close бывает и на границе соседних Zones. Same-Zone discovery не является универсальным range algorithm. |
| Та же книга, Combat Actions / Recover, стр.118; Conditions / Prone, стр.123 | Prone запрещает уход из Zone; Shooting по Prone−1d, Melee получает higher-ground+1d. Prone не задаёт общего penalty собственной Casting/Protection Test и не имеет end-turn upkeep. Удаляется Recover либо своей free move при отсутствии врага Close. |
| BOOK-GM-GUIDE 1.1, гл.VII Allies and Antagonists / Minions и Champions, стр.91–92 | Сохраняются distinct injury policies; текущий M8 roster не допускает Monstrosity. |

Новых игровых Rule IDs/house rules нет. DECLINE — выбранное допустимое решение участника, не исправление книги. Для21–22 caster включён явно, поэтому незакрытая self-inclusion ambiguity строк1–2/3–4 не решается предположением.

## Закрытая low-level граница

Первый consumer принимает текущий полный M8 roster с обязательным Casting-triggered `pending_miscast` либо action/interruption-triggered `pending_interruption`. Он явно выбирает **DECLINE_CAST_BEFORE_MISCAST**, подготавливает и публикует actual prepared magic, однократно бросает всю Pool, затем применяет только выпавшую строку21–22. Иная строка сохраняет prepared/rolled prefix и Pool как незавершённый эффект. Не выбирается другая строка, не восстанавливаются successes/Lore и не совершается повторный бросок.

После Wind все actual Prone applications завершены, Pool0 и mandatory prefix очищен. Это законченный эффект Miscast. Текущие Prone `END_TURN`/`ACTOR_INJURY`/`TARGET_INJURY` остаются честными stops до отдельного интеграционного контракта. Этот ADR **не обещает resumed battle** и не добавляет автоматическое вставание, ranged target modifier, новую тактику/scene policy или изменения JSON/CLI.

Desperate CAST, abandonment без исходного mandatory pending, любой другой effect, Monstrosities, mounts, immunity и saved battle в этот срез не входят. Запрос неподдержанного выбора отклоняется **до** preparation/RNG. Возможность cast-before не теряется молча: required policy хранится в полном source и явно подтверждает отказ, в том числе при уже доступном spell.

## Required policy и scope facts

В `domain/npc_roster_miscast_models.py` реализованы frozen/slotted:

- `NpcRosterMiscastPolicy`: единственный admitted value `DECLINE_CAST_BEFORE_MISCAST`, без default в request.
- `NpcRosterMiscastFacts`: required bool поля `all_combatants_in_roster`, `no_external_short_range_creatures`, `unmounted_combatants_only`, `no_effect_immunities`, `no_cross_zone_close`; все должны быть явно True в первом scope. False/type mismatch отклоняются, факты не выводятся из числового профиля или Zone graph.

Facts — assertions caller, не доказательство полноты именованного NPC. `all_combatants_in_roster` не исключает non-combatant bystander: отдельный `no_external_short_range_creatures` обязателен, иначе полный effect target set неизвестен. `no_cross_zone_close` ограничивает этот low-level вход: при потенциальном Close через границу Zone нужен другой range contract, а не молчаливое исключение существа. Within этих facts Short targets выводятся из **всех живых** participants Zone caster, caster первым, остальные в roster order. Это технический детерминированный порядок, книга его не задаёт. Dead Champion/defeated Minions остаются в archive, но не входят в targets. Уже Prone цель включается с `was_already_present=True`.

До любого RNG требуется living caster и допустимый полный live snapshot. Весь roster — один Wizard/Champion плюс Minions; не добавлять fake PC/Monstrosity policies или пустые hand/Ability assumptions. Все другие Conditions и injuries сохраняются, а не лечатся вследствие Wind.

## Полный источник и новый pending owner

Текущий `NpcRosterCastingState` не может truthful хранить prepared magic под старым pending: raw Casting/interruption anchor требует прежний post-action `WizardMagicState`, а pool>level без pending запрещён. Поэтому простое очищение pending либо подмена magic без нового owner недопустимы.

Добавляется только одно typed поле `pending_miscast_continuation`, значение которого — полный `NpcRosterMiscastPreparationResult | NpcRosterMiscastRollResult | None`. Оно хранит source request со всем root до фазы и полный existing K1 result. Prepared/rolled — две конкретные стадии, не generic event/payload dictionary. До preparation legacy pending остаётся прежним; после неё обе legacy поля None, но их полные исходные proofs сохранены в source chain нового pending.

Root guards обязаны проверять:

1. Legacy Casting/interruption pending и новый prefix взаимоисключаются. Prefix не сосуществует с Champion/Minion Attack pending или Curse movement.
2. В активном ходу живого Wizard один исполненный standard action, origin execution receipt и последний root consumed execution совпадают. Casting origin — полный current Casting result; interruption — полный current skipped-Test/action result. Casting anchors сверяются с `root.casting_round_state` / `root.casting_spatial_state` (live projections), а active turn/receipt — с полным round owner. Иначе defeated archive ошибочно сделает допустимый Casting source чужим. ID-only binding недостаточен.
3. Actual prepared magic точно выведен из origin: successes0, LoreNone, latest-successes0, **прежний Pool**. После roll magic не меняется. Wizard definition/caster и полные owners/roster/spatial/receipts/history/expiry contexts сохранены.
4. Новый pending сам точно связан с опубликованным root. Проверять все root fields кроме явно меняемых pending/magic fields; нельзя сравнивать только actor/round/IDs.

Взаимные ссылки моделей решаются `TYPE_CHECKING`/отложенными annotations и узким runtime validator, а не переносом rules/engine imports в domain. Проверка текущего root не должна рекурсивно строить `prefix.state` и уходить в бесконечную валидацию. Prepared source содержит старый raw-pending root, rolled source содержит prepared root; объектный граф конечный, обратной ссылки на текущий root нет.

Любой legacy dispatch/action/start/advance/end/defeat/death consumer обязан отклонять новый prefix до executor/RNG. В частности, обновляются bound Casting/Champion Attack/Minion Attack, Broken Recover/Run, scheduling и end-turn guards. Fresh-only `NpcMagicScenario` admission также отвергает prefix: новый low-level owner не превращает fresh input в saved battle. Наличие потенциально исполнимого следующего action не позволяет проигнорировать mandatory effect.

## Typed API и фазы

Планируемые модели в `domain/npc_roster_miscast_models.py`; функции в `rules/npc_roster_miscast_resolution.py`. Все requests/results frozen/slotted, result.state — derived projection, input не мутируется.

| Фаза | Request / result | Исполнение и переход |
| --- | --- | --- |
| Preparation | `NpcRosterMiscastPreparationRequest(id, state, policy, facts)` / `NpcRosterMiscastPreparationResult(source, preparation)` | `prepare_npc_roster_miscast(request)` без RNG вызывает existing `prepare_miscast` с explicit `spell_to_cast=None`. `.state` меняет только wizard.magic, переводит legacy pending в новый prepared pending. Origin roll request берётся из полного legacy proof, не создаётся из числа pool заново. |
| One table roll | `NpcRosterMiscastRollRequest(id, state)` / `NpcRosterMiscastRollResult(source, roll)` | Только prepared prefix. `id` обязан совпасть с prepared `roll_request.resolution_id`. `roll_npc_roster_miscast(request, rng)` вызывает existing `resolve_miscast_roll` один раз. `.state` заменяет prepared prefix на rolled, magic/Pool сохраняет. |
| Actual Wind | `NpcRosterUnnaturalWindRequest(id, state)` / `NpcRosterUnnaturalWindResult(source, wind)` | Только rolled prefix с canonical UNNATURAL_WIND21–22. `id = effect_request.resolution_id + ':apply'`. `resolve_npc_roster_unnatural_wind(request)` без RNG вызывает existing `resolve_unnatural_wind` с полным ordered target snapshot. `.state` переносит target injuries в root/оба child owners, magic с Pool0, очищает prefix. |

У каждой стадии отдельная exact-source apply-функция: `apply_npc_roster_miscast_preparation`, `apply_npc_roster_miscast_roll`, `apply_npc_roster_unnatural_wind`. Они принимают typed current root/result, требуют полного `state == result.source.state` и переносят только derived result.state без повторного reducer. Outer preparation ID непустой; inner K1 preparation использует его же, поэтому готовый roll ID — `id + ':roll'`. Новые action slots/receipts, дневные Wounds или execution IDs ни одна из фаз не создаёт.

Повтор roll на rolled state запрещён независимо от нового phase ID. Повтор Wind после очистки prefix запрещён. Старый source с теми же IDs, но другим magic/spatial/roster/history или roll trace, отклоняется. Намеренное восстановление старого immutable snapshot и подлинность произвольного externally forged DTO не гарантируются pure API.

## Проверка K1 DTO и минимальные проекции

`MiscastPreparationResult`, `MiscastRollResult`, Wind/target/Condition results не доказывают полную provenance одним `isinstance`. Bound result validators проверяют записанные данные, не повторяя rules/RNG:

- Preparation: request/target/правило, предыдущие successes, exact reset magic, единственный source-derived roll follow-up с bonus0 и отсутствие SpellCastRequest.
- Roll: prepared request/target/ID, неизменный magic, exact pool/bonus0/dice count, strict d10 values/sum, entry range consistency, полный effect request/source_roll_id/Rule ID/values/total и полный trace. Требуется обе стороны: total21/22 **тогда и только тогда**, когда entry равен `MiscastTableEntry(UNNATURAL_WIND,21,22)`. Нельзя подменить известный Wind на неизвестный entry и замаскировать его unsupported. Полная таблица не копируется в новый domain rules engine.
- Wind: exact source, ordered target IDs/policies/full injuries, caster, применение только Prone через existing Condition metadata, `blocked=False` в admitted no-immunity scope, точный `was_already_present`, stable application IDs и Rule IDs. Ни Wounds, ни unrelated Conditions/effects/definition/equipment не меняются. Pool0 принимается только вместе со всеми завершёнными target applications; нельзя подставить cleared magic без effect.

Preparation/roll сохраняют root roster/round/spatial/обоих attack owners/ledgers/daily/expiries/end-turn receipts побайтно по value equality, кроме явно указанных magic/pending fields. Wind меняет только injuries выбранных live targets, roster references обоих child owners, wizard.magic и pending. Полные placements/round participants/completed/excluded/free-move usage и все histories сохраняются. Archive не фильтруется при storage.

Иная строка не вызывает Wind handler: strict request отклоняет её до effect, а rolled root с actual values/effect request и неочищенным pool остаётся доступным будущему специализированному consumer. Ошибка исполнения, включая частичный сбой RNG, не становится игровым исходом и не запускает retry/fallback; RNG не откатывается, immutable source сохраняется.

## Prone, runner и wire остаются отдельной интеграцией

Новый prefix учитывается `_pending`/terminal guards. `diagnose_npc_magic_unsupported` получает точные продолжения: prepared → `MISCAST_ROLL` (`miscast_roll`), rolled → `MISCAST_EFFECT` (`miscast_effect`) с phase CONTINUATION и canonical phase/effect source ID. Это unsupported **текущего runner**, а не отрицание наличия low-level API. Старый raw pending сохраняет MISCAST_PREPARATION. Счётчик unsupported в simulation остаётся в общем N; новых wire outcomes/fields нет.

Существующий fresh runner не создаёт prefix автоматически, не получает default decline policy и не добавляет новые step types. Новая ручная цепочка не принимается старым closed journal как будто уже интегрирована. После успешного Wind storage допускает Prone, но нынешний end-turn/request diagnosis остаётся END_TURN, а позднейшие action/target injury — ACTOR_INJURY/TARGET_INJURY. Не ослаблять эти guards, чтобы показать искусственное продолжение.

Для следующей автоматической интеграции отдельно потребуются explicit opt-in policy, точный journal prefix и source guards, scoped Prone end-turn/action/target adapters и прежние exact scene/route facts. Self-stand перед своим action не решает penalty Shooting по Prone цели, ожидающей хода. Free-move removal расходует свою free move и требует no enemy Close; не переносит Zone, не даёт нового action. Broken+Prone может потребовать сначала stand, затем forced escape; existing Broken routes нельзя считать автоматически подходящими. JSON/CLI admission/добавление optional policy также не делается этим ADR.

## Последовательность реализации и проверки

1. **Реализовано:** required policy/facts, frozen preparation request/result, typed prepared prefix в root, pure preparation/apply и все mandatory dispatch guards. В этом срезе prefix допускает только реальный PreparationResult; union расширяется настоящим RolledResult на этапе2, без placeholder DTO с пустыми guards. Deterministic tests обоих origin kinds, living caster/receipt/source/facts/choice, exact reset magic/pool retention, frozen/replace/replay и no RNG. Только затем следующий этап.
2. **Реализовано:** bound one-roll request/result/executor/apply и rolled prefix/точная diagnosis. Один RNG вызов на die, canonical source/values/effect, другой entry сохраняет prefix/pool, repeat/new-ID/stale source отвергаются. Малые pool не гарантируют21–22: например два d10 без desperate bonus не могут дать Wind; не выбирать таблицу принудительно.
3. **Реализовано:** bound Wind request/result/pure consumer/apply: self+allies+enemies в scoped Short, caster first, outside/dead archives исключены из targets, already-Prone сохранён, оба owners/все histories и effect-before-cleanup; strict malformed DTO/source guards.
4. **Завершено:** аудит всей low-level границы: primary books/контракт/tests/public production example и installed parity. Exact Prone stops должны быть доказаны, а не скрыты. Automatic runner/Prone/wire integration остаётся следующим отдельным контрактом, не частью acceptance этого consumer.

[Public finite probe](../examples/m8/unnatural_wind_contract_probe.py) и [сохранённый вывод](../examples/m8/unnatural_wind_contract_probe.output.txt) используют только existing public K1/M8 APIs. Они показывают actual trigger, explicit decline, один table roll21/22, реальные Wind applications, честный current-owner staging gap и ручную финальную проекцию с текущим Prone stop. Другой entry сохраняет K1 pool/roll/effect; probe не создаёт fake новые production types или работающий prepared/rolled root. [Subprocess test](../../tests/integration/test_m8_unnatural_wind_contract_probe.py) проверяет external bundle/stdout. Это evidence контракта, не реализованный consumer или resumed battle.

Probe доказывает fresh Casting-triggered origin, не fresh reachability interruption-origin: в нынешнем authored v1 Wizard не становится Broken от собственного Curse. Будущие interruption tests используют реальные bound Broken Recover/Run low-level fixtures и проверяют existing action-sourced origin отдельно, без объявления такой ветви естественно достижимой из fresh runner.

## Реализованный первый срез

2026-10-28: [domain models](../../src/towr/domain/npc_roster_miscast_models.py) и [pure preparation/apply](../../src/towr/rules/npc_roster_miscast_resolution.py) принимают только explicit DECLINE и пять подтверждённых facts. Root поле пока допускает только настоящий PreparationResult. Actual reset successes/Lore/latest публикуется с прежним Pool; legacy proof сохраняется в конечной source chain. Все прочие root fields сверяются без рекурсивного построения prefix.state. Interruption guard проверяет полную canonical action/increase/pool/history trace, поскольку старый K1 DTO сам этого не гарантирует. Casting anchors используют live projections, execution receipt — полный round owner.

[18 unit tests](../../tests/unit/test_m8_npc_roster_miscast_preparation.py) и [7 integration tests](../../tests/integration/test_m8_npc_roster_miscast_preparation.py) проверяют Casting, реальные bound Recover/Run interruption origins, archives, сохранение owners/histories, exact-source/replay/replace, malformed DTO и отсутствие RNG. Все legacy действия/terminal/fresh admission учитывают prepared pending; diagnosis — CONTINUATION/MISCAST_ROLL с canonical roll ID. Fresh runner продолжает останавливаться на raw MISCAST_PREPARATION, closed journal новый result не принимает. One-roll/rolled prefix, Wind и automatic integration этим срезом не реализованы. На границе первого среза следующим был пункт2 выше.

## Реализованный второй срез

2026-10-28: в тех же [domain models](../../src/towr/domain/npc_roster_miscast_models.py) и [rules](../../src/towr/rules/npc_roster_miscast_resolution.py) реализованы NpcRosterMiscastRollRequest/Result и roll_npc_roster_miscast/apply_npc_roster_miscast_roll. Request принимает только настоящий prepared prefix и canonical roll ID; executor ровно один раз вызывает existing resolve_miscast_roll с внедряемым RNG. Result проверяет strict tuple/d10/count/sum/total, exact IDs/magic/effect/rules и Wind21/22 iff canonical entry; полный каталог таблицы в domain не дублируется. Pure apply требует полного source equality без повторного reducer.

Root union теперь допускает настоящий RollResult. Он заменяет только prefix, сохраняя actual roll/effect request, Pool, roster/round/spatial/обоих child owners и все histories. Context validator сравнивает все остальные поля с prepared source без вызова prefix.state. Repeat/new-ID и stale apply отклоняются. Иная строка сохраняется так же, без cleanup/reroll/effect. Diagnosis — CONTINUATION/MISCAST_EFFECT с canonical effect ID; legacy guards/terminal/fresh admission действуют и для rolled root, а closed journal его не принимает.

[Unit tests](../../tests/unit/test_m8_npc_roster_miscast_roll.py) и [integration tests](../../tests/integration/test_m8_npc_roster_miscast_roll.py) проверяют обе origin kinds, archives/histories,21/22 и соседние/другие строки,2d10 без forced Wind, malformed weak K1 DTO и source/replay guards, exact RNG calls и частичный сбой без retry/partial state. Прямо сверены PG1.4, гл.VIII Miscasts157 / Miscast Table159; новых Rule IDs/house rules нет. На границе второго среза следующим был bound Wind application (пункт3), затем общий low-level аудит. Automatic runner/journal/Prone/JSON остаются отдельной границей.

## Реализованный третий срез

2026-10-28: NpcRosterUnnaturalWindRequest/Result в [domain models](../../src/towr/domain/npc_roster_miscast_models.py) и resolve_npc_roster_unnatural_wind/apply_npc_roster_unnatural_wind в [rules](../../src/towr/rules/npc_roster_miscast_resolution.py) реализуют actual effect. Canonical rolled Wind21–22 и applyID обязательны. Derived wind_request содержит caster первым, затем всех живых same-Zone participants в roster order; five scope facts сохранены в prepared source chain. Caller не может передать отфильтрованный target list. Defeated archives и outside actors сохраняются без изменений.

Consumer один раз вызывает existing resolve_unnatural_wind без RNG. Bound result проверяет весь weak K1 Wind/target/Condition trace: полноту/order/IDs, unchanged injuries кроме добавления Prone, already-present, literalbool flags, typed Condition.PRONE, source/block metadata/rules, exact Pool0 magic. Только полный результат допускает cleanup. Projection обновляет target injuries и roster references обоих child owners, wizard.magic/Pool0 и prefixNone; все placements/round/definitions/equipment/receipts/ledgers/daily/expiries сохранены. Pure exact-source apply не повторяет reducer, stale/replay/other-row/new-ID requests отклоняются.

[Unit](../../tests/unit/test_m8_npc_roster_unnatural_wind.py) и [integration](../../tests/integration/test_m8_npc_roster_unnatural_wind.py) tests проверяют Casting и bound Recover/Run origins, self/allies/enemies/outside/archive/already-Prone, malformed weak DTO и частичный сбой без cleanup/mutation/retry. PG1.4, гл.VIII Miscasts157 / Table159 и гл.V Range114 / Prone123, GM1.1, гл.VII Minions91 / Champions92 перечитаны напрямую. Новых Rule IDs/house rules нет. Automatic runner/journal/wire/Prone adapters не добавлены; существующие END_TURN/ACTOR_INJURY/TARGET_INJURY stops сохраняются. Пункт4 завершён [общим аудитом](../audits/m8-unnatural-wind-readiness.md), standalone production example и installed parity.

## Итоговый low-level аудит

[Readiness audit](../audits/m8-unnatural-wind-readiness.md) закрыл source/contract/test matrix всех трёх фаз,75implementation tests и [standalone public example](../examples/m8/unnatural_wind.py) / [stdout](../examples/m8/unnatural_wind.output.txt). Семь случаев/63scripted d10, все переходы через actual bound apply API без manual post-effect projection. Single-file external cwd и новый wheel/installed parity444Python/Schema files проверены. Fresh Casting, authored already-Prone bound input и отдельные bound interruption tests не смешиваются в reachability claims. Новых Rule IDs/house rules/ambiguities нет. Следующий отдельный opt-in контракт определит journal/runner и scoped Prone adapters; этот ADR не разрешает их автоматически.


Продолжение ограниченной интеграции зафиксировано отдельно в [ADR-0046](ADR-0046-opt-in-miscast-runner-and-prone.md); оно не меняет acceptance закрытого low-level consumer.
