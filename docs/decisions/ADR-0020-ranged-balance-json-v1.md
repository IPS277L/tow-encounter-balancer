# ADR-0020: JSON balance v1 и CLI balance

Статус: реализован, 2026-09-28: **три Schema, frozen command/result, strict parser, result/error encoders, application service и CLI balance**. Игровые правила и simulation v1 не меняются.

## Основание и граница

[Аудит M5](../audits/m5-readiness.md) закрывает генерацию из явного резерва и staged evaluation неподвижных numeric ranged Minions. Пользователь подтвердил метрику достижения заданной цели за общий лимит раундов и явное окно сложности. Переиспользуются [оценка](ADR-0017-ranged-candidate-assessment.md), [этапы](ADR-0018-staged-ranged-evaluation.md), [генератор](ADR-0019-ranged-composition-generation.md) и сценарное кодирование [M4](ADR-0016-ranged-simulation-json-v1.md).

Формат не вводит PC, ближний бой, движение, генерацию вне резерва, подбор характеристик, новые метрики, confidence policy или именованные presets. Caller по-прежнему явно задаёт факты и решения ведущего. Source labels не загружают профили из книги и не доказывают истинность фактов. Нормативная механика остаётся в существующих правилах и ADR; нового чтения или толкования книг для сериализации не требуется.

## Общие правила формата

Три отдельных Draft 2020-12 документа: `urn:towr:ranged-balance:{request|result|error}:1`, файлы `ranged-balance-{request|result|error}-v1.schema.json`. Они входят в package data вместе с прежними схемами. Registry разрешает только bundled ресурсы; загрузки из сети нет. `schema_version` — строка `"1"`; `ruleset` — `"towr-pg1.4-gmg1.1"`. Версия balance независима от simulation, хотя сейчас обе равны 1.

Строгие правила M4 сохраняются: UTF-8, один JSON object, запрет неизвестных/пропущенных полей на любом уровне и duplicate keys; integer tokens без float/exponent/bool coercion; запрет NaN/Infinity и lone surrogates. ID — непустая не-whitespace строка без обрезки; object key order несущественен, arrays упорядочены. Все поля ниже обязательны, кроме `workers`/`batch_size`, которые обязательны только для process и запрещены для sequential. Nullable поля результата/ошибки присутствуют явно.

`master_seed` — каноническая десятичная строка `0` либо `[1-9][0-9]*`, значение 0..2**64−1. Hex seed на входе не допускается. Остальные целые передаются JSON integer; клиенты должны сохранять точность и выше 2**53−1. Bounds JSON не обещают доступность CPU/памяти; общие quotas/timeout остаются вне локального v1.

Точная дробь кодируется объектом `{"numerator": 1, "denominator": 4}`. Числитель — int ≥0, знаменатель — int ≥1; иных полей нет. Input допускает несокращённую дробь, adapter строит `Fraction`; output, включая echoed request, всегда сокращён, ноль — 0/1. Fraction-поля не используют JSON float или строку. Window admission: `0 <= minimum <= target <= maximum <= 1`; точечное окно допустимо. Echo сохраняет значения и порядки, но не исходные пробелы, object key order или несокращённую запись дроби.

## Вход: npc_ranged_balance

[Полный пример](../examples/m5/json/balance-v1.request.json) соответствует существующему Python-примеру: пять составов, seed 42, этапы 8/32 trials с keep 3/2, верхний бюджет 136.

| Поле | Контракт |
| --- | --- |
| `schema_version`, `kind`, `ruleset` | `"1"`, `"npc_ranged_balance"`, фиксированная пара книг выше |
| `request_id` | ID внешнего balance-запроса; не участвует в seed scheme |
| `reserve` | `initial_request_id`, `round_budget`, `scenario` полного резерва |
| `generation` | `groups`, `facts`, `candidate_id_prefix`, `max_candidates` |
| `evaluation` | `master_seed`, `stages`, `max_total_trials`, `window` |
| `execution` | `{"mode":"sequential"}` либо `{"mode":"process","workers":2,"batch_size":4}` |

`reserve.initial_request_id` — отдельный ID исходного NpcRoundRequest, `round_budget` — int ≥1. `reserve.scenario` **ровно** объект `scenario` M4: definitions, actors с zone_id, battlefield, side_order, actor_order, perspective_side, objective_target_ids, facts, repeated_stagger_choice и actor_policies. Он представляет свежий полный резерв, проходит весь existing admission, а не произвольный сохранённый бой. Нет вложенного фиктивного simulation-запроса с trial count или отдельным execution.

