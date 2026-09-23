# Реестр источников

## BOOK-PLAYER-GUIDE

- Версия: `1.4` (подтверждено пользователем 2026-08-19).
- Предполагаемое название: *Warhammer: The Old World Roleplaying Game — Player’s Guide*.
- Файл: `Warhammer_the_Old_World_Roleplaying_Game_-_Players_Guide_-_29_01_26_opt.pdf`.
- Размер: `100991909` байт.
- SHA-256: `3090B91DD7B414B10C4D9F9A3BAC50CAEA1E5787CF3F86490BA4540C38EE127F`.
- PDF-страниц: `192`.
- PDF: не зашифрован, содержит встроенное оглавление и извлекаемый текстовый слой.
- Создан: `2025-11-19`, изменён `2026-02-04`; Adobe InDesign 21.0 / Adobe PDF Library 18.0.
- Издание: Cubicle 7 Entertainment / Games Workshop, copyright 2025; `Last Edited: 29th January 2026`.
- Язык: английский.
- Статус: актуальная редакция полностью извлечена и напрямую прочитана по всем страницам `1–192`; правила, guidance и lore классифицированы в `docs/audits/rulebooks-1.4-1.1.md`.
- Git: пользователь самостоятельно следит, чтобы исходный PDF не попал в репозиторий; проект не добавляет книгу в `.gitignore`.

### Подтверждённые исправления редакции

Текст страниц 157–159 проверен по локальной редакции от 29 января 2026 года. При Miscast теряются все накопленные Casting successes; доступное заклинание можно сотворить до броска таблицы, добавив к нему `+1d`. Исправленная Miscast Table использует непересекающиеся диапазоны `21–22` и `23–24`, чем закрывает `AMBIGUITY-003` старого файла от 23 июня 2025 года.

### Первичная карта

- страницы 4–9: вводный контекст и сеттинг;
- страницы 10–65: введение и создание персонажа;
- страницы 66–89: развитие, способности, таланты, знания и статус;
- страницы 90–105: снаряжение и имущество;
- страницы 106–130: основные правила, тесты, Fate, бой, раны, состояния, транспорт, исследования и социальные сцены;
- страницы 131–136: действия между приключениями;
- страницы 137–151: религия;
- страницы 152–174: магия;
- страницы 175–192: описание мира и индекс.

