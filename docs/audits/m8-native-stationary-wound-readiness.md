# M8: native stationary-wound policy и автоматическое продолжение

Дата: 2026-11-01. **ADR-0050 закрыт в согласованной native границе.** [Контракт](../decisions/ADR-0050-native-stationary-wound-policy.md): policy/eligibility/journal/diagnosis/runner, source/installed automatic example, native sequential/spawn, legacy transport и full regression проверены. Новых ошибок относительно baseline нет; suite с прежними errors не считается зелёным.

## Источники и граница

BOOK-PLAYER-GUIDE1.4, Rules115–116/119/122–123, Casting156/Miscasts157/Miscast Table159, Wounds Table190; BOOK-GM-GUIDE1.1, Champions92 непосредственно перечитаны. Новых Rule IDs/house rules или общего чтения книг нет. Scenario policy — техническое решение эксперимента.

Новый append-last `stationary_wound_continuation` имеет тип `NpcMagicStationaryWoundPolicy | None`; разрешён только `LEG_SPASM_STAND_AND_CONTINUE`. Miscast policy независима. Native policy включает canonical first9 stand и context49 Casting/Protection/end; preserved terrain9 запрещает Give Ground до treatment, но не любое ordinary movement.

## Матрица доказательств

| Граница | Evidence |
| --- | --- |
| Source model и lossless scope | [12 unit tests](../../tests/unit/test_m8_stationary_wound_policy.py): strict enum/None, four combinations, append-last/old positional forms, deepcopy/pickle, generation early rejection, direct JSON/request/result no-silent-drop, strict worker raw-string rejection. |
| Eligibility и типы источников | [Shared pure helper](../../src/towr/domain/npc_magic_stationary_wound_policy.py) использует canonical validators48/49. Только ожидаемый отказ pure source scope становится False; constructors/executors не перехватываются. Невалидная enum-policy отвергается даже на idle/pending diagnosis и при восстановлении journal. |
| Mandatory first stand | [20 unit tests](../../tests/unit/test_m8_stationary_wound_runner.py): full first9 source, current exact frame/no Close/unused move; stand до Casting/target selection и до старого Prone path. Skip/foreign source и повреждённый transported primitive без расхода free move отвергаются; StandResult повторно валидируется без reducer. |
| Сохранение Wound6 | Actual9→stand→incoming6→own-turn expiry→следующая защита сохраняет both Wounds/daily/roll/expired witness и обе child refs. Actor/end/target с selected Wound family не могут обойти canonical context через более слабый legacy guard. |
| Honest unsupported | Повторная9 после stand останавливается даже без6;9+history6, Wound10/13, missing scene/departure, Close/spent move, Wind Prone с retained terrain и mandatory Wound follow-ups не получают скрытого consumer. |
| Приоритет фаз | Actual level2 третий Casting с9,9,9 сохраняет raw Miscast при отсутствии Miscast policy; обе policies разрешают Wind21, затем retained terrain+Prone дают END_TURN stop. Actual lethal incoming Wound30 сохраняет немедленный dead exclusion до end/следующего actor. |
| Native propagation | [3 integration tests](../../tests/integration/test_m8_stationary_wound_runner.py): trial counts9actions/3rounds без stand-as-action, controlled sequential/spawn records+summary+assessment (1roundlimit/1unsupported, denominator2), seeded Random обоих policies; sources и parent RNG/child cleanup сохранены. |
| Public automatic flow | [Example](../examples/m8/stationary_wound_runner.py)/[stdout](../examples/m8/stationary_wound_runner.output.txt), [copied test](../../tests/integration/test_m8_stationary_wound_runner_example.py): two-file bundle только с `magic_scenario.py`, без tests/private sources. Four policy combinations, реальная automatic цепочка48d10 и native sequential/spawn controlled pair. |
| Packaging |459 `.py/.json` source/wheel/installed path+SHA256 parity. Installed `python -I` запускает copied public example, включая настоящий spawn новой policy; stdout совпадает с source. |

Public positive profile — явно authored Wizard4. Tens на Casting не добавляют Miscast dice; отдельные level2 controls используют настоящие9. Пример выполняет48d10 при stationary-on для обоих Miscast settings и7d10 при stationary-None. Дополнительные native sequential/spawn pair потребляют55d10 каждый. Итого220scripted d10, не вероятности.

Independent review выявил и помог закрыть enum/string equality laundering в worker/source gating, silent generation projection при forged request и отсутствие повторной validation нового transported StandResult. Также проверен canonical-source fallback: удаление terrain не позволяет selected policy пройти через legacy Casting без context. Исполнители не повторяются, RNG не перематывается.

## Выполненные проверки

12policy unit +20runner unit +3native integration +1copied example =36 новых tests. Проверялись по этапам, успешные наборы не повторялись без нового изменения/риска. Native integrations —3tests OK,3,122с вне sandbox. Legacy model/generation/wire —123tests OK,40,518с; old positional assertion адаптирован к append-last field. Journal/runner/stand/copies —42tests OK,2,516с. Расширенный copied example со spawn —1test OK,3,706с после изменения proof.

