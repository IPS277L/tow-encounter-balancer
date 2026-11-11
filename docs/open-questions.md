# Открытые вопросы и действующие допущения

Дата: 2026-11-12. Это короткий индекс незакрытых тем; читать подробности только по затронутой механике. Полные формулировки, ссылки на книги и текущие ограничения сохранены в [деталях](open-questions-details.md); закрытые темы — в [истории](open-questions-history.md).

## Действующая граница симуляции

Ограниченные M8–M70 завершены: [статус и текущие ограничения](project-status.md), [Broken exit M24](decisions/ADR-0079-pc-broken-npc-adjacent-exit.md), [архитектура](architecture/overview.md). Поддержанные PC weapons/Fate/Help/Recover и книжные combat loadouts не разрешают автоматически другие действия/Abilities. История закрытых вех не расширяет очередь и не возвращает старые wire formats.

Wounds1–23/lethal24+, source-aware Conditions и mandatory Critical/Defenceless end phases сохраняются. Невозможная повторная анатомия, недоступный2H хват без продолжения и собственный Broken turn Official без exit policy имеют точные stop boundaries. Незавершённые route/recovery/GM решения нельзя подставлять ради продолжения; observed losses относятся только к исполненному prefix.

## M70: Hochland/Aim/Fate Second Action — решение принято

[ADR-0112](decisions/ADR-0112-pc-hochland-aim-and-fate-second-action.md) реализован: выбран actual Aim→явный Fate Second Action→Shoot в том же ходу. Awareness source/one-use loss/policy/reserve/Lucky/conditional counters согласованы; при отсутствии funding обычный Aim не даёт free shot до подхода NPC. Awareness Glorious в первом срезе отклоняется, остальные выбранные Glorious используют actual остаток ресурса/Lucky. CANNOT_AIM8/mandatory/hand/CI/endphase и прежний backup действуют. Setup prelude не выбран. Current JSON1/244старыхJSON/NPC59/shared14 сохраняются. [Статус](project-status.md).

## M69: Blunderbuss/nearby Staggered — решение принято

[ADR-0111](decisions/ADR-0111-pc-blunderbuss-cluster-and-nearby-stagger.md) реализован: выбрана одна initial NPC-группа, explicit fact/order и полный nearby Trait от HIT без требования primary Wound. Source/request snapshot закреплён в HIT; primary ACK→ordered impacts/GM ACK→continuation/terminal, без новых Attack/actions. PC вне волны по actual Short premises, не по отключению friendly fire. Раздельные окрестности/смешанные Close-группы не выбраны. Current JSON1/старые240JSON/NPC59/shared14 сохраняются. [Статус](project-status.md).

## M68: Sling/free reload/Close→backup — решение принято

[ADR-0110](decisions/ADR-0110-pc-sling-free-reload-and-close-backup.md) реализован: выбран Sling с optional shield и прежним melee backup. Strength Damage/free reload/Short−1d; запрет при любом Close enemy не зависит от рук. Weapon-first release предшествует draw при занятой preferred backup hand, затем прежний shield Recover. Один пригодный hand вне Close допускается, old1H firearms сохраняют Close/Reload. Current JSON1/236старыхJSON/NPC59/shared14 прежние; Medium opening/другие Zone/новые NPC policies не добавлены. [Статус](project-status.md).

## M67: оба Handgun, volley→backup — решение принято

[ADR-0109](decisions/ADR-0109-pc-handguns-opening-volley.md) реализован: оба2H firearms, явные Blackpowder facts, Handgun Short−1d/charge3 и Repeater optional+3d→charge5. Общий native PcRangedCloseUnsupported/ranged_close_enemy заменяет bow-specific имя без aliases. JSON1/агрегаты прежние, старые232JSON сохранены. Текущий первый volley→NPC approach→backup не означает полный fresh Reload cycle. Новых NPC policies, Aim, других Zone и оружий вне этого чанка нет. [Статус](project-status.md).

## M66: оба Crossbow, volley→backup — решение принято

