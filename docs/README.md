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
- [`audits/m3-readiness.md`](audits/m3-readiness.md) — закрытие четырёх критериев M3 и граница перехода к M4;
- [`audits/m4-readiness.md`](audits/m4-readiness.md) — Schema/service/CLI/examples, проверка установленного пакета и граница M5;
- [`audits/m5-readiness.md`](audits/m5-readiness.md) — четыре критерия первого M5, 69 tests, runnable пример и граница будущего JSON/CLI balance;
- [`audits/m5-external-readiness.md`](audits/m5-external-readiness.md) — закрытие JSON/CLI M5: матрица контракта, 52 external tests, installed parity и переход к M6;
- [`rule-traceability.md`](rule-traceability.md) — книга → правило → код → тест;
- [`contradictions.md`](contradictions.md) — расхождения и неоднозначности источника;
- [`architecture/overview.md`](architecture/overview.md) — слои, зависимости и основные модели;
- [`architecture/resolution-kernel.md`](architecture/resolution-kernel.md) — контракт и фазы книжного ядра K1;
- [`decisions/ADR-0012-npc-nearby-stagger.md`](decisions/ADR-0012-npc-nearby-stagger.md) — профильный Blunderbuss executor, вторичные цели, цепочка последствий и завершение nearby trigger;
- [`decisions/ADR-0013-ranged-minion-scenario-input.md`](decisions/ADR-0013-ranged-minion-scenario-input.md) — вход и исполнитель Minion-перестрелки, policies/facts, общий бюджет и terminal outcomes;
- [`decisions/ADR-0014-independent-ranged-simulations.md`](decisions/ADR-0014-independent-ranged-simulations.md) — последовательный M3, seed/index, независимые RNG и компактные агрегаты;
- [`decisions/ADR-0015-process-ranged-simulations.md`](decisions/ADR-0015-process-ranged-simulations.md) — опциональный M3 в spawn-процессах, ограниченная очередь пакетов, RNG и обработка ошибок;
- [`decisions/ADR-0016-ranged-simulation-json-v1.md`](decisions/ADR-0016-ranged-simulation-json-v1.md) — Schema/pure adapters JSON v1, application service, typed errors и CLI simulate;
- [`decisions/ADR-0017-ranged-candidate-assessment.md`](decisions/ADR-0017-ranged-candidate-assessment.md) — aggregate-only summary, single-candidate assessment и реализованный bounded M5 evaluator с бюджетом/top_k;
- [`decisions/ADR-0018-staged-ranged-evaluation.md`](decisions/ADR-0018-staged-ranged-evaluation.md) — реализованная поэтапная оценка: промежуточный отбор, повторные пакеты, бюджет и цепочка reports;
- [`decisions/ADR-0019-ranged-composition-generation.md`](decisions/ADR-0019-ranged-composition-generation.md) — реализованный генератор численности по явному резерву: profiles/context, составы, IDs, admission и бюджет;
- [`decisions/ADR-0020-ranged-balance-json-v1.md`](decisions/ADR-0020-ranged-balance-json-v1.md) — реализованный balance JSON/CLI: Schema/adapters/service, reserve/facts/window, источники/этапы и ошибки;
- [`decisions/ADR-0021-melee-minion-scenario.md`](decisions/ADR-0021-melee-minion-scenario.md) — Melee Minion-сценарий: typed admission, динамический outnumbering, реализованный исполнитель и source-bound result;
- [`decisions/ADR-0022-independent-melee-simulations.md`](decisions/ADR-0022-independent-melee-simulations.md) — реализованные независимые Melee-прогоны, seed scheme, compact result и aggregate-only summary;
- [`audits/m6-simulation-readiness.md`](audits/m6-simulation-readiness.md) — аудит массовой Melee-симуляции: seeds, summary, spawn, ошибки, измерения и граница будущего balance;
- [`decisions/ADR-0024-melee-candidate-assessment.md`](decisions/ADR-0024-melee-candidate-assessment.md) — реализованные Melee assessment, list models и application evaluator: точные доли/окно, source, бюджет, top_k, sequential/process и ошибки;
- [`decisions/ADR-0025-staged-melee-evaluation.md`](decisions/ADR-0025-staged-melee-evaluation.md) — реализованная поэтапная Melee-оценка: helper, модели этапов/бюджета/цепочки и application service/error; аудит и самостоятельный пример завершены;
- [`decisions/ADR-0023-process-melee-simulations.md`](decisions/ADR-0023-process-melee-simulations.md) — реализованный контракт опциональных Melee-прогонов в процессах: spawn, bounded queue, те же seed/result и ошибки;
- [`audits/m6-readiness.md`](audits/m6-readiness.md) — аудит одиночного Melee-сценария и требования к будущим независимым прогонам/summary;
- [`audits/m6-evaluation-readiness.md`](audits/m6-evaluation-readiness.md) — аудит ADR-0024: source/budget/selection/error boundaries и самостоятельный пример двух составов;
- [`examples/m6/README.md`](examples/m6/README.md) — production Melee-сценарий, оценка списка в sequential/process с сохранённым выводом и отдельные constructor probes;
- [`examples/m5/json/README.md`](examples/m5/json/README.md) — запуск CLI balance, JSON request/result и три категории ошибок;
- [`../src/towr/adapters/schemas/`](../src/towr/adapters/schemas/) — packaged JSON Schema request/result/error Draft 2020-12;
- [`examples/m4/README.md`](examples/m4/README.md) — примерные JSON request/result, проверенные через существующие typed APIs;
- [`examples/m5/README.md`](examples/m5/README.md) — typed Python пример generation → staged evaluation, оба backend и сохранённый текстовый отчёт;
- [`decisions/`](decisions/) — журнал архитектурных решений;
- [`decisions/ADR-0011-bounded-minion-rounds.md`](decisions/ADR-0011-bounded-minion-rounds.md) — ограниченный прогон Minion-раундов, лимит, snapshots и остановки;
- [`decisions/ADR-0010-single-minion-round.md`](decisions/ADR-0010-single-minion-round.md) — ограниченная координация одного Minion-раунда, остановки и возобновление;
- [`decisions/ADR-0009-npc-attack-selection-policy.md`](decisions/ADR-0009-npc-attack-selection-policy.md) — выбор NPC Attack/цели по явному порядку и проверка актуальности;
- [`decisions/ADR-0008-npc-roster-boundary.md`](decisions/ADR-0008-npc-roster-boundary.md) — контракт состава NPC M2, проекции в K1 и явные ограничения;
- [`roadmap.md`](roadmap.md) — последовательность этапов;
- [`project-status.md`](project-status.md) — актуальное состояние и следующий шаг;
- [`open-questions.md`](open-questions.md) — вопросы, требующие решения владельца правил;
- [`benchmarks/README.md`](benchmarks/README.md) — воспроизводимые M3/M6 benchmarks: baseline, оптимизация continuation и сравнение sequential/spawn;
- [`testing.md`](testing.md) — стратегия и команды проверки;
- [`TOWR_Combat_Simulator_&_Encounter_Balancer_—_Context_and_Technical.md`](TOWR_Combat_Simulator_&_Encounter_Balancer_—_Context_and_Technical.md) — исходный полный дизайн-док.

