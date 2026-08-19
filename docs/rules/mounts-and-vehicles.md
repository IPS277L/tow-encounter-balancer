# Mounts и Vehicles

Источник: `BOOK-PLAYER-GUIDE`, версия 1.4, глава Rules — Mounts & Vehicles, страницы 124–127. Статус области: `draft`; spatial, rider и vehicle state в коде отсутствуют.

## RULE-MOUNT-001 — mounted entity

Обученные mount и rider обычно считаются одной сущностью: используются Characteristics/Skills/Abilities rider с добавленными Abilities mount. Mount не получает отдельный turn. Сложный физический манёвр rider проверяет Athletics, испуг mount — Leadership.

Rider атакует своим weapon/Abilities либо атакой mount с profile mount. Входящая attack обычно направлена в rider. Только Monstrosity mount можно явно выбрать отдельной целью, после чего оно защищается собственными Abilities.

Dismount возможен в составе move; Prone, стаскивание или провал Athletics при прыжке dismount принудительно. После этого mount становится отдельным GM-controlled участником.

Источник: страница 124.

## RULE-MOUNT-002 — Horse

Horse: `WS 3, BS 0, S 3, T 3, I 3, Ag 4, Re 2, Fel 1`; Speed Fast, Resilience 3, Minion; Hooves `Close, 3d/3, Damage 3`; Protection Athletics `4d/4`.

Noble Steed даёт rider `+1 Resilience`, Speed Fast и на successful Charge против non-Monstrosity применяет Prone до возможного Give Ground. Bretonnian Warhorse игнорирует Agility penalties heavy armour/barding для control/opposition; Elven Steed даёт `+1d` соответствующим Athletics.

Источник: страница 124.

## RULE-MOUNT-003 — rider на Monstrosity

Rider на Monstrosity получает общие свойства Monstrosity, но Attack action имеет особый выбор:

- использовать все attacks профиля Monstrosity; либо
- использовать одну собственную attack и одну attack Monstrosity.

Входящие Wounds применяются к rider по его обычной модели, пока attack явно не нацелена на Monstrosity; в последнем случае используется injury/reaction policy самой Monstrosity. Это уточняет общее правило `RULE-MOUNT-001` и не объединяет Wounds rider и mount.

Источник: Gamemaster’s Guide 1.1, страница 92.

## RULE-VEHICLE-001 — управление и turn

Vehicle без driver не движется/не действует. Обычно Test не нужна; на пределе применяется контекстный driving Skill/Lore. В battle driver перемещает vehicle со всеми animals/passengers своим free move либо Manoeuvre; Athletics заменяется driving Skill. Только один driver и одно движение vehicle за turn.

Driver атакует своим weapon, attack тянущего animal либо profile vehicle; Ram доступен только при Charge. Attacker выбирает видимого passenger либо vehicle/animals. Prone passenger может упасть согласно закреплению.

Источник: страницы 124–125.

## RULE-VEHICLE-002 — Damage, Faults и wreck

Attack по vehicle unopposed: любой success — hit. Vehicle immune ко всем Conditions кроме Ablaze. Damage должен превышать Resilience и тогда создаёт один Fault; `ignores armour` вместо обычной семантики даёт `+1 Damage` armoured vehicle.

При достижении Max Faults vehicle wrecked: все на борту получают Staggered+Prone, а при движении делают Endurance против Hazard (2). Иначе бросается `1d10` Fault:

- `1–3` Scratched Paintwork — superficial;
- `4–5` Rough Ride — каждый passenger Endurance или Staggered;
- `6–7` Lost Luggage — GM выбирает trapping/Asset, свободные руки могут поймать Dexterity;
- `8–9` Fallen Passenger — случайный passenger Staggered+Prone и при скорости Endurance Hazard (2);
- `10` Locomotive Failure — Speed на step ниже; уже Slow перестаёт двигаться.

Bonus dice Wounds Table не влияют на Fault roll. Repair в downtime оплачивается; в adventure подходящий Lore+tools и несколько часов могут позволить Toil снять Fault(s).

Источник: страница 125.

## RULE-VEHICLE-003 — profiles

| Vehicle | Animals / occupants | Speed | Resilience | Max Faults | Ram |
|---|---:|---|---:|---:|---:|
| Trade cart | 1 / 6 | Normal | 5 | 3 | 3 |
| Light chariot | 2 / 2 | Fast | 6 armoured | 4 | 4 |
| Chariot | 2+ / 3 | Fast | 7 armoured | 5 | 5 |
| Personal coach | 2 / 6 | Fast | 5 | 4 | 4 |
| Stagecoach | 2+ / 8 | Fast | 6 | 4 | 5 |
| Travelling stage | 2 / 6 | Normal | 5 | 5 | 3 |
| Baggage wagon | 2+ / 8 | Normal | 5 | 6 | 3 |

Missing animal снижает carriage Speed на step; Slow затем не движется. Enclosed carriage защищает passengers от ranged пока не потерял все Wounds (то есть не wrecked); open platform обычно даёт cover. Ram использует Dexterity driver.

| Boat | Occupants | Row/Sail crew | Speed | Resilience | Max Faults | Ram |
|---|---:|---|---|---:|---:|---:|
| Rowboat | 3 | 1 / n/a | Slow row | 6 | 2 | n/a |
| River ferry | 12 | 2 / n/a | Slow row | 6 | 3 | 3 |
| River barge | 8 | 4 / 3 | Slow row/sail | 6 | 4 | 4 |
| Patrol boat | 15 | 12 / 4 | Normal row/sail | 9 armoured | 5 | 5 |
| Longboat | 32 | 30 / 4 | Fast row, Normal sail | 7 armoured | 5 | 6 |
| Trade cog | 15 | n/a / 8 | Fast sail | 8 | 6 | 5 |
| War galley | 50 | 30 / 16 | Fast sail, Normal row | 10 armoured | 8 | 6 |

Недостаточный dedicated crew запрещает движение. Rowing накладывает Drained без exceptional strength/breaks; weather может снижать sail Speed. Большие boats сами могут быть Zones.

Источник: страницы 126–127.
