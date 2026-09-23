# Правила боя TOWR

Статус: спецификация упрощённого прототипа M1. Версия прототипа: `towr 0.1.0`.

Player’s Guide и Gamemaster’s Guide имеют приоритет над этим документом. Любое правило ниже может быть заменено после извлечения и согласования соответствующего книжного правила. Этот файл описывает только поведение существующего прототипа, а не окончательную систему TOWR.

Книжные правила K1, включая Casting, Miscast и lifecycle treatment/healing Wounds, нормализуются отдельно в [`docs/rules/`](rules/) и намеренно не переносятся в эту спецификацию старого прототипа.

## Бросок

Профиль `X/Y` означает бросок `X` десятигранных кубов с подсчётом результатов `<= Y`.

- количество кубов: от 1 до 10;
- порог успеха: от 1 до 10;
- особое правило: при одном кубе успехом считается только результат `1`, независимо от указанного порога.

## Встречная проверка

Атакующий бросает профиль атаки, защищающийся — `DEF`.

- больше успехов у атакующего: атака успешна;
- ненулевая ничья: атака успешна;
- меньше успехов у атакующего: промах;
- `0 против 0`: специальный исход.

При промахе атакующий получает один stagger, только если у него ещё нет stagger. Уже имеющийся stagger не увеличивается и не превращается в рану вследствие промаха.

При `0 против 0` обе стороны получают обычный накапливаемый stagger. Поэтому теоретически возможна одновременная гибель сторон.

## Урон, stagger и раны

При успешной атаке:

```text
damage = attacker_successes - defender_successes + weapon
```

- `damage > RES`: цель получает одну рану;
- `damage <= RES`: цель получает один обычный stagger;
- второй обычный stagger превращается в одну рану;
- получение любой раны сбрасывает накопленный stagger в `0`;
- боец выбывает, когда число ран достигает лимита.

## Ход боя первого среза

- сначала действует сторона игроков, затем сторона монстров;
- в первом срезе каждый живой боец выполняет все заданные атаки один раз в порядке конфигурации;
- перед каждым действием цель выбирается заново;
- выбывший боец больше не действует;
- бой заканчивается сразу после уничтожения одной или обеих сторон;
- равенство подходящих целей разрешается стабильным порядком состава;
- настраиваемый предел раундов завершает затянувшийся бой исходом `round_limit`.

Этот порядок действий является временной политикой первого среза. В дальнейшем контроллер должен выбирать порядок атак, помощи, магии и других действий.

## Возможные исходы

- победа игроков;
- победа монстров;
- одновременная гибель — ничья;
- достижение предела раундов.

## Сложность

Текущие диапазоны Easy/Medium/Hard/Impossible являются предварительными целевыми окнами, а не жёсткой полной классификацией. Их нужно хранить в конфигурации и пересмотреть после появления проверенного симулятора.

## Ссылка на книжную реализацию скрытности

