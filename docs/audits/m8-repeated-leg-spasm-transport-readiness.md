# M8: repeated Leg Spasm generation и Magic JSON/CLI v4

Дата: 2026-11-02. Статус: **ADR-0054 закрыт в принятой transport границе.** Контракт: [ADR-0054](../decisions/ADR-0054-repeated-leg-spasm-generation-and-magic-json-v4.md). Предыдущая граница: [native53](m8-native-repeated-leg-spasm-readiness.md).

## Реализованный контракт

`MagicCandidateGenerationRequest.repeated_leg_spasm_continuation` добавлен последним, defaultNone. Это отдельное matching family assertion, без наследования template. Все3 permissions и nested facts проверяются до collection materialization/enumeration/equality. Repeated требует base stationary, Miscast независим. Arithmetic Request не реконструирует Scenario через seed/trial helper; factory/result проверяют full original source. Result проверяет все candidate sources до первого count vector, projection явно передаёт family policy.

Обе magic command families поддерживают JSON1/2/3/4; default1. JSON4 содержит required nullable repeated enum в scenario, balance отдельно в reserve и generation. Все3 permission fields обязательны. Dependency и isolated matching errors имеют собственные semantic paths; при нескольких ошибках приоритет прежних полей сохранён. Mapper разделяет typed source admission и versioned lossless gate до definition/result catalog projection. Legacy1/2/3 запрещают новый key даже null и native nonNone encoding. У generation→staged→report→assessment→summary→encoder original sources и compare=False derived cache проверяются до equality/reconstruction.

Metadata4 сохраняется при null разрешениях и во всех runtime phase errors. Lexical failures дают fallback1/null ID; fully decoded unknown5 — fallback1 с decoded ID. Шесть nonmagic routes остаются только1. Privacy, exit codes, seed scheme, budgets и unsupported denominator прежние.

Это transport native53: domain/engine и игровые правила не менялись. PG1.4, гл.V Free Actions116/Giving Ground119/Conditions122–123, приложение Wounds190; GM1.1, гл.VII Champions92 — прежние источники. Новых страниц/полного чтения, Rule IDs/house rules нет. Третья9, несовместимые6/Wind при repeated stand, Wound10 и новые consumers не включены.

Byte comparison с финальным manifest53 (`.cache/adr0054-production-scope.json`):468→474files, добавлены только6v4schemas, изменены13adapter/application/CLI modules, удалений нет. Все domain/engine/rules/simulation bytes совпали с native53;36старых schema files также неизменны. Это отдельное подтверждение transport scope поверх installed parity.

## Детерминированные проверки

- [Generation unit](../../tests/unit/test_m8_repeated_leg_spasm_generation.py):11tests,6valid/2invalid combinations, все4vectors обеих perspectives, old positional forms, malformed/foreign source и first/last candidate до enumeration. Existing generation suites сохраняются.
- [Generated integration](../../tests/integration/test_m8_repeated_leg_spasm_generation.py):4tests, actual3/4actors; repeat48/66d10, post6 expiry51/69, third9 stop42/54, old controls24/30 либо7. Seq/spawn staged full reruns8trials, mixed denominator и budget4/8, реальный child PID, источники/seeds неизменны.
- [Wire unit](../../tests/unit/test_m8_magic_json_v4.py):5tests,12full policy roundtrips, strict fields/types/dependency/matching/error trust, legacy bytes и source lossless refusals, private phase causes. Старые v3 negative unsupported-version cases теперь используют5.
- [Schema tests](../../tests/unit/test_m8_magic_json_v6_schemas.py):9tests,6new schemas и offline closure42total/24magic. Initial fixture typo error code исправлен; production schema не менялась ради теста.
- [CLI integration](../../tests/integration/test_m8_magic_json_v4.py):4tests, public native/CLI result parity, own4 при чужой worker cause, actual late generation и late evaluation после полного первого stage без partial result. Initial late-failure fixture hardcoded call3 исправлен на candidate_count+1.
- [Production probe96d10](../examples/m8/repeated_leg_spasm_transport_contract_probe.py): independent finite inverse vs12actual parser4/request echoes,30actual projections, actual48journal+48summary/result4 и standard seeded balance4 source chain. Copied unittest прошёл1test/5,406с с exact stdout/empty stderr/6source+copy hashes. Sandbox TEMP/старый review timeout не объявляется успешным тестом; успешный outside-sandbox запуск выполнен отдельно.
- [Generated public runner1426d10](../examples/m8/repeated_leg_spasm_generation_runner.py): actual generated3/4actor repeat/post6/third9; sequential/realPID spawn staged и mixed denominator/budgets. Копируемый4file bundle не импортирует tests/private sources.

