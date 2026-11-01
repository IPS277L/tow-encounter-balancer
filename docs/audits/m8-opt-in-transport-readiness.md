# M8: итоговый аудит opt-in generation и Magic JSON v2

Дата: 2026-10-31. **Этап 4 и ADR-0047 завершены в согласованной границе.** [Контракт](../decisions/ADR-0047-opt-in-generation-and-magic-json-v2.md): существующая policy ADR-0046 проходит через генерацию и оба magic JSON-семейства. Игровые consumers, версии книг PG1.4/GM1.1, seed schemes и fresh-only scope не меняются. Новых Rule IDs, house rules или нового полного чтения книг нет.

## Field/guard matrix

| Граница | Evidence |
| --- | --- |
| Explicit native family assertion | Append-last nullable policy, early full equality с template, полная policy каждого subset и source reconstruction. [Аудит generation](m8-opt-in-generation-readiness.md), [unit](../../tests/unit/test_m8_opted_magic_generation.py), [integration](../../tests/integration/test_m8_opted_magic_generation.py). Удалённые резервисты отсутствуют в subset; они не становятся external Short targets. |
| Required nullable wire policy | Simulation scenario и отдельно balance reserve/family; closed object из трёх полей, пять strict-True facts. Missing не означает null. [Simulation unit](../../tests/unit/test_m8_magic_json_v2.py), [balance unit](../../tests/unit/test_m8_magic_balance_json_v2.py). |
| Independent reserve/family | Два разбора и exact equality до projection; pointer `/generation/miscast_continuation`. Отдельный installed negative case. |
| Lossless chain | Full command reconstruction/version/order; generation → staged → report sources. Same-ID policy substitution отвергается в обе стороны. Не используется temporary legacy view. [Этап 2](m8-simulation-v2-readiness.md), [этап 3](m8-balance-v2-readiness.md). |
| Version/error trust | Strict lexical decode прежде ID/version; fallback1/null ID при незавершённом decode, trusted2 для shape/semantic error. Service берёт собственную command version, сохраняет phase/candidate/counts/stage и скрывает cause/notes. Exhaustive source tests этапов 2–3; installed shape1/2, malformed2 и mismatch2. |
| V1 / null compatibility | V1 schemas/URN прежние, policy запрещена даже null; native opted source нельзя losslessly вывести в1. V2null сохраняет native aggregates, но wire остаётся2. Проверены обе magic families и оба backend. |
| Packaging / registry | Exact source/wheel/installed parity всех455 `.py/.json`; все30 bundled schemas и324 `$ref` разрешаются локально. Все12 magic schemas реально валидируют request/result/error для family/version, не только загружаются. |
| CLI | Полные stdout bytes source/module/console совпадают. Две magic routes: v1/v2-null/v2-opted × sequential/process. Шесть прежних routes: public sequential success и explicit v2 rejection. STDIN/module и UTF-8 файл/console, один result/error без лишнего stdout. |
| Public examples | Сохранённые v2 результаты получены реальным CLI. Четырёхфайловый transport probe и двухфайловый opted runner пример выполняются из копии под installed `python -I`; stdout сравнивается с сохранённым. |

**Installed audit завершён exit0: 95 child commands, 12 magic backend cases, 2 copied examples.** [Simulation result](../examples/m8/json/magic-simulation-v2.result.json) и [balance result](../examples/m8/json/magic-balance-v2.result.json) сохранены из реального sequential CLI, полные результаты равны source и installed module/console. Это наблюдения фиксированных входов/seed/runtime, не вероятности или presets; `runtime` сообщает CPython3.12.4.

Independent read-only review контракта/реализации и двух audit helpers блокеров не выявил. Устаревшие указания про manual legacy view в ADR явно переведены в историческое описание первоначального proof.

## Воспроизводимая проверка установки

[Windows preparation helper](../../tools/prepare_m8_transport_audit.ps1) создаёт новую копию `src`, `pyproject.toml`, README и LICENSE, строит wheel и создаёт отдельный venv. Рабочие `.venv` и source/build не переустанавливаются. Build isolation может получать setuptools; **offline относится к установке project wheel** с `--no-index --no-deps`. Runtime dependencies скопированы из рабочего venv вместе с metadata, а не независимо установлены из сети. `pip check` прошёл.

