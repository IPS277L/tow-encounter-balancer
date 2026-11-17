# ADR-0136: поиск по сохранённым пробам состава

Дата начала: 2026-11-17; завершено2026-11-18. Статус: проверен и отклонён, штатный поиск восстановлен. Sampler ADR-0135сохранён.

## Решение и альтернативы

ADR-0135 подтвердил действие числового sampler, но его stateless feedback не вышел из двух плато. Новая стратегия proposals хранит результаты проб одного шаблона и обязательно посещает края диапазона. Альтернативы — очередная локальная mutation-эвристика или увеличение Monte Carlo-бюджета; они не решают отсутствие экспозиции управляющего параметра. Это изменение solver целиком, не эксперимент для изоляции причинного вклада одной характеристики (Characteristic).

Public JSON/UI, бюджет C/E/V, score с приоритетом побед/затем раундов, stage battle seeds, правила и simulator неизменны. При C<4 или полностью неизменяемых применимых числовых диапазонах выполняется прежний путь ADR-0128 без нового RNG. Первая проба всегда прежняя. Дальнейшие proposals идут через отдельный calibration controller, живущий только в родительском поиске; workers получают прежний полный native source.

## Координата и шаблоны

Одна координата x∈[-1,1] задаёт `bias=float(x)` и `count=minimum+floor((x+1)/2*(maximum-minimum)+1/2)`. Позиции/середины хранятся точными Fraction. Это один ограниченный путь через count и числовые значения, не полный перебор их независимого произведения и не рейтинг силы. Каждый источник отдельно допускается и оценивается настоящим Monte Carlo.

Первый template содержит maximum NPC: начало — первая прежняя композиция, дополнение берётся из space.sample. Следующие templates целиком новые. RNG шаблона — `_seed(master,'calibration-template',lane_id)`, RNG resample — `_seed(master,'calibration-values',lane_id)`, каждый resample начинает этот stream заново. Снаряжение (Equipment), таланты (Talents) и способности (Abilities) сохраняются внутри template; count использует его prefix. Bias0исполняет существующий uniform choice API, ненулевой — weighted CDF. Поэтому pathwise монотонность не обещается даже при одинаковом seed.

В каждой lane не более5calibration попыток, включая дубликаты/unknown/неподвижные источники; затем новый template. Первые позиции+1и−1обязательны. Далее выбирается середина соседних испробованных позиций. Приоритет: нисходящий bracket с неперекрывающимися Wilson-границами относительно target; затем bracket по point estimates; затем интервал, примыкающий к лучшей supported observation; иначе самый широкий. При равенстве — ширина, затем левая позиция. Wilson здесь эвристика ранжирования, не доказательство направления или одновременный доверительный вывод после adaptive выбора. Все интервалы сохраняются, развороты не отсекаются.

Unknown — actual observation без p для bracket/выбора лучшего; остаётся в прежнем знаменателе/unsupported admission. Duplicate отмечает испробованную позицию без нового evidence и не расходует trials. После него ровно одна legacy попытка (даже если она duplicate), затем calibration продолжается. Общий attempts cap прежний. Если фактический template не имеет числовой свободы, текущая попытка использует legacy proposal, без ложного numeric evidence; предел5сохраняется. Отдельного скрытого retry нет.

Private proposal/harness metadata содержат lane/attempted position, включая no-freedom fallback; public result не получает новых полей. `calibration.attempts` считает все координатные попытки, `resampled_attempts` — фактический numeric sampler, `accepted` — недублированные numeric составы. Fallback observation не прикрепляется к координате. Developer capture возвращает тот же объект и не расходует RNG. Инварианты полного источника, уникальности композиций, budget/progress/cancel и independent validation прежние.

## Проверка до новых боёв

Детерминированные случаи: обязательные endpoints/count bounds, сохранение template facts/seed, хранение наблюдений и уточнение bracket, reversal/unknown/target0/1, duplicate без псевдоповтора/ровно один fallback,5attempts до смены lane, отсутствие freedom/C1/C<4 parity, полный budget/source/selection/progress/cancel. Отдельно текущие JSON/admission и один representative real spawn sequential/process equality. Сборка/full regression не требуются: native ядро/доставка не меняются. Независимое read-only ревью до реализации уточнило Wilson scope, отсутствие evidence у duplicate и bounded lane attempts; ревьюер боёв не выполнял.

## Замороженный условный эксперимент

После дешёвых проверок одна серия тех же шести входов melee/mixed/mixed-magic ×42/202, каждый6×8+2×32=112trials, всего672. Все шесть надо завершить без подгонки формулы или порогов после данных. Reference — сохранённая серия ADR-0130/sourcee470… с parity через ADR-0134/0135, не новый baseline run. Внедрение требует:6supported рекомендаций, корректный полный budget, proposal cap0/execfail0; unknown во всём каждом поиске≤reference0; mean absolute win error<25.520833п.п.; ≥2улучшения≥1/32, регресс каждой строки≤2/32; хотя бы один исходный stuck202выходит из100%ближе50%; суммарный search+encoding≤1.5×717.142504s. При missing recommendation macro всей шестёрки undefined, строку не исключать. Интервалы/раунды/остановки/фактические calibration probes показать отдельно.