## Установка и воспроизводимость

Финальный fresh build: `.cache/adr0054-final-installed-audit`, log `.cache/adr0054-final-build.log`. Wheel SHA256: `0bfe41af0b25aa62f88a36c86d4c13a01b3f16b27a872589f47c621e0edcb63b`. Сборка/установка выполнены офлайн, `pip check` прошёл. Build dependency setuptools84.2.1 взята из существующего локального pip HTTP cache, wheel SHA256 `ca140b45d5325a9478f880e351484f62fef15f336462e449ca0c03c873d589c2`; рабочее `.venv` не менялось. Первоначальная `.cache/adr0054-installed-audit` остановлена при ожидании build dependency и не является итоговым evidence.

[Transport helper](../../tools/archive/README.md) проверяет source/wheel/installed package bytes, bundled refs, JSON4 matrix, legacy routes/versions, public same-runtime snapshots, module/console/stdin/file/process и copied bundles. [Native/generated helper](../../tools/audit_m8_repeated_leg_spasm_runner_install.py) сохраняет отдельный native330 proof и дополнительный generated1426 proof; импорт helper не подменяет actual execution.

Команды последних запусков из корня репозитория (для повторения нужны новые `--work-dir` и fresh AuditDirectory, helper не перезаписывает evidence):

```powershell
& ./tools/prepare_m8_transport_audit.ps1 -Repository $PWD -AuditDirectory "$PWD/.cache/adr0054-final-installed-audit"
.cache/adr0054-final-installed-audit/installed/Scripts/python.exe -I tools/audit_m8_transport_install.py --repository . --wheel .cache/adr0054-final-installed-audit/wheels/towr_encounter_balancer-0.1.0-py3-none-any.whl --work-dir .cache/adr0054-final-installed-audit/transport-checks
.cache/adr0054-final-installed-audit/installed/Scripts/python.exe -I tools/audit_m8_repeated_leg_spasm_runner_install.py --repository . --wheel .cache/adr0054-final-installed-audit/wheels/towr_encounter_balancer-0.1.0-py3-none-any.whl --work-dir .cache/adr0054-final-installed-audit/native-generated-checks
```

У финальной сборки перед первой командой были заданы `PIP_NO_INDEX=1` и `PIP_FIND_LINKS` на `.cache/adr0054-build-dependencies`; там лежал проверенный setuptools wheel из локального cache. На другом компьютере зависимости сборки нужно обеспечить отдельно. Runtime dependencies и `pip check` выполняет helper в новом venv; installed interpreter запускается с `-I`, source Python получает явный `PYTHONPATH=src`.

Native/generated установленный proof завершён: `.cache/adr0054-final-installed-audit/native-generated-checks/evidence.json`, log `.cache/adr0054-final-native-generated.log`;474package paths+SHA source/wheel/installed,4child commands,2public examples/4copied Python files, native330 и generated1426d10. Real child PID проверен, source/installed stdout совпали с saved evidence. Generated proof отдельно фиксирует330direct +840full stages +256mixed stages d10, actor counts3/4, actual/planned8/8 и4/8. Это actual installed execution, без imports tests/private sources.

