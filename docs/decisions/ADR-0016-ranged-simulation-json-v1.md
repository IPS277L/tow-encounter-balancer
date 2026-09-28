# ADR-0016: минимальный JSON-контракт ranged M3

Статус: контракт принят, 2026-09-28; JSON Schema, pure adapters, application service, error encoding и CLI simulate **реализованы**. [Конечный аудит M4](../audits/m4-readiness.md) завершён; следующий технический срез определён в [ADR-0017](ADR-0017-ranged-candidate-assessment.md).

## Основание и границы

[Аудит M3](../audits/m3-readiness.md) закрывает четыре критерия roadmap для существующего [NpcRangedScenario](ADR-0013-ranged-minion-scenario-input.md). Первый M4 должен позволять передать такой сценарий и получить прежние M3 наблюдения без Python-конструкторов. Формат ниже — техническое решение, не новое правило книги и не сериализация произвольных domain dataclass.

Определения NPC отделены от участников. Числовые профили задаются входом, `source_rule_id` остаётся ссылкой caller: он не загружает NPC из каталога и не доказывает соответствие книге. Пример использует только Warbow excerpt Brigand, непосредственно сверенный с BOOK-GM-GUIDE 1.1, Allies and Antagonists / Brigands & Footpads / Brigand, стр. 97: Shooting 3d/3, Dam 3, Medium–Long/2H, Athletics 3d/2, Resilience 3+1. Полный Brigand, его Axe и Special Ability этим форматом не заявлены.

## Общие правила v1

- JSON object в UTF-8. Все описанные поля обязательны; неизвестные поля на любом уровне и duplicate object keys отклоняются. Нет неявных defaults, coercion и загрузки Python objects по имени.
- `schema_version` — строка `"1"`; несовместимая версия отвергается до построения domain и запуска RNG/pool. `kind` выбирает фиксированный документ, расширяемого языка правил нет.
- ID/source ID — непустая строка, не состоящая только из whitespace; adapter не обрезает/не нормализует её. Enum значения совпадают с явно перечисленными ниже строками.
- Поля integer принимают JSON-числа без дробной части и экспоненты; bool/строки/`1.0`/`1e0` не превращаются в int. NaN/Infinity недопустимы. Schema задаёт структуру/диапазоны, strict JSON reader дополнительно сохраняет эту границу типов.
- Master seed записывается десятичной строкой `0` либо `[1-9][0-9]*` и проверяется в `[0, 2**64)`. Trial seed на выходе — ровно 64 lowercase hex символа без `0x`. Это исключает потерю точности seeds в JSON-клиентах. Остальные integer counters передаются точно; клиент не должен округлять их через binary64 при значениях выше 2**53−1.
- Порядок object keys несущественен; порядок всех массивов сохраняется. Неизвестные поля не игнорируются как предполагаемые игровые эффекты.

## Вход: npc_ranged_simulation

[Полный пример 1×1](../examples/m4/ranged-v1.request.json). Структура верхнего уровня:

| Поле | Значение / смысл |
| --- | --- |
| `schema_version` | `"1"` |
| `kind` | `"npc_ranged_simulation"` |
| `request_id` | ID запроса; становится ID исходного NpcRoundRequest |
| `ruleset` | `"towr-pg1.4-gmg1.1"`; другая пара книг не выбирается автоматически |
| `simulation` | `master_seed` (decimal string), `trials` (int 1..2**64−1), `round_budget` (int ≥1) |
| `execution` | Один из двух объектов ниже |
| `scenario` | Определения, участники, граф, порядок, facts и policies ниже |

`execution` имеет ровно одну форму:

```json
{"mode": "sequential"}
```

```json
{"mode": "process", "workers": 2, "batch_size": 32}
```

В process workers — int 1..61, batch_size — int ≥1. Предел 61 выбран для переносимого wire API с Windows; low-level process API сохраняет собственные платформенные ограничения. Sequential не принимает workers/batch_size. RNG в JSON не настраивается: application service использует новый `random.Random(seed)` для каждого trial; Python API продолжает поддерживать injection для тестов/явных callers. JSON никогда не задаёт import path, pickle payload или callable.

### Поля scenario

