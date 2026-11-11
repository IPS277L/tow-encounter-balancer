# ADR-0099: первый PC Pistol и настоящий Exacting Reload

Дата: 2026-11-07. Статус: **принят пользователем и реализован в M54**. Выбраны Pistol без shield/backup и явная policy two_available_hands для Reload.

Дополнение M60: [ADR-0102](ADR-0102-pc-pistol-melee-backup.md) разрешает carried1H backup у Pistol с optional shield при empty/недоступном Reload. Первоначальные ограничения ниже сохраняют историю этой вехи; актуальная общая граница — в [правиле M60](../rules/equipment.md#pc-pistol-backup-m60).

## Источники и установленные факты

Адресно сверены BOOK-PLAYER-GUIDE1.4: гл.III Skills68–70, Rapid Reload79, Lores/Specialist Skills82; гл.IV Weapons92/94–95, Tools and Kits98–99; гл.V Exacting110, Actions116–118, Failed Attacks119 и Conditions123; Wounds Table190–191. Повторное чтение неизменённых частей дополнено независимой read-only сверкой. Лор о ношении нескольких пистолетов не создаёт второй предмет во входе. Новых книг/редакций/полного перечитывания нет.

- Pistol:1H, Damage5, ignores armour, Optimum Close–Short; Max Long. В current Close-сцене он допустим даже при близком враге (PG94–95).
- Shooting использует **Ballistic Skill**, Dexterity — **Initiative**, не Agility (PG68–70).
- Reload — Exacting Dexterity: каждая Test стоит action, накопить3successes; провал не уменьшает прошлый progress (PG94–95/110). Завершивший Reload action не становится бесплатным выстрелом. Rapid Reload79 — отдельный невыбранный Talent.
- Blackpowder Lore обязателен для firearm use и Dexterity Reload (PG82/95). Blackpowder Kit99 предназначен для перезарядки; без инструмента возможна только отдельно разрешённая GM импровизация с penalty по PG98. В первом срезе kit полный и подтверждён.
- Ammunition считается достаточной после подходящего снабжения либо явного stock-up (PG94). Это precondition сцены, не бесконечный kit без источника и не новый finite ammo simulator.
- Выстрел в Close остаётся Shooting, без Melee/Brawn outnumbering/higher-ground. Против Prone действует Shooting penalty; Close miss накладывает Staggered только при его отсутствии (PG94/118–119/123).
- Target может выбрать Melee opposition против Close shot. Это разрешённый выбор, не обязательная смена с текущего законного Protection. Defence против Shooting требует shield; без него обычный выбор Athletics (PG68/94/118).

## Решение 1: законченная граница первого среза

**Принято:** один initially loaded Pistol, без shield, melee backup и второй firearm у этого PC. Смешанная party с прежними melee/shield PCs допустима. Pistol-PC сохраняет ordinary self Recover и разрешённые последствия ран, затем Shoot, если loaded, иначе Reload до готовности. Aim/Manoeuvre/новый ranged Help/свободная смена оружия/Rapid Reload не добавляются.

Допускаются NPC с уже готовой **законной выбранной Protection против Shooting**: Athletics либо Defence при настоящем holds_shield. Прочие definitions отклоняются полным source preflight до RNG, если в party есть Pistol-PC. Нельзя молча оставить Defence без shield, вывести отсутствующую Athletics из имени карточки или расширить Thief Stealth permission без её ranged разбора. Каталог57NPC не переписывается; существующие melee-сцены остаются допустимыми.

Для нового входа NPC продолжают выбирать готовый lawful Protection, а не автоматически лучший Melee opposition. Это fixed NPC тактика. Противник с неготовой защитой не становится trial UNSUPPORTED_PATH: такой source пока вне M54 и отвергается раньше. При подборе полный template тоже должен быть допустим, без частичной маскировки неподдержанного профиля нулевым count.

**Большая альтернатива:** сразу поддержать Pistol+Shield того же PC. При выборе two_available_hands empty Pistol требует own-turn release shield ради Reload; reload progress имеет приоритет перед восстановлением shield, иначе возникает бессмысленный Recover/release цикл. После завершения Reload shield восстанавливается отдельным standard Recover до следующего shot по M53 policy, если руки доступны. При weapon_hand_only сам Reload не требует освобождать shield-руку. Нужны дополнительные state/proofs/priority и literal Wound tests. Новый NPC Protection каталог в эту альтернативу сам по себе не входит. Пока этот больший вариант не выбран.

## Conditional PC source и формат

В текущий PC weapon enum добавлен `pistol`, без фиктивного Sword в руках стрелка. Нынешние WS/Defence/Melee и прочие authored abilities сохраняются; дополнительные firearm abilities передаются явно только этому definition:

```json
"weapon": "pistol",
"pistol": {
  "ballistic_skill": 3,
  "shooting": 4,
  "initiative": 3,
  "dexterity": 4,
  "has_blackpowder_lore": true,
  "has_blackpowder_kit": true,
  "ammunition_supply_confirmed": true,
  "initially_loaded": true,
  "reload_hand_policy": "two_available_hands"
}
```

Это фрагмент `party[].pc`, closed object с required полями, exact scalars/enums и обычной TestProfile валидацией BS/Shooting и I/Dexterity. Для pistol требуется объект целиком, остальным weapons он запрещён. Нет значений по умолчанию, вычисления BS изWS, I изAgility или Dexterity из другого Skill. Числа выше — пример authored PC, не universal default. Боевые Damage5/1H/ignores-armour/reload3 берутся из существующего полного K1 Pistol catalog по PG95, а не из произвольных wire чисел.

Bool Lore/kit/supplies/loaded в первом fresh scope должны быть true; missing/false не подменяются штрафом или бесплатной дозарядкой. Прежние180JSON M9–M53 не мигрируются. Используется current PC JSON1/CLI; новое правило не создаёт wire version или новую family. No-pistol inputs сохраняют прежний source/echo и результаты.

Начальное held weapon — именно Pistol, hand LEFT/RIGHT. В принятой границе shield/backup/help/ally-recover policy самого стрелка отсутствуют, ordinary Attack/Recover роль сохраняется; melee PCs остаются на своих прежних policies. Melee Help не прикладывается к Shooting: при неподходящем recipient helper использует прежний Attack fallback. Protection Help к стрелку связывается с actual Defence/Athletics входящей атаки; нового Shooting/Dexterity Help пока нет.

## Решение 2: сколько рук требуется Reload

PG94 задаёт Pistol1H, но **не задаёт число рук перезарядки**. Поиск reload/hands по локальному тексту не дал отдельного обязательного правила. Поэтому следующий выбор — явная GM/scenario конкретизация, а не цитата RAW.

**Принята two_available_hands:** одна пригодная рука держит Pistol, другая доступна и свободна для kit/заряжания. Недоступная16/потерянная20/clutch18 рука не считается свободной. Травмированная12 ещё может использоваться, но реальный Reload с ней вызывает Critical; не заменять это запретом/лечением. Эта policy передаётся во входе явно.

**Альтернатива weapon_hand_only:** считать достаточным held Pistol в одной пригодной руке и разрешать Dexterity Reload без отдельной второй руки. Это другая согласуемая конкретизация абстрактного Reload; её нельзя незаметно включить по отсутствию второго hand fact.

При two_available_hands отсутствие второй руки не запрещает существующий loaded shot. Сначала завершаются реальные Wound/Near Miss/body/expiry, затем own-turn regrip/pickup; loaded Pistol может выстрелить одной оставшейся рукой. Только когда **действительно выбран Reload**, недоступная вторая рука даёт точный UNSUPPORTED_PATH перед RNG/новым действием. Не останавливать trial сразу при любой16/18, если ещё можно сделать loaded shot. Terminal objective после последнего выстрела не требует бессмысленного Reload. Если нельзя выполнить сам pickup/grip/shot, стоп привязан к этой фактической границе и её причине.

Unavailable-hand stop — граница данной simulation policy, не смерть/поражение и не утверждение, что книга запрещает Reload одной рукой. Ограничения сохраняют источники раны/оружия/цикла и подтверждённые costs/losses; дополнительный Test не бросается. Missing Lore/kit в исходном fresh source — invalid input, а не это runtime событие.

## Руки, Protection и Wounds

Loaded state/Exacting progress принадлежат отдельному weapon instance, не definition ID или hand marker. HIT и MISS разряжают ровно один loaded экземпляр, начинают новый reload cycle; rejected preparation его не расходует. Drop4/8/12, regrip и standard Recover не сбрасывают progress/loaded и не создают запасной Pistol.

PC держит реальный1H weapon: против входящего Melee допускается его Defence по общей weapon eligibility, без Sword Trait. Против Net без shield — Athletics; против Brawn — Endurance. Ни loaded flag, ни firearm Lore не дают дополнительного Defence bonus. Defenceless не действует/не Opposes.

При ранении12 использование фактической руки/обеих рук Reload даёт Critical.16/18/20 сохраняют недоступность и существующие Defenceless/Critical.14 вызывает Critical от Shoot/Reload и реального incidental swap;15 сохраняет исключения для падения/drop/clutch-face, но Shoot/Reload/Recover вызывает Critical. Near Miss обрабатывается раньше отменённых body facts. Никакого Wound treatment ради продолжения.

Shooting/Dexterity используют actual Wound/Condition modifiers: Drained, Blinded, consumed Crushed Rib next-Test и точный Fate prefix. Против Prone NPC Shooting получает–1d, не Melee+1d. Ignores-armour использует текущую NPC Toughness, не поддельно изменённый immutable profile. В full source должны сохраняться actual Shooting skill, Pistol profile/weapon instance/cycle, Defence choice и Damage rule trace.

## Исполнение и Fate

Переиспользованы готовые ranged catalog/preparation/weapon transition и Reload Exacting primitives. В существующем clock Reload — **Improvise / Skill** с weapon-bound reload approach, а не новый Recover mode или дополнительный выстрел. Один Reload action — одна Dexterity Test и один action receipt; нулевой progress/overshoot/complete state сохраняются.

PC owner добавляет source-bound shoot/weapon-consumption и Reload proof, canonical state projection и replay/type guards. Нет hidden refill, global RNG, дублированного броска после Fate или универсальной шины событий. Firearm instance IDs различны даже у PCs с одной immutable definition; trials независимы.

Configured Glorious criteria расширяются на Shooting/Dexterity с прежним spend reserve; decline_optional_fate остаётся явным отказом. Reload test тратит/учитывает Fate и W10 next-Test ровно один раз. Exacting contributions не получают придуманных Complications/bonus effects. Completion Reload тратит свой slot; Rapid Reload/второй action не подставляются.

В исходном first slice нет новых aggregate counters: Shoot/Reload/Recover входят в обычные actions, Fate — в прежние spend/burn наблюдения. Бounded count search сохраняет полную party/weapon/source и сравнивает прежние outcomes. Подробные cycle/progress доказываются native journal, не сохранением всего журнала в compact trial.

## Адресная приёмка

1. Closed source/required Lore+kit+supplies/actualBS/I/caps, exact types и no old-input migration; несовместимый NPC Protection/Shield/backup отвергается до RNG.
2. Literal loaded→HIT/MISS→empty; Damage5/ignores-armour/Close legality/Prone penalty/no Melee bonuses; ready Athletics/Shield Defence и отсутствие автоматического Melee-opposition выбора.
3. Reload0/partial/overshoot/complete, одна Test/receipt за action, следующий shot только позже, independent instances/cycle IDs; no reset при drop/recover/round, duplicate/cached source/alias rejection.
4. Dexterity на Initiative, actual Shooting/Dexterity Fate/Drained/Blinded/W10; без повторного Test и бесплатного progress. Melee Help fallback/Protection Help actual Test binding.
5. Раны4/8/12 и drops,16/18/20/regrip, выбранная hands policy: loaded one-hand shot до недоступного Reload, weapon-first pickup и точный unsupported prefix; Critical14/15/12, Defenceless и конечный objective без ненужного Reload.
6. Current JSON1 roundtrip/full root/candidate echoes, native/trials/search/CLI. Ближайшие PC Wounds/Protection/Help/Fate/weapon/Recover и K1 ranged/reload/Exacting проверки; один actual process representative. Full/wheel — по основаниям AGENTS.md, не автоматически из-за ADR.

## Реализация и проверка

Пользователь подтвердил оба решения. [PcPistolProfile](../../src/towr/domain/pc_melee_models.py) и current JSON1 связывают полный источник; [pc_pistol_models](../../src/towr/domain/pc_ranged_models.py) хранит подготовку выстрела, экземпляр/цикл и Reload proof. [Owner](../../src/towr/domain/_pc_melee_projection.py) подтверждает актуальный prefix и фактический Skill/Fate. Чистое завершение Reload после уже разрешённого Test находится в domain/reload_models; engine и rules используют его без зависимости domain от rules и без повторного RNG.

46 новых тестов прошли составными адресными прогонами:10core,8source,7JSON/services,20native execution и1actual process. Проверены общий K1 Reload/Exacting/ranged путь и209ближайших PC проверок.180прежнихJSON сохранены побайтно; NPC каталог остаётся57. Фактические команды и ограничения проверки — в [статусе](../project-status.md), исполняемые [CLI-примеры](../examples/m54/README.md). Full project regression и wheel не требовались по согласованной политике проверок.
