# ADR-0013: вход и исполнение неподвижного ranged Minion-сценария

Статус: принято, 2026-09-28.

## Основание

[Повторный аудит M2](../audits/m2-readiness.md) показал, что compositional round API принимает состояния, для которых не исполняет все обязательные эффекты. В частности, Ablaze требует end-turn Endurance против Hazard (2), но обычный NPC round не выполняет этот Test. Для первого автономного сценария нужна проверяемая узкая граница входа. Расширять все Conditions и каталог NPC для этого не требуется.

Непосредственно проверены BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112; The Battlefield / Range, стр. 114; Battlefield Features, стр. 115; Attack Tests, стр. 118; Conditions / Ablaze, стр. 122; Staggered, стр. 123; BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91; Understanding NPC Profiles, стр. 93; Brigands & Footpads / Brigand, стр. 97. Книги определяют Attack/Protection, диапазоны, повторный Staggered и поражение Minion. Приоритеты целей, неподвижность, выбор допустимого Wound и бюджет — решения сценария, не новые house rules.

## Контракт

`domain/npc_ranged_scenario_models.py` содержит три frozen dataclass. Их конструкторы выполняют preflight без RNG и исполнения правил. Отдельный одноимённый validator или дублирующий result не вводится: успешно построенный `NpcRangedScenario` является проверенным входом. Неверные типы дают TypeError, неподдержанные/несогласованные значения — ValueError.

`NpcRangedScenario(initial, facts, actor_policies, repeated_stagger_choice, perspective_side, objective)` связывает:

- существующий `NpcRoundsRequest`: полный исходный round/roster/spatial, actor order, side order и положительный `max_rounds`;
- явные `NpcRangedScenarioFacts` для всех вражеских пар на протяжении сценария;
- ровно одну `NpcRangedActorPolicy` для каждого actor;
- только `StaggerChoice.SUFFER_WOUND` при повторном Staggered;
- явную `CombatSide` и `NpcDefeatObjective`, содержащую всех исходных противников этой стороны и никого другого.

Первый раунд имеет номер 1, без активного/завершённых/исключённых ходов, pending, execution histories и weapon bindings. Все participants roster входят в round; placements содержат ровно тот же набор с теми же сторонами, без использования движения/Give Ground/Difficult Terrain. Fresh-state checks запрещают передать continuation как новый исходный сценарий. Они не защищают от отката всех внешних snapshots.

## Поддержанный профиль и факты

Каждый участник — здоровый Minion без начальных Wounds/Conditions. Разрешён ровно один numeric Shooting profile с optimum Medium–Long, 2H, обычным Damage multiplier 1, без armour-ignore, secondary effects или дополнительного pool cap. Он доступен, оружие присутствует, щита нет, текущая Resilience совпадает с определением. Protection — ровно один Athletics profile без дополнительного pool cap. Числовые dice/threshold/base Damage/Resilience остаются supplied значениями; имя или ID оружия не создают свойств. Fixture использует numeric Warbow/Protection Brigand со стр. 97, не полный каталог Brigand/Craven Opportunist.

Обязательные facts не имеют defaults: Medium Range для каждой вражеской пары, нет врага в Close, все цели осведомлены и видимы, позиция постоянна, Tests не требуют дополнительных modifiers, иных применимых правил нет, боеприпасов достаточно для бюджета, отдельный Reload action не нужен. `requires_reload_action=False` не запрещает обычное заряжание лука как часть Attack. Caller отвечает за полноту этих утверждений: в numeric definition нет полного перечня Abilities, а Zone graph не доказывает awareness, видимость, наличие стрел или укрытий.

Для каждой вражеской пары placements должны находиться в соседних Zones, что согласует supplied Medium со стр. 114. Это узкая проверка факта, не автоматический расчёт дальности/линии видимости. У графа могут быть другие незанятые Zones. Один участник на стороне допустим; размер состава не ограничен fixture 2×2.

## Явные решения

`NpcRangedActorPolicy(actor_id, target_actor_ids, defeat_decisions)` хранит приоритеты всех противников ровно по одному разу и столько же полных `MinionDefeatDecision` в том же порядке. Каждый decision принадлежит этому attacker/target и требует `gm_approved=True`. Все три существующих disposition допустимы. Это заранее явно переданные решения, не автоматически полученное согласие GM. Unknown/friendly/missing/duplicate targets или отсутствующее одобрение отклоняются. `policy_for(actor_id)` возвращает сохранённую policy; неизвестный actor даёт отказ.

Исполнитель выбирает первую ещё не побеждённую цель из этого порядка. Общий выбор повторного Staggered — получить Wound — оставляет только Staggered/defeat в замкнутом наборе последствий; Give Ground/Prone/Broken эта policy не порождает. Исходные Conditions всё равно запрещены, включая Staggered. Решение не ограничивает низкоуровневые APIs для других заявленных сценариев.

## Бюджет и границы исполнения

`initial.max_rounds` обозначает бюджет всего нового сценария. Bounded runner сохраняет прежнюю семантику одного вызова; scenario coordinator вызывает его с `max_rounds=1` и сам проверяет глобальный номер раунда до каждого advance. Продолжение того же раунда после defeat не расходует ещё один раунд и не сбрасывает бюджет.

