# M21: книжные NPC в PC balance

Первый конечный каталог содержит Footpad и Empire Townsfolk из GM Guide1.1. [Источники/правила](../../rules/npcs.md#исполняемый-каталог-pc-m21), [контракт ADR-0076](../../decisions/ADR-0076-first-pc-book-npc-catalog.md). Это боевые подпрофили для нынешней сцены, не весь бестиарий или полные NPC-карточки.

| Profile ID | Источник | Attack | Protection | Resilience |
|---|---|---|---|---|
| `footpad` | GM1.1,97 | Dagger Close3d/3, Damage2,1H | Athletics3d/3 | Toughness3+0 |
| `empire_townsfolk` | GM1.1,96 | Dagger Close2d/2, Damage2,1H | Athletics2d/2 | Toughness3+0 |

Оба Minion с пределом1Wound. Townsfolk получает именно напечатанные2d Protection, без пересчёта из Agility. NPC не наследует Traits одноимённого PC-оружия автоматически.

Python factory:

```python
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile, create_pc_book_npc, get_pc_book_npc_entry,
)

footpad = create_pc_book_npc(PcBookNpcProfile.FOOTPAD, "footpad1")
entry = get_pc_book_npc_entry(PcBookNpcProfile.FOOTPAD)
```

Factory возвращает свежий здоровый armed opposition snapshot. Metadata сохраняет книгу/версию/главу/страницу и способности с условиями/эффектами. Lurker Footpad делает spotting Awareness Grim вне боя; Streetwise Townsfolk даёт +1d Awareness против pickpocket. В этих aware/noambush боях соответствующих ситуаций нет. Это не удаление способностей и не их общий executor.

Текущий PC JSON1 использует полный числовой source, включая обязательный Skill:

```json
{
  "protection": {
    "source_rule_id": "BOOK-GM-GUIDE:1.1:p97:footpad:athletics",
    "skill": "athletics",
    "test_profile": {"dice": 3, "threshold": 3, "pool_cap": null}
  }
}
```

Это фрагмент definition; остальные поля обязательны. Для authored numeric NPC допустимы также `skill: "defence"` и другие явные числа. Пропущенный Skill, alias и неподдержанный навык отклоняются. Все24старые пары примеров дополнены `defence`, сохранив прежние значения/результаты. Новых wire version/метрик нет.

Каталожные root/attack/protection identities зарезервированы: подменённые числа/Skill или переименование лишь root IDs не позволяют сохранить ложную книжную подпись. Canonical comparison использует независимый свежий образец. Прочие caller-authored numeric NPC остаются допустимыми и не объявляются проверенными книжными профилями.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m21/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m21/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [actual CLI result](pc-melee-simulation.result.json): два авторских PC со Staff против двух Footpads и одного Townsfolk. Optional Fate declined, backup null; фиксированы порядок/приоритеты и aware Close-сцена. Seed42,6trials,budget5rounds:6objective wins,30actions,12started/6completed rounds; PC losses/unsupported/Fate/Help/ally Recover costs равны0.

[Balance request](pc-melee-balance.request.json) и [actual CLI result](pc-melee-balance.result.json) фиксируют party и меняют1–2Footpads/0–1Townsfolk, по3trials:

| Footpads | Townsfolk | Objective | Other outcomes | Actions |
|---|---|---|---|---|
| 1 | 0 | 3 | 0 | 4 |
| 1 | 1 | 3 | 0 | 8 |
| 2 | 0 | 3 | 0 | 8 |
| 2 | 1 | 3 | 0 | 16 |

Полный book source/Skill сохраняется у каждого кандидата; ranking по objective rate и разрешение равенства остаются прежними. Это лёгкие демонстрационные составы, а не оценка истинной вероятности или найденный оптимум. Другие NPC, применимые Abilities, ambush/pickpocket/spatial и новые loadouts сюда не включены.