| Поле | Контракт |
| --- | --- |
| `definitions` | Непустой массив уникальных определений; каждое используется хотя бы одним actor |
| `actors` | Массив минимум двух участников с обеими CombatSide; уникальные actor IDs |
| `battlefield` | `zone_ids` (непустой массив уникальных IDs), `connections` (массив объектов с `first_zone_id`, `second_zone_id`) |
| `side_order` | Перестановка `players_and_allies`, `opposition`, ровно по одному |
| `actor_order` | Каждый actor ID ровно один раз; порядок предпочтения внутри side |
| `perspective_side` | `players_and_allies` либо `opposition` |
| `objective_target_ids` | Все и только actor IDs противоположной стороны, без повторов |
| `facts` | Все девять явных полей NpcRangedScenarioFacts, приведённые ниже |
| `repeated_stagger_choice` | Только `"suffer_wound"`, явно переданный допустимый выбор |
| `actor_policies` | Ровно одна policy на каждого actor |

Каждый definition содержит только:

```json
{
  "id": "brigand:ranged",
  "source_rule_id": "RULE-PROFILE-TALABEC-004",
  "resilience": {"toughness": 3, "bonus": 1},
  "attack": {
    "id": "warbow", "source_rule_id": "RULE-PROFILE-TALABEC-004:warbow",
    "dice": 3, "threshold": 3, "damage": 3
  },
  "protection": {
    "source_rule_id": "RULE-PROFILE-TALABEC-004:protection", "dice": 3, "threshold": 2
  }
}
```

Dice ≥1; threshold 1..10; damage/toughness/bonus ≥0, все integer. Kind v1 фиксирует injury policy MINION/wound_limit 1, Shooting Medium–Long/2H, success_multiplier 1, ignores_armour false, пустые effects; Protection Athletics, оба pool_cap None. Эти значения заданы контрактом ограниченного сценария, а не выводятся из имени `warbow`. Неподдержанные параметры нельзя передать и затем молча потерять.

Actor содержит только `id`, `definition_id`, `side`, `zone_id`. Он начинает здоровым: ProfileInjuryState(0, 1), Conditions пусты, defeated false, доступна единственная Attack, current_resilience равна definition, wields_weapon true, holds_shield false. Fresh initial state — семантика `kind`, не автоматическое лечение входного бойца: входа с Wounds/Conditions/history нет и такие поля отклоняются. Один definition могут использовать несколько actors с независимыми состояниями. Definition/actor/zone ID относятся к разным пространствам имён.

Граф ненаправленный, без self/duplicate edges и ссылок на неизвестные Zones. Каждый actor помещён ровно в одну известную Zone; допускаются незанятые Zones. Для каждой пары противников Zones должны быть соседними. География не вычисляет awareness/видимость/cover.

```json
{
  "target_range": "medium",
  "has_enemy_in_close_range": false,
  "targets_aware": true,
  "clear_line_of_sight": true,
  "stationary": true,
  "unmodified_tests": true,
  "no_additional_rules": true,
  "ammunition_sufficient": true,
  "requires_reload_action": false
}
```

Все значения facts обязательны именно в этих значениях. Adapter не дописывает согласие с ними за caller. Любое иное значение — отказ admission, не изменение симуляции.

Policy содержит `actor_id` и ordered `targets` — массив объектов `{target_id, disposition, gm_approved}`. Он перечисляет всех врагов ровно один раз; порядок задаёт приоритет целей. Disposition: `killed`, `knocked_out` или `disarmed_and_surrendered`; gm_approved — только явное true. Один массив разворачивается в target_actor_ids и соответствующие MinionDefeatDecision в одинаковом порядке; отдельного дублирующего списка target priority в JSON нет.

### Преобразование и семантические проверки

1. Strict reader проверяет JSON/версии/shape/types/unknown keys. Schema не подменяет проверку связей между ID и admission.
2. Definitions → NpcDefinition с единственными Attack/Protection; actors → NpcParticipantSnapshot в исходном порядке → NpcRoster.
3. Round 1 создаётся из roster.turn_participants и side_order, без active/completed/excluded turns; NpcRosterAttackState без histories. NpcRoundRequest использует request_id, actor_order, pending=(), weapons=().
4. ZoneGraph/placements без usage history + NpcRoundsRequest с общим round_budget; policy targets → typed decisions. Затем строятся NpcRangedScenario и NpcRangedSimulationRequest. Все существующие конструкторные guards сохраняются.
5. Отдельный frozen application command хранит typed request и typed execution options. Это не расширение domain и не новый battle aggregate. Parsing не исполняет Attack/RNG и не создаёт pool.

