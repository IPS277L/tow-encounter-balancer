# ADR-0067: группа PC против Minions и обычных Brutes

Дата: 2026-11-04. Статус: **M11 реализована и проверена в указанной границе**.

## Выбор и источники

После M10 пользователь поручил продолжить. Следующая конечная функция — расширить существующую PC melee family числовыми Brutes и смешанным enemy reserve Minion/Brute. Это добавляет противника, переживающего несколько Wounds, без изменения поддержки PC-ран или стратегии Fate.

Адресно прочитаны локальные извлечения GM1.1, Allies and Antagonists / Minions91 и Brutes92; PG1.4, Wounds Table190–191. Minion побеждается одной Wound. Brute не бросает Wounds Table: предел ран и возможные изменения при ранении задаёт его профиль. GM92 также преобразует дополнительные Wounds dice в дополнительные Wounds; выбранный ordinary Melee срез таких модификаторов не создаёт. K1 уже реализует profile injury, его правило не переписывается.

Scope ограничен явно authored static numeric Melee profiles с прежними подтверждениями сцены/no additional abilities: без on-Wound изменений, Trait/Ability/Reactions, магии, mounts, дополнительных атак или негласной интерпретации бестиария. Ввод не утверждает поддержку любого книжного Brute. `wound_limit` — supplied положительный предел именно профиля NPC, не прототипный предел ран PC. Champions/Monstrosities не допускаются. Существующие PC Wounds1–10/lethal24+ и unsupported11–23 сохраняются.

## Поведение и контракт

Используем существующие domain/owner/runner/trials/balance/CLI. После каждой NPC Wound сохраняется canonical K1 profile result и обязательный bound acknowledgement изменения. Пока предел не достигнут, NPC остаётся живой целью/участником, участвует в outnumbering и действует по прежнему профилю. Только при фактическом defeat применяется выбранное caller/GM disposition и исключение из оставшихся ходов. Полностью выполненные обязательные последствия предшествуют новому обычному действию и итоговому исходу.

`PcProfileWoundProof(source: ProfileStateChangeRequest, decision: MinionDefeatDecision | None)` заменяет single-purpose `PcMinionDefeatProof`. Для nonterminal change `decision` обязан быть None; при defeat обязателен точный source-bound caller/GM decision. Общий existing `MinionDefeatDecision` переиспользуется как данные решения, применимого к побеждённому Brute по ссылке GM92 «see Minions»; остальные NPC families не переименовываем. Legacy PC proof alias не сохраняем.

В текущем PC JSON1 каждый `enemies[].definition` теперь обязательно содержит `injury_policy` (`minion`/`brute`) и `wound_limit`. Minion требует1; Brute использует заданный профильный предел. Оба поля сохраняются без нормализации в request/result/candidate echoes. Старый shape без них отклоняется. Новая версия wire/новая family/команда не нужны. Balanced generation группирует только по полному definition, включая policy/limit; одинаковые числа атаки не объединяют разные типы. Party и per-PC loss accounting неизменны.

## Конечная приёмка

1. Полный pre-RNG допуск двух разрешённых типов и явного лимита, строгие bool/int/Enum/identity checks; свежие snapshots и matching limit, запрет Champion/Monstrosity/abilities.
2. Actual PC Attack → nonterminal Brute Wound → acknowledgement → Brute attack; последняя Wound → caller/GM defeat → exclusion, ретаргет и пересчёт outnumbering. Нет PLAYER lifecycle/table/daily для NPC и нет RNG в acknowledgement. Repeated Staggered→Wound работает с обоими типами.
3. Full source/history/replay/forgery guards для pending и profile branch; mixed reserve/count search сохраняет policy/limit и все старые данные, denominator/selection неизменны.
4. Independent trials и один actual mixed sequential/process путь, строгие JSON1 schemas/errors/source echo, исполняемые mixed public examples и обновлённые нынешние Minion requests.

Адресная проверка PC family и ближайших K1 profile-injury/Attack paths, offline schema refs и репрезентативный CLI/process. Полный regression/wheel не нужны без выявленного внешнего риска или изменений поставки. Сначала выполнить проверки поведения, затем нужные сквозные cases; не повторять успешную дорогую матрицу автоматически.

## Реализация и фактическая проверка

Оба типа подключены к существующей PC family через полный NPC source. Nonterminal change подтверждается до следующего действия; final change требует точного GM decision. Caller policy/limit не выводятся из ID и не нормализуются. Изменены только PC admission/owner/projection/runner, codec/common schema, сообщения generation и CLI help; общие K1 reducers и механизм поставки прежние. Simulation/summary и selection переиспользуются без новых исходов/seed scheme.

Добавлены [7 deterministic domain/engine cases](../../tests/unit/test_m11_pc_melee_brutes.py), [3 mixed trials/generation cases](../../tests/integration/test_m11_pc_melee_brutes.py),2wire cases и1schema case. Сохранены прежние уникальные PC/Minion/party проверки. Read-only review сверил actual K1 profile result, acknowledgement и full-source/replay/type guards; пробелов, требующих изменения игровой границы, не найдено.

При `PYTHONPATH=src` один адресный `.venv/Scripts/python.exe -m unittest ... -v` прошёл **181 tests, OK/51.332s** с первого раза, без failures/errors/skips; `.cache/m11-subsystem.log`. Набор включал все PC unit/integration modules M9–M11, `test_k1_injury_resolution`, `test_k1_kernel`, `test_k1_attack_action_execution`, `test_k1_npc_attack_kernel_cycle`, `test_m8_magic_json_v6_schemas` и один `test_command_selects_its_own_error_family_even_without_kind` из Magic CLI. Windows process/temp cases сразу выполнены вне sandbox по уже установленной причине WinError5. Подтверждены actual nonterminal Brute Attack, final exclusion/retarget/outnumbering, mixed sequential/process parity, aggregate-only reports и representative module/console CLI. Ранее pure wire/schema25tests OK/1.999s; эти IDs входят в основной набор.

Все6 public requests M9/M10/M11 исполнены реальными CLI, полные request echoes сверены и результаты сохранены. Minion-only M9/M10 сохраняют прежние игровые наблюдения; в их нынешнем wire явно добавлены policy/limit. В [M11 simulation](../examples/m11/pc-melee-simulation.result.json) слабая party даёт12unsupported из12, в одном таком prefix подтверждена смерть товарища. Это не12поражений и не оценка вероятности победы. [M11 balance](../examples/m11/pc-melee-balance.result.json): Brute-only0,1 даёт8objective/0unsupported и выбран;1,1 —6objective/2unsupported;2,1 —2objective/6unsupported, оба исключены из selection. Главным ограничением следующих функций остаются тяжёлые PC-раны.

PC bundle сохраняет7schemas/90offline refs; shared bundle и help проверены адресно. Полный regression/wheel не повторялись: за пределами PC boundary риска не выявлено, package discovery/resources/entry points не менялись. Эти результаты не являются утверждением поддержки Brutes с on-Wound behaviours или всех NPC.
