# ADR-0124: стрельба динамических NPC и настоящий цикл перезарядки

Дата: 2026-11-16. Статус: принято пользователем в полном варианте; реализовано и проверено адресными наборами.

## Задача и альтернативы

Добавить общий компонент стрельбы (Shooting) к генератору NPC. Характеристики (Characteristics), навыки (Skills), оружие, броня и допустимые таланты продолжают генерироваться и мутировать независимо от именного каталога. Monte Carlo исполняет полученный состав и независимо проверяет финалистов. Имена и книжные statblocks не дают разрешение использовать новую механику.

Пользователь выбрал законченный чанк из трёх одноручных оружий: пистолет (Pistol), многозарядный пистолет (Repeater Pistol) и многозарядный ручной арбалет (Repeater Handbow). Меньшая альтернатива — тот же общий source/исполнение, но только Pistol; repeaters и выбор режима отложены. Пространственный бой с луками/другими дальностями — отдельная большая функция, для этого чанка не требуется.

## Сверенные источники

- Player’s Guide1.4, гл.III68/70/82/88: Стрельба (Shooting) использует Меткость (Ballistic Skill), Ловкость рук (Dexterity) — Инициативу (Initiative); Знание пороха (Lore: Blackpowder) разрешает применение firearm, не даёт автоматический бонусный куб.
- PG1.4, гл.IV94–95: все три оружия имеют оптимальную дальность Close–Short,1H и максимальную Long. Поэтому разрешены при противнике в Close. Pistol: Damage5, ignores armour, Reload3. Repeater Pistol: Damage5, ignores armour, optional+2d, после выбранного бонуса Reload3. Repeater Handbow: Damage4, optional+1d, после выбранного бонуса Reload3. Обычный выстрел repeater без бонуса не открывает Reload cycle.
- PG1.4, гл.IV94/98–99: достаточный боезапас после подготовки — явный факт сцены. Для firearms подтверждаются Lore и Blackpowder Kit; для Handbow эти требования не выдумываются.
- PG1.4, гл.V107/110/116–119: обычный cap=2×Characteristic; Reload — Exacting Dexterity, один action за Test, накопление успехов. Запрета Reload при Close нет. Shooting получает−1d против Prone, без melee higher-ground/outnumbering bonuses. Промах в Close накладывает первый Staggered, но не повторный.
- PG1.4, гл.III68/гл.IV94/97/гл.V118/123: против Close Shooting доступны Athletics, Defence с фактическим Shield либо Melee; unaware/Defenceless не получают Protection Test. Defensive Stance, PG74, относится только к входящей Melee attack, даже если Shooting отражена через Defence.
- Gamemaster’s Guide1.1, гл.VII91/93: Minion injury policy, явные характеристики и отклонения навыков от Default; NPC Lore выбирает GM. Default не доказывает Lore/kit/supply и не заменяет выбранный отдельный навык числом характеристики.

Число рук для Reload книга здесь не уточняет. Сохраняется уже согласованная интерпретация сцены: оружие удерживается одной пригодной рукой, вторая пригодная рука свободна. Это прежняя scenario policy, не новое книжное правило.

## Принятая исполнимая граница

Остаётся одна stationary all-Close сцена, melee PC против смешанного состава Melee/Shooting Minions. PC сохраняют раны, Fate/Lucky, зелья, два Elementalism spell и принятые боевые таланты. У NPC нет нового движения, Aim, магии или запасного оружия.

У generated NPC одно выбранное оружие: прежнее melee либо одно из трёх ranged. Ranged NPC начинает с заряженным оружием и двумя пригодными руками, без Shield; Light Armour допустима. Shield у melee NPC сохраняется. Это ограничение допуска первого среза: не реализуется скрытый сброс/возврат NPC Shield ради Reload. Недопустимое сочетание нельзя молча исправлять удалением предмета.

Новые исходные факты ranged NPC: BS, Shooting, I, Dexterity, initially loaded, sufficient ammunition; firearm требует явных Lore/kit. Стрелковые факты хранятся отдельным типизированным компонентом `ranged`, равным None у melee NPC (в полном JSON — null); derived Attack/Reload не восстанавливаются по ID. Existing WS/Defence/Athletics и Talent source сохраняются. Защита NPC от Melee выбирается из законных Defence/Athletics по прежнему критерию. PG68 и GM93 разрешают Defence вооружённому NPC, не ограничивая weapon словом melee; Pistol/Handbow не получают отдельного придуманного parry Trait или бонусов Sword/Staff.

Автоматический NPC envelope выводит разумные BS/I/Shooting/Dexterity диапазоны из партии, где эти факты известны; при их отсутствии использует документированную ограниченную стартовую область, не фиктивные характеристики игроков. Ручные диапазоны приоритетны. Sampler сначала выбирает допустимый тип/оружие, затем относящиеся компоненты. Не создаётся декартов каталог готовых профилей; мутации пропускают несовместимые предложения, не переписывают source.

## Выбор действий и режима

Pistol исполняет настоящий Shoot→Exacting Reload3→Shoot столько раз, сколько позволяют живые участники и лимит боя. Каждый Reload занимает действие и сохраняет фактические успехи; не заменяется задержкой на фиксированное число ходов. Промах тоже расходует заряженный Pistol. У repeater ordinary shot сохраняет ready state, выбранный бонус открывает Reload3 независимо от попадания и насыщения cap. Drained запрещает положительный бонус; уже открытый cycle нельзя отменить.

