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

Встроенное оглавление указывает ключевые страницы для прототипа: Lucky — 78, `Rolling Dice` — 107, `Opposed Tests` — 109, Exacting Tests — 110, Fate/Second Action — 111, `Combat` — 112, `Hazards` и `Combat Actions` — 115–117, `Attack Tests` — 118, `Failed Attacks` и `Successful Attacks` — 119, Retreat — 120, `Wounds & Conditions` — 121, `Conditions` — 122–123. Страница 78 делает первую Fate-трату session бесплатной даже при rating `0`; gambling Tests всегда Glorious. Страница 111 разделяет rating/session spends, разрешает GM refresh после mid-session break и позволяет потратить Fate, чтобы сделать свою Test Glorious, в том числе после initial roll до определения исхода, но запрещает повторную трату и уже Glorious Test. Она же разрешает второе отличающееся action, но запрещает повтор, вторую attack и третье действие; два разных Improvise требуют разрешения GM. Страницы 111–112 определяют permanent burn: rating уменьшается на `1`, при пустом pool штраф к расходам начинается со следующей session; варианты — реалистичный `Unmitigated Success`, отменяющий только что полученную Wound `Near Miss` и смертельный после подвига `Last Stand`. Нормализованные обе части Lucky, refresh, Glorious, Second Action, Tactical Retreat, burn producers и application consumers всех трёх burn находятся в соответствующих fate/lucky domain и rules modules; Near Miss дополнительно переиспользуется общим character-Wound lifecycle. Страница 120 требует единогласного группового Retreat в одном из двух стартовых окон, Fate одного персонажа на rearguard либо GM-owned blood/materiel/misfortune price; возможная погоня затем разрешается отдельными Athletics Tests, Lore auto-success, optional opposition и таблицей Run For Your Lives. Group/rearguard, alternative-price proof/follow-up, общий pursuit и Run For Your Lives boundaries находятся в `domain/retreat_models.py` и `rules/retreat_resolution.py`; blood follow-up применяется через отдельные `retreat_blood_price` modules к явно выбранному PC и общему Wound/Near Miss lifecycle, materiel — через `retreat_materiel_price` modules к explicit valuable item минимального `inventory_models.py` snapshot, misfortune — через `retreat_misfortune_price` modules к explicit enemy и одной записи узкого `campaign_opportunity_models.py` aggregate. Outcome-bound регистрация Run For Your Lives находится в `campaign_consequence_models.py` и `run_for_your_lives_campaign_resolution.py`; `Robbed` дополнительно применяет explicit per-PC losses через `run_for_your_lives_robbed` modules. `Trapped` routing находится в `run_for_your_lives_trapped` modules: GM явно выбирает Wounds/capture/other branch и затронутых PC, но сами эффекты ещё не исполняются. Остальные эффекты таблицы не выводятся из prose автоматически. `rules/test_resolution.py` предоставляет immutable initial-roll snapshot/completion, а `rules/turn_resolution.py` принимает только slot-bound Fate proof. Страница 121 задаёт treatment и три healing tiers; конкретная категория каждой Wound сверяется с таблицей на страницах 190–191. Страница 122 требует в конце дня после любых Wounds, включая уже treated/healed, Endurance Test: successes сравниваются с числом дневных Wounds, недобор даёт одну Festering Wound; предшествующая Anatomy Recall может назначить автоматический успех себе/союзнику. Страница 123 определяет `Drained`: Test не получает bonus dice, Glorious разрешён только от Fate, penalties и Grim сохраняются. Страница 136 уточняет `Rest and Recovery`: успешная Endurance Test лечит одну Wound и все Festering Wounds. Страница 122 также задаёт ordinary Surgery с Anatomy Lore, facilities/tools/time/supports, Dexterity Test и неопределённым риском disfigurement/death; страница 74 отдельно определяет Combat Surgeon: дополнительную Recall Test после treatment для suppression ongoing effect до конца battle и Exacting Dexterity `8` surgery с одним Test за action. Нормализованные lifecycle sources и consumers находятся в recover/downtime/surgery/wound-healing/infection/infection-prevention/combat-surgeon/drained-test/exacting models/resolvers и покрыты treatment/healing/infection/surgery/Combat Surgeon/Drained test modules. Конкретные secondary effects: Troublemakers Out! — 31, Blunderbuss — 95, Noble Steed — 124; первый нормализованный составной психологический spell `Curse of Cowardly Flight` — 162.

Direct post-roll порядок Near Miss нормализован в `domain/wound_lifecycle_models.py` и `rules/wound_lifecycle_resolution.py`: первая фаза возвращает pending Wound, вторая выполняет выбранный burn либо окончательные daily registration и Wound effect. Kernel/Hazard adapters пока используют прежний immediate путь.

Уточнение для страницы 120: `run_for_your_lives_trapped_wound` modules уже исполняют Wounds-ветвь `Trapped` последовательно поверх этого direct lifecycle с явным GM-count для каждого affected PC. Формулировка выше о неисполненных эффектах `Trapped` теперь относится к Other branch и к производным последствиям captivity.

Capture-ветвь страницы 120 теперь регистрируется через `campaign_captivity_models.py` и `run_for_your_lives_trapped_capture` modules: один explicit captor reference на affected PC, без автоматического выбора enemy и без исполнения освобождения либо производных последствий. Other branch по-прежнему не применяется.

`Surrounded` страницы 120 теперь регистрируется через `campaign_conflict_models.py` и `run_for_your_lives_surrounded` modules как отдельный conflict-opportunity hook с exact opposition/encounter-setup references. Текст книги не преобразуется в автоматический battle start, negotiation/manoeuvre Test либо spatial placement.

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
