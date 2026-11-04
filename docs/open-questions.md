# Открытые вопросы и действующие допущения

Дата: 2026-11-04. Это короткий индекс незакрытых тем; читать подробности только по затронутой механике. Полные формулировки, ссылки на книги и текущие ограничения сохранены в [деталях](open-questions-details.md); закрытые темы — в [истории](open-questions-history.md).

## Действующая граница симуляции

Ограниченные M8–M14 завершены: [Glorious/Near Miss ADR-0070](decisions/ADR-0070-pc-glorious-test-policy.md), [тяжёлые раны ADR-0068](decisions/ADR-0068-pc-heavy-wound-continuation.md), [статус](project-status.md), [архитектура](architecture/overview.md). Numeric static Minions/Brutes и PC Wounds1–23/lethal24+ исполняются с индивидуальными Fate/body/daily histories и mandatory Critical/Defenceless end phase. Гибель одного PC допускает продолжение другими; observed losses не предсказывают судьбу survivors после stop/limit. GM-замена физически невозможной повторной анатомии не задана, сохраняется actual pending stop. Остальные активные Fate options, post-healing Endurance22, лечение, Champions/Monstrosities, ally Recover/Help, campaign/inventory и оптимальная AI-policy остаются дальнейшими темами. Characteristic enum ещё не полный; PC family использует числовые WS/Skills с TestProfile. История M8 не расширяет очередь и не возвращает старые wire formats.

## Выбранная стратегия M12

Пользователь выбрал все тяжёлые раны11–23 и продолжение Attack/Recover с книжными осложнениями, здоровой рукой при возможности и clutch свободной. [ADR-0068](decisions/ADR-0068-pc-heavy-wound-continuation.md) — явная policy, не house rule. Для физически невозможной повторной анатомической потери без существующей цели сохраняется actual pending stop; произвольная GM замена результата не выбрана.

<a id="первая-метрика-m5"></a>

## Значение ничьей для балансировки

Настоящая ничья пока не определена. ROUND_LIMIT и UNSUPPORTED_PATH остаются отдельными исходами в общем знаменателе trials. [Подробности](open-questions-details.md#значение-ничьей-для-балансировки).

## Политики выбора для симуляции

Не выбран общий AI-подход для Fate, Talents, Reactions и прочих решений участника. Kernel сохраняет явного владельца решения; не подставлять новый default. [Подробности](open-questions-details.md#политики-выбора-для-симуляции).

В M14 доступны раздельные caller-owned Near Miss threshold/rating reserve и Glorious selected skills/initial-success threshold/session reserve; обе можно сочетать через `configured` либо выбрать полный отказ. [Контракт](decisions/ADR-0070-pc-glorious-test-policy.md). Числа публичного примера — параметры конкретной стратегии, не общий default и не найденный оптимум. Остальные optional Fate decisions отклоняются.

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
