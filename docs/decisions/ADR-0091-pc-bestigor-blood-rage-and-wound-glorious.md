# ADR-0091: Bestigor, добровольный Blood Rage и следующая Glorious Attack

Дата: 2026-11-06. Статус: **принято пользователем и реализовано в M46**. Выбран полный Bestigor и reroll всех доступных провалов.

## Источники

BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Bestigor144: Normal Brute2, WS4/T4/Res6 armoured, Massive Axe Close3d/4 Damage7/2H; Protection Defence4d/3 либо Athletics3d/3. Default3, Melee4, Willpower4. На W0 нельзя выбирать Give Ground или fall Prone; на W1 следующая attack Bestigor Glorious; W2defeat. Child of the Forest игнорирует woodland Difficult Terrain. Blood Rage позволяет при Attack добровольно получить Staggered, если его ещё нет; Staggered Bestigor получает+1d к Melee attacks.

BOOK-PLAYER-GUIDE1.4, гл.V Rules / Dice Modifiers107: обычный cap — удвоенная Characteristic; для Massive Axe это8 от WS4, не6 от printed pool3. Grim & Glorious108: Glorious позволяет перебросить любые провалы один раз; Grim/Glorious отменяют друг друга, повторный reroll запрещён. Attack/Staggered119: повторный Staggered даёт выбор цены; промах Close не добавляет второй Staggered. Printed NPC pool/Damage используются напрямую без PC weapon Traits/повторного penalty по GM Profiles93.

## Принятый публичный контракт

Canonical `PcBookNpcProfile.BESTIGOR_MASSIVE_AXE = bestigor_massive_axe`, definition ID `pc-book-npc:bestigor_massive_axe`, source `BOOK-GM-GUIDE:1.1:p144:bestigor_massive_axe`. Выбран Defence4d3, alternate Athletics3d3 сохраняется unselected. Без щита, Armour bonus2, printed Axe3d4Damage7/2H и explicit Attack pool_cap8. Это второе точечное cap8 исключение рядом с Minotaur Greataxe; Protection/прочие book/authored caps не расширяются.

В native `PcMeleeScenario` и текущем PC JSON1 добавить обязательный `npc_blood_rage_actor_ids`: exact tuple/list уникальных opposition actor IDs, каждый — canonical Bestigor данного loadout. Поле без default; пропуск, aliases/чужие роли/неизвестные NPC/другие профили и дубликаты отвергаются до RNG.

```json
"npc_blood_rage_actor_ids": ["bestigor1"]
```

Для указанных Bestigors перед каждой фактически предстоящей Attack: если Staggered отсутствует, получить его; если уже есть — не накладывать повторно. `[]` явно отказывается от добровольного получения Staggered. Книжный+1d к Melee attacks от **любого фактически имеющегося** Staggered работает независимо от включения в список. Этот ordinary bonus проходит cap/Drained, не применяется к защитному Melee/Defence и не превращается в free success.

Сохраняются прежние NPC Attack/target priority, NPC Help и PC SUFFER_WOUND strategy. Count search удаляет ID исключённого Bestigor без переназначения. Новых action costs/summary metrics и смены wire version нет. Все148JSON documents M9–M45 обновляются required пустыми arrays в requests/full echoes с сохранением остальных значений;48прежнихcatalog entries не меняются.

## Порядок и подтверждение Blood Rage

Owner исполняет отдельный typed source proof после обычной reservation Attack slot, до её Test/RNG. Proof связывает canonical Bestigor, caller policy, текущие actor/round/action ID и полный prefix. Только active actor с ещё не исполненной Attack и живой целью может получить этот добровольный Staggered. Нельзя применить его за PC/чужого NPC, заранее в начале encounter, после результата Test, повторно для того же действия либо вместо обычной Attack.

Наложение не расходует отдельный action, TurnEnd или RNG и не вызывает Wound само по себе. Если actor уже Staggered, proof повторного наложения не создаётся: это не repeated-Staggered impact. Пропуск обязательного proof для включённого actor перед Attack/TurnEnd отвергается. Если бой закончился до его действия, Condition не добавляется ради будущего неисполненного хода.

## Первая рана и однократный Glorious

Actual Brute0→1 profile-Wound ACK, включая Wound как цену repeated Staggered, создаёт source-bound entitlement на **следующую Attack этого Bestigor**. W1 не накладывает новый entitlement каждый раунд. Несколько Bestigors имеют независимые причины; помощь союзника не получает их Glorious. Protection/Help/переход раунда/voluntary Staggered не расходуют entitlement.

При подготовке следующего реального Attack Test добавляется rule-sourced Glorious; после фактического исполнения Attack entitlement потребляется ровно один раз независимо от HIT/MISS, числа провалов или поздней Near Miss PC. Bestigor на W2 до своего действия просто defeated, не создавая фиктивную Attack/unsupported. Source хранит actual W1 ACK и связь с единственным потребившим Attack; replay отклоняет подмену actor/ранней раны/Test, повторное применение и пропуск Glorious.

