# Casting-действие M8

[ADR-0035](../../decisions/ADR-0035-cowardly-flight-casting-boundary.md) реализован и закрыт [аудитом](../../audits/m8-casting-readiness.md) в границе одного Casting-действия с Curse of Cowardly Flight. [Input](../../../src/towr/domain/cowardly_flight_casting_models.py), [result](../../../src/towr/domain/cowardly_flight_casting_result_models.py) и [executor](../../../src/towr/engine/cowardly_flight_casting.py) доступны через typed Python API. Существующие mixed JSON/CLI не принимают мага или spell.

## Самостоятельный production-пример

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m8/casting_action.py
```

[casting_action.py](casting_action.py) использует execute_cowardly_flight_casting и public models/scheduler, без imports tests или private helpers. [Сохранённый вывод](casting_action.output.txt) проверяется [subprocess test](../../../tests/integration/test_m8_casting_example.py) из временного cwd. Запуск с отдельно установленным wheel также проверен: код загружен из installed target, stdout совпал, stderr пуст.

Шесть supplied activations расходуют ровно 24 scripted d10:

- WAIT с одним успехом → следующая активация с двумя успехами → CAST CV3/Potency2; first сопротивляется, second получает Broken.
- Pool == Wizard Level оставляет WAIT; следующая активация с pool > Level возвращает MISCAST_REQUIRED, даже при достаточных successes. Сохраняются pool, successes, receipt и pending source; preparation, desperate spell и таблица не выполняются.
- Удержанные ранее 3 successes и последний roll 0 дают Potency0, два target records без Willpower Tests.
- Пустая Zone даёт CAST без target Tests.

Проверяются один receipt на действие, unchanged inputs/spatial/global RNG и отказ повторного returned slot, чужого actor и обязательного pending Miscast до RNG. Числа caster `3d/3`, Level2 и Minion-целей `3d/3` — authored inputs, не профиль Hermit Witch. Caster не получает Minion injury policy. Изолированная Zone объясняет невозможность Give Ground; дальность и факты задаются явно.

Переходы между activations поставляет caller; пример не симулирует промежуточные ходы, следующий ход Broken, полный бой или objective/Monte Carlo. Настоящий переход раунда отдельно покрыт [integration tests](../../../tests/integration/test_m8_cowardly_flight_casting.py). Broken сохраняется как Condition, не defeat.

## Предварительный probe K1

[casting_contract_probe.py](casting_contract_probe.py) сохранён как пример ранней композиции отдельных K1 reducers; он не вызывает новый M8 executor:

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m8/casting_contract_probe.py
```

Для использования production API выбирайте casting_action.py. Probe остаётся исторической проверкой составимости нижних фаз.

Источники: **BOOK-PLAYER-GUIDE 1.4**, Rules / Combat Actions / Improvise, стр. 117; Conditions / Broken, стр. 122; Magic in the Old World / Casting a Spell / Interrupted Casting, стр. 156; Spell Potency / Miscasts and the Rule of Nine, стр. 157; Formal Spells, стр. 160; Battle Magic / Curse of Cowardly Flight, стр. 162. **BOOK-GM-GUIDE 1.1**, Allies and Antagonists / Champions, стр. 92; Hermit Witch, стр. 130.

[Контракт интеграции ADR-0036](../../decisions/ADR-0036-magic-encounter-integration.md) и standalone Give Ground completion реализованы. Пример casting_action.py сохраняет исходную границу без движения. MOVEMENT_REQUIRED и completion уже перенесены в roster/Champion owner; первый Broken Recover (safe/free move) с Casting interruption также реализован. Обычный Broken Run также реализован отдельно; первый end-turn Stomach Blow → expiry Drained также реализован. Другие timed effects, terrain/Athletics и обязательные Miscast continuations остаются отдельными consumers. Полного encounter runner ещё нет.

## Контракт первого encounter

