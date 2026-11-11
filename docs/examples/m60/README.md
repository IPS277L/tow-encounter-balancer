# M60: Pistol → melee backup при недоступном Reload

PC продолжает Shoot/Reload, пока две руки пригодны. Если Pistol пуст и осталась одна пригодная рука, на своём следующем незанятом ходу он оставляет Pistol и достаёт запасное оружие. Заряженный one-hand shot сохраняет приоритет. [Правило](../../rules/equipment.md#pc-pistol-backup-m60), [контракт](../../decisions/ADR-0102-pc-pistol-melee-backup.md).

Существующее поле current PC JSON1:

```json
"backup_weapon_policy": {
  "weapon": "sword",
  "preferred_hand": "left"
}
```

Доступны Dagger, Staff, Axe, Sword, Warhammer и Morning Star; Strength≥2, optional shield, без второго firearm/обратного переключения. Null сохраняет прежний stop. Книга разрешает carried weapons/draw, момент перехода — выбранная тактика сценария. Two_available_hands Reload остаётся ранее согласованной GM policy.

После draw действуют Melee/WS/Strength и Traits backup; Close Shooting Protection override больше не применяется. Pistol instance/loaded/progress/cycle сохраняются без refill. Пустой dropped Pistol не подбирается; последующий Recover возвращает actual backup. Shield освобождает необходимую руку раньше draw. Incidental draw не занимает action/Test, но сохраняет Critical; обычный необходимый Recover предшествует Attack.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m60/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m60/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json) развивают M58: Pistol+Shield с carried Sword и Staff+Shield против Skulker/Brewguard/Miner/Bestigor, authored armour_bonus1 у обоих PC. Seed42,6trials,8rounds:0objective/5party defeated/1limit/0unsupported,157actions,39started/34completed rounds; во всех6trials побеждён хотя бы один PC.

Native trial2 действительно переходит на Sword в раунде4 после раны18, затем выполняет две Melee Attack, сохраняя Pistol state. Итог этого trial — party_defeated,34actions. В прежнем M58 он останавливался перед Reload: продолжение не гарантирует победу и не отменяет полученную рану. Новый process representative сравнивает native/sequential/spawn records на этом реальном переходе.

[Balance request](pc-melee-balance.request.json) и [CLI result](pc-melee-balance.result.json): фиксированные Skulker/Miner и по0–1Brewguard/Bestigor;4состава по2trials. Equipment/source policy сохраняются в полном root/candidate echo.

| Brewguard | Bestigor | Objective | Party defeated | Limit | Unsupported | Actions |
|---|---|---|---|---|---|---|
| 0 | 0 | 2 | 0 | 0 | 0 | 7 |
| 0 | 1 | 1 | 1 | 0 | 0 | 36 |
| 1 | 0 | 2 | 0 | 0 | 0 | 38 |
| 1 | 1 | 0 | 2 | 0 | 0 | 44 |

Малая выборка демонстрирует интерфейс и тактику, а не истинные вероятности или оптимальный состав. Unsupported остаётся в знаменателе. Новых JSON-полей/версии/метрик нет;204прежнихJSON и57selected NPC loadouts сохранены. Общий inventory, собственный ranged Help и восстановление утраченных рук не добавлены.