[ADR-0108](decisions/ADR-0108-pc-crossbows-opening-volley-and-reload-state.md) реализован: пользователь выбрал Crossbow/Repeater Crossbow с прежним Short opening и подходом NPC. Armour Damage обычного Crossbow/Repeater modes/charges2vs3/no-cycle сохраняются; после Close active melee и retained primary state разделены. Optional authored armoured bool передаётся полно, canonical Net/book правила прежние. Для M66 решений пользователя больше не нужно. Это первый volley и melee continuation; fresh Shoot→Reload→Shoot для Crossbow не заявляется. Прежние228JSON/каталог59 сохранены. [Правило](rules/equipment.md#pc-crossbows-m66), [статус](project-status.md).

## M65: Short opening, три bows и backup — решение принято

[ADR-0107](decisions/ADR-0107-pc-bows-short-opening-and-melee-backup.md) реализован: пользователь выбрал Shortbow/Warbow/Longbow, Short внутри одной Zone, free NPC approach и one-way melee backup. Строгий source не разрешает bows в all-Close и не отключает PG94 restriction. Без backup — точный stop на реальном Shoot boundary; необходимый Recover/mandatory последствия сохраняют приоритет. Short-сцена ограничена simple authored numeric Minions; прежние Close loadouts/224JSON сохранены. Для закрытия M65 решений пользователя больше не нужно. [Правила](rules/equipment.md#pc-bows-m65), [статус](project-status.md).

## M64: оба Repeaters и generic PC ranged — решение принято

[ADR-0106](decisions/ADR-0106-pc-repeaters-and-generic-ranged-profile.md) реализован: пользователь выбрал Repeater Handbow/Repeater Pistol, when_available/never, общий PC ranged и прежние shield/backup. Handbow без firearm facts; bonus только до initial roll и без Drained, условный Reload3, normal shot без нового cycle. PC pistol key/API удалены, NPC pistol сохранён. Миграция36из220JSON точная, остальные184 побайтно прежние; каталог59. Для M64 открытых вопросов нет. Две пригодные руки для Reload — прежняя согласованная scenario policy, не новое RAW. [Правило](rules/equipment.md#pc-repeaters-m64), [статус](project-status.md).

## M63: PC Protection Skill и Melee Help — решение принято

[ADR-0105](decisions/ADR-0105-pc-close-shooting-protection-choice.md) реализован: пользователь выбрал optional Melee/Athletics и полный Melee Protection Help. Default без поля прежний; PG94 не требует weapon, fixed hand-use — actual usable active grip либо без рук. Protection Help адресуется по target, не смешивается с Melee Attack. Source/schema/owner/Traits/Fate/hand/replay/trials/search/CLI проверены;216прежнихJSON/59definitions сохранены. Вопросов для M63 нет. [Правило](rules/combat.md#pc-close-shooting-protection-m63), [статус](project-status.md).

## M62: NPC Help к Shooting — решение принято

[ADR-0104](decisions/ADR-0104-pc-npc-shooting-help.md) реализован: пользователь выбрал Militia и три Goblin/Night Goblin loadouts с Horde → оба NPC Pistol. Loaded → Help конкретному Shooting Test, empty/Reload → собственный Attack helper. Melee-only Abilities сохраняются, unused receipts не переназначаются, новых fields/schema/метрик нет. PC Protection Help не предсказывает NPC Help.212прежнихJSON/каталог59 сохранены, вопросов для M62 нет. [Правило](rules/npc-profile-catalog.md#npc-shooting-help-m62), [статус](project-status.md).

## M61: NPC Pistol и Reload — решение принято

[ADR-0103](decisions/ADR-0103-pc-npc-pistol-and-exacting-reload.md) реализован: пользователь выбрал оба Brute loadouts, initially loaded Shoot→Reload3→Shoot с explicit two-hand/Lore/kit/supplies facts. Official Broken/exit сохранены, Ogre Pistol имеет printed Close–Medium; без shield/carried melee/получения NPC Help. Новый closed per-enemy source действует только для canonical Official/Ogre, прежние208JSON сохранены. Вопросов для M61 нет. [Правило](rules/npc-profile-catalog.md#npc-pistol-reload-m61), [статус](project-status.md).

## M60: Pistol → melee backup — решение принято

[ADR-0102](decisions/ADR-0102-pc-pistol-melee-backup.md) реализован: пользователь выбрал fallback только при empty Pistol/одной пригодной руке, сохранив loaded shot и доступный Reload. Шесть1H backups/optional shield/Strength≥2, прежний existing policy без новых полей; собственный incidental draw после mandatory последствий, actual Melee и сохранённый Pistol state. Необходимые shield release/Recover и Critical сохраняются, пустой dropped gun не подбирается. Вопросов для закрытия M60 нет. [Правило](rules/equipment.md#pc-pistol-backup-m60), [статус](project-status.md).

## M59: Thief Stealth против Pistol

Закрыта последняя отдельная Protection eligibility case выбранного каталога57. Now You See Me GM103 разрешает aware Shooting; Pistol preflight теперь подтверждает существующий typed actor/full-definition permission. Printed Stealth3d5/cap6 сохраняется, Unaware/Defenceless не Opposes; исчезновение/кража автоматически не добавлены. Нет generic Stealth override и нового поля,12source Melee/Athletics policy прежняя. [Правило](rules/combat.md#pc-close-shooting-protection-m59), [статус](project-status.md).

## M58: special NPC Close Shooting Protection

Nasty Skulker, Brewguard/Warhammer, Miner/Pickaxe и Bestigor/Massive Axe подключены к прежней policy, всего12sources. Miner grudge — generic Melee bonus против focus, поэтому усиливает защитный Melee и подчиняется Drained; Distracted действует на Melee/Athletics против остальных. Brewguard focus/expiry сохраняется. GM144 Blood Rage прямо Attack-only, W1 Bestigor Glorious не расходуется opposition. Исправлены alternate Athletics caps Miner4/Bestigor8 ([CODE-CONFLICT-006](contradictions.md#code-conflict-006--athletics-caps-miner-и-bestigor-исправлено-2026-11-07)). Нового выбора тактики/поля нет. [Правило](rules/combat.md#pc-close-shooting-protection-m58), [статус](project-status.md).

## M57: Greenskin Close Shooting Protection

Orc Boy/Big ’Un Choppas/Spear без щитов добавлены по [образцу M56](decisions/ADR-0101-pc-close-shooting-npc-protection-choice.md): всего8разрешённых canonical sources, те же optional actor→Melee/Athletics policies. У всех WS3/Melee4/Ag3/Athletics3, оба cap6; Big ’Un Strength4 меняет Damage/injury type, не Melee cap. GM158 Help относится только к Attack Test; защитный Melee не получает/не расходует receipt. Новой существенной неоднозначности/тактики нет, отдельный ADR/поле не нужны. [Правило](rules/combat.md#pc-close-shooting-protection-m57), [фактический статус](project-status.md).

## M56: NPC Protection против Close Shooting

[ADR-0101](decisions/ADR-0101-pc-close-shooting-npc-protection-choice.md) принят и реализован: пользователь выбрал Melee+Athletics для State Trooper Halberd/Spear, unmounted no-shield Empire Knight/Lance и White Wolf/Wolf Hammer. Optional actor→Skill policy действует на Close Shooting, прежняя Defence от Melee сохраняется. Melee opposition не даёт counterattack/Attack bonuses. Knights Athletics2d/3/cap6 от Ag3 исправляет прежнюю невыбранную metadata с implicit4 ([CODE-CONFLICT-005](contradictions.md#code-conflict-005--cap-невыбранной-athletics-knights)). Другие NPC/Skills автоматически не разрешаются.188прежнихJSON и57выбранных definitions сохраняются.

## M55: Pistol со щитом — выбор тактики

[ADR-0100](decisions/ADR-0100-pc-pistol-shield-reload-priority.md) принят и реализован. Пользователь выбрал возврат щита отдельным Recover после завершения Reload. При пустом Pistol щит не подбирается, в том числе incidental interaction другого Recover; weapon pickup/снимаемый Prone сохраняют приоритет, release делается непосредственно перед доступным Reload. Existing weapon_first/restore_before_attack/two_available_hands выражают выбранную тактику без нового поля. Вариант leave_dropped не добавлен. Раны/недоступные руки/loaded shot сохраняют точные границы M53/M54.

## M54: Pistol, Reload и руки

[ADR-0099](decisions/ADR-0099-pc-pistol-and-exacting-reload.md) принят и реализован: loaded Pistol без shield/backup, Shooting наBS и Exacting Dexterity наInitiative,3successes Reload, явные Lore/Blackpowder Kit/supplies. Пользователь выбрал two_available_hands: это GM/scenario конкретизация, число рук Reload книга не задаёт. Loaded shot одной оставшейся рукой разрешён; stop возникает лишь при фактически нужном недоступном Reload на собственном незанятом ходу. NPC с неготовой lawful Protection против Shooting отвергаются до RNG. Pistol+Shield и release/Reload/pickup приоритеты добавлены в M55; weapon-hand-only не является допустимой альтернативой текущего source.

## M53: щит PC и конфликт рук

[ADR-0098](decisions/ADR-0098-pc-shield-and-hand-equipment.md) принят и реализован: полный weapon-first, отдельный standard Recover ради dropped shield при здоровой свободной руке, weapon pickup первым. Source только1H, no backup/2H shield.16/20 дают unavailable shield без выдуманного ground pickup; после12 shield травмированной рукой не поднимается. Generic passive injured-hand shielding, перенос2H shield и союзный pickup не определены этим срезом. Shield даёт+1Resilience и Defence против Throwing; Sword Trait требует действующего оружия, Brawn остаётся Endurance.

## M51: Great Stag, Crown и Trample

[ADR-0096](decisions/ADR-0096-pc-great-stag-crown-and-trample.md) принят и реализован. Пользователь выбрал Brawn/cap10 с PC Endurance, actual новый Prone от accepted Wound/failed Endurance первой Antlers Attack после Fate/mandatory consequences и Trample той же живой Prone цели без переназначения. Already-Prone grant не даёт. Эти три конкретизации действуют для данной карточки; general Brawn Protection исправлен по PG69. Charge/destination/riders и свободный ordinary Trample не подключены.

## M50: Bear/Crushing Weight

[ADR-0095](decisions/ADR-0095-pc-bear-crushing-weight-pre-stagger-prone.md) принят и реализован: полный Bear/Crushing Weight, early Prone/cap8 и прежний Enduring Strength. Обычный hit-Prone снимается self/ally Recover, не становится постоянным Drained-style cause и не меняет ongoing Wound-Prone. Новых полей верхнего уровня/метрик/версии нет;54прежнихпрофиля/164JSON сохранены.

Great Stag M51 использует отдельный Crown grant; Bear сохраняет different-target Enduring Strength.

## M49: Imperial Ogre и наземный Pegasus

[ADR-0094](decisions/ADR-0094-pc-imperial-ogre-cap-and-grounded-pegasus.md) принят: Ogre/Greathammer с Attack cap6 только canonical source и Pegasus с явным наземным началом/неподвижной сценой. W1 Pegasus уже находится на земле; это не общий landing executor. В будущей spatial сцене нужен настоящий ground/air state. Authored caps, Rough Shove/Mighty Throw/Charge и другие loadouts автоматически не разрешаются.

## Skin Wolf / Warped Form

[ADR-0093](decisions/ADR-0093-pc-skin-wolf-warped-form-end-phase.md) принят: одна собственная цена Staggered, волна остальным; первая wave-Wound Brewguard задаёт focus=Skin Wolf. Снятие NPC focus требует подтверждённого killed, а не любого defeat. Explicit Close list содержит всех PCs, NPC↔NPC Close задаётся отдельно. Полный путь реализован в M48; огневые/неизвестные начальные раны остаются вне physical source, общий regeneration AI этим не определяется.

## Продолжение Broken NPC

M24 задаёт конечный clear/fastest adjacent exit без преследования/Recover; пользователь выбрал успех, когда все NPC побеждены или ушли, с отдельным учётом ухода. При null policy остаётся stop M23. Открыты общий маршрут с препятствиями/Run/Manoeuvre, дальнейшее поведение и возможность снять Broken при сохраняющейся profile Wound. Аналогично, M26 не определяет будущий NPC Recover для снятия profile Staggered Merchant при сохраняющемся W1; то же ограничение будущей NPC recovery policy относится к White Wolf и Empire Knight в обоих loadouts, Knight of the White Wolf, Big ’Un, Bear и Demigryph с профильным Drained. Centigor M40 продолжает Attack с W1Prone; его будущий NPC Recover при сохраняющейся profile Wound также не определён. [Подробности](open-questions-details.md#продолжение-broken-npc).

## Weighted Net после M31

[M52 / ADR-0097](decisions/ADR-0097-pc-weighted-net-and-carried-spear.md) принят и реализован: одна Net + carried Spear, noShield/printed armoured; PC сохраняет Attack/standard Recover. По Defenceless или уже Burdened выбирается Spear, неброшенная Net сохраняется. В неподвижной сцене Burdened не ухудшает Attack/Protection. Generic Net→Defenceless precedence PG96/123 и отдельный PC Brawn Recover пока не выбраны и в M52 не исполняются; при последующем расширении отдельно сохранить Net/Wound/inventory causes. [Подробности](open-questions-details.md#weighted-net-после-m31).

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

M47 реализует [выбранные Flagellant policies](decisions/ADR-0092-pc-flagellant-feel-no-pain-and-recover.md): Feel No Pain при0Wounds и standard self Recover при1 с лечением. Оба выбора явные/независимые, `[]` сохраняет Attack-only/отказ от conversion; NPC Recover costs отдельные. M48 также разрешает Feel No Pain от Warped Form wave. Это не общий NPC recovery AI или campaign healing.

M46 реализует [выбранную Blood Rage policy](decisions/ADR-0091-pc-bestigor-blood-rage-and-wound-glorious.md): обязательный список Bestigors для добровольного Staggered перед Attack; `[]` отказывается только от acquisition, фактический Staggered сохраняет бонус. Следующая Attack после W1 Glorious однократно, выбран reroll всех доступных провалов; NPC не тратит PC Fate. Другие Blood Rage/регенерация других существ этим не подключаются.

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
