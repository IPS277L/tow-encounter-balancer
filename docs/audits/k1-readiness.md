# Аудит готовности K1 к M2

Дата: 2026-09-27. Основание: [roadmap](../roadmap.md), [ADR-0002](../decisions/ADR-0002-book-first-resolution-kernel.md), [контракт kernel](../architecture/resolution-kernel.md), [трассировка](../rule-traceability.md). На начало аудита рабочее дерево чистое. Production-код в рамках аудита не менялся.

## Вывод

**K1 готов к переходу в M2 для явно поддержанного numeric Melee/Shooting среза.** Контекстный выбор Attack/Protection закрыт source-bound preparation; сквозной тест подтвердил композицию с kernel и Wound completion. Это завершение исходных пяти критериев ниже, а не объявление поддержки всех профилей книг. Полный набор: 1488 tests OK на Python 3.14.

Следующий шаг — минимальный контракт состава участников M2. Scheduler, AI, общая battle orchestration и истинность supplied facts остаются внешними. Дополнительные Aim combinations и полный NPC catalog не являются предварительным условием перехода.

## Матрица исходного K1

Пути к реализации ниже относительны `src/towr/`, к проверкам — `tests/unit/`.

| Пункт roadmap | Реальный контракт и свидетельство | Статус и граница |
|---|---|---|
| Characteristic + Skill, готовые NPC-профили | `domain/test_models.py`: `TestProfile`, `InlineProfile`; `test_k1_test_resolution.py`: `test_profile_uses_characteristic_for_dice_and_skill_for_threshold`, `test_inline_profile_has_explicit_or_derived_pool_cap` | Готово как числовой вход Test. Полный каталог NPC и загрузчик профилей не реализованы; готовый InlineProfile не доказывает корректность его выбора. PG 68, 106–107; GM 93; RULE-TEST-001, RULE-NPC-007. |
| Basic/Opposed, modifiers, Grim/Glorious | `rules/test_resolution.py`, `rules/opposed_test.py`; `test_k1_test_resolution.py`, `test_k1_opposed_test.py`: minimum-one, cap, staged completion, nonzero tie и double-zero | Готово в границе явного Test/DecisionProvider. Оценка драматической необходимости Test и ситуационных modifiers остаётся GM/scenario input. PG 106–110; RULE-TEST-001..004,006. |
| Контекстный выбор Attack/Protection | `domain/attack_models.py`: `AttackRequest`; `rules/attack_resolution.py`; `rules/ranged_weapon_attack_preparation.py`; `test_k1_ranged_weapon_attack_preparation.py`, `test_k1_ranged_close_enemy_preflight.py` | **Готово для заявленного numeric Melee/Shooting среза.** Ranged profile/range/Lore/Aim проверяются; source-bound Protection preparation реализована в protection_models.py/protection_preparation.py (13 test_k1_protection_preparation.py). NPC numeric Melee/Shooting selection/preparation реализована (npc_attack_preparation_models.py, npc_attack_preparation.py; 13 test_k1_npc_attack_preparation.py); прочие профили явно исключены. Сквозная проверка — `tests/integration/test_k1_npc_attack_kernel_cycle.py` (3 теста / 44 сочетания). Низкоуровневый resolver сам preparation не требует. PG 68, 94, 118; GM 93; RULE-NPC-007..008. |
| Damage/Resilience | `rules/attack_resolution.py`; `test_k1_attack_resolution.py`: tie, unopposed, success margin, ignores armour, modifiers, replacement impacts | Готово для явных профилей: строгая граница Wound, Condition/Hazard replacements и rule trace. Источник фактических equipment/Conditions modifiers должен быть явно задан; полный inventory/effective-view слой не входит в эту фазу. PG 97, 118–119; RULE-COMBAT-005..009, RULE-HEALTH-001..004. |
| Staggered choice policy | `rules/stagger_resolution.py`, `rules/stagger_impact_resolution.py`; `test_k1_stagger_resolution.py`, `test_k1_kernel.py` | Готово: первый Staggered, legal repeated choices, Prone/Give Ground ограничения и внешний владелец решения. AI-оценка вариантов — M2/M3, не скрытый default kernel. PG 119; RULE-HEALTH-001..004. |
| Injury policies | `rules/injury_resolution.py`, `rules/monstrosity_resolution.py`, `rules/wound_lifecycle_resolution.py`; `test_k1_injury_resolution.py`, `test_k1_monstrosity_resolution.py`, `test_k1_wound_lifecycle_resolution.py` | Готово для Player/Champion, Minion, Brute, Monstrosity. Player/Champion разделены в enum, но используют одну книжную Wounds Table policy; реакции Monstrosity сохраняют владельца. Pending Wound требует явного completion до применения эффекта. PG 112, 190–191; GM 91–92; RULE-HEALTH-005..006. |
| Детерминированность и Rule ID | Внедряемые `RandomSource`/decisions, frozen requests/results, `RollTrace`/`applied_rule_ids`; unit-тесты выше и integration cycles | 1488 tests OK. Есть локальные trace/provenance assertions; автоматической проверки полноты всей таблицы `rule-traceability.md` нет. Закрытие K1 требует точных ссылок для поддержанного среза, а не перевода каждой строки каталога в `implemented`. |

