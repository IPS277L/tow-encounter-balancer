# Corruption

Источник: `BOOK-GM-GUIDE`, версия 1.1, глава Corruption, страницы 70–80. Статус области: `draft`; это долгосрочное состояние персонажа и кампании, в коде отсутствует.

## RULE-CORRUPTION-001 — Exposure to Chaos

В конце дня, в котором персонаж подвергался воздействию Chaos, он делает один Willpower Test. Используется худшая экспозиция дня; дополнительные penalties за несколько воздействий остаются решением GM.

| Exposure | Modifier | Примеры границы |
|---|---:|---|
| Subtle | — | краткий контакт с очищенным wyrdstone, бой с Beastmen/mutants |
| Profane | `-1d` | Miscast, сырой wyrdstone, Chaos ritual/minor daemon |
| Ruinous | `-2d` | profane spell, текст Liber Chaotica, бой с daemon |
| Soul-Searing | automatic failure | Realm of Chaos, possession, искренняя отдача души |

При провале GM выбирает одну уместную Condition и персонаж становится Vulnerable. Condition — немедленное последствие Test; Vulnerable — отдельное persistent corruption state, не значение общего `Condition` enum.

Источник: страницы 71–72.

## RULE-CORRUPTION-002 — стадии Path to Corruption

Состояния образуют направленный lifecycle:

1. `Vulnerable`: GM ровно один раз предлагает небольшой boon за уступку тёмной стороне. Принятие переводит в Tarnished; отказ снимает Vulnerable до следующего проваленного Corruption Test.
2. `Tarnished`: состояние постоянно без отдельного redemption; примерно раз в несколько sessions GM может предложить permanent boon за добровольную жертву. Принятие переводит в Tainted, отказ оставляет Tarnished.
3. `Tainted`: персонаж получает сильный boon и ruinous drawback конкретного Path; последующие жертвы ведут к Damned.
4. `Damned`: персонажа разрешено играть ещё одну финальную session, после чего он становится NPC под контролем GM.

Path выбирается персонально либо создаётся GM по образцу пяти приведённых вариантов. Переходы зависят от явного решения игрока/GM и narrative predicates; kernel не выбирает искушение, жертву или момент предложения.

Источник: страницы 72–73.

## RULE-CORRUPTION-003 — обнаружение и redemption

Обычный наблюдатель может заметить Tarnished или Tainted через Very Difficult (`-2d`) Awareness Test. Существо, способное ощущать Winds of Magic, использует обычный Awareness Test против Tainted. Damned распознаётся таким наблюдателем без Test. Явная внешняя mutation не требует этих правил скрытого обнаружения.

С разрешения GM персонаж может быть искуплён в подходящий значимый момент: он отказывается от всех даров и устраняет причину своего падения через крупное испытание. После искупления он обязан всегда противостоять Chaos; второе падение означает немедленную damnation. Это исключительная narrative procedure без фиксированного Test или числа successes.

Источник: страницы 72–73.

## RULE-CORRUPTION-004 — Child of the Forest

- Vulnerable boon: до конца session Athletics, Awareness, Endurance и Melee Tests для охоты, выслеживания или убийства в дикой местности бросаются обычно, но независимо от кубов достигают жестокого успеха.
- Tarnished bargain: после отказа от Asset, долга или иной связи с цивилизацией персонаж получает одну concealable mutation: `+1 Resilience` поверх armour; нормальное ночное зрение; либо unarmed attack с `S+2 Damage` вместо Staggered. Затем он становится Tainted.
- Tainted: последующие заметные mutations и жертвы определяет GM; точной таблицы или cadence нет.
- Damned: на финальную session Strength, Toughness и Resilience увеличиваются на `+2`, а GM может дать Abilities любого Beastman. После session персонаж становится NPC.

Источник: страницы 74–75.

## RULE-CORRUPTION-005 — Blood Must Flow

