# Аудит поэтапной Melee-оценки M6

Дата: 2026-09-29. Проверены [ADR-0025](../decisions/ADR-0025-staged-melee-evaluation.md), production helper/models/service и тесты. Рабочее дерево на старте чистое. В этом срезе добавлены аудит, самостоятельный пример и его вывод; production src/tests не меняются.

**Поэтапная оценка явного Melee-списка готова в границе ADR-0021/0025.** Upper budget, промежуточный отбор, итоговое окно, source chain и обработка ошибок согласованы. Слой bounded evaluation отдельно закрыт [аудитом ADR-0024](m6-evaluation-readiness.md). Вывод не включает генерацию составов, Melee CLI/JSON или расширение игровых механик.

## Матрица готовности

| Обязанность | Реализация и свидетельство |
| --- | --- |
| Typed immutable input | [Модели](../../src/towr/balance/melee_staged_evaluation_models.py): отдельные Melee stage/request/result/status, tuple copies, frozen/slots/replace. [17 model/helper tests](../../tests/unit/test_m6_melee_staged_evaluation.py) проверяют uint64 trials/seed, positive exact keep/budget без bool/coercion, все stages до исполнения, strictly increasing trials и отказ ranged |
| Верхний бюджет | U[0]=N, U[i+1]=min(U[i],keep[i]), planned=sum(U[i]×trials[i]). Проверяется до runner/RNG/pool; keep может расти, но отсеянные не возвращаются. Проверены 240/140/40, один/три этапа, max=239 вместо 240 отклоняется. Нет автоматического урезания |
| Промежуточный отбор | [Helper](../../src/towr/balance/melee_staged_evaluation.py) исключает unsupported, допускает outside-window/round_limit, выбирает по точному Fraction distance и stable ties, возвращает исходный порядок. Тесты различают continuation и локальные selected, включая пустые selected с непустым continuation и большой N без float rounding |
| Итог и остановка | NO_ELIGIBLE_CANDIDATES только при пустом continuation до последнего этапа, итог пуст. Последний report даёт COMPLETED даже при all-unsupported; selected только из него. Проверены early stop после ранних попаданий, reduced budget, пустой финальный выбор и отсутствие nearest fallback |
| Source/report chain | Общая `_stage_request` задаёт exact local budget, trials, keep/top_k, seed/window и исходную подпоследовательность. Result сверяет полные значения source каждого report; проверены foreign/partial/extra/reordered/wrong continuation, равная копия source, replace и производные поля. Successful result не хранит trial records/RNG/options |
| Исполнение и seeds | [Service](../../src/towr/application/melee_staged_evaluation_service.py) вызывает existing bounded evaluator один раз на достигнутый этап с тем же execution. [9 service tests](../../tests/unit/test_m6_melee_staged_evaluation_service.py) проверяют точные requests/options, index 0 и полные повторные пакеты обоих backend. Seed scheme прежняя, candidate/stage ID в неё не входят |
| Ошибки | [MeleeStagedEvaluationError](../../src/towr/application/melee_staged_evaluation_errors.py) сохраняет stage index с нуля, известный candidate ID и полную cause/notes chain. Ошибка второго этапа останавливает трёхэтапный запрос. Проверены foreign/untyped/ranged reports до следующего вызова, сборка stage/continuation, unknown candidate=None, preflight/final constructor напрямую и BaseException passthrough; partial/retry/fallback нет |
| Реальные процессы | [2 integration tests](../../tests/integration/test_m6_melee_staged_evaluation.py): полные sequential/spawn reports и selected равны, parent input/global RNG неизменны, дети завершены, pool startup failure сохраняет цепочку причин. Rename сохраняет observations; reorder проверен при сохранении обоих candidates первым этапом, намеренный tie-break от порядка не отменяется |
| Архитектура | AST-проверка не обнаружила импортов balance/application из domain/engine/simulation. Application запускает существующий bounded API, pure balance работает с input/aggregates. Shared window/options сохранены; новых runner/pools, generic scheduler и wire format нет |

Матрица опирается на **28 тестов ADR-0025**: 17 model/helper + 9 service + 2 integration. Синтетические наблюдения покрывают редкие остановки/ties/unsupported; реальные Monte Carlo тесты не требуют конкретного процента или победителя. Guards проверяют согласованность ручных агрегатов, а не доказательство их происхождения. Исключение может удерживать traceback/промежуточные объекты; отсутствие full records относится к успешному отчёту.

## Самостоятельный пример

