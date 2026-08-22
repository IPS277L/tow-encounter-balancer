# Тестирование

Правила проверяются детерминированно через заданные последовательности d10. Monte Carlo-тесты не должны зависеть от точного процента побед.

Основная команда:

```powershell
$env:PYTHONPATH = "src"
py -3.12 -m unittest discover -s tests -v
```

Минимальные группы тестов M1:

- валидация профиля и особое правило одного куба;
- все исходы встречной проверки;
- границы `damage` относительно RES;
- обычное накопление stagger и ограниченный stagger за промах;
- сброс stagger при ране;
- немедленное завершение боя и отсутствие хода погибшего;
- одновременная гибель;
- предел раундов;
- воспроизводимость seed.

Группы K1 Test kernel:

- Characteristic + Skill и готовый inline-профиль NPC;
- динамический предел в два значения Characteristic и явное исключение из предела;
- книжное минимальное правило, когда модифицированный пул стал меньше одного;
- таблица результата Basic Test;
- обязательный Grim и добровольный Glorious с явной decision policy;
- отмена Grim и Glorious и запрет повторного переброса;
- фиксированные модификаторы успехов и полный `RollTrace`;
- победа по успехам, контекстный tie-break и отдельный результат `0:0` для Opposed Test.

Группы K1 Attack/Impact:

- попадание при ненулевой ничьей и промах при `0:0`;
- обязательный успех unopposed атаки;
- Damage из базового значения и разницы/общего числа успехов;
- профильный коэффициент Damage за успех;
- строгая граница `Damage > Resilience` для Wound;
- временное игнорирование брони и фазовые модификаторы Damage/Resilience;
- Staggered атакующего только за промах в Close Range и только при отсутствии состояния.
- `DamageImpactSpec` без изменения обычного Damage/Resilience поведения;
- Condition вместо Damage без фиктивных числовых значений;
- повторный Staggered replacement через общую decision policy;
- Hazard вместо Damage как typed exposure с рейтингом и Skill;
- replacement impact не применяется при промахе.

Группы K1 Hazards:

- успехи, равные рейтингу, полностью избегают Hazard;
- shortfall задаёт базовые кубы Wounds Table до untreated Wounds;
- shortfall становится числом Wounds для профильных NPC;
- Condition-only Hazard не создаёт Wound;
- failure Conditions применяются после Wound и не отменяются Near Miss;
- результат постороннего Test нельзя передать другой экспозиции.

Группы K1 Secondary effects:

- secondary effects не срабатывают при промахе;
- Prone применяется до repeated-Staggered и тем самым запрещает Give Ground;
- конкретный эффект может исключить Monstrosity;
- Blunderbuss создаёт typed request для других существ в Close Range от цели;
- multi-target request ставится после последствий основной цели;
- Rule ID применённых secondary effects сохраняются в результате.
- основная цель и повторные secondary target IDs отклоняются;
- вторичные цели разрешаются слева направо с последовательным RNG;
- каждая цель использует собственный Stagger context и decision request ID;
- Player/Champion используют Wounds Table, а Minion/Brute/Monstrosity — профильные Wounds;
- Near Miss сохраняет исходное Staggered вторичной цели.
- after-Give-Ground Condition не срабатывает на первом Staggered или при другом выборе;
- Give Ground follow-up всегда предшествует Condition follow-up;
- отложенный reducer применяет Condition без преждевременной мутации состояния;
- тот же after-Give-Ground эффект доступен вторичным целям.
- Condition-on-hit требует обычный Damage и не срабатывает при промахе;
- Damage/Staggered/Wound полностью разрешается до on-hit Condition;
- Near Miss отменяет Wound, но сохраняет дополнительный Condition попадания;
- on-hit Condition появляется до отложенного Give Ground → Condition.
- Terrifying ставит Broken после Give Ground либо фактически принятой Wound;
- Near Miss, первый Staggered и Fall Prone не запускают Terrifying;
- условие принятой Wound одинаково работает в kernel и для профильной вторичной цели.

