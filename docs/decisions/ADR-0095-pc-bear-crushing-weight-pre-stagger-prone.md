# ADR-0095: Bear / Crushing Weight и Prone до Staggered

Дата: 2026-11-06. Статус: **принято пользователем и реализовано M50**. Выбран полный Bear/Crushing Weight, ранний Prone и прежняя политика второй Attack.

## Почему следующий шаг — этот loadout

После M49 рассмотрены Great Stag / Crown of Antlers и Bear / Crushing Weight. Great Stag требует двух выбранных Attack profiles, нового условного second-action grant и решения о skill/cap Trample. Это самостоятельная следующая функция.

Для M50 рекомендован законченный Bear/Crushing Weight: подключить уже существующий K1 `ProneBeforeGiveGroundSpec` к PC owner/JSON и полностью сохранить Enduring Strength. Это одна пользовательская функция через все слои, а не отдельная веха для каждого слоя. Новый общий effect оправдывает один проверочный профиль вместо формального чанка3–5.

## Источники и профиль

Непосредственно сверена полная локальная карточка BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Bear138: WS4/S5/T5/Ag3, Normal Brute3, Resilience6 armoured. Crushing Weight Close3d/3 Damage7; попадание даёт Prone до возможности Give Ground. Athletics3d/3 Protection. W1–2Drained, W3defeat. Enduring Strength после успешной Attack позволяет второе действие Attack по **другому** Close enemy; Fearsome даёт Broken после Give Ground от его атак.

BOOK-PLAYER-GUIDE1.4, гл.V Dice Modifiers107 / Attack118 / Prone123: cap2×Characteristic, prone target даёт higher ground последующей Melee attack, ordinary Recover снимает Prone при отсутствии ongoing причины. Existing [M39](ADR-0087-pc-bear-second-attack-policy.md) сохраняет этот альтернативный Bear attack unselected с отдельными3d/cap8; не применять ещё один PC weapon penalty.

Предложен canonical `BEAR_CRUSHING_WEIGHT = bear_crushing_weight`, definition ID `pc-book-npc:bear_crushing_weight`, source `BOOK-GM-GUIDE:1.1:p138:bear_crushing_weight`. Natural hands=null/noWeapon/noShield. Attack — `InlineProfile(3,3,8)`, Damage7; Protection — `InlineProfile(3,3)`/null, T5Res6. Sweeping Claws остаётся unselected. Old Sweeping Claws definition/metadata не меняются.

## Публичная граница PC JSON1

Existing `attack.secondary_effects` получает вторую закрытую форму:

```json
{
  "kind": "prone_before_give_ground",
  "rule_id": "RULE-PROFILE-CREATURE-010:crushing-weight-prone",
  "affects_monstrosities": true
}
```

Все три поля required, unknown fields/типовые aliases отвергаются; defaults не подставляются. Typed mapping — существующий `ProneBeforeGiveGroundSpec`. Native source admission разрешает эту форму только в полном canonical Bear/Crushing Weight. Authored/другие book NPC не получают произвольного pre-Stagger Prone. Сохраняется максимум одного effect в этой PC family.

Прежний descriptor `condition_on_hit`/Drained остаётся post-Damage, с прежними source/retention semantics. Новый Prone **не** отображается на него: это другой порядок применения. Не расширять `ConditionOnHitSpec` общим phase enum или универсальным языком effects.

Explicit cap8 разрешить только Attack нового полного canonical Bear в дополнение к прежним Minotaur Greataxe/Bestigor; Ogre cap6 и остальные null сохраняются. Числовая schema уже допускает8, но меняется native source admission.

Existing required `npc_extra_attack_actor_ids` допускает оба Bear loadouts. Для указанного Crushing Weight Bear первая successful Attack и все её обязательные последствия завершаются; затем выбирается первый другой живой PC по прежнему enemy_target_priority. Второе действие использует тот же выбранный Crushing Weight и может также наложить Prone. `[]` отказывается только от optional второй Attack, не отключает Prone на попадании. Настройка/тактика M39 не меняются.

Новых полей верхнего уровня, counters, wire version или миграции164старыхJSON M9–M49 не требуется. Existing extra-Attack counts учитывают реальные выполненные slot2 actions обоих Bears; subset filtering и source echoes сохраняются. Каталог54→55.

## Порядок и жизнь Prone

1. Завершить actual Attack/Protection Tests. MISS не накладывает Prone. Новая Prone не даёт задним числом higher-ground бонус уже брошенному Test.
2. На HIT K1 накладывает Prone **до** Staggered choice и Wound lifecycle. Source/result должны сохранять этот effective pre-Stagger target. При повторном Staggered Prone уже запрещает Give Ground/Fall Prone; выбранный SUFFER_WOUND сохраняется.
3. При direct/repeated Wound завершить настоящие Wounds Table/Near Miss/Endurance/body/expiry. Near Miss отменяет Wound, сохраняя Prone от попадания; source предыдущего injury не подменяется поздней application.
4. После всех mandatory continuations выполнить разрешённую вторую Attack по другому живому PC и лишь затем один TurnEnd. При unsupported сохранить actual prefix без притворного второго действия. Смерть первой цели не отменяет ability, если другой живой PC существует; living Defenceless допустим как прежде. Третьей Attack нет.