При неуспехе закончить серию, сохранить таблицу/решение и вернуть только собственные solver/harness/tests к точному baseline snapshot `.cache/adr136/*.baseline.py`, сохранив sampler ADR-0135. Не выполнять дальнейшие дорогие candidate проверки. При успехе — fresh mixed505/112 baseline/candidate: рекомендация, unknown≤baseline, cap/errors0, win error≤baseline+1/32, время≤1.5×baseline. Только после успеха505 — прежний fullUI mixed-magic202/436: supported recommendation с error≤10п.п., search+encoding≤900s, unknown≤reference2; разрешённые typed stops только `pc_magic_miscast_unresolved`+`zone_hazard/random_transport/fascinating_rift/spell_recast/daemon_rift`. Это практические gates на ограниченной выборке, не доказательство глобального оптимума/общей устойчивости UI. Старый полный прогон/192-trial native контроль не повторять.

Source/harness hashes, baseline/candidate snapshots и raw artifacts сохраняются в `.cache/adr136/`; переносимые результаты и решение дополняются здесь. Commit/push выполняет пользователь.

## Проверки перед сравнением

60-test адресный запуск:59OK и один устаревший ожидаемый count в legacy resize test после ограничения этого теста планом C3. Исправлен только этот expected count; адресный повтор1OK/3.834s. Новая стратегия проверяется отдельными tests, legacy test сохраняет проверку удаления одного NPC и остальных профилей. Native full-source/budget/progress/cancel и12deterministic calibration tests пройдены (`model-validation.log`, `legacy-resize-validation.log`). Это составная проверка, не единый зелёный60-test run.

JSON/harness и новый representative real spawn calibrated search:33OK/27.190s (`json-process-validation.log`). Sequential/process результаты совпали, один pool закрыт. Read-only ревью блокеров не нашло; его замечание о невидимых no-freedom attempted positions устранено отдельной metadata без ложного evidence. Повтор затронутых12unit/14harness/1native trace:27OK/5.189s (`telemetry-validation.log`). Четыре actual encoded C1/nonnumeric результата42/202равны sampler baseline как полные JSON-объекты (`invariant-candidate.json`). Новых игровых source/версий/сборки нет.

Candidate source SHA-256`a684d234c04d50ce04651335879e7e2d99d98784571bc202c6b4c690c3068439`, harness `a7aceff4c8b8c7a7531ba6e28cc14a1a43eb468bcc997686d576152af8298b24`; `.cache/adr136/frozen.json` перечисляет snapshots. Серия запущена командой:

```powershell
$env:PYTHONPATH='src;.'
.venv/Scripts/python.exe -u tools/benchmark_dynamic.py --requests .cache/dynamic-stability-2026-11-17/melee-42.request.json .cache/dynamic-stability-2026-11-17/melee-202.request.json .cache/dynamic-stability-2026-11-17/mixed-42.request.json .cache/dynamic-stability-2026-11-17/mixed-202.request.json .cache/dynamic-stability-2026-11-17/mixed-magic-42.request.json .cache/dynamic-stability-2026-11-17/mixed-magic-202.request.json --output .cache/adr136/candidate-short.json
```

Один process-pool на поиск, тяжёлые серии последовательно. `compare_short.py` проверяет source/schema/accounting/metadata, уникальность и точное покрытие шести reference request IDs, затем все заранее заданные gates. Scripts/results/log/snapshots находятся в `.cache/adr136/`; основные результаты ниже сохраняются независимо от переноса cache.

## Полная серия и решение

Завершены все шесть входов, каждый112trials, всего672. Schema/source/accounting, уникальные request IDs и actual attempted positions проверены до и после возврата. Execution failure0, proposal cap0, duplicate0;30calibration attempts действительно выполнились и приняты, по5на запрос, в каждом только одна lane. Шесть первых legacy samples прежние; проверки ротации templates/fallback выполнены детерминированно, но в этой короткой MC-серии не потребовались. Score/C/E/V/kernel/формула не менялись во время измерений.