[melee_staged_evaluation.py](../examples/m6/melee_staged_evaluation.py) использует public staged API и прежние builders/printer из [melee_evaluation.py](../examples/m6/melee_evaluation.py), без tests/private imports. Явные Footpad-составы 2×1 и 2×2, seed 42, три раунда, окно [1/4,1/2,3/4]. Stages=(8 trials,keep=1),(32 trials,keep=1), upper budget=2×8+1×32=48. Facts/GM approvals заданы для каждого состава, генерации или автоматического вывода Close/awareness нет.

Скрипт сравнивает полные sequential/process results и selected IDs, сохраняет parent source, проверяет input/global RNG и cleanup. Вывод включает все строки каждого report, четыре counts/rates, local selected, отдельный continuation, final status/selected и planned/actual budget. При ошибке печатает stage/candidate/cause и пробрасывает исключение с ненулевым exit code. Отдельная инъекция ошибки после двух реальных прогонов первого этапа подтвердила stage_index=1, сохранение bounded → root cause/notes, отсутствие partial report и запуска process после сбоя.

[Сохранённый вывод](../examples/m6/melee_staged_evaluation.output.txt), Windows/Python 3.14.5: в первом этапе 2×1 дал 8/8 цели и оказался вне окна, 2×2 дал 5/8 и прошёл на уточнение; в финале 2×2 дал 17/32 и выбран. Actual=48 на вызов, оба режима вместе выполняют 96 trials. Это наблюдение конкретного seed/runtime, не preset или гарантия вероятности; в assertions нет заранее заданной доли/победителя.

32 финальных trial исполняются целиком с index 0. Их первые 8 повторяются; бюджет одного вызова 48, а не 40. Counts этапов не складываются для новой финальной доли, оценки этапов не считаются независимыми выборками. У разных составов общий seed не обещает одинаковых бросков соответствующих действий. Prefix reuse и оценка performance gain не заявляются.

## Книги и ограничения

Непосредственно перечитаны локальные извлечённые страницы BOOK-PLAYER-GUIDE 1.4: Rules / Combat, стр. 112; The Battlefield / Range, стр. 114; Attack Modifiers, стр. 118; Conditions / Staggered, стр. 123. BOOK-GM-GUIDE 1.1: Allies and Antagonists / Minions, стр. 91; Brigands & Footpads / Footpad, стр. 97. Сохраняются порядок ходов/раундов, явный Close, динамический обычный outnumbering по Zone, выбранный SUFFER_WOUND, defeat/disposition и numeric Footpad. Lurker применяется вне боя, пример начинает бой с осведомлёнными участниками. Новых игровых правил/house rules/противоречий нет.

Готовность ограничена неподвижными numeric Minions с фиксированными явными facts/policies. PC, движение/Charge/Brawn, mixed battle и новые Abilities не включены. Окно/keep/trials — явные продуктовые параметры; confidence policy и пресеты сложности отсутствуют. Генерация численности и перенос общих фактов на семейство сценариев требуют отдельного контракта.

## Проверки и следующий шаг

Полная регрессия: **2132 tests OK (136,244 с)**, Windows/Python 3.14.5. Compileall, 1265 локальных Markdown-путей и git diff --check успешны. Актуальные команды — в [project-status.md](../project-status.md#последняя-проверка). Пример и его обработка ошибки проверены; production src/tests не менялись. Python 3.12/другие ОС, wheel и повторные benchmarks не входят в этот аудит. Прежние замеры не объявляются результатами текущего дерева. Commit/push не выполнялись.

Следующий законченный шаг — подготовить контракт ограниченной генерации **Melee-составов по явно заданному резерву** по образцу [ADR-0019](../decisions/ADR-0019-ranged-composition-generation.md). Зафиксировать неизменную perspective-сторону, группы/диапазоны численности, сохранение numeric profiles/GM policies, полную область применимости facts (особенно Close и всех combatants Zone), перестроение roster/combat/spatial/targets/defeat decisions/objective, детерминированные IDs/порядок и preflight max_candidates/полного staged budget. Проверить допустимые и отклоняемые конечные примеры. Сначала контракт и матрица, реализация отдельно; не добавлять автоматические facts/GM approvals, новые Abilities, prefix reuse или CLI/JSON.

Продолжение 2026-09-29: [ADR-0026](../decisions/ADR-0026-melee-composition-generation.md) подготовлен, конечный constructor probe проверен. Group/request preflight реализован и проверен отдельно; construction/result/error также реализованы. Integration генерация → staged evaluation проверена отдельными tests. [Аудит генерации](m6-generation-readiness.md) и самостоятельный пример завершены. [Контракт JSON/CLI ADR-0027](../decisions/ADR-0027-melee-json-cli-v1.md) подготовлен; следующий срез — simulation Schema/command и pure adapters; вывод данного аудита относится к staged API.
