# Документация проекта

Документы разделены по назначению, чтобы следующая рабочая сессия могла восстановить контекст без истории чата.

- [`source-policy.md`](source-policy.md) — иерархия источников и порядок разрешения расхождений;
- [`source-index.md`](source-index.md) — реестр книг, редакций, глав и состояния разбора;
- [`audits/rulebooks-1.4-1.1.md`](audits/rulebooks-1.4-1.1.md) — постраничный журнал полного аудита Player’s Guide 1.4 и Gamemaster’s Guide 1.1;
- [`rules/`](rules/) — нормализованные правила, извлечённые из книги и согласованные с пользователем;
- [`lore/`](lore/) — отделённый от механики контекст мира;
- [`game-rules.md`](game-rules.md) — правила существующего упрощённого прототипа;
- [`audits/k1-readiness.md`](audits/k1-readiness.md) — матрица готовности K1, критерии перехода к M2 и следующий implementation-срез;
- [`audits/m2-readiness.md`](audits/m2-readiness.md) — пять пунктов M2, фактические границы, остаток перед M3 и следующий срез;
- [`rule-traceability.md`](rule-traceability.md) — книга → правило → код → тест;
- [`contradictions.md`](contradictions.md) — расхождения и неоднозначности источника;
- [`architecture/overview.md`](architecture/overview.md) — слои, зависимости и основные модели;
- [`architecture/resolution-kernel.md`](architecture/resolution-kernel.md) — контракт и фазы книжного ядра K1;
- [`decisions/ADR-0012-npc-nearby-stagger.md`](decisions/ADR-0012-npc-nearby-stagger.md) — профильный Blunderbuss executor, вторичные цели, цепочка последствий и завершение nearby trigger;
- [`decisions/ADR-0013-ranged-minion-scenario-input.md`](decisions/ADR-0013-ranged-minion-scenario-input.md) — вход и исполнитель Minion-перестрелки, policies/facts, общий бюджет и terminal outcomes;
- [`decisions/ADR-0014-independent-ranged-simulations.md`](decisions/ADR-0014-independent-ranged-simulations.md) — последовательный M3, seed/index, независимые RNG и компактные агрегаты;
- [`decisions/`](decisions/) — журнал архитектурных решений;
- [`decisions/ADR-0011-bounded-minion-rounds.md`](decisions/ADR-0011-bounded-minion-rounds.md) — ограниченный прогон Minion-раундов, лимит, snapshots и остановки;
- [`decisions/ADR-0010-single-minion-round.md`](decisions/ADR-0010-single-minion-round.md) — ограниченная координация одного Minion-раунда, остановки и возобновление;
- [`decisions/ADR-0009-npc-attack-selection-policy.md`](decisions/ADR-0009-npc-attack-selection-policy.md) — выбор NPC Attack/цели по явному порядку и проверка актуальности;
- [`decisions/ADR-0008-npc-roster-boundary.md`](decisions/ADR-0008-npc-roster-boundary.md) — контракт состава NPC M2, проекции в K1 и явные ограничения;
- [`roadmap.md`](roadmap.md) — последовательность этапов;
- [`project-status.md`](project-status.md) — актуальное состояние и следующий шаг;
- [`open-questions.md`](open-questions.md) — вопросы, требующие решения владельца правил;
- [`benchmarks/README.md`](benchmarks/README.md) — воспроизводимый M3 benchmark, baseline времени/памяти и следующий performance-срез;
- [`testing.md`](testing.md) — стратегия и команды проверки;
- [`TOWR_Combat_Simulator_&_Encounter_Balancer_—_Context_and_Technical.md`](TOWR_Combat_Simulator_&_Encounter_Balancer_—_Context_and_Technical.md) — исходный полный дизайн-док.

Обе книги являются главными источниками игровых правил. Нормализованные правила из них размещаются в `rules/`. `game-rules.md`, исходный дизайн-док, код и тесты текущего прототипа подчинены книгам и будут пересмотрены.
