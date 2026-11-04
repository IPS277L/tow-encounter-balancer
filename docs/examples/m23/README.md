# M23: Empire Official, первая рана и Broken

Первый книжный Brute в PC-каталоге — Empire Official с Dagger. [Правило и таблица](../../rules/npc-profile-catalog.md#official-broken-m23), [контракт ADR-0078](../../decisions/ADR-0078-pc-official-first-wound-broken-boundary.md).

```python
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile, create_pc_book_npc, get_pc_book_npc_entry,
)

official = create_pc_book_npc(PcBookNpcProfile.EMPIRE_OFFICIAL_DAGGER, "official1")
entry = get_pc_book_npc_entry(PcBookNpcProfile.EMPIRE_OFFICIAL_DAGGER)
```

GM1.1 стр.98: Brute2, Toughness3/Resilience3, Dagger Close2d/3 Damage2,1H; Athletics3d/3. Pistol явно unselected. Metadata wound_bands сохраняет0No effect/1Broken/2Defeated. Heard It All Before сохраняет Grim для Persuade/Distract без bribe; нынешняя family этих действий не исполняет.

Первая рана увеличивает профильный счётчик и получает полный ACK с Broken, без PC Wounds Table. Broken не мешает Official защищаться обычной Athletics; следующие PC ещё могут нанести вторую рану и победить. Если живой Broken Official становится следующим actor, симуляция останавливается **до его TurnStart**: обязательное бегство требует пока отсутствующих маршрута/безопасной Zone. Предыдущие PC Critical/end phases и другие ходы завершаются.

Native `PcNpcBrokenTurnUnsupported` содержит actor, реальную причинившую рану Attack execution ID и exact Brute0→1 change. Он не использует фиктивный PC table_total. Вторая рана до окна даёт обычный defeat; stop не считается ни flee, ни defeat. Снятие Broken/Willpower recovery и дальнейшее перемещение не выбраны.

Текущие JSON1/команды/метрики прежние. Полные definition/limit/Skill уже выражают Brute, нового поля или миграции28старых пар нет. При Unsupported статистика отражает исполненный prefix; trials остаются в знаменателе, соответствующий candidate не выбирается.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m23/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m23/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [actual CLI result](pc-melee-simulation.result.json): два авторских PC со Staff против одного Official Dagger и одного Footpad. Aware Close-сцена, optional Fate declined/backup null, seed42,6trials,budget5rounds. Получены3objective wins и3unsupported, без party defeat/limit/PC losses;19actions,9started/3completed rounds, все optional/support costs0. Проверка тех же native seeds подтвердила причину всех трёх остановок: `npc_broken_turn`.

[Balance request](pc-melee-balance.request.json) и [actual CLI result](pc-melee-balance.result.json): fixed party,1–2Officials/0–1Footpad, по3trials:

| Officials | Footpads | Objective | Unsupported | Other outcomes | Actions |
|---|---|---|---|---|---|
| 1 | 0 | 1 | 2 | 0 | 6 |
| 1 | 1 | 1 | 2 | 0 | 9 |
| 2 | 0 | 1 | 2 | 0 | 9 |
| 2 | 1 | 1 | 2 | 0 | 12 |

Selected candidates пусты: каждый наблюдавшийся состав имеет неподдержанный путь. Такие trials не фильтруются ради ложной оценки сложности. Это граница первого среза, не свидетельство проигрыша игроков и не истинная вероятность боя. Catalog definitions/party/Fate/policies сохраняются у каждого кандидата, journal в balance не хранится.