Встроенное оглавление указывает ключевые страницы для прототипа: Lucky — 78, `Rolling Dice` — 107, `Opposed Tests` — 109, Exacting Tests — 110, Fate/Second Action — 111, `Combat` — 112, `Hazards` и `Combat Actions` — 115–117, `Attack Tests` — 118, `Failed Attacks` и `Successful Attacks` — 119, Retreat — 120, `Wounds & Conditions` — 121, `Conditions` — 122–123. Страница 110 задаёт Opposed-вклад в Exacting Test: положительная разница successes, `1` за выигранный tie-break и отсутствие уменьшения running total при failure; `exacting_test` modules реализуют Basic/Opposed contributions с единым immutable progress и one-shot Test provenance. Страница 78 делает первую Fate-трату session бесплатной даже при rating `0`; gambling Tests всегда Glorious. Страница 111 разделяет rating/session spends, разрешает GM refresh после mid-session break и позволяет потратить Fate, чтобы сделать свою Test Glorious, в том числе после initial roll до определения исхода, но запрещает повторную трату и уже Glorious Test. Она же разрешает второе отличающееся action, но запрещает повтор, вторую attack и третье действие; два разных Improvise требуют разрешения GM. Страницы 111–112 определяют permanent burn: rating уменьшается на `1`, при пустом pool штраф к расходам начинается со следующей session; варианты — реалистичный `Unmitigated Success`, отменяющий только что полученную Wound `Near Miss` и смертельный после подвига `Last Stand`. Нормализованные обе части Lucky, refresh, Glorious, Second Action, Tactical Retreat, burn producers и application consumers всех трёх burn находятся в соответствующих fate/lucky domain и rules modules; Near Miss дополнительно переиспользуется общим character-Wound lifecycle. Страница 120 требует единогласного группового Retreat в одном из двух стартовых окон, Fate одного персонажа на rearguard либо GM-owned blood/materiel/misfortune price; возможная погоня затем разрешается отдельными Athletics Tests, Lore auto-success, optional opposition и таблицей Run For Your Lives. Group/rearguard, alternative-price proof/follow-up, общий pursuit и Run For Your Lives boundaries находятся в `domain/retreat_models.py` и `rules/retreat_resolution.py`; blood follow-up применяется через отдельные `retreat_blood_price` modules к явно выбранному PC и общему Wound/Near Miss lifecycle, materiel — через `retreat_materiel_price` modules к explicit valuable item минимального `inventory_models.py` snapshot, misfortune — через `retreat_misfortune_price` modules к explicit enemy и одной записи узкого `campaign_opportunity_models.py` aggregate. Outcome-bound регистрация Run For Your Lives находится в `campaign_consequence_models.py` и `run_for_your_lives_campaign_resolution.py`; `Robbed` дополнительно применяет explicit per-PC losses через `run_for_your_lives_robbed` modules. `Trapped` routing находится в `run_for_your_lives_trapped` modules: GM явно выбирает Wounds/capture/other branch и затронутых PC; Wounds исполняются через общий lifecycle, Capture регистрирует active captivity, а Other сохраняет opaque GM-defined cost без его интерпретации. Остальные эффекты таблицы не выводятся из prose автоматически. `rules/test_resolution.py` предоставляет immutable initial-roll snapshot/completion, а `rules/turn_resolution.py` принимает только slot-bound Fate proof. Страница 121 задаёт treatment и три healing tiers; конкретная категория каждой Wound сверяется с таблицей на страницах 190–191. Страница 122 требует в конце дня после любых Wounds, включая уже treated/healed, Endurance Test: successes сравниваются с числом дневных Wounds, недобор даёт одну Festering Wound; предшествующая Anatomy Recall может назначить автоматический успех себе/союзнику. Страница 123 определяет `Drained`: Test не получает bonus dice, Glorious разрешён только от Fate, penalties и Grim сохраняются. Страница 136 уточняет `Rest and Recovery`: успешная Endurance Test лечит одну Wound и все Festering Wounds. Страница 122 также задаёт ordinary Surgery с Anatomy Lore, facilities/tools/time/supports, Dexterity Test и неопределённым риском disfigurement/death; страница 74 отдельно определяет Combat Surgeon: дополнительную Recall Test после treatment для suppression ongoing effect до конца battle и Exacting Dexterity `8` surgery с одним Test за action. Нормализованные lifecycle sources и consumers находятся в recover/downtime/surgery/wound-healing/infection/infection-prevention/combat-surgeon/drained-test/exacting models/resolvers и покрыты treatment/healing/infection/surgery/Combat Surgeon/Drained test modules. Конкретные secondary effects: Troublemakers Out! — 31, Blunderbuss — 95, Noble Steed — 124; первый нормализованный составной психологический spell `Curse of Cowardly Flight` — 162.

Страницы 94–95 задают Optimum/Maximum Range, Damage, hands, отдельные weapon Traits и Reload как Exacting Dexterity Test с одной Test за action и weapon-specific целями `2–5`; отсутствие числа означает бесплатную подготовку в составе attack. Repeater даёт необязательный бонус к одному Shooting Test и требует указанную перезарядку именно после его применения. Страница 114 относит Extreme Range к GM-approved Aim, а страницы 116–117 задают Aim и action context. `ranged_weapon_profiles.py` фиксирует полный combat-каталог всех 13 строк, вычислимую Max Range и отдельный reload-подкаталог с тремя triggers; combat-запись ссылается на reload profile того же weapon ID без копирования его значений. `ranged_weapon_attack_preparation` modules применяют профиль к одному Attack без RNG: проверяют range/Lore/Aim, добавляют точные modifiers/effects и после этого создают optional Aim follow-up и готовый unified request. `reload_models.py`, `reload_resolution.py` и ranged executors сохраняют прежний one-kernel/one-receipt transition. `prepared_ranged_weapon_attack` modules требуют завершённую подготовку, сохраняют полный trace и выбирают ровно один unified либо Aim-bound execution с immutable consumption chain. Проверка Max Range Long для всех `1H` исправлена по странице 94: Aim/GM approval не обходят этот предел. Обязательный `has_enemy_in_close_range` реализует запрет Equipment (стр. 94) независимо от дистанции цели; таблица стр. 95 даёт исключение Pistol, Repeater Pistol и Repeater Handbow. Проверка сохраняется в preparation/execution trace под `RULE-EQUIPMENT-004:close-enemy-restriction`. Nearby targets, ammunition и spatial-поиск врагов остаются внешними.