P1 не моделирует Move Quietly и историю укрытий. K1 атомарно исполняет hidden Attack и регистрирует раскрытую позицию независимо от попадания, затем передаёт actor-scoped историю следующей подготовке. Нормативное описание: [регистрация раскрытого укрытия](rules/combat.md#регистрация-раскрытого-укрытия), BOOK-PLAYER-GUIDE 1.4, Rules / Attack Tests, стр. 118.

K1 `HiddenLifecycleState` объединяет активную Move Quietly opportunity и consumption/history одного бойца; Move Quietly всех outcomes, continuation, standalone loss, completed free-movement/Give Ground loss и registered Attack возвращают согласованный snapshot. Это orchestration-контракт книжной реализации, не изменение P1; [подробности](rules/combat.md#actor-scoped-hidden-lifecycle).

Свободное движение из укрытия и потеря opportunity теперь доступны одним атомарным K1 adapter: typed source-bound request, один movement resolver, один consumer и общий lifecycle result; игровые правила не меняются (PG 1.4, Rules / Combat Actions и Manoeuvre, стр. 116–117).

Give Ground из укрытия доступен одним атомарным K1 adapter с сохранением единственного movement/Broken result и проверками до движения (PG 1.4, Rules / Manoeuvre, стр. 117; Giving Ground, стр. 119). История укрытий при этом не меняется.

Same-round Give Ground hidden boundary принимает также проверенную цепочку готовых free-movement/Give Ground других бойцов при неизменной позиции владельца. Это расширение подтверждения spatial continuity, не новое правило скрытности.

Интеграционный K1 тест подтверждает полный путь от потери укрытия через Give Ground/Broken и Recover до нового скрытия, Aim и prepared Crossbow Attack. Broken снимается только успешным Willpower в Zone без врага; при failure действие завершается с сохранением Condition. Новых правил или P1 изменений нет.

Интеграционный сценарий K1 продолжен через weapon-bound Reload (Dexterity/Exacting) и второй скрытый Crossbow выстрел. Проверены накопление 0 → 1 → 2 успеха за отдельные действия, запрет атаки до completion и прежнего укрытия, два reload cycle и непрерывные history/consumption chains. Правила и P1 не менялись: PG 1.4, Equipment / Ranged Weapons, стр. 94–95; Rules / Exacting Tests, стр. 110; Attack Tests, стр. 118.

Сквозной K1 сценарий после Reload проверяет также провал Move Quietly и успех с явным отказом от скрытия: оба тратят действие без hidden opportunity и регистрации позиции. Следующая успешная попытка и Attack используют возвращённые состояния, заряженное оружие и прежние consumption chains. Основание: PG 1.4, Rules / Manoeuvre, стр. 117; Attack Tests, стр. 118. Правила и P1 не менялись.

K1 интеграционный тест подтверждает сохранение активной hidden opportunity через нулевой, частичный и завершающий Reload при неизменной позиции без раскрытия. Только последующая атака расходует opportunity и регистрирует укрытие. Это проверка существующего continuation и исправления CODE-CONFLICT-001, без изменения правил: PG 1.4, Equipment / Ranged Weapons, стр. 94–95; Rules / Manoeuvre, стр. 117; Attack Tests, стр. 118.

K1 интеграция явного раскрытия после частичного Reload проверена: hidden opportunity теряется однократно, progress оружия сохраняется, раскрытая без атаки позиция не регистрируется как used. После завершения Reload старая hidden Attack отвергается до RNG, новая Move Quietly и hit/miss продолжают историю. Основание: PG 1.4, Equipment / Ranged Weapons, стр. 94–95; Rules / Manoeuvre и Attack Tests, стр. 117–118. Раскрытие задано caller, automatic awareness не добавлено.

K1 интеграционный сценарий подтверждает независимость Aim и скрытности: промежуточный completed Reload отменяет Aim даже при нулевом вкладе, но сохраняет hidden opportunity при неизменной позиции без раскрытия. Финальный hit/miss не получает Aim dice. Учёт LOST follow-up подключён к отдельному consumer; выбор следующего действия остаётся внешним. Основание: PG 1.4, Rules / Aim, стр. 116; Manoeuvre, стр. 117. Правила и P1 не менялись.

K1 получил чистый consumer готового LOST Aim по completed неатакующему receipt. Он проверяет actor/action/chronology и атомарно дополняет immutable историю Aim source/follow-up IDs, отклоняя повтор source даже с новым follow-up ID. Интеграция Reload/hidden Attack использует возвращённую историю. Проверка source history подключена отдельным adapter над existing ranged preparation. Правило не менялось: PG 1.4, Rules / Aim, стр. 116.

Подготовка K1 ranged Attack теперь имеет отдельный adapter с AimConsumptionState: погашенный Aim source отвергается до построения бонуса независимо от новых preparation/follow-up IDs. Без Aim и со свежим Aim прежняя preparation вызывается один раз; history/trace и обе consumption chains сохраняются. Основание: PG 1.4, Rules / Aim, стр. 116. APPLIED registration доступна отдельным consumer завершённой атаки.

K1 регистрирует completed Aim-bound ranged Attack в AimConsumptionState через register_aim_ranged_attack: actor/receipt/APPLIED/prefix проверяются, исходный Aim ID погашается независимо от hit/miss и нулевого bonus, готовая follow-up chain переносится один раз. Возвращённая история запрещает этот Aim в следующей history-aware preparation. Основание: PG 1.4, Rules / Aim, стр. 116. Нет повторного исполнения Attack/RNG; атомарный execute_registered_aim_ranged_attack проверяет actor/source/prefix/chronology до RNG, затем один раз исполняет Attack и регистрирует готовый результат. Immutable result сохраняет sole execution, receipt, weapon state и обе Aim истории; RNG при исключении не откатывается. Prepared composition с Aim подключена отдельным adapter; совместная hidden/Aim registration подключена отдельным adapter; актуальная history и выбор next action остаются у caller.

K1 execute_registered_prepared_aim_ranged_attack объединяет prepared Attack с Aim и регистрацию source/follow-up history. Проверка истории происходит до RNG; один prepared executor сохраняет profile trace/weapon/receipt, готовый вложенный Aim result регистрируется один раз. Hit/miss и Aim 0 завершают использование одинаково; новые IDs не обходят source guard. No-Aim и hidden composition не включены. Книжное правило не менялось: BOOK-PLAYER-GUIDE 1.4, Rules / Aim, стр. 116.

K1 execute_registered_hidden_aim_attack объединяет prepared hidden Attack с Aim и обе регистрации. Один existing registered hidden executor раскрывает позицию и расходует opportunity, затем register_aim_ranged_attack регистрирует тот же nested execution; оба history preflight выполняются до RNG. Hit/miss и Aim 0 не меняют расход; profile trace, reload cycle и единственный receipt сохраняются. Возвращённые aim_state/hiding_position_state передаются следующей preparation. Правила прежние: BOOK-PLAYER-GUIDE 1.4, Rules / Aim, стр. 116; Manoeuvre, стр. 117; Attack Tests, стр. 118. HiddenLifecycleState подключён отдельным adapter; автоматического awareness нет.

K1 execute_hidden_lifecycle_aim_attack сверяет exact active source, opportunity prefix и историю укрытий текущего HiddenLifecycleState до совместного Aim/hidden исполнения. Единственный registered hidden result применяется existing lifecycle consumer, закрывая opportunity без повторной атаки; Aim history переносится из того же result. Первый выстрел hidden recovery cycle использует этот путь. Caller сохраняет оба snapshot; правила прежние: PG 1.4, Rules / Aim, стр. 116; Manoeuvre, стр. 117; Attack Tests, стр. 118.

Восьмой тест hidden recovery cycle проверяет свежий Aim после Crossbow Reload 0/1/2 и Move Quietly в новом укрытии. Первый и второй Aim имеют разные source IDs; оба выстрела используют execute_hidden_lifecycle_aim_attack, между ними переносятся возвращённые lifecycle/Aim histories без ручного добавления ID. Проверены 8 сочетаний: первый Aim 0/1 × второй Aim 0/1 × второй hit/miss; первый выстрел всегда miss, чтобы intervening idle Recover не требовал дополнительных Condition transitions цели. Повтор первого Aim с новыми preparation/follow-up IDs отклоняется history-aware preparation и совместным execution request до RNG. Проверяются ровно два kernel-вызова за сценарий, один receipt на каждый выстрел, обе использованные позиции, оба Aim sources/follow-ups, сохранённая trace, два reload cycle, неизменность входов и replay завершённого результата. Production API и правила не менялись. Источники: BOOK-PLAYER-GUIDE 1.4, Equipment / Ranged Weapons, стр. 94–95; Rules / Aim, стр. 116; Manoeuvre / Move Quietly, стр. 117; Attack Tests, стр. 118.

K1 consume_attack_lost_aim регистрирует завершённую обычную Attack по другой цели либо Melee/Brawn по исходной как расход готового LOST Aim. Actor/target/source/state/receipt/chronology сверяются, Aim source/follow-up дополняют общую immutable историю один раз; hit/miss и нулевой Aim не сохраняют бонус. Следующая history-aware preparation отвергает этот source даже с новыми IDs. Нет повторного исполнения или RNG; другие attacking actions пока отдельно; atomic execution+registration доступен отдельным adapter. Правило прежнее: BOOK-PLAYER-GUIDE 1.4, Rules / Aim, стр. 116.

K1 execute_registered_aim_loss_attack проверяет history, LOST/exact Attack по другой цели либо Melee/Brawn по исходной, actor/slot/chronology до RNG; затем один execute_attack_action и один consume_attack_lost_aim возвращают неизменяемую регистрацию с единственным execution/receipt и новой history. Повтор с новыми IDs не обходит source guard. Основание прежнее: BOOK-PLAYER-GUIDE 1.4, Rules / Aim, стр. 116. Caller выбирает next action; composed attacking adapters не добавлены.

Интеграция Aim по A → Attack по B / LOST → свежий Aim по A → APPLIED проверена через действительный round/turn scheduler и возвращённую историю: первая атака не получает бонус, вторая получает свежий, старый Aim с новыми IDs не применяется. 16 сочетаний Aim 0/2 и обоих hit/miss; BOOK-PLAYER-GUIDE 1.4, Rules / Combat Actions / Aim, стр. 116. Новых правил нет.

Same-target Melee/Brawn LOST → свежий Aim → APPLIED проверены интеграционно с реальным scheduler и переносом Conditions через Recover: цель восстанавливается после hit, явно Close союзник помогает hero после close miss. История блокирует старый Aim и разрешает свежий. PG 1.4, Rules / Aim, стр. 116; Recover и Attack Tests, стр. 118; Failed/Successful Attacks, стр. 119. Production rules не изменены.

K1 consume_charge_lost_aim регистрирует LOST после готового ordinary Melee Charge. Charge является промежуточным действием и расходует Aim независимо от цели, hit/miss и числа успехов Aim; сохраняются готовые движение/атака и бонус Charge +1d. Source/follow-up history дополняется однократно, replay запрещён. PG 1.4, Rules / Aim, стр. 116; Manoeuvre / Charge, стр. 117. Atomic guard до движения/RNG реализован через execute_registered_aim_loss_charge: общий preflight, один Charge executor и один consumer, единственные kernel/receipt и новая history. Повтор source с новыми IDs отклоняется до executor; игровое правило не менялось.

Интеграция Aim → Melee Charge/LOST → свежий Aim → APPLIED проверена с реальными ходами и returned spatial/target/Condition states. Только бонус Charge применяется к первой атаке, свежий Aim — ко второй; старый source не восстанавливается. PG 1.4, Rules / Aim, стр. 116; Manoeuvre / Charge, стр. 117; Recover, стр. 118; Failed/Successful Attacks, стр. 119. Новых игровых правил нет.
