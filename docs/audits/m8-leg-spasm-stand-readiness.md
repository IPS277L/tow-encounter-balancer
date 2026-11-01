# M8: аудит source-bound Leg Spasm self-stand

Дата: 2026-11-01. **ADR-0048 закрыт в согласованной low-level границе.** [Контракт](../decisions/ADR-0048-source-bound-leg-spasm-stand.md): реализация, public example, isolated install, transport checks и полная регрессия завершены. Новых ошибок относительно baseline нет; полный suite с известными errors зелёным не считается.

## Граница и доказательства

BOOK-PLAYER-GUIDE1.4, приложение Wounds Table190, строка9; гл.V Free Actions116, Conditions122/Prone123; BOOK-GM-GUIDE1.1, гл.VII Champions92. Нормативные страницы сверены на контрактном этапе; нового полного чтения книг, Rule IDs или house rules при реализации/аудите нет.

| Обязательство | Проверка |
| --- | --- |
| Канонический источник | [25 unit tests](../../tests/unit/test_m8_leg_spasm_stand.py): полные пары Prone/UNTIL_REMOVED и Difficult Terrain/UNTIL_TREATED каждого Wound9; resolved untreated/unhealed9 и superficial1–3; multiple9, fixed-entry provenance, strict integers/bools, duplicate/missing/foreign effects и другие Wounds отвергаются. |
| Полный owner | [Модели](../../src/towr/domain/npc_roster_leg_spasm_models.py) сохраняют Wound/daily/roll histories, magic/round/actions/positions, других участников и обе child roster references. Проверяется полный immutable before/after и исходная неизменность. |
| Единственное исполнение | [Executor](../../src/towr/rules/npc_roster_leg_spasm_resolution.py) вызывает один existing K1 removal; no Test/RNG. Apply требует полного source equality, stale/replay отвергаются. Pending/turn guards сохраняются. |
| Реальная рана | [Integration](../../tests/integration/test_m8_leg_spasm_stand.py) и [новый public example](../examples/m8/leg_spasm_stand.py) получают Wound9 реальным fresh runner при None/explicit policy, затем вызывают новый request/stand/apply. Controls10/13 получены реальными атаками и отвергаются. |
| Честная граница runner | До stand — ACTOR_INJURY; после stand retained Difficult Terrain по-прежнему даёт ACTOR_INJURY. Новый result не принимается automatic journal. Scope Casting/Protection/end-turn не расширен. |
| Копируемый пример | Только `leg_spasm_stand.py` + `magic_scenario.py`, без tests/private sources. [Сохранённый stdout](../examples/m8/leg_spasm_stand.output.txt), [subprocess test](../../tests/integration/test_m8_leg_spasm_stand_example.py):1 test OK,0,767с вне sandbox. Всего45scripted d10; stand дополнительных бросков не делает. |
| Установка | [Installed helper](../../tools/audit_m8_leg_spasm_install.py): исходники/wheel/установленные457 `.py/.json` совпадают по наборам путей/SHA256, оба новых модуля импортируются из isolated venv; PDF/reference sources отсутствуют в wheel. Source и installed copied example дают одинаковый полный stdout. |

Независимое read-only review исходного контракта и implementation пунктов1–2 не выявило блокеров. Оба explicit факта stand обязательны: отсутствие enemy Close подтверждается полным authored hostile-pair snapshot, отсутствие внешней неснимаемой причины задано сценой. Из одной Zone дальность не выводится. Новая проверка не утверждает, что другие книжные раны вообще запрещают вставать: они вне этого consumer.

## Воспроизведение установки

Команды из корня репозитория, Windows/CPython3.12.4. Для повтора выбрать новый несуществующий audit directory:

```powershell
tools/prepare_m8_transport_audit.ps1 -Repository (Get-Location).Path -AuditDirectory "$((Get-Location).Path)/.cache/adr0048-installed-repeat"
.cache/adr0048-installed-repeat/installed/Scripts/python.exe -I tools/audit_m8_leg_spasm_install.py --repository . --wheel .cache/adr0048-installed-repeat/wheels/towr_encounter_balancer-0.1.0-py3-none-any.whl --work-dir .cache/adr0048-installed-repeat/leg-spasm-checks
.cache/adr0048-installed-repeat/installed/Scripts/python.exe -I tools/audit_m8_transport_install.py --repository . --wheel .cache/adr0048-installed-repeat/wheels/towr_encounter_balancer-0.1.0-py3-none-any.whl --work-dir .cache/adr0048-installed-repeat/transport-checks
```

