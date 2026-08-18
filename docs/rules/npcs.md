# NPC и профили противников

Основной источник: `BOOK-GM-GUIDE`, страницы 89–91. Дополнительный источник: `BOOK-PLAYER-GUIDE`, страница 191. Статус: базовые injury policies `implemented`; профильные Special Abilities остаются `draft`.

## RULE-NPC-001 — типы NPC

NPC относятся к одному из четырёх типов: Minion, Brute, Champion или Monstrosity. Тип главным образом определяет поведение в бою и модель Wounds.

## RULE-NPC-002 — Minion

Minion побеждён сразу после получения одного Wound. Атакующий при участии GM определяет, убит ли NPC, оглушён, обезоружен или принуждён сдаться.

## RULE-NPC-003 — Brute

Brute выдерживает профильное количество Wounds и может менять свойства при их накоплении. Он не бросает по Wounds Table. Если эффект добавил бы дополнительный куб к броску Wounds Table, Brute вместо этого получает дополнительный Wound.

## RULE-NPC-004 — Champion

Champion получает Wounds по модели персонажа игрока и бросает по Wounds Table.

## RULE-NPC-005 — Monstrosity

Monstrosity использует профильное количество Wounds и Reactions вместо Wounds Table. Дополнительный куб Wounds Table превращается в дополнительный Wound.

Особые правила:

- может проходить сквозь меньших существ и сопоставимые препятствия;
- при Attack action может использовать все атаки профиля;
- каждая Attack Test и каждая Opposed Test выполняются отдельно в выбранном Monstrosity порядке;
- обычно старается выбирать разные цели, но конкретные атаки и доступные цели определяются профилем и контекстом;
- не получает Staggered за неудачную Melee-атаку;
- Give Ground в Zone с меньшим противником не создаёт Broken;
- при Damage, не превышающем Resilience, получает Staggered; если уже Staggered, выбирает Wound либо Reaction;
- при Damage выше Resilience атакующий выбирает Wound либо Reaction.

## RULE-NPC-006 — обычное число атак

NPC может иметь несколько атак или вариантов оружия, но без специального правила использует только одну атаку при выполнении Attack action. Наличие атаки в профиле не гарантирует, что NPC несёт соответствующее оружие в каждом столкновении.

## RULE-NPC-007 — профиль атаки

Профиль атаки содержит Range, готовый dice/target профиль, Damage, требование к рукам и специальные свойства. Значения броска выводятся из Characteristic и Skill, но хранятся в профиле NPC для удобства GM.

## RULE-NPC-008 — Protection

Protection задаёт готовый профиль встречной защиты. Обычно он выводится из Athletics; вооружённый NPC может использовать лучший Defence против ближней атаки. Профиль также указывает наличие щита и возможность Defence против дальних атак.

## RULE-NPC-009 — Default Skill

Default Skill применяется ко всем навыкам, для которых профиль не задаёт отдельного значения. Явные навыки переопределяют default.

## RULE-NPC-010 — свойства оружия

NPC не получает автоматически все свойства одноимённого оружия игрока. Применяются только эффекты, явно указанные в NPC-профиле или общем правиле.

## RULE-NPC-011 — area и multi-target эффекты

Универсального AoE-правила нет. Число атак, цели и вторичные эффекты определяются конкретным профилем атаки, оружия, Special Ability или Monstrosity. Старый прототипный алгоритм AoE отменён пользователем.

## RULE-NPC-012 — Monstrous Flight Reaction

Griffon, Dragon и Wyvern при срабатывании Monstrous Flight дают Ground, предпочитая вертикальное перемещение в midair Zone, если оно доступно. Если Monstrosity уже давала Ground в текущем ходу, вместо этого она получает Wound. Источник: GM Guide, страницы 175, 177–178.

