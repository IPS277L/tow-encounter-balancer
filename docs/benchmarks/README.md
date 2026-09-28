# Профилирование M3

`tools/profile_m3.py` — developer harness последовательного M3; это не CLI приложения. В исходном baseline domain, engine и simulation не менялись; результат первого performance-среза приведён ниже. [Baseline 2026-09-28](m3-baseline-2026-09-28.md) сохранён вместе с командой, runtime, revision исходного `src`, seed scheme, агрегатами, digest всех trial records и cProfile.

```powershell
$env:PYTHONPATH = "src"
py -3.14 tools/profile_m3.py --trials 100 --master-seed 20260928 --round-budget 5 --repeats 3 --top 12 --output docs/benchmarks/m3-baseline-2026-09-28.md
```

Команда заново записывает указанный отчёт. Для будущего сравнения сохранять новый отчёт под другим именем, чтобы исходный baseline оставался доступен. Параметры можно менять, но сравнивать разные версии движка нужно на одинаковых входах.

## Набор и методика

Фиксированы составы 1×1, 2×2, 3×2, обычный порядок сторон и actor/target priorities. Fixture строится непосредственно из public contracts без импорта тестов: numeric Warbow Shooting 3d/3, Damage 3, Medium–Long/2H; Athletics 3d/2; Resilience 3+1. Источник непосредственно проверен: BOOK-GM-GUIDE 1.1, Allies and Antagonists / Brigands & Footpads / Brigand, стр. 97. Это ranged excerpt, не полный Brigand. Facts — неподвижность, видимые осведомлённые противники в соседней Zone, достаточные боеприпасы, отсутствие дополнительных эффектов. Повторный Staggered → Wound; все GM-approved defeat dispositions — knocked out. Ограничения [ADR-0013](../decisions/ADR-0013-ranged-minion-scenario-input.md) сохраняются.

- Импорты и построение input вне измерений; каждый case прогревается на min(3, trials).
- Три wall-clock повтора через perf_counter без cProfile/tracemalloc. Перед каждой измеряемой фазой выполняется gc.collect вне таймера; GC остаётся в исходном режиме.
- Отдельный запуск tracemalloc измеряет максимум выделений Python во время пакета. Импорты, исходный fixture и уже существующий reference result не входят. Это **не RSS процесса** и не оценка всей памяти интерпретатора.
- Ещё один отдельный запуск cProfile даёт top cumulative/self time и callers dataclasses.replace. Cumulative строки перекрываются, их нельзя суммировать. Эти времена не заменяют обычный wall-clock.
- Все timed/memory/profile результаты сравниваются целиком с reference NpcRangedSimulationResult, включая каждый trial. Изменение records вызывает отказ даже при совпадении агрегатов. Digest в отчёте — SHA-256 от seed scheme и ordered строк `index|seed|outcome|attacks|visited_rounds`, разделённых LF, без завершающего LF.
- Профайлер/трассировщик, уже активный до measure, отклоняется. Ошибки не скрываются, tracemalloc выключается также при ошибке измеряемого запуска.

Замеры зависят от нагрузки, частоты CPU, runtime и прогрева. В частности, 3×2 на этих seeds заканчивается раньше и выполняет меньше Attack, чем 2×2: время не обязано расти только с числом участников. Этот небольшой набор не подтверждает масштабирование на большие составы или миллионы trials.

## Полученный baseline

CPython 3.14.5, Windows 11; source revision и CPU указаны в сыром отчёте. Во время финального baseline тесты/другие измерения параллельно не запускались. Во всех трёх обычных повторах, memory run и profile run records совпали.

| Состав | Медиана wall, с / 100 trials | Peak Python, КиБ | Attack | Посещённых раундов |
| --- | --- | --- | --- | --- |
| 1×1 | 0,306063 | 96,7 | 368 | 212 |
| 2×2 | 0,703143 | 145,1 | 810 | 307 |
| 3×2 | 0,647570 | 149,3 | 735 | 232 |

В 2×2 cProfile показывает 28487 вызовов dataclasses.replace с cumulative 0,746 с из 1,867 с корневого вызова профилируемого пакета. Существенная часть работы — конструкторы и проверки CombatRoundState, NpcRoundRequest и roster state. Это не основание отключать guards: они обеспечивают source continuity.

Callers позволяют выделить небольшой безопасный кандидат: getter [NpcRosterAttackExecutionResult.state](../../src/towr/domain/npc_roster_attack_models.py) заново создаёт roster/state при каждом чтении. На пакете 2×2 из него вызван replace 4334 раза, cumulative 0,088 с; на 3×2 — 3972 раза, 0,085 с. Эти числа относятся к вызовам replace из getter, **не к числу обращений к property**. Это один из источников затрат, а не вся стоимость validation и не обещанный процент ускорения.

## Выбранный по baseline срез (выполнен)

В NpcRosterAttackExecutionResult вычислять и сохранять immutable derived state один раз после исходной source validation. Сохранить все проверки, replay guards, Wounds/Conditions/history и исходные snapshots; не менять другие projections и не добавлять общий cache или mutable battle aggregate.

Проверить неизменность результатов ordinary Melee/Shooting, повторные чтения без повторного построения state, source/receipt отказов и полный набор тестов. Затем повторить эту же команду в отдельный отчёт: сравнить все trial digests/агрегаты, число replace calls из getter, median wall и peak Python. Прирост скорости оценивать по измерениям; увеличение памяти от сохранённого snapshot также указать. Параллелизм пока не добавлять.

Harness проверяется четырьмя детерминированными тестами в [test_m3_profiling.py](../../tests/unit/test_m3_profiling.py); точное время, проценты исходов и размер памяти не фиксируются как пороги тестов.

## Однократное построение Attack state