`generation.groups` — непустой массив объектов с `group_id`, `actor_ids`, `minimum_count`, `maximum_count`. IDs и ranges отображаются в RangedCompositionGroup без defaults: actor_ids непусты/уникальны, `0 <= minimum_count <= maximum_count <= len(actor_ids)`. Группы имеют уникальные group IDs, разбивают всех и только противников perspective-side, без повторов; участники каждой группы имеют одно точное definition. Все участники perspective-side фиксированы. Порядок групп и actor_ids задаёт count vectors и префиксы резервов по ADR-0019.

`generation.facts` — отдельный обязательный объект той же формы, что `reserve.scenario.facts`. Он утверждает факты **для каждого генерируемого состава** и отображается в RangedCandidateGenerationRequest.facts; не копируется из резерва автоматически. Даже совпадающие значения требуют обоих объектов. Поддержанный scenario admission сохраняется. `candidate_id_prefix` — явный ID prefix, `max_candidates` — int ≥1.

`evaluation.stages` — непустой массив `{"trials_per_candidate":8,"keep":3}`: trials — int 1..2**64−1, строго возрастают; keep — int ≥1, допускается больше текущего числа кандидатов. Последний keep задаёт итоговый top_k; отдельного top_k нет. `max_total_trials` — int ≥1, `window` содержит ровно minimum/target/maximum в формате дроби выше.

До materialization/RNG проверяются C и верхний бюджет: C=произведение размеров диапазонов минус пустой состав, если он присутствует; `1 <= C <= max_candidates`. Для U₀=C, Uᵢ₊₁=min(Uᵢ,keepᵢ) требуется `sum(Uᵢ * trialsᵢ) <= max_total_trials`. Пакеты исполняются полностью заново с trial index 0; стоимость 5×8+3×32=136, а не стоимость добавочных trials. Early stop может уменьшить фактические затраты.

Execution переиспользует SimulationExecutionOptions M4: process workers 1..61, batch_size ≥1; sequential без этих полей. Backend выбирает caller, RNG на внешнем пути только random.Random. Candidate ID имеет вид `prefix:counts:0,1`, initial ID его сценария — `candidate_id + ":initial"`; численность в порядке groups. IDs scoped внешним request, не глобальный hash и не proof одинаковых правил. Stage ID — только нулевой `stage_index`, без дополнительной строки stage_id. Outer request_id и reserve.initial_request_id независимы; совпадать им не требуется и не запрещено.

## Переиспользование M4 и typed boundary

Новая request Schema ссылается на **неизменённую** M4 request Schema по `#/properties/scenario`, `#/properties/scenario/properties/facts`, `#/properties/execution` и `#/properties/simulation/properties/master_seed`. Balance задаёт собственные envelope/reserve/groups/stages/window. Старые $id, документы, принятые формы и ошибки simulate остаются прежними. Ссылки на фрагменты получают исходную базу M4 для её локальных `$ref`.

Общие внутренние функции strict reading и scenario mapping выделены из M4 adapter: scenario data + initial ID + round budget + path prefix → typed scenario/definition_order; обратное отображение — typed scenario + definition_order → data. Это внутренние helpers без JSON envelope, trial count, runner или RNG. Ошибки получают верные пути `/reserve/scenario/...`; повторный parse фиктивного simulation JSON и копирование двух реализаций правил не нужны. M4 regression tests обязаны подтвердить прежнее поведение, включая lossless guards. Schema не проверяет ссылки, sums, точную seed range из строки или источник результата — это обязанности reader/typed constructors/encoder.

Реализованные application dataclasses — frozen/slots с tuple normalization и повторной validation при replace:

| Модель / функция | Назначение |
| --- | --- |
| `RangedBalanceCommand(request_id, generation_request, execution, definition_order)` | Проверенные ID, RangedCandidateGenerationRequest, прежние options и порядок всех использованных definitions без повторов |
| `RangedBalanceResult(generation_result, evaluation_result)` | RangedCandidateGenerationResult + RangedStagedEvaluationResult; exact `evaluation_result.source_request == generation_result.evaluation_request` |
| `parse_ranged_balance_request(str \| bytes)` | Strict parse → command; только admission/C/budget, без materialization, RNG/pool/I/O |
| `encode_ranged_balance_result(command, result)` | Pure source-bound projection → JSON string + LF; не выполняет оценку |
| `execute_ranged_balance(command)` | Реализован: generate_ranged_candidates → evaluate_ranged_candidates_staged с command.execution → RangedBalanceResult |

