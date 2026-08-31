# Открытые вопросы

## Политики выбора для симуляции

Книга оставляет участникам решения: исход повторного Staggered, расход Fate, некоторые Talents, выбор Wound/Reaction у Monstrosity, добровольную Regeneration, ответ цели на Foul Stench и замену неподходящего результата Wounds Table для не-физического Hazard. Kernel сохранит владельца и варианты каждого решения. Перед массовой симуляцией нужно определить набор AI-policy: например, минимизация ожидаемого вреда, удержание позиции или профиль поведения NPC. Без отдельной Hazard-policy безопасный технический default — не заменять выпавшую строку таблицы.

Техническая граница первого среза согласована в `ADR-0002` и `architecture/resolution-kernel.md`; пользовательского решения для начала K1 не требуется.

## Масштаб Unmitigated Success и Last Stand

Player’s Guide 1.4 на страницах 111–112 ограничивает Unmitigated Success лучшим реалистически возможным исходом и предлагает игроку с GM согласовать более широкий результат; Last Stand может быть масштабнее, но должен соответствовать тону и также допускает корректировку GM. Универсальной формулы для цели Test, конкретного подвига и допустимого изменения сцены книга не даёт. Оба application consumer поэтому требуют внешние stable scope/target/consequence references и подтверждения ограничений, но сами не выбирают и не применяют изменение сцены; Last Stand лишь проверяемо завершает уже исполненный подвиг обязательной смертью. Перед автоматической симуляцией нужна policy оценки масштаба; безопасного общего default кроме заранее подготовленного закрытого набора эффектов нет.

## Конкретизация альтернативной цены Retreat

Player’s Guide 1.4 на странице 120 разрешает при полностью исчерпанном Fate назначить цену Retreat в blood (одна Wound), materiel (один valuable trapping) или misfortune (golden opportunity для врагов), но не определяет цель Wound, владельца/конкретный предмет и содержание либо получателя возможности. K1 требует GM выбрать класс цены и создаёт связанный proof с полным допустимым snapshot. Blood consumer принимает явно выбранного PC и проводит Wound через общий lifecycle; автоматической target policy нет. Взаимодействие с Near Miss книга отдельно не оговаривает: временно Wound можно отменить общим burn, но application остаётся погашенным (`AMBIGUITY-011`). Materiel consumer принимает explicit owner/item и внешнюю оценку ценности, не выбирая их и не выводя `valuable` из Cost tier. Misfortune consumer принимает explicit enemy из opposition snapshot и stable reference на заранее подготовленное GM описание, затем только регистрирует одну opportunity в campaign state. Policy выбора индивидуального/коллективного beneficiary, содержания и последующего исполнения возможности всё ещё внешняя (`AMBIGUITY-012`); безопасного универсального default нет.

## Конкретизация последствий Run For Your Lives

Player’s Guide 1.4 на странице 120 задаёт девять narrative outcomes, но не определяет числовую длительность Lost, величину репутационной потери Mocked, содержание долга Indebted, бонус готовности Marked, объём знания Exposed, условия окончания Hunted, число/алгоритм выбора trappings Robbed, параметры нового конфликта Surrounded или точный объём цены Trapped. Для Robbed также не описан случай персонажа без переносимых trappings, хотя текст говорит определить потерю каждого персонажа. K1 регистрирует только exact typed outcome и stable references на явно подготовленное GM содержание. Robbed consumer требует непустую explicit GM-selection carried items для каждого PC, не ранжирует вес и отклоняет пустой случай без частичной мутации (`AMBIGUITY-013`). Trapped routing требует explicit GM-owned kind `WOUNDS`/`CAPTURE`/`OTHER`, affected PC subset и exact references, но пока лишь создаёт typed branch follow-up (`AMBIGUITY-014`). Для автоматической симуляции фактической цены Trapped и остальных outcomes нужны отдельные ограниченные policy и campaign/injury/spatial consumers; безопасного общего default нет.

## Как ранжировать most vigilant enemy

Player’s Guide 1.4 на странице 117 требует противопоставлять Move Quietly Awareness «most vigilant enemy», но не задаёт универсальную формулу сравнения разных Awareness profiles, situational modifiers и качеств Test. K1 не вычисляет вымышленный expected score: `MoveQuietlyObserver` получает внешний целочисленный `vigilance_priority`, максимальное значение побеждает, а равенство сохраняет порядок стабильного eligible snapshot. Перед AI/battle orchestration нужно определить policy формирования этого приоритета; до этого безопасный адаптер может использовать явный выбор GM и ранжировать выбранного наблюдателя выше остальных.

## Значение ничьей для балансировки

Ничья является отдельным исходом. Перед реализацией балансировщика нужно решить, учитывается ли она как поражение игроков или влияет на отдельную функцию оценки. В базовой статистике она будет публиковаться отдельным `draw_rate`.

## Лимит раундов

Лимит подтверждён, но его продуктовый default ещё не выбран. M1 использует явное обязательное значение конфигурации движка; application layer позже задаст пользовательский default.

## Порядок multi-target целей

`NearbyTargetsStaggerRequest` фиксирует событие Blunderbuss относительно позиции существ в момент попадания, общий `ZoneHazardRequest` — Hazard для уже выбранной Zone, а его Reactor-вариант — падение Giant относительно текущей Zone. K1 не ищет и не сортирует цели по Zones. Executors принимают выбранный упорядоченный набор разных целей и обрабатывают его слева направо; только Giant-обёртка дополнительно требует включить самого реагирующего. Перед полноценной симуляцией нужно определить стабильный spatial-порядок либо отдельную policy выбора, если порядок способен изменить исход.