**Рекомендуемая тактика:** на этом Glorious NPC Attack перебросить все доступные провалы один раз, через существующий Test resolver. Это явный выбор стратегии, а не требование перебрасывать всё из книги. Начальные успехи/запертые dice не перебрасываются, каждое реальное повторение потребляет RNG. Grim cancellation и Help/free successes используют прежнюю семантику. NPC не тратит PC Fate и не меняет его counters. Пустой Blood Rage список не отключает обязательный Glorious от W1 или выбранную reroll strategy.

W0 запрет **выбора** Give Ground/Prone не является общей immunity к принудительному Prone. В текущем фиксированном owner price strategy выбирает SUFFER_WOUND; альтернативные NPC цены не добавляются этой вехой. Woodland movement, NPC Recover/лечение и новые Attack actions не входят в срез. Skin Wolf не подключается: его end-turn Warped Form требует собственной политики/регенерации и не может быть молча отключён ради количества профилей.

## Альтернативы

- **Рекомендовано:** весь Bestigor с явным Blood Rage списком, W1 one-shot Glorious и reroll всех доступных провалов. Один профиль обоснован новой общей механикой выбора/entitlement.
- Отложить M46 и выбрать другую законченную функцию. Замена Glorious обычным бонусом, отключение Rage при фактическом Staggered или повторное Glorious каждый раунд не предлагаются.

## Проверенная граница

1. Catalog/full source: printed Attack/Protection/Armour/Brute/Wound bands, exact cap8 только нового canonical Attack, сохранность48прежнихentries. Source aliases/partial renames/gear/numeric profiles отвергаются.
2. Required policy/native/schema: пустой/непустой списки, exact types/уникальность/actor roles; full echoes и count filtering без переназначения.148старыхJSON сохраняют остальные значения.
3. Actual Blood Rage: before-roll/after-slot proof, Staggered и ordinary+1d, уже Staggered без повторного Condition/Wound, независимость бонуса от policy, no bonus Defence, cap8/Drained/Help. Replay/missing/duplicate/wrong actor/action proofs и no extra costs/RNG.
4. Actual W1 ACK → следующая Attack Glorious → однократное consumption: direct/repeated-Staggered Wound, несколько Bestigors, переход раунда, miss/all successes/failed rerolls, W2 до хода. Literal d10 scripts доказывают первоначальные/повторные броски и отсутствие PC Fate spend; source/quality trace не теряется.
5. Native → compact trials/summary → count search → текущий JSON1/CLI-примеры. Изменение общего PC owner и NPC Test decisions требует адресных PC/Protection/Help/Fate/Wound зависимостей; объём определить по итоговому diff. Один representative process check оправдан новым typed source policy, полная backend matrix/wheel/project regression не обязательны без другого основания.

Согласование получено от пользователя; оно требовалось по [AGENTS.md](../../AGENTS.md), раздел «Автономная работа до согласованной вехи»: «Спрашивать при существенной неоднозначности правил, смене согласованного контракта или блокере с решением пользователя». Здесь вводятся обязательный публичный список добровольного Rage, новый canonical cap exception и явная стратегия NPC Glorious rerolls. [Статус](../project-status.md), [очередь](../roadmap.md).

Реализация выводит Glorious entitlement из actual ACK/Attack history без нового mutable bank; typed `PcBestigorGloriousSource` сохраняется в Attack proof и сверяется полным replay. [Policy](../../src/towr/domain/pc_npc_blood_rage_policy_models.py), [proof/entitlement](../../src/towr/domain/pc_bestigor_models.py), [owner](../../src/towr/domain/pc_melee_result_models.py), [projection](../../src/towr/domain/_pc_melee_projection.py), [runner](../../src/towr/engine/pc_melee_runner.py). [Catalog](../../tests/unit/test_m46_pc_bestigor_catalog.py), [native](../../tests/unit/test_m46_pc_bestigor_execution.py), [JSON](../../tests/integration/test_m46_pc_bestigor_json.py), [process](../../tests/integration/test_m46_pc_bestigor_process.py), [CLI-примеры](../examples/m46/README.md). Фактические команды/результаты/следующий шаг — в [статусе](../project-status.md).

Проверки M46: единый PC/Test checkpoint88модулей/815tests OK за48.184s; отдельно representative process parity1test OK за1.984s. Все30новыхtests прошли:8catalog,14native,7JSON/trials/search,1process. Это адресный checkpoint, не полный regression проекта. Независимое review конкретных дефектов не нашло.148прежнихJSON documents мигрированы только обязательным Rage key; подробные фактические CLI результаты и preservation checks — в статусе/примерах.

Уточнение формулировки при M58: GM144 явно говорит Melee attacks; прежнее краткое «+1d Melee» не разрешало общий Test bonus. Исполнение M46 уже применяло Blood Rage только в Attack preparation. Новая защитная Melee из M58 бонус не получает и W1 next-Attack entitlement не расходует; voluntary trigger по-прежнему только собственная Attack.
