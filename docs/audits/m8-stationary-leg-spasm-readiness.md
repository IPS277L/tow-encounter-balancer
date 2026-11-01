# M8: stationary continuation после Leg Spasm

Дата: 2026-11-01. **ADR-0049 закрыт в согласованной low-level границе.** [Контракт](../decisions/ADR-0049-stationary-leg-spasm-continuation.md): пункты1–4 реализованы и проверены, actual mixed flow/isolated install/transport/full regression завершены. Новых ошибок относительно baseline нет; полный suite с прежними errors не считается зелёным.

## Проверенная граница

BOOK-PLAYER-GUIDE1.4, Rules115–116/118–119/122–123, Casting156/Miscasts157, Wounds Table190–191; BOOK-GM-GUIDE1.1, Champions92. Все страницы непосредственно перечитаны в contract-срезе, версии/хэши прежние. Новых Rule IDs, house rules или общего прочтения книг нет.

Explicit low-level context допускает living Wizard с canonical retained terrain9, superficial1–3 и active/expired6; strict-True no-external-causes fact. Normal Tests без бонусов/Glorious/Fate. После stand нет Prone Shooting−1d; Give Ground остаётся запрещённым по119+190. Ordinary movement не объявляется невозможным.

| Обязательство | Evidence |
| --- | --- |
| Canonical full source | [Контекст](../../src/towr/domain/npc_stationary_wound_models.py), [23 unit tests](../../tests/unit/test_m8_stationary_wound_context.py): exact ordered terrain/Condition views, strict facts/types/provenance, duplicate/missing effects, active/expired6, source/role/pending/clock guards. Drained iff active6. |
| Exact expired source | [Receipt](../../src/towr/domain/npc_wound_turn_models.py) сохраняет keyword-only `expired_sources` только для нового end-path; actual actor/attack order/deadline и root daily/consumed/Wound linkage проверены. IDs-only receipts новой области недостаточно. None сохраняет старые receipts. |
| Casting / end | [6 новых tests](../../tests/unit/test_m8_stationary_wound_casting_end.py): full source/role, None rejection, exact known Condition causes, single scheduler/no Test/RNG, immutable histories и stale/replay. Typed Condition filtering не обращается к `.condition` restriction effects. |
| Incoming Shooting | [9 новых tests](../../tests/unit/test_m8_stationary_wound_shooting.py): lower full witness + outer exact root, foreign root с тем же child, unchanged normal Protection, Drained6, effective GG=False, actual new6+expiry, unsupported new4/9/10/13 сохранены без отката. |
| Multiple causes | Actual second6 поверх actual first6 + authored terrain fixture: оба bound expiry сохраняются после чужого end и истекают на Wizard end, terrain/истории остаются. |
| Actual manual chain | [Public example](../examples/m8/stationary_wound_continuation.py)/[stdout](../examples/m8/stationary_wound_continuation.output.txt), [copied test](../../tests/integration/test_m8_stationary_wound_continuation.py): actual9→stand→Casting/end→incoming6→Casting/end/expiry→Protection в round3. 39scripted d10, никаких ручных изменений injury/expiry/clock. |
| Installed package |458 `.py/.json` source/wheel/installed path+SHA256 parity, включая новый context; copied three-file bundle под `python -I`, exact source/installed stdout. |

Независимые review нашли и проверили устранение двух chronology gaps: подмена active expiry witness с теми же IDs и преждевременный expired receipt без сохранённого deadline. Также уточнён фактический mapping: daily registration ID оканчивается `:daily-wound`, receipt ID — `:daily-wound:receipt`; wound request и lifecycle имеют разные IDs. Это технические исправления source evidence, не изменение книжного срока.

Контрактный [probe](../examples/m8/stationary_wound_contract_probe.py)/[test](../../tests/integration/test_m8_stationary_wound_contract_probe.py) сохраняется как проверка None admission и независимых K1/actual6 controls. Он не подменяет новую mixed full-owner chain. Новый public example не включает automatic runner policy.

## Выполненные проверки

38 новых unit tests:23 context +6 Casting/end +9 Shooting. Успешные части не повторялись без новых изменений; после archive refinement проверены8 затронутых context cases и20 Casting/end+legacy tests (0,093с). Stage3 legacy:46 tests OK. Первый source/None набор:26 tests OK. Полный результат ниже даёт единый актуальный набор.

Public copied flow до archive refinement вместе с6новыми Casting/end tests:7tests OK,1,921с. После archive refinement прямой39d10 flow прошёл снова; финальная установленная копия также прошла. Source/global RNG неизменны; ни treatment/healing, ни extra terrain Test не добавлены.