| Партия/seed | Победы reference→candidate, по32 | Wilson95% candidate | NPC candidate | Раунды reference→candidate | Search+encoding reference→candidate, s | Unknown во всём поиске |
| --- | --- | --- | --- | --- | --- | --- |
| Melee42 |19→14 (59.375→43.75%)|28.17–60.67%|7|7.688→7.500|105.893→96.159|0→0|
| Melee202 |32→20 (100→62.5%)|45.25–77.07%|7|4.281→8.125|31.125→81.724|0→0|
| Mixed42 |20→10 (62.5→31.25%)|17.95–48.57%|6|6.250→6.656|145.380→122.736|0→0|
| Mixed202 |19→5 (59.375→15.625%)|6.86–31.75%|6|8.500→6.406|150.188→105.734|0→0|
| Mixed-magic42 |23→4 (71.875→12.5%)|4.97–28.07%|10|6.094→4.906|194.597→213.741|0→1|
| Mixed-magic202 |32→11 (100→34.375%)|20.41–51.69%|10|3.531→5.625|89.959→178.935|0→0|

Mean absolute win error25.521→20.833п.п.,3улучшения≥1/32; оба stuck202вышли из100%. Но mixed202ухудшил error на25п.п., mixed-magic42на15.625п.п., превысив разрешённые6.25п.п. У mixed42регресс ровно6.25п.п., на допустимой границе. Кроме того, unknown в mixed-magic42вырос0→1. Провалены per-cell/unknown gates, поэтому стратегия **отклонена**. Улучшение среднего не стало основанием ослабления заранее заданных условий.505и fullUI202не запускались; формула после данных не перенастраивалась.

В magic42близкий к цели9NPC-финалист получил17/32побед, но также1`UNSUPPORTED_PATH` и потому исключён. Остановка — `pc_magic_miscast_unresolved/zone_hazard`, actor`mage`, validation0/trial17, total33; seed/source находятся в raw artifact. Его win completion range[17/32,18/32], а не объявленные поражением неизвестные исходы. Рекомендацией стал supported10NPC с4/32побед. Во время промежуточного сообщения17/32преждевременно были названы улучшением до полного accounting; итоговое решение использует только допустимую рекомендацию.

Всего в разных составах363победы,304поражения,4round-limits,1unknown. Это accounting672боёв, не оценка одной общей вероятности. Все4limits относятся к melee42/mixed42, по2; длительность сохраняет censored prefixes. Для каждой рекомендации выше unknown0. Интервалы широкие и условны на данном источнике/тактике; сравнение нескольких адаптивно выбранных составов не доказывает универсального улучшения или монотонности.

Стоимость search+encoding717.143→799.029s,13.32мин; cost gate≤1075.714s пройден, но ускорения нет. Diagnostic replay не входит в это время. В mixed202проверены counts3/10/1/6/3/4; после последней пробы остался непроверенный промежуток между координатами с count4и6. Это наблюдаемый недостаток разрешения при5calibration probes, **не доказательство**, что count5или дополнительная проба дали бы цель. Другая проблема — исключение перспективного финалиста из-за неподключённой магии. Причины не исправляются подменой unknown на поражения или угадыванием книжного продолжения.

## Возврат и следующий шаг

После завершения process-сессии проверено совпадение live-кода/tests с frozen candidate snapshots, затем пять существовавших файлов восстановлены побайтно из собственных baseline copies. Два новых experimental test modules удалены из runtime; сохранены в `.cache/adr136/*.candidate.py`. Прежний sampler/API/9unit tests ADR-0135и diagnostic proposal helper ADR-0134остались. Source снова `1beb53fc42061ebe2ea88db2f6351096acfde6a5167dbccfc7dff9368064bdae`; `restored-verification.json` фиксирует exact snapshot/source/accounting checks. Остальные прежние dirty файлы пользователя не восстанавливались/не изменялись.

```powershell
$env:PYTHONPATH='src;.'
.venv/Scripts/python.exe -m unittest tests.unit.test_numeric_composition_sampling tests.unit.test_proposal_schedule tests.unit.test_directed_count_proposals tests.unit.test_dynamic_encounter_progress tests.integration.test_dynamic_encounter tests.unit.test_dynamic_benchmark -q
```

После возврата **59OK/14.761s**, вне sandbox из-за Windows TEMP harness (`restored-validation.log`). Успешные JSON/process проверки до серии не повторялись: runtime возвращён точно; full/wheel без нового риска не нужны. Архив измерений — `candidate-short.json`, log и `short-comparison.json`; для точного повтора на другой машине переносить cache отдельно. Переносимые итоги/формулы/gates остаются здесь.

Следующий шаг — сначала дешёвая проверка того, как бюджет делится между покрытием диапазона, уточнением и независимой validation. Проверять на детерминированных функциях с узкой областью цели, плато, разворотом и unknown, с явным условием достаточного разрешения. Это подготовка отдельного протокола, не разрешение повторно подогнать ADR-0136под шесть известных строк. Затем выбирать один solver/allocation experiment и замораживать новые критерии до боёв. В этой функции бюджет/порог допуска/score менять после отрицательного результата не стали; гарантии, что больше проб решат проблему, нет. Runtime/UI сохраняют ADR-0128; новых публичных полей и игровых правил нет.
