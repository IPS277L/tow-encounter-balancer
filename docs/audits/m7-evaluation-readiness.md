# M7: аудит оценки явного mixed-списка

Дата: 2026-09-29. Основание — [ADR-0031](../decisions/ADR-0031-mixed-candidate-assessment.md). Аудит сопоставляет реализованный контракт с тестами и самостоятельным примером; production src/tests/tools в этом срезе не менялись.

**Оценка конечного списка mixed-кандидатов готова в границе неподвижных numeric Minions по ADR-0028/0031.** Вход задаёт каждый сценарий, факты и решения GM целиком. Генерация составов, поэтапное уточнение и mixed JSON/CLI остаются отдельными задачами.

## Матрица готовности

| Обязанность | Реализация и проверка |
| --- | --- |
| Pure assessment | [Модель](../../src/towr/balance/mixed_assessment_models.py), [helper](../../src/towr/balance/mixed_assessment.py), [9 unit tests](../../tests/unit/test_m7_mixed_assessment.py): typed mixed input/summary, равенство полного source, отказ ranged/Melee/full result, frozen/replace guards, равная копия допустима. Не исполняет RNG/runner/pool и не хранит records/journals |
| Метрика и окно | Четыре Fraction count/N, включая round_limit и unsupported. Inclusive/point window; unsupported > 0 даёт UNSUPPORTED_OBSERVATIONS и window_match=None независимо от goal rate. ELIGIBLE не означает попадание в окно. Общий ObjectiveRateWindow сохраняет class/import/pickle identity; большие N не округляются к float |
| Полный вход и бюджет | [List models](../../src/towr/balance/mixed_evaluation_models.py), [11 tests](../../tests/unit/test_m7_mixed_evaluation.py): finite tuple copies, точные уникальные IDs, mixed types, общий perspective/round budget, uint64 seed/trials. Positive exact int max_total_trials/top_k, без bool/coercion. Полный C×N проверяется до исполнения; replace пересобирает simulation_requests |
| Отчёт и выбор | Все строки ровно один раз в исходном порядке; полный source/window каждой строки. Только window_match=True, stable Fraction distance к target и top_k. Точное равенство сохраняет порядок; outside/unsupported остаются в отчёте, пустой выбор допустим без nearest fallback. Проверены foreign pairs/GM approvals/escape facts, partial/reordered rows, N=2**60+1 |
| Application | [Service](../../src/towr/application/mixed_evaluation_service.py), [8 tests](../../tests/unit/test_m7_mixed_evaluation_service.py): request/options до runner, один полный existing run на кандидата, явные backend/workers/batch_size, typed result и полный source до projection. Parent request сохраняется; предыдущий full result освобождается перед следующим run, проверено weakref |
| Ошибки | [MixedBalanceEvaluationError](../../src/towr/application/mixed_evaluation_errors.py): candidate_id и исходный cause/notes, без partial/retry/fallback. Проверены сбой второго кандидата без третьего, projection/assessment/row errors, прямой проброс BaseException и preflight/final report errors. Traceback может удерживать объекты; лимит trials не является квотой памяти |
| Реальные backend | [Assessment integration](../../tests/integration/test_m7_mixed_assessment.py) и [3 evaluation integration tests](../../tests/integration/test_m7_mixed_evaluation.py): sequential/spawn, source/global RNG/cleanup, replay/reorder/rename, pool startup failure. Заданные d10 дают все четыре исхода 1/1/1/1 и 17 Attack/6 visited; goal=1/4 внутри point window не позволяет выбрать unsupported-кандидата. Supported prefix отдельно проверен |
| Слои | Balance получает input/aggregate summary; application запускает existing simulation и проецирует результат. Domain/engine/rules/simulation не зависят от balance/application. Execution options и окно переиспользуются без переноса; старые ranged/Melee APIs и wire formats сохранены. Generic scheduler, auto backend и общий battle aggregate отсутствуют |

В контракте **32 теста**: 9 assessment unit + 1 integration, 11 list models, 8 service + 3 integration. Ошибки, unsupported и ranking проверены детерминированно; Monte Carlo процент или победитель не закреплены в assertions. Предыдущие границы — [одиночный mixed-сценарий](m7-readiness.md) и [массовые прогоны](m7-mass-simulation-readiness.md).

## Самостоятельный пример