Aim страницы 116 уже нормализует Awareness successes в bonus dice следующей ranged Attack. `aim_ranged_weapon_attack` modules принимают результат этой подготовки только для Shooting, требуют exact prepared Attack, один раз исполняют profile-aware weapon path и ведут отдельную consumed-follow-up chain. Aim и Repeater modifiers остаются обычными и вместе подчиняются общему pool cap; нулевой Aim result также считается использованным. Это orchestration-связывание не вводит нового толкования книжного правила. `prepared_hidden_ranged_attack` modules соединяют final preparation с Move Quietly (Rules / Manoeuvre, стр. 117) и одним prepared execution, сохраняя hidden/Aim chains. Сверка Rules / Manoeuvre и Attack Tests, стр. 117–118 привела к исправлению `CODE-CONFLICT-001`: `hidden_continuation` modules сохраняют opportunity после completed non-attacking action, если позиция не оставлена и explicit раскрытия нет. Aim и hidden сохраняют разные условия продолжения; `OTHER_ACTION` удалён. `test_k1_hidden_continuation_resolution.py` проверяет правила и цепочку следующего раунда.

Direct post-roll порядок Near Miss нормализован в `domain/wound_lifecycle_models.py` и `rules/wound_lifecycle_resolution.py`: первая фаза возвращает pending Wound, вторая выполняет выбранный burn либо окончательные daily registration и Wound effect. Kernel/Hazard adapters пока используют прежний immediate путь.

Уточнение для страницы 120: `run_for_your_lives_trapped_wound` modules исполняют Wounds-ветвь `Trapped` последовательно поверх direct lifecycle с явным GM-count для каждого affected PC. Конкретное исполнение opaque Other price и производные последствия captivity остаются внешними.

Capture-ветвь страницы 120 регистрируется через `campaign_captivity_models.py` и `run_for_your_lives_trapped_capture` modules: один explicit captor reference на affected PC, без автоматического выбора enemy и без исполнения освобождения либо производных последствий. Other branch регистрируется через `campaign_trapped_other_models.py` и `run_for_your_lives_trapped_other` modules как exact opaque GM-defined cost без универсального effect payload.

`Surrounded` страницы 120 теперь регистрируется через `campaign_conflict_models.py` и `run_for_your_lives_surrounded` modules как отдельный conflict-opportunity hook с exact opposition/encounter-setup references. Текст книги не преобразуется в автоматический battle start, negotiation/manoeuvre Test либо spatial placement.

`Hunted` страницы 120 теперь использует `campaign_hunt_models.py` и `run_for_your_lives_hunted` modules: outcome создаёт inactive threat с explicit pursuer/activation-trigger references, а отдельная фаза активирует её по stable movement-event reference. Текст не превращается в автоматический таймер укрытия, detection, route либо новый pursuit.

`Indebted` страницы 120 теперь использует `campaign_debt_models.py` и `run_for_your_lives_indebted` modules: exact creditor/debt/repayment references сохраняются как outstanding obligation. Текст не превращается в автоматическую сумму, услугу, deadline, санкцию или repayment transition.

`Mocked` страницы 120 теперь использует `campaign_reputation_models.py` и `run_for_your_lives_mocked` modules: непустой ordered witness/rival snapshot и exact gossip/reputation-effect references сохраняются как reputation consequence. Текст не превращается в numeric penalty, social propagation, duration или recovery.

`Lost` страницы 120 теперь использует `campaign_delay_models.py` и `run_for_your_lives_lost` modules: exact unfamiliar-territory/intended-destination/return-delay/enemy-opportunity references сохраняются как delay consequence. Текст не превращается в automatic route, duration, spatial relocation, calendar advance или enemy action.

