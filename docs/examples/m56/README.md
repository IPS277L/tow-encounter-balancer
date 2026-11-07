# M56: NPC Melee/Athletics против Close Shooting

Для четырёх уже существующих loadouts можно явно выбрать защитный Skill от Close Shooting: State Trooper Halberd/Spear, пеший Empire Knight/Lance без щита и Knight of the White Wolf/Wolf Hammer. От Melee эти NPC сохраняют прежнюю Defence. [Правило](../../rules/combat.md#pc-close-shooting-protection-m56), [принятый контракт](../../decisions/ADR-0101-pc-close-shooting-npc-protection-choice.md).

Optional настройка находится на уровне scenario/template нынешнего PC JSON1:

```json
"npc_close_shooting_protection_policies": [
  {"actor_id": "trooper1", "skill": "melee"},
  {"actor_id": "spear_trooper1", "skill": "athletics"},
  {"actor_id": "empire_knight1", "skill": "athletics"},
  {"actor_id": "wolf_knight1", "skill": "melee"}
]
```

Одна запись на NPC, только эти canonical loadouts, точные actor_id/skill без собственных dice/caps. Если поле присутствует, список непустой; null/пустой список/duplicates/unknown fields/PC actors отвергаются. Нужен Pistol-PC в party. Без настройки действует прежняя выбранная Protection, которая тоже должна быть законной против Shooting. Подбор удаляет записи исключённых NPC без переназначения; пустой остаток означает отсутствие поля.188прежнихJSON не мигрируются.

Troopers используют Melee3d/3/cap6 либо Athletics3d/3/cap6. Knights — Melee4d/4/cap8 либо Athletics2d/3/cap6. У Knights Ag3, поэтому maximum6; уменьшение до printed2dice соответствует уже учтённой heavy armour. Второй armour penalty не добавляется. Прежняя Defence не переписывается.

Защитный Melee не наносит ответный Damage и не тратит действие NPC, не получает Attack-only outnumbering/higher-ground/Charge или PC weapon Traits. Tie/both-fail остаются обычными исходами Attack. Prone NPC даёт–1d самому Shooting, W1Drained/W2defeat Knights сохраняются; Unaware/Defenceless не получают opposition. Pistol+Shield/Reload/Fate работают по M54/M55.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m56/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m56/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): mixed party из Pistol+Shield и Sword+Shield против всех четырёх loadouts, policy как выше; seed42,6trials,8rounds. Получены0objective/4party defeated/1limit/1unsupported,114actions,30started/25completed rounds;5trials с поражением хотя бы одного PC.

Native разбор trial1 подтвердил прежнюю границу M54: третья рана PC1 даёт W16/unusable arm, а позднее фактически необходимый Reload требует второй руки. Stop — `pistol_reload_hands_unavailable`, не отказ нового Melee/Athletics пути и не поражение оставшегося PC. Исполненные costs/losses сохраняются.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json): Halberd Trooper и Spear Trooper фиксированы по одному; Empire Knight и White Wolf Knight — по0–1, четыре состава по2trials. Каждый loadout имеет отдельную однородную count group.

| Empire Knight | White Wolf Knight | Objective | Party defeated | Limit | Unsupported | Actions |
|---|---|---|---|---|---|---|
| 0 | 0 | 2 | 0 | 0 | 0 | 10 |
| 0 | 1 | 0 | 2 | 0 | 0 | 40 |
| 1 | 0 | 0 | 1 | 1 | 0 | 47 |
| 1 | 1 | 0 | 1 | 0 | 1 | 25 |

Малые выборки показывают интерфейс и выбранную тактику, а не истинные вероятности или оптимальный состав. Unsupported остаётся в знаменателе trials; observation относится к реальному prefix.