[mixed_evaluation.py](../examples/m7/mixed_evaluation.py) использует public APIs и соседний [builder](../examples/m7/mixed_scenario.py), без tests/private imports. Явные альтернативы: 3×2 с одним лучником и 2×2 с двумя; numeric Footpad Dagger / Brigand Warbow, фиксированные позиции, оружие и приоритеты целей. Все участники — Minions, в том числе сторона players_and_allies. Pair ranges, awareness, разрешение обычного outnumbering и knockout с GM approval заданы для каждого исходного сценария. Brigand не использует Axe/Craven Opportunist; Lurker Footpad относится к действиям вне боя.

Seed 42, два раунда, по 8 trials, planned/max_total_trials=16 на один вызов, окно [1/4,1/2,3/4], top_k=1. Скрипт выполняет sequential и process workers=2/batch_size=3: **32 trials всего**, сравнивает полные reports/selected IDs, source identity, planned/actual, input/global RNG и отсутствие оставшихся дочерних процессов. Печать отчёта начинается только после двух успешных вызовов и проверок. [Сохранённый вывод](../examples/m7/mixed_evaluation.output.txt) — наблюдение на текущем runtime, не эталон вероятности или ожидаемого победителя.

Два запуска из корня и отдельного временного cwd с абсолютным PYTHONPATH дали одинаковый stdout и пустой stderr: суммарно 64 trials. Дополнительно проверен entry point с ошибкой второго кандидата после 8 реальных trials первого: точный candidate_id, тот же cause и notes, исключение проброшено, stdout пуст, сообщение ошибки идёт в stderr. Process после сбоя не запускался; fallback/partial result нет, глобальный RNG и дочерние процессы сохранены.

## Книги и ограничения

Прямо перечитаны локальные извлечённые страницы:

- BOOK-PLAYER-GUIDE 1.4, Equipment / Ranged Weapons, стр. 94; Rules / Combat, стр. 112; The Battlefield, стр. 114; Attack Tests / Attack Modifiers, стр. 118–119; Conditions / Staggered, стр. 123.
- BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91; Understanding NPC Profiles, стр. 93; Brigands & Footpads, стр. 97.

RULE-COMBAT-001/009 и RULE-NPC-002 сохранены. Окно, бюджет и ranking — технический контракт; новых правил/house rules нет. Visited round не обязательно завершён; defeat не означает обязательную смерть. Нет доступной цели при фиксированных оружии/позициях — технический unsupported_path, не игровой исход. Даже отсутствие unsupported в выборке не доказывает полноту симуляции или статистическую точность. Равные seeds разных составов не гарантируют сопоставимых бросков отдельных действий. Source guards подтверждают согласованность вручную созданных aggregates, а не доказывают их происхождение.

Движение, смена оружия, автоматические awareness/GM approvals, PC, магия и полный каталог способностей не входят в эту оценку. Performance не менялся и повторно не измерялся; прежние benchmark не объявляются замерами текущего evaluator. Python 3.12/другие ОС и installed wheel в этом аудите не проверялись.

## Итоговая проверка

Windows / Python 3.14.5: **2446 tests OK (302,736 с)**, включая real spawn/ranged/Melee/CLI. Compileall src/tests/tools/docs/examples/m7, 1910 локальных Markdown-путей, AST import boundaries и diff/whitespace успешны. Лог полного набора: build/m7-evaluation-audit-tests.log (ignored). Все 17 исходных dirty/untracked файлов сохранены; добавлены этот аудит, пример и его вывод, обновлена документация. Новых unittest tests нет, src/tests/tools не менялись. Commit/push не выполнялись.

## Следующий шаг

Подготовить отдельный контракт поэтапной оценки **явного mixed-списка** по образцу [ADR-0025](../decisions/ADR-0025-staged-melee-evaluation.md): typed stages/request/result/status, верхний бюджет полных повторных пакетов, отдельный промежуточный отбор и final selection, exact source/report chain и stage/candidate error context. Сначала ADR, матрица проверок и конечный probe; реализация — следующим срезом. Метрика/окно прежние; prefix reuse, генерация, JSON/CLI и новые игровые действия не добавляются.

Продолжение, 2026-09-29: [ADR-0032](../decisions/ADR-0032-staged-mixed-evaluation.md) и [конечный probe](../examples/m7/staged_contract_probe.py) подготовлены. Pure helper и frozen staged models реализованы с 19 deterministic tests. Application staged service/error реализованы, [отдельный staged аудит](m7-staged-evaluation-readiness.md) завершён; следующий контракт — генерация mixed-составов. Вывод этого аудита по ADR-0031 сохранён.