`Marked` страницы 120 теперь использует `campaign_enemy_readiness_models.py` и `run_for_your_lives_marked` modules: outcome создаёт pending readiness с explicit enemy/acquired-intelligence/next-action-trigger references, а отдельная фаза фиксирует первый matching action event. Текст не превращается в автоматический bonus, ambush, encounter либо enemy-AI решение.

`Exposed` страницы 120 теперь регистрируется через `campaign_intelligence_models.py` и `run_for_your_lives_exposed` modules: exact enemy/home/shelters/weakness references сохраняются как disclosure, но атака, target, encounter timing и числовой эффект из prose не выводятся.

### Извлечение

- приватный каталог: `references/private/player-guide-extracted/`;
- страниц с текстом: `192/192`;
- всего извлечено около `607021` символов;
- элементов встроенного оглавления: `188`;
- содержимое каталога игнорируется Git.

После первичного извлечения сюда добавляется карта глав и диапазонов страниц с пометками `rules`, `lore`, `examples`, `tables` и `needs_visual_review`.

## BOOK-GM-GUIDE

- Версия: `1.1` (подтверждено пользователем 2026-08-19).
- Название: *Warhammer: The Old World Roleplaying Game — Gamemaster’s Guide*.
- Файл: `Warhammer_the_Old_World_Roleplaying_Game_-_Gamemasters_Guide_-29_01_26_opt.pdf`.
- Размер: `98333170` байт.
- SHA-256: `A920C1893D75A38E569D33153D74EB5735410685BA3ADEEAE23E24239AFC7055`.
- PDF-страниц: `192`.
- PDF: не зашифрован, содержит встроенное оглавление и извлекаемый текстовый слой.
- Создан: `2025-11-19`, изменён `2026-02-04`; Adobe InDesign 21.0 / Adobe PDF Library 18.0.
- Издание: Cubicle 7 Entertainment / Games Workshop, copyright 2025; `Last Edited: 29th January 2026`.
- Язык: английский.
- Статус: актуальная редакция полностью извлечена и напрямую прочитана по всем страницам `1–192`; правила, guidance и lore классифицированы в `docs/audits/rulebooks-1.4-1.1.md`, NPC profiles проиндексированы в `docs/rules/npc-profile-catalog.md`.
- Git: приватный извлечённый текст находится под `references/private/` и игнорируется; пользователь самостоятельно исключает исходный PDF из коммитов.

### Первичная карта

- страницы 6–41: Talagaad, приключения и Contacts;
- страницы 42–65: руководство GM, построение кампаний и приключений, подготовка и баланс боя, применение правил;
- страницы 66–80: события и Corruption;
- страницы 81–90: магические предметы;
- страницы 91–187: типы NPC, формат профилей, фракции, противники и монстры;
- страницы 188–192: индекс и краткие справочные таблицы.

Ключевые страницы для проекта: `Preparing for Battle` — 60, `Balancing Encounters` — 62, `Types of NPC` — 91–92. Magic Resistance Talent и общее определение Spell Potency находятся на страницах 78 и 157 Player’s Guide; магическое противодействие и Rule of Nine — на страницах 74 и 157; порог, подготовка, бросок и таблица Miscast — на страницах 157–159. Психологическая невосприимчивость undead-профилей повторяется на страницах 168–174 GM Guide; Monstrous Regeneration — на страницах 153 и 183; Undead Monstrosity и Bone Dragon — на странице 174; Monstrous Flight — на страницах 177, 179–180; Soporific Breath — на странице 179; Foul Stench — на странице 180; Stone Troll, Troll Stupidity, Regeneration и Vomit — на странице 182; Troll Hag Swamp Breath и Mother Knows Best — на странице 183; Giant Unsteady — на странице 185.

### Извлечение

- приватный каталог: `references/private/gamemaster-guide-extracted/`;
- страниц с текстом: `192/192`;
- всего извлечено около `624921` символов;
- элементов встроенного оглавления: `211`;
- содержимое каталога игнорируется Git.

## Проверка скрытой атаки 2026-09-22

