# Открытые вопросы и действующие допущения

Дата: 2026-11-03. Закрытые направления и история реализации перенесены в [архив](open-questions-history.md). Текущий этап и следующий шаг — в [статусе](project-status.md). Этот список не расширяет scope принятых ADR.

## Актуальные внешние контракты

По решению пользователя [ADR-0063](decisions/ADR-0063-single-current-magic-contract.md) оставляет только Magic JSON6. Упоминания прежних wire versions ниже отражают историю игровых consumers, а не поддержку старых форматов. Backward compatibility и migration adapters не требуются; игровые ограничения и открытые вопросы остаются действующими.

## Действующая граница симуляции

M2/M6/M7 завершены для ограниченных numeric Minion-сценариев; их исходы, массовые прогоны и подбор не означают поддержку произвольного боя. Первый M8 допускает одного authored Champion-Wizard с Curse of Cowardly Flight и numeric Shooting Minions; неизвестные scene facts и обязательные неподдержанные продолжения дают отдельный UNSUPPORTED_PATH. Broken и другая Zone не считаются defeat. Никакая остановка не исключается из числа trials.

Массовые прогоны/оценка сохраняют ограниченный single-run scope. Native API, generation с отдельным matching family assertion и обе magic JSON3/4 families поддерживают независимую stationary-wound policy ADR-0050/0051. JSON1/2 знают только прежний decline → Wind21–22/standalone Prone opt-in. Исторические закрытые этапы — в [архиве](open-questions-history.md) и профильных аудитах. Никакой опциональный consumer не означает поддержку всех Wounds/Miscasts.

<a id="первая-метрика-m5"></a>

## M8 — текущая граница и Crushed Rib transport58

Native53 и transport54 закрыты. Канонические first9/stand48/context49 и один repeated stand52 доступны при explicit matching permissions; Drained от6 после stand сохраняет expiry. Третья9, несовместимые6/Wind при repeated stand, ordinary movement/Recover/treatment и другие Wounds требуют отдельных consumers. JSON1/2 не принимают stationary, JSON1/2/3 — repeated, а generation/JSON4 требуют отдельного matching family assertion. Flag stripping для legacy view запрещён.

[ADR-0055](decisions/ADR-0055-source-bound-crushed-rib-test.md) реализован; [actual33d10/installed audit](audits/m8-crushed-rib-test-readiness.md) проверен, full4110tests/33known errors/0failures завершён. Consumer ограничен K1 injury-bound ordinary/Casting Test при одной canonical resolved/untreated/unhealed rolled10; подготовка не расходует effect, completion снимает только NEXT_TEST, Drained сохраняется. Несколько pending10,9/6, treatment/healing и Fate/Lucky/Talent proofs пока исключены. Это ограничение реализации, не запрет книги; новых house rules/книжных неоднозначностей для выбранного среза не выявлено.

[ADR-0056](decisions/ADR-0056-source-bound-crushed-rib-owner-bridge.md) реализован: full-owner pending/consumed context, first actual consuming result как witness, Protection handoff до Wound и Casting до pool/follow-ups. [Actual63d10/приёмка](audits/m8-crushed-rib-owner-readiness.md). Source compatibility не доказывает journal membership или произвольную достижимость; настоящий current owner предоставляет authoritative caller. Wizard action/end-turn gap для stripped10 без witness закрыт, включая удаление context после десериализации. Новые post-Test Wounds регистрируются полностью и затем ограничивают context.

[ADR-0057](decisions/ADR-0057-native-crushed-rib-continuation.md) закрыт в ограниченной native границе; [приёмка](audits/m8-native-crushed-rib-readiness.md). ADR-0058 полностью закрыт: generation, обе Magic JSON5 families и [installed/full boundary audit](audits/m8-crushed-rib-transport-readiness.md). JSON1–4 сохраняют refusal Crushed Rib даже null; Balance5 требует matching reserve/family assertion. Новые injury сочетания/current-state-history transport/save-resume не открываются. Python 3.12 expectation fixes проверены полным прогоном 4223/4223.

K1 Wound5 consumer [ADR-0059](decisions/ADR-0059-battered-leg-endurance-test.md) связывает одну canonical rolled5 с полным effect witness и явным normal Endurance Test. Первая граница исключает Conditions/active effects, modifiers, treatment/healing и mounted actors; combinations требуют отдельных preparations/consumptions. Actor/profile authority и chronology принадлежат caller нижнего consumer; native Scenario/journal определены в61, fresh-source generation/wire — в62.

