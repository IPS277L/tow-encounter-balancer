# Аудит оценки Melee-кандидатов M6

Дата: 2026-09-29. Проверены [ADR-0024](../decisions/ADR-0024-melee-candidate-assessment.md), production models/service и тесты. На старте 17 dirty/untracked файлов; существующая работа сохранена. Этот срез добавляет документацию и исполняемый пример, production src/tests не меняются.

**Оценка явного конечного списка Melee-кандидатов готова в границе ADR-0021/0024.** Pure assessment, полный бюджет, выбор внутри окна, sequential/process orchestration и ошибки согласованы. Генератор составов, поэтапное уточнение и внешние Melee-форматы этим выводом не закрываются.

## Матрица готовности

| Обязанность | Реализация и проверка |
| --- | --- |
| Допущенный вход | [List models](../../src/towr/balance/melee_evaluation_models.py): frozen typed Melee candidates, tuple copy, непустые точные уникальные IDs, общий perspective/round budget. [10 model tests](../../tests/unit/test_m6_melee_evaluation.py) проверяют отказ ranged, bool/coercion, несовпадающие параметры и rebuild derived simulation requests |
| Бюджет до исполнения | Общий uint64 seed/trials проходит existing simulation request; positive exact int max_total_trials/top_k. Полный C×N проверяется до runner/RNG/pool. Список не сокращается; max_total_trials не является квотой памяти |
| Pure assessment | [Assessment](../../src/towr/balance/melee_assessment.py) и [модель](../../src/towr/balance/melee_assessment_models.py) принимают только input/aggregate summary с равным полным source. [9 unit tests](../../tests/unit/test_m6_melee_assessment.py): чужие seed/trials/scenario, равная копия, frozen fields, отсутствие RNG/runner/full records |
| Метрика и окно | Четыре Fraction count/N, N включает все trials. ROUND_LIMIT не становится поражением; unsupported > 0 даёт window_match=None. ELIGIBLE не означает попадание в окно. Общий ObjectiveRateWindow сохраняет class identity/import/pickle path; inclusive/point windows и большие N без float проверены |
| Отбор и полнота | Result требует все rows в исходном порядке с точными ID/source/window. Selected — только window_match=True, stable sort по Fraction distance к target, затем top_k; равенство сохраняет входной порядок. Outside/unsupported остаются в отчёте, пустой выбор без nearest fallback; model tests проверяют partial/foreign/reordered rows |
| Исполнение | [Service](../../src/towr/application/melee_evaluation_service.py): typed request/options до runner, ровно один полный run на кандидата, выбранные existing sequential/process APIs, точные workers/batch_size. Typed result/source проверяются до projection. [8 service tests](../../tests/unit/test_m6_melee_evaluation_service.py) проверяют порядок, options и освобождение предыдущего full result через weak references |
| Ошибки | [MeleeBalanceEvaluationError](../../src/towr/application/melee_evaluation_errors.py) сохраняет candidate_id и исходные cause/worker notes. Нет partial success/retry/fallback. Проверены runner, projector/assessment/row failures, остановка после первого успешного кандидата, BaseException passthrough. Preflight и финальная ошибка report не получают вымышленный candidate ID; traceback может удерживать объекты |
| Реальные backend | [1 assessment integration test](../../tests/integration/test_m6_melee_assessment.py) с заданными d10 проверяет exact shares; [2 evaluation integration tests](../../tests/integration/test_m6_melee_evaluation.py) — равные reports/selected IDs, rename/reorder invariance, input/global RNG, cleanup и pool startup error. Process использует прежнюю отдельную seed scheme, candidate ID/порядок в seed не входят |
| Архитектурная граница | Domain/engine/simulation не импортируют Melee balance/application. Balance получает только input/summary; application отвечает за запуск и projection. Режимы/окно переиспользованы, ranged wire/API не менялись. Generic scheduler, auto backend и общий battle aggregate не добавлены |

В срезе ADR-0024 — **30 тестов**: 9 assessment unit + 1 integration, 10 model, 8 service + 2 integration. Ошибки/unsupported/ties проверяются заданными наблюдениями; реальные Monte Carlo тесты не требуют заранее выбранного процента или победителя. Ранее проверенные engine/simulation boundaries описаны в [аудите одиночного сценария](m6-readiness.md) и [аудите массовых прогонов](m6-simulation-readiness.md).

## Самостоятельный пример

[melee_evaluation.py](../examples/m6/melee_evaluation.py) использует public APIs и соседний builder [melee_scenario.py](../examples/m6/melee_scenario.py), без tests/private imports. Вход — два явно заданных состава Footpad 2×1 и 2×2, seed 42, три раунда, по 16 trials, общий бюджет 32 на вызов, окно [1/4,1/2,3/4], top_k=1. Для 2×1 заново согласованы roster, combat/spatial snapshots, target priorities, defeat decisions и цель E1. Сценарий не моделирует удаление участника во время боя; это отдельный исходный состав. Facts и GM approvals явно применимы к обоим примерам, автоматического вывода из Zone нет.

