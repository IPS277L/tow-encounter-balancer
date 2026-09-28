# Аудит готовности первого M5

Дата: 2026-09-28. На старте рабочее дерево чистое. Проверены public APIs, исходный план, ADR-0017/0018/0019 и существующие tests. В этом срезе добавлены runnable typed пример, сохранённый вывод и один subprocess integration test; production src не менялся.

**Четыре критерия M5 выполнены в ограниченном неподвижном ranged Minion-сценарии: ограничения кандидатов, явное окно, генерация конечной области и поэтапная оценка и выбор нескольких подходящих результатов.** Готовность относится к Python API и заданному резерву, а не к универсальному бою, PC-партии или подбору произвольных профилей.

## Матрица roadmap

| Критерий | Реализация | Проверка | Вывод |
| --- | --- | --- | --- |
| Ограничения кандидатов | [Generation models](../../src/towr/application/ranged_candidate_generation_models.py), [pure projection](../../src/towr/application/ranged_candidate_generation.py); неизменные definitions/state, group partition, count bounds, explicit family facts, max_candidates и staged budget | [10 model](../../tests/unit/test_m5_ranged_candidate_generation_models.py), [7 construction](../../tests/unit/test_m5_ranged_candidate_generation.py), [2 integration](../../tests/integration/test_m5_ranged_candidate_generation.py): отказ до materialization, все независимые порядки, полный source/result, повторное admission, ошибки/cause | Выполнено для count prefixes supplied резерва; выбор позиций/AI/статистик и клонирование сверх резерва отсутствуют |
| Конфигурируемое окно | [Assessment models](../../src/towr/balance/ranged_assessment_models.py) и [pure assessor](../../src/towr/balance/ranged_assessment.py); явные Fraction minimum/target/maximum | [9 unit](../../tests/unit/test_m5_ranged_assessment.py), [1 integration](../../tests/integration/test_m5_ranged_assessment.py): точные доли, все trials в знаменателе, включённые границы, unsupported=None, source/frozen guards | Выполнено для подтверждённой метрики цели за лимит; confidence policy и именованные пресеты не вводились |
| Этапный поиск и оценка | [Staged models](../../src/towr/balance/ranged_staged_evaluation_models.py), [continuation](../../src/towr/balance/ranged_staged_evaluation.py), [service](../../src/towr/application/ranged_staged_evaluation_service.py) поверх bounded evaluator | [14 model](../../tests/unit/test_m5_ranged_staged_evaluation.py), [7 service](../../tests/unit/test_m5_ranged_staged_evaluation_service.py), [2 integration](../../tests/integration/test_m5_ranged_staged_evaluation.py): все stage specs до RNG, full rerun budget, outside continuation/unsupported stop, точная chain, обе execution modes | Выполнено для сгенерированного либо supplied конечного списка; поколения новых candidates между этапами и prefix reuse отсутствуют |
| Несколько лучших кандидатов | [Bounded models](../../src/towr/balance/ranged_evaluation_models.py), [service](../../src/towr/application/ranged_evaluation_service.py); final-only window_match, Fraction distance, stable input tie-break, до top_k | [9 model](../../tests/unit/test_m5_ranged_evaluation.py), [5 service](../../tests/unit/test_m5_ranged_evaluation_service.py), [2 integration](../../tests/integration/test_m5_ranged_evaluation.py): полный report, exact ties, empty selection, source и failure boundaries | Выполнено; лучший результат только среди допущенных кандидатов последнего этапа, без гарантии глобального оптимума |

В M5 **69 тестов: 61 unit и 8 integration**, включая новый [запуск примера](../../tests/integration/test_m5_example.py). Aggregate-only M3 summary дополнительно покрыта [9 unit](../../tests/unit/test_m3_npc_ranged_summary.py) и [1 integration](../../tests/integration/test_m3_npc_ranged_summary.py); эти 10 не включены в число M5. Существующая регрессия также проверяет domain/engine/M4.

## Сквозной пример и источники

[Пример и команды](../examples/m5/README.md) не импортируют tests или benchmark harness. Вход: numeric Warbow/Protection/Resilience Brigand, fixed P1/P2, reserves A1/A2 и B1, counts 0..2 и 0..1, оба авторами заданные Minion-состава. Пять generated candidates поступают в настоящий staged service: seed 42, round budget 3, window [1/4,3/4], target 1/2, stages 8/3 и 32/2, max_trials 136. Process backend явно получает workers=2/batch_size=4. Скрипт имеет guarded main и проверен вне repository cwd с абсолютным PYTHONPATH к текущему src.