Ручной full-owner переход [ADR-0060](decisions/ADR-0060-battered-leg-owner-bridge.md) получает Endurance profile в manual request, погашает точный pending и сохраняет bounded receipt в root. [Native ADR-0061](decisions/ADR-0061-native-battered-leg-continuation.md) реализован: отдельная policy с Scenario-owned profile и exact journal completion. None сохраняет прежний pending stop. Новый actual Staggered/completed Wound после success выходит за глобальную exact-injury границу60 и получает END_TURN scope stop до factory, после mandatory tails. Direct death после sole first5 недостижима до этого stop; другой injury/death scope и Wound-sourced Prone5 removal требуют отдельных consumers. Приёмка61 — в [аудите](audits/m8-native-battered-leg-readiness.md).

Для передачи Battered Leg реализован [ADR-0062](decisions/ADR-0062-battered-leg-generation-and-magic-json-v6.md): matching целого authored profile, independent family assertion, required nullable JSON6 object и ранние старые wire gates. [Приёмка62](audits/m8-battered-leg-transport-readiness.md). Profile1d/5 и11d/5 допустимы; transport не возвращает prototype maximum10 или правило «единственный куб — только1». Prone5 removal, mixed injuries и current-state/save-resume остаются отдельными consumers.

Существующий `Characteristic` enum покрывает шесть характеристик; Weapon Skill и Ballistic Skill пока представлены только числовыми профилями, без собственных enum values. Поэтому ADR-0059 поддерживает Toughness и явные альтернативы только из текущего enum; полная coverage книжных Characteristics остаётся отдельной задачей.

## Значение ничьей для балансировки

Первый M5 уже согласован: доля достижения явно заданной цели за общий лимит раундов, отдельные defeat/round-limit/unsupported и явное числовое окно без difficulty presets. ROUND_LIMIT и UNSUPPORTED_PATH не являются ничьей и сохраняются в общем знаменателе. Семантика настоящей ничьей, если она появится в будущем, потребует отдельного решения.

## Политики выбора для симуляции

Книга оставляет участникам решения: исход повторного Staggered, расход Fate, некоторые Talents, выбор Wound/Reaction у Monstrosity, добровольную Regeneration, ответ цели на Foul Stench и замену неподходящего результата Wounds Table для не-физического Hazard. Kernel сохранит владельца и варианты каждого решения. Перед массовой симуляцией нужно определить набор AI-policy: например, минимизация ожидаемого вреда, удержание позиции или профиль поведения NPC. Без отдельной Hazard-policy безопасный технический default — не заменять выпавшую строку таблицы.

Техническая граница первого среза согласована в `ADR-0002` и `architecture/resolution-kernel.md`; пользовательского решения для начала K1 не требуется.

## Масштаб Unmitigated Success и Last Stand

Player’s Guide 1.4 на страницах 111–112 ограничивает Unmitigated Success лучшим реалистически возможным исходом и предлагает игроку с GM согласовать более широкий результат; Last Stand может быть масштабнее, но должен соответствовать тону и также допускает корректировку GM. Универсальной формулы для цели Test, конкретного подвига и допустимого изменения сцены книга не даёт. Оба application consumer поэтому требуют внешние stable scope/target/consequence references и подтверждения ограничений, но сами не выбирают и не применяют изменение сцены; Last Stand лишь проверяемо завершает уже исполненный подвиг обязательной смертью. Перед автоматической симуляцией нужна policy оценки масштаба; безопасного общего default кроме заранее подготовленного закрытого набора эффектов нет.

## Конкретизация альтернативной цены Retreat

Player’s Guide 1.4 на странице 120 разрешает при полностью исчерпанном Fate назначить цену Retreat в blood (одна Wound), materiel (один valuable trapping) или misfortune (golden opportunity для врагов), но не определяет цель Wound, владельца/конкретный предмет и содержание либо получателя возможности. K1 требует GM выбрать класс цены и создаёт связанный proof с полным допустимым snapshot. Blood consumer принимает явно выбранного PC и проводит Wound через общий lifecycle; автоматической target policy нет. Взаимодействие с Near Miss книга отдельно не оговаривает: временно Wound можно отменить общим burn, но application остаётся погашенным (`AMBIGUITY-011`). Materiel consumer принимает explicit owner/item и внешнюю оценку ценности, не выбирая их и не выводя `valuable` из Cost tier. Misfortune consumer принимает explicit enemy из opposition snapshot и stable reference на заранее подготовленное GM описание, затем только регистрирует одну opportunity в campaign state. Policy выбора индивидуального/коллективного beneficiary, содержания и последующего исполнения возможности всё ещё внешняя (`AMBIGUITY-012`); безопасного универсального default нет.

