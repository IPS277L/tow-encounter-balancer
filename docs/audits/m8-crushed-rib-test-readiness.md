# K1 Crushed Rib next-Test: готовность ADR-0055

Дата: 2026-11-02. Статус: **ADR-0055 закрыт в принятой K1 границе.** [Контракт](../decisions/ADR-0055-source-bound-crushed-rib-test.md), [предыдущая граница54](m8-repeated-leg-spasm-transport-readiness.md).

## Реализация и граница

[Шесть frozen/slots моделей](../../src/towr/domain/crushed_rib_test_models.py) и [семь функций](../../src/towr/rules/crushed_rib_test_resolution.py) реализуют ordinary/Casting preparation, execution, completion и exact-injury apply. Domain не импортирует rules/RNG. Все шесть типов экспортированы из `towr.domain`; функции находятся в собственном rules module.

Preparation сохраняет full original injury/Test source, добавляет canonical Grim и вызывает existing Drained preparation. Она не расходует restriction и не бросает dice. Completion проверяет полный Test trace, pool/minimum/quality/modifiers/locks/rerolls/successes; Casting дополнительно parent/previous magic state/progress и exact Rule-of-Nine follow-ups по final dice. Проверка не выполняет Test повторно. Result снимает только pending NEXT_TEST effect, сохраняя Drained/UNTIL_TREATED, Wound records/flags/order/dice/origin и остальные данные injury.

Первый source — одна canonical resolved/untreated/unhealed rolled10, optional предыдущие Superficial Injuries1–3, только Drained и exact canonical effects в порядке actual lifecycle. Подменённые enums/bool-int aliases, списки вместо original tuples, missing/duplicate/foreign effects, другие injuries/Conditions, treatment/healing/Fate/Lucky/Talent proofs отклоняются до RNG/equality. Apply повторно проверяет original result/current injury и actor, отвергает stale/повторное применение. Преднамеренный restore старого immutable source и actor↔injury mapping вне authoritative owner этим K1 API не решаются.

Нормативная база прежняя: BOOK-PLAYER-GUIDE1.4, гл.V Rules107–108/Attack Tests118/Drained123, гл.VIII Casting156–157, приложение Wounds Table190; BOOK-GM-GUIDE1.1, гл.VII Champions92. Новых страниц/полного чтения, Rule IDs или house rules при реализации не добавлено. Адресная сверка по локальным извлечениям проведена при подготовке55.

M8 full owner/journal и normal-Test validators не изменялись. Consumed injury не подставляется в roster ради обхода guards; Wound10 сохраняет ACTOR_INJURY stop. Runner/policy/generation/JSON1–4 и coexistence9/6/Wind не расширены. Будущий full-owner bridge требует отдельного контракта.

## Проверки

- [10 основных unit tests](../../tests/unit/test_k1_crushed_rib_test_resolution.py): actual rolled10 с0–3prior superficial Wounds, Drained suppression, penalties/fixed successes/locks/minimum die, failed/zero-success/already-Grim, Cast9/progress/pool, pure completion и один existing executor на ветку, exception без partial completion, stale/replay/frozen/pickle. Агентский запуск10/10,0,031с.
- [20 независимых adversarial tests](../../tests/unit/test_k1_crushed_rib_test_refusals.py): original nested admission, source/effect/trace aliases, first/last records/modifiers, detached Drained receipts, ordinary/Casting full witness, post-state и exact apply. Они обнаружили приём reversed effect order; source guard сужен до actual canonical Drained→NEXT_TEST. Два вспомогательных fixture naming collisions исправлены без ослабления source assertions.
- Root targeted run:20adversarial + [actual copied example](../../tests/integration/test_k1_crushed_rib_example.py) + [historical contract copied proof](../../tests/integration/test_m8_crushed_rib_test_contract_probe.py) — **22tests OK/2,234с**; log `.cache/adr0055-targeted-integration.log`. Финальный source был заморожен после этой проверки, до build/full regression.

[Actual consumer33d10](../examples/m8/crushed_rib_test.py) / [stdout](../examples/m8/crushed_rib_test.output.txt) выполняет настоящий K1 consumer от actual M8 Wound10. Ordinary Grim5d10, Casting Grim4d10 с original9 lock и reroll-to9, progress1→3 и pool3→5/Miscast pending, failed/zero-success/already-Grim, Drained suppression и minimum-die rule проверены. Consumption выполняется до post-Test pool follow-up, Wound/Drained сохраняются. Later ordinary Test только подготовлен, без приписанного ему броска. Defence — явно выбранная K1 Test, не выполненный M8 Protection. Ручной oracle не заменяет actual consumer.

