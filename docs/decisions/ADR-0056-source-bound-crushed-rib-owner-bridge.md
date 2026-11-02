# ADR-0056: Crushed Rib в полном M8 owner

Дата: 2026-11-02. Статус: **ADR-0056 реализован и закрыт в ручной full-owner границе**. [Приёмка](../audits/m8-crushed-rib-owner-readiness.md). Регрессионное подтверждение составное, с33прежними errors отдельно.

Основа: [закрытый K1 ADR-0055](ADR-0055-source-bound-crushed-rib-test.md), [его аудит](../audits/m8-crushed-rib-test-readiness.md), [архитектура](../architecture/overview.md). Цель этой вехи — ручной typed M8 handoff; automatic runner, permissions, generation и wire потребуют следующего контракта.

## Источники и граница

BOOK-PLAYER-GUIDE1.4: приложение Wounds Table, стр.190, Crushed Rib10; гл.V Rules / Grim & Glorious108, Attack Tests118, Conditions / Drained123; гл.VIII Casting a Spell156, Rule of Nine / Miscast Pool157. BOOK-GM-GUIDE1.1: гл.VII Allies and Antagonists / Champions92. Нормативная механика и Rule IDs прежние: [правила ран](../rules/wounds-and-conditions.md), RULE-HEALTH-005/008, RULE-TEST-004, RULE-MAGIC-004. Это инженерное связывание уже прочитанных правил, без нового полного чтения книг или house rule.

Ближайшей Test Wizard может быть Protection до своего хода или собственная Casting. Подготовка, объявление действия, Wounds Table dice и end-turn без Test не расходуют effect. Завершённая неуспешная Test расходует NEXT_TEST; Drained UNTIL_TREATED сохраняется. Новая рана после Protection не относится к её pre-Test source.

Первый source повторяет55: один живой Champion-Wizard с canonical resolved, untreated, unhealed rolled10, optional **предшествующие** superficial1–3, только вызванный этой раной Drained. Несколько10,9/6/Wind, сторонние Conditions, treatment/healing, Fate/Lucky/Talents и cancellation proofs не входят. Ограничение реализации не является запретом книги. Полный owner — существующий `NpcRosterCastingState`, включая обе child projections, histories, pending и phase state.

## Полный контекст и доказательство расхода

Добавить два frozen/slots M8 типа, отдельно от K1 injury models:

| Тип | Поля |
| --- | --- |
| `NpcCrushedRibContext` | `state: NpcRosterCastingState`, `actor_id: str`, `no_external_condition_sources: bool`, `consumption: NpcCrushedRibConsumptionWitness \| None = None` |
| `NpcCrushedRibConsumptionWitness` | `result: NpcRosterChampionAttackResult \| NpcRosterCastingResult`, `consumption: CrushedRibTestResult \| CrushedRibCastingResult` |

`no_external_condition_sources` принимает только strict `True`: это явный authored M8 факт об отсутствии иных причин Drained, а не вывод из перечня Conditions. `actor_id` — ровно owner Wizard. Перед equality проверять исходные nested types, enum identities, bool/int aliases, tuples, canonical source и согласованность root/children; не нормализовать испорченный source. Все обязательные pending blockers проверяются до RNG. Неполный daily/roll/lifecycle history не заменяется совпадением actor/Wound ID.

**Pending:** `consumption=None`; injury в полном current owner совпадает с допустимым pending55 source. Context привязан ко всему request owner, выбранному действию/слоту и актуальным profile/scene/magic facts. Внутренний executor связывает actor с exact injury и выбирает Test, которая действительно выполняется этим действием.

**Consumed:** witness содержит именно **первый реально расходующий M8 result** и его собственный nested55 completion. Источник этого result имеет pending context, nested actual Test/receipt/slot и post-Test state проверяются полностью. Witness от поздней normal action, который только пересылает чужой context, не принимается. Новая normal Test не создаёт ещё один55 completion.

Current Wizard injury должен быть **exact equal `consumption.state`**. Сохраняются Wounds/effects/order/provenance и Drained; сверяются actor definitions/sides и daily day. Полные consumed execution IDs, daily receipts и consumed Wound roll IDs из первого `result.state` должны сохраняться как ordered prefixes текущих историй, с согласованными child projections. `current.round >= result.state.round`; в том же раунде completed-turn prefix и excluded actors не регрессируют. Сам текущий clock/active slot проходит existing phase guards. Допустимые внешние phase transitions не создают нового расхода, но context всегда заново привязан к полному актуальному state. Лечение, новая Wound/Condition или смена source выводят состояние за эту границу.

