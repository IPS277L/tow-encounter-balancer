# Пример первого M5: генерация и поэтапная оценка

[ranged_balance.py](ranged_balance.py) строит typed input через публичные domain/application модели, генерирует пять составов и вызывает существующий staged evaluator. Импортов tests, benchmark harness или private API нет. Это исполняемый пример Python API; приложение также поддерживает [JSON/CLI balance](json/README.md).

## Запуск

Из корня репозитория, после подготовки окружения по [README](../../../README.md):

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m5/ranged_balance.py --mode sequential
.venv/Scripts/python.exe docs/examples/m5/ranged_balance.py --mode process
```

Без аргументов выбирается sequential. Process явно использует workers=2, batch_size=4; protected main допускает Windows spawn. Остальные параметры фиксированы в `build_request()`, автоматического подбора режима нет. Для вызова из другого cwd нужно задать абсолютный PYTHONPATH к src и путь к скрипту. Этот срез проверен с исходным кодом через PYTHONPATH, а не с переустановленным wheel.

## Вход и источники

Обе стороны используют числовой фрагмент Brigand: Shooting 3d/3, Damage 3, Warbow Medium–Long/2H, Athletics Protection 3d/2, Resilience 4 (Toughness 3 + armour 1). Источник напрямую проверен: **BOOK-GM-GUIDE 1.1, Allies and Antagonists / Brigands & Footpads / Brigand, стр. 97**. Отдельный melee Attack и применимый только к Melee Craven Opportunist не используются в этом неподвижном ranged-сценарии. Пример не объявляет поддержку всего профиля/каталога NPC.

P1,P2 фиксированы на perspective_side=PLAYERS_AND_ALLIES; они остаются Minions, а не персонажами игроков. Противоположная сторона состоит из резервов A=(A1,A2), count 0..2 и B=(B1), count 0..1. Группы используют одинаковые definitions, но разные actor IDs. Перебор сохраняет пять ненулевых count vectors: (0,1), (1,0), (1,1), (2,0), (2,1); одинаковая статистика не объединяет разные составы.

В исходном коде явно заданы порядок ходов, приоритеты всех целей и GM-approved KNOCKED_OUT для каждой attacker/target пары. Это выбранные автором примера решения, а не автоматически найденное согласие ведущего. **BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91** определяет поражение после Wound и выбор disposition с учётом решения GM; **Understanding NPC Profiles, стр. 93** не даёт NPC всех свойств PC-оружия по имени.

Две соседние Zones, Medium для всех вражеских пар, awareness, clear LOS, отсутствие врага в Close, неподвижность, отсутствие дополнительных применимых правил, неизменённые Tests и достаточные боеприпасы утверждены для **всех составов** на весь round budget=3. В шаблоне и family input facts передаются явно. Граф сам этого не доказывает: **BOOK-PLAYER-GUIDE 1.4, Rules / The Battlefield / Zones, Position, Range, стр. 114**. Повторный Staggered разрешается заданным SUFFER_WOUND по существующему [контракту сценария](../../decisions/ADR-0013-ranged-minion-scenario-input.md).

| Параметр | Значение |
| --- | --- |
| master_seed | 42, seed scheme towr:npc-ranged-trial:v1 |
| Objective | Поражение всех противников perspective_side в пределах 3 раундов |
| Явное окно | [1/4, 3/4], target=1/2, точные Fraction; это параметры примера, не preset |
| Этапы | 8 trials / keep 3; затем 32 trials / keep 2 |
| Кандидаты | 5, max_candidates=5 |
| Верхний бюджет | 5×8 + 3×32 = 136, max_total_trials=136 |

Второй этап повторяет полный пакет с теми же indexed seeds начиная с 0; это 136 исполненных trials, без reuse prefix. Доли разных этапов не складываются в новую оценку.

## Чтение отчёта

[Сохранённый stdout](ranged_balance.output.txt) получен на CPython 3.14.5. Sequential и process дают одинаковую часть отчёта после строки execution. Сам отчёт — текст примера, не версионированный wire protocol. Он показывает параметры, все оценки каждого выполненного этапа, четыре отдельных outcome counts, точную долю цели, попадание в окно, continuation, итоговый status/selected и фактический бюджет.

На проверенном запуске первые два кандидата имеют rate=1 и не попадают в окно. Один из них проходит промежуточный отбор на уточнение; `continue` не означает окончательную пригодность. На последнем этапе составы (1,1) и (2,0) получают по 13/32 достижения цели и выбираются оба. Их наблюдения равны при этом вводе, а равенство ranking сохраняет исходный порядок; это разные count vectors/actor IDs.

`round_limit` входит в общий знаменатель и остаётся отдельным исходом. При `unsupported_path > 0` оценка непригодна, window отображается как unsupported; такой кандидат не продолжается и не выбирается. Пустой final_selected допустим и не заменяется ближайшим outside-window кандидатом. При отказе построения или исполнения скрипт завершается с исключением до вывода полного отчёта; нового протокола errors/exit codes M4 он не задаёт.

Эти малые пакеты демонстрируют воспроизводимость и контракты, а не точность оценки сложности. Сохранённые числа не являются вероятностью победы полной группы PC или гарантией будущего результата. Полный replay требует прежних inputs, code/rules, RNG и runtime. Изменение seed не меняет область генерации, но может изменить наблюдения и отбор.

[Интеграционный тест](../../../tests/integration/test_m5_example.py) запускает сам скрипт в двух режимах из временного cwd и сравнивает отчёты. Он проверяет бюджет и завершение, не фиксируя конкретную вероятность или selected IDs. [Аудит M5](../../audits/m5-readiness.md) описывает проверенные критерии и оставшиеся ограничения.

Внешний JSON-формат закреплён в [ADR-0020](../../decisions/ADR-0020-ranged-balance-json-v1.md); [JSON-образцы](json/README.md) используют тот же резерв и stages. Schema, parser/result/error encoders, application service и CLI balance реализованы.
