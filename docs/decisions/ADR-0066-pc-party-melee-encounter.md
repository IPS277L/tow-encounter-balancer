# ADR-0066: общий бой группы PC против Minions

Дата: 2026-11-04. Статус: **M10 реализована и проверена в указанной границе**.

## Решение и граница

После завершённой M9 пользователь поручил продолжить рекомендованное направление — группу персонажей игроков против Minions. Расширяем существующую PC melee family: один и тот же owner и pipeline обслуживают непустую группу, включая один PC. Не запускаем последовательность независимых дуэлей и не создаём вторую почти одинаковую family.

PG1.4, Rules / Combat112: сначала полные ходы PC и союзников, затем противников. Фиксированный caller-selected порядок обеих сторон остаётся ограниченной стратегией; книга разрешает менять его между раундами. PG1.4, Rules / Attack Tests118–119: outnumbering учитывает живых, не Defenceless участников всей Zone с обеих сторон; GM может удержать бонус. Все участники этой замкнутой сцены находятся в одной Zone. Новых правил ран/Fate не вводим: действуют источники и границы [ADR-0065](ADR-0065-first-pc-melee-encounter.md), Common Wounds1–10, lethal24+ после Near Miss decline;11–23 дают точный pending stop.

Uniform `party` содержит отдельные Characteristics/Skills, оружие, Fate snapshot, policies и priority целей каждого PC. Нет привилегированного главного героя. Один общий clock, индивидуальные injury/daily/weapon/expiry histories. Каждый Minion атакует первую живую цель из общего явно supplied `enemy_target_priority`; каждый PC — первую живую цель собственного списка. Recover поддерживает только self, без помощи и лечения. После смерти PC исключается из следующих действий и outnumbering; его смерть не завершает бой, пока жив другой PC. Обязательные последствия текущей атаки закрываются прежде следующего действия или результата.

Исходы: `objective_achieved` (все Minions побеждены), `party_defeated` (все PC погибли), `round_limit`, `unsupported_path`. Unsupported сохраняет PC-владельца и actual pending source, остаётся в знаменателе и запрещает selection кандидата. Дополнительно сохраняем подтверждённые потери: ordered IDs погибших PC в trial, число trials хотя бы с одной подтверждённой смертью и per-PC counts в summary. Это наблюдения до фактической остановки, а не прогноз судьбы оставшихся при unsupported/limit. Все rates используют полный trials denominator.

## Интерфейсы и владение

- `PcMeleeParticipant(actor_id, pc, fate, policy, fate_policy, random_hand_policy, initial_weapon_hand, target_priority, defeat_decisions)`.
- `PcMeleeScenario(id, party, day_id, enemies, facts, pc_activation_order, enemy_activation_order, enemy_target_priority, max_rounds)`; непустая party и enemies, уникальные actor IDs, каждый порядок — точная полная partition соответствующей стороны, решения defeat привязаны к своему атакующему.
- `PcMeleeParticipantState(actor_id, injury, weapon_hand, fate, daily_wounds, timed_wounds)`; `PcMeleeState` содержит ordered party, enemies, clock и общий journal/mandatory queue с явным PC-владельцем.
- Count search фиксирует всю party, меняет только bounded Minion prefixes и фильтрует enemy priority/defeat decisions каждого PC; party order и enemy target priority неизменны.

Существующие `simulate-pc-melee` / `balance-pc-melee` и текущий JSON1 изменяются вместе с моделями, схемами и примерами. Старый одиночный wire shape не принимается; converter, alias или deprecated-период не нужны. Magic JSON6 и остальные families не меняются. RNG namespace PC trials остаётся прежним: одинаковые master seed/index означают одинаковый независимый поток, а не обещание прежнего исхода при новом составе.

## Конечная приёмка

1. Строгий полный preflight до RNG: все PC/Fate/policies, actor/order partitions, per-PC decisions, canonical types и источник.
2. Общий source-bound бой: разные PC, обе стороны outnumbering, retarget после смерти, исключение умершего, продолжение оставшимися, отдельные Fate/daily/expiry/оружие, Wounds1–10 и pending stop с владельцем. Replay/forged/missing prefix отклоняются.
3. Independent sequential/process trials и party-loss accounting; fixed-party generation и aggregate-only selection, бюджеты и denominator сохранены.
4. Один актуальный JSON1/CLI, strict closed schemas/offline refs, runnable party simulation/balance examples, удалённый старый wire shape.