В K1 kernel переносит конкретный `MonstrousFlightReactionSpec`, дополнительные профильные Wounds исходной атаки и условные эффекты в `MonstrosityReactionRequest`. После добавления актуального spatial-контекста `resolve_monstrosity_reaction` возвращает типизированный `GIVE_GROUND` либо `SUFFER_WOUND`. В первой ветви `GiveGroundRequest` сохраняет предпочтение `VERTICAL_MIDAIR_IF_ABLE`; во второй используется общая профильная injury policy. Terrifying применяется после подтверждённого исхода тем же правилом, что и для обычного impact.

## RULE-NPC-013 — Unsteady Reaction

При срабатывании Unsteady Giant получает Prone. Когда Giant действительно падает Prone, все существа в его Zone, включая самого Giant, проверяют Athletics против Hazard (3). Источник: GM Guide, страница 183.

В K1 `UnsteadyReactionSpec` добавляет Prone к состоянию Giant и возвращает `ReactorZoneHazardRequest`. Этот запрос означает всех существ в Zone реагирующего Giant, но не выбирает их без spatial state. Если Giant уже Prone, Condition не накладывается повторно и Hazard не создаётся: результат явно получает исход `ALREADY_PRONE`. Staggered при падении не снимается. Условие Terrifying не срабатывает, поскольку Unsteady само по себе не создаёт Give Ground или Wound.

## RULE-NPC-014 — Monstrous Regeneration Reaction

Ghorgon и Troll Hag в конце своего хода могут выбрать восстановление одной Wound, получая Staggered, если этого Condition ещё нет. Wound от огня восстановить нельзя. Если их Reaction срабатывает, они не могут регенерировать на следующем ходу. Источник: GM Guide, страницы 151 и 181.

Текущий K1-срез реализует только немедленное последствие Reaction: `MonstrousRegenerationReactionSpec` возвращает исход `REGENERATION_SUPPRESSED` и source-aware `SuppressRegenerationNextTurnRequest`. Состояние, Wounds и Conditions при этом не меняются. Future turn orchestration должно сохранить запрет, применить его к следующей возможности регенерации и однократно погасить. Добровольное end-turn лечение, Staggered и проверка огненного источника Wound пока не исполняются без turn/wound-source state.

## Реализация injury policies в K1

- Minion получает один Wound и сразу становится defeated;
- Brute и Monstrosity считают Wounds до профильного лимита без Wounds Table;
- дополнительный куб Wounds Table преобразуется в `AdditionalProfileWound`;
- Champion использует ту же Wounds Table policy, что и персонаж игрока;
- изменение диапазона Wounds возвращается как `ProfileStateChangeRequest`, чтобы профильная Ability могла обновить характеристики без скрытой логики в общей policy;
- Monstrosity Wound/Reaction разрешается в `src/towr/rules/monstrosity_resolution.py` с правильным владельцем решения;
- прямое наложение Staggered без Damage, например вторичный эффект Blunderbuss, использует общую repeated-Staggered policy и не запускает Monstrosity Reaction;
- профильные атаки с обычным Damage и формулировкой `hits inflict Condition` используют `ConditionOnHitSpec`, не replacement impact;
- Terrifying у Dragon/Wyvern использует `ConditionOnGiveGroundOrWoundSpec`: Broken следует только после Give Ground или принятой Wound, но не после Near Miss;
- Monstrous Flight у Griffon/Dragon/Wyvern разрешается отдельным типизированным resolver и сохраняет различие между лимитом Reaction «в текущем ходу» и общим Give Ground «раз за раунд»;
- Unsteady у Giant применяет Prone и только при новом падении создаёт Hazard (3) для всех существ в Zone;
- Monstrous Regeneration у Ghorgon/Troll Hag создаёт source-aware запрет регенерации на следующий ход без немедленного изменения injury state;
- правило отсутствия Staggered за неудачную Melee-атаку поддерживается явным исключением в `AttackRequest` и сохраняется в trace.

Проверки находятся в `tests/unit/test_k1_injury_resolution.py`, `tests/unit/test_k1_monstrosity_resolution.py`, `tests/unit/test_k1_monstrosity_reaction_resolution.py` и `tests/unit/test_k1_kernel.py`.