Контекст доказывает source compatibility и связь первого actual consuming result с его Test. Он **не доказывает произвольную достижимость current state, принадлежность глобальному журналу или отсутствие скрытых внешних Tests**. Авторитетный caller передаёт настоящий current owner; будущий dispatcher/journal должен выводить context из собственного префикса. Root archive, произвольный replay или рекурсивная цепь всех действий не добавляются.

Для action branches с actual Test upper/lower binding проверяется в обе стороны: отсутствие upper context запрещает lower witnesses; pending context требует exact preparation и первый completion в result; consumed context требует exact старый receipt, normal текущую Test и отсутствие нового completion. Нельзя передать lower opt-in под upper None и обойти проверку первого full-owner result. End-turn без Test лишь сохраняет pending/consumed состояние, не требует и не создаёт новый completion.

## Protection: точка между Test и последствиями

Первый поддержанный случай — обычная **opposed Shooting** атака Minion по Wizard. Pending10 + unopposed attack отклоняется до RNG: отсутствующая defender Test не расходует effect.

1. Сохранить исходный full owner, normal attack/protection preparation, exact выбранный Protection skill и исходный kernel target injury. `NpcRosterChampionAttackRequest` получает kw-only optional `crushed_rib_context=None`; `NpcChampionAttackRequest` — optional `crushed_rib_preparation: CrushedRibTestPreparationResult | None` и `crushed_rib_consumption: CrushedRibTestResult | CrushedRibCastingResult | None`, а `NpcChampionAttackResult` — `crushed_rib: CrushedRibTestResult | None`. Все новые optional поля kw-only/default None. Full context остаётся в upper source request, K1 preparation/receipt — в lower request/result; outer result связывает их с полным owner. Lower pending использует только preparation, lower consumed — только старый completion с exact current injury/actor, оба одновременно запрещены. Lower K1 witness сам по себе не доказывает full-owner lineage: это проверка upper wrapper. Stationary/repeated contexts с ним одновременно не поддерживаются.
2. Из selected defender Test подготовить55. Изменяется только selected option; невыбранные options, attacker Test, IDs, profiles, target и все scene facts прежние. Нельзя изменить owner injury, чтобы пройти старый admission.
3. Выполнить existing `resolve_attack` **один раз**: attacker Test → defender initial dice → Grim rerolls. Связать `complete_crushed_rib_test` с actual defender result до Stagger/Wound consequences. Hit/miss, BOTH_FAIL и нулевые successes не отменяют расход состоявшейся Test.
4. Выделить узкую private kernel функцию продолжения после уже выполненного `AttackResult`. Она принимает проверенные actual attack и post-Test target injury. Старый `resolve_kernel_attack` вызывает `resolve_attack` и эту же функцию; новый путь передаёт injury из55 receipt. Публичный универсальный continuation protocol не нужен. Запрещён повторный kernel/attack execution для получения того же Test.
5. Сохранить original pre-Test source отдельно от вычисленного post-Test consequence request. `NpcChampionAttackResult` проверяет Wound lifecycle source относительно **вычисленного post-Test injury**, а не сравнивает его безусловно со старым kernel source. Actual attack/action receipt остаётся один. Полный result обязан доказать оба snapshot и их единственную допустимую разницу.
6. Исполнить и зарегистрировать все реальные последствия атаки: Stagger, Wound lifecycle, daily/roll receipts, action slot/consumed ID и обе child projections. Результат нельзя публиковать наполовину. Если последствия добавили Wound/Condition и injury уже не равен55 receipt.state, сохранить их и остановить дальнейший Crushed Rib context admission. Это относится даже к новой superficial Wound. Новая10 сохраняет **свой новый** NEXT_TEST; прежняя Protection его не расходует.

После расхода compatible owner может выполнять следующие normal Protection с оставшимся Drained и тем же первым consumed witness. У selected Test нет нового Crushed Rib Grim, а ordinary bonuses/Glorious всё ещё подавлены Drained. Не переиспользовать whole Leg Spasm `_attack_witness`: его HIT/new9/NORMAL assumptions здесь не подходят.