NPC автоматически выбирает ordinary либо bonus shot до броска; пользователь не задаёт per-actor паттерн. Принята ограниченная оценка на H=min(3, оставшееся число собственных ходов, включая текущий), с текущими целями/Conditions/Resilience неизменными только для прогноза. Цель сохраняет существующий enemy_target_priority. Ценность выстрела — прежняя ожидаемая польза попадания/раны; качество/броня/cap учитываются реально подготовленным Test.

Состояния прогноза — loaded либо число оставшихся успехов Reload1–3. Loaded сравнивает ценность ordinary shot плюс продолжение loaded с ценностью bonus shot плюс продолжение Reload3. Для Reload продолжение усредняется по точному конечному распределению Dexterity successes. На горизонте0 польза0; при равенстве обычный выстрел без нового Reload. Это небольшая динамическая программа, без RNG, расхода ресурсов или вложенного Monte Carlo, а не оптимальная стратегия всего боя. Literal tests должны показывать оба выбора и учёт реальной цены Reload.

PC автоматически выбирает законную Athletics/Shield Defence/Close Melee Protection, без нового ручного выбора во входе партии. Общий подготовленный Test используется и в advisor, и в actual proof. Учитываются рабочие руки, Shield, раны, Conditions, Fate и уже адресованная Help; выбор фиксируется до броска. Wild Attack не получает новую активацию в чужой ход и не применяется к Shooting; собственные Attack/Melee Help сохраняются. Defensive Stance не срабатывает от Shooting.

PC advisor больше не предполагает, что каждый NPC каждый ход атакует Melee: различает Shooting и текущий Reload, Armour ignore и Prone penalty; защита/Help адресуются настоящему будущему Test. Применимые старые механики не отключаются для облегчения интеграции.

## Публичный source и взаимодействия

В Dynamic JSON1 расширяются допустимые weapon и диапазоны BS/I/Shooting/Dexterity. В resolved NPC и отдельном NPC-файле сохраняется полный conditional `ranged` component. Текущие примеры/схемы/character files/UI обновляются вместе, без compatibility aliases или нового wire version. UI показывает новые значения в уже существующих placeholder-полях и выбранное оружие тегом; новые ручные tactical policies не добавляются.

Native JSON поле `scenario.enemies[].pistol` заменяется на `scenario.enemies[].ranged`, Python `npc_pistol_policies` — на `npc_ranged_policies`; соответствующий runtime bank/shot/reload owner обобщается в `ranged` с единым shot/reload owner для generated источников и прежних Official/Ogre Pistol. Canonical старые профили продолжают проверяться полностью; новая capability допускается только по целым generated components. Текущие native request/replay примеры мигрируются, historical ADR не переписываются. Source включает новый descriptor, реальные next cycle IDs/progress, выбранный repeater mode и однократные receipts. Итог не допускает потерянный/повторный выстрел, Reload или mandatory Wound/Miscast continuation.

Minion source, proof ownership, частные seeds, independent trials/process transport, budget/cancellation и независимая validation финалистов сохраняются. Отдельная Magic JSON6 family не меняется.

## Адресная приёмка после выбора

- Admission/derive/sampler/mutation: произвольные допустимые BS/I/Skills, все три weapons, mixed compositions, no ID dispatch, несовместимый Shield, ложные Lore/kit/supply, неверные типы и подменённые generated profiles — отказ до MC. Без искусственных готовых статблоков.
- Literal многократный Shoot/Reload/Shoot, partial/zero-success Reload, cap/minimum die, HIT/MISS, ordinary/bonus repeater, Drained, mode commitment, точные руки/цена/однократность, NPC magic-penalty consumption и existing on-hit effects. Проверять actual proofs и full replay.
- PC Protection/Help/Fate/Lucky/Shield/руки/раны; правильный Prone Shooting penalty, отсутствие melee bonuses, armour ignore, miss Staggered, no Defensive Stance vs Shooting, собственные Wild Attack/Help без лишних активаций.
- Конечный advisor показывает ordinary/bonus choices и Reload cost без RNG; PC risk не создаёт несуществующую атаку во время Reload. Счётчики Shooting и Reload разделены и связаны с реальными действиями; UI показывает полезные aggregate расходы.
- Dynamic JSON1/native replay/character-file source roundtrip, offline schema refs, один real process parity, mixed generated CLI smoke и UI. Прежние melee generated NPC, PC talents/potions/magic и canonical NPC Pistol — адресные зависимые проверки. Full/wheel только при основании по AGENTS.md.

Полный вариант выбран пользователем. Веха выполняется через все необходимые слои до проверяемого результата; меньший вариант только с Pistol не выбран.

## Реализация и результат

Три оружия, полный conditional generated source, совместимые мутации, общий native shot/Reload owner, конечный выбор режима и автоматическая PC Protection подключены. Current Dynamic/PC JSON1, character files, UI, actual observations и current M61–M63 examples мигрированы вместе. Старый Pistol source/owner удалён, compatibility aliases отсутствуют. Общий выбор Protection Help исправлен для известного Reload; причина изменения M63 подтверждена A/B запуском со старым selector и отдельным deterministic test.

Финальные48проверок нового среза,295зависимых,26magic/potions JSON-проверок, реальный mixed sequential/process и отдельный повтор browser прошли. Все124current PC request/result pairs проверены offline без симуляций; collection6354tests без import errors не выдаётся за full regression. [Точные команды, результаты и ограничения](../project-status.md#текущий-срез-стрельба-динамических-npc). Full/wheel по действующей политике не запускались.