Адресная проверка: вся PC melee подсистема и затронутые общий CLI/schema paths; один репрезентативный real spawn. Полный regression нужен только при выявленном риске за пределами PC subsystem; wheel не требуется, поскольку discovery/resources/entry points не меняются. Успешные дорогие проверки не повторяем без причины.

## Реализация и фактическая проверка

Контракт реализован через существующие PC domain/runner, trials/summary, count search и JSON1/CLI. Добавлены [13 party execution guards](../../tests/unit/test_m10_pc_party_execution.py), [4 проверки статистики/проекции](../../tests/unit/test_m10_pc_party_statistics.py) и [3 сквозных party tests](../../tests/integration/test_m10_pc_party_simulation.py); прежние уникальные одиночные проверки перенесены на party из одного PC. [Wire tests](../../tests/unit/test_m9_pc_melee_json.py) и [schemas](../../tests/unit/test_m9_pc_melee_json_schemas.py) дополнены multi-PC cases. Исходы/журналы прежнего одиночного примера при тех же входных игровых данных и seeds сохранены; актуальные отчёты добавляют новые поля и название `party_defeated`.

Проверка закрыта **составно, 190 уникальных адресных IDs**, без утверждения единого зелёного full run:

- В `.cache/m10-subsystem.log`:188 tests за39.457s;182 успешны. Пять errors вызваны Windows sandbox `PermissionError/WinError5` на process pipes/temp cwd, один CLI process failure возник в той же среде.
- Только эти6 cases повторены с разрешённым запуском вне sandbox: **6 OK/16.576s**, `.cache/m10-process-recheck.log`. Подтверждены single/party real spawn, worker error context, aggregate-only balance и module/console/external cwd.
- После адресного усиления recorded source/history guards: **36 OK/2.353s**, включая2 новых регрессии; `.cache/m10-source-binding-recheck.log`. Один зависимый party real spawn отдельно повторён: **1 OK/1.616s**, `.cache/m10-final-party-spawn.log`. Успешная дорогая CLI-матрица повторно не запускалась.
- Ранее при интеграции:27 pure simulation/balance/statistics tests OK/0.115s;40 model/engine/battle/casualty aggregate tests OK/0.850s;22 wire/schema tests OK/2.040s. Финальные адресные наборы выше включают эти IDs.

Read-only review выявил и закрыл два типа пробелов: loss union bounds должны учитывать trials с подтверждёнными потерями, а не весь denominator; отдельно скопированный recorded source/state не может скрыть equal-but-wrong-type leaf в старом proof. Сравнение типов с уже проверенным canonical prefix не переигрывает прошлые Tests/RNG. Сохранены source-bound обязательные продолжения и полный prefix; перенос чужого PC, replay и пропуск шага отклоняются.

Четыре public requests M9/M10 выполнены реальными CLI; полные request echo проверены и результаты сохранены. [M10 simulation](../examples/m10/pc-melee-simulation.result.json):14 objective/2 unsupported из16, подтверждённых смертей0. [M10 balance](../examples/m10/pc-melee-balance.result.json):3 состава ×16trials, все16objective в каждом, counts1затем2 выбраны по стабильному порядку при равной дистанции от target. Это наблюдения конкретных inputs/seeds, не фиксированные вероятности. Истинные потери подтверждены отдельным scripted боем: pc1 погибает после трёх завершённых Wounds, Minion4 переключается на pc2, выживший продолжает следующий раунд; aggregate сохраняет1 casualty при round limit, без party defeat.

В PC bundle остаются7 schemas/90 offline refs; полная локальная schema registry проверена ближайшими shared tests. CLI help отражает party. Full regression проекта и wheel/install не повторялись: общий K1 и механизм поставки не менялись. Более тяжёлые Wounds/Brutes/Champions/active Fate/ally Recover/campaign остаются отдельным scope.