Повторно непосредственно прочитаны `references/private/player-guide-extracted/pages/0117.txt` и `0118.txt` (BOOK-PLAYER-GUIDE 1.4, Rules / Manoeuvre и Attack Tests). Страница 118 связывает раскрытие присутствия с атакой по unaware target без условия попадания и требует Move Quietly к новому hiding spot. Модули hiding_position_models/resolution реализуют регистрацию после трёх hidden executors и передачу actor-scoped истории следующей preparation. Источник достаточен; новых house rules не введено.

В продолжении среза страница 118 повторно проверена непосредственно: composite `execute_registered_hidden_attack` сохраняет то же раскрытие при hit/miss. Изменение касается порядка history preflight → execution → registration, новых игровых правил нет.

Хронология hidden Attack сверена напрямую по страницам 117–118 той же локальной редакции: Move Quietly предоставляет следующую атаку из сохранённой позиции, а не атаку из предшествующего round/slot. Общий preflight теперь проверяет строгий порядок `(round, slot)`; собственного срока истечения книга здесь не задаёт, поэтому нового round-limit нет.

Source-slot binding сверено по тому же нормативному фрагменту Rules / Manoeuvre, стр. 117: hidden Attack использует результат конкретной успешной Move Quietly. Проверка receipt относится к техническому подтверждению source result и не меняет условие следующей атаки или срок жизни opportunity.

## Проверка hidden lifecycle 2026-09-23

Повторно непосредственно сверены BOOK-PLAYER-GUIDE 1.4, Rules / Manoeuvre, стр. 117, и Attack Tests, стр. 118, по локальным pages/0117.txt и 0118.txt. Новый HiddenLifecycleState объединяет уже реализованные source/opportunity/history snapshots и не меняет условие следующей атаки или нового укрытия. Continuation и registered Attack переиспользуют прежние reducers; нового expiry, awareness policy или house rule нет.

Standalone loss → lifecycle сверено по тем же локальным страницам 117–118: связь возможности с исходной позицией и unaware target остаётся прежней. Новый adapter переносит существующую loss-классификацию в actor state, не выполняет Attack и не регистрирует used hiding position. Нового правила раскрытия либо вычисления awareness нет.

Move Quietly → lifecycle adapter проверен по локальному BOOK-PLAYER-GUIDE 1.4, Rules / Manoeuvre, стр. 117: скрытие и next-unopposed-attack возникают после успешного Stealth и использования cover/concealment. FAILED и явный отказ от укрытия завершают действие без hidden opportunity. Общий action receipt и conditional movement переиспользованы из прежнего executor; новые игровые условия не вводились.

Completed free movement → hidden loss непосредственно сверено по локальным pages/0116.txt, 0117.txt и 0118.txt BOOK-PLAYER-GUIDE 1.4: Rules / Combat Actions, стр. 116 — один free move за turn; Manoeuvre, стр. 117 — следующая атака из исходной позиции; Attack Tests, стр. 118 — новое укрытие после атаки. Новый consumer доказывает уход в другую Zone и не считает его атакой или раскрытием для used-position history. Более поздний round нужен для нового free move, а не как срок истечения hidden opportunity.

Атомарный free-movement → hidden lifecycle executor повторно сверён по локальным pages/0116.txt, 0117.txt, 0118.txt (BOOK-PLAYER-GUIDE 1.4, Rules / Combat Actions, Manoeuvre, Attack Tests, стр. 116–118). Новых игровых условий нет: прежние movement и position-bound loss объединены без второго движения или action receipt.

Completed Give Ground → hidden loss непосредственно сверено по локальным pages/0117.txt и 0119.txt BOOK-PLAYER-GUIDE 1.4: Rules / Manoeuvre, стр. 117 — unopposed attack из исходной позиции; Giving Ground, стр. 119 — перемещение в соседнюю Zone, собственный once-per-round limit и Broken при входе к врагу. Отдельный consumer не переисполняет movement/Condition. Same-round exact-snapshot guard является технической границей подтверждения последовательности, не правилом книги.

Атомарный Give Ground → hidden lifecycle executor повторно сверён по локальным pages/0117.txt и 0119.txt BOOK-PLAYER-GUIDE 1.4, Rules / Manoeuvre, стр. 117; Giving Ground, стр. 119. Общий movement resolver сохраняет собственный round limit, ограничения пути и Broken; composition не меняет книгу, awareness или историю использованных укрытий.

