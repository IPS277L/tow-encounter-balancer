# M8 Crushed Rib full-owner: приёмка ADR-0056

Дата: 2026-11-02. Статус: **ADR-0056 закрыт в принятой ручной full-owner границе**. [Контракт56](../decisions/ADR-0056-source-bound-crushed-rib-owner-bridge.md), [предыдущая K1 граница55](m8-crushed-rib-test-readiness.md). Регрессионное подтверждение составное; один full run без failures не заявляется.

## Реализованная граница

[NpcCrushedRibContext и ConsumptionWitness](../../src/towr/domain/npc_crushed_rib_models.py) связывают pending injury или первый actual consuming M8 result с полным текущим owner. Оба frozen/slots типа экспортированы из `towr.domain`. Валидация исходных rosters/children, profiles, enum/bool/int/container forms, daily receipts/roll IDs и phase state выполняется до equality/RNG. Consumed context сохраняет exact receipt injury, definitions/day и ordered history prefixes; clock не регрессирует. Связь с произвольным глобальным журналом и намеренный restore старого immutable snapshot не доказываются.

[Protection lower](../../src/towr/domain/npc_champion_attack_models.py) хранит исходную normal preparation и pre-Test kernel. Computed effective Attack заменяет только выбранный defender Test. [Executor](../../src/towr/rules/npc_champion_attack_execution.py) вызывает один actual Attack, complete55, затем private [kernel continuation](../../src/towr/rules/kernel.py) с post-Test injury; создаёт один action receipt и завершает реальный Wound lifecycle. Miss/BOTH_FAIL расходуют effect; нулевые successes не отменяют Test. Новые10/superficial/другие Wounds и pending follow-ups регистрируются полностью, затем узкий context останавливается. Новая10 сохраняет собственный NEXT_TEST.

[Upper Protection](../../src/towr/domain/npc_roster_champion_attack_models.py) проверяет context в обе стороны с lower preparation/receipt; [factory](../../src/towr/rules/npc_roster_shooting_preparation.py) готовит55 из selected actual Protection. Подмена upper context на None при оставшемся lower witness отклоняется при Result/apply. [Wizard end-turn](../../src/towr/domain/npc_wound_turn_end_models.py) также требует context для Wound10 и повторно проверяет его после десериализации. Enemy end-turn не расходует Wizard effect.

[Casting request](../../src/towr/domain/cowardly_flight_casting_models.py) и [result](../../src/towr/domain/cowardly_flight_casting_result_models.py) получают только K1 preparation/completion. [Engine](../../src/towr/engine/cowardly_flight_casting.py) выполняет existing Casting attempt один раз и complete55 до pool/decision. Rule-of-Nine lock и final nines сохраняются. [Full-owner wrapper](../../src/towr/domain/npc_roster_casting_models.py) атомарно проецирует consumed Wizard injury, magic, action/history и обе child rosters. При первом расходующем Casting Movement/Miscast pending сохраняют nested55 receipt. Actual movement completion не перебрасывает Casting Test и не возвращает restriction, но выполняет normal target Willpower; тесты Miscast56 проверяют pending и блокировку новых действий, не полное исполнение Miscast outcomes. Следующая нормальная Casting/Protection использует первый witness в upper context/caller, без второго lower55 receipt или root archive.

Legacy Wizard action/end-turn admission для resolved10 с вручную удалённым NEXT_TEST и оставшимся Drained без witness закрыт. Это явное исправление допуска, а не обещание прежней совместимости stripped10. Все поддержанные None paths вне этого пробела сохраняют normal traces/RNG. Domain/engine не получают JSON/CLI зависимостей; RNG внедряется. Автоматические dispatcher/journal/runner/policies, mass trials, generation, adapters/JSON1–4/CLI и42schemas не расширены. Wound10 по-прежнему останавливает automatic runner; ручной typed bridge не является native policy.

Scope: одна canonical resolved/untreated/unhealed rolled10, optional prior superficial1–3 и только Drained. Несколько10,9/6/Wind, лечение/Fate/Lucky/Talents и дополнительные Tests не разрешены автоматически. Нормативные источники прежние: BOOK-PLAYER-GUIDE1.4 Rules108/Attack Tests118/Drained123, Casting156–157, Wounds Table190; BOOK-GM-GUIDE1.1 Champions92. При реализации новые страницы/PDF не открывались; новых Rule IDs/house rules нет.

## Детерминированные проверки

[17 context tests](../../tests/unit/test_m8_crushed_rib_context.py), [11 Casting](../../tests/unit/test_m8_crushed_rib_casting.py), [11 Protection](../../tests/unit/test_m8_crushed_rib_protection.py), [2 actual Casting integrations](../../tests/integration/test_m8_crushed_rib_casting.py), [5 full-owner Protection integrations](../../tests/integration/test_m8_crushed_rib_protection_owner.py). Проверены first consumption, later normal Test, zero success/BOTH_FAIL, old/new Wound provenance, actual lifecycle/history, stale/repeated apply, full-source mismatch и original aliases; invalid source отказывает до первого RNG draw. Дополнительно сохранены14 прежних end-turn checks и оба copied tests56.