Sequential/process дают одинаковые отчёты после execution header. В сохранённом запуске actual_trials=136, final selected=(1,1),(2,0), objective rate каждого 13/32. Это наблюдения примера, не статистический критерий теста или новый preset. Все четыре outcomes отображаются отдельно; continuation не выдаётся за окончательный window match. [Вывод](../examples/m5/ranged_balance.output.txt).

Прямо перечитаны BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91; Understanding NPC Profiles, стр. 93; Brigands & Footpads / Brigand, стр. 97; BOOK-PLAYER-GUIDE 1.4, Rules / The Battlefield / Zones, Position, Range, стр. 114. Профили/полные GM-approved decisions переданы явно, граф не создаёт awareness/LOS, числовой фрагмент не объявляется полным NPC. Новых Rule IDs, house rules или вопросов к трактовке книги нет.

## Проверенные архитектурные границы

- Generation и application orchestration находятся снаружи balance/simulation. Balance получает вход и aggregates, не per-trial records/engine/JSON. Full compact result существует временно в bounded service до проекции; stage reports сохраняют inputs и summaries.
- Preflight считает число составов без Cartesian materialization и общий бюджет полных запусков до RNG. Generation result и staged result требуют полных exact sources, правильного порядка и допустимого завершения цепочки; они не доказывают истинность вручную заданных facts или происхождение агрегатов.
- Actor IDs/definitions/positions и полные decisions сохраняются; independently supplied actor/target orders не заменяются group order. Family-wide facts обязательны, подходят не все области поиска с контекстом, зависящим от численности.
- Shared stage guards и budget formula переиспользуются без нового RNG. Стандартный application путь использует прежний runner default; low-level injectable RNG и indexed seed scheme M3 сохранены.
- Ошибки generation/candidate/stage содержат локальные IDs и __cause__; partial complete results, retry/fallback отсутствуют. Unsupported observations — отдельная непригодная оценка, не exception или defeat. Interrupts не оборачиваются.

## Ограничения и продолжение

Не реализованы полноценная PC-группа, melee/движение в данном сценарии, полный NPC-каталог, универсальные эффекты и общий battle aggregate. Отдельные K1 primitives для этих механик не означают их включения в автономную симуляцию. В генераторе нет изменения характеристик/позиций/AI и перебора произвольных подмножеств одного размера; равные по статистикам составы не дедуплицируются.

Оценки являются наблюдаемыми долями цели в пределах round budget. Малый N, повтор seed prefixes между этапами и адаптивный отбор не дают confidence guarantee или независимость этапов. Все повторно исполненные trials входят в budget. Timeout, hard memory quota, streaming/checkpoint и performance benefit staged search этим аудитом не проверялись. Max_candidates ограничивает выходной список, но не байты исходного резерва; полный reserve и все reports хранятся в памяти.

Python 3.12 в среде отсутствует; Windows / CPython 3.14.5 проверен с текущим src через PYTHONPATH. Установленный wheel, другие ОС и huge inputs не проверялись заново. Скрипт примера не создаёт `towr balance` или JSON wire contract; его stdout не имеет гарантий доставки/версии M4.

Следующий законченный срез — отдельный ADR для **JSON balance v1 и CLI balance** поверх готовых generation/staged APIs: источник reserve и family facts, groups/count bounds, точное окно, seed/stages/бюджеты и execution options; source-bound aggregate-only output с полными stage reports; категории validation/generation/execution/I/O errors, request/candidate/stage IDs и exit codes. Определить переиспользование M4 scenario encoding без изменения simulation v1, правила версий и golden examples. Не добавлять новые метрики, presets или игровые механики. Реализация Schema/adapters/service/CLI должна следовать после этого контракта.

Итоговая проверка: **1919 tests OK**, Python 3.14.5, 72,765 с, включая настоящий spawn и запуск примера вне repo. Compileall (src/tests/tools/docs/examples/m5), pip check, локальные ссылки и git diff --check успешны. Ни production src, ни pyproject.toml не менялись; commit/push не выполнялись.
