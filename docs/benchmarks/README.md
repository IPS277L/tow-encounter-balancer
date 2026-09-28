# Профилирование M3 и M6

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

[Аудит M4](../audits/m4-readiness.md) завершён; bounded evaluation списка с бюджетом и top_k по [ADR-0017](../decisions/ADR-0017-ranged-candidate-assessment.md) реализован. [ADR-0018](../decisions/ADR-0018-staged-ranged-evaluation.md) реализован с полным учётом повторных пакетов без prefix reuse. Генератор численности по [ADR-0019](../decisions/ADR-0019-ranged-composition-generation.md) реализован: явный резерв участников, неизменные профили/решения, предел составов и полный staged budget. Первый M5 закрыт [аудитом](../audits/m5-readiness.md) в текущем scope; [typed пример](../examples/m5/README.md) проверен в sequential/process. Контракт [JSON balance v1 / CLI balance](../decisions/ADR-0020-ranged-balance-json-v1.md) реализован полностью в текущем scope: Schema/adapters, application service, кодирование ошибок и CLI balance. Внешняя граница M5 закрыта [аудитом](../audits/m5-external-readiness.md); следующий этап M6 — ограниченный контракт ближнего боя Minions, выбранный пользователем. Backend/workers задаются явно, кандидаты исполняются по очереди; прежний simulation runner не менялся, новый benchmark в этом срезе не запускался.

## Melee baseline M6

