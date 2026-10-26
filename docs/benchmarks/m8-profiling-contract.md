# Контракт первого profiling-среза M8

Дата: 2026-10-26. Основание — завершённый [ADR-0038](../decisions/ADR-0038-independent-magic-simulations.md). Это ограниченный developer harness над public sequential API, не новое игровое правило или приложение. Production src, seeds, admission и обязательные stops сохраняются; оптимизация и process backend в эту веху не входят.

## Нагрузки и параметры

[tools/m8_benchmark_fixtures.py](../../tools/m8_benchmark_fixtures.py) строит public NpcMagicSimulationRequest без imports из tests/docs/probes. Числа authored, не профиль книжного NPC: один Champion-Wizard Level 2, Casting/Willpower 3d/3, Resilience 4; два Shooting Minions 3d/3, Damage 3, Resilience 3, Athletics 3d/3. Одна memorised Curse of Cowardly Flight. Все начинают в arena; enemy может последовательно уйти в shelter и boundary. Порядок spatial archive отличается от roster order.

| Case | Порядок и явные факты | Назначение |
| --- | --- | --- |
| curse-routes | Wizard → ally → enemy; enemy выбирает Wizard, затем ally | Casting/WAIT/Curse, ordinary attacks, Broken Recover и Wound stops |
| champion-pressure | Тот же порядок; enemy выбирает ally, затем Wizard | Defeat acknowledgement, archived ally, Champion Wound/daily history |
| missing-departure | Ally → Wizard → enemy; initial frame не содержит attack_departures | Нулевая action/нулевая RNG technical stop; отдельный контроль стоимости preflight/unsupported, не типичный бой |

Первые два case имеют шесть explicit scene frames: три позиции enemy × полный live roster/archived defeated ally. Все пары и Zone ranges, directed approvals, departures, Give Ground и safe Recover facts задаются явно; соседство графа не подменяет доступность пути или дальность. Control имеет только initial frame. Неподдержанные эффекты не пропускаются ради длинного trial.

Defaults: 100 trials, master_seed=20261026, round_budget=4, repeats=3, top=12. Request использует прежнюю magic seed scheme. Положительные целые repeats/top, полный допуск всех requests и отсутствие активных tracemalloc/profiler проверяются до первого измерения. Бюджет раундов и seed/trials проверяют typed constructors.

## Измерение и сравнение

Для каждого case: warm-up min(3,N), R обычных wall repeats, отдельный tracemalloc run и отдельный cProfile run. При defaults это 503 trials на case / 1509 всего. Fixtures/imports, deepcopy input, source hashing, gc.collect, digest и equality checks вне таймера. В wall время входит только public sequential batch и summary projection. Режим GC не меняется. Во время исходных замеров не запускаются tests или другие наши тяжёлые проверки.

Все R+2 полных results и summaries равны первой обычной попытке; сравниваются source, каждый record и агрегаты. Равных counts при разных records недостаточно. Input и global RNG сохраняются. Чужой source, изменение observations или ошибка прерывают измерение; mandatory unsupported остаётся обычным отдельным outcome. Tracer/profiler очищаются при ошибках, чужая активная instrumentation отклоняется до работы. Для Python 3.12+ проверяется также занятый sys.monitoring.PROFILER_ID: cProfile может работать без sys.getprofile(), и его слот нельзя молча заменять.

Peak Python — incremental traced allocations одного отдельного batch, не RSS: fixtures и retained reference result созданы до tracemalloc. cProfile cumulative строки пересекаются; их нельзя складывать или выдавать profiled time за обычный wall time. Отчёт содержит все обычные времена/median, отдельный peak, cumulative/self profiles и dataclasses.replace callers.

Canonical trial digest: ASCII seed scheme + LF + строки `index|seed|outcome|actions|started|completed`, разделённые LF без завершающего LF; SHA-256. Digest служит компактным указателем observations; он не заменяет сравнение полных объектов и не доказывает происхождение dice.

Source manifest охватывает все `src/**/*.py`, включая untracked, и два файла `tools/profile_m8.py`, `tools/m8_benchmark_fixtures.py`. Relative POSIX paths сортируются, затем для каждого добавляются UTF-8 path + NUL + raw SHA-256 содержимого, после чего вычисляется общий SHA-256. До/после измерений manifest должен совпасть. Docs/tests/bytecode исключены. HEAD/dirty status/runtime/OS/CPU и команда записываются отдельно. Старый отчёт заменяется атомарно только после успешных измерений, сравнения, source guard и rendering.

## Проверки и граница выводов

Детерминированные tests проверяют fixtures/архив/routes, zero-action stop, полный результат при равных агрегатах, summary mismatch, порядок/число вызовов, preflight, cleanup, manifest и сохранение старого output при ошибке. Точные времена, память, проценты исходов и порог ускорения не являются test expectations.

Отчёт — локальный baseline, а не обещание process speedup, масштабируемости или оценка сложности боя. Контрольный case не усредняется с обычными боями. Доля unsupported показывается вместе с actions и started/completed; она не исключается из N. CPU affinity/частота и фоновая нагрузка ОС не контролируются; другие workloads/Python/ОС, RSS/память детей, process startup/serialization и балансировщик пока не измерены.

После baseline определить следующий ограниченный шаг по evidence: отдельный process transport/исполнение контракт при оправданной нагрузке либо конкретный эксперимент над выявленной повторной работой. Production оптимизация не принимается только по высокому cumulative времени; нужны равные результаты и отдельное воспроизводимое сравнение.