[Отчёт после изменения](m3-cached-attack-state-2026-09-28.md) использует те же fixtures, seeds, 100 trials, round budget 5 и три повтора. Source revision тот же, но с незакоммиченным изменением `src/towr/domain/npc_roster_attack_models.py`: private derived `_state` строится в конце `__post_init__`, getter только возвращает его. Все исходные проверки и алгоритм проекции сохранены. Новый отчёт записан отдельно; baseline не перезаписан. Финальный замер выполнен после полного набора тестов, без одновременной тяжёлой проверки.

| Состав | Median wall baseline → после, с | Изменение | Peak Python baseline → после, КиБ |
| --- | --- | --- | --- |
| 1×1 | 0,306063 → 0,273343 | −10,7% | 96,7 → 96,6 |
| 2×2 | 0,703143 → 0,584341 | −16,9% | 145,1 → 144,7 |
| 3×2 | 0,647570 → 0,643556 | −0,6% | 149,3 → 149,0 |

Все три trial-record SHA-256 и агрегаты совпали с baseline. Callers `replace` из прежнего getter и нового `_build_state`: 2×2 — 4334 → 1798 на тех же 810 Attack; 3×2 — 3972 → 1635 на 735 Attack. Getter больше не строит state. Сохранённый snapshot живёт вместе с result; общего cache нет. Локальный peak Python не вырос, но это не RSS, и измерения не доказывают улучшения всей памяти процесса или устойчивого процента ускорения. Для 3×2 разница wall мала относительно разброса повторов; cProfile times также нельзя использовать как обычный тайминг.

Три новых unit tests в test_m2_npc_roster_attack_execution.py подтверждают eager construction/repeated reads без replace/RNG, immutable inputs, все histories, пересборку при dataclasses.replace и прежние отказы до проекции. Полный набор 1787 tests OK.

## Сравнение последовательного режима и spawn

Опциональный process runner реализован ([ADR-0015](../decisions/ADR-0015-process-ranged-simulations.md)). Отдельный developer harness tools/benchmark_m3_parallel.py переиспользует те же numeric fixtures, seed 20260928, budget 5; batch_size 32, workers 1/2, три повтора на 100 и 1000 trials. [Отчёт 100](m3-spawn-100-2026-09-28.md), [отчёт 1000](m3-spawn-1000-2026-09-28.md).

```powershell
$env:PYTHONPATH = "src"
py -3.14 -m tools.benchmark_m3_parallel --trials 1000 --master-seed 20260928 --round-budget 5 --workers 1 2 --batch-size 32 --repeats 3 --output docs/benchmarks/m3-spawn-1000-2026-09-28.md
```

Для 100 trials команда та же с --trials 100 и отдельным output. Каждый process timer включает свежий pool, pickle request/factory, spawn/imports, исполнение, сбор compact records, validation и shutdown. Режимы чередуются по порядку; parent warm-up min(3, trials), fixture/imports родителя и gc.collect вне таймера. Замеры выполнены после полного набора тестов, без одновременного тяжёлого тестирования. Это обычный wall-clock без tracemalloc/cProfile; память дочерних процессов и общий RSS не измерялись.

| Trials | Состав | Sequential median, с | Spawn 1 worker, с | Spawn 2 workers, с | Sequential / 2 workers |
| --- | --- | --- | --- | --- | --- |
| 100 | 1x1 | 0.249827 | 1.181107 | 1.195772 | 0.209 |
| 100 | 2x2 | 0.663755 | 1.551590 | 1.445490 | 0.459 |
| 100 | 3x2 | 0.636179 | 1.487279 | 1.421033 | 0.448 |
| 1000 | 1x1 | 2.835034 | 3.951510 | 2.827635 | 1.003 |
| 1000 | 2x2 | 6.609370 | 7.296600 | 4.884708 | 1.353 |
| 1000 | 3x2 | 6.297143 | 7.233059 | 5.173094 | 1.217 |

Все compact records во всех режимах/повторах совпали, для 100 trials совпали также три SHA-256 исходного baseline и его агрегаты. Ratio больше 1 означает ускорение относительно последовательного запуска в этом замере. На 100 trials создание процессов не окупается. Результаты 1000 trials также относятся только к текущим runtime/host, worker count и этим сценариям; универсального порога выгодности или автоматического выбора режима из них не следует. Sequential остаётся самостоятельным API; пользователь выбирает process режим явно. Постоянный pool, больше workers и миллионы trials не проверялись.

На 1000 trials два workers дали median ratio 1,353 для 2×2 и 1,217 для 3×2. Для 1×1 ratio 1,003 практически не отличается от единицы. Один worker здесь медленнее sequential во всех составах. Разброс повторов (особенно 3×2) сохранён в сыром отчёте; эти числа не являются гарантией ускорения на другом host.

## Точный следующий шаг

M4 Schema, pure adapters, application service и CLI simulate выполнены; актуальный [статус](../project-status.md) сохраняет прежнюю границу правил.

[Аудит M4](../audits/m4-readiness.md) завершён; bounded evaluation списка с бюджетом и top_k по [ADR-0017](../decisions/ADR-0017-ranged-candidate-assessment.md) реализован. [ADR-0018](../decisions/ADR-0018-staged-ranged-evaluation.md) реализован с полным учётом повторных пакетов без prefix reuse. Генератор численности по [ADR-0019](../decisions/ADR-0019-ranged-composition-generation.md) реализован: явный резерв участников, неизменные профили/решения, предел составов и полный staged budget. Следующий шаг — сквозной аудит первого M5 и воспроизводимый пример генерации → поэтапной оценки. Backend/workers задаются явно, кандидаты исполняются по очереди; прежний simulation runner не менялся, новый benchmark в этом срезе не запускался.
