# ADR-0125: стрельба PC и автоматическая смена оружия в генераторе

Дата: 2026-11-16. Статус: принято пользователем в полном варианте; реализовано.

## Задача и принятый фундамент

Подключить стрелковые факты игроков к динамическому генератору. Общий PC ranged owner уже исполняет выстрелы, Reload, Fate, руки, Shield и Wounds в прежних явных сценах. ADR-0124 добавил generated Melee/Shooting Minions и автоматическую PC Protection. Недостаёт допуска фактов партии и общего выбора собственного действия; копировать manual Shoot→Reload pattern в обычный UI не требуется.

Принят законченный срез: Pistol, Repeater Pistol и Repeater Handbow, optional Shield, один carried1H melee backup из шести уже поддержанных видов, обратимая смена между этими двумя предметами и Shooting Help. Сохраняются melee PC, potions, два Elementalism spell, Lucky/Fate и два боевых Talent. Рекомендуемый вариант не вводит пространственный бой или новый каталог NPC.

Меньшая альтернатива — те же три стрелковых оружия, optional Shield и автоматические Shoot/Reload/Help, но без запасного оружия и смены. При действительно недоступном Reload остаётся точный stop, если другое поддержанное действие не решает ситуацию. Меньший вариант не выдаётся за полное управление инвентарём.

## Источники

- Player’s Guide1.4, гл.IV92–95: переносимое оружие,1H/2H, три Close–Short ranged profiles, Damage/armour ignore и conditional Reload repeaters. Количество weapons до Strength; превышение даёт Burdened, а не абсолютный запрет ношения.
- PG1.4 III68/70/82/88, IV98–99: BS/Shooting, I/Dexterity, Lore (Blackpowder), Blackpowder Kit; доступ к firearms не добавляет автоматический бонусный куб. Handbow не требует Blackpowder Lore/Kit.
- PG1.4 V107–108/110/116–119: cap, Exacting Reload, draw/swap как incidental action в свой ход; поднятие dropped предмета рядом с enemy требует Recover. Help может поддержать релевантную upcoming Test, не только Melee. Положительные бонусы/Drained и Close MISS применяются прежним ядром.
- PG1.4 III74/81, V111/122–123, Appendix190–191: Defensive Stance/Wild Attack, actual Fate, ongoing Conditions и hand/other-action последствия ран. Смена предмета не устраняет травму, не восстанавливает dropped предмет бесплатно и не отменяет Critical end-phase.

PG92 и PG108/116/117 адресно перечитаны для carry/swap/Help; профильные94–95, принятые руки/Reload/Shield/Wounds и Fate сверяются с уже прочитанными источниками ADR-0100/0102/0106/0123/0124. Новых книг или house rules не вводится. Две пригодные руки Reload остаются ранее выбранной scenario policy.

## Вход партии и UI

В `party[].characteristics` появляются исполняемые `ballistic_skill` и `initiative`, в `skills` — `shooting` и `dexterity`. Они обязательны для стрелкового loadout и не выводятся из WS/Agility или рейтинга другого Skill. У чистого melee PC эти optional факты не создаются искусственно. UI использует существующие поля/порядок книги, активируя их при выборе поддержанного ranged primary; отсутствующие факты явно требуют ввода.

Отдельный `party[].ranged` содержит факты подготовки единственного начального ranged-оружия, без чисел тактики:

```json
"ranged": {
  "initially_loaded": true,
  "ammunition_supply_confirmed": true,
  "has_blackpowder_lore": true,
  "has_blackpowder_kit": true
}
```

Для Handbow оба Blackpowder поля равны null. Наличие Lore/kit/supply подтверждает персонажа и сцену; это не derived бонус и не произвольная policy. Срез начинает fresh loaded бой; иной draft можно сохранить, но неподдержанный старт отвергается до MC. У начального melee loadout этот объект отсутствует.

Оружие по-прежнему описывается предметами с ID и location. Первое held ranged оружие — начальное активное; optional единственный melee backup начинает carried. Требуется Strength≥2 при двух weapons, чтобы этот срез не создавал начальный Burdened. Два held weapons, вторая пушка, несколько backups, dual wield и избыточный carry остаются явными unsupported drafts. Ничего не удаляется и не выбирается молча при компиляции.

Optional Shield/Light Armour/Helmet сохраняются как отдельные предметы. Shield не превращается в weapon или автоматический Lore. Native source, character files, source echo и replay сохраняют полные данные; переключение UI/JSON не теряет новые факты. В обычном UI нет input паттерна Shoot/Reload, режима repeater, Help recipient или Fate threshold.

## Состояние оружия и обратимая смена

