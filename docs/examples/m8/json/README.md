# Текущий Magic JSON-контракт

Поддерживается только `schema_version="6"` по [ADR-0063](../../../decisions/ADR-0063-single-current-magic-contract.md). Прежние форматы1–5 удалены, конвертеров нет. Номер формата не меняется при каждом добавлении правила во время разработки.

## Базовые примеры

- Simulation: [request](magic-simulation.request.json), [result](magic-simulation.result.json), [error](magic-simulation.error.json).
- Balance: [request](magic-balance.request.json), [result](magic-balance.result.json), [error](magic-balance.error.json).

Это fresh authored sources: source/seed/trials прежних базовых сценариев сохранены; все пять nullable permissions явно заданы какnull. Saved results — конечные наблюдения указанного runtime, не эталон вероятности и не гарантия одинаковых Monte Carlo bytes между версиями Python.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-magic docs/examples/m8/json/magic-simulation.request.json
.venv/Scripts/python.exe -m towr balance-magic docs/examples/m8/json/magic-balance.request.json
```

После установки используются `towr simulate-magic INPUT` и `towr balance-magic INPUT`; `-` читает UTF-8 из stdin. Process задаётся во входе: `{"mode":"process","workers":2,"batch_size":1}` в `execution`; CLI не переопределяет seed/budget/source.

## Дополнительные сценарии того же формата

- Battered Leg: [simulation](magic-simulation-v6.request.json), [balance](magic-balance-v6.request.json). Это профиль Endurance2d/5 и matching family assertion, не иной wire contract.
- Stationary Wound: [simulation](magic-simulation-stationary.request.json), [balance](magic-balance-stationary.request.json).
- Гибель Wizard: [request](dead-champion-v1.request.json), [result](dead-champion-v1.result.json). Историческое имя сценария сохранено; содержимое использует6.

## Строгие границы

`miscast_continuation`, `stationary_wound_continuation`, `repeated_leg_spasm_continuation`, `crushed_rib_continuation` и `battered_leg_continuation` обязательны даже приnull. Balance отдельно задаёт их в `reserve.scenario` и `generation`; значения должны полностью совпадать. Endurance profile содержит strict integer `dice>=1`, `threshold=1..10`, без custom cap. Repeated требует stationary. Значение permission не разрешает произвольные injury combinations.

Схемы закрыты для неизвестных полей и разрешаются offline через общие definitions. Float tokens, duplicate keys, nonfinite numbers и invalid UTF-8 отвергаются. Неподдержанная строковая версия даёт `unsupported_version`; все ошибки представлены текущим форматом6. Lexical failure имеет request_id=null; после полного decoding доверенный ID сохраняется.

Это fresh-source contract: текущее состояние боя, history и save/resume не передаются. Domain/engine, UNSUPPORTED_PATH в знаменателе trials и ограничения игровых consumers не меняются при очистке wire versions. История прежних форматов и проверок хранится в ADR, audits и Git.
