# M62: NPC Help конкретному выстрелу

Militia/Strength in Numbers и Goblin/Night Goblin/Horde могут помочь Official или Ogre сделать Shooting Test. У загруженного стрелка каждый настоящий Help даёт отдельный +1d с превышением обычного cap; у пустого — помощник атакует сам, пока стрелок Reload. [Правило](../../rules/npc-profile-catalog.md#npc-shooting-help-m62), [контракт](../../decisions/ADR-0104-pc-npc-shooting-help.md).

Используется прежний current PC JSON1 список, без новых полей:

```json
"npc_help_policies": [
  {"helper_id": "militia1", "beneficiary_id": "ogre1"},
  {"helper_id": "goblin1", "beneficiary_id": "ogre1"},
  {"helper_id": "night1", "beneficiary_id": "official1"},
  {"helper_id": "net1", "beneficiary_id": "ogre1"}
]
```

Все помощники должны действовать раньше своего получателя; несколько helpers могут помогать одному Test. Сцена явно считает этих NPC союзниками. Peasant/Cultist и Orc/Big ’Un остаются Melee-only; их назначение к Pistol отклоняется до RNG. Source не позволяет вручную выбрать Skill или величину бонуса.

Help занимает обычное действие и учитывается в прежних NPC Help counters, но не делает Test/RNG. Получатель/Skill/round/Test ID фиксируются: бонус не переходит на Reload, следующую атаку, другую цель или новый раунд. Если бой завершился до выстрела, Help остаётся потраченным. Drained receiver вызывает Attack fallback, а Drained helper может выполнить no-Test Help. Net helper не расходует сеть при Help; его Attack fallback исполняет прежний Net→Spear путь.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m62/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m62/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): PC Pistol+Shield/Sword backup и Staff+Shield против четырёх helpers и двух стрелков, seed42/6trials/8rounds. Получены0objective/0party defeated/6limit/0unsupported,230actions,48started/48completed rounds; в1trial побеждён хотя бы один PC. Всего19NPC Help: Militia0, Goblin6, Night Goblin6, Net Goblin7, стрелки0. PC первыми атакуют Militia, поэтому в этих seeds она не успевает помочь; наличие policy не гарантирует выполненного действия.

Native trial0: round_limit/44actions. В раунде1 Goblin/Night/Net исполняют3Shooting Help; далее стрелки действительно Reload, а помощники используют собственные Attack. Official Reload в раундах2–5/7–8, Ogre2–6/8. Это не помощь Dexterity: реальные NPC Help receipts отсутствуют в Reload Tests. Отдельные детерминированные тесты проверяют все4helper loadouts с обоими стрелками, cap bypass, Net stock и возврат Help после завершённого Reload.

[Balance request](pc-melee-balance.request.json) и [CLI result](pc-melee-balance.result.json): Militia/Official0–1, остальные4NPC фиксированы;4состава по2trials. Исключение helper либо shooter удаляет соответствующую пару без переназначения, полный source остаётся в root/candidate echoes.

| Militia | Official | Objective | Party defeated | Limit | Unsupported | Actions | NPC Help |
|---|---|---|---|---|---|---|---|
| 0 | 0 | 2 | 0 | 0 | 0 | 46 | 2 |
| 0 | 1 | 1 | 0 | 1 | 0 | 62 | 4 |
| 1 | 0 | 1 | 0 | 1 | 0 | 63 | 4 |
| 1 | 1 | 0 | 0 | 2 | 0 | 78 | 6 |

Малые выборки демонстрируют интерфейс и тактику, не истинную вероятность или лучший состав. Limit/unsupported остаются в знаменателе. PC Protection Help сохраняет прежнюю привязку к первому текущему NPC и не предсказывает его будущий Help: такой receipt может остаться unused, но не переходит на другого стрелка. PC Shooting Help, помощь Reload, новые NPC loadouts и wire version не добавлены.212прежнихJSON и59definitions сохранены.