Prone от Crushing Weight — обычное состояние до допустимого удаления, а не постоянная Wound cause. Standard self/ally Recover может его снять, не меняя прежних правил ongoing Wound-Prone. История попадания не должна повторно включать уже снятое состояние. Новая legitimate Attack может наложить его снова. Не помещать Prone в постоянный Spider Drained retention bank и не добавлять постфактум раннюю application.

W1Drained самого Bear применяется после actual profile-Wound ACK, включая Warped Form источник; оно фильтрует Test bonuses, но не убирает Damage7 или сам hit-Prone effect. Нет новых NPC Recover решений. Current SUFFER_WOUND не вызывает Fearsome; полное условие сохраняется в metadata.

## Адресная проверка

- Полная карточка/cap8/natural/Protection/W1–3 и обе способности;54старыхentries/metadata и164JSON остаются прежними. Full canonical source/partial rename, cap/null/Protection, wrong descriptor/false flag/aliases отвергаются до RNG.
- Literal MISS/HIT/positive tie/weak hit/direct Wound/repeated Staggered; Prone присутствует в actual pre-Stagger state и Wound source. Already Prone не создаёт повторного бонуса; Near Miss сохраняет hit-Prone, body/Endurance выполняются в своей очереди.
- Standard self/ally Recover снимают обычный hit-Prone; ongoing wound cause сохраняется по прежним правилам; новая Attack снова может повалить цель. Post-Damage Drained/его expiry-retention не меняются.
- Enduring Strength: both Bears/selected/declined, different target/current priority/последняя смерть/Defenceless, pending/unsupported/once-only/replay, actual action receipts/counters/один TurnEnd. Warped Form W1 даёт Bear Drained.
- Current JSON1 schema/codec/semantic guards/full echoes, trials/count search и полезный CLI-пример. Выбрать nearest K1 secondary/Stagger/Wound/Fate/Recover/PC owner/extra-action consumers по итоговому diff. Полный project regression/wheel/backend matrix не назначается автоматически; process cases заранее отделяются от Windows sandbox.

## Что остаётся для Great Stag

GM176: Mighty Antlers4d3Damage6, Charge inflicts Prone; Trample5d3Damage5, только Prone enemy; Athletics5d4, WS4/S5, W2Drained/W3defeat. Crown of Antlers даёт вторую Trample Attack, когда его attack заставляет enemy упасть Prone, и отдельно выбирает destination Give Ground. Current scene не выполняет Charge/Give Ground.

До следующей реализации требуется конкретизировать: считается ли accepted Wound/failed Wound Endurance после обычной Antlers Attack таким trigger, что делать с уже Prone целью, и какую текущую Prone цель выбирать для optional Trample. Не подменять это Bear grant, который требует другой цели. Напечатанный Trample5d3 здесь не помечен Skill: при WS4/S5 нужно обосновать соответствующий Characteristic/skill/cap, а не выводить его только из числа кубов. Эти вопросы не разрешаются автоматически введением Crushing Weight.

## Согласование

По [AGENTS.md](../../AGENTS.md), раздел «Автономная работа до согласованной вехи»: «Спрашивать при существенной неоднозначности правил, смене согласованного контракта или блокере с решением пользователя». Для M50 меняются допустимые descriptor, canonical cap8 и круг участников existing policy; порядок Prone следует из книги и готового K1 rule.

Пользователь выбрал сначала полный Bear/Crushing Weight. Альтернатива — сначала продолжить разбор Great Stag — отложена до следующей функции. [Статус](../project-status.md), [очередь](../roadmap.md).

Реализация: [catalog](../../src/towr/domain/pc_npc_catalog.py), [pre-Stagger target/Drained boundary](../../src/towr/domain/pc_hit_condition_models.py), [owner projection](../../src/towr/domain/_pc_melee_projection.py), [source admission](../../src/towr/domain/pc_melee_models.py), [wire](../../src/towr/adapters/_pc_melee_scenario_json.py). [Catalog tests](../../tests/unit/test_m50_pc_crushing_weight_catalog.py), [literal native tests](../../tests/unit/test_m50_pc_crushing_weight_execution.py), [JSON/search](../../tests/integration/test_m50_pc_crushing_weight_json.py), [CLI-примеры](../examples/m50/README.md). Фактическая приёмка и следующий шаг — в [статусе](../project-status.md).
