# ADR-0111: PC Blunderbuss и nearby Staggered в исходной NPC-группе

Дата: 2026-11-11. Статус: **принято и реализовано M69**. Пользователь выбрал одну исходную NPC-группу и полный nearby Trait.

## Книжные источники и функция

Адресно перечитаны BOOK-PLAYER-GUIDE1.4 IV95 и ranged94; переиспользуются прежние III82/IV99, V107/110/114–119/123. Сверены existing shared Blunderbuss profile/preparation, kernel NearbyTargetsStaggerRequest и secondary-target resolution, прежний M2 NPC nearby completion, PC Attack projection/Short approach/Warped Form. Новых книг/версий/house rules нет.

Blunderbuss:2H, optimum Short, maximum Medium, Damage4 с обычной бронёй, +2d Shooting на Short, каждый HIT/MISS→Reload3. Требует Blackpowder Lore/kit и прежних explicit Exacting facts. Бонус диапазона не optional Repeater bonus; Drained запрещает положительные dice, но не отменяет расход заряда и nearby Trait при HIT. Cap обычный.

PG95: creatures in Close Range of a hit target are Staggered. Trigger — **HIT**, а не получение основной целью Wound. Волна действует и после обычного Staggered основной цели, и после её defeat; MISS волну не создаёт. Ранее упрощённый прототипный AoE Wound-trigger к этому книжному Trait не применяется. Primary получает обычный Damage/Stagger/Wound только один раз; secondary — другие существа по принятому RULE-EFFECT-006/shared NearbyTargetsStaggerResolutionRequest, без повторного Attack/Protection Test.

Реализован полный Trait в нынешнем restricted Short opening: первый выстрел→nearby consequences→NPC approach→own-turn melee backup. Не расширять одновременно named NPC/Abilities/Brutes/PC movement/другие Zone/тактику NPC. NPC стоят одной **исходной** плотной группой; порядок nearby задаёт caller. Более широкие окрестности каждой NPC-цели не выбраны.

## Пространственные premises первого среза

Текущий Short opening подтверждает clustered PC party, но не отношения NPC↔NPC. Из одной Zone нельзя вывести, что все враги находятся друг у друга в Close. Поэтому добавить явное подтверждение исходной NPC-группы, а не молча объявлять всех nearby.

До подхода NPC все PC находятся на Short от NPC. После подхода любого живого NPC Blunderbuss уже не может стрелять по PG94. Поэтому при допустимом выстреле живые возможные secondary targets — оставшиеся NPC исходной группы; PC на Short и в волну не входят. Это следствие выбранной сцены, а не отключение friendly fire или разрешение всегда исключать PC. Friendly fire/смешанные Close-группы потребуют отдельного source при пространственном расширении.

NPC, подошедший к PC, покидает исходную группу. Если он жив, Shoot запрещён; если уже defeated, он не становится nearby target. Источник подтверждает initial cluster, а не вечную взаимную Close-связь после движения.

## Текущий публичный контракт

Добавлен PcMeleeWeapon.BLUNDERBUSS в PC_RANGED_WEAPONS11→12 и2H ranged7→8; free-reload group4 прежняя. pc.ranged — те же9required fields, что ordinary Handgun: BS/Shooting/I/Dex, true Blackpowder Lore/kit/ammunition/initially_loaded и two_available_hands. Repeater policy запрещена, initial grip=BOTH, shield запрещён; backup/Strength≥2/6существующих1H/preferred hand прежние.

Current PC JSON1/key ranged сохраняются. Принятый optional scenario field, обязательный ровно при наличии Blunderbuss:

```json
"blunderbuss_nearby": {
  "initial_npc_clustered_confirmed": true,
  "target_priority": ["minion2", "minion1", "minion3"]
}
```

Exact object/true/ordered unique NPC IDs; target_priority содержит всех NPC текущего source ровно один раз, PC/unknown/duplicates запрещены. Это полный порядок группы, не выбор, кого разрешено пропустить. Без Blunderbuss поле отсутствует/в native None; null wire/false/пустой object/лишние keys не заменяют подтверждение. В generation порядок фильтруется по фактически сохранённым NPC без переназначения. Пустой порядок допустим только если пустая opposition уже допускается существующим source/generation; M69 не меняет это правило family.

На actual HIT фиксируется ordered snapshot живых secondary NPC, исключая primary и уже defeated. Он связывается с full исходным выстрелом/actor/weapon instance/kernel resolution ID/exact NearbyTargetsStaggerRequest. Положение и состав не пересчитываются от нового target priority после исходного попадания. Snapshot остаётся действительным при defeat primary, без добавления primary/атакующего/PC. Existing per-PC defeat_decisions используются для каждого поражённого wave NPC; новая GM disposition по умолчанию не выдумывается.

Старые240JSON M9–M68 не мигрируются, других новых полей/версий/aliases/доставки не требуется. Каталог59NPC/shared14 не расширяются. Aggregate costs прежние: nearby consequences не считаются отдельными Attack/actions; существующие результаты NPC/исходы trial учитывают actual consequences.

