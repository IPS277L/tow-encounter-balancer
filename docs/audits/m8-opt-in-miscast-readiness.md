# M8: аудит opt-in Miscast runner и Prone

Дата: 2026-10-31. ADR-0046 завершён в согласованной ограниченной границе с отдельно учтёнными известными ошибками тестовых ожиданий. [Контракт](../decisions/ADR-0046-opt-in-miscast-runner-and-prone.md): explicit decline/five facts, один table roll, actual Wind21–22 и scoped Prone transitions. Это не общий каталог Miscast, saved battle или универсальный engine.

## Контракт и источники

Нормативная основа прежняя: BOOK-PLAYER-GUIDE1.4, гл.V Rules / Range114, Free Actions116, Recover118, Attack Modifiers119, Dropping Prone120, Conditions/Broken122, Prone123; гл.VIII Casting/Interrupted Casting156, Miscasts157–159; BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Minions91, Champions92. Этот этап проверяет integration/propagation/packaging, не заявляет нового полного чтения книг. Новых house rules/Rule IDs нет.

## Evidence по границам

| Граница | Проверка |
| --- | --- |
| Explicit opt-in / None | Required typed policy/five facts/stand choice, fresh-only admission; None сохраняет прежние traces/IDs/draws/stops. [Admission](../../tests/unit/test_m8_miscast_continuation_policy.py), [runtime controls](../../tests/unit/test_m8_opted_miscast_runner.py). |
| Journal / mandatory sequence | Полный origin witness, в том числе разные Recover traces с равным post-state; exact predecessor/tail, death guard, canonical IDs/namespace collisions. [Этап 3](m8-opt-in-runner-integration.md), [journal tests](../../tests/unit/test_m8_miscast_journal.py). |
| Wind / другие rows | Preparation→one-roll→actual effect прежде Pool0; другие строки сохраняют rolled prefix/Pool/MISCAST_EFFECT. Missing future frame/budget не прерывают mandatory фазу. Exceptions не превращаются в outcome/retry. |
| Prone | Self-stand по exact current frame, одна free move, no Close/unsafe Broken; stand/end не считаются actions. Shooting−1d/effective departure=False, обычные собственные Tests, separate Wound whitelist/expiry; alternative Recover без standard benefits. [Source policy](../../tests/unit/test_m8_prone_journal_policy.py). |
| Trial/sequential/process | Actual Wind journal даёт 3 actions, не количество фаз; реальные spawn workers, полные records/source/seed и summaries равны sequential. Default Random(seed) проверяет parity, не заданные вероятности. [7 propagation tests](../../tests/integration/test_m8_opted_miscast_propagation.py). |
| Assessment / candidates | Полный opted scenario сохраняется через records/summary/assessment/report. Scripted objective/round-limit/unsupported остаются в общем знаменателе; unsupported исключает eligibility, не trial. Same-ID/seed legacy substitution отклоняется. |
| Ошибки | Table RNG failure распространяется через sequential/process; evaluator сохраняет candidate/cause без fallback. Child processes закрываются; input/global RNG неизменны. |
| Generation / wire | Native opted generation family отвергается до enumeration; JSON/CLI v1 lossless-reject policy, schema не принимает неизвестное поле даже null. [Simulation JSON](../../tests/unit/test_m8_magic_json.py), [balance JSON](../../tests/unit/test_m8_magic_balance_json.py). |

Independent read-only review не выявил блокирующих пробелов. Найденный на этапе 3 missing-departure journal gap закрыт regression; old hand-built fixture явно записывает использовавшийся can_leave=True. На этапе 4 production не менялся.

## Самостоятельный пример

[opted_miscast.py](../examples/m8/opted_miscast.py) + [magic_scenario.py](../examples/m8/magic_scenario.py) — двухфайловый bundle, только stdlib/public towr imports. [Вывод](../examples/m8/opted_miscast.output.txt), [external-cwd test](../../tests/integration/test_m8_opted_miscast_example.py).

Четыре настоящих fresh-runner случая / 50 scripted d10: None legacy до preparation; other-row с Pool3; Wind в последнем budget round→Prone end→две self-stand/Shooting; следующий round→Wizard self-stand/Casting→objective. Проверяются source/witness, owner references, counters/global RNG. Это конечное доказательство путей, не вероятности или сложность.