## Конкретизация последствий Run For Your Lives

Player’s Guide 1.4 на странице 120 задаёт девять narrative outcomes, но не определяет числовую длительность Lost, величину репутационной потери Mocked, содержание долга Indebted, бонус готовности Marked, объём знания Exposed, условия окончания Hunted, число/алгоритм выбора trappings Robbed, параметры нового конфликта Surrounded или точный объём цены Trapped. Для Robbed также не описан случай персонажа без переносимых trappings, хотя текст говорит определить потерю каждого персонажа. K1 регистрирует только exact typed outcome и stable references на явно подготовленное GM содержание. Robbed consumer требует непустую explicit GM-selection carried items для каждого PC, не ранжирует вес и отклоняет пустой случай без частичной мутации (`AMBIGUITY-013`). Trapped routing требует explicit GM-owned kind `WOUNDS`/`CAPTURE`/`OTHER`, affected PC subset и exact references. Wounds consumer дополнительно требует от GM положительное число Wounds каждому выбранному PC, исполняет их последовательно через общий lifecycle и после смерти пропускает остаток назначения этой цели (`AMBIGUITY-014`). Capture consumer требует по одному explicit captor/consequence reference на PC и только регистрирует active captivity (`AMBIGUITY-015`). Other consumer сохраняет exact affected PC/references и описание как opaque GM-defined cost, но не классифицирует и не исполняет его (`AMBIGUITY-014`). Surrounded consumer принимает exact ordered references на новую opposition и encounter setup и регистрирует только conflict opportunity, не выбирая Test, difficulty, conflict start или placement (`AMBIGUITY-016`). Hunted consumer регистрирует inactive threat с exact pursuer/trigger references и активирует её только по external movement-event reference; смысл `move again`, lay-low duration и новый pursuit остаются внешними (`AMBIGUITY-017`). Exposed consumer требует explicit enemy/home/non-empty shelters/weakness references и только регистрирует knowledge disclosure; его эксплуатация остаётся внешней (`AMBIGUITY-018`). Marked consumer регистрирует pending readiness с exact enemy/acquired-intelligence/next-action-trigger references и отдельно фиксирует matching action event; смысл `move against them`, bonus, ambush, encounter и дальнейший расход готовности остаются внешними (`AMBIGUITY-019`). Indebted consumer требует explicit creditor/debt/repayment references и только регистрирует outstanding obligation; сумма, срок, конкретная услуга, санкция и способ закрытия долга остаются внешними (`AMBIGUITY-020`). Mocked consumer требует непустой ordered witness/rival snapshot и explicit gossip/reputation-effect references, но не назначает magnitude, social scope, duration или recovery (`AMBIGUITY-021`). Lost consumer требует explicit unfamiliar-territory/intended-destination/return-delay/enemy-opportunity references, но не назначает duration, route, spatial relocation, calendar advance или enemy action (`AMBIGUITY-022`). Для автоматической симуляции дальнейших последствий нужны отдельные ограниченные policy и campaign/spatial consumers; безопасного общего default нет.

## Как ранжировать most vigilant enemy

Player’s Guide 1.4 на странице 117 требует противопоставлять Move Quietly Awareness «most vigilant enemy», но не задаёт универсальную формулу сравнения разных Awareness profiles, situational modifiers и качеств Test. K1 не вычисляет вымышленный expected score: `MoveQuietlyObserver` получает внешний целочисленный `vigilance_priority`, максимальное значение побеждает, а равенство сохраняет порядок стабильного eligible snapshot. Перед AI/battle orchestration нужно определить policy формирования этого приоритета; до этого безопасный адаптер может использовать явный выбор GM и ранжировать выбранного наблюдателя выше остальных.

## Лимит раундов

Лимит подтверждён, но его продуктовый default ещё не выбран. M3/M4 требуют явный round_budget; CLI не добавляет default. Первый контракт M5 сохраняет обязательный общий лимит сравниваемых кандидатов, не выводя длительность или difficulty из числа раундов автоматически.

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

## Границы orchestration histories

Актуальные Aim, hidden lifecycle и replay guards описаны в [архитектуре ядра](architecture/resolution-kernel.md) и профильных tests. Автоматическое forgetting укрытий, перенос history между боями и полная общая battle chronology не определены. Это пробелы интеграции, а не разрешение сбрасывать IDs/state. Подробная история закрытых boundaries сохранена в [архиве](open-questions-history.md#временная-граница-истории-укрытий).