Повторяющиеся definition IDs, включая одинаковые копии, и неиспользуемые definitions отклоняются на adapter boundary. Неизвестные ссылки, friendly/missing/duplicate targets, неполный actor_order, иная цель, несмежные противники и неподдержанные facts отклоняются до исполнения. Истинность supplied facts/source labels за пределами структурных проверок остаётся обязанностью caller.

## Успешный выход: npc_ranged_simulation_result

[Пример результата](../examples/m4/ranged-v1.result.json) получен реальным sequential M3 из typed отображения примерного запроса, не вручную выбранными исходами. Production parser/encoder теперь воспроизводят этот пример в integration test; runtime metadata сравнивается с текущим интерпретатором.

| Поле | Значение / смысл |
| --- | --- |
| `schema_version`, `kind` | `"1"`, `"npc_ranged_simulation_result"` |
| `request` | Полный проверенный вход выше, включая scenario, seed и execution; arrays сохраняют порядок |
| `seed_scheme` | `"towr:npc-ranged-trial:v1"` |
| `runtime` | `package_version`, `python_implementation`, `python_version`, `rng` (`"random.Random"`) |
| `summary` | Поля ниже, только проекции полного NpcRangedSimulationResult |
| `trials` | Все compact records в возрастающем trial_index, без пропусков/дубликатов |

Summary содержит `outcome_counts` с четырьмя обязательными counters `objective_achieved`, `side_defeated`, `round_limit`, `unsupported_path`; `total_attack_count`, `total_visited_round_count` — integers; `mean_attack_count`, `mean_visited_round_count` — конечные JSON numbers. Counts суммируются в simulation.trials; sums/means вычисляются из records, не принимаются на доверии от другого caller. Суммы и знаменатель дают точные значения; means отражают float-проекции существующего API.

Каждая запись: `trial_index` (integer), `seed_hex` (64 hex), `outcome` (одна из четырёх строк выше), `executed_attack_count`, `visited_round_count` (integer). Семантика и budget guards — прежние M3. Unsupported path и round limit сохраняются отдельно; полей winner, victory rate, dead/survivors и invented difficulty score нет. Полный combat journal не сериализуется.

Encoder требует result.source_request == command.request; весь result и его records уже должны пройти existing checks. Подмена результата другого сценария/seed отвергается. Runtime metadata не является доказательством идентичности исходного кода: для replay нужны те же правила, реализация RNG и совместимый runtime; package_version сам по себе не гарантирует это. Timestamp, timing и случайный report ID в wire result не добавляются. Между sequential/process сравниваются summary/trials; echoed execution options закономерно различаются.

## Ошибки

Формат application/CLI boundary, отдельно от успешного результата:

```json
{
  "schema_version": "1",
  "kind": "simulation_error",
  "request_id": "example:brigands:1x1",
  "error": {
    "code": "invalid_input",
    "path": "/scenario/facts/targets_aware",
    "message": "targets_aware must be true"
  }
}
```

Request_id — проверенный ID либо null, если его нельзя извлечь. Error codes: `invalid_json`, `unsupported_version`, `invalid_input`, `execution_failed`. Path — JSON Pointer при известном поле, иначе null; message — понятная причина, не стабильный машинный enum. Partial summary/trials в ошибке запрещены. Pure parser поднимает typed input error; внешний error encoder формирует envelope из typed input/execution error. Ошибки исполнения и pool не классифицируются как неверное игровое правило или игровой outcome. Traceback остаётся диагностикой вызывающей среды, не полем result.

## Порядок реализации M4

**Первый срез выполнен:** три JSON Schema (request/result/error), frozen application command/options и pure JSON adapters: strict parse → typed request, typed result → output. Проверены positive examples, unknown/duplicate keys, uint64 seed boundaries, types/enums, source binding и cross-reference/facts/policy отказы до RNG/pool. Product application service, запуск из JSON и CLI в этот срез не входят.

Application service с выбором прежнего sequential/process API, стабильные errors и CLI simulate с protected main реализованы следующими срезами ниже; конечный аудит M4 завершён. Таймауты, service resource quotas и streaming больших результатов не выводятся из числовых границ схемы; автоматический подбор workers не вводится. Никакие лимиты JSON не заменяют книжные правила.

## Реализация первого среза

