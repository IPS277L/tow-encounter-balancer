# Аудит внешней границы M6 — Melee JSON/CLI

Дата: 2026-09-29. Область: [ADR-0027](../decisions/ADR-0027-melee-json-cli-v1.md), `simulate-melee` и `balance-melee`. Оба пути реализованы в границе неподвижного numeric Minion-сценария. Это закрывает внешний интерфейс текущего M6; неподдержанные игровые сценарии остаются за его пределами.

## Матрица контракта и доказательств

| Требование | Реализация и проверка |
| --- | --- |
| Строгий вход, версии, отдельные families | Общий [reader](../../src/towr/adapters/_json_common.py), отдельные Melee errors и parsers. [Simulation tests](../../tests/unit/test_m6_melee_json.py) и [balance tests](../../tests/unit/test_m6_melee_balance_json.py): duplicate keys, Unicode/UTF-8, nonfinite/float/exponent tokens, required/unknown fields на каждом уровне, uint64 seed, exact большие counts, JSON Pointer и cross-family отказ. |
| Шесть локальных Schema | [Registry](../../src/towr/adapters/melee_json_schema.py) и [package data](../../pyproject.toml). Draft 2020-12 request/result/error для каждого семейства; bundled refs на Melee scenario и прежние ranged seed/execution fragments. Проверены из установленного wheel без исходного checkout в import path. |
| Явные профили, facts и решения GM | [Scenario mapper](../../src/towr/adapters/_melee_scenario_json.py) вызывает public constructors. Tests сохраняют hands/Protection Skill, True/False outnumbering approval, полный target priority/defeat policy, отдельные reserve/family facts и escape path. Close, awareness и применимость способностей не выводятся из ID или Zone. |
| Неизменяемые команды и полный source | [Simulation command](../../src/towr/application/melee_simulation_models.py), [balance command/result](../../src/towr/application/melee_balance_models.py). Frozen/slotted, копирование порядков в tuple, exact source chain; encoder проверяет command → wire → command. Несовместимые independent combat/spatial orders отклоняются. Проверены одинаковые ID при отличающихся facts/policies/window. |
| Pure adapters и preflight | Parsers проверяют admission, C и полный staged budget до materialization/RNG; encoders не запускают генератор/симулятор/pool. Отдельные negative tests проверяют отсутствие вызовов и потери полей. Schema проверяет форму, typed models — семантические связи. |
| Simulation service и summary | [Service](../../src/towr/application/melee_simulation_service.py) проверяет полный result/source, затем summary/source. [Unit](../../tests/unit/test_m6_melee_service.py) и [integration](../../tests/integration/test_m6_melee_json.py): exact dispatch/options, четыре исхода, суммы, отсутствие records в wire, равные sequential/process results. |
| Генерация и staged balance | [Service](../../src/towr/application/melee_balance_service.py), [encoder](../../src/towr/adapters/melee_balance_json.py). Полный ordered catalog, counts из vectors, planned/actual trials, Fraction rates и stage/source chain. [JSON tests](../../tests/unit/test_m6_melee_balance_json.py) различают local selection, continuation вне окна, final selection и early stop; unsupported остаётся отдельным исходом. |
| Ошибки и остановка | [Balance unit](../../tests/unit/test_m6_melee_balance_service.py), [integration](../../tests/integration/test_m6_melee_balance_service.py), [simulation errors](../../tests/unit/test_m6_melee_error_json.py): active phase, outer request ID, известные candidate/counts/stage, неизвестный контекст null, Python cause/notes, общие wire messages. Ошибка после готового composition/этапа/trial не возвращает partial report. BaseException проходит. |
| CLI и I/O | [CLI](../../src/towr/cli.py), [simulation unit](../../tests/unit/test_m6_melee_cli.py)/[integration](../../tests/integration/test_m6_melee_cli.py), [balance unit](../../tests/unit/test_m6_melee_balance_cli.py)/[integration](../../tests/integration/test_m6_melee_balance_cli.py). UTF-8 bytes/file/stdin, exit 0/2/3/4, read/write/flush/closed streams, диагностический pipe, отсутствие второй записи и fallback; encoder failures не маскируются. |
| Установка и совместимость | Module/console × sequential/process вне repo без PYTHONPATH; все 337 Python/Schema файлов установленного пакета равны src после нормализации line endings. Обе ranged-команды и четыре error families сохранены. Установка не содержит tests; production и standalone examples не импортируют tests/private books. |

## Книги и граница модели

Непосредственно перечитаны локальные извлечённые страницы:

- BOOK-PLAYER-GUIDE 1.4, Rules / The Battlefield / Range, стр. 114: Close требует досягаемости; одна Zone сама по себе её не доказывает.
- BOOK-PLAYER-GUIDE 1.4, Rules / Attack Tests / Attack Modifiers, стр. 118–119: обычный Melee/Brawn outnumbering даёт +1d; исключаются defeated/Defenceless/non-combatants, GM может удержать бонус. Пример 7:6 не задаёт порог.
- BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91: один Wound побеждает Minion, disposition определяется атакующим с учётом решения GM.
- BOOK-GM-GUIDE 1.1, Allies and Antagonists / Understanding NPC Profiles, стр. 93: Attack/Protection передаются как профильные числа, NPC не получают автоматически все преимущества оружия PC.
- BOOK-GM-GUIDE 1.1, Allies and Antagonists / Brigands & Footpads, стр. 97: Footpad подходит к примеру обычного боя; его Lurker относится к обнаружению вне боя. Brigand Craven Opportunist меняет бонус на +2d и не покрывается ordinary numeric admission.

Книги доступны; новых противоречий и house rules не обнаружено. [RULE-COMBAT-009](../rules/combat.md#rule-combat-009--модификаторы-атаки) и [RULE-NPC-002](../rules/npcs.md#rule-npc-002--minion) не меняются. Schema/source IDs не доказывают истинность supplied facts или полноту применимых Abilities. Caller не вправе удалять способность только ради допуска сценария.

## Установленный пакет и примеры

Повторно использован wheel четвёртого среза ADR-0027, установленный с runtime dependencies в отдельный временный venv. Код с момента сборки не менялся; соответствие всех 337 файлов проверено заново. Установленный `pip check` успешен. Рабочий каталог расположен вне repo, PYTHONPATH удалён, text streams ASCII, JSON передаётся UTF-8 bytes. Module использует stdin, console — относительный файл; Unicode request ID сохраняется.

Оба Melee request из [примеров](../examples/m6/json/README.md) прошли module/console × sequential/process. Результаты равны после исключения echoed execution; simulation исполняет 8 trials на запуск, balance — пять составов, planned=actual=18. Проверены также прежние ranged simulate/balance через обе точки входа, malformed JSON с собственным error kind всех четырёх команд, help/usage и missing-file I/O. Exit 3 и ошибки write/flush/pipe дополнительно покрыты указанными unit/integration tests.

[Contract probe](../examples/m6/json_contract_probe.py) и [production balance example](../examples/m6/melee_balance.py) исполняются установленным Python вне repo без tests/private builders. Probe проверяет 52 trials и семь semantic refusals; balance example — 208 trials (104 на backend). Исходные fixtures и typed inputs сохраняются. Сохранённые MC percentages не используются как oracle нового прогона; проверяются равенство backend и контракт результата.

## Ограничения

- Только свежие здоровые Minions, обычный порядок сторон, один stationary Close Melee attack, явные facts/GM policies и текущая repeated-Staggered policy. Нет PC/Brute/Champion, смешанного ranged+Melee, движения, автоматической awareness, общего battle aggregate или каталога способностей.
- Генерация перебирает численность явных групп резерва с фиксированными profiles/policies. Она не создаёт новые профили и не меняет тактику. Пустой final selection допустим и не заменяется ближайшим составом. Unsupported observations не считаются скрытой победой/поражением.
- Каждый этап оплачивает полный повторный пакет с trial index 0. Нет reuse префикса или обещания статистической независимости этапов; окно задаётся пользователем, пресетов Easy/Medium нет.
- Compact wire не означает streaming: simulation материализует records, генератор — семейство составов, encoder — полный JSON. Бюджеты ограничивают число работ, но не гарантируют wall time/RAM. Нет автоматического выбора backend или нового performance обещания.
- Seed scheme/runtime metadata описывают штатный путь `random.Random`, не удостоверяют происхождение произвольно построенного typed aggregate или версию кода хешем. Custom RNG нельзя выдавать за штатный CLI результат. Source equality проверяет структуру, не криптографическое происхождение.
- Проверено на Windows/Python 3.14.5. Python 3.12, другие ОС и большие нагрузки в этом аудите не проверялись. Получатель должен сохранять точные большие JSON integers и отбрасывать неполный output при I/O failure.

## Проверки и продолжение

241 targeted/regression tests OK (178,641 с); compileall, 1488 локальных Markdown-путей, diff --check и whitespace untracked файлов успешны. Результаты текущего запуска и точные команды приведены в [статусе проекта](../project-status.md#последняя-проверка). Отдельный набор ADR-0027 содержит 134 tests; regression дополнительно включает прежние ranged JSON/services/CLI. Последняя полная проверка реализации: 2298 tests OK; audit не изменяет src/tests.

План ADR-0027 исчерпан. Пользователь выбрал смешанный дальний и ближний бой: [ADR-0028](../decisions/ADR-0028-mixed-minion-scenario.md) и [probe M7](../examples/m7/README.md) подготовлены. Production mixed admission и mixed runner реализованы; отдельный аудит одиночного mixed-сценария ещё предстоит. Вывод этого аудита относится только к ADR-0027.
