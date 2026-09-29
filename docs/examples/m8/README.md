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

Следующий шаг — отдельный книжный контракт magic encounter: Champion injury, action dispatch, Broken turns и обязательные Miscast continuations. Полноценная магия в боевой симуляции пока не реализована.
