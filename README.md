# TOWR Encounter Balancer

Симулятор боёв и подбор сложности столкновений для TOWR. Нормативные источники: Player’s Guide1.4 и Gamemaster’s Guide1.1; упрощённый прототип не имеет приоритета над книгами.

Действующий генератор создаёт новые составы NPC из компонентов и проверяет их симуляциями Monte Carlo. Игровое ядро поддерживает раны (Wounds), судьбу (Fate), восстановление (Recover), помощь (Help), часть талантов (Talents) и магии (Magic). Подключена вся область двуручного оружия для игроков и динамических NPC: переменный хват, реальные дистанции/движение, натиск (Charge), повторная стрельба, сети (Weighted Net) и обученная лошадь (Horse). Подключена общая область брони (Armour), включая пять магических видов защиты (Magic Armour), конскую броню (Barding) и применимые зависимости маунтов (Mounts). Каталог книжных NPC остаётся отдельным набором пресетов. Фактическая готовность, проверки и ограничения — в [статусе](docs/project-status.md).

## Цель продукта и текущий приоритет

Генератор должен сам создавать противников из характеристик, навыков, реализованных талантов/способностей и снаряжения, симулировать составы методом Monte Carlo и возвращать несколько вариантов под заданную сложность и длительность. Пользователь задаёт партию и ограничения поиска, а не готовый NPC на каждую комбинацию параметров.

