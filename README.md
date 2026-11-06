# TOWR Encounter Balancer

Симулятор боёв и подбор сложности столкновений для TOWR. Нормативные источники: Player’s Guide1.4 и Gamemaster’s Guide1.1; упрощённый прототип не имеет приоритета над книгами.

Реализованы ограниченные ranged/melee/mixed Minion-сценарии и M8 с одним Champion-Wizard, Curse of Cowardly Flight и явно разрешёнными продолжениями. PC melee поддерживает немагическую группу против Minions и обычных числовых Brutes, включая тяжёлые PC Wounds11–23, Critical/Defenceless turns, Help атаке/защите и Recover союзнику, явные Glorious/Near Miss policies и статистику действий/потерь/расхода ресурса. Оружие PC: шесть одноручных и семь двуручных Close-профилей; явная backup policy позволяет перейти на запасное1H в свой ход, иначе недоступный2H хват даёт unsupported. Книжный PC каталог содержит51fixed combat loadouts, включая гоблинов с Dirty Coward/Backstabba, shield snapshots, Brutes с профильными Conditions и естественные атаки существ. Есть явный NPC Help Peasant/Militia/Cultist/Goblin/Night Goblin с бонусным кубом и Orc Boy/Big ’Un с free success без Test, отдельные NPC costs, независимые sequential/process прогоны, агрегаты и подбор составов. Точные границы и текущая приёмка — в [статусе](docs/project-status.md).

## Начало работы

Для новой сессии: [AGENTS.md](AGENTS.md), этот README, [статус](docs/project-status.md) и [индекс вопросов](docs/open-questions.md). Далее читать материалы своей задачи по [карте документации](docs/README.md). Хронология находится в [архиве](docs/archive/README.md).

Python3.12+; первая установка окружения:

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -e .
```

## Запуск

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m23/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m23/pc-melee-balance.request.json
```

После установки доступны `towr simulate-pc-melee INPUT` и `towr balance-pc-melee INPUT`; `-` читает stdin. Seed, trials, round budget и execution задаются во входе. PC melee и другие немагические families используют собственный текущий JSON1; Magic — JSON6. Все семейства перечислены ниже.

| Сценарий | Примеры и команды |
|---|---|
| Ranged | [Simulation](docs/examples/m4/README.md), [balance](docs/examples/m5/README.md) |
| Melee | [Simulation и balance](docs/examples/m6/README.md) |
| Mixed | [Simulation и balance](docs/examples/m7/README.md) |
| Magic | [Python API](docs/examples/m8/README.md), [JSON/CLI](docs/examples/m8/json/README.md) |
| Группа PC против Minions/Brutes | [Flagellant/Feel No Pain/Recover M47](docs/examples/m47/README.md); [Bestigor/Blood Rage/Glorious M46](docs/examples/m46/README.md); [Чанк Sharpshooter/Gor/Orc Spears M45](docs/examples/m45/README.md); [Halfling Thief/Stealth M44](docs/examples/m44/README.md); [Miner/grudge M43](docs/examples/m43/README.md); [Brewguard/Distracted M42](docs/examples/m42/README.md); [Gor/Knight со щитами M41](docs/examples/m41/README.md); [Demigryph/Centigor/White Wolf Claws M40](docs/examples/m40/README.md); [Bear/вторая Attack M39](docs/examples/m39/README.md); [Minotaur Greataxe/cap8 M38](docs/examples/m38/README.md); [Razorgor/Minotaur M37](docs/examples/m37/README.md); [Spear loadouts M36](docs/examples/m36/README.md); [Cultist/Elf Militia/Ungor M35](docs/examples/m35/README.md); [Horde/Power Help M34](docs/examples/m34/README.md); [NPC Help M33](docs/examples/m33/README.md); [Empire Peasant/Watch/Militia M32](docs/examples/m32/README.md); [Гоблины M31](docs/examples/m31/README.md); [Три Brutes M30](docs/examples/m30/README.md); [Official/Broken, simulation и подбор](docs/examples/m23/README.md); [Brigand/Craven](docs/examples/m22/README.md), [Footpad/Townsfolk](docs/examples/m21/README.md), [запасное оружие](docs/examples/m20/README.md), [двуручное оружие](docs/examples/m19/README.md), [одноручное оружие](docs/examples/m18/README.md), [Ally Recover](docs/examples/m17/README.md), [Protection Help](docs/examples/m16/README.md), [Melee Help](docs/examples/m15/README.md), [Glorious/Near Miss](docs/examples/m14/README.md), [тяжёлые раны](docs/examples/m12/README.md), [состав NPC](docs/examples/m11/README.md), [Minion-группа](docs/examples/m10/README.md), [одиночный пример](docs/examples/m9/README.md) |

## Проверка изменений

Запускать тесты изменённого поведения и зависимых компонентов. Пример:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.unit.test_k1_opposed_test -v
```

Полная регрессия и проверка установленного wheel нужны по основаниям из [политики проверок](AGENTS.md#политика-проверок). [Архитектура](docs/architecture/overview.md), [план](docs/roadmap.md) и [тестирование](docs/testing.md) описывают актуальную работу. Commit и push выполняет пользователь.
