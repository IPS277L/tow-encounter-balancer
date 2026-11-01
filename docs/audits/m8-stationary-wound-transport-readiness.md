# M8 / ADR-0051: общий source/wheel/installed аудит

Дата: 2026-11-01. **Пункт4 и весь [ADR-0051](../decisions/ADR-0051-stationary-wound-generation-and-magic-json-v3.md) закрыты в принятой границе.** [Native generation](m8-stationary-wound-generation-readiness.md), [simulation3](m8-simulation-v3-readiness.md) и [balance3](m8-balance-v3-readiness.md) вместе с source/wheel/installed/schema/CLI/spawn проверены. Gameplay/Rule IDs/house rules/версии PG1.4 и GM1.1 не менялись, нового чтения книг нет.

## Field/guard matrix

| Поле / переход | Что проверяет текущая граница |
| --- | --- |
| Template + generation family | Два независимых nullable permissions; strict types/facts и exact matching до enumeration. Caller подтверждает каждое семейство, удалённые reserve actors отсутствуют в его мире |
| Subset projection | Обе family policies явно передаются каждому Scene/Scenario; source/facts/frames/orders/IDs/seeds/budgets сохраняются. Candidate types/facts проверяются до equality с полной expected projection |
| Simulation command→runner→summary | Fresh source request/scenario/facts/permissions повторно проходят pure admission; None/opted или same-value raw enum/int1 не скрываются equality. Runtime error берёт собственные command version/ID |
| Balance generation→staged→report→row→summary | Проверяются все явные source edges и detached summary; original `compare=False` simulation_requests cache должен совпасть с derivation до rebuild. Ошибка не нормализует чужой source |
| JSON3 scenario/reserve/family | Обязательные nullable stationary enum string и полный Miscast object независимы. Balance требует отдельные reserve/family fields; mismatch до generation, точный family pointer |
| Версии и доверие |1/2/3 обеих magic families, default1; версии1/2 отвергают stationary field даже null. Полный decoded3 даёт errors3; неполный lexical decode — fallback1/null ID; unknown4 — fallback1/decoded допустимый ID |
| Error phases/CLI | Сохраняются candidate/counts либо stage/candidate и command metadata; cause/notes/partial reports не публикуются. Input/usage/execution/I/O различаются, encoder работает до stdout write |
| Другие routes |6ranged/melee/mixed commands сохраняют1 и отвергают2/3, не наследуют magic version support |
| Installed package | Только свежий wheel,465package `.py/.json` paths+SHA256; isolated `python -I`, отсутствие editable/source import. Все36schemas/383refs/18magic bundled local |

## Найденное и исправленное при аудите

Независимый read-only probe обнаружил оставшийся public generation-result gap: отдельный `candidate.scenario.facts.no_external_condition_sources=1` сравнивался равным True, при этом source request оставался валидным. Balance publication уже отклоняла такой payload, но `MagicCandidateGenerationResult` reconstruction мог принять его.

Исправлен общий `_validate_generation_policy_types` в [generation models](../../src/towr/application/magic_candidate_generation_models.py): собственные typed scenario facts проходят constructor до policy/equality проверки, включая candidate source. Это узкая revalidation существующей модели, без recursive validator/RNG и изменения допустимых игровых входов.

В [unit module](../../tests/unit/test_m8_stationary_wound_generation.py) добавлен1regression method:4policy combinations ×detached int1/wrongtypedNone facts, source/template остаются strictTrue, int-case сохраняет bad==good. Result отвергается TypeError до expected projection, вход не нормализуется, RNG неизменен. **20/20 module tests OK/0,355с**. Дополнительный installed `python -I` probe на actual public balance3 request также отверг detached int1 при неизменном source/cache и global RNG; evidence `.cache/adr0051-final-installed-audit/candidate-facts-guard.log`.

Первичная сборка `.cache/adr0051-installed-audit` сделана до этого исправления и **не используется как итоговая evidence**. Финальная сборка и full suite выполнены заново после production fix; прежний3986 baseline сам по себе не объявляется проверкой исправленного кода.

## Воспроизводимые команды

База `cfc694e M8 P21` плюс незакоммиченные изменения пункта3, сохранённые без commit/push. Working `.venv` не переустанавливается. [Build helper](../../tools/prepare_m8_transport_audit.ps1) копирует src/pyproject/README/LICENSE в новую папку, строит wheel, создаёт isolated venv, копирует runtime dependencies с metadata и устанавливает wheel offline `--no-index --no-deps`; pip check прошёл. Build isolation может использовать установленный pip cache/индекс для setuptools.

```powershell
& tools/prepare_m8_transport_audit.ps1 -Repository 'F:\git\tow-encounter-balancer' -AuditDirectory 'F:\git\tow-encounter-balancer\.cache\adr0051-final-installed-audit'

& .cache/adr0051-final-installed-audit/installed/Scripts/python.exe -I tools/audit_m8_transport_install.py --repository 'F:\git\tow-encounter-balancer' --wheel 'F:\git\tow-encounter-balancer\.cache\adr0051-final-installed-audit\wheels\towr_encounter_balancer-0.1.0-py3-none-any.whl' --work-dir 'F:\git\tow-encounter-balancer\.cache\adr0051-final-installed-audit\transport'

& .cache/adr0051-final-installed-audit/installed/Scripts/python.exe -I tools/audit_m8_leg_spasm_install.py --repository 'F:\git\tow-encounter-balancer' --wheel 'F:\git\tow-encounter-balancer\.cache\adr0051-final-installed-audit\wheels\towr_encounter_balancer-0.1.0-py3-none-any.whl' --work-dir 'F:\git\tow-encounter-balancer\.cache\adr0051-final-installed-audit\native' --example stationary_wound_runner
```

