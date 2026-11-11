# Динамический генератор: первый сквозной срез

Генератор сам создаёт NPC, варьируя WS/Strength/Toughness/Agility, Melee/Athletics, Staff/Dagger и Light Armour. Число врагов может быть фиксированным: поиск всё равно меняет их параметры и экипировку. Готовый reserve и книжные NPC не нужны. [Контракт и ограничения](../../decisions/ADR-0113-dynamic-npc-generation-and-adaptive-search.md).

Запуск из корня репозитория:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe docs/examples/dynamic/search.py --candidates 12 --trials 16 --finalist-trials 64 --top 3 --min-npcs 2 --max-npcs 2 --target-win-rate 0.6 --target-rounds 3 > generated.json
```

Пример повторно использует только партию PC, day и arena facts из M10. Все enemies прежнего файла отбрасываются. `--party-from` позволяет использовать свой существующий melee input; Python API принимает непосредственно tuple PC participants и факты, без scenario/reserve. Наибольшая стоимость команды —384trials; меньше, если поиск не набрал уникальных кандидатов или все наблюдения unsupported. Для короткой проверки использовать `--candidates 3 --trials 2 --finalist-trials 3 --top 2 --max-rounds 3` (12trials максимум).

`--allow-authored-drained` явно допускает дополнительный компонент Drained-on-hit. Это authoring permission для этого пространства, не выдача книжного таланта любому NPC; по умолчанию выключено. Действующий owner учитывает фактическое попадание и независимый источник Conditions.

Выход содержит search space, фактическую стоимость, screening и отдельные validation observations. `selected` ссылается только на independently validated кандидатов без observed unsupported. Каждый кандидат содержит исходные NPC компоненты, win rate/Wilson95, mean started rounds/Hoeffding95, все outcome counts и `replay` — полноценный текущий PC simulation JSON1. Сохранённый replay можно передать `towr simulate-pc-melee`. Одинаковые вход/seed воспроизводят предложения и результаты; повторный запуск validation replay воспроизводит именно эту выборку.

Это лучшие найденные приближения к целям при заданной тактике и бюджете. Длительность включает цензурированные round-limit/unsupported префиксы; проверки target tolerance и глобального оптимума нет. Малое число trials годится для smoke, но даёт широкие интервалы. Если наблюдался unsupported, такой screening кандидат не проходит в validation; unsupported validation сохраняется в отчёте, но не в selected. Пустой selected — допустимый честный результат.

Python API: `towr.application.dynamic_encounter.DynamicEncounterRequest`, `NpcSearchSpace`, `search_dynamic_encounter`. Допустимые значения каждого параметра задаются tuple; `abilities` содержит альтернативные наборы typed `GeneratedAbility`. Simulator можно передать явно для другого существующего backend; по умолчанию используется sequential aggregate. Нет нового wire format/установленной CLI-команды генератора. Текущий набор намеренно мал; расширять нужно компоненты генерации и их prerequisites, а не список именных statblocks.