Result encoder проверяет `result.generation_result.source_request == command.generation_request`, всю существующую generation/staged source chain и lossless command → wire → command. Невыразимые M4-порядки low-level snapshot не теряются молча. Command/result не содержат mutable source dict; command не удерживает материализованные candidates. Balance получает inputs/aggregates; JSON/application не проникают в domain/engine/simulation.

## Успешный выход: npc_ranged_balance_result

[Пример результата](../examples/m5/json/balance-v1.result.json) получен из реальных aggregate reports существующих APIs; он был сохранён при подготовке контракта; готовый encoder воспроизводит его из typed aggregate fixtures, а CLI проверен с тем же входом.

| Поле | Контракт |
| --- | --- |
| `schema_version`, `kind` | `"1"`, `"npc_ranged_balance_result"` |
| `request` | Полный проверенный вход с резервом, family facts, порядками, window и execution |
| `seed_scheme` | `"towr:npc-ranged-trial:v1"` |
| `runtime` | package_version, python_implementation, python_version, rng=`"random.Random"`, как в M4 |
| `candidate_count`, `planned_trials`, `total_trials` | C, верхний staged бюджет, фактически исполненные полные пакеты |
| `candidates` | Полный каталог `{"candidate_id":"example:counts:0,1","counts":[0,1]}` в порядке генерации, включая не дошедшие до конца составы |
| `stage_reports` | Непустая допустимая цепочка завершённых этапов в порядке stage_index |
| `status` | `"completed"` либо `"no_eligible_candidates"`, как в staged API |
| `selected_candidate_ids` | Итоговый ранжированный top_k последнего этапа либо пустой массив |

Полный echoed reserve + groups + count vectors восстанавливает источник каждого candidate по ADR-0019. Отдельные полные candidate scenarios, seed каждого trial, trial records и combat journals в wire output не добавляются. Counts выводятся из источника генерации, не разбираются из произвольной строки candidate_id и не принимаются независимо. Одинаковые профили/исходы не являются основанием дедупликации.

Каждый `stage_reports[]` содержит ровно:

- `stage_index` (int ≥0), `trials_per_candidate`, `keep`, `total_trials`;
- `candidates` — все оценки исполненного подмножества в исходном порядке;
- `selected_candidate_ids` — локальный ranked выбор внутри окна;
- `continuation_candidate_ids` — пригодные для **следующего** этапа в исходном порядке, включая outside-window; на последнем заданном этапе всегда `[]`, поскольку следующего этапа нет.

Каждая оценка содержит `candidate_id`, `summary`, `rates`, `status`, `window_match`. Summary: `trials`, четыре целых `outcome_counts` (objective_achieved, side_defeated, round_limit, unsupported_path), `total_attack_count`, `total_visited_round_count`, конечные JSON numbers `mean_attack_count`/`mean_visited_round_count`. Means — описательные float-проекции существующего API, суммы/trials сохраняют точные значения. Rates — четыре одноимённых поля outcome в формате сокращённых дробей; знаменатель исходной доли всегда **все trials**, не только завершившиеся достижением/поражением. `status` — eligible либо unsupported_observations; `window_match` — boolean либо null только при unsupported observations.

Источник assessment восстанавливается из request, candidate и stage trials. Суммы исходов, budget/attack/visited guards, rates, status, window, оба отбора и вся цепочка выводятся из typed result, а не доверенных счётчиков другого JSON. Промежуточный локальный selected не используется для continuation. Равные distances сохраняют input order, как в существующих API.

Если список пригодных исчерпан до последнего заданного этапа, status=no_eligible_candidates, последний continuation=[], final selected=[], actual budget учитывает только исполненное. Если выполнены все заданные этапы, status=completed даже при полностью unsupported последнем этапе или пустом final selection. Это полные результаты с exit 0. Ошибка generation/execution не является таким early stop и не выдаёт успешно завершённый префикс.

