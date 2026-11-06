# ADR-0088: Brewguard, источник Distracted и время действия

Дата: 2026-11-06. Статус: **трактовка A принята пользователем и реализована в M42**. Focus — фактический attacker первой раны, Condition снимается после его подтверждённой смерти; Defenceless не снимает эффект.

## Задача и подтверждённые правила

BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Dwarf Brewguard104: Normal Brute2, T4/Res5 armoured, Warhammer Close4d/3 Damage3,1H, Defence4d/3; alternate Athletics2d/3 и Bare Hands не выбираются. W1 содержит «Attacker inflicts Distracted condition», W2 defeats. GM92–93 описывает Wound bands как изменения раненого существа: Condition получает Brewguard, накладывает её фактический attacker. Новый Distract action или Opposed Willpower Test для наложения не указан. PC Warhammer Traits не добавляются к printed NPC профилю.

BOOK-PLAYER-GUIDE1.4, гл.V Conditions122 / Distracted123: штраф−1d действует на Tests, включая Opposed, направленные на что-либо кроме объекта отвлечения. Новый Distracted заменяет прежний. Указаны refocus через Willpower и прекращение отвлечения при поражении либо исчезновении отвлекающего персонажа из видимости. PG117 различает defeat и rendering Defenceless: живой Defenceless сам по себе не является подтверждённым поражением focus.

PG122 запрещает снимать Condition от ongoing Wound, пока не устранена причина. GM104 не уточняет, является ли W1 одноразовым наложением от attacker либо постоянно поддерживаемой Wound причиной. Он также не называет focus. PG129 Distract связывает отвлечение с применившим его персонажем; PG30 In My Sights явно называет quarry, применяющего Distracted, и отсутствие штрафа против quarry. Это поддерживает focus=attacker, но не заменяет отсутствующее уточнение карточки Brewguard.

Неоднозначность влияет на достижимый бой: wounded Brewguard может пережить гибель PC, который нанёс первую рану. Fixed Close/noMove исключает обычную потерю видимости, но не смерть или Defenceless. Простого флага Condition недостаточно для правильного−1d и снятия эффекта.

## Принятая трактовка A

1. При подтверждении actual Wound0→1 атакующий разово накладывает Distracted на Brewguard. Focus — **фактический PC, нанёсший эту рану**, включая Wound от repeated Staggered; не helper, не текущая preferred target и не произвольно выбранный объект. Это принятая конкретизация карточки, а не дословно указанное в ней правило выбора focus.
2. Пока focus действует, Brewguard делает Melee по этому PC и Protection против него без штрафа Distracted. Против остальных PC получает один ordinary−1d, с обычным минимумом пула; bonus dice/Help применяются своими существующими правилами. Первый завершённый Test/Wound не пересчитывается задним числом.
3. При **подтверждённой смерти** focus Distracted снимается, даже если Brewguard остаётся с W1. Raw lethal injury до закрытия Near Miss/Fate окна не подтверждает смерть. Defenceless, Prone, завершённый ход PC и смена target priority не снимают эффект и не переназначают focus.
4. W1 сам по себе не накладывает Condition повторно после снятия или замены. В этой трактовке применимы обычные способы refocus; реализация Willpower Recover, Cooler Heads и внешней замены не входит в M42. Если появится другое Distracted, оно должно заменить прежнее по PG123; автоматического возврата старого focus нет.

## Отклонённая альтернатива B

Focus также равен первому ранившему PC, но W1 считается ongoing Wound причиной. Пока рана сохраняется, Distracted сохраняется и после гибели focus: Tests против оставшихся PC продолжают получать−1d. Автоматического снятия или переназначения нет. Лечение/Recover/замена и повторное наложение требуют отдельной будущей границы. Это другая трактовка взаимодействия GM104 и PG122–123; её нельзя незаметно подставить вместо A.

Источник допускает несколько прочтений; нормативная уверенность сверх текста не заявляется. Пользователь явно выбрал A, с сохранением обеих ссылок на книги. B не реализована; публичного переключателя между трактовками нет.

## Реализованная граница M42