[Audit helper](../../tools/audit_m8_transport_install.py) запускается installed Python с `-I`, проверяет путь импорта внутри isolated site, точные наборы путей/SHA256 package `.py/.json` и отсутствие PDF/reference sources в wheel. Это не равенство wheel metadata, launcher binaries или файлов зависимостей. В конце исходники повторно сравниваются с начальным snapshot.

Для повторного запуска нужен **новый, несуществующий** audit directory. Пример из корня репозитория на Windows:

```powershell
tools/prepare_m8_transport_audit.ps1 -Repository (Get-Location).Path -AuditDirectory "$((Get-Location).Path)/.cache/adr0047-installed-repeat"
.cache/adr0047-installed-repeat/installed/Scripts/python.exe -I tools/audit_m8_transport_install.py --repository . --wheel .cache/adr0047-installed-repeat/wheels/towr_encounter_balancer-0.1.0-py3-none-any.whl --work-dir .cache/adr0047-installed-repeat/checks
```

У каждого child command timeout120с и захват stdout/stderr; неуспех прерывает аудит. Helpers не изменяют tracked fixtures. Новый прогон нужен после изменения проверяемого source или runtime, а не для повторения уже успешной проверки.

Фактический cwd проверки: `.cache/adr0047-installed-audit/checks`, внутри checkout, но вне корня запуска, `src`, `tests` и исходных examples. Installed module использует `-I`; console получает environment без `PYTHONPATH`/`PYTHONHOME`. Скопированные examples добавляют только собственную папку bundle. Source control отдельно получает `PYTHONPATH=src`; его полные JSON bytes сравниваются с installed outputs. Это не утверждение запуска вне всего checkout.

Wheel SHA-256: `ee95c1f74bebbe5a559ccdb4cd0dfa0029d48a458a955d78c9a854e5ebbd57ad`.

Среда: Windows x64 / CPython3.12.4; jsonschema4.26.0, referencing0.37.0, jsonschema-specifications2025.9.1, attrs26.1.0, rpds-py2026.9.1, typing-extensions4.16.0. Это finite correctness evidence, не performance или cross-platform guarantee. Локальные wheel/venv/evidence находятся в `.cache/adr0047-installed-audit/`; переносить их для продолжения работы не нужно.

## Полная регрессия и границы выводов

Последняя полная регрессия неизменных production/tests: **3796 tests /33 известных errors /0 failures /0 skipped,766,473с**, log `.cache/adr0047-balance-v2-regression.log`. Команда: `$env:PYTHONPATH="src"; .venv/Scripts/python.exe -m unittest discover -s tests -v`. Все33 error headers совпали с предыдущим baseline:16+16 K1 frozen/slotted TypeError и один M5 replace(init=False) ValueError. [Подробности этапа 3](m8-balance-v2-readiness.md).

На этапе 4 production и tests не менялись; проверены packaging, helpers, fixtures и документация. Полный unittest повторно не запускался: предыдущая успешная часть регрессии сохраняет силу, а новый риск установки проверяется отдельным installed audit. Suite с33 errors **не считается зелёным**; корректировка известных expectations остаётся отдельной задачей.

Финальная проверка:1212 локальных Markdown-путей в12 документах — OK (не проверка anchors), оба saved v2 result совпадают с generated outputs после нормализации CRLF/LF, `git diff --check` — OK. Заголовки33 известных errors повторно сопоставлены с baseline без расхождений. Изменены только docs/fixtures и два audit helpers; commit/push не выполнялись.

## Ограничения и следующий шаг

Fresh-only вход не является save/resume. Только Wind21–22 и scoped Prone; other Miscast rows, desperate cast/abandonment, ongoing Prone Wounds, unsafe Broken, Run после spent free move и неизвестные scene facts не достраиваются. Unsupported остаётся в denominator; eligibility/window match не доказывают полноту тактики. Facts и решения GM остаются explicit assertions пользователя.

Следующий шаг после этого аудита — актуализировать [инвентаризацию mandatory continuations](m8-continuation-inventory.md) с учётом ADR-0044–0047 и выбрать один следующий узкий consumer. Сначала сверка соответствующих книжных страниц, существующего K1/runner и новый контракт/finite proof; не расширять gameplay непосредственно в transport audit.