Same-round movement chain повторно сверена по локальным pages/0117.txt и 0119.txt BOOK-PLAYER-GUIDE 1.4, Rules / Manoeuvre, стр. 117; Giving Ground, стр. 119. Позиция владельца сохраняется до его Give Ground; промежуточные движения других actor лишь подтверждают spatial continuity. Chain не создаёт игровых условий, awareness или нового движения.

Для следующего интеграционного сценария непосредственно проверена pages/0122.txt, BOOK-PLAYER-GUIDE 1.4, Rules / Conditions / Broken, стр. 122: после Broken нужно уйти в Zone без врага, затем доступен Recover с Willpower. План продолжения не предполагает новую Move Quietly/Attack до разрешённого снятия Broken.

Для сквозного hidden recovery cycle непосредственно сверены локальные PG 1.4 pages/0116.txt (Rules / Aim), 0118.txt (Attack Tests), 0122.txt (Conditions / Broken) и 0095.txt (Equipment / Ranged Weapons, Crossbow). Сценарий соблюдает уход в безопасную Zone перед Recover/Willpower, отсутствие действий между Aim и атакой, unopposed unaware Attack и обязательную перезарядку Crossbow после выстрела. Связанные Move Quietly/Give Ground ранее сверены по стр. 117/119.

Для продолжения hidden recovery cycle через Reload непосредственно перечитаны локальные BOOK-PLAYER-GUIDE 1.4 pages/0094.txt и 0095.txt (Equipment / Ranged Weapons: отдельное действие на Dexterity Test, Crossbow требует 2 успеха), 0110.txt (Rules / Exacting Tests: накопление успехов, failure не уменьшает progress) и 0118.txt (Rules / Attack Tests: новое hiding spot для следующей unopposed атаки). Проверки используют эти правила без новых допущений.

Для неатакующих ветвей после Reload непосредственно перечитана локальная BOOK-PLAYER-GUIDE 1.4 pages/0117.txt, Rules / Manoeuvre, стр. 117: Move Quietly — Stealth против наиболее бдительного врага; скрытие требует успеха и использования укрытия через free move. FAILED и явный DECLINE не создают hidden opportunity. Регистрация позиции остаётся следствием последующей атаки (Rules / Attack Tests, стр. 118, ранее непосредственно проверена). Новых игровых допущений нет.

Для Reload при активном скрытии повторно непосредственно сверены локальные BOOK-PLAYER-GUIDE 1.4 pages/0094.txt (Equipment / Ranged Weapons: каждое Dexterity Test требует action), 0117.txt (Rules / Manoeuvre: следующая атака из данной позиции) и 0118.txt (Rules / Attack Tests: раскрытие атакой, новое укрытие для следующей такой атаки). Crossbow target 2 ранее проверен по стр. 95. Неатакующее действие Reload само по себе не является книжным основанием потери opportunity; отсутствие раскрытия передаётся явно, не вычисляется.

Для сценария раскрытия при Reload непосредственно перечитаны локальные BOOK-PLAYER-GUIDE 1.4 pages/0094.txt и 0095.txt (Equipment / Ranged Weapons: отдельные Dexterity actions и Crossbow target 2), 0117.txt и 0118.txt (Rules / Manoeuvre и Attack Tests: скрытие и unaware attack). Книга не объявляет Reload автоматическим раскрытием; тест передаёт отдельный explicit fact. Для следующего шага также проверена pages/0116.txt, Rules / Aim: другие действия между Aim и ranged Attack лишают её бонуса.

Для Aim → Reload → hidden Attack непосредственно перечитаны локальные BOOK-PLAYER-GUIDE 1.4 pages/0116.txt (Rules / Aim: бонус требует отсутствия других действий до атаки) и 0117.txt (Rules / Manoeuvre: следующая атака из укрытия). Они задают разные условия продолжения: завершённый Reload является промежуточным действием для Aim, но без ухода/раскрытия не расходует hidden opportunity. Reload и Crossbow target 2 ранее проверены по Equipment / Ranged Weapons, стр. 94–95.