При exception до полного TestResult completion/новый owner не публикуются. Ошибка позже также не даёт частично применяемый public result. Откат RNG не обещается. Неподдержанный post-Test injury — штатный сохранённый итог атаки, не основание откатывать её последствия.

## Casting: action receipt, затем pool и follow-ups

Верхний `NpcRosterCastingRequest` получает optional kw-only full `crushed_rib_context=None`. Он проверяет owner/слот/caster/lore/magic и требует exact preparation55 для реальной Casting Test при pending context. Подготовку создаёт factory `prepare_npc_roster_casting(..., crushed_rib_context=...)`; прямой constructor получает уже подготовленный lower witness. Нижний generic `CowardlyFlightCastingRequest` получает kw-only `crushed_rib_preparation: CrushedRibCastingPreparationResult | None = None`, а result — `crushed_rib: CrushedRibCastingResult | None = None`. Generic spell model не импортирует M8 root; связь этих witnesses с full owner проверяет верхний wrapper.

Existing `execute_casting_attempt` уже принимает effective CastingTestRequest и создаёт единственный actual action receipt. Использовать его с preparation55, затем `complete_crushed_rib_casting(preparation, execution.casting)` **до** `resolve_casting_action_post_test`. Не вызывать дополнительно resolver55: это повторит Test. Единственный Rule-of-Nine lock, final nines, progress, pool и решения остаются existing Casting semantics.

Lower normal-Test validator получает узкую ветку по explicit55 witness; прочие Tests spell targets остаются NORMAL. Недостаточно разрешить Grim по quality или по совпавшему ID. Post-Test result обязан содержать actual preparation/complete trace, action receipt и canonical pool/decision.

Outer result атомарно проецирует consumed Wizard injury, magic state, executed slot/history и обе child rosters. Затем публикуется WAIT, MISCAST_REQUIRED, MOVEMENT_REQUIRED или RESOLVED с настоящими pending данными. Pending Miscast/movement/interruption не снимаются, чтобы пройти admission; до их завершения новые действия запрещены. Movement completion сохраняет уже consumed Wizard injury и receipt, не перебрасывает Test. Если Miscast/Wind или другое последствие меняет injury вне exact receipt.state, последствия сохраняются, дальнейший context отклоняется; автоматическая поддержка нового сочетания не подразумевается.

Consumed branch на позднем Casting использует normal Test с Drained, сохраняет первый witness и не создаёт повторный55 receipt. Parent/magic snapshot/actual latest action проверяются перед публикацией pending, включая путь завершения follow-up.

## Admission и старые пути

Фактический пробел baseline: `NpcRosterCastingRequest` и Wizard `NpcWoundTurnEndRequest` могут принять resolved10 с уже отсутствующим restriction и одним Drained UNTIL_TREATED без доказательства расхода. **В56 этот допуск закрывается:** Wizard action/end-turn с Wound10 требует explicit56 context даже для уже spent формы. Поддержка вручную stripped10 не сохраняется ради совместимости.

Прежние поддержанные None scenarios без указанного legacy10 admission gap сохраняют actual traces/RNG. Direct Wizard action/end-turn со stripped/spent10 без witness — явное исключение из прежнего допуска. `NpcWoundTurnEndRequest` получает optional kw-only `crushed_rib_context=None` и сверяет source целиком; end-turn не создаёт нового55 receipt. Обычные actors и enemy end-turn с pending10 у Wizard остаются допустимыми, если их собственные guards выполняются. Общий `_validate_phase_source` не превращается в глобальный запрет Wound10: он должен хранить unsupported owner и позволять прежние stop sequences. Новые guard branches локальны к затронутому Wizard action/end-turn.

Автоматический scenario runner продолжает ACTOR_INJURY stop. Dispatcher/step/journal, native mass trials, policy, generation, adapters, JSON1–4/CLI и schemas не расширяются. Их прежние fixtures и stop/RNG controls являются regression boundary, а не обходом нового context. Wire5 не добавляется.

## Finite proof и порядок реализации

[Probe](../examples/m8/crushed_rib_owner_contract_probe.py), [stdout](../examples/m8/crushed_rib_owner_contract_probe.output.txt), [copied test](../../tests/integration/test_m8_crushed_rib_owner_contract_probe.py) используют существующие public APIs. Это доказательство композиции и обнаруженных seams, **не результат будущего bridge**. Ни consumed injury, ни фиктивный56 result в M8 не вставляются.

