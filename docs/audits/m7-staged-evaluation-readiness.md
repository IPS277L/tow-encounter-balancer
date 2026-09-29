# M7: аудит поэтапной mixed-оценки

Дата: 2026-09-29. Проверены [ADR-0032](../decisions/ADR-0032-staged-mixed-evaluation.md), helper/models/service/error, 31 тест и самостоятельный пример. Существующие изменения сохранены; production src/tests/tools в этом срезе не менялись.

**Поэтапная оценка явного mixed-списка готова в границе неподвижных numeric Minions ADR-0028/0032.** Верхний бюджет, промежуточный отбор, итоговое окно, цепочка источников и ошибки согласованы. Базовый evaluator отдельно закрыт [аудитом ADR-0031](m7-evaluation-readiness.md). Генерация составов и mixed JSON/CLI этим выводом не закрываются.

## Матрица готовности

| Обязанность | Реализация и проверка |
| --- | --- |
| Typed input | [Models](../../src/towr/balance/mixed_staged_evaluation_models.py), [19 tests](../../tests/unit/test_m7_mixed_staged_evaluation.py): отдельные frozen/slotted stages/request/result/status, tuple copies/replace, uint64 seed/trials, positive exact keep/budget без bool/coercion. Все stages проверяются заранее, trials строго растут; ranged/Melee families отклоняются, shared window/class/pickle identities сохраняются |
| Верхний бюджет | U[0]=N, U[i+1]=min(U[i],keep[i]), planned=sum(U[i]×trials[i]) до runner/RNG/pool. Проверены один/три этапа, 240/140/40/1140, max=239 вместо 240 отклоняется. Рост keep не возвращает отсеянных; нет автоматического сокращения stages/trials |
| Промежуточный отбор | [Helper](../../src/towr/balance/mixed_staged_evaluation.py): unsupported исключён, outside-window/round_limit допускаются для уточнения. Exact Fraction distance, stable ties/cutoff, возврат исходного порядка. Continuation отличается от локального selected; проверены пустой selected с непустым continuation и большие N без float rounding |
| Завершение | Пустой continuation до финала даёт NO_ELIGIBLE_CANDIDATES и пустой выбор. Полная цепочка даёт COMPLETED, даже с all-unsupported или пустым selected. Финальный выбор только последнего report, без возврата ранних попаданий/nearest fallback; denominator включает все trials |
| Цепочка sources | Общая `_stage_request` задаёт local budget, trials, keep/top_k, seed/window и точную подпоследовательность. Result требует полное равенство source каждого report; partial/extra/reordered/wrong continuation запрещены. Mixed 3×2/2×2 сохраняют свои пары/facts/policies; изменение pair order, GM approval, escape fact или порядка objective отклоняется на обоих этапах при прежних observations |
| Исполнение | [Service](../../src/towr/application/mixed_staged_evaluation_service.py), [9 tests](../../tests/unit/test_m7_mixed_staged_evaluation_service.py): один existing bounded call на достигнутый stage с тем же execution; typed/full source до продолжения. Полный пакет с index 0 в обоих backend, прежняя mixed seed scheme. ID и номер stage не входят в seed |
| Ошибки | [MixedStagedEvaluationError](../../src/towr/application/mixed_staged_evaluation_errors.py): stage_index с нуля, известный candidate_id либо None и полная cause/notes chain. Проверены сбой второго этапа без третьего, чужие typed/source reports, stage assembly/continuation errors, preflight/final constructor напрямую и BaseException passthrough. Нет partial/retry/fallback |
| Реальные backend | [3 integration tests](../../tests/integration/test_m7_mixed_staged_evaluation.py): full sequential/spawn equality, replay/rename/reorder с учётом tie-break, parent source, input/global RNG/cleanup и pool startup error chain. Scripted N=3 outside-window prefix продолжается в N=4 с unsupported внутри окна: COMPLETED, пустой выбор, total=7; первый stage N=4 останавливается до N=5, total=4 из planned=9 |
| Границы слоёв | Balance работает с input/aggregates, application вызывает existing bounded API; domain/engine/rules/simulation не зависят от balance/application. Shared window/options и ranged/Melee APIs сохранены. Successful result не содержит trial records/journals/RNG/options. Новых executors, auto backend, generic scheduler и wire formats нет |

Матрица опирается на **31 тест ADR-0032: 19 models/helper + 9 service + 3 integration**. Синтетические counts проверяют редкие границы; реальные scripted броски проверяют все четыре исхода (1/1/1/1, 17 Attack/6 visited) и supported prefix (1/1/1/0, 16 Attack/5 visited). Monte Carlo процент/победитель не закреплены в assertions. Source guards подтверждают согласованность ручных aggregates, а не их происхождение. Traceback ошибки может удерживать промежуточные объекты; budget не является квотой памяти.

## Самостоятельный пример

[mixed_staged_evaluation.py](../examples/m7/mixed_staged_evaluation.py) использует public staged API, builder/printer из [mixed_evaluation.py](../examples/m7/mixed_evaluation.py) и неизменный [mixed_scenario.py](../examples/m7/mixed_scenario.py), без tests/private imports. Явные составы 3×2 с одним лучником и 2×2 с двумя: numeric Footpad Dagger / Brigand Warbow, фиксированные позиции/оружие/приоритеты целей. Facts и GM approvals заданы отдельно в исходных сценариях; все участники Minions, включая сторону players_and_allies. Нет генерации, автоматического Close/awareness или новых решений GM.