- [application/ranged_simulation_models.py](../../src/towr/application/ranged_simulation_models.py): frozen RangedSimulationCommand(request, execution, definition_order), SimulationExecutionOptions и typed enum. Порядок definitions хранится отдельно, поскольку он не обязан совпадать с порядком первого появления actors. Другие массивы уже сохранены в domain input. Команда не хранит изменяемый исходный dict.
- [adapters/ranged_simulation_json.py](../../src/towr/adapters/ranged_simulation_json.py): parse_ranged_simulation_request(str | UTF-8 bytes) и encode_ranged_simulation_result(command, result) → str. Никаких runner/RNG/pool вызовов. Encoder восстанавливает request из typed input, проверяет result.source_request и проверяет обратное отображение wire request в ту же command: low-level snapshots с невыразимым в v1 порядком (например, placements независимо от actors) отклоняются, а не теряются молча.
- [adapters/ranged_json_errors.py](../../src/towr/adapters/ranged_json_errors.py): RangedSimulationInputError с typed code, path и request_id. Некорректный JSON/duplicate keys дают invalid_json; float/exponent input tokens — invalid_input; неизвестная строковая версия — unsupported_version. Для field/schema/constructor ошибок path указывает известный узел, иногда весь scenario; при невозможности разобрать документ path/request_id могут быть null. Текст message не является стабильным API. Кодирование error envelope описано ниже.
- [Три схемы](../../src/towr/adapters/schemas/) входят в package data wheel. $id — `urn:towr:ranged-simulation:{request|result|error}:1`; result ссылается на request. Локальный Registry содержит все документы; remote retrieval отсутствует.

