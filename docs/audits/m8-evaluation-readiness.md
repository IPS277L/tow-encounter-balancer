# M8: аудит оценки явного magic-списка

Дата: 2026-10-27. **Bounded magic evaluation [ADR-0040](../decisions/ADR-0040-magic-candidate-assessment.md) готов в прежнем single-run scope ADR-0037.** Проверены пять production modules, 39 implementation tests, самостоятельный public example и установленный wheel. Новых игровых правил и исправлений production не потребовалось.

На старте HEAD c8f1f84 и 15 existing dirty/untracked файлов предыдущего service-среза. Они учтены как исходные: service/error и их tests сохранены побайтно, общая документация синхронизирована. Добавлены пример/output, новый test-файл с двумя tests и этот аудит. Commit/push не выполнялись.

## Матрица готовности

| Обязанность | Реализация и evidence |
| --- | --- |
| Pure assessment | [Models](../../src/towr/balance/magic_assessment_models.py), [helper](../../src/towr/balance/magic_assessment.py), [11 unit tests](../../tests/unit/test_m8_magic_assessment.py): typed magic input/summary/shared window, full-source equality и equal copies без rebinding, frozen/replace, отказ других families/full result. Нет runner/RNG/pool или records/journals |
| Метрика и окно | Четыре native Fraction count / все N; actions/started/completed остаются в summary. Inclusive/point/outside/all-limit/large-N проверены; любой unsupported даёт UNSUPPORTED_OBSERVATIONS/window_match=None, даже при goal внутри окна. ELIGIBLE не означает попадание в окно или полноту тактики |
| List/preflight | [Models](../../src/towr/balance/magic_evaluation_models.py), [15 tests](../../tests/unit/test_m8_magic_evaluation.py): strict tuple/list без потребления generator, exact IDs, typed scenarios, общий perspective_side/scenario.max_rounds, uint64 seed/N и positive exact int budget/top_k. Полный C×N до execution; произведение может превышать uint64. Replace пересобирает derived requests |
| Полный report/ranking | Все rows ровно один раз в исходном порядке, exact IDs/full source/window; equal copies допустимы. Только window_match=True, stable Fraction distance/top_k; outside/unsupported остаются в report, пустой selection без nearest fallback. Проверены same-ID Wizard/profile/frames, rename/reorder/ties/large-N, immutable/pickle aggregate-only ownership |
| Service | [Evaluator](../../src/towr/application/magic_evaluation_service.py), [9 unit tests](../../tests/unit/test_m8_magic_evaluation_service.py): typed request/options до runner, один полный existing run на кандидата, explicit backend/options, typed full source до summary, исходный parent request в report. Weakref подтверждает освобождение полного result до следующего runner |
| Ошибки | [MagicBalanceEvaluationError](../../src/towr/application/magic_evaluation_errors.py) сохраняет candidate ID и original cause/worker notes. Нет partial/retry/fallback/следующего кандидата. Summary/assessment/row failures оборачиваются, preflight/final constructor и BaseException проходят напрямую. Traceback может удерживать объекты; мгновенный kill/rollback не обещается |
| Real integration | [1 assessment integration](../../tests/integration/test_m8_magic_assessment.py), [3 evaluation integration](../../tests/integration/test_m8_magic_evaluation.py): полные sequential/spawn reports, child PID, repeat/reorder/rename, input/global RNG/children, startup failure. Scripted N4 counts1/1/1/1 totals24/10/9 и независимый N3 counts1/1/1/0 totals23/9/9 проверяют unsupported=None против supported=True без фильтрации N4 |
| Слои и shared types | Balance получает только input/summary, application использует existing simulation. ObjectiveRateWindow и SimulationExecutionOptions не копируются/переносятся; class/import/pickle paths и прежние families/JSON/CLI сохраняются. Внутренние слои не импортируют application/balance; generic scheduler/event bus/cache не добавлены |

Счёт реализации: **39 tests** (11 assessment unit + 1 integration + 15 list + 9 service unit + 3 integration). Два новых example tests дают **41 test текущего bounded evaluation**. Исторический assessment contract probe/test считается отдельно: с ним 42, он не заменяет production guards. AST-проверка 311 domain/engine/rules/simulation modules и новых balance/application modules не выявила нарушений импортов. Независимый read-only reviewer сверил контракт/код/tests/example/книги, блокеров нет.

## Самостоятельный production-пример

[magic_evaluation.py](../examples/m8/magic_evaluation.py) использует public APIs и два соседних builders: magic_simulation.py и magic_scenario.py. Bundle не импортирует tests/tools/private helpers. Один authored Champion-Wizard Level2/Casting3d/3/Willpower3d/3/RES4, союзный и вражеский Shooting Minions3d/3/Dam3/RES3. Scene frames/ranges/departures, Curse Give Ground/Broken Recover, Staggered→Wound и GM-approved knockout заданы явно; исходные профили не объявляются книжными именованными NPC.

Две альтернативы меняют только enemy target priority: ally-first и wizard-first. Seed42, B4, N8 на кандидата, planned/max16, окно [1/4,1/2,3/4], top_k2. Полные sequential и process workers2/batch3 reports и selected IDs равны; исходный parent request и каждый derived simulation source, input/global RNG/children сохраняются. **32 trials на запуск примера**. Stdout публикуется только после двух успешных evaluations и всех проверок.

[Stored output](../examples/m8/magic_evaluation.output.txt) — локальное seeded наблюдение текущего runtime:

| Кандидат | goal / defeated / limit / unsupported | actions / started / completed | status / window_match |
| --- | --- | --- | --- |
| ally-first | 6 / 0 / 0 / 2 | 39 / 17 / 15 | unsupported_observations / None |
| wizard-first | 8 / 0 / 0 / 0 | 37 / 15 / 15 | eligible / False |

