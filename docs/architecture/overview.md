# Архитектура

## Направление зависимостей

```text
CLI / JSON / future GUI
          |
          v
 application services
          |
          +---------> balance
          |              |
          v              v
       engine <----- simulation
          |
          v
        rules
          |
          v
        domain
```

Внешние слои знают о внутренних, но внутренние не импортируют адаптеры или пользовательские интерфейсы.

## Модели

Текущие `CombatantDefinition`, `CombatantState` и `AttackAction` относятся к прототипу P1 и не являются целевым контрактом книги. Они сохраняются только как материал миграции.

Целевая модель разделяет неизменяемое определение, состояние экземпляра, запрос элементарного разрешения и правила orchestration. Подробный контракт K1 описан в [`resolution-kernel.md`](resolution-kernel.md).

Будущий `BattleEngine` отвечает за цели, исполнение действий, объединение состояний и очередь follow-up. Первый независимый orchestration primitive уже задаёт раунды, постоянный порядок двух сторон, выбранный активный ход и проверенные action slots. Resolution kernel отвечает только за одну проверку или атаку и возвращает новое состояние, trace, события и последующие запросы.

`RandomSource` внедряется в движок. Стандартная реализация оборачивает `random.Random`, а тесты используют заданную последовательность результатов.

`BattleEvent` — структурированная запись уже произошедшего факта. На первом этапе события служат журналированию и проверке; они не являются универсальной мутирующей шиной правил.

Первый K1 spatial primitive использует неизменяемые `ZoneGraph`, `SpatialEntityPlacement` и `SpatialBattleState`. Граф хранит только книжное соседство Zones; неоднозначная позиция внутри Zone передаётся явным контекстом конкретной операции. Общий Give Ground executor меняет размещение и собственный round-scoped usage. Отдельная free-move boundary связывает spatial snapshot с активным actor/round: движение применяет Slow/Normal/Fast limit, а альтернативная ветвь снимает Prone с self/Close ally; обе делят один usage и не расходуют action slot. Difficult Terrain reducer пересекает одну границу до Athletics outcome, сохраняет общий turn-факт Test и на провале применяет Prone. Move Carefully переиспользует free-move route как action composite, обходит terrain Test, расходует free-move usage и опционально выполняет Awareness search. Move Quietly связывает stable observer priority, opposed Test и условный free move к явному hiding position; его narrow opportunity теперь одноразово исполняет подходящую unopposed Attack либо возвращает явную причину потери. Подробности: [`ADR-0003`](../decisions/ADR-0003-zone-graph-and-spatial-boundary.md).

`CombatRoundState` и `CombatTurnState` являются отдельным неизменяемым orchestration-срезом. Они проверяют порядок сторон и бюджет действий, но не владеют injury/spatial/magic state и не вызывают kernel автоматически. Зарезервированный `CombatActionSlot` разрешает отдельную фазу исполнения; только добавленный после успешного reducer `ActionExecutionReceipt` отмечает её завершение. Узкие adapters связывают обычный Attack slot с `KernelAttackRequest`, Aim — с Awareness и одноразовым next-ranged-Attack snapshot, Help — с собственным Test и привязанным к upcoming allied Test bonus, Recover — с Condition/magic transitions и typed treatment/mount/inventory follow-ups, spell Improvise — с одним `CastingTestRequest` и обязательной post-Test threshold/decision-фазой, Skill Improvise — с одним basic/opposed Test и optional GM-approved Condition application, Troll Vomit/Swamp Breath/Soporific Breath Ability Improvise — с одиночным либо Zone Endurance Hazard/Wound pipeline, Run — с отдельным `SpatialBattleState`, Medium/Long Charge — с атомарными spatial→attack/Test composite-переходами, Move Carefully — с terrain-aware free-move/search composite, а Move Quietly — с opposed-Test/conditional-hiding composite. Оба Breath adapter связывают Zone selection с актуальным spatial snapshot и требуют точного совпадения ordered targets со всеми placements выбранной Zone, не изменяя spatial state; Soporific Breath дополнительно проверяет Drained/Defenceless replacement после Wound. Skill-Improvise action result не владеет состоянием цели: отдельная application boundary принимает актуальные `ConditionState`/immunity snapshot, применяет только Prone/Distracted общим reducer и ведёт immutable consumed-ID snapshot до появления battle aggregate. Recover treatment также применяет созданный action-фазой follow-up отдельно: требует тот же injury snapshot, меняет одну Wound, удаляет только её `UNTIL_TREATED` effects и использует явный Condition-source snapshot, не создавая второй receipt. Провал Test внутри Long Charge, Move Quietly, Aim, Help, Recover или Skill Improvise является завершённым действием с собственным типизированным результатом. Добровольное прекращение уже активного Casting остаётся отдельным magic decision без нового action slot и переиспользует общую Miscast preparation. Подробности: [`ADR-0004`](../decisions/ADR-0004-round-turn-and-action-slots.md).

## Текущая граница

Текущий этап — K1, книжное ядро разрешения и минимальные typed orchestration boundaries без нового battle loop. Реализованный бой `1 на 1` является устаревшим P1; его интерфейсы не обязаны сохраняться. Порядок раундов/сторон, action budget, Aim, Help, Recover и application его успешного treatment, Skill Improvise и применение его Prone/Distracted follow-up, конкретные Ability Improvise Troll Vomit, Troll Hag Swamp Breath и Forest Dragon Soporific Breath, исполнение обычного и Move-Quietly-hidden Attack slot, обеих фаз Run, Medium/Long Charge, Move Carefully, Move Quietly, standalone Difficult Terrain traversal и его free-move/base-Run/Medium-Charge consumers, normal post-Casting путь, triggered Miscast preparation, добровольное прекращение Casting, общий skipped Casting Test для non-Casting action receipts и обе ветви free move уже выделены. End-of-battle automatic treatment, применение mount/inventory/spell/roll follow-ups, остальные Ability и attacking Skill Improvise, другие incidental actions, общий battle aggregate, завершение боя, Monte Carlo, сериализация, CLI и балансировщик относятся к следующим этапам.