Для Aim loss consumer непосредственно перечитана локальная BOOK-PLAYER-GUIDE 1.4 pages/0116.txt, Rules / Combat Actions / Aim, стр. 116: любое промежуточное действие отменяет бонус. Проверка chronology и история source IDs — техническое подтверждение однократного применения готового LOST, а не новое игровое правило. Receipt следующего действия выбирает caller; consumer не вычисляет порядок всего боя.

Для подготовки ranged Attack с Aim history непосредственно перечитана BOOK-PLAYER-GUIDE 1.4 pages/0116.txt, Rules / Aim, стр. 116. Уже погашенный исходный Aim не должен снова создавать бонус при переименовании preparation/follow-up; новый guard проверяет canonical source ID. Это enforcement существующей потери после промежуточного действия, не новое правило или автоматическое определение next action.

Для регистрации APPLIED Aim непосредственно перечитана BOOK-PLAYER-GUIDE 1.4 pages/0116.txt, Rules / Aim, стр. 116: бонус относится к следующей ranged Attack по выбранной цели, без промежуточных действий. Правило не ставит расход Aim в зависимость от попадания или положительного числа Awareness successes; consumer регистрирует completed result для всех исходов. Технический source/prefix guard не вводит новое игровое правило.

Для атомарного Aim-bound execution+registration 2026-09-24 непосредственно перечитана локальная BOOK-PLAYER-GUIDE 1.4 pages/0116.txt, Rules / Combat Actions / Aim, стр. 116. Новая композиция переносит те же проверки actor/source/prefix/chronology перед единственным исполнением Attack и последующей регистрацией. Источник достаточен; правила бонуса и следующего действия не изменены, новых house rules нет.

Для prepared Aim execution+registration 2026-09-24 непосредственно перечитана локальная BOOK-PLAYER-GUIDE 1.4 pages/0116.txt, Rules / Combat Actions / Aim, стр. 116. Новый adapter сохраняет прежнюю подготовку оружия и регистрирует готовый nested Aim result после единственного prepared исполнения. Он не меняет правило бонуса, условия следующего действия или профиль оружия. Новых house rules и пробелов источника для этого связывания нет.

Для совместной регистрации Aim и раскрытого укрытия 2026-09-24 непосредственно перечитаны локальные BOOK-PLAYER-GUIDE 1.4 pages/0116.txt–0118.txt: Rules / Combat Actions / Aim, стр. 116; Manoeuvre / Move Quietly, стр. 117; Attack Tests, стр. 118. Aim относится к следующей ranged Attack без промежуточных действий; hidden opportunity — к следующей атаке из позиции; атака раскрывает присутствие и требует нового hiding spot независимо от hit/miss. Новый adapter связывает прежние исполнение и consumers без изменения этих правил. Источники достаточны, новых house rules нет.

Для подключения совместного hidden/Aim исполнения к lifecycle 2026-09-24 непосредственно сверены локальные BOOK-PLAYER-GUIDE 1.4 pages/0116.txt–0118.txt: Rules / Aim, стр. 116; Manoeuvre / Move Quietly, стр. 117; Attack Tests, стр. 118. Проверка exact active source и histories подтверждает уже существующие правила перед единственной атакой; lifecycle consumer переносит готовую регистрацию. Правила срока жизни Aim/hidden opportunity и раскрытия не менялись, источники достаточны.

Для интеграции второго свежего Aim 2026-09-24 непосредственно перечитаны локальные BOOK-PLAYER-GUIDE 1.4 pages/0094.txt–0095.txt (Equipment / Ranged Weapons: каждое Reload Test требует action, Crossbow — 2 успеха), 0116.txt (Rules / Aim: бонус к следующей ranged Attack по выбранной цели без промежуточных действий), 0117.txt–0118.txt (Manoeuvre / Move Quietly и Attack Tests: следующая атака из позиции и новое укрытие после раскрытия атакой). Сценарий исполняет новый Aim после Reload/нового скрытия и переносит существующие histories; production rules не менялись. Та же стр. 116 достаточна для следующего consumer LOST при Attack по другой цели.