Ранее низкоуровневый Step vocabulary отвергал Leg Spasm result по типу. Теперь vocabulary расширен; предыдущие negative tests и старый public stand example проверяют отказ scenario policy, а не отсутствие класса в union. Их отрицательная проверка не удалена, stdout старого stand сохранён.

## Установка и воспроизведение

Новый несуществующий directory, из корня на Windows:

```powershell
tools/prepare_m8_transport_audit.ps1 -Repository (Get-Location).Path -AuditDirectory "$((Get-Location).Path)/.cache/adr0050-installed-repeat"
.cache/adr0050-installed-repeat/installed/Scripts/python.exe -I tools/audit_m8_leg_spasm_install.py --repository . --wheel .cache/adr0050-installed-repeat/wheels/towr_encounter_balancer-0.1.0-py3-none-any.whl --work-dir .cache/adr0050-installed-repeat/native-checks --example stationary_wound_runner
.cache/adr0050-installed-repeat/installed/Scripts/python.exe -I tools/audit_m8_transport_install.py --repository . --wheel .cache/adr0050-installed-repeat/wheels/towr_encounter_balancer-0.1.0-py3-none-any.whl --work-dir .cache/adr0050-installed-repeat/transport-checks
```

Actual wheel SHA256: `244a037a4bd170db9e8b5b1857aa84b7ebb10b764319fe5c2bb5f8c42e78ebeb`. Финальный native evidence: `.cache/adr0050-installed-audit/native-verified/evidence.json` и соседний stdout. Два top-level helper child commands (source/installed), каждый запускает native spawn; это не подсчёт всех OS worker processes.

Runtime dependencies скопированы с metadata из рабочего venv; project wheel ставится offline `--no-index --no-deps`, `pip check` OK. Build isolation может загружать setuptools. Working venv не переустанавливался. Installed children без PYTHONPATH/PYTHONHOME, `-I`; bundle добавляет только свою папку. Cwd внутри checkout `.cache`, но вне source/tests/original examples. Проверяются package `.py/.json`, не metadata/dependency bytes. Новых performance/cross-platform claims нет.

## Full regression и legacy transport

Полная регрессия вне sandbox: **3901 tests /33known errors /0failures /0skipped,1073,701с**. Full command: `$env:PYTHONPATH='src'; .venv/Scripts/python.exe -m unittest discover -s tests -v`, log `.cache/adr0050-regression.log`. Все33 exact ERROR headers совпали с `.cache/adr0049-regression.log`:32 K1 frozen/slotted property expectations и1 M5 replace(init=False) expectation Python3.12. Новых errors/failures нет; полный suite не зелёный.

Все36 новых tests прошли:12policy unit +20runner unit +3native integration +1copied example. Финальная220d10 версия copied example со spawn включена в полный прогон. Это correctness evidence фиксированного runtime Windows/CPython3.12.4, не сравнение производительности с предыдущими прогонами.

Transport audit завершён exit0:95child commands/12magic backend cases/2copied examples;30schemas/324local refs/12magic schemas. Source/module/console stdout совпадают для обеих magic families v1/v2-null/v2-opted × sequential/process; шесть прежних routes сохраняют success/v2 rejection. Все request/result/error schemas, error-version/fallback/mismatch guards проверены. Saved v2 simulation/balance outputs совпали с новым installed audit после нормализации CRLF/LF. Нового поля/schema для stationary policy нет.

Transport log `.cache/adr0050-transport.log`, evidence `.cache/adr0050-installed-audit/transport-checks/evidence.json`. Runtime dependencies: jsonschema4.26.0, referencing0.37.0, jsonschema-specifications2025.9.1, attrs26.1.0, rpds-py2026.9.1, typing-extensions4.16.0.

Финально проверены1675 локальных Markdown-путей в24 изменённых документах (без anchors), `git diff --check` — OK. Source package после сборки не менялся; финальный public proof с installed spawn проверен отдельно и полным набором. Предыдущие незакоммиченные изменения сохранены; commit/push не выполнялись.

## Ограничения и следующий шаг

Новый opt-in пока только native Scenario/trial/simulation/explicit candidate APIs. Generation template с ненулевой policy и JSON1/2 serialization отвергаются до неподдержанной projection; это lossless boundary, не temporary legacy view. Fresh-only wire не становится save/resume.

Следующая веха — ADR-0051: explicit generation family propagation и отдельный versioned wire/CLI контракт новой policy. Не превращать `miscast_continuation` в общий Wound opt-in. Повторный stand с частично снятыми9causes/history6, movement, Recover/treatment, другие Wounds/Miscasts требуют отдельных consumers. Unsupported остаётся в общем denominator.