Выбран Draft 2020-12 и стандартная библиотека jsonschema `>=4.18,<5`, referencing `>=0.28.4,<1`; проверено с jsonschema 4.26.0/referencing 0.37.0. Использованы публичные [validation API](https://python-jsonschema.readthedocs.io/en/stable/validate/) и [Registry/Resource API](https://python-jsonschema.readthedocs.io/en/stable/referencing/). Собственного универсального schema evaluator нет. Зависимости только во внешнем adapter-слое; domain/engine/simulation не изменялись.

validate_ranged_document(document, kind) проверяет только Schema и поднимает jsonschema.ValidationError. Schema не различает математически целые 1 и 1.0, не доказывает references/GM policies/seed range из decimal string, не проверяет sums/means из records. Эти обязанности выполняют strict reader, domain constructors и typed encoder. Поэтому публичный вход — parse_ranged_simulation_request, а не один вызов Schema validator. Master seed spelling ограничена схемой, верхняя граница uint64 проверяется adapter. Reader также отвергает непарные Unicode surrogates в decoded keys/values, чтобы принятый текст можно было вернуть как UTF-8; правильные пары/Unicode IDs поддержаны. Output allow_nan=False сохраняет только конечные JSON numbers.

Runtime в encoder описывает текущую среду и фиксированный v1 RNG random.Random. Низкоуровневый M3 result не содержит доказательства RNG provenance; caller encoder обязан передавать результат стандартного v1 исполнения, а не выдавать injected custom RNG за него. Реализованный application service не открывает RNG factory через JSON.

14 unit + 2 integration tests: все object levels unknown/missing keys, nested duplicates, lexical types/UTF-8/versions, uint64 seeds, process options, facts/GM decisions/ссылки, frozen command, source binding/lossless projection; actual sequential/process с двумя definitions и переставленными orders. Полный набор **1813 tests OK** на Python 3.14.5. Wheel собран/установлен в .venv; isolated Python `-I` загрузил schemas и прочитал пример без PYTHONPATH. CLI/service не добавлены.

## Application service и кодирование ошибок

[execute_ranged_simulation(command)](../../src/towr/application/ranged_simulation_service.py) принимает только RangedSimulationCommand и возвращает прежний NpcRangedSimulationResult. SEQUENTIAL вызывает run_npc_ranged_simulation; PROCESS вызывает run_npc_ranged_simulation_parallel с точными workers/batch_size из command. Оба используют штатный random.Random; application boundary не принимает RNG factory. Внедряемый RNG остаётся в нижних APIs для тестов и других callers. Для process caller по-прежнему нужен importable main с guard; service сам не создаёт entry point.

Service проверяет тип результата и точное равенство result.source_request == command.request. Неверный тип/source и любой Exception из runner дают [RangedSimulationExecutionError](../../src/towr/application/ranged_simulation_errors.py) с request_id из scenario.initial.current.id и исходной ошибкой в __cause__, включая notes. Retry, fallback и partial result отсутствуют; все четыре игровых outcome передаются без переклассификации. Неверный тип аргумента service даёт TypeError до dispatch. KeyboardInterrupt/SystemExit не перехватываются. Штатный cleanup pool остаётся обязанностью прежнего process runner; ожидание уже запущенных детей не заменяется принудительным завершением.

Внешний encode_ranged_simulation_error(error) → str принимает только RangedSimulationInputError или RangedSimulationExecutionError. Для input сохраняются code/path/request_id/message; для execution — execution_failed, path=null и общее сообщение `Simulation execution failed`. Причина/traceback доступны Python caller, но в JSON не сериализуются. Неизвестные исключения дают TypeError, а не автоматически выбранную категорию. Envelope проверяется готовой error Schema, заканчивается LF; ensure_ascii=True сохраняет UTF-8 вывод даже при lone surrogate в диагностике malformed input. Ошибки parsing/admission возникают до service и не становятся execution_failed. Это чистое кодирование, без RNG/pool/I/O; application не импортирует adapters/JSON/CLI.

9 новых unit tests проверяют dispatch/options, все outcomes, source/type guards, причины/notes, no retry/fallback, interrupts, коды/pointers/Unicode и отказ неизвестных errors. Два прежних integration tests теперь проходят через service с настоящими sequential/spawn. Ещё 3 integration tests проверяют parsing/admission до dispatch, ошибку после completed trial и сбой создания pool; ошибок с partial summary/trials нет. Полный набор **1825 tests OK**, Python 3.14.5. CLI, автоматический backend selection, timeout/quotas/streaming остаются вне этого среза; правила и domain/engine/simulation не изменены.

## CLI simulate

[cli.main(argv)](../../src/towr/cli.py) — внешний adapter: `python -m towr simulate INPUT` либо установленная команда `towr simulate INPUT`. INPUT обязателен: путь к файлу или `-` для stdin. Относительный путь считается от cwd caller. Файл/stdin читаются как bytes и передаются прежнему strict UTF-8 parser. Далее вызываются application service и encoder; отдельные CLI flags для seed/backend/workers не вводятся. [__main__.py](../../src/towr/__main__.py) защищён `if __name__ == "__main__"`; console entry point объявлен в pyproject.toml. Оба запуска проверены с настоящим spawn, включая установленный wheel вне репозитория без PYTHONPATH.

Для simulation response stdout содержит ровно один JSON v1 документ в UTF-8 с завершающим LF; binary stream исключает зависимость от console code page/PYTHONIOENCODING. Typed input/execution error также выводится в stdout по готовой error Schema; stderr получает краткую строку с кодом и message. Причина исполнения и traceback не печатаются для ожидаемого typed failure. `--help` выводит текст справки в stdout; usage error — текст в stderr, без JSON.

| Exit code | Значение | Stdout |
| --- | --- | --- |
| 0 | Полное исполнение либо help | result JSON либо справка |
| 2 | invalid_json / unsupported_version / invalid_input | error JSON |
| 2 | Неверные аргументы CLI | Пусто |
| 3 | execution_failed | error JSON |
| 4 | Ошибка чтения, записи или диагностики | При ошибке чтения пусто; при ошибке записи доставка не гарантируется |

Все четыре игровых outcomes, включая ROUND_LIMIT/UNSUPPORTED_PATH, являются успешным завершением команды с code 0. Ошибки чтения файла/stdin не классифицируются как invalid_json/execution_failed и не расширяют wire enum: только stderr и code 4. При write/flush failure CLI не пытается писать второй JSON; fd неисправного stdout/stderr перенаправляется в devnull, чтобы повторный flush при shutdown не заменил code 4 на 120. Если недоступен stderr, диагностику доставить нельзя; code 4 сохраняется. Неожиданные программные исключения и KeyboardInterrupt/SystemExit не маскируются typed errors; обычная диагностика Python остаётся доступна.

Исполнение и encoding заканчиваются до первой записи stdout: partial trial result при сбое симуляции отсутствует. Атомарная доставка в ОС/pipe не обещается — при I/O failure получатель может увидеть часть bytes, которую нужно отбросить по ненулевому exit code. Streaming, output-файл/атомарное переименование, timeout, service quotas и backend fallback не добавлены. Весь JSON/result пока хранится в памяти. Application/domain/engine/simulation не импортируют CLI и не менялись.

7 unit tests покрывают typed execution failure, read/write/flush/stderr errors, propagation unexpected encoder error и interrupts. 8 subprocess integration tests покрывают file/stdin, Unicode при ASCII text streams, реальный spawn, строгий ввод/admission, help/usage, missing/directory input, closed stdout/stderr pipes с сохранением code 4 и injected pool startup failure. [Примеры запуска](../examples/m4/README.md).