Последний единый targeted run: **62 tests OK/4,031с**, CPython3.12.4, outside-sandbox runner. До него выполнены независимые old Casting/stationary/movement и kernel/action checks; их отдельные результаты не заменяют окончательный full run. Независимое ревью нашло и помогло закрыть pre-RNG aliases, detached child injury и удаление context из готового Result/end-turn. Два ранних full прогона остановлены через55,437с и52,469с до этих последних guards; их logs `adr0056-full-regression-pre-final-interrupted*.log` диагностические, не итоговое покрытие.

[Actual public example](../examples/m8/crushed_rib_owner.py), [stdout](../examples/m8/crushed_rib_owner.output.txt), [copied test](../../tests/integration/test_m8_crushed_rib_owner_example.py):63 scripted d10. First10→failed Grim Casting→pool0→2/WAIT→end-turn; другой настоящий current E2 Attack расходует effect, E3 normal Protection сохраняет первый witness. Отдельные new10 и superficial2 после Protection полностью сохраняют receipts и затем отклоняют новый context. Consumed injury входит в полный M8 только через production result/apply, ручного stripping нет. Исторический [contract probe25d10](../examples/m8/crushed_rib_owner_contract_probe.py) остаётся отдельной проверкой seams; его negative-control message уточнён под новый missing-context guard, saved stdout прежний.

## Установленный пакет

Новая отдельная venv собрана офлайн [build helper](../../tools/prepare_m8_transport_audit.ps1); рабочая `.venv` не менялась. [Audit helper](../../tools/audit_crushed_rib_owner_install.py) прошёл fresh installed Python с `-I`:477source/wheel/site py/json paths+SHA,2public exports, module site paths,42schemas/444local refs. Bundle7Python files без tests/private imports: owner63, owner-contract25, K1actual33, K1contract40 и3fixtures. Все8source/installed child commands дали exact saved stdout из внешнего cwd; source/copied fixtures сохранили SHA до/после. PDF/references в wheel отсутствуют.

Evidence `.cache/adr0056-installed-audit/checks/evidence.json`, log `.cache/adr0056-installed-checks.log`; wheel SHA256 `9461273001987fe074710a87cde65f71be42534c16216f33b2bfed8ead00889d`. Scope относительно закрытого55:1new module,18changed package files,0removed; `.cache/adr0056-production-scope.json`. Adapters/simulation/application/schemas не менялись.

```powershell
$env:PIP_NO_INDEX = '1'
$env:PIP_FIND_LINKS = "$PWD/.cache/adr0054-build-dependencies"
& ./tools/prepare_m8_transport_audit.ps1 -Repository $PWD -AuditDirectory "$PWD/.cache/adr0056-installed-audit"
.cache/adr0056-installed-audit/installed/Scripts/python.exe -I tools/audit_crushed_rib_owner_install.py --repository . --wheel .cache/adr0056-installed-audit/wheels/towr_encounter_balancer-0.1.0-py3-none-any.whl --work-dir .cache/adr0056-installed-audit/checks
```

Для повторения нужны новые AuditDirectory/work-dir и локальный build dependency cache. Команды не разрешают сетевую загрузку или изменение working environment.

## Окончательная регрессия

Полный `.cache/adr0056-full-regression.log`: **4158tests/1059,911с,33known errors,1failure,0skipped**. Все551integration прошли. Единственный failure — устаревший regex сообщения отказа в [старом unit test](../../tests/unit/test_m8_current_roster_casting.py): после закрытия gap вместо общего «Wound effects» выдаётся точное требование контекста Crushed Rib. Отказ до RNG правильный; изменено только ожидание этого сообщения, production/integration/примеры не менялись.

После исправления повторён **весь unit-набор:3607tests/105,099с,33known errors,0failures/0skipped**, `.cache/adr0056-final-unit-regression.log`. Таким образом подтверждены все4158current cases:551integration из полного прогона и3607unit после fixture fix. Это составное покрытие, не единый full run без failures и не зелёный набор. Старые33errors —32subcase expectation errors K1 frozen/slotted `.state` assignment и1M5 TypeError/ValueError expectation — остаются отдельной задачей.

`.cache/adr0056-regression-comparison.json` хранит counts/durations/logSHA и headers: exact sorted33ERROR headers full run совпали с baseline55. В отдельном unit loader отсутствует package prefix `unit.`; после ровно этой проекции остальные header text/параметры всех33cases совпали. Новых errors нет. Команды завершённых запусков:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m unittest discover -s tests/unit -v
```

После suite477package py/json paths+SHA совпали с installed evidence и pre-run snapshot; все97public example py/json/txt hashes прежние, включая93до56. Исторический owner-contract25 изменил только expected refusal message под новый guard; при audit/full run его bytes уже стабильны. Source/wheel/installed manifest не менялся после build. Проверены1786local Markdown paths/17изменённых документов:broken paths0 (anchors не проверялись); diff/whitespace чистые. Evidence `.cache/adr0056-document-checks.json`.60dirtyfiles включают31предшествующий; данные Git записи не менялись.

Следующий шаг после приёмки56 — подготовить отдельный ADR-0057 для native Crushed Rib dispatcher/journal/permission. Он должен выводить context из собственного actual prefix и сохранять mandatory follow-up order/old stops; автоматическое включение generation/JSON/wire5 не подразумевается. Commit/push, `.gitignore` и книги не менялись.