## Исполнение и инварианты

- Shared Blunderbuss profile/preparation остаётся одним источником Traits. PC строит canonical Attack с NearbyTargetsStaggerSpec, перед K1 снимает только собственный profile-owned Trait и восстанавливает ровно один раз, как range/damage Traits. Не разрешать forged/doubled/foreign effect ради допуска.
- Kernel сохраняет обычные primary follow-ups перед NearbyTargetsStaggerRequest. Сначала исполняются обязательные последствия основной цели, затем nearby в выбранном порядке. Даже если primary побеждён или волна добивает последних NPC, effect/completion/GM ACK нельзя потерять через ранний terminal return.
- Каждая secondary цель получает один Stagger impact. Уже Staggered вызывает прежний SUFFER_WOUND без Give Ground; для нынешних numeric Minions W1/defeat подтверждается existing GM disposition. Нет дополнительных Attack/Protection/RNG на попадание. Готовый shared resolver использовать без переноса NPC roster owner или Warped Form cost/heal в PC Attack.
- PC state/proofs удерживают actual source, committed order, consumed/completed trigger и все target results. Запретить replay, перестановку/пропуск/добавление целей, stale state, замену snapshot после primary, двойную Wound и ACK чужого actor. Domain не импортирует CLI/балансировщик, RNG явный.
- После полного nearby continuation продолжается прежний round/approach/backup. Retained empty cycle3 не активирует Reload у melee backup, ranged bonus не переносится на Sword. No-backup/руки/Recover/mandatory/Defenceless/terminal boundaries прежние.

## Адресная приёмка

1. Source/JSON/schema: exact9ranged+exact2clusterkeys, true/source order/IDs, BOTH/no shield/Short-only, firearm но **без** ignores armour, cached/foreign/missing/null/false source и подменённый cached order до RNG; новый корректный caller order допустим. Generation сохраняет fact и фильтрует порядок при разных составах; full request/candidate echoes прежние.
2. Literal Short Damage4/+2d/full armour, low-BS cap/minimum, Drained убирает bonus но не HIT Trait/cycle3, Glorious before effective HIT. HIT с Wound и без Wound запускает одну волну; MISS не запускает. Primary/secondary различны, primary defeat не теряет trigger, пустой secondary snapshot завершается честно.
3. Все свежие nearby Minions получают Staggered; уже Staggered вторично получают Wound/defeat с фактическими dispositions. Несколько PC/Blunderbuss подряд: второй выстрел видит actual state после первой волны. Order, full-source/replay/forged/ACK/stale guards и отсутствие лишних Attack/actions/RNG проверяются детерминированно.
4. Все последствия до approach/другого действия/terminal objective; после живого Close NPC Shoot запрещён даже по Short-цели. Friendly PC не включаются именно по actual Short premises. Retained charge/backup/old11ranged/бывшие Close permissions сохраняются.
5. Services/trials/count search/actual CLI, current offline schemas/full source/candidate echoes, native pickle новых source/proofs,240старыхJSON/NPC59/shared14. Ближайшие kernel nearby/preparation и PC ranged/Conditions/projection/backup tests по риску; не повторять автоматически198/247/419/full/wheel/backend matrix. Новый Trait не меняет package discovery/dependencies/entry points; отдельный process нужен при конкретном transport/backend риске, не ради каждой новой weapon row.

## Согласование и результат

Пользователь явно выбрал «Одна NPC-группа, полный Trait». Source/JSON1/generation и полный nearby continuation реализованы через новые typed snapshot/receipt, прежний shared K1 и текущий PC owner. Атомарный ordered batch включает все Minion profile results/GM acknowledgements: это допустимо для данной restricted сцены без промежуточных реакций/Abilities и не является общим механизмом для PLAYER/Champion/Brute targets.

Внутреннее review выявило недостаточную фиксацию source-order между HIT и wave. Добавлен PcAttackProof.nearby_snapshot с full cluster source/request до primary change; две новые native проверки отвергают позднюю замену корректного source-order, missing/forged snapshot и snapshot у MISS. Финальные15native tests — OK1.043s.5integration tests первоначально прошли2.046s и затем вошли в финальный прогон.

До усиления snapshot guard единый адресный checkpoint245tests — OK19.150s: kernel secondary/preparation, текущие source/enum/schema, PC hit Drained/Prone, ranged/bows/Crossbows/Handguns/Sling и backup. После изменения повторены затронутые JSON/services и репрезентативные PC hit/ranged paths:59tests — OK6.851s. Это разные адресные прогоны, не единый зелёный full run. Actual simulation/balance CLI повторены на финальном коде; фактические команды/результаты и source/schema/pickle сверка — в [статусе](../project-status.md), [примеры](../examples/m69/README.md).

Старые240JSON/NPC59/shared14 сохраняются. Wheel/full/backend matrix не запускались без нового основания: package discovery/resources/dependencies/entry points/backend прежние, новые source/proofs проверены адресно. [Следующий шаг](../roadmap.md#после-m69).