- Vulnerable boon: немедленная бесплатная дополнительная Melee attack; независимо от броска она убивает текущего врага. Принятие переводит в Tarnished.
- Tarnished bargain: за череп достойного противника выбирается один permanent boon — вторая Melee attack как дополнительное действие каждый turn; `+2 Strength`; либо `+1d` на Wounds Table при нанесении Wound в Melee. Получатель становится Tainted.
- Tainted: GM постепенно делает больше небоевых Tests Grim, а больше Melee Attack Tests Glorious; убрать обнажённое оружие требует Grim Willpower Test. Остальные потери контроля narrative и не имеют фиксированной cadence.
- Damned: в финальную session Damage каждого удара удваивается; затем персонаж становится NPC/покидает игру.

Источник: страницы 75–76.

## RULE-CORRUPTION-006 — Secrets of Sorcery

- Vulnerable boon: персонаж может сотворить любой spell, включая неизвестный, с Potency `9`; одновременно немедленно бросается `3d` по Miscast Table, причём эффект центрируется на другом находящемся рядом персонаже. Затем знание исчезает и персонаж становится Tarnished.
- Tarnished bargain: GM может повысить Wizard Level либо предоставить новые spells; требуемая жертва связана с уничтожением преследователя магии. После выполнения персонаж становится Tainted.
- Tainted: все Casting Tests Glorious; каждая финальная `9` добавляет два Miscast Dice вместо одного. Grimoire или magic item рекомендуется встречать примерно раз в две sessions. После девятого отказа от финального дара персонаж теряет прежнюю силу, и все Casting Tests навсегда становятся Grim; принятие делает его Damned.
- Damned: финальная невозможная arcane act определяется GM и не имеет числового spell contract; после неё персонаж теряется.

Источник: страницы 76–77.

## RULE-CORRUPTION-007 — Enduring the Unendurable

- Vulnerable boon временно снимает выбранное тяжёлое страдание, болезнь или одну серьёзную Wound; конкретная форма определяется GM. Принятие переводит в Tarnished.
- Tarnished получает `-1d` к большинству Charm Tests. За распространение страдания GM может дать один из тематических даров: `+1 Resilience`; immunity to disease; либо лечение всех Wounds после одной ночи отдыха с сохранением уродующего следа. После обращения бывшего друга/товарища персонаж становится Tainted.
- Tainted продолжает бросать растущий пул Wounds Table, но Wounds кроме severed limbs и decapitation не оказывают эффекта; Drained, Blinded и Deafened также не мешают. Значение «не оказывают эффекта» требует отдельного suppression layer и не удаляет записи Wounds/Conditions.
- Damned в финальном деянии может быть убит только огнём или decapitation; его присутствие само является Corruption exposure. Если после деяния его не убить и полностью не сжечь, остальные заражаются в течение дня. Детали supernatural protection и infection определяет GM.

Источник: страница 78.

## RULE-CORRUPTION-008 — Dark Obsession

- Vulnerable boon может быть Unmitigated Success, временный Asset или шанс получить признание. Если персонаж не отказывается от дара и выбирает личное превознесение, он становится Tarnished.
- Tarnished как минимум раз за session получает Distracted на Tests, не связанные с воспроизведением момента совершенства. За персональную жертву предлагается один permanent boon: все Tests одного Skill Glorious, повышение Status либо выбранный Asset; принятие переводит в Tainted.
- Tainted в каждый Downtime случайно теряет `1` rating несвязанного с obsession Skill, минимум до `1`. Если другая Career лучше соответствует obsession, персонаж должен пытаться перейти в неё либо теряет доступ к Career Talent и Assets текущей Career. При каждом отказе от части прежней личности он может получить один уместный boon: `+2` к Skill; at-will Distracted для выбранных целей через сверхъестественную привлекательность; новый Gold Asset; obsession выбранного NPC персонажем; либо любой Talent без prerequisites.
- Damned в финальном выступлении получает Unmitigated Success на каждый Test; после завершения персонаж исчезает из игры.

Источник: страницы 79–80.

## Архитектурная граница

Corruption требует отдельных campaign-компонентов: дневной журнал exposures, стадия и выбранный Path, уже сделанное предложение, принятые boons/жертвы, session/downtime cadence и владение персонажем после damnation. Точные модификаторы можно представить типизированными effects, но расплывчатые формулировки вроде «больше Tests» и выбор сюжетной жертвы должны приходить от GM/scenario policy, а не вычисляться resolution kernel.
