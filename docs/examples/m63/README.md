# M63: PC Melee/Athletics против Close Shooting

PC явно выбирает навык для защиты от близкого выстрела. Без настройки действует прежний порядок Defence с рабочим shield, иначе Athletics. [Правило](../../rules/combat.md#pc-close-shooting-protection-m63), [принятый контракт](../../decisions/ADR-0105-pc-close-shooting-protection-choice.md).

Optional поле participant текущего PC JSON1:

```json
"close_shooting_protection_skill": "melee"
```

Допустимы `melee` и `athletics`; null/`defence`/прочие Skills не принимаются. Athletics выбирается и при held shield. По PG94 Melee opposition в Close доступен без отдельного weapon requirement. Для учёта рук принята fixed тактика: использовать пригодный active held weapon/grip, иначе защищаться без рук. Выбор не подбирает dropped предмет и не меняет оружие/loaded state. Throwing/Net, Brawn и incoming Melee сохраняют прежнюю защиту.

Melee Test получает общие Traits фактически удерживаемого оружия, но не Sword/Glaive Defence bonus или Attack-only Warhammer bonus. Нет counterattack/дополнительного action/Damage/расхода PC Pistol. Injury12 учитывает использованный grip; без рук новый Critical не создаётся. Действуют Drained/Blinded/W10/Fate и прежние mandatory Wound tails.

Protection Help теперь допускает:

```json
"help_policy": {
  "beneficiary_id": "pc2",
  "target": "first_incoming_protection",
  "protection_skill": "melee"
}
```

Это настоящий Melee Help Test и обычное действие. Receipt адресуется конкретному NPC Protection Test, отдельно от `target:"melee_attack"`. Неподходящий/неисполненный Test не переносит бонус. First-current-NPC тактика не предсказывает будущий Reload или NPC Help. Pistol-PC сам по-прежнему не выбирает роль helper, но может получать помощь в защите.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m63/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m63/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): Sword+Shield PC1 помогает Staff+Shield PC2, который защищается Melee; PC1 для своей Shooting-защиты выбрал Athletics. Ogre действует первым среди NPC, Official имеет прежний explicit Broken exit. Seed42/6trials/8rounds:4objective/0party defeated/2limit/0unsupported,133actions,44started/40completed rounds, без потерь PC.44PC Help, Official выходит во всех6trials.

Native trial0: round_limit/24actions,8Help, одна actual application к Ogre Shooting в раунде1; PC2 бросает5Melee dice. Последующие Help могут остаться unused, пока первый NPC Reload: бонус не попадает в Dexterity и не переадресуется второму стрелку. Это расход тактики, не гарантированный бонус каждому входящему удару.

[Balance request](pc-melee-balance.request.json) и [CLI result](pc-melee-balance.result.json): Ogre1/Official0–1,2состава по2trials. Без Official:2objective/34actions/12Help; с ним:1objective+1limit/45actions/15Help. PC choice/Protection Help остаются в полном root/candidate source. Удаление последнего shooter также сохраняет party preferences; их неиспользование допустимо.

Выборки демонстрационные и не оценивают истинную вероятность/оптимальный состав. Unaware/другие ranges/general inventory/автоматический best Skill не добавлены.216прежнихJSON и59NPC definitions сохранены, wire version/метрики прежние.