## Дополнительные K1 boundaries и Aim/hidden

Это уже реализованные надстройки вокруг kernel. Их объём не превращается в требование перебрать все декартовы комбинации действий.

| Семейство | Проверка | Остаток / ответственность caller |
|---|---|---|
| Round/slot, Fate, action receipts | `test_k1_turn_resolution.py`, `test_k1_fate_resolution.py`, `test_k1_attack_action_execution.py` | Battle scheduler, выбор следующего actor/action и хранение всех состояний — M2. Fate second-action spend уже связан с slot proof. |
| Aim APPLIED/LOST, подготовка и replay | `tests/integration/test_k1_aim_target_switch.py`, `test_k1_aim_ranged_attack_cycle.py`; unit `test_k1_aim_resolution.py`, registered/prepared loss tests | Следующее фактическое действие выбирает caller. Низкоуровневые result consumers не защищают от уже израсходованного RNG; atomic adapters делают preflight. Семантика Aim включает Shooting/Throwing в `aim_models.py`; отдельный каталог/исполнение thrown weapon этим не доказаны. |
| Medium/Long/terrain Melee/Brawn Charge → LOST → Recover → fresh Aim/APPLIED | `tests/integration/test_k1_aim_charge_cycle.py`, `test_k1_aim_long_charge_cycle.py`, `test_k1_aim_difficult_terrain_charge_cycle.py` | 2/6/4 теста соответствующих общих сценариев. Long включает оба stopped-short; terrain — повторное crossing. AMBIGUITY-007 остаётся открытой; +1d временно только Melee. |
| Hidden position/history/lifecycle и совместный Aim | `tests/integration/test_k1_hidden_recovery_cycle.py`; unit hidden registration/lifecycle tests | Проверены одно исполнение, новое укрытие, Reload, explicit reveal, independent Aim loss/hidden continuation. Автоматическая awareness, забывание укрытий, same-Zone перемещения и произвольная цепочка чужих изменений не реализованы и не выводятся из этих тестов. |
| Miscast и Wound completion | `test_k1_miscast_effect_resolution.py`: `test_player_can_use_near_miss_before_internal_damage_completion`, `test_fixed_completion_is_target_bound_and_consumed_once` | Internal Damage и Ears Ringing уже используют общий lifecycle. GM-owned target discovery, recast и narrative consequences остаются внешними. |

Long Charge через terrain нельзя автоматически ставить в очередь как «недостающую комбинацию»: PG 1.4, Rules / Difficult Terrain, стр. 115 запрещает дополнительную Athletics для дальней Zone на ходу с terrain Test. Отдельный случай обхода terrain Test требует своего книжного контекста; текущий Medium terrain contract не следует расширять по аналогии.

Остальные attacking Skill/Ability Improvise, полные spell/mount/item каталоги и arbitrary follow-up chains не являются обязательными wrappers перед следующим срезом. Если конкретный профиль будет включён в M2, его допустимые действия и эффекты должны иметь проверенный contract либо явный отказ при неподдержанном запросе.

## Открытые вопросы и границы M2

- AMBIGUITY-007 (Brawn Charge bonus) сохраняет временную политику. Это ограничение результатов с данным действием; Protection preparation от него не зависит.
- Monstrous Flight без возможного Give Ground, Greatsword `+1 to Defence`, self-inclusion Miscast, end-battle trappings и surgery scope требуют своих решений перед включением таких сценариев. Аудит не выбирает house rules.
- Caller сейчас передаёт awareness, Close/range, доступность Give Ground, equipment и выбранные targets. Их автоматическое получение и перенос единого актуального состояния относятся к M2.
- Condition/effective-view интеграция, источники Distracted, healed Ruptured Organs, optional early Endurance остаются отдельными неполными областями. Они не должны молча считаться поддержанными профилями первого M2-сценария.
- Campaign/downtime, Corruption, Faith, полный каталог items/Abilities, serialization/CLI, Monte Carlo и balancing не становятся условиями завершения исходного K1. Порядок M2–M5 не изменён.