Проверено25 scripted d10: actual first10/owner7; actual Wizard slot-bound Grim Casting4 и completion55 до реального pool0→2/WAIT; независимый genuine authored five-actor source с first10/owner7 и actual E1 end/E2 start без Tests; текущая E2 Shooting/selected Athletics K1 Attack7 с completion55. Последний owner точно равен настоящему stopped current, phase results совпадают с actual journal entries. Ни новой M8 атаки, ни её Wound consequences proof не публикует. Нижние/верхние старые NORMAL/condition guards остаются negative controls.

Copied bundle: probe, `stationary_wound_runner.py`, `generation_contract_probe.py`, `magic_scenario.py`. Команда `$env:PYTHONPATH='src'; .venv/Scripts/python.exe -m unittest tests.integration.test_m8_crushed_rib_owner_contract_probe -v` прошла: **1 test OK/0,932с**, CPython3.12.4, outside-sandbox runner. Exact saved stdout/empty stderr, source/copied SHA до/после и неизменность owners/global RNG проверены. Независимый read-only review подтвердил current Protection source и отсутствие блокеров контракта; тест повторно без изменений не запускался.

Реализовывать56 до проверяемой вехи последовательно:

1. Context/witness, canonical original-source guards, optional contracts и закрытие admission gap. Deterministic refusal tests: aliases, чужой actor/owner/профиль/слот/day/history, missing/forged witness, stale/повторный apply, mutually exclusive contexts. До RNG никаких частичных изменений.
2. Private post-Test kernel seam и actual Protection completion; integration tests текущего полного owner. Miss/BOTH_FAIL/zero successes; consumption перед новой Wound; новая10 и superficial сохраняются вместе с точными receipts и затем ограничивают admission. None attack call/RNG order прежний.
3. Actual slot-bound Casting, strict lower witness branch, atomic full owner и pending completion. WAIT/failure, one9lock, final nines/pool/Miscast, movement; consumed normal Casting/Protection и Wizard end-turn с remaining Drained. Pending/stale/mismatched follow-ups отвергаются.
4. Public actual-owner example, copied/installed package proof и source/wheel/installed parity. Один full regression на границе вехи с отдельным сравнением33 известных Python3.12 ERROR headers. Закрыть56 только после этого аудита. До него статус — контракт/реализация, не выполненная M8 поддержка.

Исторический contract-only шаг не повторял полный suite/installed wheel: на его границе действовал baseline55,4110tests/33known errors/0failures/0skipped,542integration OK. Итог реализации56 фиксируется ниже и в отдельном аудите.

## Реализация и приёмка

Шаги1–3 реализованы. [Full context/witness](../../src/towr/domain/npc_crushed_rib_models.py), lower/upper Protection/Casting и end-turn сохраняют исходные source, расходуют effect на actual Test и проецируют полный owner. Для literal original Protection preparation options остаются normal; computed `effective_attack` меняет только selected defender Test, computed post-Test kernel добавляет injury из actual55 receipt. Это реализация точки handoff, без дополнительного Attack или временного stripped owner.

62targeted tests прошли, включая39new unit,7actual integrations,2copied56 и14old end-turn. [Public63d10](../examples/m8/crushed_rib_owner.py) и [installed477files/8commands](../audits/m8-crushed-rib-owner-readiness.md) прошли. Strict original-source guards отклоняют aliases до RNG; удаление upper context из готового Result/end-turn не обходит привязку. Full4158tests/1059,911с дал33known errors и1устаревший message assertion failure; все551integration OK. После исправления только этого fixture повторены все3607unit:33known errors/0failures/105,099с. Exact33ERROR headers full run прежние; production/installed/examples не менялись. Это составное4158покрытие, не единый full run без failures.56 закрыт аудитом; automatic runner/journal/policy, generation/JSON/wire5 по-прежнему вне этой вехи.

Исторический scope contract-only шага:476package py/json и93прежних public example py/json/txt сохраняли SHA256 закрытого55;1738local Markdown paths/16документов, broken paths0 (без anchors). Diff/whitespace были чистыми;31dirtyfile включал27предшествующих. Evidence `.cache/adr0056-contract-checks.json`. Эти числа не являются scope последующей реализации; актуальные результаты — в аудите. Commit/push, `.gitignore` и книги не менялись.
