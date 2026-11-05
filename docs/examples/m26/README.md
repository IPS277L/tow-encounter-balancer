# M26: чанк Artisan, Bretonnian Squire и Elf Merchant

Три fixed Close loadouts добавлены и проверены одной функцией. [Правило, источники и границы](../../rules/npc-profile-catalog.md#catalog-chunk-m26).

| Фабричный Profile ID | Атака | Protection | Профиль |
|---|---|---|---|
| ARTISAN | Make-Shift Weapons2d/2 Damage2,1H | Athletics3d/2 | Minion,Resilience3 |
| BRETONNIAN_SQUIRE_SWORD | Sword3d/3 Damage3,1H | Athletics3d/4 | Minion,Resilience3 |
| ELF_MERCHANT_JEWELLED_BLADE | Jewelled Blade4d/3 Damage3,1H | Athletics4d/3 | Brute2,Resilience4 armoured |

```python
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc

artisan = create_pc_book_npc(PcBookNpcProfile.ARTISAN, "artisan1")
squire = create_pc_book_npc(PcBookNpcProfile.BRETONNIAN_SQUIRE_SWORD, "squire1")
merchant = create_pc_book_npc(PcBookNpcProfile.ELF_MERCHANT_JEWELLED_BLADE, "merchant1")
```

Artisan: GM96, Professional Pride относится к покупке trapping непосредственно у изготовителя и следующему Test с ним. Текущие no_external_effects исключают и ожидающий применения бонус от покупки **до боя**. Squire: GM109, Longbow явно unselected; Noble Service даёт +2d Help обслуживаемому Knight, а нынешняя NPC-стратегия Help не выполняет. Merchant: GM107, Hard Bargain даёт -1d торговым Tests, которых в этой сцене нет. Эти условия/эффекты сохранены в metadata; NPC не получают PC Sword Traits.

Первая рана Merchant накладывает один Staggered на обязательном profile ACK. Если он уже Staggered, сама рана сначала снимает прежний Staggered, затем накладывается новый; немедленной второй раны нет. Следующий отдельный повторный Staggered при нынешнем выборе SUFFER_WOUND может дать W2 defeat. Merchant продолжает свой обычный ход, без Broken stop. NPC Recover и снятие profile Condition при сохраняющемся W1 не входят в чанк.

Current JSON1, схемы, команды и метрики не менялись. Requests по-прежнему содержат полные numeric definitions; подмена Damage/Protection/книжных root или nested sources не проходит canonical admission. Все34прежние request/result pairs M9–M25 неизменны.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m26/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m26/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [actual CLI result](pc-melee-simulation.result.json): два PC со Staff против Merchant, Artisan и Squire, seed42,6trials,budget5rounds. Optional Fate declined, backup/exit policy null. Получены6objective, без party defeat/limit/unsupported/PC deaths;72actions,21started/15completed rounds. Все optional/support/exit counters нулевые.

[Balance request](pc-melee-balance.request.json) и [actual CLI result](pc-melee-balance.result.json):1–2Merchants,0–1Artisan,0–1Squire, fixed party/loadouts/policies, по3trials на8составов:

| Merchants | Artisan | Squire | Objective | Round limit | Actions |
|---|---|---|---|---|---|
| 1 | 0 | 0 | 3 | 0 | 13 |
| 1 | 0 | 1 | 3 | 0 | 29 |
| 1 | 1 | 0 | 3 | 0 | 26 |
| 1 | 1 | 1 | 3 | 0 | 37 |
| 2 | 0 | 0 | 2 | 1 | 44 |
| 2 | 0 | 1 | 2 | 1 | 43 |
| 2 | 1 | 0 | 2 | 1 | 50 |
| 2 | 1 | 1 | 1 | 2 | 68 |

Party defeat/unsupported нулевые во всех составах. При top_k2 выбраны2Merchants без остальных NPC и2Merchants+1Squire. ROUND_LIMIT остаётся в знаменателе; это не победа NPC и не фильтр неудачных trials. Малая воспроизводимая выборка не задаёт истинную вероятность или оптимальную сложность. Подбор сохраняет полные projected sources и агрегаты без native journals.