Добавить один `DWARF_BREWGUARD_WARHAMMER = dwarf_brewguard_warhammer`, source `BOOK-GM-GUIDE:1.1:p104:dwarf_brewguard_warhammer`, без щита, exact printed profiles и обычными caps8/8. Fresh source не содержит начального Distracted. Полные Bare Hands и Cooler Heads Prevail остаются явно unselected/inactive в fixed Attack/SUFFER_WOUND сцене. Cooler Heads — отдельное optional Leadership действие: каждый success позволяет снять Distracted у одного выбранного character в Medium; оно не становится автоматической тактикой.

M42 — новая функция object-aware Condition с одним validating book loadout; не одиночная каталоговая веха ради количества. Она включает модели/source admission, наложение на actual profile ACK, подготовку Melee/Protection с actual focus, lifetime по выбранной трактовке, native replay, trials/count search/current JSON1 и полезные CLI-примеры.

Публичные source policy/стратегии/метрики/версия PC JSON1 не меняются. Focus выводится из фактической истории, не принимается свободным полем caller. Старые132JSON documents M9–M41 и41loadouts сохраняются. В отчёте результат эффекта отражается обычными исходами/расходами; наложение или снятие сами по себе не являются действиями и не требуют RNG.

## Ответственность слоя

`ConditionState` сохраняет общий флаг; не превращать его в глобальный provenance framework ради одной функции. PC owner хранит небольшой typed source/focus bank, связанный с actual полным Attack/profile-Wound receipt и Rule ID. Он проверяет канонический Brewguard, рану0→1, реального attacker и однократность ACK. Равенство ID или projected injury само по себе не доказывает членство в истории.

Наложение и, для A, снятие — проверяемые последствия реального journal prefix. Они завершаются до следующей подготовки Test. Снятие по гибели focus не обходит mandatory Wound/Fate работу и не вызывает TurnEnd либо дополнительный action slot. Общий kernel получает уже подготовленный Test, без знания стратегии и source bank.

Модель ограничена PC family и этим источником. Troll Stupidity/Foul Stench, spells, social Distract, NPC лечение и произвольные focus objects не считаются автоматически интегрированными. Общий [вопрос provenance](../open-questions-details.md#источник-distracted) остаётся шире M42.

## Проверки

1. Exact source/fresh snapshot/Defence versus alternate Athletics, T4Res5/noShield, Warhammer без PC Traits; W0/W1/W2 и отказ чужим/частично переименованным/cached источникам до RNG.
2. Actual direct/repeated-Staggered Wound0→1 накладывает Condition один раз после удаления Staggered; завершённая Protection не меняется. Helper не становится focus. W2 defeats без новой Condition или лишнего действия.
3. Два PC: Melee/Protection против focus без штрафа, против другого−1d; actual target selection не заменяет focus. Проверить сочетание ordinary cap/Help, сохранение penalties при Drained на чистом уровне подготовки и целостность source/Test receipts.
4. По A: confirmed focus death снимает эффект до следующего Melee/Protection; Near Miss сохраняет focus; Defenceless без смерти не снимает. По B: соответствующие проверки фиксируют сохранение эффекта при W1. После снятия нет самопроизвольного повторного наложения.
5. Native journal → trials/summary → subsets/count search → current JSON1/full source echoes → CLI. Сохранение старых41entries/132JSON documents; адресный прогон изменённого поведения и ближайших Condition/Wound/Help/Fate consumers. Full/wheel/повторная backend matrix без отдельного влияющего изменения не требуются.

Согласование требуется по [AGENTS.md](../../AGENTS.md), раздел «Автономная работа до согласованной вехи»: «Спрашивать при существенной неоднозначности правил, смене согласованного контракта или блокере с решением пользователя». Здесь неоднозначны focus/lifetime W1 эффекта, и различие достижимо в нынешнем бою.

Реализация: [source/focus bank и expiry proof](../../src/towr/domain/pc_npc_distraction_models.py), [owner/Test preparation](../../src/towr/domain/pc_melee_result_models.py), [profile ACK/expiry projection](../../src/towr/domain/_pc_melee_projection.py), [runner](../../src/towr/engine/pc_melee_runner.py). Проверки: [catalog](../../tests/unit/test_m42_pc_brewguard_catalog.py), [15 native cases](../../tests/unit/test_m42_pc_brewguard_execution.py), [JSON/trials/search](../../tests/integration/test_m42_pc_brewguard_json.py), [CLI-примеры](../examples/m42/README.md). Единый PC checkpoint72модулей/665tests OK за35.251s, включая все29новыхtests. Точные команды/ограничения/следующий шаг — в [статусе](../project-status.md).
