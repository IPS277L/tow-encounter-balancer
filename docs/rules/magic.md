# Магия

Основной источник: `BOOK-PLAYER-GUIDE`, страницы 78, 152–174. Статус: полный casting/action pipeline остаётся `draft`; первые детерминированные effect/preflight-фазы реализованы в K1.

## RULE-MAGIC-006 — публичная магия и Magical Panic

Публичное применение магии привлекает внимание и, как правило, пугает обычных свидетелей. Если GM нужна быстрая преувеличенная реакция толпы, он может бросить `d10`:

| d10 | Реакция |
|---:|---|
| 1–2 | один свидетель падает в обморок |
| 3–4 | крики; часть убегает, часть молится |
| 5–6 | большинство убегает, немногие бросают в мага подручные предметы |
| 7–9 | толпа убегает, затем возвращается с факелами и вилами |
| 10 | большинство убегает, один свидетель просит обучить его магии |

Таблица является опциональным GM random event, а не автоматическим последствием каждого spell. Она не задаёт боевые профили толпы, дальность или время возвращения.

Источник: Gamemaster’s Guide 1.1, страница 60.

## RULE-MAGIC-005 — Wizard и схема spell

В главе слово Wizard обозначает любое существо, способное cast spell, независимо от традиционного названия. Wizard Talent и известные Magic Lores определяют доступ к созданным/изученным spells и пределы effects.

Каждый spell задаёт:

- `CV` — необходимое число casting successes; любой Wizard Level с нужной Lore может выучить formal spell любого CV;
- `Target` — обязательный валидный subject (`Self`, `Creature`, `Zone`, `Object` либо иной явно указанный тип);
- `Range` — target за пределами недопустим;
- `Duration` — момент окончания; `Battle` означает несколько минут/текущую ситуацию.

Источник: Player’s Guide 1.4, страница 155. Страницы 152–154 классифицированы как `LORE/SETTING`: преследование Wizards, Hexenguilde, Dhar и восемь Winds сами по себе не создают Test modifiers или corruption без отдельного правила.

## RULE-MAGIC-001 — Curse of Cowardly Flight

Источник: Player’s Guide, страница 162.

Заклинание мгновенно воздействует на всех врагов в выбранной Zone через их разум и страх. Каждая цель:

1. немедленно выполняет Give Ground, если может;
2. затем проходит Willpower Test;
3. при числе успехов меньше Potency получает Broken.

Описания «reach into the minds» и «tapping into their fears» классифицируют весь источник как `PSYCHOLOGICAL`. Совпавший `EffectImmunity` отменяет для конкретной цели всё заклинание до движения и Test, а не только итоговый Broken. `Willpower` сам по себе такой классификации не создаёт — она следует из источника.

K1 принимает одну уже выбранную цель как `CowardlyFlightRequest`. Spatial orchestration отвечает за врагов в Zone, их стабильный порядок, актуальную возможность Give Ground, Willpower-профиль и injury state. Resolver выполняет source-level preflight и при отсутствии блокировки создаёт упорядоченные follow-up:

- `GiveGroundRequest`, только если движение возможно;
- `CowardlyFlightWillpowerRequest` всегда, даже если Give Ground невозможен.

Второй resolver вызывается после исполнения предыдущего movement follow-up. Успехи, равные Potency, достаточны для сопротивления; при недостатке успехов общий Condition reducer добавляет Broken и сохраняет Rule ID заклинания. Проверка casting value, выбор Zone, расход действия, Miscast и исполнение пространственного перемещения не входят в этот срез.

## RULE-MAGIC-002 — target-scoped изменение Potency

Potency уже успешно сотворённого заклинания равна числу успехов последнего Casting Test. Magic Resistance (Player’s Guide, страницы 78 и 157) уменьшает Potency любого заклинания, затрагивающего обладателя, на 1; при результате 0 заклинание не оказывает эффекта.

`SpellPotencyRequest` получает исходную положительную Potency, конкретный `target_id` и уникальные source-aware `SpellPotencyModifier`. Чистый reducer суммирует изменения, ограничивает итог снизу нулём и возвращает исходное значение, delta, effective Potency, `has_effect` и применённые Rule IDs. Он вызывается после успешного Casting Test, но до любого эффекта заклинания для этой цели. Если `has_effect=False`, orchestration не создаёт последующие spell-effect запросы.

K1 временно трактует Potency как эффективное значение отдельно для защищённой цели: присутствие Stone Troll среди нескольких целей не ослабляет то же заклинание для остальных. Неоднозначность формулировки зафиксирована как `AMBIGUITY-002`.

## RULE-MAGIC-003 — Rule of Nine при магическом противодействии

Любая девятка на Casting Test немедленно добавляет куб в Miscast Pool мага и не может быть переброшена даже на Glorious Test. Willpower Tests для противодействия сотворению, рассеивания или поддержания заклинаний создают Miscast dice тем же способом. Источник: Player’s Guide, страницы 74 и 157.

