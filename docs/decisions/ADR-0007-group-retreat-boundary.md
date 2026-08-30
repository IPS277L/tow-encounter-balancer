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
- Ветку без Fate открывать только по полному immutable snapshot Fate states всех PC с нулевым остатком. Возвращать `RetreatAlternativePriceRequest` с владельцем GM и ровно тремя книжными классами цены; не выбирать цель, Wound, предмет или golden opportunity внутри reducer.
- Не мутировать `CombatRoundState` и не объявлять battle завершённым до появления агрегирующего слоя. Первый принятый rearguard-result и одноразовость Retreat между actor-scoped Fate states должен обеспечить будущий battle aggregate.

## Последствия

Состав группы, единогласие, окно объявления и цена Fate проверяются без RNG и без скрытых решений. Три общих Fate spend kind используют один session pool, а raw rearguard без proof невозможен. Следующий срез может независимо добавить pursuit decision, Lore/Athletics и Run For Your Lives поверх сохранённого ordered PC snapshot. До общего battle aggregate остаётся внешним запрет второго rearguard от другого actor для уже принятого Retreat.