Runtime — описание текущего encoder/runtime, не hash кода и не доказательство происхождения custom RNG. Для внешнего пути caller обязан использовать штатный application service; низкоуровневые custom-RNG reports нельзя выдавать за него. Sequential/process сравниваются по каталогу, stage reports и производным итогам; echoed execution закономерно различается. Timestamp, timing и случайный report ID отсутствуют.

## Ошибки и CLI

Отдельный envelope `{"schema_version":"1","kind":"balance_error","request_id":null,"error":{...}}`. Error содержит обязательные `code`, `path`, `message`, `candidate_id`, `counts`, `stage_index`. Message — человекочитаемое описание без стабильной формулировки. Path — валидный JSON Pointer либо null. Request_id — проверенный внешний ID либо null при невозможности извлечения; reserve ID не подставляется вместо него.

| Code | Контекст error | Exit |
| --- | --- | --- |
| `invalid_json` | Неверный UTF-8/JSON, duplicate keys/nonfinite/surrogates; candidate/counts/stage=null | 2 |
| `unsupported_version` | Неизвестная строковая версия, path=/schema_version; candidate/counts/stage=null | 2 |
| `invalid_input` | Schema, lexical float, admission, groups/window/C/budget; известный path, candidate/counts/stage=null | 2 |
| `generation_failed` | Сбой materialization после preflight; candidate_id и counts при известном составе, иначе null; stage/path=null | 3 |
| `execution_failed` | Сбой staged evaluation; нулевой stage_index и candidate_id при известном контексте, иначе null; counts/path=null | 3 |

Недопустимый диапазон/бюджет — input failure до materialization; отказ при проекции отдельного уже допущенного состава — generation failure. Unsupported observation — игровой outcome в успешном отчёте, не execution failure. Во всех ошибках запрещены partial stage reports, summary, selected и trial records.

Реализованный pure input error `RangedBalanceInputError` хранит code/path/request_id. Service оборачивает прежние RangedCandidateGenerationError и RangedStagedEvaluationError в request-bound `RangedBalanceGenerationError` / `RangedBalanceExecutionError`; известный состав/этап/кандидат сохраняет, неизвестные поля оставляет null. Любой другой Exception внутри соответствующего generate/evaluate вызова получает ту же фазовую категорию без выдуманного контекста. Cause/notes сохраняются цепочкой `raise ... from error`; JSON содержит общее сообщение фазы, не traceback/cause. Неверный тип аргумента service и неизвестный error для encoder дают TypeError; KeyboardInterrupt/SystemExit не перехватываются. Неожиданные ошибки самого encoder не маскируются как ошибки исполнения.

`encode_ranged_balance_error` принимает только три известных typed boundary errors. CLI: `python -m towr balance INPUT` / установленный `towr balance INPUT`, INPUT — файл относительно cwd или `-` для stdin. Нет flags для переопределения seed/window/backend. Protected main сохраняет spawn. Команда добавляется рядом с simulate, не меняя её формата/кодирования/exit codes.

Stdout — один UTF-8 JSON с LF после полного execution+encoding; stderr — краткая диагностика typed failure. Code 0 — complete result или help; 2 — typed input failure либо usage (usage только stderr, без JSON); 3 — generation/execution failure; 4 — read/write/flush/diagnostic I/O failure. При read failure stdout пуст; I/O не получает wire error code. При write failure нет второй попытки выдать JSON, shutdown flush не должен менять exit 4 на 120. Доставка bytes в pipe не атомарна; ненулевой exit требует отбросить неполный результат. Retry/fallback, streaming, output-файл, timeouts и автоматический backend selection не вводятся.

## Матрица проверки и порядок реализации

