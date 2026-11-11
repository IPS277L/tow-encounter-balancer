# M61: NPC Pistol и Exacting Reload против группы PC

Два новых книжных loadouts: Empire Official/Pistol и Imperial Ogre/Ogre Pistol. Каждый начинает с заряженным оружием, стреляет, затем тратит действия на накопление3успехов Reload. Завершение Reload позволяет стрелять следующим действием. [Правило](../../rules/npc-profile-catalog.md#npc-pistol-reload-m61), [контракт](../../decisions/ADR-0103-pc-npc-pistol-and-exacting-reload.md).

| NPC | Shooting | Reload Dexterity | Protection | Особенность |
|---|---|---|---|---|
| Official | 2d/3, cap4, Damage5, Close–Short | 3d/3, cap6 | Athletics3d/3 | W1Broken; W2defeat |
| Ogre | 3d/2, cap6, Damage5, Close–Medium | 2d/2, cap4 | Athletics3d/3 | W1–2Speed Normal; W3defeat |

Оба оружия1H и игнорируют armour. Reload берёт dice из Initiative, threshold из Default Skill — GM не назначает эти числа. Ogre Pistol сохраняет отдельный профиль GM103, не подменяется обычным Handgun или PC Pistol с меньшей дальностью.

В current PC JSON1 новый primary `definition.attack` явно содержит `skill:"shooting"`, `range_min:"close"` и `ignores_armour:true`; `range_max` хранит напечатанный верхний optimum. Эти дополнительные поля допускаются только полному canonical Official/Pistol или Ogre/Pistol. Соответствующий `enemies[]` требует:

```json
"pistol": {
  "initially_loaded": true,
  "has_blackpowder_lore": true,
  "has_blackpowder_kit": true,
  "ammunition_supply_confirmed": true,
  "reload_hand_policy": "two_available_hands"
}
```

Это явные условия сцены и выбранная тактика. У NPC одна рука держит Pistol, вторая свободна; нет shield/carried melee. Бой остаётся fixed Close без движения, кроме прежнего явного Broken exit. PC защищается Defence с рабочим shield, иначе Athletics. Defenceless не Opposes; Fate/Protection Help/Near Miss и последствия ран сохраняются. NPC Reload не является Recover/Help, входит в общее число действий; отдельного нового публичного counter нет.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m61/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m61/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): PC Pistol+Shield/Sword backup и Staff+Shield против обоих NPC, seed42/6trials/8rounds. Получены6objective/0party defeated/0limit/0unsupported,107actions,39started/33completed rounds; потерь PC нет. Official ушёл в3trials, эти3успеха учитываются отдельно от defeat.

Native trial0 подтверждает реальный цикл Ogre: три отдельных Reload Test по1success, затем loaded; итог objective_achieved,17actions. PC Pistol имеет независимый weapon instance/cycle, NPC progress ему не передаётся. Процессный representative отдельно проверяет действительные выстрелы обоих NPC и partial/completed Reload, равенство sequential/spawn records и summaries.

[Balance request](pc-melee-balance.request.json) и [CLI result](pc-melee-balance.result.json): Ogre фиксирован, Official0–1,2состава по2trials. Оба состава дали2objective, суммарные actions25 без Official и39 с ним. Count projection сохраняет survivor Pistol facts и удаляет policy исключённого Official без переназначения; полный root/candidate source включён в результат.

Это малые демонстрационные выборки, не оценка истинной вероятности/лучшего состава. В первом срезе NPC-стрелки не получают `npc_help_policies`: такой source отклоняется до RNG, а не исполняется с потерянным бонусом. Обычные mixed NPC Help остаются в прежней границе. Нет автоматической melee смены, Champion Wounds для Noble/Witch Hunter, движения/ranged distance AI или общего inventory.208прежнихJSON сохранены побайтно, каталог57→59.