Seed 42, два раунда, окно [1/4,1/2,3/4], stages=(8,keep=1),(32,keep=1). Верхний бюджет **2×8+1×32=48** на вызов. Скрипт сравнивает полные sequential/process reports и selected IDs, проверяет parent identity, planned/actual, неизменные input/global RNG и завершение детей. Process: workers=2, batch_size=3. Отчёт печатается после двух успешных вызовов и проверок: все строки/четыре доли каждого этапа, локальный selected, отдельный continuation, итоговые status/selected и общий бюджет.

[Сохранённый вывод](../examples/m7/mixed_staged_evaluation.output.txt), Windows/Python 3.14.5: на первом этапе 3×2 даёт 6/8 целей и 0 unsupported, а 2×2 — 7/8 unsupported. Продолжается 3×2; в финальных 32 trials у него 22 достижения цели и 3 unsupported. Доля цели 11/16 внутри окна, но итоговый выбор пуст, status=COMPLETED. Ранний выбор не возвращается. Это наблюдение конкретного seed/runtime, а не preset, вероятность с гарантией или ожидаемый победитель теста.

Actual=48 на каждый backend, один запуск скрипта исполняет 96 trials. Из корня и отдельного временного cwd с абсолютным PYTHONPATH получен одинаковый stdout и пустой stderr: **192 trials** в двух проверочных запусках. Финальные 32 trials считаются целиком; первые 8 повторяются. Бюджет 48, а не 40; counts stages не объединяются для новой итоговой доли, оценки stages не объявляются независимыми выборками. У разных составов общий seed не гарантирует одинаковых бросков действий.

Отдельная инъекция ошибки entry point после 16 реальных trials первого этапа: следующий полный пакет N=32 не исполняется, ошибка сохраняет stage_index=1, ID кандидата из фактического stage request и цепочку staged → bounded → OSError с исходными notes. stdout пуст, сообщение идёт в stderr, исключение проброшено; process после сбоя не запускается. Input/global RNG/children сохранены. Assertions не закрепляют заранее выбранного survivor.

## Книги и ограничения

Прямо перечитаны локальные извлечённые страницы BOOK-PLAYER-GUIDE 1.4: Equipment / Ranged Weapons, стр. 94; Rules / Combat, стр. 112; The Battlefield / Range, стр. 114; Attack Tests / Attack Modifiers, стр. 118–119; Conditions / Staggered, стр. 123. BOOK-GM-GUIDE 1.1: Allies and Antagonists / Minions, стр. 91; Understanding NPC Profiles, стр. 93; Brigands & Footpads, стр. 97.

Сохранены явные дистанции/осведомлённость, обычный outnumbering, SUFFER_WOUND и выбранные с GM dispositions. Brigand использует только Warbow, без Axe/Craven Opportunist; Footpad Lurker относится к действиям вне боя. Visited round не обязательно завершён; defeat не означает обязательную смерть. Новых игровых правил/house rules/противоречий нет. Окно/keep/trials — параметры продукта, не правила книги.

Готовность ограничена неподвижными numeric Minions с явными facts/policies. Потеря доступной цели при фиксированном оружии остаётся unsupported; отсутствие unsupported в выборке не доказывает полноты тактики. Движение/смена оружия, PC, магия, новые Abilities, автоматические awareness/approvals и полный каталог не добавлены. Confidence policy/presets и prefix reuse отсутствуют. Python 3.12/другие ОС, installed wheel и performance в этом аудите не проверялись; прошлые benchmarks не объявляются замерами staged evaluator.

## Итоговая проверка

Windows / Python 3.14.5: **2477 tests OK (278,851 с)**, включая real spawn/ranged/Melee/CLI. Compileall src/tests/tools/docs/examples/m7, 2019 локальных Markdown-путей, AST import boundaries, public imports примера и diff/whitespace успешны. Лог: build/m7-staged-audit-tests.log (ignored). SHA-256 всех 659 файлов src/tests/tools совпали со снимком начала среза. Все 30 исходных dirty/untracked файлов сохранены; добавлены аудит, пример и его вывод, обновлена документация. Новых unittest tests нет; commit/push не выполнялись.

## Следующий шаг

Подготовить контракт ограниченной генерации **mixed-составов из явно заданного резерва** по образцу [ADR-0026](../decisions/ADR-0026-melee-composition-generation.md). Зафиксировать неизменную perspective-сторону, группы/диапазоны численности противоположной стороны, сохранение numeric profiles/оружия/приоритетов и решений GM. Отдельно определить область применимости family facts и pair ranges, проекцию roster/combat/spatial/targets/defeat decisions/objective и проверку mixed admission для каждого состава: обе роли и начальные доступные цели обязательны. Deterministic IDs/порядок, предел числа кандидатов и полный staged budget проверяются до материализации. Недопустимые составы не пропускать молча.

Сначала ADR, матрица и конечные допустимые/отклоняемые примеры; production реализация отдельно. Facts/дистанции/GM approvals не выводятся автоматически из состава; новые действия/способности, JSON/CLI, prefix reuse и общий battle aggregate не включаются.
