# M8: native opt-in generation, ADR-0047 этап 1

Дата: 2026-10-31. [Контракт](../decisions/ADR-0047-opt-in-generation-and-magic-json-v2.md). Реализован только native generation с полной family policy; JSON v2 ещё не реализован, v1 остаётся закрытым для opt-in. Боевые правила/runner не менялись, новых Rule IDs/house rules нет. Источники и границы существующего consumer — ADR-0046; книги в этом техническом срезе заново не извлекались.

## Реализация

- [Request](../../src/towr/application/magic_candidate_generation_models.py): последнее поле `miscast_continuation=None`, existing typed policy либо None, полное равенство template до проверки коллекций/перебора. Opted template без отдельного family assertion отклоняется; equal immutable copy принимается. Старые positional calls сохраняются.
- [Projection](../../src/towr/application/magic_candidate_generation.py): полная family policy передаётся каждому новому scenario. Existing result validator реконструирует expected candidates той же функцией и проверяет полный source. No skip/repair/partial и error/cause boundaries прежние.
- Нижние слои, seed schemes, ID/count order, budgets и v1 schemas/adapters не менялись. Staged/simulation уже сохраняют полный scenario; дополнительной передачи отдельных policy fragments не требуется.

Удалённые резервисты отсутствуют из мира отдельного сценария, не являются external Short creatures. Policy/facts — explicit caller assertions, не доказанные программой обстоятельства. Любая unsupported ветвь остаётся в общем знаменателе trials.

## Матрица evidence

| Проверка | Результат |
| --- | --- |
| [14 новых unit tests](../../tests/unit/test_m8_opted_magic_generation.py) | Early typed/equality guards, unreadable collections, append-last/None/positional/output/seed parity; independent equal policy copy; все четыре vectors и четыре сочетания Wizard side/perspective; frozen/replace/pickle/full source; equal-frame collapse, early/late conflict, invalid Broken plan, cause/notes и no RNG/pool |
| [4 integration tests](../../tests/integration/test_m8_opted_magic_generation.py) | Реальные Wind effects на retained live actors всех четырёх составов, omitted IDs отсутствуют; legacy source equality и прежний 3-d10 stop; реальный default-RNG sequential/spawn без фиксации Monte Carlo rates |
| Scripted staged Wind | Полные одинаковые sequential/process reports; child-PID assertion; пакеты2,2,2,2,4,4 оплачивают16/16 trials, prefixes seeds и full policy/source сохраняются |
| Scripted mixed outcomes | На каждого из четырёх кандидатов два round-limit и один other-row unsupported: denominator3, unsupported1/3, window_match=None. No eligible, actual12/planned24, stage2 не запускается |
| [Дополнительный v1 unit test](../../tests/unit/test_m8_magic_balance_json.py) | Admitted opted family с полным synthetic aggregate chain не кодируется v1; family поле запрещено даже null. Это проверка source/codec, не simulation observation |
| [Обновлённый public probe](../examples/m8/opt_in_transport_contract_probe.py) | Настоящий native opted generator совпадает с manual projection и legacy+policy для четырёх vectors и opposite perspective; v2 portion остаётся ручным mapping |

Input/global RNG/child cleanup проверены. Generation не исполняет правила; only RNG injection использован для scripted backend evidence. На source-substitution/конечном result guard нет ID-only equality. Independent read-only review production, unit/v1 и integration tests блокеров не выявило.

## Команды и результаты

Windows x64 / CPython3.12.4:

```powershell
$env:PYTHONPATH = "src;tests"
.venv/Scripts/python.exe -m unittest unit.test_m8_opted_magic_generation -v
.venv/Scripts/python.exe -m unittest integration.test_m8_opted_magic_generation -v
.venv/Scripts/python.exe -m unittest unit.test_m8_magic_candidate_generation_models unit.test_m8_magic_candidate_generation unit.test_m8_miscast_continuation_policy unit.test_m8_magic_balance_json unit.test_m8_magic_json -q
.venv/Scripts/python.exe -m unittest integration.test_m8_opt_in_transport_contract_probe integration.test_m8_opted_miscast_example -q
```

Соответственно: **14 OK (0,135 с); 4 OK (17,906 с); 101 OK (16,526 с); 2 OK (2,773 с)**. Всего 121 проверка, из них 19 новых тестов. Spawn/TemporaryDirectory потребовали запуск вне sandbox; первоначальный отказ Windows Pipe не является игровым outcome. Public examples проверены как copied bundles вне исходного cwd/stdout parity, не как installed wheel.

Полная регрессия: **3748 tests / 33 известных errors / 0 failures / 0 skipped (613,814 с)**:

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Log: `.cache/adr0047-generation-regression.log`. Все 33 ERROR headers отсортированы и сравнены с `.cache/adr0047-contract-regression.log`: различий нет. Это16+16 TypeError в двух K1 Aim loss модулях и один ValueError replace(init=False) в M5. FAIL headers/skipped отсутствуют; новых ошибок нет. Известные assertions остаются отдельной задачей, полный suite с ними не объявляется зелёным. Проверены 1147 локальных Markdown paths и `git diff --check`.

## Оставшаяся граница

JSON/CLI v1 не принимает policy, v2 ещё нет. Opted generator не добавляет другое spell/effect/тактику и не является saved-battle API. Installed source/wheel/schema аудит нового transport выполняется в этапе4 ADR-0047, прежний installed449files не доказывает новую сборку. Другие ОС/performance не проверялись.

Следующий шаг — этап2 ADR-0047 целиком: simulation v2 с тремя schemas, versioned command/errors, strict magic reader/mapper, lossless parser/summary/error encoders, service/CLI и tests v1/v2-null/opted/trusted-version. Balance v2 следует после него. Незакоммиченные исходные изменения сохранены; commit/push не выполнялись.
