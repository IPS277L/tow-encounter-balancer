# Аудит одного Casting-действия M8

Дата: 2026-09-29. [ADR-0035](../decisions/ADR-0035-cowardly-flight-casting-boundary.md) закрыт **в границе одного действия**: input/preflight, executor, source-bound result и самостоятельный production-пример согласованы. Полный бой с магом, следующий ход Broken и разрешение Miscast этим не объявляются готовыми.

## Проверенная граница

| Область | Реализация и evidence |
| --- | --- |
| Вход | [Input models](../../src/towr/domain/cowardly_flight_casting_models.py): frozen/slotted definition отдельно от actor/magic/round state, explicit facts и CAST_WHEN_READY, один standard spell Improvise. [23 admission tests](../../tests/unit/test_m8_cowardly_flight_casting_models.py) проверяют types/facts, actor/slot/Lore/pool, полный Zone target order, healthy Minions без Conditions и Give Ground, empty Zone, обе стороны caster, immutable tuple-copy |
| Одно действие | [Executor](../../src/towr/engine/cowardly_flight_casting.py) вызывает execute_casting_attempt ровно один раз; WAIT/CAST/Miscast сохраняют один receipt и активный ход. Pure pool projection используется только для решения; post-Test получает исходный Casting result. End-turn, таблица Miscast и автоматический Recover отсутствуют |
| Состояния магии | WAIT сохраняет successes/Lore/latest roll; normal CAST очищает successes/Lore, сохраняя pool; Potency последнего roll. Pool == Level допускает normal decision, > Level возвращает pending source/state без выбора desperate spell или подготовки. [24 unit tests](../../tests/unit/test_m8_cowardly_flight_casting.py) проверяют точное число бросков, девятки без повторного расхода, state/branch/source splices, ошибки без retry и повтор immutable input |
| Заклинание | Canonical definition → preflight → target Potency → Curse Zone batch → Willpower. Все enemies выбранной Zone в порядке round participants; spatial order не задаёт порядок Tests. Healthy targets, отсутствие модификаторов/иммунитета и невозможность Give Ground заданы явно. Broken сохраняется как Condition, не defeat. Zero Potency/empty Zone дают no-effect результаты без лишних Tests |
| Результат | [Result models](../../src/towr/domain/cowardly_flight_casting_result_models.py) сверяют полные phase payloads, normal trace/profile, decision, targets и spatial snapshot. Returned snapshots и pending Miscast — read-only projections. Validators не вызывают rules/RNG. Смена source при прежних IDs, неверная Potency, чужие target/context, порядок, Broken или pending roll отклоняются |
| Перенос между ходами | [2 integration tests](../../tests/integration/test_m8_cowardly_flight_casting.py) выполняют end-turn мага, Recover остальных, advance/start/reserve следующего раунда и второй cast. Successes/pool мага не очищаются между активациями; WAIT → CAST и WAIT → mandatory Miscast проверены |
| Публичное использование | [Standalone example](../examples/m8/casting_action.py) импортирует только stdlib/public APIs. [Subprocess test](../../tests/integration/test_m8_casting_example.py) запускает его вне cwd и сверяет [сохранённые наблюдения](../examples/m8/casting_action.output.txt). В примере 6 supplied activations, 24 заданных d10, отсутствие изменения input/global RNG и отказ replay/actor/pending до RNG |
| Установка и зависимости | Wheel построен offline и установлен в отдельный build target; пример запущен с `-S`, только installed target в PYTHONPATH, из временного cwd. Путь импортированного engine проверен: код загружен из wheel, не src. Вывод совпал, stderr пуст. Canonical definition остаётся одним объектом в domain с прежним rules реэкспортом |

Production-код и существующие tests в этом аудите не менялись. Новый test защищает самостоятельный пример. Source guards подтверждают согласованность предоставленных данных; они не удостоверяют истинность GM facts, происхождение dice или исторического владельца actor-agnostic WizardMagicState. Откат caller к старому immutable input остаётся допустимым воспроизведением вычисления, а не новым расходом в текущем состоянии боя.

## Непосредственная сверка книг

Прочитаны локальные извлечённые страницы выбранных редакций:

| Книга, глава и страница | Проверено |
| --- | --- |
| BOOK-PLAYER-GUIDE 1.4, Rules / Combat Actions / Improvise, стр. 117 | Spell использует Improvise action |
| Та же книга, Magic in the Old World / Casting a Spell / Interrupted Casting, стр. 156 | Действие за каждый Exacting Willpower Test, Lore до броска, накопление и normal CAST, последствия skipped Casting; armour/bulky item даёт Grim |
| Та же книга, Spell Potency / Miscasts and the Rule of Nine, стр. 157 | Potency последнего roll, возможность WAIT, неперебрасываемые 9, строгий порог > Level, desperate spell до таблицы с +1d, очистка после разрешения эффекта |
| Та же книга, Formal Spells, стр. 160 | Memorised spell либо grimoire; чужой grimoire даёт Grim; текущий допуск выбирает memorised вариант |
| Та же книга, Battle Magic / Curse of Cowardly Flight, стр. 162 | CV3/Zone/Long/Instant; все enemies Give Ground если могут, затем Willpower против Potency, иначе Broken |
| Та же книга, Rules / Conditions / Broken, стр. 122 | Следующий ход требует ухода в Zone без enemies, затем возможен Recover; это не defeat |
| BOOK-GM-GUIDE 1.1, Allies and Antagonists / Champions, стр. 92; Hermit Witch, стр. 130 | Champion использует Wounds Table; книжный Level 2 Wizard не превращается в Minion ради существующего battle runner |

Числа `3d/3` и Level 2 в примере — authored inputs, не профиль Hermit Witch. У caster нет назначенной injury policy. Новых Rule IDs/house rules и противоречий не выявлено; Magic Resistance/AMBIGUITY-002 и открытые вопросы отдельных Miscast effects не используются этим допуском. Проверки Potency 0 используют существующий K1 contract, не новую трактовку spell.

## Наблюдения примера

| Вызов | Результат | Существенные данные | d10 |
| --- | --- | --- | --- |
| Первый cast | WAITING | successes 1, pool 0 | 3 |
| Следующая supplied activation | SPELL_RESOLVED | accumulated 3, Potency 2; first resisted, second Broken | 9 |
| Pool достигает Level | WAITING | pool 2, successes 1 | 3 |
| Следующая supplied activation | MISCAST_REQUIRED | pool 3, successes 3; normal CAST не выполняется | 3 |
| Ранее удержанные successes, последний roll 0 | SPELL_RESOLVED | Potency 0, два target records, без Willpower Tests | 3 |
| Пустая Zone | SPELL_RESOLVED | targets 0, без Willpower Tests | 3 |

Пример не выполняет промежуточные ходы: новые activations задаёт caller. Реальный переход раунда проверен отдельными integration tests. Изолированная Zone объясняет supplied can_give_ground=False; доступность движения и Range не вычисляются по названиям/графу. Не существует автоматического продолжения с Broken targets или обязательным Miscast.

## Проверки и ограничения

Windows / Python 3.14.5: **227 связанных tests — OK (1,004 с)**, включая **50 tests M8** и 177 K1. Standalone example из repo cwd, temporary cwd и установленного wheel даёт одинаковый сохранённый stdout, stderr пуст. `compileall` и `git diff --check` успешны; 2348 локальных Markdown-путей существуют. SHA-256 подтвердил неизменность всех 676 существовавших Python-файлов src/tests/tools; проверены UTF-8/newline/whitespace новых файлов и public imports примера. Wheel собран без сети с локальным setuptools 84.0.0 и без постоянного pip cache; установлен в `build/m8-casting-audit/installed`, существующая .venv не изменялась. Логи build/install и installed stdout находятся в ignored build. Это проверка импорта/работы typed API; полный dependency resolver или magic CLI не проверялись.

Полный набор повторно не запускался: последняя полная проверка неизменённого production-кода — **2713 tests OK (395,812 с)**; в этом аудите добавлен один subprocess test. Python 3.12/другие ОС и performance не проверялись. Исходные незакоммиченные изменения сохранены; commit/push не выполнялись.

## Следующий законченный шаг

Подготовить **контракт magic encounter** по книгам: инвентаризировать готовые Champion injury/attack, Casting, Broken movement/Recover и Miscast consumers; определить первый поддерживаемый состав/тактику, владельца состояний и обязательных продолжений. Зафиксировать action dispatch, когда encounter обязан остановиться с unsupported_path, и какие зависимости нужно реализовать до запуска боя. Прямо проверить PG1.4 Casting/Miscasts/Conditions и GM1.1 Champion-профили; существенные неоднозначности вынести на решение пользователя.

Не подменять Champion мага Minion-моделью, Broken победой или обязательный Miscast успешным завершением. Не добавлять общий battle aggregate, новые spells, Monte Carlo/balance или JSON/CLI по одному факту готовности action boundary. Направление остаётся выбранной пользователем магией; повторного выбора направления не требуется.

Продолжение аудита: [ADR-0036](../decisions/ADR-0036-magic-encounter-integration.md) подготовлен. Inventory подтверждает разрыв между отдельными K1 reducers и encounter consumers; ближайшая реализация — actor-bound Casting → roster application, затем зависимости в порядке ADR. Выводы этого аудита об отсутствии полного encounter остаются в силе.