[Contract probe40d10](../examples/m8/crushed_rib_test_contract_probe.py) сохранён как отдельная историческая evidence: его manual injury-only views не выдаются за production apply. Source/global RNG, copied/source hashes и M8 stop в обоих примерах сохраняются.

## Fresh wheel и isolated installed audit

Build `.cache/adr0055-installed-audit`, log `.cache/adr0055-build.log`; рабочее `.venv` не менялось. Использованы локальный setuptools84.2.1 wheel из `.cache/adr0054-build-dependencies`, `PIP_NO_INDEX=1`/`PIP_FIND_LINKS`; runtime dependencies скопированы helper в fresh venv, wheel установлен offline, `pip check` прошёл.

Wheel SHA256: `7e94f1278e70ad8416b4f1410550827500e3b1b8039fb2656c019a83553f7cbc`.

[Installed helper](../../tools/audit_crushed_rib_test_install.py) выполнен fresh Python с `-I`; evidence `.cache/adr0055-installed-audit/checks/evidence.json`, log `.cache/adr0055-installed-checks.log`. Проверены476package py/json paths+SHA source/wheel/installed, module site paths, identity всех6public exports;42старые schemas/444local refs замкнуты offline. Четыре source/installed child commands из внешнего cwd исполнили public bundle4Python files, без tests/private imports. Actual33d10 и historical40d10 имеют отдельные stdout hashes; каждый совпал с source и saved stdout. Fixtures/скопированные файлы не изменились во время исполнения. PDF/references в wheel отсутствуют.

```powershell
$env:PIP_NO_INDEX = '1'
$env:PIP_FIND_LINKS = "$PWD/.cache/adr0054-build-dependencies"
& ./tools/prepare_m8_transport_audit.ps1 -Repository $PWD -AuditDirectory "$PWD/.cache/adr0055-installed-audit"
.cache/adr0055-installed-audit/installed/Scripts/python.exe -I tools/audit_crushed_rib_test_install.py --repository . --wheel .cache/adr0055-installed-audit/wheels/towr_encounter_balancer-0.1.0-py3-none-any.whl --work-dir .cache/adr0055-installed-audit/checks
```

Это команды завершённого запуска; для повторения нужны fresh AuditDirectory/`--work-dir` и доступный локальный build dependency. `.cache/adr0055-production-scope.json` подтверждает: добавлены только2consumer modules, из прежних package files изменён только `domain/__init__.py`, удалений нет. Все engine/simulation/application/adapters и89прежних tracked examples побайтно прежние.

## Регрессия и следующий шаг

Полный `.cache/adr0055-full-regression.log`: **4110tests/949,557с,33known errors/0failures/0skipped**, Windows11/CPython3.12.4. Все542integration tests прошли. `.cache/adr0055-regression-comparison.json` хранит counts/duration/logSHA и exact sorted33ERROR headers: они совпали с `.cache/adr0054-final-unit-regression.log`. Это один полный прогон актуального source, без объединения прежних успешных частей; старый4078baseline не выдаётся за новый результат.

Known32subcase errors относятся к frozen/slotted `.state` assignment expectations K1 registered Aim-loss, ещё1 — к M5 `replace(init=False simulation_requests)` TypeError/ValueError expectation. Они не исправлялись в этой вехе; весь набор не объявляется зелёным. Новых errors/failures нет.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

После полного прогона476package paths+SHA вновь совпали с installed evidence; все93public example py/json/txt hashes неизменны (89прежних tracked +4новых actual/historical files). Production с момента build не менялся. После синхронизации документов проверены1704local Markdown paths/15documents:broken paths0 (anchors не проверялись). `git diff --check` и whitespace13untracked text files чистые.27незакоммиченных файлов включают17предшествующих; commit/push, `.gitignore` и книги не менялись.

Следующий шаг — подготовить отдельный ADR-0056 M8 full-owner contract: Protection-before-Casting, pre/post-Test injury projections, existing normal-Test validators, pending follow-ups, remaining Drained и provenance consumed receipt. До этого automatic M8 stop для10 сохраняется. Удаление effect из roster для обхода admission не является такой интеграцией; runner/policy/wire не расширяются автоматически.
