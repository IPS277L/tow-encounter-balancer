# ADR-0087: Bear / Enduring Strength и вторая Attack

Дата: 2026-11-06. Статус: **принято пользователем и реализовано**. Выбран обязательный список Bears и существующий приоритет других живых PC.

## Задача и источники

BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Bear138: Enduring Strength позволяет после успешной Attack потратить второе действие на Attack другого врага в Close. BOOK-PLAYER-GUIDE1.4, гл.V Combat Actions116 ограничивает ход двумя действиями и обычно запрещает повторять действие. Способность Bear — специальное разрешение повторной Attack, без разрешения третьего действия.

PG109/118–119: успешная Attack — попадание, включая положительную ничью и Damage, не превышающий Resilience; рана не обязательна. При0/0 обе стороны проваливают Test. PG112 Near Miss отменяет рану, сохраняя успешную Attack. PG118/123 допускает живого Defenceless врага как цель без Protection Test. Это адресная сверка локальных извлечений выбранных версий, не новое полное чтение книг.

## Принятая законченная функция M39

Добавить один canonical loadout `BEAR_SWEEPING_CLAWS = bear_sweeping_claws`: WS4/BS0/S5/T5/I3/Ag3/Re2/Fel1, Normal, Res6 armoured, Brute3. Sweeping Claws — natural Melee Close4d/3 Damage5, hands=null, implicit maximum8; Protection Athletics3d/3 с implicit maximum6. В полной карточке сверены Default1/Melee3/Brawn4/Endurance4/Awareness3/Athletics3/Willpower4; loadout хранит выбранные Melee/Athletics, прочие Skills не исполняются. W0 без Condition, W1–2 Drained, W3 defeated; существующая no-NPC-Recover граница остаётся.

Полные альтернативные атаки/Abilities сохраняются в metadata. Crushing Weight не выбирается: ей нужны отдельный Prone-before-Give-Ground путь и cap8 при printed3d. Fearsome требует Give Ground от атаки Bear; нынешние PC выбирают SUFFER_WOUND. Charge, движение, лечение, NPC Recover и другие стратегии не добавляются. Один профиль здесь соответствует одной новой общей механике, а не искусственно раздробленному чанку.

## Принятый публичный контракт и тактика

В текущий PC JSON1 и native Scenario добавить обязательный `npc_extra_attack_actor_ids`: список/tuple разных opposition actor IDs с canonical Bear/Sweeping Claws. Пустой список означает явный отказ от optional второй Attack. Поле не имеет default; отсутствие или неподходящий actor отвергается до RNG. Порядок списка не меняет порядок активаций.

Для включённого Bear после успешной первой Attack:

1. Полностью исполнить её обязательные последствия, PC Wounds/Fate и acknowledgements. При pending unsupported сохранить фактический prefix и остановиться до выдачи второго slot.
2. По текущему `enemy_target_priority` выбрать первого другого живого PC. Исключить actual target первой Attack независимо от того, погиб он или пережил Near Miss. Живой Defenceless PC подходит; при отсутствии другой живой цели завершить ход без второго действия, reservation или RNG.
3. Выдать ability slot2 и исполнить отдельную Attack с новым source/target/receipt и уникальными action/kernel/Test IDs. Затем один раз завершить ход. Между атаками нет TurnEnd/end-turn эффектов. Первая и вторая атаки обе учитываются как исполненные действия; grant/reservation действием не считается. Второй успех третьего действия не даёт.

Staggered или Drained сами по себе не запрещают способность; обычные Test modifiers применяются к каждой фактической Attack. Help receipt, предназначенный для Test первой Attack, не переносится на вторую. Каждая Protection/Fate decision привязана к своему фактическому Test/Wound.

Count search сохраняет настройку у оставшихся Bears и удаляет IDs исключённых NPC, без переназначения. Наличие только одного PC допустимо: другая цель просто не возникает.

