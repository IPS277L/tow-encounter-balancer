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

Первый K1 spatial primitive использует неизменяемые `ZoneGraph`, `SpatialEntityPlacement` и `SpatialBattleState`. Граф хранит только книжное соседство Zones; неоднозначная позиция внутри Zone передаётся явным контекстом конкретной операции. Общий Give Ground executor меняет размещение и собственный round-scoped usage. Отдельная free-move boundary связывает spatial snapshot с активным actor/round: движение применяет Slow/Normal/Fast limit, а альтернативная ветвь снимает Prone с self/Close ally; обе делят один usage и не расходуют action slot. Подробности: [`ADR-0003`](../decisions/ADR-0003-zone-graph-and-spatial-boundary.md).

`CombatRoundState` и `CombatTurnState` являются отдельным неизменяемым orchestration-срезом. Они проверяют порядок сторон и бюджет действий, но не владеют injury/spatial/magic state и не вызывают kernel автоматически. Зарезервированный `CombatActionSlot` разрешает отдельную фазу исполнения; только добавленный после успешного reducer `ActionExecutionReceipt` отмечает её завершение. Узкие adapters связывают обычный Attack slot с `KernelAttackRequest`, а spell Improvise — с одним `CastingTestRequest` и обязательной post-Test threshold/decision-фазой, не сливая turn, injury и magic state. Добровольное прекращение уже активного Casting остаётся отдельным magic decision без нового action slot и переиспользует общую Miscast preparation. Подробности: [`ADR-0004`](../decisions/ADR-0004-round-turn-and-action-slots.md).

## Текущая граница

Текущий этап — K1, книжное ядро разрешения и минимальные typed orchestration boundaries без нового battle loop. Реализованный бой `1 на 1` является устаревшим P1; его интерфейсы не обязаны сохраняться. Порядок раундов/сторон, action budget, исполнение обычного Attack slot, normal post-Casting путь, triggered Miscast preparation, добровольное прекращение Casting, skipped Casting Test после Attack и обе ветви free move уже выделены. Исполнение подготовленных spell/roll follow-ups, остальные interrupted/actions, другие incidental actions, Manoeuvre, spatial target discovery, общий battle aggregate, завершение боя, Monte Carlo, сериализация, CLI и балансировщик относятся к следующим этапам.