[ADR-0037](../../decisions/ADR-0037-magic-scenario-runner.md) задаёт один authored Champion-Wizard, союзный и вражеский Minion, актуальные scene facts, objective/лимит и полные unsupported stops. Production [scenario/facts/policies](../../../src/towr/domain/npc_magic_scenario_models.py) и [scene models](../../../src/towr/domain/npc_magic_scene_models.py) с pure admission реализованы. [encounter_contract_probe.py](encounter_contract_probe.py) проверяет этот вход и композицию прежних компонентов; result/runner ещё отсутствуют.

```sh
PYTHONPATH=src python docs/examples/m8/encounter_contract_probe.py
```

[Сохранённый вывод](encounter_contract_probe.output.txt): production admission расходует 0 d10, action chains — 38 scripted d10 (6 дополнительных для оставшегося хода союзника перед реальным advance/start). Public helper admitted_scenario() собирает полный frozen вход из authored initial(), с explicit GM flags/routes/defeat choices. Lookup ещё не заданного будущего frame возвращает None. Probe не импортирует tests/private helpers, сохраняет исходные snapshots и global RNG. Все activations запускают full-owner wrappers над существующим scheduler, порядок сторон обычный; отдельные fixtures меняют сторону Wizard, без фиктивных промежуточных ходов.

- 10 d10: обычная incoming Shooting → Stomach Blow/daily receipt → Wizard Casting → target-turn expiry Drained, с сохранением Wound/магии/histories.
- 7 d10: Nicked Arm сохраняет полный Endurance follow-up и блокирует end-turn.
- 6 d10: Curse → обязательный Give Ground → Willpower/Broken → end-turn; один Casting receipt, обновлённые позиции, Broken не defeat.
- 3 d10: Miscast сохраняет весь pool/source/receipt и останавливается до preparation/table/desperate choice.
- 6 d10: bound Minion Attack переносит defeat/full pending в magic owner. End-turn блокируется, затем explicit knocked-out decision/GM approval закрывает pending и исключает ожидающую цель без новых d10; после этого caller явно завершает ход атакующего.

Принятый scenario.initial далее используется в реальной Curse → Give Ground цепочке; после движения новый key отсутствует в supplied frames, без выдуманного контекста. [31 deterministic test](../../../tests/unit/test_m8_npc_magic_scenario.py) дополнительно проверяет frozen/source/type/role/partition/Range/Speed/route guards, обе Wizard/perspective стороны и independent orders. Все 238 M8 tests проходят.

`scenario.initial_runtime_state` присоединяет пустой Minion ledger до первой активации; сам scenario.initial остаётся fresh admitted source. Probe использует этот runtime в Curse, incoming Champion Wound и Minion handoff. [Bound models](../../../src/towr/domain/npc_roster_minion_attack_models.py) и [executor/application](../../../src/towr/rules/npc_roster_minion_attack_resolution.py) сохраняют полный source/pending без второго Attack. 19 unit + 6 integration tests покрывают перенос/блокировки/оба ledgers, все 263 M8 tests проходят.

Bound defeat [models](../../../src/towr/domain/npc_roster_minion_defeat_models.py)/[functions](../../../src/towr/rules/npc_roster_minion_defeat_resolution.py) добавлены; пример сохраняет source/decision, exact acknowledgement ID и полный roster/round. Replay закрытого результата отвергается. Это не narrative inventory/death engine: equipment и injury повторно не меняются. 10 unit + 4 integration tests, все 277 M8 tests проходят.

Probe не выбирает маршруты/тактику автоматически, не выполняет полный бой и не проверяет четыре будущих outcomes. [Full-owner start/advance](../../../src/towr/domain/npc_roster_turn_models.py) реализованы: 17 новых tests, 294 M8 суммарно; фазы расходуют 0 d10, сверяют pending/таймеры и сохраняют архив/оба ledgers. Следующий срез — typed encounter steps/result/unsupported с pure chain validation, затем runner. Raw M2 round API остаётся Minion-only; общие чистые defeat/exclusion helpers переиспользуются без фиктивного round с Champion.
