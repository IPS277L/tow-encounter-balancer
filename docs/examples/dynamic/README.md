# Динамический генератор: первый сквозной срез

Генератор сам создаёт NPC, варьируя WS/Strength/Toughness/Agility, Melee/Athletics, Staff/Dagger и Light Armour. Число врагов может быть фиксированным: поиск всё равно меняет их параметры и экипировку. Готовый reserve и книжные NPC не нужны. [Контракт и ограничения](../../decisions/ADR-0113-dynamic-npc-generation-and-adaptive-search.md).

Запуск JSON/CLI из корня репозитория:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr generate-encounter docs/examples/dynamic/search.request.json > generated.json
```

После установки доступна та же команда `towr generate-encounter INPUT`; `-` читает UTF-8 JSON из stdin. [Полный входной пример](search.request.json) содержит только party/facts/day, пространство компонентов, число NPC, цели и бюджет. Нет enemy reserve, target_priority или defeat_decisions в партии. Эти поля создаются при сборке найденных боёв; порядок партии определяет PC activation/NPC target priority, порядок NPC — PC target priority/NPC activation. `defeat_disposition` явно подтверждает общее GM-решение для созданных целей.

JSON family `dynamic_encounter_search`, version1: `search_space` задаёт массив разрешённых значений каждого параметра и массив альтернативных наборов abilities. `npc_count.minimum/maximum` ограничивают численность. `targets.win_rate` и `targets.started_rounds` — сокращённые дроби `{numerator, denominator}`; например3/5 и3/1. Только integer JSON tokens, seed — десятичная строка uint64. Бюджет обязан покрывать `max_candidates * exploration_trials + top_k * finalist_trials`. Первый CLI backend — `execution: {"mode":"sequential"}`. Все поля закрыты; неподдержанные компоненты/режимы и несогласованные значения отвергаются до симуляции.

Пример ограничен3кандидатами ×2trials +2финалистами ×3trials =12trials максимум. Для полезной оценки увеличьте trials и budget: например12×16+3×64=384. Значения smoke-примера демонстрируют формат и воспроизводимость, но дают широкие интервалы.

JSON-результат содержит `source_request` (полный точный вход), `explored`, отдельные `validations`, `selected` (ID только финалистов без observed unsupported), фактические `total_trials`, `proposal_attempts` и `proposal_limit_reached`. Каждый кандидат содержит NPC компоненты, win rate/Wilson95, mean started rounds/Hoeffding95, outcome counts и `replay` — полноценный текущий PC simulation JSON1. Чтобы повторить конкретный бой:

```powershell
$r = Get-Content generated.json -Raw | ConvertFrom-Json
$r.validations[0].replay | ConvertTo-Json -Depth 100 | Set-Content replay.json -Encoding utf8NoBOM
.venv/Scripts/python.exe -m towr simulate-pc-melee replay.json
```

Команды записи рассчитаны на PowerShell7. Ошибки входа дают JSON `dynamic_encounter_search_error` и exit2; сбой исполнения — exit3 без частичного результата; ошибки I/O — exit4. Диагностика идёт в stderr. Схемы [request](../../../src/towr/adapters/schemas/dynamic-encounter-request-v1.schema.json), [result](../../../src/towr/adapters/schemas/dynamic-encounter-result-v1.schema.json), [error](../../../src/towr/adapters/schemas/dynamic-encounter-error-v1.schema.json) разрешаются offline.

Authored Drained-on-hit допускается только явной альтернативой `search_space.abilities: [[], ["drained_on_hit"]]`; по умолчанию `[[]]`. Это разрешённый авторский компонент, не автоматическая выдача книжного таланта. Действующий owner учитывает фактическое попадание и независимый источник Conditions.

Это лучшие найденные приближения к целям при заданной тактике и бюджете. Длительность включает цензурированные round-limit/unsupported префиксы; проверки target tolerance и глобального оптимума нет. Если наблюдался unsupported, такой screening кандидат не проходит в validation; unsupported validation сохраняется в отчёте, но не в selected. Пустой selected — допустимый честный результат.

Python API: `towr.application.dynamic_encounter.DynamicEncounterRequest`, `NpcSearchSpace`, `search_dynamic_encounter`. Simulator можно передать явно; по умолчанию sequential aggregate. Предыдущий [Python-пример](search.py) также работает: он переиспользует партию из M10, отбрасывая прежних enemies. Новый JSON-вход полностью самостоятельный и такого scenario не требует. Расширять нужно составляемые компоненты и их prerequisites, а не список именных statblocks.
