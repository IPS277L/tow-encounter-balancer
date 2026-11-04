# Открытые вопросы и действующие допущения

Дата: 2026-11-04. Это короткий индекс незакрытых тем; читать подробности только по затронутой механике. Полные формулировки, ссылки на книги и текущие ограничения сохранены в [деталях](open-questions-details.md); закрытые темы — в [истории](open-questions-history.md).

## Действующая граница симуляции

Ограниченные M8–M23 завершены: [статус и текущие ограничения](project-status.md), [Official/Broken M23](decisions/ADR-0078-pc-official-first-wound-broken-boundary.md), [архитектура](architecture/overview.md). Поддержанные PC weapons/Fate/Help/Recover и книжные combat loadouts не разрешают автоматически другие действия/Abilities. История закрытых вех не расширяет очередь и не возвращает старые wire formats.

Wounds1–23/lethal24+, source-aware Conditions и mandatory Critical/Defenceless end phases сохраняются. Невозможная повторная анатомия, недоступный2H хват без продолжения и собственный Broken turn Official имеют точные stop boundaries. Незавершённые route/recovery/GM решения нельзя подставлять ради продолжения; observed losses относятся только к исполненному prefix.

## Продолжение Broken NPC

M23 по выбору пользователя останавливается перед собственным ходом Broken Official, сохраняя Wound и очередь предыдущих ходов. Для дальнейшего исполнения не выбраны safe route/fastest-path facts, значение ухода для objective и возможность снять Broken при сохраняющейся profile Wound. [Подробности](open-questions-details.md#продолжение-broken-npc).

## Бонус Greatsword

PG1.4 Equipment93 содержит `+1 to Defence` без `d`. Тип модификатора пока не определён; Greatsword исключён из M19, положительное решение не подставлять. [Подробности](open-questions-details.md#бонус-greatsword).

## Выбранная стратегия M12

Пользователь выбрал все тяжёлые раны11–23 и продолжение Attack/Recover с книжными осложнениями, здоровой рукой при возможности и clutch свободной. [ADR-0068](decisions/ADR-0068-pc-heavy-wound-continuation.md) — явная policy, не house rule. Для физически невозможной повторной анатомической потери без существующей цели сохраняется actual pending stop; произвольная GM замена результата не выбрана.

<a id="первая-метрика-m5"></a>

## Значение ничьей для балансировки

Настоящая ничья пока не определена. ROUND_LIMIT и UNSUPPORTED_PATH остаются отдельными исходами в общем знаменателе trials. [Подробности](open-questions-details.md#значение-ничьей-для-балансировки).

## Политики выбора для симуляции

Не выбран общий AI-подход для Fate, Talents, Reactions и прочих решений участника. Kernel сохраняет явного владельца решения; не подставлять новый default. [Подробности](open-questions-details.md#политики-выбора-для-симуляции).

В M14 доступны раздельные caller-owned Near Miss threshold/rating reserve и Glorious selected skills/initial-success threshold/session reserve; обе можно сочетать через `configured` либо выбрать полный отказ. [Контракт](decisions/ADR-0070-pc-glorious-test-policy.md). Числа публичного примера — параметры конкретной стратегии, не общий default и не найденный оптимум. Остальные optional Fate decisions отклоняются.

M15 добавляет caller-owned роль Melee helper для конкретной атаки более позднего обычного PC в этом раунде, с self Recover/Attack fallback. [Граница](decisions/ADR-0071-pc-melee-help-policy.md). Получение бонуса само по себе не доказывает преимущество этой тактики; оптимальный выбор Help/Attack не задан. Clock сохраняет всю PC-side перед NPC-side.

M16 расширяет тот же Help на [конкретный incoming Protection Test](decisions/ADR-0072-pc-protection-help-policy.md) первого ожидаемого live NPC, с явным Defence/Athletics. Protection beneficiary может уже завершить ход; прежние snapshots не переназначаются при смене цели/Skill или гибели NPC. Общий выбор самых выгодных действий/врагов не определён.

M17 добавляет [явный standard Recover союзнику](decisions/ADR-0073-pc-ally-standard-recover.md): self-required приоритет, иначе ally-first по каждому benefit. Оngoing причины сохраняются, Prone13 вызывает Critical у фактического получателя. Получение помощи не является его действием14/15. Это не лечение ран и не оптимальный выбор по всем целям.

## Масштаб Unmitigated Success и Last Stand

Масштаб подвига задают GM и игрок; универсального вычисления по successes нет. Пока нужны явные scope/target/consequence facts. [Подробности](open-questions-details.md#масштаб-unmitigated-success-и-last-stand).

## Конкретизация альтернативной цены Retreat

Price consumers сохраняют выбранную цену и явные последствия; автоматический выбор/оценка GM-цены не определены. [Подробности](open-questions-details.md#конкретизация-альтернативной-цены-retreat).

## Конкретизация последствий Run For Your Lives

Регистрация campaign hooks реализована, их произвольное дальнейшее исполнение не задано. Не трактовать запись последствия как готовую симуляцию campaign. [Подробности](open-questions-details.md#конкретизация-последствий-run-for-your-lives).

## Как ранжировать most vigilant enemy

Пока используется явный vigilance_priority со стабильным порядком при равенстве. Формулу автоматического сравнения Awareness profiles ещё нужно выбрать. [Подробности](open-questions-details.md#как-ранжировать-most-vigilant-enemy).

## Лимит раундов

Budget обязателен и явен; продуктовый default не выбран. Не выводить difficulty из длительности автоматически. [Подробности](open-questions-details.md#лимит-раундов).

## Порядок multi-target целей

Executor принимает разные цели в явном порядке. Будущему spatial discovery нужна стабильная policy выбора/порядка. [Подробности](open-questions-details.md#порядок-multi-target-целей).

## Monstrous Flight без доступного Give Ground

Если перемещение невозможно и нет уже использованного Give Ground, исход требует GM-policy; текущая ветвь отклоняется без выдуманной замены. [Подробности](open-questions-details.md#monstrous-flight-без-доступного-give-ground).

## Источник Distracted

ConditionState не хранит объект отвлечения. Нужна provenance-модель либо явная синхронизация со специализированными Ability states. [Подробности](open-questions-details.md#источник-distracted).

## Spell Recast без определённой недавней истории

Не определены recently, веса spells и пустая история. Пока caller передаёт непустой стабильный snapshot options. [Подробности](open-questions-details.md#spell-recast-без-определённой-недавней-истории).

## Objects Transfigured при недостатке объектов

При нехватке объектов GM-policy ещё не выбрана. Reducer сохраняет выпавшее число и не сокращает его молча. [Подробности](open-questions-details.md#objects-transfigured-при-недостатке-объектов).

## Range-формулировки Miscast и сам маг

Неодинаковые формулировки self-inclusion требуют решения перед общим target discovery; пока caller явно задаёт target snapshot. [Подробности](open-questions-details.md#range-формулировки-miscast-и-сам-маг).

## Бонус Charge для Brawn

Есть расхождение формулировок PG117/118. Временная узкая policy даёт бонус Charge только Skill.MELEE. [Подробности](open-questions-details.md#бонус-charge-для-brawn).

## End-battle treatment при неполном наборе инструментов

Частичный набор trappings не определён. Пока требуется явное наличие инструментов для всех ран (AMBIGUITY-008). [Подробности](open-questions-details.md#end-battle-treatment-при-неполном-наборе-инструментов).

## Последствие провала Surgery и наём NPC

Книга не задаёт вероятность disfigurement/death и цену/автоуспех NPC. Risk остаётся GM-owned, Test явный (AMBIGUITY-009). [Подробности](open-questions-details.md#последствие-провала-surgery-и-наём-npc).

## Что именно отменяет Combat Surgeon

Пока снимается требование theatre и меняется time, но сохраняются tools/supports. Более широкое чтение не утверждено (AMBIGUITY-010). [Подробности](open-questions-details.md#что-именно-отменяет-combat-surgeon).

## Границы orchestration histories

Не определены общий battle chronology, забывание укрытий и перенос histories между боями. IDs/state не сбрасываются автоматически. [Подробности](open-questions-details.md#границы-orchestration-histories).
