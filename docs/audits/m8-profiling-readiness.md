# Аудит первого profiling-среза M8

Дата: 2026-10-26. **Контракт, developer harness и исходный sequential baseline завершены.** Основание: [ADR-0038](../decisions/ADR-0038-independent-magic-simulations.md), [контракт измерения](../benchmarks/m8-profiling-contract.md), [сырой отчёт](../benchmarks/m8-baseline-2026-10-26.md). На старте рабочее дерево чистое, HEAD `908bb28` (M8 P5). Production src, прежние tools/tests и игровые правила не менялись; commit/push не выполнялись.

## Реализация и проверка

- [Fixtures](../../tools/m8_benchmark_fixtures.py) строят три свежих admitted authored inputs только через public APIs, без imports tests/docs/probes. Первые два имеют шесть frames с полным spatial archive и разными приоритетами enemy; третий — отдельный zero-action missing-departure control.
- [Harness](../../tools/profile_m8.py) измеряет public sequential batch + pure summary: warm-up, обычные wall repeats, отдельные tracemalloc и cProfile. Input/global RNG и все полные results/summaries проверяются после измерения. Full-record mismatch отвергается даже при равных агрегатах.
- Manifest охватывает все src/**/*.py, в том числе untracked, и оба новых tools файла; совпал до/после. Runtime/revision/dirty status, полная команда и canonical trial digests сохранены. Docs/tests/bytecode не входят в manifest.
- Report заменяется атомарно после успешных source guards/rendering; injected failures сохраняют старый output и удаляют temp. Чужие tracer/profiler отклоняются, инструменты не перекрываются и очищаются при exceptions/BaseException.
- Tests выявили runtime-особенность Python 3.12: cProfile может использовать sys.monitoring при пустом sys.getprofile(). Guard дополнен проверкой PROFILER_ID; настоящий nested-cProfile test доказывает отказ без отключения инструмента caller.

[10 fixture tests](../../tests/unit/test_m8_benchmark_fixtures.py) — OK (0,025 с): strict admission, six-frame archive/ranges/departures, Curse/Broken Recover, defeated ally → оба Curse destinations, lethal Champion Wound/daily chain, zero-action stop и input/global RNG. [24 harness tests](../../tests/unit/test_m8_profiling.py) — OK (0,315 с): preflight, отдельные фазы и mismatch каждой, source до baseline, input/global mutation, type/range, canonical digest и отдельное влияние каждого round counter, manifest/content/rename, cleanup, main failure/atomic output preservation. Порог времени/памяти и точный Monte Carlo-процент не используются как test oracle.

## Исходные измерения

CPython 3.12.15 / macOS 26.5.1 arm64, GC включён; CPU affinity/частота/нагрузка ОС не контролировались. N=100, master_seed=20261026, round_budget=4, три обычных повтора. Для каждого case ещё отдельные trace/profile и warm-up 3; всего 15 полных measured batches / 1500 trials + 9 warm-up = **1509 trials**. Наши tests/другие тяжёлые проверки в это время не запускались.

| Case | Median, с | Диапазон обычных повторов, с | Peak Python, KiB | achieved / defeated / limit / unsupported | actions / started / completed |
| --- | --- | --- | --- | --- | --- |
| curse-routes | 0,184446 | 0,184265–0,184602 | 773,7 | 73 / 0 / 7 / 20 | 539 / 215 / 195 |
| champion-pressure | 0,215089 | 0,213970–0,215270 | 953,2 | 57 / 0 / 32 / 11 | 620 / 264 / 253 |
| missing-departure | 0,015296 | 0,015219–0,015488 | 254,6 | 0 / 0 / 0 / 100 | 0 / 100 / 0 |

Все пять результатов/summary каждого case равны; остановки не фильтруются из N. Control оценивает только технический путь без actions/dice и не усредняется с боями. Отсутствие perspective defeat в этой конкретной seeded выборке не удаляет исход: реальная lethal цепочка покрыта deterministic fixture tests.

Source/harness SHA-256: `2d2444c68b9152843ea92f1048c41881e0f76fcceb561012c372509591736bc4`.

| Case | Canonical trial digest |
| --- | --- |
| curse-routes | `260c6eba6f0a45615e078224a2693028f0d530a0b893e06f518ac3cef1512548` |
| champion-pressure | `681692c90a31024d414694ebd4a50f0c2064986a4703435ac7472e841b9344c8` |
| missing-departure | `d45396b2f9b131dd6fea7573b5664e228e121e5f8da28cfed8ca2e292def42f4` |

cProfile показывает 25718/30325 total dataclasses.replace calls для двух боевых inputs. NpcMagicStep.after вызывается 4184/4927 раз с cumulative 0,211/0,248 с; вложенные state/round projections повторно строят validated snapshots. Эти cumulative времена пересекаются и не складываются. Это указатель для возможного отдельного эксперимента, не доказательство wall speedup от cache или основание ослабить guards. Production caches не добавлены.

## Регрессия и источники

Полный набор после измерений: **3114 tests / те же 33 errors, 100,078 с**. Counter полных error headers и exception signatures точно равен baseline ADR-0038; новых ошибок нет. Старые dataclasses expectations Python 3.12 остаются отдельной задачей, полный suite не зелёный. Лог: `/private/tmp/towr-m8-profiling-tests.log`; [подробности baseline](../open-questions.md#проверки-dataclasses-на-python-312).

```sh
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m tools.profile_m8 --trials 100 --master-seed 20261026 --round-budget 4 --repeats 3 --top 16 --output docs/benchmarks/m8-baseline-2026-10-26.md
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest discover -s tests -q
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m compileall -q src tests tools
```

Прямо перечитан локальный текст PG1.4 Rules / Combat, стр. 112; Battlefield/Range/Speed/Actions/Recover/Giving Ground, стр. 114–119; Conditions / Broken, стр. 122; Magic in the Old World / Casting/Potency/Miscasts, стр. 156–157; Battle Magic / Curse of Cowardly Flight, стр. 162; Wounds Table, стр. 190–191; GM1.1 Allies and Antagonists / Minions/Champions, стр. 91–92. Числа и routes — authored experiment facts, не профиль книжного NPC. Новых Rule IDs/house rules и решений старых Miscast ambiguities нет. Независимые агенты проверили источники, fixtures, harness/tests и интерпретацию отчёта; после исправления monitoring guard блокирующих findings нет.

Compileall, 2738 локальных Markdown-путей и входящие status/question anchors, public-import AST, whitespace и сохранность прежних production/tests/tools — OK. Итог — в [актуальном статусе](../project-status.md#последняя-проверка). Другие ОС/Python, installed wheel, RSS, большие N и process costs в этом performance-срезе не проверялись; предыдущая wheel parity ADR-0038 не является benchmark нового harness.

## Следующий ограниченный шаг

Подготовить отдельный контракт опционального magic process transport/spawn и finite probe: несколько indexed trials и настоящий spawn round-trip, без production executor или cache changes. Учесть полный scenario внутри magic records: проверить full source после pickle и определить нормализацию равных worker source copies к общему исходному input родителя, сохранив seeds/order/четыре исхода/fail-fast/cleanup.

Исходные 0,18–0,22 с на 100 trials сами по себе не обосновывают ускорение процессами. После проверки transport потребуется отдельное сравнение большего N с учётом startup/serialization/shutdown. Новая оценка сложности, balance/generation и JSON/CLI остаются отдельными дальнейшими контрактами.