## Воспроизведение установки

Новый несуществующий audit directory, из корня проекта:

```powershell
tools/prepare_m8_transport_audit.ps1 -Repository (Get-Location).Path -AuditDirectory "$((Get-Location).Path)/.cache/adr0049-installed-repeat"
.cache/adr0049-installed-repeat/installed/Scripts/python.exe -I tools/audit_m8_leg_spasm_install.py --repository . --wheel .cache/adr0049-installed-repeat/wheels/towr_encounter_balancer-0.1.0-py3-none-any.whl --work-dir .cache/adr0049-installed-repeat/stationary-checks --example stationary_wound_continuation
.cache/adr0049-installed-repeat/installed/Scripts/python.exe -I tools/audit_m8_transport_install.py --repository . --wheel .cache/adr0049-installed-repeat/wheels/towr_encounter_balancer-0.1.0-py3-none-any.whl --work-dir .cache/adr0049-installed-repeat/transport-checks
```

Actual wheel SHA256: `1570ec5ac31782c39db9363ea2dd9d520586f93ab0daaaeb86608dbd86211764`. Installed evidence: `.cache/adr0049-installed-audit/stationary-checks/evidence.json`,2child commands/1copied example. Helper с явным `--example` сохраняет прежний default Leg Spasm stand audit.

Working venv не переустанавливался. Project wheel ставится `--no-index --no-deps`, runtime dependencies копируются с metadata из рабочего venv; `pip check` OK. Build isolation может загрузить setuptools. Cwd внутри `.cache`, вне source/tests/original examples, но внутри checkout; PYTHONPATH/PYTHONHOME убраны из installed children. Проверяется package `.py/.json`, не metadata/launcher/dependency bytes. Новых performance/cross-platform claims нет.

## Полная регрессия и transport

Полная регрессия вне sandbox: **3865 tests /33known errors /0failures /0skipped,1255,616с**. Full command: `$env:PYTHONPATH='src'; .venv/Scripts/python.exe -m unittest discover -s tests -v`, log `.cache/adr0049-regression.log`. Все33 exact ERROR headers совпали с `.cache/adr0048-regression.log`:32 K1 frozen/slotted property expectations и1 M5 replace(init=False) expectation Python3.12. Новых errors/failures нет, полный suite не зелёный.

Набор вырос с3825 до3865:23context +6Casting/end +9Shooting unit tests,1original contract probe и1actual public mixed flow. Все40 новых tests прошли, включая финальный archive witness и copied output. Это correctness evidence фиксированного Windows/CPython3.12.4 runtime, не performance comparison с предыдущим прогоном.

Transport audit завершён exit0:95child commands/12magic backend cases/2copied examples,30schemas/324local refs/12magic schemas. Обе magic families v1/v2-null/v2-opted × sequential/process дают одинаковый source/module/console output; шесть прежних routes сохраняют success/v2 rejection. Saved v2 simulation/balance outputs совпали с новым installed output после нормализации CRLF/LF. Error-version/fallback/mismatch guards и все request/result/error schemas проверены.

Transport log: `.cache/adr0049-transport.log`, evidence `.cache/adr0049-installed-audit/transport-checks/evidence.json`. Dependencies: jsonschema4.26.0, referencing0.37.0, jsonschema-specifications2025.9.1, attrs26.1.0, rpds-py2026.9.1, typing-extensions4.16.0. Default обновлённого installed helper также проверен отдельно: прежний Leg Spasm stand copied example совпал source/installed stdout,2child commands, `.cache/adr0049-installed-audit/leg-compat-checks/evidence.json`.

Финальная проверка:1633 локальных Markdown-пути в22 изменённых документах — OK (без anchors), `git diff --check` — OK. Новые и прежние незакоммиченные изменения сохранены. Commit/push не выполнялись.

## Ограничения и следующий шаг

Context — explicit low-level opt-in. Scenario policy, journal union, diagnosis, dispatcher и JSON1/2 не расширяются. Не выбирать новую тактику за caller. Повторный stand с history6, Broken, движение/Give Ground, treatment, дополнительные modifiers/Fate и другие Wounds вне scope; результаты новых атак/mandatory pending сохраняются для отдельного consumer.

Следующий шаг — подготовить ADR-0050 и finite proof отдельной native stationary-wound policy и journal/diagnosis/runner integration, использующей доказанные low-level consumers. Generation/wire propagation потребует отдельного transport решения с lossless rejection до поддержки. `miscast_continuation` не переопределяется как Wound permission.
