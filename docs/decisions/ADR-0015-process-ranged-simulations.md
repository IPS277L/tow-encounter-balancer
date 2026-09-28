# ADR-0015: опциональное исполнение M3 в процессах

Статус: принято, 2026-09-28.

## Контекст

Последовательный [M3](ADR-0014-independent-ranged-simulations.md) уже задаёт стабильный seed по master seed/index, отдельный RNG и компактный результат. После baseline и первого performance-среза требуется исполнение независимых trials в процессах с сохранением этого контракта. Игровая граница остаётся [неподвижным ranged Minion-сценарием](ADR-0013-ranged-minion-scenario-input.md); новых правил, policies и Rule IDs нет.

## API и направление зависимостей

`towr.simulation.npc_ranged_parallel.run_npc_ranged_simulation_parallel(request, *, workers, batch_size=32, rng_factory=Random)` принимает прежний NpcRangedSimulationRequest и возвращает прежний NpcRangedSimulationResult. workers и batch_size — положительные int, bool запрещён. workers задаётся явно; автоматического переключения режима или выбора CPU count нет. Последовательный API сохраняется.

Процессы — ответственность simulation; domain/engine/rules не импортируют multiprocessing и не менялись. Новый pool создаётся на каждый вызов с explicit spawn context, независимо от глобального start method. Даже workers=1 использует дочерний процесс. Дополнительно действуют платформенные ограничения стандартного ProcessPoolExecutor (в частности, не более 61 workers на Windows).

Входной скрипт caller должен быть импортируемым, с защищённой точкой входа:

```python
from towr.simulation.npc_ranged_parallel import run_npc_ranged_simulation_parallel

def main():
    request = build_admitted_simulation_request()  # application-owned construction
    result = run_npc_ranged_simulation_parallel(request, workers=2, batch_size=32)
    consume_result(result)

if __name__ == "__main__":
    main()
```

Это шаблон вызова с внешними build/consume functions, не новый application API. Интерактивный stdin/REPL и notebook как entry point этим срезом не поддерживаются.

## Разбиение и воспроизводимость

Каждая задача получает тот же immutable request, непрерывный диапазон абсолютных trial indices и фабрику RNG. Request сериализуется для каждого пакета; глобального worker state, общего RNG или mutable aggregate нет. Внутри задачи вызывается existing run_npc_ranged_trial: свежий RNG из seed каждого индекса, один scenario execution и проекция в compact record. Полные журналы не передаются родителю и освобождаются между trials.

Одновременно удерживаются не более `2 * workers` submitted futures. Диапазоны выдаются лениво; завершённые пакеты собираются в произвольном порядке, затем существующий result constructor сортирует indices и проверяет полноту, отсутствие дубликатов, seeds и бюджеты. В результирующем объекте сохраняется исходный request родителя. Размер compact результата остаётся O(trials); bounded queue не делает весь результат потоковым.

Фабрика внедряется и в process API. Она должна быть picklable/importable (например, top-level function или functools.partial от неё) и создавать независимый RandomSource только из supplied seed. Lambda/local closure отклоняются preflight pickle до создания пула; проверки не гарантируют успешный импорт в ребёнке или чистоту фабрики. Счётчики вызовов, PID, порядок задач и shared side effects не должны влиять на RNG. Стандартный Random(seed) обеспечивает тот же replay при том же runtime и правилах.

## Ошибки и завершение

Неверные request/options/callable и невозможность сериализации отклоняются до pool. Ошибки trial/RNG не становятся outcome: ребёнок добавляет note с trial index/seed и передаёт исключение. Ошибки сериализации, импорта или сломанного пула также распространяются; fallback на последовательное исполнение и автоматические retries отсутствуют. Частичный NpcRangedSimulationResult не возвращается.

При выходе отменяются ещё не запущенные pending futures; context manager закрывает pool и ждёт уже выполняющуюся работу. Поэтому ошибка не означает немедленное принудительное завершение остальных детей, timeout/hard-kill API отсутствует. Immutable входы остаются прежними. Никаких rollback внешних side effects пользовательской фабрики не гарантируется.

## Проверки и измерения

5 unit tests в [test_m3_npc_ranged_parallel.py](../../tests/unit/test_m3_npc_ranged_parallel.py): preflight до pool, bounded queue с обратным завершением и неполным хвостом, абсолютные indices, отмена pending/закрытие при ошибке, отказ отсутствующих/чужих records. 3 integration tests в [одноимённом файле](../../tests/integration/test_m3_npc_ranged_parallel.py) используют настоящие spawn-процессы: 1×1/2×2/3×2, workers 1/2 и разбиение 1/3, точные outcomes на injected RNG, больший batch prefix, PID вне родителя, immutable input/global RNG, ошибка из ребёнка и отсутствие оставшихся процессов. Два теста benchmark проверяют сопоставление records и guards параметров. Полный набор: 1797 tests OK, Python 3.14.5; Python 3.12 в текущем окружении отсутствует.

[tools/benchmark_m3_parallel.py](../../tools/benchmark_m3_parallel.py) сравнивает обычный wall-clock на тех же fixtures с учётом pickle, spawn/imports, выполнения и shutdown нового пула при каждом повторе. Mode order чередуется, records сравниваются целиком. Memory/RSS дочерних процессов и cProfile в этот отчёт не входят. [Результаты и ограничения](../benchmarks/README.md).

Постоянный pool, автоматический подбор workers/batch size, distributed execution, retry/checkpoint, сокращение validation и расширение правил не входят в решение.

M3 закрыт в указанной границе [конечным аудитом](../audits/m3-readiness.md). Wire execution options и ограничения первого M4 определены в [ADR-0016](ADR-0016-ranged-simulation-json-v1.md); JSON никогда не передаёт callable/pickle.