## Monstrous Flight без доступного Give Ground

Общее правило (Player’s Guide, страница 119) запрещает Give Ground, если существо Prone или не может покинуть Zone. Monstrous Flight (GM Guide, страницы 177, 179–180) говорит, что при Reaction Monstrosity даёт Ground, а если уже делала это в текущем ходу — получает Wound; отдельного исхода для полностью невозможного перемещения не указано. K1 разрешает известные ветви, но при `can_give_ground=False` без предыдущего Give Ground возвращает явную ошибку и требует GM/simulation policy. Нужно решить, теряется ли Reaction, превращается ли она в Wound или применяется иной исход.

## Источник Distracted

Общее правило Distracted (Player’s Guide, страница 123) связывает Condition с конкретным объектом отвлечения и заменяет старое Distracted новым. Текущий `ConditionState` хранит только факт наличия Condition и не различает Stupidity, Foul Stench, заклинание или иной источник. `TrollStupidityState` отдельно и однозначно хранит собственный штраф и suppression, но перед полноценной симуляцией нужно решить, станет ли provenance/объект отвлечения частью общего Condition state либо останется в состояниях конкретных Abilities. До этого orchestration обязано явно сообщать Stupidity о внешнем снятии Distracted.

## Spell Recast без определённой недавней истории

Строка Miscast `23–24` (Player’s Guide 1.4, страница 159) требует случайно повторить недавно сотворённое заклинание, но не определяет временную границу `recently`, способ взвешивания повторных сотворений одного spell и исход, если маг ещё не сотворил ни одного подходящего заклинания. Текущий K1 требует от casting orchestration непустой стабильный `MiscastRecentSpellOption` snapshot с уникальными option IDs и случайно выбирает один option; пустой snapshot отклоняется без очистки Miscast Pool. Перед полным battle loop нужна GM/simulation policy для формирования snapshot и пустого случая.

## Objects Transfigured при недостатке объектов

Строка Miscast `5–6` (Player’s Guide 1.4, страница 159) требует преобразовать `1d10` случайных малых объектов в Short Range, но не задаёт исход, если подходящих объектов меньше выпавшего числа. Текущий reducer сохраняет точный `object_count_roll` и возвращает запрос на такое же число объектов, не сокращая его молча. Перед spatial/inventory executor нужна GM/simulation policy: использовать все доступные объекты, дополнить сцену подходящими объектами либо применить иной исход.

## Range-формулировки Miscast и сам маг

Строка Miscast `3–4` (Player’s Guide 1.4, страница 159) затрагивает `anyone within Short Range of you`, а `1–2` — `all those within Medium Range`, но ни одна не говорит `including you`; строка `21–22` на той же странице добавляет это уточнение явно. Текущий K1 принимает уже выбранный стабильный target snapshot и не включает либо исключает мага самостоятельно. Перед общим spatial target discovery нужно утвердить единообразную policy self-inclusion для таких формулировок.

## Бонус Charge для Brawn

Определение Charge на странице 117 Player’s Guide 1.4 даёт `+1d`, если последующая атака является Melee. На странице 118 тот же модификатор находится в списке, предварительно названном применимым к Melee и Brawn attacks. Текущий K1 использует узкую формулировку страницы 117: `+1d` получает только `Skill.MELEE`, а Brawn Charge остаётся без бонуса. Нужно решить, считать ли unarmed Brawn Attack «Melee attack» для этого правила.

## End-battle treatment при неполном наборе инструментов

Player’s Guide 1.4 на странице 121 одновременно говорит автоматически обработать все Wounds после боя при возможности перевести дух и запрещает обрабатывать конкретную injury без подходящих trappings. Не уточнено, обрабатываются ли только те раны, для которых инструменты имеются, либо automatic batch вообще требует полного набора. Текущий `EndBattleWoundTreatmentRequest` принимает только явный факт `has_required_trappings_for_all_wounds=True`; частичный случай отклоняется без мутации. Перед inventory orchestration нужно утвердить per-Wound trappings policy (`AMBIGUITY-008`).

## Последствие провала Surgery и наём NPC

Player’s Guide 1.4 на странице 122 говорит только, что провал Dexterity Test несёт риск permanent disfigurement or death; вероятность, обязательность и таблица исхода отсутствуют. Там же обычным способом названа оплата NPC, но книга не задаёт цену и не говорит, становится ли операция автоматически успешной. K1 не подменяет это вероятностями: failed `DowntimeSurgeryResult` возвращает GM-owned `SurgeryFailureRiskRequest` с обоими книжными рисками без мутации state, а квалифицированный NPC использует тот же explicit Test. Перед симуляцией campaign consequences нужна отдельная GM/AI policy (`AMBIGUITY-009`).

## Что именно отменяет Combat Surgeon

Player’s Guide 1.4 на странице 122 отдельно перечисляет operating theatre, specialist medical tools, time и recovery supports, а Combat Surgeon на странице 74 говорит только, что specialist medical facilities не нужны. Текущий battle adapter использует узкую политику: отменяет theatre, заменяет time одной action за каждую Test и всё ещё требует tools/supports. Нужно решить, должно ли более широкое чтение Talent отменять также specialist medical tools и/или recovery supports (`AMBIGUITY-010`).