Скрипт выполняет два полных вызова evaluator (всего 64 trials), сравнивает **полные** reports и selected IDs, проверяет исходный input/global RNG и отсутствие дочерних процессов после завершения. [Сохранённый вывод](../examples/m6/melee_evaluation.output.txt) относится к Windows/Python 3.14.5: 2×1 дал 16/16 достижения цели и остался вне окна; 2×2 дал 10/16 и выбран. Это наблюдение конкретного seed/runtime и малого пакета, не preset, гарантия истинной вероятности или нормативный результат. Четыре исхода и обе строки видимы в отчёте. Скрипт не фиксирует ожидаемый winner/rate в assertions; ошибка candidate выводится с причиной и пробрасывается с ненулевым exit code.

## Книжная проверка и ограничения

Непосредственно перечитаны локальные извлечённые страницы:

- BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112: ход/раунд; visited round не обязательно завершён.
- BOOK-PLAYER-GUIDE 1.4, Rules / The Battlefield, стр. 114: одна Zone сама по себе не задаёт Close.
- BOOK-PLAYER-GUIDE 1.4, Rules / Attack Modifiers, стр. 118–119: численное преимущество по всей Zone, исключение defeated/Defenceless/non-combatants и +1d.
- BOOK-PLAYER-GUIDE 1.4, Rules / Conditions / Staggered, стр. 123: SUFFER_WOUND — явно выбранный допустимый вариант повторного Staggered.
- BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91, и Brigands & Footpads / Footpad, стр. 97: defeat после Wound, disposition с решением GM; Dagger 3d/3 Dam2, Athletics 3d/3, RES3, Lurker вне боя.

Новых правил, house rules или противоречий нет. Окно/бюджет/top_k — продуктовый контракт. Вывод ограничен неподвижными numeric Minions с явными Close/awareness/facts и фиксированными решениями. PC, движение, Charge/Brawn, mixed battle, новые Abilities и полный бой не поддерживаются этим evaluator. Агрегаты вручную можно построить через public constructors: source guards проверяют согласованность, а не доказательство исполнения. Совпадение seed между составами не обещает сопоставимых бросков действий или статистического уменьшения ошибки.

## Проверки и следующий шаг

Полная регрессия: **2104 tests OK (139,947 с)**, Windows/Python 3.14.5. AST-проверка импортов подтвердила границы domain/engine/simulation. Отдельный injected failure проверил error path примера: точный candidate ID/cause/notes, проброс исключения, один вызов runner и отсутствие partial selection. Compileall, 1181 локальный Markdown-путь и git diff --check успешны. Команды — в [статусе проекта](../project-status.md#последняя-проверка). Пример проверен обоими backend, полный отчёт и выбранные IDs совпали. Python 3.12/другие ОС, wheel и повторные benchmark не входят в этот аудит; старые performance-замеры не объявляются замерами текущего дерева. Commit/push не выполняются.

Следующий законченный шаг — подготовить контракт поэтапной оценки **явного Melee-списка** по образцу [ADR-0018](../decisions/ADR-0018-staged-ranged-evaluation.md): отдельные typed stages/request/result, верхний бюджет полных повторных пакетов, промежуточный отбор, exact source/report chain и stage/candidate error context. Сначала определить матрицу и конечные примеры; реализация отдельным срезом. Метрика/окно прежние, prefix reuse, генератор, CLI/JSON и игровые расширения не включаются автоматически.

Продолжение, 2026-09-29: [ADR-0025](../decisions/ADR-0025-staged-melee-evaluation.md) подготовлен; [finite probe](../examples/m6/staged_contract_probe.py) проверяет синтетическую арифметику и existing bounded reports без исполнения боя. Следующий срез — pure continuation helper и frozen stage/request/result/status; затем application service. Вывод этого аудита относится к ADR-0024 и не объявляет staged API реализованным.

Продолжение реализации ADR-0025, 2026-09-29: pure helper и frozen staged models готовы, 17 новых deterministic tests. Это слой input/aggregate chain, не исполнение этапов; следующим срезом остаются application service/error. Аудит ADR-0024 и его исходные результаты сохранены.

Продолжение ADR-0025, 2026-09-29: staged application service/error реализованы, добавлены 9 unit + 2 real sequential/spawn integration tests. Результаты этого аудита по ADR-0024 сохранены; следующий шаг — отдельный аудит staged evaluation и самостоятельный пример.
