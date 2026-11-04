# ADR-0065: первый книжный PC-сценарий ближнего боя

Дата: 2026-11-04. Статус: **M9 реализована и проверена в указанной ограниченной границе**. Направление и поддержка Wounds1–10 выбраны пользователем; source regression и installed delivery завершены.

Интерфейс одиночного PC ниже описывает историческую границу M9. [ADR-0066](ADR-0066-pc-party-melee-encounter.md) заменяет его uniform party в той же текущей JSON1 family, без legacy converter. Игровые границы Wounds/Fate сохраняются; нынешние примеры используют обновлённый формат.

## Задача и источники

Исходная цель — оценивать бои игроков с монстрами. M2–M8 исполняют NPC; `CombatantDefinition` P1 с `wound_limit` не является книжной моделью PC. M9 вводит один ограниченный бой PC с Minions и доводит его до независимых прогонов, подбора численности и JSON/CLI. Diagnostics M8 остаётся отдельным backlog.

Адресно прочитаны локальные извлечения выбранной BOOK-PLAYER-GUIDE1.4:

| Глава / страницы | Основание |
|---|---|
| Abilities / Characteristics & Skills68–69, Rules106–109 | Weapon Skill+Melee/Defence, Agility+Athletics, Toughness+Endurance; cap2×Characteristic, качества Test |
| Rules / Fate111–112 | Необязательные spends/burns, Glorious, Unmitigated Success, second action, Retreat, Near Miss и Last Stand; исчерпанные spends не запрещают burn |
| Rules / Combat112, Attack118–119 | Стороны/полные ходы, opposed Attack, Damage, Toughness/Resilience, dynamic outnumbering и повторный Staggered |
| Equipment / Melee Weapons92–93 | Одноручные Staff/Sword, Damage Strength; Sword даёт +1d Defence при отсутствии Staggered |
| Rules / Recover118, Wounds121, Conditions122–123 | Recover, PLAYER Wounds Table, источники Conditions и их снятие |
| Appendix / Wounds Table190–191 | Непосредственные последствия1–10, временные effects,24+ death |

Повторное полное чтение книг не заявляется. Каноническая математика и lifecycle берутся из K1, не переписываются по прототипу.

## Вход и конечная граница

Ровно один немагический PC стороны PLAYERS_AND_ALLIES, против непустого numeric Minion reserve стороны OPPOSITION. Начальное тело PC и Minions здоровое, без Conditions/Wounds/external effects; начальный Wound/daily журнал пуст. Перенос прежних ран/дневных receipts из campaign в этот fresh input не поддержан, в отличие от явно supplied Fate session. Один обычный Attack за ход; стороны идут по книжному порядку без ambush. Одна явно замкнутая сцена/Zone с известным Close, awareness и полным составом; без движения между Zones, mounts, Help, Charges, Talents, spells и внешних изменений. Порядок Minions и priority целей PC заданы caller. GM явно подтверждает либо удерживает outnumbering bonus. Исходы: objective achieved, PC defeated, round limit, unsupported — раздельно.

PC хранит самостоятельный definition с Weapon Skill, Strength, Toughness, Agility и Melee/Defence/Athletics/Endurance; используемые TestProfiles строятся из этих значений. Поддержаны одноручные Staff и Sword, один явно указанный занятый hand и пустая другая рука; числовой armour Resilience bonus задан явно. Нет общего inventory: хранится только состояние этого оружия в руке/на земле в той же Zone. Sword trait обязателен; PC не превращается в numeric NPC. Minion definition/snapshot переиспользуется при строгом допуске одного обычного Melee profile без новых Traits/Abilities; InlineProfile.pool_cap только None, без неподтверждённого custom pool origin. Wire сохраняет это поле явно и не стирает недопущенное значение.

Обязательные caller-selected policies, без default:

- `ATTACK_OR_RECOVER_SELF`: PC атакует первую живую цель из priority, либо выполняет STANDARD Recover, если нужно снять Prone/поднять собственное оружие. Recover исполняет все положенные стандартные выгоды, но не лечит раны; ongoing Conditions сохраняются. Пока оружие на земле, Protection использует Athletics вместо недоступной Defence. Minions атакуют единственного PC.
- `DECLINE_OPTIONAL_FATE`: PC явно не выбирает spends/burns и дополнительные действия во всех применимых окнах. Это стратегия, не отмена правил Fate. Полный supplied FateSessionState сохраняется неизменным, не обнуляется и не обновляется между боями. Lucky и дополнительные действующие Abilities в этот срез не входят.
- При повторном Staggered выбирается `SUFFER_WOUND`. Не утверждается, что Give Ground/Prone недоступны по книге: это явный выбор стратегии, поэтому движение не требуется.
- Random hand: явно выбранный GM-протокол одного d10,1–5 left /6–10 right, при каждом действительном требовании random hand. Пустая выбранная рука не подменяется занятой. Это способ исполнения случайного выбора, не изменение последствия таблицы.

