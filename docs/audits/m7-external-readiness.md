# Аудит внешней границы M7 — Mixed JSON/CLI

Дата: 2026-09-29. Область: [ADR-0034](../decisions/ADR-0034-mixed-json-cli-v1.md), `simulate-mixed` и `balance-mixed`. Обе команды реализованы в границе неподвижного numeric Minion-сценария [ADR-0028](../decisions/ADR-0028-mixed-minion-scenario.md). Исправлений production-кода и новых тестов при аудите не потребовалось.

## Матрица контракта и доказательств

| Требование | Реализация и проверка |
| --- | --- |
| Строгий вход и отдельные семейства | Общий [reader](../../src/towr/adapters/_json_common.py), [mixed errors](../../src/towr/adapters/mixed_json_errors.py), [simulation tests](../../tests/unit/test_m7_mixed_json.py) и [balance tests](../../tests/unit/test_m7_mixed_balance_json.py): UTF-8, duplicate keys, BOM/surrogates/nonfinite, exact integer tokens, uint64 seed, версии/kind, missing/unknown fields и JSON Pointer. Чужой формат не вызывает autodetection/fallback. |
| Шесть bundled Schema | [Registry](../../src/towr/adapters/mixed_json_schema.py) разрешает только локальные ресурсы; [package data](../../pyproject.toml) включает request/result/error обоих семейств. Проверены Draft 2020-12 и refs на mixed fragments и прежние ranged seed/execution fragments из установленного wheel. Schema проверяет форму; derived values и source chain проверяют typed models/encoders. |
| Явная mixed-сцена | [Scenario mapper](../../src/towr/adapters/_mixed_scenario_json.py) вызывает public constructors. Полные enemy pairs с сохранением order/orientation, Skill/Range/Hands, definitions/actors/orders, facts и все GM decisions передаются явно. can_leave_zone задаётся каждому actor. Общая Zone не назначает Close; role не выводится из ID. |
| Неизменяемые команды и точный источник | [Simulation command](../../src/towr/application/mixed_simulation_models.py) и [balance command/result](../../src/towr/application/mixed_balance_models.py): frozen/slotted, ordered snapshots копируются в tuple. Encoders проверяют exact source и command → wire → command; несовместимые низкоуровневые порядки отвергаются без молчаливой нормализации. Tests меняют pairs, policies, escape flags, seed/window при прежних ID. |
| Simulation execution и aggregate output | [Service](../../src/towr/application/mixed_simulation_service.py), [adapter](../../src/towr/adapters/mixed_simulation_json.py), [service tests](../../tests/unit/test_m7_mixed_service.py) и [integration](../../tests/integration/test_m7_mixed_json.py): точные options, result/source и summary/source; четыре исхода и счётчики, без trial records на wire. Sequential/process совпадают. |
| Reserve → generation → staged evaluation | [Balance service](../../src/towr/application/mixed_balance_service.py) и [adapter](../../src/towr/adapters/mixed_balance_json.py): отдельные family facts/pairs, fixed perspective, C/полный staged budget до materialization. Каталог содержит все vectors/counts, reports сохраняют Fraction rates и local/continuation/final selection. [Integration](../../tests/integration/test_m7_mixed_balance_json.py) проверяет backend equality и независимые порядки. |
| Недопустимые subset и phase errors | [Service/error tests](../../tests/unit/test_m7_mixed_balance_service.py) и [integration](../../tests/integration/test_m7_mixed_balance_service.py): preflight может допустить bounds, но construction (0,1) теряет Close-цель и завершает весь вызов с generation_failed. Generation/source проверяется до evaluator. Сбой второй materialization и поздний trial failure сохраняют внешний request ID, candidate/counts либо stage/candidate/cause/notes без partial result. |
| CLI/I/O и отсутствие подмены ошибок | [CLI](../../src/towr/cli.py), [simulation unit](../../tests/unit/test_m7_mixed_cli.py)/[integration](../../tests/integration/test_m7_mixed_cli.py), [balance unit](../../tests/unit/test_m7_mixed_balance_cli.py)/[integration](../../tests/integration/test_m7_mixed_balance_cli.py): UTF-8 file/stdin, exit 0/2/3/4, закрытые read/write/flush/diagnostic streams, pipe shutdown без exit 120, один JSON без retry. Семейство выбирает команда. BaseException и encoder failures не превращаются в execution error. |

## Книжная сверка

Непосредственно перечитаны локальные извлечённые страницы выбранных книг:

- **BOOK-PLAYER-GUIDE 1.4**, Equipment / Ranged Weapons, стр. **94**: запрет обычной дальней атаки при Close-враге, Optimum Range и reload; Rules / The Battlefield / Range, стр. **114**: досягаемость и расстояния между Zones.
- Та же книга, Rules / Attack Tests / Attack Modifiers, стр. **118–119**: opposed Attack, локальный обычный Melee/Brawn outnumbering и право GM удержать бонус; Failed/Successful Attacks и Giving Ground, стр. **119**: последствия попадания/промаха и ограничения ухода.
- **BOOK-GM-GUIDE 1.1**, Allies and Antagonists / Minions, стр. **91**: одна Wound и явный disposition; Understanding NPC Profiles, стр. **93**: numeric Attack/Protection и отсутствие автоматического наследования преимуществ оружия PC; Brigands & Footpads, стр. **97**: Footpad Dagger и Brigand Warbow, Lurker вне боя и Craven Opportunist только для Melee.

[RULE-COMBAT-009](../rules/combat.md#rule-combat-009--модификаторы-атаки), [RULE-NPC-002](../rules/npcs.md#rule-npc-002--minion) и existing mixed admission сохранены. Новых Rule IDs, противоречий и house rules нет. Проверка JSON/source ID не удостоверяет истинность supplied facts и полноту Abilities. Нельзя удалять применимую способность ради допуска. can_leave_zone не означает автоматическое движение, потеря доступной цели означает технический unsupported_path, а не игровой исход.

## Установленный пакет и примеры

Повторно использован offline wheel четвёртого среза ADR-0034 в отдельном временном venv с runtime dependencies. Все **374 Python/Schema-файла** сверены с текущими исходниками; src с момента сборки не менялся. `pip check` успешен. Рабочий каталог вне repo, PYTHONPATH/PYTHONHOME удалены, проверено кодирование через ASCII text streams и UTF-8 bytes.

Обе mixed-команды проверены через **module/stdin и console/относительный файл × sequential/process**. Полный нормализованный request, Unicode, actor flags и aggregates сохранены; результаты равны после исключения echoed execution. Simulation fixture содержит 8 trials, balance — четыре состава и planned=16. Проверены шесть Schema/local refs, версии и malformed/wrong-family inputs, реальный generation failure (0,1), help/usage и missing-file I/O. Четыре прежние команды дают одинаковые результаты через обе точки входа и сохраняют свои error families. Ошибки исполнения и output pipes дополнительно покрыты перечисленными unit/integration tests.

Отдельная проверка установленного public service → encoder для обоих семейств подтверждает runtime metadata (`0.1.0`, CPython `3.14.5`, `random.Random`), mixed seed scheme, точный обратный разбор request, неизменность command/global RNG и отсутствие оставшихся child processes после sequential/process. Metadata описывает текущую среду кодирования, а не удостоверяет происхождение произвольного typed aggregate.

[Contract probe](../examples/m7/json_contract_probe.py) и [production balance example](../examples/m7/mixed_balance.py) выполнены установленным Python вне repo без tests/private builders. Probe проверяет 48 trials, 12 semantic rejections и generation failure; пример — 192 trials, по 96 на backend. Inputs/global RNG/children сохраняются. Saved fixtures не перезаписывались и не используются как Monte Carlo oracle нового прогона.

## Ограничения

- Только свежие здоровые Minions, фиксированные Melee/Close и Shooting/Medium роли, Athletics Protection, обычный порядок сторон и явные GM policies. Нет движения, смены оружия, reload actions, PC/Brute/Champion, магии, Aim/hidden или автоматической awareness в этом сценарии.
- Генерация меняет численность групп заданного резерва, сохраняя profiles/positions/policies. Она не ищет за пределами резерва. Весь неподходящий subset отклоняется, а observed unsupported исключает кандидата из продолжения и выбора. Пустой final selection допустим, nearest fallback отсутствует.
- Каждый stage заново оплачивает полный пакет. Повторные observations не объединяются как независимая выборка. Метрика — доля достижения заданной цели за лимит, окно задаёт caller; пресетов сложности нет.
- Aggregate-only wire не означает streaming: simulation создаёт trial records, generator — семейство, encoder — полный JSON. Бюджет работ не гарантирует wall time/RAM. Source equality структурная, не криптографическая; RNG/runtime metadata не заменяет provenance пользовательских aggregates.
- Проверено на Windows/Python 3.14.5; Python 3.12, другие ОС и новые performance-измерения не проверялись. Получатель должен сохранять точность больших JSON integers и отбрасывать неполный output при I/O failure.

## Проверки и продолжение

Набор ADR-0034 содержит **149 tests: 122 unit и 27 integration**. **378 targeted/regression tests OK (280,372 с)**, включая M4/M5/M6 JSON/services/CLI; точные команды и результаты записаны в [статусе проекта](../project-status.md#последняя-проверка). Compileall, AST layer boundaries, 2251 локальный Markdown-путь, UTF-8/whitespace и diff --check успешны. Последняя полная проверка реализации — 2664 tests OK; аудит не меняет src/tests.

План ADR-0034 исчерпан. Пользователь выбрал **магию в боевой симуляции**. Следующий шаг M8 — инвентаризация existing K1 магии, прямая сверка книг и ограниченный контракт подключения к симулятору. Сам аудит новых игровых возможностей не вводит.