Transport audit завершён успешно: `.cache/adr0054-final-installed-audit/transport-checks/evidence.json`, log `.cache/adr0054-final-transport.log`.486child commands,52backend cases,42schemas/444localrefs/24magic, exact474source/wheel/installed bytes. Six old routes отвергают2/3/4. Обе magic families исполняют1/2/3/4 через source/module/console, stdin/copied UTF-8 file и real process; full echo и seq/spawn result совпали.

Проверены legacy new-key null/selected refusals, dependency/matching paths4 и прежний приоритет base family error, lexical4 fallback, decoded unknown5/non-string/missing-version trust,2actual generation failure envelopes3/4,6native phase-error envelopes3/4 с own metadata/privacy. Evaluation exception envelopes не выдаются за actual gameplay fault: реальный late-stage отказ проверен отдельным CLI integration test.

Public v2/v3/v4 saved result SHA совпали с actual source/module/console bytes на CPython3.12.4. У v1 snapshots другой runtime: проверены schema/full request/version и зафиксированы оба хэша, exact bytes/aggregate equivalence между разными runtime здесь не заявляется. Четыре copied examples в трёх независимых bundles4/5/6files прошли; repository fixtures и production manifest не изменились во время аудита.

Первый неполный regression log `.cache/adr0054-full-regression.log` остановлен после нахождения устаревшего unsupported4 CLI ожидания. Все такие magic v1/v2/v3 negative cases перенесены на5; default1 и closed legacy shapes не ослаблены. Existing v2 unit36tests/25,259с и schema17tests/10,184с, соответствующие CLI3tests/31,231с прошли. Production/wheel после этого не менялись.

## Финальная регрессия

Полный `.cache/adr0054-final-regression.log`:4078tests/1010,552с,33known errors и1failure старого `test_m8_opted_magic_generation` positional metadata assertion. Он ожидал2последних fields вместо3; исправлены только ожидаемый suffix и required positional slice. Все540integration tests полного прогона прошли. Затем выполнен **весь unit-набор**, `.cache/adr0054-final-unit-regression.log`:3538tests/106,399с,33known errors,0failures/0skipped; исправленный positional test прошёл. Production, integration tests и fixtures между этими проверками не менялись.

Таким образом, актуальное покрытие4078tests подтверждено540успешными integration и3538повторно проверенными unit, без новых ошибок/failures. Это составной итог; единый полный прогон с нулём failures после fixture fix не заявляется. Успешные integration не повторялись после изменения только unit-ожидания.

`.cache/adr0054-regression-comparison.json` хранит counts/durations/log hashes и все33ERROR headers: exact sorted list совпал для native53 full,54full и54unit. Known32subcase errors — frozen/slotted `.state` assignment expectation в K1 registered Aim-loss; ещё1 — M5 `replace(init=False simulation_requests)` TypeError/ValueError expectation. Они не исправлялись в transport54, набор не объявляется полностью зелёным.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m unittest discover -s tests/unit -t tests -v
```

После обоих прогонов повторно сверены474package paths+SHA и89example hashes с installed transport evidence: изменений нет. Проверка ссылок и `git diff --check` выполнены отдельно после синхронизации документов.

Финальная проверка документации:1744local Markdown paths в20изменённых документах,0broken paths; anchors не проверялись. `git diff --check` завершился0, только LF→CRLF warnings.103незакоммиченных файла включают57предшествующих; commit/push не выполнялись. `.gitignore` и PDF книг не менялись.

## Следующая граница

Следующий шаг — отдельный bounded contract по [inventory](m8-continuation-inventory.md): начать с адресной сверки Crushed Rib10 и source-bound однократного next-Test Grim, включая Protection до Casting, затем подготовить finite proof будущего ADR-0055. Правило и scope ещё требуют этой сверки; transport4 Wound10 автоматически не включает.33прежние Python3.12 expectation errors остаются самостоятельной задачей.