| Слой | Обязательные проверки |
| --- | --- |
| Schema/package | Три balance схемы и локальные refs в M4; positive request/result/error examples; unknown/missing fields на всех уровнях; enum/range/nullable context; wheel без cwd/PYTHONPATH |
| Strict reader | UTF-8, duplicate nested keys, bool/float/exponent, uint64 decimal seed limits, lone surrogates, версии/ruleset/kind, дробь denominator=0, отрицательная/выше 1/переставленные bounds; сокращение Fraction |
| Admission | Reserve references/facts/orders, явные family facts, exact group partition/definitions, ranges; C=0/max_candidates и staged budget до generation/RNG/pool; прежние M4 ошибки/pointers |
| Immutable/source | Frozen command/result; сохранение definition/group/target order; разные внешние/reserve IDs; exact generation/staged source; потеря low-level порядка, чужие seed/window/состав/этап, пропущенные/повторные/reordered reports отвергаются |
| Pure output | Все four outcomes/rates; unsupported null, outside-window continuation, tie order, один этап, early stop и final all-unsupported; no records; нулевой последний continuation; отсутствие dispatch/RNG/I/O |
| Service | Explicit backend/options; standard RNG; cause/notes/context для сбоя второго состава и позднего этапа; unknown context null, no next calls/partial/retry/fallback; interrupts |
| CLI | Module/console, file/stdin/Unicode, real spawn, installed wheel вне repo; parity aggregate reports, exit 0/2/3/4, usage/help, closed stdout/stderr, read/write/flush failures без второго JSON |

Точные Monte Carlo counts сохранённого примера — иллюстрация данного runtime, не универсальный statistical test oracle. Детерминированные source/selection/error проверки строятся на явных typed fixtures; real sequential/process должны совпадать между собой без ожидания конкретной вероятности.

**Первый implementation-срез выполнен:** три packaged balance Schema с локальным reuse M4, frozen command/result и pure request parser/result encoder. Общие strict/scenario helpers выделены с M4 regression tests. Проверены request/result examples, точные дроби, preflight, source/lossless/chain guards и реальный typed API round-trip sequential/process. Service orchestration, typed generation/execution error envelope encoding и CLI реализованы отдельным срезом ниже; error Schema сохраняет прежнюю форму. Не менять низкоуровневые generation/evaluation APIs, правила или simulation v1.

## Проверка контрактного среза

2026-09-28: mapping probe подтвердил exact equality с existing typed example и реальное sequential/process равенство для пяти составов, 136 trials. Сохранённый JSON output реконструируется в допустимую typed source chain со всеми counts/rates/means и обоими видами отбора; четыре M4 schema fragments разрешаются локально. Полный набор повторно **1919 tests OK**, Python 3.14.5, 100,422 с; compileall/pip check/diff check и ссылки успешны. Production src/tests/pyproject.toml не менялись; балансировочные Schema/adapters/service/CLI и установленный пакет этим probe не проверены. Подробности происхождения examples — в [README](../examples/m5/json/README.md).

## Реализация Schema и pure adapters

- [ranged_balance_models.py](../../src/towr/application/ranged_balance_models.py): frozen RangedBalanceCommand/RangedBalanceResult, проверка typed input/options/definition_order и exact generation → staged source.
- [ranged_balance_json.py](../../src/towr/adapters/ranged_balance_json.py): parse_ranged_balance_request и encode_ranged_balance_result. Parser проверяет reserve/facts/groups/window/stages/C/budget без генерации; encoder проверяет exact source и lossless round-trip, кодирует каталог count vectors и все aggregate stage reports. Counts берутся из общего generator enumeration, не из строки ID. Tuple arrays нормализуются при JSON serialization, дроби сокращаются; финальный continuation пуст.
- [_ranged_json_common.py](../../src/towr/adapters/_ranged_json_common.py) и [_ranged_scenario_json.py](../../src/towr/adapters/_ranged_scenario_json.py) обслуживают M4 и balance. Общий RangedInputError имеет отдельные simulation/balance subclasses; M4 exception type/code/path сохранены, reserve pointers используют /reserve/scenario. Cross-field generation/budget ошибки могут указывать корень документа (пустой JSON Pointer), поскольку касаются нескольких разделов. Причина сохраняется через __cause__.
- [ranged_json_schema.py](../../src/towr/adapters/ranged_json_schema.py): новый validate_ranged_balance_document, только bundled Registry. Balance загружает три своих и три M4 документа; simulation validator не зависит от balance схем. Прежние M4 JSON Schema и pyproject.toml не менялись; wildcard package data уже включает новые файлы. Error Schema и error encoder реализованы; service/CLI описаны ниже.

22 [unit tests](../../tests/unit/test_m5_ranged_balance_json.py) проверяют strict input, все уровни unknown/missing keys, точные дроби, source/type/immutable/lossless guards, C/budget до materialization, отдельные facts, четыре outcomes, tie/continuation/early stop/final unsupported, no generation/RNG/runner/pool при parse/encode и воспроизведение сохранённого aggregate JSON через typed fixtures. 2 [integration tests](../../tests/integration/test_m5_ranged_balance_json.py) проходят реальный generation/staged sequential/spawn и lossless JSON round-trip; проверены разные definitions, независимые orders и полные decisions. Конкретная Monte Carlo-вероятность не ожидается.