Динамический Python/JSON/CLI-путь уже создаёт новые Minions из характеристик/навыков, одноручного и двуручного melee/ranged оружия и сети (Weighted Net), обычной брони (Armour), щитов (Shields), явно разрешённых магических средств защиты (Magic Armour) и on-hit компонентов, адаптивно ищет составы и отдельно проверяет финалистов Monte Carlo. [Запуск и текущие ограничения](docs/examples/dynamic/README.md). Книжные statblocks остаются пресетами и проверочными примерами. NPC автоматически выбирают Защиту (Defence) или Атлетику (Athletics); свойства оружия исполняются по выбранным компонентам. [Пример снаряжения](docs/examples/dynamic/equipment.request.json). Стрелковые компоненты включают настоящие Shooting/Reload и автоматический выбор режима; [смешанный пул](docs/examples/dynamic/ranged.request.json). Вход партии разделяет характеристики/навыки/equipment/Lucky/Fate; диапазоны NPC строятся автоматически, ручные ограничения необязательны. PC автоматически выбирают Attack/цель, стандартный Recover и Help в ограниченном melee-пути. В этом пути исполняются Healing Potion и Enhancement Potion для WS/S/T/Ag с автоматическим применением и конечным запасом. Подключена первая магия PC: Lightning Blast и Fire Breath школы Elementalism с настоящими Casting и боевыми Miscasts; [пример и ограничения](docs/examples/dynamic/README.md#магия-персонажей). Генератор выбирает допустимые поднаборы одиннадцати книжных талантов (Talents): Сопротивление магии (Magic Resistance), Оборонительная стойка (Defensive Stance), Дикая атака (Wild Attack), Могучий удар (Mighty Blow), Быстрая перезарядка (Rapid Reload), Пробой брони (Armour Bane), Братья по оружию (Allies in Arms), Оглушающий удар (Bash Attack), Акробат (Acrobatic), Снова в седле (Back in the Saddle) и Боевой музыкант (Battlefield Musician), с проверкой требований. [Пример талантов NPC](docs/examples/dynamic/talents.request.json). Дополнительно общие Связанный честью (Honour Bound) и Благословения Леди (Blessings of the Lady) требуют явного контекста GM; генератор выбирает разрешённый полный источник обета. [Пример обетов](docs/examples/dynamic/oaths.request.json). Для PC дополнительно подключены Крепкий (Hardy), Удачливый (Lucky) и Волшебник (Wizard); автоматические действия сохраняют явный источник приобретения Talent; [пример PC](docs/examples/dynamic/pc-talents.request.json). Полные таланты (Talents), магия (Magic) и общее оптимальное планирование боя ещё не реализованы; ближайшая очередь закреплена в статусе. [Следующая функция](docs/roadmap.md#после-m70), [статус](docs/project-status.md).

## Начало работы

Текущий приоритет — расширить боевые возможности динамического генератора: снаряжение (Equipment), таланты (Talents), магию (Magic) и необходимые для них действия/сцену. Дальнейшая настройка качества поиска отложена. [Матрица существующего исполнения](docs/implementation-coverage.md), [очередь и ближайший блок](docs/roadmap.md#очередь-расширения-боевых-возможностей).

Динамический поиск учитывает обе цели с допусками±10процентных пунктов по победам и±1раунд (Round) по средней длительности. Результат различает совпадение оценок с обеими целями и ближайший найденный вариант вне допусков. [Статусы и ограничения](docs/examples/dynamic/README.md#совместные-цели-и-статус-результата).

Игроки и генерируемые NPC используют несколько удерживаемых и переносимых предметов одноручного и двуручного оружия, Щит (Shield) в допустимых сочетаниях и отдельный начальный заряд каждого оружия с Перезарядкой (Reload). Навыки и подготовка определяются всем инвентарём, включая убранное оружие. Генератор сам выбирает число и виды предметов NPC; готовые loadouts не нужны. Автоматическая тактика выбирает реальные движение, атаку, перезарядку, помощь (Help) и смену оружия, сохраняя ресурсы и руки. [Сцена и снаряжение](docs/examples/dynamic/README.md#сцена-двуручное-оружие-и-сети), [малый пример смешанного инвентаря](docs/examples/dynamic/inventory.request.json), [пример сетей](docs/examples/dynamic/weighted-net.request.json).

Полный боевой каталог оружия (Weapons):49физических видов и безоружный бой (Unarmed), общий инвентарь PC/NPC, конечные заряды и настоящие действия магического оружия (Magic Weapons). Магические предметы и Огромный пистолет (Ogre Pistol) включаются в генерацию явно. [Малый пример](docs/examples/dynamic/magic-weapons.request.json), [условия и границы](docs/examples/dynamic/README.md#магическое-оружие-и-факты-сцены).

Броня (Armour) задаётся настоящими предметами: преимущества, штрафы, руки/потеря/подбор и независимые причины состояний исполняются для партии и генерируемых NPC. Магические виды защиты (Magic Armour) требуют явного допуска в поиске. [Малый пример](docs/examples/dynamic/armour.request.json), [снаряжение и условия воздушной сцены](docs/examples/dynamic/README.md#броня-и-защитное-снаряжение).

Для новой сессии: [AGENTS.md](AGENTS.md), этот README, [статус](docs/project-status.md) и [индекс вопросов](docs/open-questions.md). Далее читать материалы своей задачи по [карте документации](docs/README.md). Хронология находится в [архиве](docs/archive/README.md).

Python3.12+; первая установка окружения:

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -e .
```

## Запуск

Минимальный UI: запустите сервер и откройте `http://127.0.0.1:8765/` в браузере. Запрос и результат переключаются между карточками и JSON. Карточки запроса редактируются; правки помечают результат как устаревший, пересчёт запускается кнопкой, выполняющуюся генерацию можно отменить. Seed меняется только вручную. Есть загрузка/скачивание файлов. [Подробности](docs/examples/dynamic/README.md#локальный-ui).

Новый запрос UI автоматически использует до четырёх процессов для независимых симуляций; автоплан учитывает ускорение. Загруженный JSON сохраняет явно выбранный режим исполнения. [Настройка process/sequential](docs/examples/dynamic/README.md#параллельное-исполнение).

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr ui
```

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr generate-encounter docs/examples/dynamic/search.request.json
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m23/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m23/pc-melee-balance.request.json
```

После установки доступны `towr generate-encounter INPUT` (динамическая генерация), `towr simulate-pc-melee INPUT` и `towr balance-pc-melee INPUT`; `-` читает stdin. Seed, trials, round budget и execution задаются во входе. PC family (включая первый магический путь) и Dynamic используют собственный текущий JSON1; отдельная NPC Magic family — JSON6. Все семейства перечислены ниже.

| Сценарий | Примеры и команды |
|---|---|
| Ranged | [Simulation](docs/examples/m4/README.md), [balance](docs/examples/m5/README.md) |
| Melee | [Simulation и balance](docs/examples/m6/README.md) |
| Mixed | [Simulation и balance](docs/examples/m7/README.md) |
| Magic | [Python API](docs/examples/m8/README.md), [JSON/CLI](docs/examples/m8/json/README.md) |
| Группа PC против Minions/Brutes | [M70 Hochland/Aim/Fate](docs/examples/m70/README.md); [M69 Blunderbuss](docs/examples/m69/README.md); [M68 Sling](docs/examples/m68/README.md); [M67 Handguns](docs/examples/m67/README.md); [M66 Crossbows](docs/examples/m66/README.md); [M65 bows + Short opening](docs/examples/m65/README.md); [PC Repeaters M64](docs/examples/m64/README.md); [PC Protection choice + Melee Help M63](docs/examples/m63/README.md); [NPC Help к Shooting M62](docs/examples/m62/README.md); [NPC Pistol + Reload M61](docs/examples/m61/README.md); [Pistol → melee backup M60](docs/examples/m60/README.md); [Pistol против Thief Stealth M59](docs/examples/m59/README.md); [Skulker/Dwarfs/Bestigor против Pistol M58](docs/examples/m58/README.md); [Orc Boy/Big ’Un против Pistol M57](docs/examples/m57/README.md); [NPC Melee/Athletics против Pistol M56](docs/examples/m56/README.md); [Pistol со щитом M55](docs/examples/m55/README.md); [Pistol + Reload M54](docs/examples/m54/README.md); [PC со щитом M53](docs/examples/m53/README.md); [Net + carried Spear M52](docs/examples/m52/README.md); [Great Stag/Crown/Trample M51](docs/examples/m51/README.md); [Bear/Crushing Weight M50](docs/examples/m50/README.md); [Ogre/наземный Pegasus M49](docs/examples/m49/README.md); [Skin Wolf/Warped Form M48](docs/examples/m48/README.md); [Flagellant/Feel No Pain/Recover M47](docs/examples/m47/README.md); [Bestigor/Blood Rage/Glorious M46](docs/examples/m46/README.md); [Чанк Sharpshooter/Gor/Orc Spears M45](docs/examples/m45/README.md); [Halfling Thief/Stealth M44](docs/examples/m44/README.md); [Miner/grudge M43](docs/examples/m43/README.md); [Brewguard/Distracted M42](docs/examples/m42/README.md); [Gor/Knight со щитами M41](docs/examples/m41/README.md); [Demigryph/Centigor/White Wolf Claws M40](docs/examples/m40/README.md); [Bear/вторая Attack M39](docs/examples/m39/README.md); [Minotaur Greataxe/cap8 M38](docs/examples/m38/README.md); [Razorgor/Minotaur M37](docs/examples/m37/README.md); [Spear loadouts M36](docs/examples/m36/README.md); [Cultist/Elf Militia/Ungor M35](docs/examples/m35/README.md); [Horde/Power Help M34](docs/examples/m34/README.md); [NPC Help M33](docs/examples/m33/README.md); [Empire Peasant/Watch/Militia M32](docs/examples/m32/README.md); [Гоблины M31](docs/examples/m31/README.md); [Три Brutes M30](docs/examples/m30/README.md); [Official/Broken, simulation и подбор](docs/examples/m23/README.md); [Brigand/Craven](docs/examples/m22/README.md), [Footpad/Townsfolk](docs/examples/m21/README.md), [запасное оружие](docs/examples/m20/README.md), [двуручное оружие](docs/examples/m19/README.md), [одноручное оружие](docs/examples/m18/README.md), [Ally Recover](docs/examples/m17/README.md), [Protection Help](docs/examples/m16/README.md), [Melee Help](docs/examples/m15/README.md), [Glorious/Near Miss](docs/examples/m14/README.md), [тяжёлые раны](docs/examples/m12/README.md), [состав NPC](docs/examples/m11/README.md), [Minion-группа](docs/examples/m10/README.md), [одиночный пример](docs/examples/m9/README.md) |

## Проверка изменений

Запускать тесты изменённого поведения и зависимых компонентов. Пример:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.unit.test_k1_opposed_test -v
```

Полная регрессия и проверка установленного wheel нужны по основаниям из [политики проверок](AGENTS.md#политика-проверок). [Архитектура](docs/architecture/overview.md), [план](docs/roadmap.md) и [тестирование](docs/testing.md) описывают актуальную работу. Commit и push выполняет пользователь.

Боевой музыкант (Battlefield Musician) подключён для PC и динамических NPC: физический инструмент, Знание музыки (Music Lore), настоящая проверка Лидерства (Leadership), вдохновение и защитные равенства. [Малый запрос и условия слышимости](docs/examples/dynamic/README.md#боевой-музыкант-battlefield-musician).