Этот сценарий не добавляет автоматическую post-battle recovery, Monte Carlo или общий battle aggregate. Его результат фиксирует момент после последствий последней атаки; оставшийся active turn/незавершённый раунд не объявляется завершённым. BOOK-PLAYER-GUIDE 1.4, Rules / Recover, стр. 118 связывает automatic Recover с возможностью перевести дух; такой факт здесь не задаётся. Низкоуровневый run_npc_round остаётся compositional API. Blunderbuss доступен отдельно, его reload/secondary policies не входят в этот автономный сценарий.

## Исполнитель и исход сценария

`engine/npc_ranged_scenario_runner.py`: `run_npc_ranged_scenario(scenario, rng)` принимает только NpcRangedScenario и внедряемый RandomSource. Private candidate provider передаёт surviving targets по сохранённому порядку и unmodified Shooting/Athletics Tests. Pure projection `ranged_scenario_candidates` используется также при проверке итогового журнала. Decision provider выполняет явно заданный SUFFER_WOUND; иных специальных Test/character/Monstrosity решений допущенный вход не требует. Никаких глобальных RNG или Monte Carlo внутри нет.

Один проход вызывает existing run_npc_rounds для остатка текущего раунда. Pending Minion defeat связывается с полной последней Attack; существующие acknowledgement/application записывают соответствующий supplied decision. Ещё не походившая цель исключается existing exclusion consumer. Уже завершивший ход участник сохраняется в completed history до следующего состава; повторное исключение не производится.

Если после этих последствий осталась одна действующая сторона, возвращается terminal result немедленно: следующий actor/round не запускается. Иначе runner возобновляет этот же раунд без повторения Attack. После завершения раунда сначала проверяется общий бюджет; при оставшемся бюджете advance получает всех живых участников и исходный actor order, отфильтрованный по ним. Side order постоянен. Каждый resume погашает новое defeat, каждый advance увеличивает round number: цикл ограничен бюджетом и числом участников.

`NpcRangedScenarioResult(source_scenario, runner_report, terminal_acknowledgement=None, terminal_exclusion=None)` хранит immutable полные источники. `runner_report` — существующий NpcRoundsChainSummary с настоящим runner result на обоих концах. При terminal defeat он заканчивается на pending; отдельный terminal suffix содержит ровно последнее подтверждение и, когда необходимо, исключение. Проверяются exact snapshot/full Attack, supplied GM decision и соответствие target. Объект не фабрикует пустой runner result ради старого ограничения отчёта.

`current` возвращает состояние **после** terminal suffix. `defeat_acknowledgements` объединяет обычные и последнее подтверждения ровно один раз. Число Attack и посещённых/завершённых раундов берётся из runner_report: suffix не исполняет действия и не завершает раунд. `runner_report.current/pending` описывает именно последний вызов runner; для итогового состояния следует использовать `result.current`. Полные решения не восстанавливаются из consumed IDs.

`outcome` вычисляется по итоговому состоянию и источникам:

- OBJECTIVE_ACHIEVED: все противники выбранной стороны побеждены, последствия погашены;
- SIDE_DEFEATED: побеждены все участники выбранной стороны, последствия погашены;
- ROUND_LIMIT: обе стороны ещё действуют, последний допустимый раунд завершён;
- UNSUPPORTED_PATH: runner остановился на неподдержанном пути, с сохранённой диагностикой/очередью.

Неподдержанный исход не является поражением или ничьёй. Неправильный input отклоняется preflight до RNG; неожиданные ошибки executor/RNG не перехватываются как игровые исходы. Конструктор результата проверяет начальный source, общий лимит, target/candidate/Staggered policies, все GM decisions, следующий состав/порядок и отсутствие runner/advance после terminal defeat. Недостающий supported defeat acknowledgement, чужой terminal suffix или преждевременная остановка на лимите одного вызова отклоняются. Source checks не защищают от полного отката всех snapshots и не являются криптографическим доказательством происхождения бросков.

## Проверки

12 unit tests в [test_m2_npc_ranged_scenario.py](../../tests/unit/test_m2_npc_ranged_scenario.py): 1×1/2×2/3×2, оба порядка сторон, все dispositions, сохранение immutable sources/порядка, полный набор начальных Conditions, unsupported profiles/types/effects, equipment, spatial consistency, incomplete decisions/objectives, used state, типы и бюджет.

3 integration tests входного среза в [test_m2_npc_ranged_scenario_preflight.py](../../tests/integration/test_m2_npc_ranged_scenario_preflight.py): valid input передаётся existing round через test-only provider, восемь сочетаний miss/first Staggered/repeated Staggered/Wound и порядка сторон, точные execution/RNG counts, refusal continuation; отдельные Ablaze/weapon-bound inputs отклоняются до round/RNG. На этом первоначальном срезе provider/terminal loop ещё отсутствовали; полный набор тогда: **1751 tests OK**, Python 3.14.

Исполнитель: [10 unit tests](../../tests/unit/test_m2_npc_ranged_scenario_runner.py) и [8 integration tests](../../tests/integration/test_m2_npc_ranged_scenario_cycle.py). Проверены terminal на первом/последующем выстреле, уже походившая цель, все dispositions, обе стороны, explicit reordered priorities, повторный Staggered между раундами, budget 1/2/3 через resume, исключительно промахи, 20 повторяемых seed-прогонов без статистических порогов. Sources/decision/candidate substitution и post-terminal observation отклоняются; RNG и количество исполнений проверены. Полный набор **1769 tests OK**, Python 3.14. Предыдущая проверка 1751 относится только к входному контракту.