Wounds1–10 исполняются и допускают дальнейший бой:1–3 superficial;4 Endurance/drop;5 Endurance/Prone;6 Drained expiry;7 Endurance/Blinded expiry;8 drop/CANNOT_AIM;9 Prone/difficult movement;10 next Test Grim/ongoing Drained. Сохраняются повторные источники и последовательность mandatory Tests; Grim погашается фактически следующим Test, включая Endurance. Неприменимость движения/Aim не стирает corresponding restriction. Вне этой таблицы — точный stop на actual pending PLAYER lifecycle до completion/daily/effects; unresolved окно/источник сохраняются. Исключение — поддержанная lethal24+ Wound, обязательно завершённая после выбранного отказа Near Miss. Нельзя превратить Defenceless/потерю оружия/достигнутый лимит в выдуманную смерть.

Каждый PLAYER Wound сначала получает actual pending lifecycle roll. Выбранный отказ Near Miss связывается с текущим PC/policy/source до daily registration/effect application. Только после completion и closure возможен terminal death; сырой `dead=True` на roll не завершает бой раньше этого окна. Glorious/Unmitigated отказ связывается с PC Test; Last Stand/second action/Retreat не расходуют ресурс автоматически. Профиль с rating>0 и исчерпанными session spends остаётся полноценным проверяемым случаем, а не заменяется рейтингом0.

Достижимость next-Test Grim: правило охватывает любую следующую Test, но в native M9 новая ordinary Wound требует предварительной PC Protection. Поэтому после10 до новой Wound/её Endurance сначала встретится PC Attack либо Protection; цепь «новая5, Endurance — первый Test после10» без внешнего/secondary источника в данном сценарии не заявляется. Проверяется actual consumption на Attack/Protection, а не выдуманная native chronology.

## Владение и интерфейсы

Выбран отдельный bounded PC owner, а не расширение `NpcDefinition` значением PLAYER и не общий rules DSL. Он хранит PC definition/state, Fate/daily history, ordered Minion snapshots, один общий `CombatRoundState`, состояние оружия и pending/effect/expiry histories. NPC APIs M2–M8 сохраняют прежнюю ответственность. K1 Attack/Protection/Test/turn/Wound/Recover reducers переиспользуются; новые adapters связывают полный источник с этим owner.

- `domain/pc_melee_models.py`: `PcMeleeDefinition`, `PcMeleeWeapon`, `PcMeleeFacts`, `PcMeleePolicy`, `PcFatePolicy`, `PcRandomHandPolicy`, `PcWeaponHand`, `PcMeleeScenario` — immutable preflight, без RNG/исполнения.
- `domain/pc_melee_result_models.py`: typed owner, source-bound шаги/результат, pending stop и четыре исхода. Полная цепь связывает соседние состояния, actual Test/Attack/lifecycle/receipt и выбранные policies. Скалярные счётчики не заменяют историю и не дают права исполнять forged/stale result.
- `engine/pc_melee_runner.py::run_pc_melee_scenario(scenario,rng)`: один непрерывный бой через K1 с source-bound результатом, без JSON/balance и глобального RNG.
- `simulation/pc_melee_*`: независимые indexed-seed trials, compact records/aggregates и process parity; только aggregate summary передаётся балансировщику.
- Application/balance: фиксированный PC, bounded counts supplied Minion groups, exact источник/бюджет/порядок; observed unsupported исключает кандидата, знаменатель не фильтруется.
- Новая отдельная current family JSON1 и команды `simulate-pc-melee`/`balance-pc-melee`; Magic остаётся current6. Не создавать compatibility converter или универсальный battle JSON до появления потребности.

Первый source interface для параллельной работы фиксирован: `PcMeleeScenario(id, actor_id, pc, fate, day_id, enemies, facts, policy, fate_policy, random_hand_policy, initial_weapon_hand, enemy_activation_order, target_priority, defeat_decisions, max_rounds)`. Все поля обязательны. `enemies` — ordered tuple `NpcParticipantSnapshot`; defeat decisions — ordered `MinionDefeatDecision` от данного PC на каждую цель. Definition: `id, weapon_skill, strength, toughness, agility, melee, defence, athletics, endurance, weapon, armour_bonus`. Facts: `zone_id, all_opponents_close, targets_aware, all_combatants_included, unmounted, no_external_effects, no_terrain_modifiers, no_additional_abilities, no_ambush, outnumbering_bonus_approved, can_leave_zone`; последние два bool допускают оба значения, прочие утверждения обязательны true. Реализация при уточнении обязанностей синхронизирует этот интерфейс, сохраняя выбранную границу.

## Приёмка и порядок

Сначала admission/source cases и достижимость четырёх исходов, затем execution/mandatory continuations, trials/balance/wire и один аудит на границе M9. Не объявлять законченной всю M9 по наличию модели или одного Attack.

Адресные проверки: bool/int/Enum/source guards до RNG; WS/Melee/Defence и Sword cap; actual Attack в обе стороны; Wounds1–10 и legal mixed/repeated effects; dropped empty/occupied hand, unarmed Protection и Recover; actual next-Test Grim на Attack/Protection; expiry после следующего собственного хода; положительный Fate без расхода, исчерпанный session allowance без запрета burn, Near Miss closure перед lethal outcome; daily receipts и replay/stale/forged state/history; четыре исхода; aggregate denominator/budget/selection; fixed source/seed real spawn; полный текущий wire/error/report.