## Конечные критерии готовности K1 к M2

1. Все семь пунктов матрицы имеют действующие typed contracts и детерминированные проверки, включая source/context validation выбора Attack/Protection. Пробел этой строки нельзя закрыть одним green full suite.
2. Для явно поддержанного входного среза есть сквозная проверка: подготовка одной атаки → kernel → required Wound completion/follow-ups, с сохранением RNG, source и trace. Scheduler и AI не требуются.
3. Список поддержанных профилей/эффектов конечен и указан; неподдержанные механики остаются explicit external inputs/ошибками, без фиктивных default и без наследования поведения P1. Полный NPC catalog не обязателен.
4. Нет известных расхождений с книгой внутри заявленного среза без явно отмеченного допущения. Открытые rulings ограничивают соответствующие сценарии; решение не подменяется тестом.
5. Полный набор тестов и `git diff --check` проходят; roadmap, status и traceability совпадают с кодом. На текущем окружении проверен Python 3.14; проверка Python 3.12 отдельно не выполнена.

## Выполненный implementation-срез: Protection preparation

Создать узкие immutable request/result и чистую preparation function для **одного явно выбранного способа защиты**. Она принимает supplied profiles, incoming attack kind/range и explicit awareness/Defenceless/weapon/shield facts; возвращает допустимый defender Test либо явный unopposed result с причиной и Rule IDs. Сохранять source binding, не вызывать RNG и не изменять kernel. Допустимые варианты и выбор caller разделить: не ранжировать Athletics/Defence по выдуманной expected-value policy.

Источник: GM Guide 1.1, Allies and Antagonists / Understanding NPC Profiles, стр. 93; PG 1.4, Skills / Defence, стр. 68; Equipment / Ranged Weapons, стр. 94; Rules / Attack Tests, стр. 118. Непосредственно перечитать их перед реализацией.

Минимальная проверка:

- Athletics как обычная защита; Defence против close combat при подходящем вооружении;
- Shooting/Throwing: Defence при щите и отказ без него;
- специальная возможность Melee против ranged Attack в Close по PG 94 — отдельный допустимый выбор, без автоматического бонуса оружия NPC;
- unaware/Defenceless → unopposed, без защитного броска;
- отсутствие требуемого выбранного профиля, несовместимый skill/context и stale source отклоняются;
- детерминированная композиция с существующим `resolve_attack`: один opposed/unopposed result, tie/double-zero, переданный RNG и trace;
- несколько допустимых вариантов не превращаются в автоматическую боевую policy.

Не добавлять полный NPC catalog, GM text parser, экипировку/inventory, AI, battle aggregate, новые Aim wrappers или общий язык правил. Protection и numeric Melee/Shooting NPC preparation выполнены. Integration-срез подтвердил существующий критерий 2; новые criteria не добавлены.

## Исправленные расхождения документации

- Трассировка ошибочно оставляла Miscast character Wounds вне lifecycle: оба consumer уже существуют и проверены; optional early Endurance не закрыт этим исправлением.
- В architecture overview оставалась фраза об отсутствии prepared/hidden/Charge LOST compositions после их реализации.
- Общая строка action budget говорила об отсутствии Fate resource consumption, хотя `spend_fate_for_second_action` и slot proof уже проверяются. Это не означает, что все Ability resource policies реализованы.
- Статус готового Attack resolver отделён от отсутствующей подготовки Protection; добавлена отдельная строка RULE-NPC-008, чтобы `implemented` damage/attack pipeline не скрывал этот пробел.

Проверка аудита: `PYTHONPATH=src; py -3.14 -m unittest discover -s tests -v` — **1459 tests, OK**. Production/test-код не менялся; новые тесты ради документации не добавлялись. Ссылки документации и `git diff --check` проверены отдельно.

Обновление после реализации Protection: 13 новых тестов, полный набор 1472 OK на Python 3.14. prepare_protection сохраняет supplied Test и исходную атаку, выбирает только явно указанный допустимый Skill, не использует RNG. Awareness/equipment/profile актуальность остаётся caller-owned. Следующий срез — выбранная NPC Attack и её композиция с Protection; K1 целиком не объявлен завершённым.

Обновление после NPC preparation: 13 новых тестов, полный набор 1485 OK. Для Brigand Axe/Warbow и Town Watch Polearm непосредственно сверена GM p97; профильные значения не заменяются PC equipment traits. Availability/target/range и exact Protection pair проверяются до исполнения. Numeric Melee/Shooting поддержаны; Throwing/Brawn/non-damage/Extreme/multi-attack и полный NPC catalog исключены из этой boundary. Следующая проверка: оба preparation results → existing kernel → pending Player/Champion Wound completion или immediate Minion/Brute injury, один набор бросков и обе traces. Это исходный integration-критерий аудита, не новая ветка возможностей.

