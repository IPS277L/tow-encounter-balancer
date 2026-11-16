# ADR-0121: общее melee-снаряжение динамических NPC

Дата: 2026-11-16. Статус: принято пользователем и реализовано. Выбран полный чанк с автоматической защитой.

## Задача и источники

Динамический поиск сейчас меняет характеристики (Characteristics), навыки (Skills), посох (Staff), кинжал (Dagger), лёгкую броню (Light Armour) и разрешённый authored эффект Drained. Следующий результат — новые комбинации общего снаряжения, а не новые именные statblocks. Имеющиеся PC и книжные NPC consumers не означают, что их свойства уже исполняются для generated NPC.

Адресно сверены Player’s Guide1.4, гл.III Characteristics & Skills68; гл.IV Melee Weapons93 и Armour97; гл.V Skill Table107. Defence использует Weapon Skill, Athletics — Agility. Armour97 включает Shield в определение armoured; свойство Axe нельзя проверять только по body armour. Нормализованные правила: RULE-EQUIPMENT-003/006, RULE-COMBAT-006. Для дальнейшей реализации использовать также текущие общие Tests/Conditions/Damage consumers, не превращая существующий код в источник правил.

## Принятый чанк

Сохраняются Staff и Dagger; добавляются четыре одноручных Close-оружия и Shield:

| Компонент | Выводимые значения и исполняемое свойство PG93/97 |
|---|---|
| Топор (Axe) | Damage=S; +1 Damage против armoured цели |
| Меч (Sword) | Damage=S; +1d к Defence, пока владелец не Staggered |
| Боевой молот (Warhammer) | Damage=S; +1d к Melee против Staggered цели |
| Моргенштерн (Morning Star) | Damage=S+1; −1d к Melee при собственном Staggered; без dual wield |
| Щит (Shield) | +1 Resilience отдельно от Light Armour; занимает вторую руку |

Каждый NPC несёт одно выбранное 1H-оружие и optional Shield, с Light Armour либо без неё. Strength/Toughness и конкретные предметы выводят Damage/Resilience; их производные числа не вводятся вручную. Staff/Dagger сохраняют прежний Damage и не получают несуществующих боевых бонусов conceal/terrain. Drained удаляет положительные dice modifiers, но не Damage bonus Axe; действуют обычные caps и отрицательные modifiers. Никакого автоматического присвоения книжных Talents этим чанком нет.

Первый путь остаётся stationary all-Close против Minions, с прежними PC potions/magic и обязательными последствиями. NPC пока не стреляют. Shield сохраняется как настоящий предмет/факт, но отдельный generated Shooting-сценарий этим решением не заявляется. Heavy Armour, dual wield, смена оружия, NPC-зелья/магия, новые статусы NPC и преследование вне среза.

## Автоматическая защита

GeneratedNpc получает отдельное числовое значение Defence наряду с Melee/Athletics. Builder сохраняет обе допустимые защиты: WS/Defence и Agility/Athletics. При реальной incoming Attack NPC выбирает профиль с большим ожидаемым числом успехов после фактических условий, применимых weapon modifiers и cap; при равенстве выбирается Defence. Это ограниченная детерминированная тактика без будущих бросков или вложенного Monte Carlo, не доказательство оптимальной защиты по всем исходам боя.

Выбор пересчитывается для каждой защиты: Sword bonus пропадает при Staggered, Drained удаляет его как положительный куб, отдельный next-Test penalty учитывается до выбора. При Defenceless/Unaware не создаётся фиктивная Protection Test. PC advisor и исполнение используют один и тот же подготовленный профиль, чтобы поиск не оценивал другую защиту. Альтернатива с прежней Athletics-only защитой отклонена пользователем: выбрано полноценное применение Sword и обоих защитных навыков.

## Источник и публичная граница

GeneratedNpc и NpcSearchSpace дополняются `defence` и `shield`, а enum оружия — четырьмя значениями. В автоматических диапазонах Defence строится вокруг партии, разрешаются шесть оружий и варианты Shield false/true; ручной search space остаётся приоритетным. Proposal/mutation самостоятельно выбирают и варьируют новые компоненты при прежнем trial budget, без перечисления всего декартова произведения.