execute_ranged_balance(command), request-bound generation/execution errors с cause/context, их encoder и CLI balance реализованы следующим срезом ниже. Нижние APIs/метрика/правила остаются прежними.

Проверка реализации: **1943 tests OK**, Python 3.14.5, 126,873 с; compileall/pip check/diff check и локальные ссылки успешны. Wheel установлен и проверен через Python -I вне repo: bundled schemas, все пять examples, real sequential/process round-trip и прежний CLI simulate. Существующие незакоммиченные документы контрактного шага сохранены. Правила/domain/engine/simulation/CLI и pyproject.toml не менялись; service/error encoder/CLI balance остаются следующим срезом.

## Application service, error encoder и CLI balance

[execute_ranged_balance](../../src/towr/application/ranged_balance_service.py) принимает только RangedBalanceCommand. До оценки проверяет type/exact source результата generate_ranged_candidates; затем передаёт готовый staged input и исходные command.execution в evaluate_ranged_candidates_staged. RangedBalanceResult проверяет exact связь generation/evaluation. Standard RNG/backend orchestration остаётся в прежних services. Completed/early-stop/empty selection/unsupported observations возвращаются как успешный typed result, без повторных попыток.

[RangedBalanceGenerationError/RangedBalanceExecutionError](../../src/towr/application/ranged_balance_errors.py) связывают сбой с внешним request_id. Из известных lower errors переносятся candidate/counts либо stage_index/candidate; неизвестный контекст остаётся null. Type/source failures результата относятся к фазе, вернувшей неверный результат. Original cause/notes доступны через цепочку __cause__; interrupts не оборачиваются. [encode_ranged_balance_error](../../src/towr/adapters/ranged_balance_json.py) кодирует только input/generation/execution errors, проверяет готовую Schema и не сериализует cause/traceback/partial reports. Непарные surrogates в сообщении ошибочного ввода экранируются, output остаётся UTF-8.

[CLI](../../src/towr/cli.py) добавляет `balance INPUT` рядом с simulate и разделяет их parse/execute/encode/error types при общем byte I/O. Файл/stdin, отдельный stderr и exit codes 0/2/3/4 соответствуют таблице выше. Complete encoding выполняется до stdout; неожиданная ошибка encoder (включая typed exception) выходит за catch исполнения. При write/flush failure не выдаётся второй JSON; прежняя обработка неисправных streams сохраняет exit 4 при shutdown. __main__ guard и console entry point переиспользуются без изменения pyproject.toml. [Команды и примеры](../examples/m5/json/README.md).

Добавлены 12 [service/error unit tests](../../tests/unit/test_m5_ranged_balance_service.py), 8 [CLI unit tests](../../tests/unit/test_m5_balance_cli.py), 2 [service integration tests](../../tests/integration/test_m5_ranged_balance_service.py) и 6 [CLI subprocess tests](../../tests/integration/test_m5_balance_cli.py). Проверяются оба backend options, source/type guards, известный/неизвестный контекст, cause/notes/interrupts, отсутствие retry/partial output, ошибки второго состава и trial позднего этапа, error examples, Unicode, file/stdin/help/usage, pool failure и broken pipes. Два прежних JSON integration tests теперь проходят через новый service с real sequential/spawn, без ожидания конкретных Monte Carlo counts.

[Конечный аудит внешней границы M5](../audits/m5-external-readiness.md) завершён: Schema/adapters/service/CLI сопоставлены с матрицей контракта и критериями roadmap. Следующий выбранный пользователем этап — контракт ограниченного ближнего боя Minions (M6). Новые правила, presets и механики из готовности CLI не выводятся.

Проверка внешнего запуска: **1971 tests OK**, Python 3.14.5, 158,354 с; compileall/pip check/diff check и локальные ссылки успешны. Установленный wheel проверен вне repo без PYTHONPATH: module/console × sequential/process дают равные полные reports для пяти составов/136 trials; работают file/stdin, balance input errors и прежний simulate. На старте рабочее дерево чистое; низкоуровневые APIs/правила/schemas/pyproject.toml не менялись.