## Закрытие критериев после NPC/kernel integration

tests/integration/test_k1_npc_attack_kernel_cycle.py: 3 теста / 44 сочетания Brigand Axe/Warbow, opposed/unopposed hit/miss, Player/Champion pending Wound → exact completion, Minion defeat и Brute до/на wound limit, Player Near Miss после настоящего броска. Проверены один Attack и требуемые Test/Wound броски, returned target state, сохранение обеих preparation traces, эффект Drained только после принятия Wound, отсутствие эффекта/суточной регистрации при Near Miss и сохранение Staggered. Replay отклоняется с returned consumption history либо на уже завершённом kernel result; защита от отката caller-owned snapshots не заявлена. Production API и правила не менялись. Непосредственно перечитаны BOOK-GM-GUIDE 1.1, Allies and Antagonists / Types of NPC, стр. 91–92; Understanding NPC Profiles, стр. 93; Brigands & Footpads, стр. 97; BOOK-PLAYER-GUIDE 1.4, Rules / Near Miss, стр. 112; Attack Tests, стр. 118; Failed/Successful Attacks, стр. 119; Wounds & Conditions, стр. 121; Wounds Table / Stomach blow (6), стр. 190.

Конечный подтверждённый срез:

| Вход / поведение | Поддержка и граница свидетельства |
|---|---|
| NPC Attack | Supplied numeric Melee/Shooting. Книжные fixtures: Brigand Axe/Warbow, Town Watch Polearm (unit); Axe/Warbow (integration). Без подразумеваемых PC weapon traits или специальных Abilities. |
| Protection | Явно выбранный допустимый Skill и supplied Test; awareness/Defenceless/equipment задаёт caller. Integration использует Athletics 3d/3 как заданный профиль цели, а не Protection Brigand. |
| Injury | Player/Champion: Stomach blow и Near Miss у Player; Minion: defeat; Brute: ниже/на лимите. Resilience 2 и Brute limit 2 — параметры синтетических целей, не новые книжные NPC. Остальные таблица/политики/Conditions покрыты отдельными unit-тестами матрицы. |
| Trace / follow-ups | Подготовки хранятся рядом с execution; kernel их trace не поглощает. Close miss возвращает AttackerStaggerRequest, profile Wound — state_change. Исполнение всей очереди внешним scheduler не заявлено. |
| Исключения | Нет автоматической awareness/range/equipment, полного каталога, Throwing/Brawn/non-damage/Extreme/multi-attack NPC preparation, NPC reload/slot consumption и AI. Monstrosity policy проверена отдельно, но не включена в этот integration fixture. |

1. Все семь пунктов матрицы имеют contracts/tests; selection и Protection теперь проверяются до исполнения.
2. Три integration tests подтверждают подготовку → единственное исполнение → обязательный Wound completion либо profile injury с точным RNG.
3. Конечные fixtures и эффекты перечислены выше; границы generic contracts отделены от проверенных сценариев.
4. Новых расхождений с непосредственно прочитанными книгами внутри среза нет. AMBIGUITY-007 и остальные rulings не закрываются: соответствующие сценарии исключены.
5. 1488 tests OK; compileall, ссылки документации и git diff --check успешны. Python 3.12 отсутствует, проверен 3.14.

Первый срез M2 — определить и реализовать минимальный immutable контракт состава участников для поддержанного numeric NPC Melee/Shooting: отдельные определения и состояния экземпляров, actor/side IDs, явные доступные атаки и Protection, соответствие injury policy/state. Зафиксировать ADR и границы первого сценария; проверить получение существующих preparation inputs из состава с сохранением source/actor binding и отказом для неподдержанных профилей. Не переносить P1 CombatantDefinition как книжную модель; пока не добавлять scheduler, AI, автоматическую awareness, общий battle aggregate или новые Aim wrappers. Перед реализацией сверить существующие turn/side contracts и GM 1.1, Allies and Antagonists, стр. 91–93,97; PG 1.4, Rules / Combat, стр. 113–114 и Attack Tests, стр. 118.

Продолжение M2: контракт состава участников реализован в NpcRoster ([ADR-0008](../decisions/ADR-0008-npc-roster-boundary.md)); 13 новых тестов, 1501 tests OK. Критерии завершения K1 не расширены. Следующий шаг M2 — один выбранный Minion Attack через turn/slot executor с сохранением returned roster state и follow-ups.
