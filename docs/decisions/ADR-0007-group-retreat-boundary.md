# ADR-0007: групповая граница Retreat и rearguard

Статус: принято 2026-08-30.

## Контекст

Player’s Guide 1.4 на странице 120 разрешает Retreat только при единогласии игроков и только в начале round либо в начале их side turn, когда противник действовал первым. Один персонаж тратит Fate на rearguard. Если у всей группы Fate исчерпан, GM выбирает цену из blood, materiel или misfortune. После этого возможная погоня требует отдельных Athletics Tests, Lore auto-success, opposition более быстрым врагом и агрегации Run For Your Lives.

Текущий K1 не имеет общего battle aggregate, классификатора PC/NPC, состояния инвентаря и campaign consequences. Встраивание всех этих частей в один reducer либо выдумало бы состав группы и цену GM, либо преждевременно создало бы новый battle loop.

## Решение

- Представлять начало Retreat неизменяемым `GroupRetreatDeclaration`: stable battle/Retreat IDs, initiator, ordered PC IDs, отдельный полный consent snapshot и актуальный `CombatRoundState`.
- Проверять оба книжных timing window по round state: до первого хода, когда сторона игроков первая, либо после завершения всей первой opposition side и до первого хода игроков, когда противник первый. Не считать преждевременное объявление до opposition side, активный или частично завершённый player turn допустимым окном.
- Не выводить PC-состав из coalition-like стороны боя. Союзные NPC могут находиться на той же стороне, но сопровождаемые NPC и добыча не получают книжную защиту автоматически; классификацию roster передаёт orchestration.
- Тратить Fate отдельным composite consumer. `FateTacticalRetreatProof` связывает session, actor, spend, battle, Retreat ID и точный ordered PC group; `RetreatRearGuardResult` принимается только с таким proof.
- Не называть rearguard-result окончательным безопасным исходом. Он подтверждает покрытие группы и обязательно сохраняет следующий `pursuit_decision_required`, потому что решение преследовать, Tests и таблица ещё не выполнены.
- Ветку без Fate открывать только по полному immutable snapshot Fate states всех PC с нулевым остатком. Возвращать `RetreatAlternativePriceRequest` с владельцем GM и ровно тремя книжными классами цены.
- Разрешать alternative price отдельным GM decision/result. Result связывает выбор с request/Retreat/battle/ordered group, создаёт proof и ровно один typed application follow-up: один Wound с ещё не выбранной целью, один valuable trapping с ещё не выбранным владельцем либо одну golden opportunity для opposition snapshot. Не выбирать цель, Wound, предмет или содержание opportunity внутри reducer.
- Представлять pursuit отдельным GM-owned request поверх закрытого `RetreatCoverResult`: Fate-funded rearguard либо resolved alternative price. Пустой ordered enemy snapshot означает отсутствие погони; непустой snapshot требует ровно одну попытку на каждого PC в прежнем порядке группы.
- Различать basic Athletics, GM-approved Lore automatic success и Opposed Athletics против конкретного pursuer. Не вычислять выбор pursuer из Speed: формулировка `especially` не создаёт обязательного алгоритма, поэтому enemy selection и contextual opposed tie-break остаются явными входами.
- На Marginal Success требовать отдельное решение: продолжить без Complication, принять Complication со stable ID либо выбрать failure вместо чрезмерной цены. Сохранять failure/Complication facts и вычислять только число будущих обязательных table rolls и доступность одного GM-optional roll при нескольких Complications без failures.
- Разрешать Run For Your Lives отдельным immutable request/result поверх pursuit result. Бросать ровно один `1d10` на каждый failure в ordered PC-порядке; optional roll при нескольких Complications требует явного GM-решения даже для отказа и при согласии добавляется ровно один раз.
- Хранить individual rolls с причиной и source IDs, сумму и typed table band. Положительный итог создаёт только GM-owned campaign-consequence request с полным Retreat context; конкретные потери, перемещения, репутация, долг, враги, пленение и Wounds не применяются без соответствующего campaign state.
- Не мутировать `CombatRoundState` и не объявлять battle завершённым до появления агрегирующего слоя. Первый принятый rearguard-result и одноразовость Retreat между actor-scoped Fate states должен обеспечить будущий battle aggregate.

## Последствия

Состав группы, единогласие, окно объявления и цена Fate проверяются без RNG и без скрытых решений. Три общих Fate spend kind используют один session pool, а raw rearguard и raw alternative-price grant без proof невозможны. Оба книжных способа покрытия группы входят в общий pursuit, Lore/Athletics/opposition, Complication/failure и Run For Your Lives pipeline. Price application и campaign consequence намеренно остаются типизированными follow-up. До общего battle aggregate остаётся внешним запрет второго cover-result для уже принятого Retreat.