Helper подготовки создаёт копию сборки и отдельный venv. Build isolation может загружать setuptools; project wheel устанавливается offline с `--no-index --no-deps`. Runtime dependencies скопированы вместе с metadata из рабочего venv, `pip check` прошёл. Рабочее окружение не переустанавливалось.

Actual wheel SHA256: `f649874fdbfc773c0260fa6158eb106b983c7fca742c94b6ae7dcc76c12a91e6`. Installed check выполнен с `-I`, child environment очищен от PYTHONPATH/PYTHONHOME; bundle добавляет только собственную папку. Cwd `.cache/adr0048-installed-audit/leg-spasm-checks` — внутри checkout, но вне source/tests/original examples. Это parity package `.py/.json`, не metadata/launcher/dependency bytes или всего репозитория.

Evidence окончательного примера: `.cache/adr0048-installed-audit/leg-spasm-verified/evidence.json` и соседний stdout;2child commands/1copied example. После review добавлен explicit current/initial placements equality перед использованием ranges; финальная установленная копия прошла повторно. Локальные wheel/venv/logs не нужны для переноса контекста. Новых performance/cross-platform claims нет.

## Полная регрессия и transport

Полная регрессия вне sandbox: **3825 tests /33known errors /0failures /0skipped,657,616с**. Команда: `$env:PYTHONPATH='src'; .venv/Scripts/python.exe -m unittest discover -s tests -v`; log `.cache/adr0048-regression.log`. Все33 exact ERROR headers совпадают с `.cache/adr0047-balance-v2-regression.log`:32 K1 frozen/slotted property expectations и1 M5 replace(init=False) expectation. Это существующие ошибки проверок типов исключений Python3.12, не новые игровые регрессии; suite не зелёный.

Набор вырос с3796 до3825:1 исходный contract-probe test,25unit+2integration реализации и1copied public example. Финальная версия нового примера (с current/frame placement check) и все остальные новые tests прошли в полном наборе. Успешная проверка повторно не запускалась.

Transport helper завершился exit0 под новым wheel:95child commands,12magic backend cases,2copied examples;30schemas/324local refs/12magic schemas. Source/module/console outputs совпадают для обеих magic families v1/v2-null/v2-opted × sequential/process; шесть прежних routes сохраняют success/v2 rejection. Все request/result/error schemas валидируются, fallback/mismatch/error-version guards проверены. Полные сохранённые simulation/balance v2 outputs совпали с новым installed audit после нормализации CRLF/LF.

Evidence: `.cache/adr0048-installed-audit/transport-checks/evidence.json`, log `.cache/adr0048-transport.log`. Runtime dependencies: jsonschema4.26.0, referencing0.37.0, jsonschema-specifications2025.9.1, attrs26.1.0, rpds-py2026.9.1, typing-extensions4.16.0.

Финально проверены1581 локальный Markdown-путь в20 изменённых документах (без anchors), `git diff --check` — OK. В текущем audit-срезе production не менялся: добавлены public example/stdout, copied test, installed helper и отчёт; обновлены docs. Ранее созданные implementation/transport изменения сохранены. Commit/push не выполнялись.

## Следующая граница

Следующий шаг — подготовить ADR-0049 и finite proof stationary continuation с retained Leg Spasm restriction: Casting/Protection/end-turn, coexistence Wound6 expiry, authoritative injury/source guard и explicit runtime policy. Movement/Give Ground, Broken, Recover/treatment и wire policy требуют отдельных решений. `miscast_continuation` не становится общим Wound opt-in.

Текущие blockers: `NpcRosterCastingRequest`, `NpcChampionAttackRequest`, `NpcWoundTurnEndRequest`, Prone end и `_injury_supported`. End-turn validators обращаются к `e.condition`, поэтому одного расширения whitelist недостаточно для coexistence restriction + timed condition. Сначала согласовать typed source/condition projection и exact expiry contract, затем подключать исполнение/runner. В этом аудите эти guards не менялись.