[tools/profile_m6.py](../../tools/profile_m6.py) измеряет отдельный последовательный pipeline ADR-0022: simulation → aggregate summary. [Сырой baseline](m6-baseline-2026-09-28.md) содержит runtime/CPU, revision с отметкой незакоммиченного src, хеш фактических исходников/harness, seeds, каждый wall repeat, peak Python memory, trial digests и cProfile. Существующие M3 отчёты не перезаписаны; сравнение времени M3/M6 не является сравнением скорости одного сценария, поскольку профили/правила/seed schemes различаются.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe tools/profile_m6.py --trials 100 --master-seed 20260928 --round-budget 5 --repeats 3 --top 20 --output docs/benchmarks/m6-baseline-2026-09-28.md
```

Команда перезаписывает указанный отчёт; будущий замер сохранять под другим именем. Fixture построен из public constructors без imports tests: здоровые Footpad 1×1/2×2/3×2, Dagger Close 3d/3 Dam2 1H, Athletics 3d/3, RES3, полные GM-approved knocked_out decisions. Непосредственно сверены BOOK-GM-GUIDE 1.1, Allies and Antagonists / Brigands & Footpads / Footpad, стр. 97 и BOOK-PLAYER-GUIDE 1.4, Rules / Attack Tests / Attack Modifiers, стр. 118–119. Lurker вне боя не применяется. Явные Close всех вражеских пар, awareness/LOS, stationary, полный состав одной Zone, отсутствие mounts/высоты/других правил и modifiers; обычный outnumbering одобрен всем actors. Выход в соседнюю Zone доступен, тактика повторного Staggered — SUFFER_WOUND. Исходный и целевой порядки заданы roster order.

Методика повторяет M3: warm-up min(3,trials), три отдельных perf_counter повтора, затем отдельные tracemalloc и cProfile, gc.collect вне таймеров. Импорты/fixture вне таймера, summary projection внутри. Полные compact result и aggregate summary сравниваются после каждой фазы; отличие records отклоняется даже при равных aggregates. SHA-256 records использует прежнее текстовое encoding `scheme + LF + index|seed|outcome|attacks|visited_rounds`, без завершающего LF. Source/harness hash: сортированные по relative POSIX path все src/**/*.py и tools/profile_m6.py, для каждого path в UTF-8 + NUL + raw SHA-256 bytes файла, затем общий SHA-256. Включены untracked sources, исключены bytecode и документация. Hash до/после замера обязан совпасть; он связывает отчёт с bytes, но не хранит их копию и не является доказательством происхождения среды.

CPython 3.14.5 / Windows 11. Во время baseline полный набор тестов и другие наши тяжёлые проверки не выполнялись. Успешно совпали результаты всех трёх обычных повторов, memory/profile runs. Внешняя нагрузка ОС не контролировалась. Peak — дополнительные Python allocations пакета, не RSS: заранее созданные input/reference result, импортированные модули не включены. Cumulative rows перекрываются, их нельзя суммировать или трактовать как обычный wall time.

| Состав | Медиана wall, с / 100 trials | Peak Python, КиБ | Цель / поражение / лимит / unsupported | Attack | Посещённых раундов |
| --- | --- | --- | --- | --- | --- |
| 1×1 | 0,396322 | 87,8 | 52 / 48 / 0 / 0 | 312 | 182 |
| 2×2 | 0,770624 | 125,1 | 58 / 42 / 0 / 0 | 606 | 227 |
| 3×2 | 0,703346 | 148,4 | 96 / 4 / 0 / 0 | 616 | 209 |

Это наблюдения фиксированных seeds, не статистическая гарантия баланса/скорости. Отсутствие round_limit/unsupported в этих 300 trials не отменяет такие исходы; они проверены отдельными тестами simulation. Время не обязано расти с численностью: число ходов/раундов, поражений и resume различается. CPU affinity, RSS, другие ОС/Python 3.12 и большие пакеты не проверялись.

### Выбранный следующий performance-срез

В 2×2 cProfile показывает 21483 вызова dataclasses.replace (cumulative 0,733 с). Это главным образом построение typed snapshots и validation; отключать guards нельзя. Узкий повторяемый источник затрат — [MinionDefeatAcknowledgementResult.continuation](../../src/towr/domain/minion_defeat_models.py): getter каждый раз строит одинаковые roster history и NpcRoundRequest. Из getter вызван replace 1304 раза / 0,065 с для 1×1; 1832 / 0,082 с для 2×2; 1908 / 0,092 с для 3×2. Это количество replace calls, а не количество defeat или чтений property; getter делает два replace. Числа не являются обещанием процента ускорения.

Выбранный срез (теперь выполнен ниже): однократно построить immutable continuation в MinionDefeatAcknowledgementResult после проверки source, с private derived field `init=False, repr=False, compare=False`. Getter возвращает тот же snapshot. Сохранить все source/GM/receipt/replay guards, удаление только подтверждённого pending, остальные pending и histories; dataclasses.replace(result, source_request=...) должен пересобирать derived value. Не вводить общий cache и не оптимизировать остальные getters одновременно.

Проверить repeated reads без replace/RNG, frozen sources и сохранность чужих pending, typed/foreign/stale/replay отказы и полную регрессию ranged/Melee. Затем повторить baseline в новый отчёт с теми же seeds/параметрами, сравнить три trial digests и агрегаты, wall/peak и replace callers. Сохранённый snapshot продлевает время жизни объекта; возможную цену по памяти оценить вместе со скоростью. Результат оптимизации приведён ниже; Melee process backend/балансировщик не добавлены.

Harness покрыт [5 детерминированными тестами](../../tests/unit/test_m6_profiling.py): fixtures, реальная композиция измерений/summary/report, расхождение records в каждой фазе, invalid settings/active profiler и cleanup tracing при ошибке, hash untracked sources/harness. Точные времена, проценты и байты не являются test expectations.

## Однократная Minion defeat continuation

[Отчёт после изменения](m6-cached-defeat-continuation-2026-09-28.md) получен тем же неизменённым tools/profile_m6.py: 100 trials, seed 20260928, budget 5, три повтора, top 20. Production-изменение только в MinionDefeatAcknowledgementResult: private derived continuation строится в конце source validation, getter возвращает её. [Контракт ADR-0010](../decisions/ADR-0010-single-minion-round.md#однократная-проекция-minion-defeat-continuation). Исходный baseline сохранён. Новый benchmark выполнен после полного набора тестов, отдельно от тяжёлых проверок.

| Состав | Median wall baseline → после, с | Наблюдаемое изменение | Peak Python baseline → после, КиБ | Replace calls из getter → builder |
| --- | --- | --- | --- | --- |
| 1×1 | 0,396322 → 0,272819 | −31,2% | 87,8 → 87,6 | 1304 → 200 |
| 2×2 | 0,770624 → 0,602216 | −21,9% | 125,1 → 125,0 | 1832 → 458 |
| 3×2 | 0,703346 → 0,622719 | −11,5% | 148,4 → 148,4 | 1908 → 458 |

Все три trial-record SHA-256, seeds/бюджеты, четыре outcome counts, суммы Attack/visited rounds совпали с baseline. Между повторами, tracemalloc и cProfile также совпали полные result/summary. Replace из прежнего getter исчез; builder выполняет по два replace на acknowledgement. Cumulative replace time из него изменилось 0,065→0,007 с, 0,082→0,023 с, 0,092→0,032 с соответственно. Это профилируемые вложенные времена, не обычный wall-clock.

Сохранённый snapshot удерживается вместе с result: добавлена ссылка и продлено время жизни проекции. В измеренном incremental peak Python роста не видно, но это не доказательство уменьшения памяти каждого result или всего процесса; RSS не измерялся. Наблюдаемая разница wall time включает шум среды: повтор 2×2 лежит между 0,532522 и 0,760313 с, CPU affinity/частота и нагрузка ОС не контролировались, запуски baseline/после не чередовались. Поэтому весь процент разницы нельзя приписать только этому изменению или обещать его на другом host. Надёжный структурный результат — отсутствие повторного построения getter и меньше replace при идентичных игровых результатах.

Три новых unit tests проверяют eager construction, repeated reads/apply без построения, сохранность source/очереди/histories, rebuild через dataclasses.replace, immutable value/identity contract и отказ invalid source до builder. Полный набор **2055 tests OK (126,598 с)**, Python 3.14.5, включая ranged/Melee и реальные spawn workers. Следующий шаг — отдельный контракт опционального Melee process runner; дальнейшая оптимизация других getters в этот срез не включалась.