Начальная активность описывает начало боя, а не обязанность первым действием выстрелить. Controller может предпочесть melee уже в первый свой ход, если это полезнее. Принято не более одной добровольной смены оружия за свой ход: ограничение автоматической тактики, не утверждение о книжном запрете других incidental actions.

Полный вариант хранит состояния двух конкретных предметов: held/carried/dropped и actual hand, а заряд/cycle/progress принадлежат ranged instance независимо от активности. Убранный в carried Pistol остаётся пустым или частично перезаряженным; возврат не даёт нового заряда или успехов Reload. Обычный swap не означает drop. Dropped Pistol нельзя объявить carried и достать бесплатно: требуется настоящий Recover, отдельно от подбора другого предмета.

Смена выполняется только в свой ход до обещанного основного Test, при законных руках, после mandatory continuations. Новый source-bound receipt фиксирует предметы, состояния/руку до и после и committed action/target/mode. Выбор не пересчитывается после изменения фактов в swap так, чтобы устроить цикл переключений. Incidental use сохраняет W12/14/15 Critical последствия; сама смена не создаёт дополнительный основной action/Test/Fate.

После потери руки заряженный Pistol может выстрелить; при empty и недоступном Reload controller может выбрать carried melee. После Healing Potion и восстановления рук разрешено снова достать Pistol и продолжить тот же Reload cycle. Это настоящее обратимое владение предметами, а не прежний необратимый boolean fallback. Неподдержанная анатомия/нет доступных предметов не обходятся выдуманным unarmed Attack.

Shield использует фактические положения/руки: при нужном Reload его придётся освободить, а возврат dropped Shield занимает Recover. Сохраняется ранее выбранная тактика Shield drop→Recover; это не утверждение, что книга запрещает убирать Shield в carried. Новый обратимый swap касается двух weapons, не скрытого изменения этой тактики Shield. Controller учитывает эту цену в выборе; не выполняет Reload через занятую/непригодную руку. Предметы не телепортируются и не поднимаются одновременно одним interaction. Прежние explicit fixed policies сохраняют собственные правила как самостоятельные поддержанные тактики; новый automatic mode не подменяет их поведение. Это не сохранение старого wire format.

## Автоматический выбор действия

Общий selector сравнивает Shoot/ordinary или bonus repeater, Reload, доступную Melee Attack, standard Recover, potion, Help и два поддержанных spells. Оценивает настоящие prepared Tests, caps/Conditions/оружие/Protection/armour ignore, available Fate/Lucky, руки и цену смены/Reload/Shield Recover. Не тратит RNG/ресурсы и не запускает вложенный Monte Carlo. При равной пользе предпочитает отсутствие добровольной цены и смены, затем стабильный source order.

Для Shoot/Reload используется конечный горизонт до трёх собственных основных действий, аналогично ADR-0124, но с актуальным PC Fate policy и возможностью melee. Разрешённые промежуточные состояния включают готовность/cycle, активный предмет и Shield; недоступные переходы не оцениваются как бесплатные. Это ограниченная эвристика, не оптимальный ИИ всего боя. Будущие enemy outcomes и dice не читаются.

Fate расходуется только в actual окне; compiler добавляет Shooting/Dexterity к прежним автоматическим критериям Glorious при0initial successes и полезном эффекте. Near Miss≥11 остаётся прежним. Auto repeater не требует ручного `when_available/never`; native source фиксирует автоматический выбор до roll и запрещает повторный bonus/Fate reroll. Drained может сделать ordinary shot законным и полезным без открытия Reload.

Wild Attack по-прежнему относится только к Melee Test, включая Melee Help; он не усиливает Shooting, Dexterity или Casting. Defensive Stance требует отражённой Melee attack и реально доступного нового Staggered; ongoing W15 не снимается. Два spells и potions не отключаются при первоначально ranged loadout.

## Помощь и защита

Help к атаке обобщается на конкретный upcoming Melee или Shooting Test. Selector учитывает, действительно ли получатель собирается атаковать, а не Reload/Recover/Cast/swap ради другого действия. Бонус связывается с actor, Skill и Test ID; не переходит на Reload или другое оружие/проверку после смены плана. Protection Help сохраняется отдельно.

По PG95 optional bonus repeaters относится к Shooting Test, а не только к Attack. Полный срез включает выбор бонуса и для Shooting Help: режим фиксируется до броска, actual Help Test получает правильный+1d/+2d, затем открывается Reload3 по тому же weapon instance. Это typed Test-use receipt, не выдуманная Attack. Обычный Shooting Help не расходует заряд Pistol, не создаёт Damage/Close-miss Staggered и не увеличивает shots; bonus Help считается отдельно от bonus shots. При Drained или cap-эквивалентной цене selector может отказаться от бонуса.

