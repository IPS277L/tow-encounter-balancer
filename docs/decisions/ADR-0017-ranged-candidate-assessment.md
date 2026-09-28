# ADR-0017: агрегаты и ограниченная оценка кандидатов M5

Статус: технический следующий срез определён, 2026-09-28. Контракт оценки кандидатов — **предложение**, до подтверждения продуктовой метрики; код M5 ещё не реализован. [Аудит M4](../audits/m4-readiness.md) завершён.

## Основание и решения разного уровня

AGENTS.md требует, чтобы балансировщик получал только вход симулятора и агрегированный результат. Нынешний NpcRangedSimulationResult хранит ещё и per-trial records; передавать его целиком новому balance evaluator не следует. Нужна отдельная неизменяемая проекция счётчиков с исходным NpcRangedSimulationRequest. Она не зависит от определения сложности.

Исходный дизайн, разделы 19–22, предлагает player victory rate, приблизительные окна Easy/Medium/Hard/Impossible, желаемую длительность и многоэтапный поиск. Это продуктовые ориентиры прототипа, не нормативные правила книги и не готовый контракт первого M5. Текущий [NpcRangedScenario](ADR-0013-ranged-minion-scenario-input.md) допускает только Minions; objective перечисляет всех противников perspective_side. OBJECTIVE_ACHIEVED означает поражение противоположной стороны в данном сценарии, а не утверждение о смерти всех NPC или победе полноценной группы PC.

Пользователю предложен ограниченный первый M5: оценка достижения заданной цели за явный round budget, отдельные shares round_limit/unsupported_path, числовое окно без именованных пресетов. Подтверждение ещё не получено; это не house rule и не повод менять engine. Без ответа можно выполнить только независимый aggregate-only срез ниже.

## Первый implementation-срез: только сводка M3

Предлагаемые публичные имена:

- `simulation/npc_ranged_summary_models.py`: frozen, slots `NpcRangedSimulationSummary`.
- `simulation/npc_ranged_summary.py`: `summarize_npc_ranged_simulation(result) -> NpcRangedSimulationSummary`.

Сводка хранит только `source_request`, typed `outcome_counts`, `total_attack_count`, `total_visited_round_count`. Число прогонов берётся из `source_request.trials`; mean_attack_count и mean_visited_round_count вычисляются из сумм, как в M3, а не передаются независимо. Ни trial records, ни seed на каждый trial, ни журналы, terminal injury snapshots или ссылка на полный result не удерживаются. Сам input simulator разрешён архитектурной границей и остаётся неизменяемым.

`summarize` принимает только завершённый NpcRangedSimulationResult, переносит его exact source и счётчики без runner/RNG/JSON. Не происходит повторной оценки outcomes или проигрывания боя. Конструктор сводки проверяет typed source/counts, exact int без bool, неотрицательные totals, сумму четырёх outcomes == trials, допустимые суммарные границы числа атак и посещённых раундов по source. Для раундов учитывается нижняя граница: каждый ROUND_LIMIT использует весь budget, остальные outcomes посещают хотя бы один раунд; для атак — минимум по одному на terminal outcome и не больше slots за посещённые раунды. Guards проверяют непротиворечивость агрегатов, а не восстанавливают утраченные trial records и не доказывают происхождение данных.

Средние вычисляются с тем же смыслом, что сейчас: visited rounds включают посещённый последний раунд, даже если он не завершён; unsupported/round_limit записи не отбрасываются. Это не средняя длительность только выигранного или полностью завершённого боя. Rates и difficulty labels в первый срез не входят. M3 result, CLI/JSON v1 и существующие service APIs сохраняются; отдельного endpoint или сериализации сводки пока нет.

Следующие детерминированные тесты обязательны: точные четыре outcome counts и totals, совпадение means с M3, frozen inputs/summary, неверные types/count sums/budgets, отсутствие trial/result references, отсутствие RNG/runner при проекции; реальная sequential/process композиция даёт равные сводки одного source. Это не Monte Carlo-тест на конкретную вероятность.

## Предложение последующей границы M5

После подтверждения метрики отдельный `balance` слой зависит только от simulation input/summary contracts. Никаких JSON, CLI, engine calls, игровых журналов, RNG или знания Attack/Wound resolution внутри evaluator. Application orchestration исполняет прежний runner, создаёт aggregate summary и передаёт его оценщику. UI/JSON для balance появятся отдельным решением, а не расширением simulation v1 без версии.

| Модель (предварительное имя) | Содержание |
| --- | --- |
| RangedBalanceCandidate | Непустой candidate_id и готовый допущенный NpcRangedScenario; сценарий не генерируется и не исправляется оценщиком |
| RangedBalanceEvaluationRequest | Упорядоченный непустой tuple уникальных candidates, общие master_seed/trials_per_candidate/max_total_trials, одно явное окно цели, top_k |
| ObjectiveRateWindow | Точные рациональные min/target/max в [0,1], min ≤ target ≤ max; без defaults Easy/Medium и без весов |
| RangedCandidateAssessment | Exact candidate/request/summary source, вычисленные доли/средние, пригодность оценки и соответствие окну; нельзя независимо передать готовый score |
| RangedBalanceEvaluationResult | Все assessments в порядке входа, выбранные candidate IDs, фактический бюджет и параметры воспроизведения; не содержит per-trial records |

