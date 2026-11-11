# M59: Pistol против Halfling Thief Stealth

Halfling Thief/Dagger сохраняет исходную Stealth Protection и против Pistol. GM1.1 VII103 Now You See Me разрешает Stealth против атак, о которых цель знает; ограничения на Melee нет. Printed Stealth3d/5, cap6 от Ag3. [Правило](../../rules/combat.md#pc-close-shooting-protection-m59), [исходный typed permission](../../decisions/ADR-0090-pc-halfling-stealth-protection.md).

Новых полей в PC JSON1 нет. NPC остаётся полным canonical `pc-book-npc:halfling_thief_dagger` со своей Protection `stealth`; Pistol profile задаётся как в [M54](../m54/README.md), shield — как в [M55](../m55/README.md). Preflight создаёт существующий HalflingStealthProtectionPermission с actual actor и полной definition, а owner/K1 проверяют его при реальной атаке. Generic/renamed/численно поддельный Thief не получает разрешение только по Skill.

Melee/Athletics override не нужен: Thief уже использует Stealth как основную Protection. Поле npc_close_shooting_protection_policies остаётся ограниченным12sources/двумя Skills и не принимает stealth. Unaware/Defenceless остаются без opposition/ability trace. Fixed PC source начинается aware; исчезновение, Move Quietly и кража автоматически не выполняются. Thief имеет обычные Attack turns, без hidden action/counterattack/лишнего RNG. Reload/расход заряда и source replay прежние.

По Protection выбранный каталог57 теперь имеет44готовых Athletics/Shield Defence,12явных Melee/Athletics paths и1specific Thief Stealth path. Это не полная реализация всех NPC cards/Abilities или обещание отсутствия Wound/Reload stops.200прежнихJSON M9–M58 сохранены побайтно.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m59/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m59/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): mixed party Pistol+Shield/Sword+Shield с authored armour_bonus1 у обоих против2Thieves+1Footpad; seed42,6trials,8rounds. Получены6objective/0party defeated/0limit/0unsupported,50actions,17started/11completed rounds; потерь PC нет. Оба weapons используют Stealth именно защищающегося Thief.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):1–2Thieves и0–1Footpad, четыре состава по2trials, party/тактика фиксированы.

| Thieves | Footpads | Objective | Party defeated | Limit | Unsupported | Actions |
|---|---|---|---|---|---|---|
| 1 | 0 | 2 | 0 | 0 | 0 | 2 |
| 1 | 1 | 2 | 0 | 0 | 0 | 4 |
| 2 | 0 | 2 | 0 | 0 | 0 | 4 |
| 2 | 1 | 2 | 0 | 0 | 0 | 14 |

Малая выборка показывает интерфейс и выбранную тактику, а не истинную вероятность или оптимальный состав. Полный root/candidate source, включая canonical Stealth, сохраняется в result echo; новый transport/version не вводится.