Группы K1 Staggered:

- первое получение состояния без дополнительного выбора;
- явная decision policy при повторном Staggered;
- Give Ground не чаще раза за раунд и только при допустимом перемещении;
- запрет Give Ground и повторного Prone для уже лежащей цели;
- автоматический запрос Wound, если других вариантов нет;
- сохранение Staggered до окончательного принятия или отмены Wound.

Группы K1 Injury и сквозного kernel:

- все границы Wounds Table от `1–3` до `27+`;
- один куб плюс untreated Wounds и фазовые модификаторы, минимум один куб;
- смертельные результаты, снятие Staggered и сохранение состояния при Near Miss;
- общая policy Player/Champion;
- Minion, профильный лимит Brute/Monstrosity и преобразование extra table die в Wound;
- владелец решения Monstrosity Wound/Reaction для обоих порогов Damage;
- Monstrous Flight после выбора Reaction возвращает Give Ground либо профильную Wound в зависимости от Give Ground в текущем ходу;
- Give Ground от Monstrous Flight сохраняет предпочтение вертикальной midair-зоны и ставит Terrifying после движения;
- Wound от повторной Monstrous Flight проходит общую профильную injury policy, включая дополнительные Wounds и Terrifying;
- полностью невозможный Give Ground завершается явной ошибкой неоднозначности, а не скрытым исходом;
- Unsteady сохраняется kernel как конкретный Reaction spec без строковой диспетчеризации;
- новое падение Giant накладывает Prone, сохраняет Staggered и создаёт Athletics Hazard (3) для всех существ в его Zone;
- уже Prone Giant не падает повторно и не создаёт повторный Zone Hazard;
- Give Ground context отклоняется для Unsteady как неприменимый к этой Reaction;
- Zone Hazard batch обязан включать реагирующего и иметь уникальные target/Test IDs;
- выбранные Zone-цели проходят Test и Hazard слева направо на общем RNG с отдельными trace и состояниями;
- Zone Hazard executor передаёт Test/Wound decisions, injury policy и failure Conditions в общие resolvers;
- Monstrous Regeneration сохраняется kernel как конкретный Reaction spec;
- Reaction Ghorgon/Troll Hag не меняет injury state и создаёт ровно один source-aware запрет регенерации на следующий ход;
- suppression не маскируется Condition и не запускает Terrifying;
- сохранённый suppression пропускает ближайшее end-turn окно, не вызывает decision provider и возвращается ровно один раз как consumed;
- suppression погашается даже при нуле Wounds, поэтому не переносится на более поздний ход;
- без suppression лечение требует решения Actor, блокируется при отсутствии неогненной Wound и уменьшает Wounds ровно на 1;
- Ghorgon/Troll Hag получает Staggered только при его отсутствии, а уже Staggered Monstrosity продолжает иметь право на лечение;
- Mother Knows Best даёт обычный +1d Casting modifier только при 0 Wounds и не обходит предел пула;
- Long Range и once-per-round снимки закрывают недоступную NPC Wizard opposition без готового Test result;
- завершённая opposition обязана содержать ожидаемые Casting/Willpower Test IDs, а её исход не влияет на подсчёт девяток Troll Hag;
- девятки создают typed увеличение собственного Miscast Pool, отсутствие девяток всё равно расходует round budget, а переброшенная исходная девятка отклоняется;
- Rule of Nine lock исключает девятку из Glorious decision choices и автоматического Grim reroll, включая порог, при котором 9 считается успехом;
- Casting Test переиспользует общий Test resolver, сам устанавливает Rule of Nine lock и считает девятки по финальным значениям;
- последовательные Casting rolls накапливают successes только для одного объявленного Lore и отдельно сохраняют successes последнего броска для Potency;
- нулевой бросок всё равно открывает Casting-попытку выбранного Lore, а смена Lore до её завершения отклоняется;
- source-aware Casting follow-up напрямую применяется существующей Miscast Pool threshold-фазой;
- normal WAIT не выбирает spell и сохраняет весь Casting snapshot, а CAST проверяет Lore/CV, переносит latest-roll Potency и очищает snapshot;
- pending Miscast блокирует normal CAST/WAIT, но pool, равный Wizard Level, не блокирует решение;
- общий `SpellCastRequest` используется normal и pre-Miscast ветвями и допускает base Potency 0;
- нулевая base/effective Potency не создаёт spell effect;
- spell definition фиксирует для Curse of Cowardly Flight `CV 3`, Battle Magic, Zone, Long и Instant;
- schema preflight проверяет Rule ID/Lore/CV cast, различает неверный Target и out-of-range и только для `READY` создаёт target execution;
- выбранная Zone отделена от списка затронутых врагов: пустой affected-target snapshot валиден и не создаёт искусственных эффектов;
- target execution требует уникальные цели и сохраняет их стабильный порядок;
- Potency modifiers разрешаются независимо для каждой цели, включая разные effective значения одного multi-target cast;
- нулевая effective Potency сохраняет target result для трассировки, но не создаёт `SpellEffectApplicationRequest`;
- положительный effect follow-up сохраняет cast/caster/spell/lore/target и effective Potency для конкретного spell reducer;
- адаптер `Curse of Cowardly Flight` принимает только собственный spell/source Rule ID и отклоняет чужой эффект;
- target-local effective Potency из общего executor становится порогом Willpower существующего spell reducer;
- переданные movement/injury/immunity snapshots сохраняют книжный порядок Give Ground → Willpower и общую психологическую блокировку;
- Zone batch требует ровно один context для каждого положительного effect, отклоняет missing/extra/duplicate/forged contexts и уникализирует Willpower Test IDs;
- контексты могут поступить в ином порядке, но результаты и отдельные movement/Willpower очереди следуют стабильному affected-target snapshot; movement сохраняет target ID в typed wrapper;
- цель с effective Potency 0 не требует effect context, а пустая Zone создаёт пустой корректный batch с сохранённым selected Zone ID;
- movement-completion gate принимает подтверждения в любом порядке, но до RNG отклоняет missing/extra/duplicate/forged confirmations и подменённые очереди Zone batch;
- после полного movement gate Willpower Tests используют один RNG и исходный affected-target порядок; невозможность Give Ground не отменяет Test, а пустая Zone не расходует RNG;
- Zone graph отклоняет неизвестные/self/duplicate connections, а spatial state — неизвестные Zone, повторные entity ID и некорректные раздельные Give Ground/free-move usage;
- free movement требует active actor и совпавший round, не создаёт action slot и меняет только placement actor плюс once-per-turn usage;
- Slow/Normal пересекают одну Zone boundary, Fast — до двух последовательных связей; неизвестный, несвязный, повторный или возвращающийся к origin маршрут отклоняется;
- Prone/Defenceless, enemy path blocker и obstacle блокируют прямой free move, Burdened и союзник на пути не блокируют; Difficult Terrain исполняется отдельным traversal и принимается terrain-aware composite без второго Test;
- повторный free move отклоняется, а переход spatial round очищает его usage одновременно и независимо от Give Ground/Difficult Terrain Test;
- снятие Prone вместо движения требует active actor, Prone target и отсутствие врага Close; self не принимает ally-range fact, а ally обязан быть отдельной дружественной целью с явным Close Range;
- успешная Prone-removal ветвь сохраняет placements/action slots, удаляет только Prone из target Conditions и расходует тот же free-move usage actor;
- movement после Prone removal и Prone removal после movement одинаково отклоняются как повторное использование общей once-per-turn возможности;
- базовый Run требует зарезервированный `ManoeuvreKind.RUN`, active actor, совпавший spatial round и завершённость всех более ранних slots;
- Normal/Fast Run перемещает actor ровно на одну соседнюю Zone, сохраняет free-move/Give Ground usage и лишь после spatial mutation добавляет execution receipt;
- Slow, Burdened, Prone, Defenceless, неизвестная/несоседняя Zone, enemy path blocker, obstacle и Difficult Terrain закрывают Run без изменения обоих входных состояний;
- незавершённый Run запрещает конец хода, исполненный slot нельзя использовать повторно, а forged spatial/round/result transitions отклоняются доменной моделью;
- optional Run Athletics принимает только завершённый base Run и typed Athletics Test; success перемещает ещё на одну соседнюю Zone без нового receipt;
- failed Athletics не двигает actor и добавляет Staggered только при отсутствии; уже Staggered остаётся единственным без repeated-Staggered choice;
- подтверждённый Difficult Terrain usage того же turn, terrain на extra path, obstacle, enemy blocker и movement Conditions закрывают optional Test до RNG;
- Test trace/модификаторы, Conditions и spatial snapshots входят в result invariants; forged outcome/test/application/state отклоняются;
- базовый Charge требует enemy target ровно на соседней Zone, active reserved Charge slot, отсутствие enemy Close в начале turn и явное достижение Close после movement;
- Slow/Burdened/Prone/Defenceless, Long/невалидная цель, enemy path blocker, obstacle и Difficult Terrain закрывают Charge до RNG;
- Melee Charge добавляет ровно один source-aware `+1d`, а Brawn/Shooting/Throwing не получают его; заранее встроенный Charge modifier отклоняется;
- successful preflight сначала создаёт spatial snapshot, затем исполняет один Close kernel attack и только после результата добавляет receipt; kernel failure оставляет оба входа неизменными;
- незавершённый/повторный Charge и нарушение порядка slots отклоняются; result invariants защищают target Close fact, movement, prepared attack, bonus и turn transition;
- terrain-aware Medium Charge принимает только traversal с совпавшими actor/round/origin/target destination/path/Conditions и current crossed state, затем выполняет attack без повторного движения или Athletics;
- failed terrain Athletics сохраняет crossed placement и Prone, но не отменяет Charge attack; post-terrain Staggered context, Melee-only `+1d`, slot-order и остальные ограничения базового Charge продолжают проверяться;
- подменённый traversal/current snapshot, stale attack, duplicate bonus, повторное потребление исполненным slot и forged Condition/spatial/kernel/round results отклоняются;
- Long Charge требует enemy target ровно через две последовательные Zone links без прямого Medium adjacency и сохраняет intermediate Zone в request/result;
- successful Long Athletics перемещает actor в Zone target, выполняет один Close kernel attack с общей Melee-only `+1d` policy и завершает исходный Charge slot;
- failed Long Athletics перемещает actor только в intermediate Zone, не подготавливает и не выполняет attack, впервые добавляет Staggered и также завершает Charge slot;
- уже Staggered на провале остаётся единственным Condition без repeated-Staggered choice; обе ветви разрешают завершить turn;
- подтверждённый Difficult Terrain usage того же turn, terrain на route, obstacle, enemy blocker, Close в начале turn и stale attack context закрывают Long attempt до RNG; forged outcome/Test/Condition/spatial/kernel/receipt transitions отклоняются;
- Difficult Terrain traversal требует active actor, adjacent destination, Athletics Test и явный path context; Prone/Defenceless, obstacle и enemy blocker закрываются до RNG, тогда как Burdened/ally не блокируют общий crossing;
- spatial placement и turn-scoped terrain usage создаются до Test outcome; success сохраняет Conditions, failure после crossing применяет Prone и не откатывает движение;
- повторный terrain crossing в одном turn делает новый Test без duplicate usage; переход spatial round очищает факт, а forged movement/usage/Test/Condition result отклоняется;
- terrain result сохраняет полный source request; free-move/Run/Medium-Charge composites требуют совпадения actor/round, origin state, Conditions, destination, path и obstacle, а подмена provenance закрывается до bookkeeping;
- terrain-aware free move после success/failure добавляет только общий free-move usage; terrain-aware Run добавляет только receipt, обе ветви сохраняют crossed placement и полученный на провале Prone;
- попытка применить traversal к уже обновлённому spatial/round snapshot отклоняется; Slow/Burdened и slot-order ограничения базового Run сохраняются после разделения фаз;
- общий Give Ground executor требует соседнюю Zone и при указанном attacker увеличивает graph-distance, запрещает повтор в round, Prone/Defenceless, enemy path blocker, obstacle и Difficult Terrain;
- успешный Give Ground сохраняет порядок placements, меняет только mover Zone, записывает round usage и после движения накладывает Broken при наличии врага в destination, но не при одном союзнике;
- переход к следующему spatial round очищает Give Ground и free-move usage; Cowardly completion принимает generic spatial result только для своего target/request, а batch требует одну ordered state chain из selected Zone до final spatial state;
- равенство Miscast Pool и Wizard Level не срабатывает, а строгое превышение создаёт запрос броска всего сохранённого пула;
- несколько добавленных Miscast dice сохраняют provenance Ability/Rule of Nine/pool rule, а уже сработавший неразрешённый пул не принимает новые кубы;
- preparation всегда теряет накопленные Casting successes; выбранное доступное заклинание стоит перед Miscast roll и добавляет ровно `+1d`;
- добровольное прекращение активного Casting с непустым пулом переиспользует preparation на всех текущих dice, допускает тот же optional spell и отклоняет уже triggered pool;
- добровольное прекращение с пустым пулом очищает Lore/successes/latest roll без `MiscastRollRequest`; spell-before-Miscast в этой ветви недопустим;
- Miscast roll использует pool и bonus dice, сохраняет все d10 и создаёт typed table-effect request, не очищая пул преждевременно;
- актуальная таблица покрыта без пробелов и пересечений: `22 → UNNATURAL_WIND`, `23 → SPELL_RECAST`, `39+ → CATASTROPHIC_DEATH`;
- Arcane Spill использует общий repeated-Stagger resolver, сохраняет внешний minor-Lore request и очищает Miscast Pool;
- Hideous Stench сохраняет stable target order, требует решение Target только при доступном Give Ground и автоматически назначает `–1d` при невозможном движении;
- пустой spatial snapshot Hideous Stench всё равно создаёт Grim для всех Fellowship Tests мага до купания, а неверные/отсутствующие решения и повторные target IDs отклоняются;
- Sense of Loss сохраняет stable Medium Range target order, допускает пустой snapshot, отклоняет дубликаты и явно не удаляет предметы;
- Nauseating Wave сохраняет stable Short Range target order, допускает пустой snapshot, отклоняет дубликаты и не создаёт иной эффект помимо внезапной тошноты;
- Objects Transfigured отдельно бросает `1d10`, сохраняет точное число случайных малых объектов и возвращает Short Range follow-up с GM-owned видом существ и случайными направлениями без inventory mutation;
- Shadow Chittering создаёт caster-scoped auditory effect до следующего Mannslieb full, сохраняет nearby-shadow origin и unpredictable recurrence без RNG или вымышленного механического penalty;
- Food Spoiled создаёт Long Range inventory follow-up для всей свежей еды, явно сохраняет пригодность любой preserved food и считает dried/salted/pickled неисчерпывающими примерами;
- Unnatural Weather создаёт привязанный к магу GM-owned запрос локальной погоды, сохраняет оба книжных примера и явно не определяет точную площадь, длительность или механические последствия;
- Random Transport выбирает индекс из стабильного набора Medium Range Zone через внедряемый RNG и возвращает relocation без мутации карты; пустой, повторный или содержащий origin snapshot отклоняется;
- Sunlight Blindness создаёт caster-scoped illumination policy до downtime, разделяет natural и torch/artificial/arcane light и очищает Miscast Pool без вымышленной Blinded Condition или Test modifier;
- Unnatural Wind требует мага первой уникальной целью, сохраняет stable order, напрямую применяет Prone и не изменяет Monstrosity;
- Spell Recast детерминированно выбирает индекс из стабильного recent-spell snapshot через внедряемый RNG и создаёт Potency 1 follow-up без выбранной цели, принадлежащей GM;
- пустой recent-spell snapshot и повторные option IDs отклоняются до очистки Miscast Pool;
- Truthbound создаёт caster-scoped ограничение речи до следующего downtime без анализа реплик и очищает Miscast Pool;
- Arcane Sight создаёт caster-scoped state до полнолуния Morrslieb и только по явному context выдаёт Grim для затронутой обычной Awareness либо Glorious для обнаружения магии;
- строковый/неверный Arcane Sight context отклоняется вместо неявной классификации Test;
- Feared Foe Illusion сохраняет внешний narrative reference, использует `until battle end` в бою и требует положительное число минут вне боя;
- in-battle minute duration и out-of-battle эффект без минут отклоняются как смешение разных книжных ветвей;
- Internal Damage различает Wounds Table Player/Champion и profile Wound NPC, учитывает существующие Wounds и явную negation;
- Zone Hazard считает rating по pool и bonus dice, сохраняет battle-scoped anchor и предлагает Endurance/Athletics без скрытого выбора;
- multi-skill Zone Hazard отклоняет цель без явного выбора, а общий executor переносит выбранный Skill в exposure;
- Ears ringing требует мага первой уникальной целью, сохраняет stable order и создаёт fixed Wound без фиктивных d10; профильные NPC не используют Wounds Table;
- Daemon Rift очищает пул и создаёт GM-owned manifestation contract без выбора профиля или создания NPC; обязательная враждебность, оба начальных курса и оба события возврата в Realm of Chaos сохраняются явно;
- Fascinating Rift сохраняет GM-selected Long Range Zone и stable witness order, добавляет `−1d` к каждому базовому Willpower Test и создаёт compulsion только при нуле successes;
- психологическая иммунность блокирует Fascinating Rift до Test без расхода RNG, повторные witness/Test IDs отклоняются, а portal contract содержит только события входа и выхода;
- Catastrophic Death не бросает Wounds Table, уничтожает тело, запрещает reanimation и завершает профильного NPC;
- немонтированный Bone Dragon при Reaction автоматически получает профильную Wound;
- Liche/Tomb King открывает явный выбор владельца Monstrosity между доступными Wound, Give Ground и Prone;
- недоступные Give Ground/Prone исключаются до decision policy, а неподдерживаемый выбор отклоняется;
- Give Ground и Wound от Undead Monstrosity запускают Terrifying, тогда как Prone не запускает;
- общий Condition application блокирует только совпавшую явную классификацию источника;
- психологическая иммунность сохраняет source/blocking Rule IDs и не удаляет уже существующий Condition;
- Bone Dragon блокирует психологический replacement Condition до прямого/Staggered reducer;
- одно значение Broken без психологической классификации не активирует иммунитет;
- психологический Condition-on-hit блокируется после обычного impact без отмены самого impact;
- Terrifying после принятой Wound блокируется без отмены Wound;
- Fearsome переносит classification/immunity через Give Ground follow-up и блокируется только после движения;
- Bone Dragon Reaction переносит immunity и блокирует психологический Terrifying после профильной Wound;
- полный путь `Attack → Impact → Staggered/Wound → state + follow-ups`;
- отсутствие скрытого выбора при Glorious, повторном Staggered, Near Miss и Monstrosity Reaction.