В текущем K1 общий `NpcWizardCastingOppositionRequest` принимает уже завершённый `OpposedTestResult`, где Casting Test расположен со стороны initiator, а Willpower реагирующего NPC Wizard — со стороны opponent. Resolver проверяет Test IDs, считает финальные девятки только в броске реагирующего мага и создаёт `MiscastPoolIncreaseRequest` для его собственного пула независимо от победителя проверки. Девятка, появившаяся как результат допустимого переброса другого значения, тоже учитывается; trace с переброшенной исходной девяткой отклоняется как нарушающий книгу.

Дальность Long Range и round-scoped использование передаются явными снимками. Недоступная ветвь не принимает уже выполненную проверку. Сам факт вызова доступного resolver означает, что добровольное противодействие уже объявлено; выбор применять Ability, построение общей Opposed-проверки и накопление Casting successes остаются orchestration.

`RerollLock(RULE-MAGIC-003, 9)` подключает запрет до принятия решения о перебросах: девятка исключается и из доступных Glorious failures, и из автоматических Grim successes при необычно высоком пороге. Decision provider не может вернуть заблокированный индекс. Проверка завершённого trace в NPC Wizard resolver остаётся защитой границы на случай, если внешний casting pipeline не передал lock.

## RULE-MAGIC-004 — состояние и порог Miscast Pool

Miscast срабатывает, только когда после магической проверки число кубов в Miscast Pool строго превышает Wizard Level. Равенство уровню означает лишь `Portent of Doom`, но не бросок таблицы. При срабатывании маг бросает весь пул и складывает результаты; пул очищается после разрешения эффекта Miscast. Источник: Player’s Guide, страницы 157–159.

`WizardMagicState` хранит изменяемые Miscast dice и накопленные successes текущего Exacting Casting Test; неизменяемый Wizard Level остаётся входом resolver, а не частью боевого состояния. `MiscastPoolResolutionRequest` применяет source-aware `MiscastPoolIncreaseRequest`. При `pool <= level` он возвращает `ACCUMULATED`; при `pool > level` — `MISCAST_TRIGGERED` и базовый `MiscastRollRequest` на всё новое значение пула.

Сработавший пул намеренно остаётся в состоянии и блокирует новые увеличения. Это не cooldown: кубы нужны для будущего броска, а книга требует обнулить их только после разрешения табличного эффекта.

Перед броском вызывается явная preparation-фаза. Без выбранного заклинания она теряет все накопленные Casting successes и передаёт исходный пул дальше. Если `MiscastSpellSelection` указывает заклинание с Casting Value не выше накопленных successes, результат сначала создаёт `MiscastSpellCastRequest`, затем `MiscastRollRequest` с одним bonus die. Порядок follow-up не позволяет бросить таблицу до разрешения немедленного заклинания. Выбор его целей и применение spell effect остаются обязанностью casting orchestration.

Roll-фаза использует внедряемый RNG, бросает `pool_dice_count + bonus_dice`, сохраняет исходные значения и сумму и выбирает ровно одну из 21 непересекающейся строки актуальной таблицы. В частности, total `22` означает `UNNATURAL_WIND`, а `23` — `SPELL_RECAST`; `39+` остаётся открытым верхним диапазоном. Результат создаёт source-aware `MiscastTableEffectRequest`, но сохраняет Miscast Pool до отдельного исполнения эффекта. Конкретные табличные эффекты подключаются следующими явными reducers, поскольку включают Conditions, Wounds, Zones, случайные цели, долгосрочные состояния и решения GM.

Первый набор effect reducers исполняет пятнадцать строк таблицы:

- `11–12 Arcane Spill` проводит самого мага через общий `StaggerImpactRequest`, включая обычный выбор при повторном Staggered и возможную Wound policy, и создаёт отдельный `MiscastMinorLoreEffectRequest` для описываемого GM малого эффекта известного Lore в Short Range;
- `13–14 Hideous Stench` принимает стабильный снимок разных существ, находившихся в Short Range в момент Miscast. Цель, способная Give Ground, явно выбирает между движением и `MiscastNextTestPenaltyRequest` с `–1d`; при невозможном движении штраф назначается без фиктивного выбора. Независимый `MiscastFellowshipGrimUntilBatheRequest` делает все Tests характеристики Fellowship мага Grim до купания даже при пустом списке ближайших существ;
- `17–18 Random Transport` принимает текущую Zone и стабильный непустой снимок уникальных допустимых Zone на Medium Range. Поскольку Medium Range означает одну Zone между точками, текущая Zone не может входить в snapshot. Reducer выбирает индекс через внедряемый RNG, сохраняет выбранную Zone и создаёт `MiscastRandomTransportRelocationRequest`, но не меняет spatial state самостоятельно;
- `19–20 Sunlight Blindness` создаёт caster-scoped `MiscastSunlightBlindnessUntilDowntimeRequest`. Закрытый `MiscastIlluminationKind` разделяет непригодные sunlight/other natural light и пригодные torchlight/other artificial/arcane illumination; без пригодного источника маг видит сцену как глубокой ночью. Reducer не выводит освещение из текста сцены, не превращает эффект в общую Blinded Condition и не назначает отсутствующий в книге Test modifier;
- `21–22 Unnatural Wind` принимает уже выбранный стабильный список разных существ в Short Range, обязательно начиная с мага, и напрямую применяет Prone через общий Condition reducer; Monstrosity сохраняется в результате как явно исключённая цель без изменения состояния;
- `23–24 Spell Recast` случайно выбирает через внедряемый RNG один элемент непустого стабильного `MiscastRecentSpellOption` snapshot и создаёт `MiscastSpellRecastApplicationRequest` с Potency 1. Запрос не содержит выбранной цели: владельцем следующего решения является GM. Понятие «recently» и состав/веса option snapshot определяет casting orchestration;
- `25–26 Truthbound` создаёт caster-scoped `MiscastTruthboundUntilDowntimeRequest`: до следующего downtime маг может произносить только то, что считает правдой. Reducer не получает текст реплики, не определяет объективную истинность и не подменяет человеческую интерпретацию NLP-классификатором;
- `27–28 Arcane Sight` создаёт caster-scoped state до следующего полнолуния Morrslieb. Отдельный helper принимает уже классифицированный контекст: затронутая обычная Awareness Test получает Grim, а Test обнаружения магического явления — Glorious. Reducer не считает любую Awareness автоматически затронутой и не выводит контекст из текста действия;
- `29–30 Feared Foe Illusion` принимает подготовленную narrative reference самого страшного врага мага. В активном бою effect-state строго действует до конца боя; вне боя GM/orchestration обязан передать положительную длительность в минутах для книжного «few minutes». Reducer не выводит страх из профиля персонажа и не смешивает две duration-ветви;
- `31–32 Internal Damage` наносит магу обычную Wound: Player/Champion бросает Wounds Table с существующими Wounds, modifiers и доступной negation, а профильный NPC получает одну профильную Wound без броска таблицы;
- `33–34 Zone Hazard` создаёт `ZoneHazardRequest`, привязанный к текущей Zone мага и действующий до конца боя. Rating равен числу всех фактически брошенных кубов таблицы (`pool_dice_count + bonus_dice`), поэтому `+1d` за немедленное заклинание тоже увеличивает rating. Каждый участник явно выбирает Endurance либо Athletics до общего Zone Hazard executor; reducer не выбирает Zone, цели или Skill и не выполняет их Tests;
- `35–36 Ears ringing` принимает уже выбранный стабильный список разных целей, обязательно начиная с мага. Player/Champion получает фиксированную запись Wound `EARS_RINGING` и её обычный эффект без вымышленного d10; поскольку Near Miss применяется «after rolling on the Wounds Table» (страница 112), эта фиксированная строка не создаёт опцию Near Miss. Minion/Brute/Monstrosity применяет собственную профильную Wound policy и не начинает использовать Wounds Table;
- `37 Daemon Rift` создаёт `MiscastDaemonManifestationRequest`, привязанный к магу как источнику разрыва. Природу Daemon, его stat block, точное размещение и начальный курс выбирает GM; reducer неизменно фиксирует полную враждебность к магу и его союзникам, допустимые цели beguile/corrupt/destroy, возможность немедленно действовать либо скрыться и условие возврата в Realm of Chaos при уничтожении Daemon или мага. Kernel не создаёт NPC и не планирует его ход;
- `38 Fascinating Rift` принимает выбранную GM Zone в пределах Long Range и стабильный снимок свидетелей. Для каждой цели психологическая иммунность проверяется до RNG; незаблокированный свидетель проходит общий Willpower Test с добавленным reducer-ом `−1d`. Один или больше successes сопротивляются эффекту, а провал создаёт `MiscastFascinatingRiftCompulsionRequest` с обязательным стремлением войти. Удержание препятствует входу, не снимая compulsion автоматически; портал содержит только два книжных close trigger: кто-то вошёл либо что-то вышло;
- `39+ Catastrophic Death` без Wound roll убивает мага, уничтожает тело и явно запрещает reanimation; профильный NPC дополнительно переводится в defeated-состояние.

Каждый request проверяет соответствие строки исходному `MiscastTableEffectRequest` и сохранённому размеру пула. После преобразования всей строки в непосредственные изменения и типизированные follow-up Miscast Pool обнуляется. Неподдерживаемые строки не проходят через общий fallback и потому не могут очистить пул преждевременно.

Источник этой последовательности и диапазонов: Player’s Guide редакции `Last Edited: 29th January 2026`, страницы 157–159; определение Medium Range — страница 114.

## Граница других психологических эффектов

Импровизированные Illusion Control spells страниц 170–171 могут менять восприятие и память, но их конкретный эффект и допустимый Test определяет GM. `Shackles of Truth` страницы 147 действует вне текущего боевого kernel. Для них пока не вводится универсальная модель принуждения или управления разумом. Necromancy Control над mindless undead страницы 174 относится к управлению оживляющей магией и не классифицируется как психологический эффект только из-за слова «control».