Selection пуст: первый непригоден из-за unsupported при goal=3/4, второй вне окна при goal=1. Это корректный полный report, не обещание подходящего состава. Пример не закрепляет winner/Monte Carlo процент; точные числа в сохранённом выводе не становятся метрикой истинной вероятности.

[Два новых integration tests](../../tests/integration/test_m8_magic_evaluation_example.py) — **OK (1,148 с)** после усиления проверки отсутствия AssertionError в stderr: внешний cwd с тремя скопированными файлами даёт stored stdout/empty stderr. Отдельный entry-point test завершает реальные 8 trials первого кандидата, затем второй отказывает: marker подтверждает первый пакет, stdout пуст, stderr содержит wizard-first/OSError/original note; original cause/notes проверены, process не запускается. Старые implementation tests не менялись.

## Установленный пакет

Свежий offline wheel собран в отдельной временной копии pyproject/README/LICENSE/src, без PDF/tests и repo egg-info мутаций; README завершён до build. Установка в отдельный venv без зависимостей через локальный pip, без network. Все **416 Python/Schema files** побайтно равны current src, wheel и installed package; imports package/service/models указывают на installed site-packages.

Трёхфайловый bundle вне repo, без PYTHONPATH и с отключённым user site, дал stored stdout/empty stderr. Late-failure entry point также проверен на installed tree после первого полного N8 run: пустой stdout, candidate ID/cause/notes, отсутствие process/fallback, global RNG/children сохранены. Это package correctness, не installed-wheel performance.

Wheel SHA-256: `d0149ddb08433be68cab5114d5d0d0b98bf18f7bc168b4b04b4525fcfa50ccd3`. Build/install/stdout/failure logs: `/private/tmp/towr-m8-evaluation-audit-s9x3qy98`; report `/private/tmp/towr-m8-evaluation-wheel-report.json`. Временные evidence не нужны для использования проекта и не входят в Git.

## Книги, воспроизводимость и ограничения

Локальные извлечённые страницы прямо перечитаны независимым reviewer; main дополнительно сверил builders и Casting/NPC policies. Нормативные основания:

| Источник | Сохранённая граница |
| --- | --- |
| BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр.112 | Turn/action, полный ход перед следующим actor; лимит/N/окно — технический контракт |
| Та же книга, Conditions / Broken, стр.122 | Уход/Recover не равны defeat |
| Та же книга, Magic in the Old World / Casting a Spell / Interrupted Casting, стр.156; Spell Potency / Miscasts and the Rule of Nine, стр.157 | Casting/action/накопление, последний Test для Potency и обязательный Miscast; evaluator не очищает pending ради продолжения |
| Та же книга, Battle Magic / Curse of Cowardly Flight, стр.162 | Give Ground если возможно, затем Willpower против Potency; existing chain сохраняется |
| Та же книга, Wounds Table, стр.190–191 | Champion Wounds и обязательные effects, Stomach Blow expiry и lethal rows не смешиваются |
| BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions и Champions, стр.91–92 | Minion defeated от Wound с attacker/GM disposition; Champion использует Wounds Table |

Новых Rule IDs/house rules нет. Ранее открытые Miscast ambiguities остаются открытыми. Magic scope ADR-0037 не расширен: неподдержанные Wound/Miscast/chronology, обычный Attack Give Ground и неизвестные scene/route дают отдельный unsupported, не фильтруются и не становятся draw/loss. Broken/другая Zone не defeat.

Structural/source guards проверяют согласованность агрегатов, не происхождение вручную собранных observations. Point estimate и даже отсутствие unsupported в N не доказывают точность или полноту. Равные seeds альтернатив не означают одинаковые броски соответствующих действий; воспроизводимость требует тех же source/rules и совместимого RNG/runtime. Полный каталог, PC, новые spells/consumers и универсальная тактика не готовы.

Память application — один полный пакет плюс исходный список всех inputs и aggregate rows завершённых кандидатов; budget не RSS cap. Cleanup underlying pool ждёт running работу. Нет persistent pool, auto backend, новых caches, streaming/resume или rollback side effects. Успешный report не удерживает records/journals, но error traceback может их удерживать.

Текущий source/harness manifest **401 file / `ac055c19711c8d2f124931f3b07c3ff7dbadeb51829bf785544980cbaebb0ec1`** не изменился в аудите. Исторические performance reports имеют manifest 396 files до пяти новых balance/application modules; raw hash не ожидается равным текущему. Simulation/engine/fixtures/tools не менялись, benchmark не повторялся. Старые локальные speedup observations не объявляются замерами evaluator или установленного wheel.

## Проверки и следующий шаг

Полная регрессия до one-line parent assertion в новом test: **3204 tests / 33 прежних errors (100,650 с)**. После усиления error-path guard повторены только два новых tests: OK (1,148 с); runtime и программа example не менялись. Counter полных error headers/signatures точно равен предыдущему baseline; новых ошибок нет, полный набор не зелёный. Compileall, 3011 локальных Markdown-путей, 75 anchors, import boundaries/public imports/whitespace — OK; начальные четыре Python-файла сохранены побайтно. Команды и файловые проверки — в [статусе](../project-status.md#последняя-проверка).

Следующий законченный шаг — **ADR-0041 и finite probe поэтапной оценки явного magic-списка**, по образцу ADR-0032/M7: typed stages/request/result/status, верхний бюджет полных повторных пакетов, отдельные intermediate continuation/final selection, exact source/report chain и stage/candidate errors. Сначала контракт/probe, затем implementation. Prefix reuse, generation, JSON/CLI, confidence presets и новые gameplay consumers не входят в текущий аудит и не добавляются автоматически.