На границе — одна полная source regression и одна installed delivery проверка по действующей политике, без копии всех unit tests в installed. Значения вероятностей в детерминированных проверках не угадываются. Наличие unsupported после более тяжёлых ран остаётся видимым ограничением, а не «победой» или оценкой оптимальной игры PC.

## Реализация и адресная проверка

Вход, owner/runner, независимые simulation records/summary/process, aggregate-only count search и отдельный current JSON1/CLI реализованы. Count search здесь одностадийный, с одинаковым явным trials_per_candidate; staged reruns не заявлены. Public requests/results и фактические наблюдения находятся в [примере M9](../examples/m9/README.md).

| Проверка | Фактический результат |
|---|---|
| Input models/source admission |18 unit OK/0.035s|
| Engine/result/Wounds1–10 |21 tests OK/0.781s,12 unit+9 battle с scripted d10|
| Simulation observations/accounting |7 unit OK/0.014s|
| Один source, четыре actual outcomes/real spawn/worker failure |4 integration OK/2.408s; counts1/each,40actions/16started/13completed|
| Generation/source/selection |16 unit OK/0.071s;3 actual integration OK/0.972s, включая aggregate-only и real spawn|
| Pure JSON/schemas |18 IDs закрыты составно:17OK, один тест ошибочно предполагал refs>100. После исправления этого ожидания offline-closure test отдельно OK/0.618s; production failures не было.7 schemas/85 refs, общий bundle32/414|
| CLI и соседняя Magic family |5 новых CLI IDs и1 прежний Magic error-family ID одним run:6OK/21.982s; module/console, внешний cwd, process, private failure и pre-RNG guards|
| Общий schema bundle |Изменённый прежний Magic offline-bundle test отдельно OK/0.468s; Magic current6 сохраняется|

Read-only review выявил четыре source/provenance gap, исправленные с регрессиями: полный canonical PLAYER Wound source, запрет foreign kernel branches ordinary Attack, повторный допуск nested DailyWoundRegistration и nested RecoverStandardResult/Condition changes. Дополнительно строго проверяются equal-but-wrong-type bool/raw Enum/numeric leaves и полный prefix/replay.

Локальные адресные logs: `.cache/m9-pc-engine-final.log`, `.cache/m9-simulation-integration.log`, `.cache/m9-cli-integration.log`. Финальные проверки ниже отдельно подтверждают весь актуальный набор.

## Финальная приёмка 2026-11-04

- [x] **Source regression:** при `PYTHONPATH=src` команда `.venv/Scripts/python.exe -m unittest discover -s tests -v` — **4404 tests, OK за 1353.865s**, один полный run без failures/errors/skips. В него вошли 92 новых M9 IDs и прежние проверки, включая изменённый общий CLI/schema bundle. 1005 файлов source/tests `.py/.json` не менялись с начала проверки; hashes сохранены в `.cache/m9-source-checkpoint-manifest.json`.
- [x] **Installed delivery:** одна offline wheel-сборка из свежей копии package sources/metadata, установка вместе с настоящими cached dependency wheels в новый venv; `pip check` успешен. SHA256 всех 495 `.py/.json` совпали source→wheel→installed. 32 schemas/414 refs разрешились offline, включая PC7/85; прежняя Magic family сохраняет current6. Импорты подтверждены внутри нового venv, запуск — из внешнего временного cwd без `PYTHONPATH`/`PYTHONHOME` и editable paths.
- [x] **Восемь installed CLI cases:** обе PC-команды module/console sequential дали полные ответы, равные сохранённым source examples; один console process simulation сохранил summary и explicit backend echo. Три input errors проверили bool вместо WS, non-reduced Fraction с точным pointer и lexical float с untrusted request ID. Stdout/exit codes/stderr соответствуют контракту. Повторных сборок и полных installed unit suites не было.

Финальная приёмка прошла без исправлений исходников и без повторного full/wheel. Логи: `.cache/m9-final-source-regression.log`, `.cache/m9-final-delivery.log`; установленный отчёт `.cache/m9-final-delivery-df0a8c457e/report.json`. Wheel `towr_encounter_balancer-0.1.0-py3-none-any.whl`, SHA256 `3c863c553ed0a9369e87f652cf67ea952f3bc37d819873c92b5aacbb593b667d`. Offline build/install используют `pip wheel --no-index --find-links WHEELHOUSE --no-deps PACKAGE_COPY`, fresh `venv`, `pip install --no-index --find-links WHEELHOUSE WHEEL`, `pip check`; локальный driver `.cache/m9_final_delivery.py` — вспомогательный артефакт проверки.

Все конечные критерии M9 выполнены в этой границе. Партия PC, активное использование Fate, остальные оружие/Talents/раны, общий inventory, лечение и campaign требуют отдельных последующих функций; текущий milestone ими не расширяется автоматически.