Для повторения использовать **новые** work/build directories: helpers не перезаписывают прежнюю evidence и repository fixtures. Исходные books/references не входят в wheel.

## Package и native evidence

Windows11 x64 / CPython3.12.4. Финальный wheel: `towr_encounter_balancer-0.1.0-py3-none-any.whl`, SHA256 `9ba0b5433efcb3f99bd8e5a098236a5cfaf358231781023b8231aa6edd388b35`. Source/wheel/installed package `.py/.json` имеют одинаковые465paths и hashes.36schemas/383local `$ref`/18magic проверены; никаких сетевых resolver.

[Native helper](../../tools/audit_m8_leg_spasm_install.py) с `--example stationary_wound_runner` прошёл: source/installed stdout совпали, два helper child commands, двухфайловый скопированный bundle `stationary_wound_runner.py` + `magic_scenario.py`. Его main выполняет220scripted d10: four policy combinations, actual9→stand→Casting/end→incoming6→expiry и native sequential/spawn full records/source/summary/denominator parity. Evidence `.cache/adr0051-final-installed-audit/native/evidence.json` и stdout.

Это **installed native runner** actual9/6 и spawn, а не отдельный installed generated-9/6 spawn fixture. Actual generated3/4actor9/6 sequential/spawn проверен source integration этапа1/3; installed generation/family/codec выполняется публичным transport probe, package bytes совпадают. Разные свидетельства не подменяются друг другом.

## Transport evidence

[Расширенный helper](../../tools/audit_m8_transport_install.py) сохраняет прежние CLI flags и требует isolated installed Python. Плановая конечная матрица:28backend cases — обе families ×(v1, v2-null, v2-opted, четыре independent v3 combinations) ×sequential/process. Каждый input исполняется source module/installed module/installed console, stdin и copied UTF-8 file из отдельного cwd; точный текущий stdout должен совпасть. Также native phase-error encoders, actual balance3 generation failure/context, trusted/lexical errors и copied public examples.

Genuine public v1/v2 requests проверяются отдельно от synthetic v3 null-parity variants; saved result request/version связывается с правильным fixture ID. Saved artifact bytes сравниваются при одинаковом runtime; при другом runtime отдельно фиксируются hashes/metadata, это не объявляется exact stdout parity с другой Python. Repository example hashes до/после должны остаться прежними. V3 public request/result обоих families проверяются actual CLI и schema/source bindings.

Transport helper **завершился успешно**:269child commands,28backend cases,3copied examples в отдельных4/5-file bundles.6legacyroutes проверены на success/refuse2/refuse3; обе magic families — на1/2/3, four3-policy combinations и seq/process. Actual CLI generation failure3 сохранил candidate/counts(1,0);3native phase-error envelopes source/installed совпали и не содержат cause/notes. Все error schemas1/2/3 реально исполнялись.

Публичные v2 и v3 results обоих families совпали с сохранёнными **байт-в-байт на одинаковом runtime**. V1 snapshots используют Python3.12.15, текущий runtime3.12.4: их bytes/hashes не объявляются равными. Отдельное read-only сравнение показало равенство всех JSON fields обоих v1 results после удаления только runtime metadata; это finite observation, не cross-runtime Monte Carlo promise. Repository example hashes до/после неизменны, source/module/console текущий stdout всегда сравнивался точно.

Evidence `.cache/adr0051-final-installed-audit/transport/evidence.json` хранит465package hashes, hashes всех M8 public fixtures, wheel/interpreter/site/isolation и saved-result provenance. Dependencies: towr0.1.0, jsonschema4.26.0, referencing0.37.0, jsonschema-specifications2025.9.1, attrs26.1.0, rpds-py2026.9.1, typing-extensions4.16.0. Copied actual outputs и все matrix/error artifacts находятся в той же work directory. Helpers не меняли repository fixtures.

## Full regression и дальнейшая работа

После production fix запущен полный набор:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

**3987tests /33known errors /0failures /0skipped,906,227с**, вне sandbox; log `.cache/adr0051-final-audit-regression.log`. Все20generation regression tests, включая новый detached-facts case, прошли. Все33 отсортированных exact `ERROR:` headers совпали с `.cache/adr0051-balance-v3-regression.log`:32Aim frozen/slotted property expectations и1`dataclasses.replace(init=False)`, см. [открытые вопросы](../open-questions.md#проверки-dataclasses-на-python-312). Новых errors/failures нет. Полный suite с прежними33errors не считается зелёным.

После full suite повторно сравнены текущие465source package hashes и все public fixture hashes с installed audit manifest: изменений нет. Production/tests/helpers/probes после этой проверки не менялись. Локальные Markdown paths (без anchors) и `git diff --check` проверены. Повторение зелёных targeted/installed checks после doc-only closure не требуется.

[Continuation inventory](m8-continuation-inventory.md) технически обновлён по фактическим13labels/runner/diagnosis и закрытому transport. Следующий шаг — сравнить оставшиеся узкие candidates (включая Wound10/repeated9/Wind-Prone), выбрать один для ADR-0052 с finite proof и адресной книжной сверкой. Новое поведение не реализуется до отдельного source-bound контракта; policy не расширяется автоматически.

Незакоммиченные изменения пункта4: audit helper, narrow candidate-facts guard,1regression test и сопутствующие docs. Предыдущие изменения пункта3 сохранены. Commit/push выполняет пользователь.