Для consumer LOST после Attack по другой цели 2026-09-24 непосредственно перечитана локальная BOOK-PLAYER-GUIDE 1.4 pages/0116.txt, Rules / Combat Actions / Aim, стр. 116. Бонус относится к следующей ranged Attack по выбранной цели без других действий между ними. Регистрация готового LOST сохраняет это правило, включая нулевой бонус и hit/miss; actor/receipt/chronology/history guards являются подтверждением однократного применения, не house rule. Источник достаточен.

Для атомарной ordinary Attack с LOST Aim 2026-09-24 непосредственно перечитана локальная BOOK-PLAYER-GUIDE 1.4 pages/0116.txt, Rules / Combat Actions / Aim, стр. 116. Новый wrapper переносит прежние source/actor/target/chronology guards до RNG и регистрирует единственный completed result. Книжное правило выбранной цели и следующего действия не менялось; источник достаточен, новых house rules нет.

Для интеграции смены цели Aim 2026-09-24 непосредственно перечитана локальная BOOK-PLAYER-GUIDE 1.4 pages/0116.txt, Rules / Combat Actions / Aim, стр. 116. Сценарий Aim по A → Attack по B / LOST → свежий Aim по A → APPLIED проверяет существующее правило выбранной цели и следующего действия; нового нормативного материала не требуется.

Для same-target Melee Aim LOST 2026-09-24 непосредственно перечитаны локальные BOOK-PLAYER-GUIDE 1.4 pages/0116.txt (Rules / Combat Actions / Aim, стр. 116) и 0118.txt (Rules / Attack Tests, стр. 118). Aim относится к следующей ranged Attack без промежуточных действий; Melee — skill атаки оружием ближнего боя. Регистрация LOST для Melee по исходной цели следует прежнему правилу Aim; источники достаточны.

Для same-target Brawn Aim LOST 2026-09-24 непосредственно перечитаны BOOK-PLAYER-GUIDE 1.4 pages/0116.txt (Rules / Combat Actions / Aim, стр. 116) и 0118.txt (Rules / Attack Tests, стр. 118). Brawn назван skill безоружной атаки; такая Attack не является ranged и расходует Aim без его бонуса даже по исходной цели. Источник достаточен; правило Charge не пересматривалось.

Для same-target Melee/Brawn Aim integration 2026-09-24 непосредственно перечитаны локальные BOOK-PLAYER-GUIDE 1.4 pages/0116.txt (Rules / Aim, стр. 116), 0118.txt (Recover и Attack Tests, стр. 118), 0119.txt (Failed/Successful Attacks, стр. 119). Использованы нормативные абзацы об Aim, снятии Staggered с self/Close ally, Staggered атакующего при close miss и цели при Damage ≤ Resilience; combat example не служил самостоятельным основанием.

Для completed Melee Charge Aim LOST 2026-09-24 непосредственно перечитаны BOOK-PLAYER-GUIDE 1.4 pages/0116.txt (Rules / Aim, стр. 116) и 0117.txt (Manoeuvre / Charge, стр. 117). Charge — действие с движением и атакой, которое прерывает Aim; +1d Melee Charge остаётся отдельным бонусом. Источники достаточны, Brawn/Charge ruling не затрагивался.

Для атомарного ordinary Melee Charge с LOST Aim 2026-09-24 непосредственно перечитаны локальные BOOK-PLAYER-GUIDE 1.4 pages/0116.txt (Rules / Aim, стр. 116) и 0117.txt (Manoeuvre / Charge, стр. 117). Общий guard переносит проверку расхода Aim до движения/RNG; новое толкование Charge или Aim не вводится.

Для Aim → Melee Charge/LOST → свежий Aim → APPLIED integration 2026-09-24 непосредственно перечитаны локальные BOOK-PLAYER-GUIDE 1.4 pages/0116.txt (Rules / Aim, стр. 116), 0117.txt (Manoeuvre / Charge, стр. 117), 0118.txt (Recover, стр. 118), 0119.txt (Failed/Successful Attacks, стр. 119). Нормативные условия Aim, движения/бонуса Charge и Staggered/Recover достаточны; автоматическая awareness не требуется — обе атаки fixture opposed.