Первый evaluator не проверяет, что два сценария являются одним и тем же encounter с изменённым ровно одним параметром. Caller явно подаёт разрешённый конечный список альтернатив; отчёт сохраняет каждый полный input. Общими обязаны быть perspective_side и round budget. Более сильные ограничения на неизменную группу/геометрию и генерация допустимых вариантов требуют отдельного контракта. Нельзя автоматически менять composition, свойства профиля, awareness, policies или GM decisions ради попадания в окно.

## Предложение метрик и фильтрации

Для N = trials публикуются четыре наблюдаемые доли: objective_achieved/N, side_defeated/N, round_limit/N, unsupported_path/N. Знаменатель никогда не заменяется суммой только terminal outcomes. При отсутствии unsupported вероятность цели трактуется только как оценка достижения цели **в пределах заданного бюджета**, а не победы при неограниченной длительности. ROUND_LIMIT остаётся собственным исходом и не объявляется поражением или ничьей.

При unsupported_path > 0 предложено помечать оценку `UNSUPPORTED_OBSERVATIONS`: счётчики и observed shares сохраняются, но candidate не получает valid difficulty/window match и не попадает в selected. Нет подмены unsupported поражением, исключения таких trials из знаменателя или скрытого rerun. Это ограничение достоверности инструмента, а не новое игровое правило. Ошибка исполнения вообще не создаёт assessment с игровым outcome.

Для пригодных кандидатов сравнение с включёнными границами окна и расстоянием до target выполняется по точным отношениям counts/N; в typed window предлагается stdlib Fraction, без неоднозначного float epsilon. Внутри окна выбираются до top_k по abs(objective_rate − target), равенство сохраняет исходный порядок candidates. Кандидаты вне окна остаются в отчёте; если никто не подходит, selected пуст, а «ближайший» не выдаётся за подходящий. Формула не сочетает разные показатели с выдуманными весами.

Длительность и Attack counts пока только описательные. Target rounds, условные средние по исходам, confidence intervals, доверительная пригодность малого N и именованные difficulty presets требуют отдельного продуктового/статистического контракта. Попадание точечной оценки в окно не является гарантией истинной вероятности. Прежние приблизительные Easy/Medium/Hard/Impossible границы не включаются по умолчанию.

## Предложение seeds, бюджета и исполнения

Application строит для каждого candidate прежний NpcRangedSimulationRequest с одним явно заданным master_seed и trials_per_candidate; seed scheme/index M3 не меняются. Candidate ID/порядок не входят в derivation; перестановка кандидатов не меняет наблюдения каждого. Один и тот же trial index имеет один seed у разных сценариев, но разные ветвления могут расходовать RNG по-разному — равенство seed не означает тождественность бросков соответствующих действий или доказанное снижение ошибки сравнения.

Все candidates, окно, positive exact int trials/top_k/max_total_trials и общие поля проверяются до первого runner. `len(candidates) * trials_per_candidate <= max_total_trials` — явный бюджет исполнения; при превышении полный request отклоняется до работы, без неявного уменьшения списка или trials. Каждый candidate оценивается один раз полным пакетом. Несколько candidates исполняются последовательно; опциональный process backend применяется только внутри одного кандидата с явно переданными options. Вложенные pools, автоматический подбор режима и бюджет времени не вводятся.

При runner failure/source mismatch вычисление заканчивается типизированной ошибкой с candidate_id и исходной причиной. Уже вычисленные summaries не выдаются как complete evaluation result. Никаких retries/checkpoints или продолжения после исключения. UNSUPPORTED_OBSERVATIONS — assessment по готовому результату, а не исключение runner. Отчёт хранит общий seed/trials, полный source каждого кандидата и seed scheme; runtime/code provenance остаётся обязанностью application/report adapter, как в M4.

Staged search остаётся следующим этапом roadmap. Первый evaluator не обещает reuse prefix или адаптивное увеличение N; бюджет будущего повторного полного запуска должен учитывать все реально исполненные trials, пока не появится отдельный контракт incremental evaluation. Universal optimizer, изменение правил, общий battle aggregate и PC/Minion смешанная модель вне решения.

## Порядок продолжения

1. Реализовать и проверить aggregate-only summary/projection, независимо от ответа на вопрос о сложности.
2. Подтвердить или скорректировать продуктовую метрику из [open-questions](../open-questions.md#первая-метрика-m5); после этого принять соответствующие разделы ADR и реализовать pure single-candidate assessment с детерминированными тестами границ/unsupported.
3. Отдельным срезом соединить конечный список кандидатов с existing runners, бюджетом и source-checked отчётом. Затем обсудить staged search и генерацию, сохранив M5 в roadmap.

Новых Rule IDs, трактовок книг или house rules этот документ не вводит. Book-dependent semantics остаются в ADR-0013/0014; книги для технического аудита повторно не извлекались. Продуктовая гипотеза явно отделена от уже проверенной механики.