Обе книги являются главными источниками игровых правил. Нормализованные правила из них размещаются в `rules/`. `game-rules.md`, исходный дизайн-док, код и тесты текущего прототипа подчинены книгам и будут пересмотрены.

[Аудит staged Melee evaluation](audits/m6-staged-evaluation-readiness.md) — матрица ADR-0025, полный бюджет повторных пакетов, source/error boundaries и проверенный [самостоятельный пример](examples/m6/melee_staged_evaluation.py). [ADR-0026](decisions/ADR-0026-melee-composition-generation.md) фиксирует контракт генерации из явного резерва; [конечный probe](examples/m6/generation_contract_probe.py) проверен. [Group/request preflight](../src/towr/application/melee_candidate_generation_models.py) реализован и покрыт [13 tests](../tests/unit/test_m6_melee_candidate_generation_models.py). [Генератор](../src/towr/application/melee_candidate_generation.py), result/error реализованы и покрыты [14 tests](../tests/unit/test_m6_melee_candidate_generation.py). [5 integration tests](../tests/integration/test_m6_melee_candidate_generation.py) проверяют реальные sequential/process reports, повтор/rename prefix и динамический outnumbering на generated scenarios. [Аудит генерации](audits/m6-generation-readiness.md) завершён; [production-пример](examples/m6/melee_balance.py) и [вывод](examples/m6/melee_balance.output.txt) проверены. [Контракт JSON/CLI ADR-0027](decisions/ADR-0027-melee-json-cli-v1.md) и [конечные примеры](examples/m6/json/README.md) подготовлены. Melee simulation Schema/command и pure adapters реализованы. Simulation service/error encoder и simulate-melee реализованы; balance Schema/models и pure adapters также реализованы; balance service/errors/error encoder и balance-melee также реализованы; [Общий аудит Melee JSON/CLI](audits/m6-external-readiness.md) завершён; ADR-0027 закрыт в текущей границе numeric Minions.

[M7 / ADR-0028](decisions/ADR-0028-mixed-minion-scenario.md) — контракт смешанного неподвижного Minion-боя, явные pair ranges и техническая остановка без доступной цели. [Probe](examples/m7/README.md) проверен через public K1/M2 APIs; typed admission реализован: четыре immutable модели и 25 tests; provider/result/runner также реализованы (34 новых tests). Далее аудит одиночного mixed-сценария.