Native описание NPC сохраняет типизированные факты выбранного снаряжения, достаточные для проверки полного source и вывода modifiers. Новый путь проверяет компоненты и связанные профили/Resilience/руки, а не выдаёт Traits по canonical ID или только по строке `source_rule_id`. Существующие именные definitions остаются на своей проверенной границе; общие modifiers переиспользуются без двойного наложения печатных чисел/бонусов. Входы, proofs и current replay должны отвергать подменённое снаряжение, несогласованные профили и shield state.

Для Axe/магии общий факт armoured цели должен учитывать Shield и надетую броню, включая сохранённый Helmet с нулевым отдельным бонусом; нельзя приписывать шлему лишнюю Resilience или терять факт его ношения при компиляции партии. Это относится к общему факту снаряжения, а не к наличию Wizard tag.

Текущие Dynamic/PC JSON1, schemas, parser/encoder, характер-файлы NPC, примеры и tests обновляются вместе; compatibility-ветки не вводятся. UI показывает Defence и Shield, все шесть weapons и точные tooltips свойств в текущем стиле. Полный источник и downloaded executable replay содержат новые компоненты. Пользователь не задаёт отдельные attack/protection bonuses или tactical policies.

## Адресная проверка

- Derived Damage/Resilience/руки и оба профиля; Shield без body armour, Light Armour+Shield, S1 Dagger Damage0, несовместимые/подменённые components и исходные nested значения.
- Literal RNG: каждое из четырёх свойств по обе стороны условия, Drained/cap/negative modifier, выбор Defence/Athletics и смена при Staggered, отсутствие лишней Protection при Defenceless.
- Полный native source/projection/replay и однократность; независимость механики от имени/ID, прежние книжные source guards, обе Elementalism spells и armoured metadata, включая Helmet/Shield.
- Реальный dynamic поиск при фиксированном числе NPC создаёт разные допустимые комбинации; explicit manual space соблюдается, мутации/independent validation/seeds/budget сохранены. Current JSON/schema/character-file roundtrip; UI editor/result/export и один representative process parity.
- Проверки изменённых generated/equipment/protection/tactics компонентов и ближайших simulation/JSON callers. Не повторять full/wheel без отдельного основания по AGENTS.md.

## Исполнение текущего контракта

`NpcDefinition.generated_components` сохраняет полный типизированный GeneratedNpc. Общий roster validator заново выводит все profiles/Resilience; PC admission дополнительно проверяет исходные условия/Shield state. Components нельзя удалить, сохранив generated source label, или подменить одним правилом/ID. Старые canonical/numeric definitions остаются на своей границе.

`pc_generated_equipment.npc_protection_test` используется и native Attack, и advisor. В admitted NPC Protection нет quality/success modifiers: сравнение ordinary Tests выполняется точно через целочисленный числитель dice×threshold, с уже применёнными cap/минимальным кубом/отрицательными modifiers. При равенстве исходный порядок Defence→Athletics сохраняется без float-погрешности. Прогноз Recover удаляет prospective Staggered перед оценкой Warhammer, а реальные receipts по-прежнему опираются на актуальное состояние.

Current native JSON1 сохраняет existing `protection` и условный `alternate_protection` только вместе с `generated_components`; decoder восстанавливает полный tuple. Нет второй версии/legacy decoder. Generic `party[].armour_worn` заменяет дублирование факта внутри Wizard: compiler записывает реальную worn body/Helmet броню, native источник может не задавать поле, когда достаточно прежнего числового body bonus. Нулевой бонус Helmet сохраняет armoured=True без увеличения Resilience; рабочий Shield учитывается отдельно в runtime. Магический профиль содержит только факты мага.

[Native literal/source/защита/магия](../../tests/unit/test_generated_npc_equipment.py), [current JSON/roundtrip/process](../../tests/integration/test_generated_equipment_json.py), [исполняемый пример](../examples/dynamic/equipment.request.json), [последние команды/результаты](../project-status.md#текущий-срез-снаряжение-динамических-npc). Shared schemas используют прежнее resource discovery; wheel/full не запускались без основания.
