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

## Реализация injury policies в K1

- Minion получает один Wound и сразу становится defeated;
- Brute и Monstrosity считают Wounds до профильного лимита без Wounds Table;
- дополнительный куб Wounds Table преобразуется в `AdditionalProfileWound`;
- Champion использует ту же Wounds Table policy, что и персонаж игрока;
- изменение диапазона Wounds возвращается как `ProfileStateChangeRequest`, чтобы профильная Ability могла обновить характеристики без скрытой логики в общей policy;
- Monstrosity Wound/Reaction разрешается в `src/towr/rules/monstrosity_resolution.py` с правильным владельцем решения;
- прямое наложение Staggered без Damage, например вторичный эффект Blunderbuss, использует общую repeated-Staggered policy и не запускает Monstrosity Reaction;
- правило отсутствия Staggered за неудачную Melee-атаку поддерживается явным исключением в `AttackRequest` и сохраняется в trace.

Проверки находятся в `tests/unit/test_k1_injury_resolution.py`, `tests/unit/test_k1_monstrosity_resolution.py` и `tests/unit/test_k1_kernel.py`.
