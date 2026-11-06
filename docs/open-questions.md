# Открытые вопросы и действующие допущения

Дата: 2026-11-06. Это короткий индекс незакрытых тем; читать подробности только по затронутой механике. Полные формулировки, ссылки на книги и текущие ограничения сохранены в [деталях](open-questions-details.md); закрытые темы — в [истории](open-questions-history.md).

## Действующая граница симуляции

Ограниченные M8–M47 завершены: [статус и текущие ограничения](project-status.md), [Broken exit M24](decisions/ADR-0079-pc-broken-npc-adjacent-exit.md), [архитектура](architecture/overview.md). Поддержанные PC weapons/Fate/Help/Recover и книжные combat loadouts не разрешают автоматически другие действия/Abilities. История закрытых вех не расширяет очередь и не возвращает старые wire formats.

Wounds1–23/lethal24+, source-aware Conditions и mandatory Critical/Defenceless end phases сохраняются. Невозможная повторная анатомия, недоступный2H хват без продолжения и собственный Broken turn Official без exit policy имеют точные stop boundaries. Незавершённые route/recovery/GM решения нельзя подставлять ради продолжения; observed losses относятся только к исполненному prefix.

## Продолжение Broken NPC

M24 задаёт конечный clear/fastest adjacent exit без преследования/Recover; пользователь выбрал успех, когда все NPC побеждены или ушли, с отдельным учётом ухода. При null policy остаётся stop M23. Открыты общий маршрут с препятствиями/Run/Manoeuvre, дальнейшее поведение и возможность снять Broken при сохраняющейся profile Wound. Аналогично, M26 не определяет будущий NPC Recover для снятия profile Staggered Merchant при сохраняющемся W1; то же ограничение будущей NPC recovery policy относится к White Wolf и Empire Knight в обоих loadouts, Knight of the White Wolf, Big ’Un, Bear и Demigryph с профильным Drained. Centigor M40 продолжает Attack с W1Prone; его будущий NPC Recover при сохраняющейся profile Wound также не определён. [Подробности](open-questions-details.md#продолжение-broken-npc).

## Weighted Net после M31

Пользователь выбрал три melee-профиля; Net не входит в Night Goblin loadout. Для отдельной функции нужны primary Burdened вместо Damage, Throwing, конечный запас/расход/подбор или смена оружия и явный выбор альтернативного Brawn Recover. Перед реализацией отдельно сверить Net против Defenceless; нынешний K1 damage-only gate не является правилом книги. [Подробности](open-questions-details.md#weighted-net-после-m31), [граница M31](decisions/ADR-0082-pc-goblin-melee-chunk.md).

## Shield и Resilience Dragon Ogre

GM148 перечисляет shield в Typical Trappings, но не в Protection; для2H loadout пока не выбрана трактовка printed Res8 без shield или7 после вычитания. Профиль исключён из M45 до уточнения. [Подробности](open-questions-details.md#dragon-ogre-shield-resilience).

## Бонус Greatsword

PG1.4 Equipment93 содержит `+1 to Defence` без `d`. Тип модификатора пока не определён; Greatsword исключён из M19, положительное решение не подставлять. [Подробности](open-questions-details.md#бонус-greatsword).

## Выбранная стратегия M12

Пользователь выбрал все тяжёлые раны11–23 и продолжение Attack/Recover с книжными осложнениями, здоровой рукой при возможности и clutch свободной. [ADR-0068](decisions/ADR-0068-pc-heavy-wound-continuation.md) — явная policy, не house rule. Для физически невозможной повторной анатомической потери без существующей цели сохраняется actual pending stop; произвольная GM замена результата не выбрана.

<a id="первая-метрика-m5"></a>

## Значение ничьей для балансировки

Настоящая ничья пока не определена. ROUND_LIMIT и UNSUPPORTED_PATH остаются отдельными исходами в общем знаменателе trials. [Подробности](open-questions-details.md#значение-ничьей-для-балансировки).

## Политики выбора для симуляции

M47 реализует [выбранные Flagellant policies](decisions/ADR-0092-pc-flagellant-feel-no-pain-and-recover.md): Feel No Pain при0Wounds и standard self Recover при1 с лечением. Оба выбора явные/независимые, `[]` сохраняет Attack-only/отказ от conversion; NPC Recover costs отдельные. Это не общий NPC recovery AI или campaign healing.

M46 реализует [выбранную Blood Rage policy](decisions/ADR-0091-pc-bestigor-blood-rage-and-wound-glorious.md): обязательный список Bestigors для добровольного Staggered перед Attack; `[]` отказывается только от acquisition, фактический Staggered сохраняет бонус. Следующая Attack после W1 Glorious однократно, выбран reroll всех доступных провалов; NPC не тратит PC Fate. Другие Blood Rage/регенерация этим не подключаются.

M39 реализует [выбранную тактику Enduring Strength](decisions/ADR-0087-pc-bear-second-attack-policy.md): обязательный список включённых Bears, после успешной первой Attack и всех её последствий — первый другой живой PC по текущему приоритету; `[]` явно отказывается от способности. Дополнительные атаки имеют реальные slots/receipts и отдельные costs. Произвольные дополнительные действия других существ этим не разрешаются.

M33 поддерживает [согласованные multiple NPC Help pairs](decisions/ADR-0083-pc-npc-automatic-help-policy.md); [M34](decisions/ADR-0084-pc-greenskin-automatic-help.md) расширяет их на Goblin/Night Goblin/Orc Boy/Big ’Un, [M35](rules/npc-profile-catalog.md#minion-chunk-m35) — на Sigmarite Cultist, [M36](rules/npc-profile-catalog.md#spear-chunk-m36) — на копейные Orc/Big ’Un loadouts. Пользователь выбрал Orc Help для Drained beneficiary, Attack fallback у dice helpers; free successes сохраняются, bonus dice запрещены. M37 не меняет стратегию: Fearsome/Charge/Charging Bull не исполняются fixed SUFFER_WOUND/Attack сценой. Конфигурация явная, NPC costs отдельные; общего оптимального AI нет.

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

M43 реализует выбранный пользователем [контракт Miner/grudge](decisions/ADR-0089-pc-miner-grudge-policy.md): обязательные явные пары Miner→PC, encounter application до первого хода и прежний target priority. `[]` явно означает отсутствие grudge; confirmed death снимает Distracted без переназначения отношения или повторного наложения в новом раунде.

M42 реализует выбранную пользователем [трактовку A Brewguard W1](decisions/ADR-0088-pc-brewguard-distracted-focus.md): разовое наложение от ранившего PC с ним как focus, снятие при его подтверждённой смерти после Wound/Fate, сохранение при Defenceless. Оставшаяся W1 эффект повторно не накладывает. Вариант ongoing W1 причины не выбран.

ConditionState не хранит объект отвлечения. M42/M43 используют owner-local typed source/focus bank без общей миграции всех consumers; общий provenance вопрос шире одной функции. [Подробности](open-questions-details.md#источник-distracted).

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