Группа K1 round/turn/action budget:

- round требует уникальных участников обеих сторон, сохраняет player-first либо persistent opposition-first порядок;
- actor внутри текущей стороны выбирается свободно, но следующая сторона не начинает ход до завершения всех участников текущей;
- активным бывает только один полный ход, а завершивший ход actor не действует повторно в том же round;
- первый action использует standard slot, второй требует Fate либо source-aware Ability, третий запрещён;
- одинаковые actions не повторяются; два разных Improvise требуют явного разрешения GM и разных approach ID;
- Attack, Charge и атакующий Improvise используют общий предел одной атаки за turn;
- slot reservation не исполняет action, не расходует Fate и не обращается к RNG/kernel;
- специализированный Attack executor связывает active actor/target/slot с `KernelAttackRequest → ResolutionResult` и меняет только receipt выбранного slot;
- не-ATTACK, Charge, чужой, незарезервированный, уже исполненный slot и нарушение порядка slots отклоняются до RNG;
- сбой kernel не отмечает slot исполненным, а зарезервированный Attack блокирует завершение хода до успешного исполнения;
- результат Attack execution отклоняет подмену actor, receipt или несвязанную мутацию round state;
- Improvise обязан явно назвать Skill, spell либо Ability и stable approach ID;
- spell Improvise executor требует Lore, совпадающий с approach ID, и выполняет ровно один общий Casting Test;
- Casting action post-Test проверяет финальные девятки/provenance и применяет агрегированный Rule of Nine follow-up до любого normal decision;
- при `pool <= Wizard Level` decision обязан совпасть по actor, level и точному post-pool state, после чего общий reducer выполняет `CAST` либо `WAIT`;
- при `pool > Wizard Level` normal decision запрещён, Casting snapshot сохраняется и наружу выходит базовый Miscast roll request;
- отсутствие обязательного decision в normal-ветви, его присутствие в triggered-ветви и подмена count/target/Test/Lore отклоняются;
- не-spell Improvise, другой action, чужой caster, незарезервированный/повторный slot и незавершённый ранний slot отклоняются до RNG;
- зарезервированный spell Improvise блокирует завершение хода до успешного Casting Test, а ошибка RNG не добавляет receipt;
- Casting execution result отклоняет подмену actor или несвязанную мутацию round state;
- Casting post-Test result отклоняет state, не совпадающий с вложенным decision либо triggered Miscast result;
- action Miscast preparation принимает только triggered post-Test result с точным source roll, actor и magic state;
- отказ от spell очищает Casting snapshot и оставляет один Miscast roll без bonus die;
- допустимый pre-Miscast spell стоит перед roll, получает Potency последнего Casting Test и добавляет roll ровно `+1d`;
- normal post-Test result и подменённые source/state/actor отклоняются, а итоговый result проверяет actor/state вложенной preparation;
- Miscast increase provenance закрыто различает фактический Test и завершённое action execution;
- завершённый обычный Attack активного caster создаёт ровно один action-sourced Miscast die и сохраняет Lore/successes;
- skipped-Test die проходит общий threshold: накапливается до уровня и создаёт triggered roll при превышении;
- отсутствие активного Casting, чужой actor, pending Miscast и forged Attack executor receipt отклоняются;
- skipped-Test result отклоняет подмену source kind/action ID/amount и итогового magic state;
- следующий round получает новый participant snapshot, очищает completed/active turn state и сохраняет порядок сторон.

Группы K1 Wound effects:

- явная спецификация каждой строки Wounds Table `1–27+`;
- однократное применение строки и сохранение источника/срока каждого эффекта;
- безусловные Conditions, ограничения до Treat/Heal и постоянные последствия;
- порядок немедленных consequences и Endurance Test;
- успешный и неуспешный Endurance с Condition либо внешним consequence;
- обе ветви обязательного выбора `Spilling guts`;
- сквозная фиксация `WoundEffectResult` в результате kernel.