В trial добавить `npc_extra_attack_counts` в порядке исходных NPC; в summary — их агрегат, `npc_extra_attack_trial_count` (число trials хотя бы с одной второй Attack) и `total_npc_extra_attack_count` (сумма исполненных вторых Attack). Все wire метрики обязательны; native totals могут быть производными свойствами, как существующие Help totals. Считать только реально исполненные вторые Attack, включая их в общий action count. Проверки верхних границ расходов учитывают фактические extra actions, configured actors и число начатых раундов. Source echo сохраняет полную настройку.

Версия остаётся PC JSON1; compatibility ветвей нет. Все120текущихJSON documents M9–M38 мигрировать обязательным пустым списком и нулевыми метриками при сохранении прочих наблюдений. Native builders/fixtures явно задают новые поля. Схемы, codec, агрегаты и примеры обновляются вместе.

## Отклонённая альтернатива

Рассматривались явные пары Bear → фиксированный вторичный PC. Второй удар разрешался бы только по названному PC; если он умер или оказался actual primary target, Bear отказывался бы от optional Attack, без переназначения. Пользователь выбрал существующий приоритет других живых PC. Обе тактики допустимы книгой; автоматического выбора самой выгодной цели книга не задаёт.

## Граница слоёв и защита доказательства

Clock хранит узкое типизированное разрешение повторной Attack: actor/round, полный receipt исполненной первой Attack, первая и разрешённая вторая цели. Оно допустимо только на slot2/ABILITY/Attack после slot1/Attack. Сам `grant_rule_id` не разрешает повторение. Reservation и admission готового Turn/Round state проверяют одинаковые ограничения, включая отсутствие третьего действия, чужого или устаревшего proof.

PC owner сверяет разрешение с actual первой записью журнала, её полным source/result, HIT, canonical Bear/Ability, policy и завершёнными последствиями. Нейтральное разрешение в clock не подменяет доказательство успеха. Executor и admission готового Attack result проверяют, что фактическая target совпадает с разрешённой второй целью. Полный Attack result не импортируется в turn models, чтобы не создавать цикл слоёв.

## Проверенная граница

1. Полный Bear source/fresh factories, W0/W1/W2/W3, Drained/Test cap, сохранение35прежнихloadouts.
2. HIT без раны/положительная ничья/Near Miss разрешают второй удар; MISS/0–0 не разрешают. Первая цель погибла; альтернативная цель Defenceless; один оставшийся PC; явный отказ `[]`.
3. Реальные slots/receipts/уникальные IDs, порядок Wound/Fate/ack/end phase, отсутствие третьего действия и повторного Help. Неправильные actor/round/source/первый receipt/target, незавершённые последствия и forged cached результаты отвергаются.
4. Native journal → trials/summary → count search → current JSON1/schema/full source echo → полезные CLI simulation/balance примеры; расходы отражают исполненный prefix, не выданные slots.
5. Изменяется общий запрет повторной Attack, поэтому проверить ближайшие K1 turn/action/Fate/Help consumers и PC подсистему. Перед более дорогой общей регрессией отдельно назвать её основание и объём по фактическому diff. Wheel не нужен без изменения доставки/сборки.
6. Миграция120прежнихJSON documents сохраняет прежние значения; новые поля обязательны, malformed source не исправляется. Markdown/local links и `git diff --check`.

Согласование требуется по [AGENTS.md](../../AGENTS.md), раздел «Автономная работа до согласованной вехи»: «Спрашивать при существенной неоднозначности правил, смене согласованного контракта или блокере с решением пользователя». Здесь выбираются публичная policy и тактика optional второй Attack; правило книги не заменяется house rule.

Реализация и проверка завершены: [нормализованное правило](../rules/npc-profile-catalog.md#bear-second-attack-m39), [публичные примеры](../examples/m39/README.md), [статистика](../../tests/unit/test_m39_pc_extra_attack_statistics.py), [JSON1](../../tests/integration/test_m39_pc_bear_json.py), [process parity](../../tests/integration/test_m39_pc_bear_process.py). Единый checkpoint104модулей/1114tests OK; отдельно process test OK после разрешения Windows Pipe вне sandbox. Все44новыхtests прошли; прежние35entries и значения120JSON documents сохранены. Полный project regression/wheel не запускались. Фактические команды, ограничения и следующий шаг — в [project-status](../project-status.md).