Authored Recover/Run harness — отдельное evidence этапа 3: подставляет только initial runtime property с настоящим зарезервированным ходом, не pending/result. Это не fresh reachability этих origins и не API сохранённого боя.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m8/opted_miscast.py
.venv/Scripts/python.exe -m unittest tests.integration.test_m8_opted_miscast_propagation -q
.venv/Scripts/python.exe -m unittest tests.integration.test_m8_opted_miscast_example -q
```

Propagation: 7 tests OK, 7,282 с; external-cwd example: 1 test OK, 1,070 с. Sandbox блокировал multiprocessing Pipe/TemporaryDirectory (WinError5); повтор вне sandbox прошёл. Это ошибки разрешений проверки, не игровые outcomes.

## Установленный пакет

Wheel собран из отдельной копии src/pyproject/README/LICENSE, без изменения рабочего src/build/lib или переустановки рабочего .venv. Изолированный build environment получил setuptools через pip. Новый venv установил wheel offline с --no-deps; runtime dependencies скопированы из проверочного .venv. `pip check` — exit0.

Все **449 Python/Schema files** source/wheel/installed совпали побайтно, наборы путей равны. PDF/reference sources в wheel не обнаружены. Пример прошёл из отдельного cwd под **python -I**, новые journal/runner imports находятся внутри isolated site. Stdout точно совпал с сохранённым, stderr пуст; PYTHONPATH не участвует.

Wheel SHA-256: `3f6b6ceae5521335e77390b2530d0785764f95b426b3d082100b266d4be19277`. Windows x64 / CPython3.12.4; jsonschema4.26.0, referencing0.37.0, jsonschema-specifications2025.9.1, attrs26.1.0, rpds-py2026.9.1, typing-extensions4.16.0. Это не cross-platform/performance benchmark.

Локальные артефакты: `.cache/adr0046-audit-c5af23d6873c4b0f956bb61185fa767e/` — wheel, installed venv, `verify-installed.ps1`, `full-regression.log`. Каталог игнорируется Git; для продолжения проекта переносить его не требуется. Первая sandbox-попытка ensurepip завершилась ошибкой; отдельный venv затем успешно создан вне sandbox.

## Полная регрессия

Полный запуск: **3728 tests / 33 errors / 1 failure / 0 skipped, 597,715 с**, вне sandbox. Все 33 errors относятся к известному baseline: 16 TypeError в K1 registered Aim loss prepared, 16 TypeError в ranged и один ValueError replace(init=False) в M5 evaluation. Проверены полные error headers; новых error-модулей нет.

Единственный failure — negative test `test_supported_broken_recover_keeps_receipt_and_requires_supplied_plan` в integration/test_m8_npc_magic_scenario_result.py. Он пересоздавал scenario из старого fixture и вместе с Broken plan терял обязательные departure facts прежней Attack; теперь изменяет только broken_plans в полном result.source. Production не менялся. После исправления весь integration result module, unit result module и Prone source-policy module: **43 tests OK, 0,137 с**. Остальные успешные тесты полного прогона повторно не запускались; полного rerun после этой локальной правки нет. Поэтому исходный full log сохраняет один уже исправленный failure, и зелёный полный suite не заявляется. Неустранённых новых регрессий по этим проверкам нет; известные 33 assertions остаются отдельной задачей.

Domain import boundary, local Markdown paths и `git diff --check` проверены. Предыдущие пользовательские изменения сохранены; commit/push не выполнялись.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m unittest tests.integration.test_m8_npc_magic_scenario_result tests.unit.test_m8_npc_magic_scenario_result tests.unit.test_m8_prone_journal_policy -q
git diff --check
```

## Следующая граница

Рекомендуемый следующий контракт — lossless передача явной opt-in policy через native generation и versioned JSON/CLI. Explicit native candidates уже поддержаны, но генерация/внешний формат намеренно отвергают policy. Сначала зафиксировать None compatibility, projection каждого subset, required facts и schema version, затем finite round-trip proof. Не менять v1 молча и не добавлять другие Miscast effects в этот scope.