Для первого автоматического режима Shooting Help выбирается только при held loaded ranged weapon и пригодной руке; это ограниченная тактика, не книжный запрет помогать без заряженного оружия. Использование actual руки сохраняет W12. Результат Help не переадресует bonus на другой Test, а отменённый/неисполненный Help не создаёт Reload. Запрет повторного reload-cycle/bonus-Test proof сохраняется независимо от того, была ли выполнена Attack.

Native current PC Help contract использует `target:"attack"` и `skill:"melee"|"shooting"`; для `target:"first_incoming_protection"` тот же `skill` задаёт Defence/Athletics/Melee. Это заменяет прежнее поле `protection_skill`, а старый `melee_attack` не сохраняется как alias. Текущие схемы/примеры мигрируются вместе.

PC получает автоматическую Close Protection из ADR-0124. Generated NPC против PC Shooting выбирает законные Athletics, Defence с actual Shield или Close Melee по полным component-derived профилям; обычная Defence без Shield не становится законной из-за хорошего числа. Defenceless не Oppose. Melee Protection/Help не расходуют дополнительный заряд.

## Текущий контракт и ответственность

Автоматическая policy получает нейтральное имя `automatic_combat` вместо `automatic_melee`; исходные explicit сценарные policy остаются отдельными тактиками. Это один текущий PC JSON1, без deprecated периода/alias/новой wire version. Dynamic JSON1, native source/replay, schemas, UI, current examples/tests обновляются вместе. Magic JSON6 не меняется.

Native source автоматического loadout сохраняет ID и исходные позиции конкретных предметов, а derived primary/grip/ranged profiles проверяются на совпадение с этими фактами. Одного using_backup_weapon boolean недостаточно для обратимого владения dropped/carried предметами.

Application компилирует факты и инвентарь, controller выбирает допустимое действие, domain/engine владеют actual исполнением и source-bound журналом. Не создаётся универсальный DSL, event bus или общий планировщик всех предметов книги. Счётчики PC shots/bonus shots/Reload, Shooting Help/bonus Help и swaps наблюдают реальные receipts; Help не считается выстрелом, swaps не раздувают action budget. Process trials получают независимые item/weapon/Fate состояния. Поиск NPC/independent finalist validation/seed/план/отмена сохраняются.

## Адресная приёмка

- Четыре новые характеристики/навыка-факта: строгие типы/границы/требования, Lore/kit/supply и Handbow null, исходный grip/Shield/carry/ID; malformed input до MC, character-file/UI/JSON roundtrip без silent repair.
- Literal все три оружия: actual повторные выстрелы/partial+zero+complete Reload, ordinary/bonus/cap/Drained/Prone/armour ignore, Fate/Lucky/минимальный куб, правильный action budget и полное replay.
- Двусторонний swap с carried/dropped/held, разные руки и реальные Wounds12/14/15/16/18/20, отсутствие бесплатного pickup/нового заряда/cycle; Shield release/Recover, Healing Potion→возврат, terminal/mandatory/foreign/repeated receipt guards.
- Melee/Shooting Help с конкретным Skill/Test, Repeater bonus Help→Reload без fake Attack/shot/Damage/miss penalty, обычный Pistol Help без расхода заряда; защита от mixed generated enemies; отсутствие Wild на Shooting и Stance от Shooting; PC magic/potions/обычный melee без регрессии.
- Конечный selector без RNG: Shoot versus Reload versus melee, цена Shield/свапа, оба repeater режима, стабильное равенство/committed intent. Полезный mixed party/NPC пример, current schemas/native source, aggregate bounds, один real sequential/process и UI.
- Адресные зависимые PC source/owner/Help/Fate/inventory/Shield/Wounds/magic/potions/generator проверки; полный regression/wheel только при основании по AGENTS.md.

Исполнение: [инвентарь и смена](../../src/towr/domain/pc_weapon_inventory.py), [конечный выбор](../../src/towr/domain/pc_ranged_advice.py), [Shooting Help](../../src/towr/domain/pc_ranged_models.py), [наблюдаемые счётчики](../../src/towr/simulation/pc_ranged_statistics.py). Проверки: [literal/native inventory](../../tests/unit/test_pc_weapon_inventory.py), [Help без fake shot](../../tests/unit/test_pc_ranged_help_use.py), [конечный прогноз](../../tests/unit/test_pc_ranged_advice.py), [счётчики](../../tests/unit/test_pc_ranged_statistics.py), [source/JSON/генерация/process](../../tests/integration/test_dynamic_pc_ranged_json.py). Фактические последние команды и результаты — в [статусе](../project-status.md).

[Настоящий ranged Wizard](../../tests/unit/test_pc_ranged_magic.py) проверяет Shoot→partial Reload→Casting с расходом Судьбы (Fate), без потери состояния экземпляра и с полным повторным воспроизведением журнала.
