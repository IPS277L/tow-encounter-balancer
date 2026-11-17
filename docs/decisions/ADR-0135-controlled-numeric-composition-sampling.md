# ADR-0135: управляемое распределение числовых параметров состава

Дата: 2026-11-17. Статус: sampler принят как Python API; автоматический feedback проверен и отклонён. Формула и gates записаны до измерений.

## Модель и границы

Локальные изменения/перестановка операторов ADR-0131–0134не улучшили подбор. Проверяется управление числовыми параметрами всего состава внутри существующего `NpcSearchSpace`. Новый sampling control не является рейтингом силы NPC или книжным правилом монотонности; каждый полученный состав оценивается настоящим симулятором.

`space.resample_numeric(composition, rng, bias=0.)` возвращает frozen `NumericCompositionSample(composition, bias, variable_fields, changed_members)`. Вход — непустой tuple допущенных GeneratedNpc; bias — точный int/float, кроме bool, finite[-1,1]. Всё проверяется до RNG. Оружие/броня/щиты/способности/таланты (Weapons/Armour/Shields/Abilities/Talents) и подтверждённые ranged scene facts сохраняются. Меняются только WS/S/T/Agility/Melee/Athletics/Defence, а у стрелков BS/Shooting/I/Dexterity; прежний native builder выводит производные значения.

Для каждого поля сначала строятся все допустимые полные источники через прежние GeneratedNpc guards, включая текущее значение; Talent Requirements не снимаются. Допустимые значения сортируются численно. При n>1 вес значения ранга i равен `exp(log(9)*bias*i/(n-1))`. Bias+1даёт отношение весов максимума/минимума9,−1обратное,0равномерную выборку. Ненулевой bias использует explicit RNG random/CDF,0—choice; singleton допустимого поля RNG не расходует. Ни один допустимый вариант не получает нулевой вес. Старые sample/mutate не меняются; новый neutral resample — uniform, не обещание no-op. `variable_fields` считает позиции с несколькими допустимыми значениями; `changed_members` — отличающихся NPC.

Снаряжение (Equipment) и Таланты (Talents) сохраняются буквально, но ограничения могут сужать числовой диапазон, например WS≥3у Defensive Stance. Индивидуальные выборки используют переданный stream без принудительного клонирования NPC; случайные совпадения разрешены. Неизменяемое числовое пространство возвращает прежние значения без RNG. Это явная модель текущих компонентов, без общего DSL.

## Проверки до native контроля

- Exact endpoint weights на детерминированных13midpoint tickets для3значений:1/3/9и9/3/1; numeric sorting, диапазон/невалидный bias, requirements, ranged confirmations, сохранение input/RNG при неизменяемом пространстве, воспроизводимость/изменение нескольких NPC.
- Actual native admission нескольких составов; четыре прежних C1/nonnumeric JSON controls равны original, так как обычный sampler/поиск пока не используют новый метод. Параллельных тяжёлых прогонов нет; full/wheel без нового риска не нужны.

## Заранее заданный native gate

Три прежние партии melee/mixed/mixed-magic, NPCcount10. Для каждой один neutral template через текущий sample/Random606; низкий и высокий варианты получают resample bias−1/+1с Random707. Native battle master808,32trials каждый, process4/batch1: всего192боя. Эти seeds не использовались для выбора модели. Полные источники допускаются до запуска, пары сохраняют party/count/gear/talents/facts/actor IDs, меняя только numeric source и производные значения. Trial indices используют одинаковые seeds внутри пары; это разные бои, не192независимых оценок одной вероятности. Дополнительные бои ради смены коэффициента не запускаются.

Прогресс/полные native JSON results и ordered trial records сохраняются. Показать outcomes с denominator32, Wilson для confirmed wins, mean started rounds/censored prefixes, фактическое время и все unknown. Неизвестные исходы не считаются поражением: для каждой выборки completion range `[wins/n,(wins+unknown)/n]`.

Для продолжения нужны: все192trials без execution failure, source/schema/seed/accounting согласованы; минимум в двух партиях `(wins_low-wins_high-unknown_high)/32 >= .25` и одновременно `party_defeated_high-party_defeated_low >= 4`. Ни в одной `(wins_high-wins_low-unknown_low)/32 > 2/32`. Успех не должен объясняться только добавлением round-limits. Это практический gate направления эффекта на данной выборке, не статистическое доказательство монотонности; undefined GM Miscasts остаются видимыми. Если gate не пройден — сохранить результаты, модель не объявлять управлением сложностью, вернуть свой snapshot; коэффициент9не подбирать после данных.

При успехе sampler как проверенная Python-функция может остаться независимо от следующего feedback-кандидата; source baseline после модели фиксируется отдельно. Наличие sampler не объявляется улучшением штатного генератора/UI.

## Интеграция одного feedback-оператора при успешном gate

Только прежняя component-ветка меняется на numeric resample всего выбранного parent состава. Parent/elite выбираются прежним способом. Если parent unsupported или win rate точно равен target — прежняя single-NPC mutation. Иначе bias=`(parent.win_rate-target)/max(target,1-target)`, всегда[-1,1]. При отсутствии числовой свободы — прежняя single-NPC mutation без дополнительных RNG; если свобода была, но случайно выпали прежние значения, работает обычный duplicate/cap. Restart/count/старый selector ADR-0128, score, C/E/V, stage seeds/kernel не меняются. Нет памяти bias между поисками, нового JSON поля или скрытой policy расписания.

Private proposal metadata/developer metrics заполняют sampling_bias/changed_members для фактического resample, иначе nullable поля имеютNone; public result по-прежнему хранит полный native source. C1 сохраняет прежний результат. Это один новый компонентный оператор, не сохранение отклонённых policies как второго фактора. Динамические варианты снаряжения/талантов продолжают создаваться прежними restart/count sampling и legacy mutation fallback; активный numeric resample их фиксирует внутри выбранного parent.

После deterministic/JSON/real-process проверок — те же шесть112-trial inputs42/202. Условия внедрения прежние:6рекомендаций, budget/cap/errors корректны, unsupported≤reference0в каждой строке; macro absolute win error ниже reference, минимум2улучшения≥1/32, регресс каждой≤2/32; хотя бы один исходный stuck202выходит из100%ближе50%; search+encoding≤1.5×исторического717.143s. Все пары/активация/стоимость видимы. При провале закончить серию, откатить feedback к проверенному sampler baseline, не запускать505/full candidate и не менять bias формулу.

Только при успехе — frozen baseline/candidate mixed505/112: рекомендация, unsupported≤baseline, cap/errors0, win error≤baseline+1/32, время≤1.5×baseline. Затем при успехе — прежний fullUI mixed-magic202/436: supported recommendation с point win error≤10п.п., search+encoding≤900s, unsupported≤reference2. Причины ограничены уже наблюдавшимися парами `pc_magic_miscast_unresolved`+`zone_hazard/random_transport/fascinating_rift/spell_recast/daemon_rift`; другие stops/errors gate не проходят. Новый observed daemon_rift из ADR-0134включён до этих измерений. Unknown исключают конкретный состав по прежней политике; один full seed не доказывает общего качества.

Исторические source/harness hashes, original/model baseline/candidate snapshots и artifacts `.cache/adr135/` фиксируются отдельно; parity нейтрального поведения не выдаётся за новые боевые reference-прогоны. Результаты/решение — здесь, текущий этап/следующий шаг — в статусе. Commit/push выполняет пользователь.

## Подготовка модели

Original source `e7b98831ffef2c1174f89b39c6be22ae65efa01806da5ffc467b73c817375467`; модель без feedback-интеграции `1beb53fc42061ebe2ea88db2f6351096acfde6a5167dbccfc7dff9368064bdae`. Старые sample/mutate/proposal selector не изменены, новые методы пока не используются обычным поиском.

`tests.unit.test_numeric_composition_sampling tests.unit.test_proposal_schedule tests.unit.test_directed_count_proposals tests.unit.test_dynamic_encounter_progress tests.integration.test_dynamic_encounter -q`:45OK/10.115s (`model-validation.log`). Девять новых deterministic tests включают exact13tickets, numeric sorting, neutral choice, requirements, gear/ranged source preservation, input/admission до RNG, metadata/воспроизводимость/несколько изменённых NPC. Четыре actual full JSON C1/nonnumeric42/202равны original (`invariant-original.json`/`invariant-model-final.json`); обычному генератору не приписывается эффект нового sampler.

Все шесть control sources предварительно допущены через native parser, в каждом изменились10из10NPC, сохранились equipment/Talents/abilities/conditional ranged confirmations. Harness `.cache/adr135/native_control.py` сохраняет source/results/ordered trial records и фейл-диагностику до интерпретации. До первого боя допускается вся серия; source/harness заморожены.

```powershell
$env:PYTHONPATH='src;.'
.venv/Scripts/python.exe -u .cache/adr135/native_control.py
```

Один pool4/batch1на серию, источники исполняются последовательно; real spawn вне sandbox из-за Windows pipes. Native run/encoding/diagnostic replay/total time различаются. Промежуточный artifact `.cache/adr135/native/measurements.json`, log `.cache/adr135/native-control.run.log`. Diagnostic unknown replays ограничены первыми3на source, все исходы остаются в records/агрегатах; выборка не объявляется списком всех причин, если их больше.

## Native gate: результаты и сохранённая функция

Все192trials завершены:59побед игроков,133поражения,0round-limit/unknown/execution failure. Это сумма разных составов, не59/192оценка одной вероятности. Полные текущие native JSON/source echo,32ordered indices/seed каждого source, неизменность party/count/gear/Talents/facts и accounting проверены `verify_native.py`; результат `native/verification.json`.

| Партия | Победы low→high, по32 | Поражения low→high | Mean started rounds low→high | Wilson95% low / high |
| --- | --- | --- | --- | --- |
| Melee |18→0 (56.25→0%)|14→32|8.156→2.719|39.33–71.83% /0–10.72%|
| Mixed |4→0 (12.5→0%)|28→32|7.406→2.469|4.97–28.07% /0–10.72%|
| Mixed-magic |32→5 (100→15.625%)|0→27|3.844→4.625|89.28–100% /6.86–31.75%|

Gate пройден в2из3пар: снижение confirmed-win fraction56.25/84.375п.п., рост поражений18/27; у mixed снижение12.5п.п. при дополнительных4поражениях не достигло порога. Обратного эффекта в этой выборке нет; контроль с unknown проверял бы лишь нижнюю границу неизбежного reversal, не отсутствие любого возможного reversal и не статистическую значимость. Здесь unknown0. Все source содержали десять NPC с разными числовыми выборками; изменение только числового состава действительно влияет на исходы в рамках данного native контроля, а не только на остановки по лимиту.

Это не гарантия достижения50%во всех исходных составах. В mixed даже low-выборка дала мало побед; остаются count/equipment/Talent constraints, случайность конкретного шаблона и широкие32-trial интервалы. Случаи/seed частично связаны общими streams и не являются независимыми подтверждениями общего качества.

Сумма native run289.292s, encoding0.774s; общий контроль с одним pool/IO занял290.662s (4.84мин). Diagnostic replays не потребовались. Sampler как проверенная Python-функция сохраняется независимо от исхода следующего feedback-эксперимента; default/UI улучшение из этого контроля не следует. Model baseline source `1beb53fc42061ebe2ea88db2f6351096acfde6a5167dbccfc7dff9368064bdae`, snapshots `*.sampler-baseline.py` в `.cache/adr135/`.

## Подготовка feedback-кандидата

Candidate source `bc56963dab578fd32f85435e477abdbc05cda1478f670f15537f3da9efb078b0`. Diff против sampler baseline ограничен component body, helper bias и private metadata. Политики count/restart/selector и текущие native rules не менялись; old sampler/solver функции sampler baseline имеют тот же AST, что sourcee7b988… до добавления API (`model-baseline-neutrality.json`). Исторические game results sourcee470… сопоставляются через прежнюю extraction parity ADR-0134и текущую neutral parity, не объявляются новым измерением baseline.

- `tests.unit.test_numeric_composition_sampling tests.unit.test_proposal_schedule tests.unit.test_directed_count_proposals tests.unit.test_dynamic_encounter_progress tests.integration.test_dynamic_encounter -q`:48OK/9.984s, `feedback-validation.log`.
- `tests.unit.test_dynamic_benchmark tests.integration.test_dynamic_encounter_json tests.integration.test_dynamic_process_json.DynamicProcessJsonSmokeTests.test_spawn_matches_sequential_result_and_preserves_source_echo tests.integration.test_dynamic_process_execution.DynamicProcessExecutionTests.test_real_spawn_pool_is_reused_and_matches_both_sequential_sources -q`:36OK/30.233s, `feedback-json-process-validation.log`.
- Четыре полных actual C1/nonnumeric JSON совпали с original (`invariant-feedback.json`). No freedom fallback сохраняет прежний RNG, unknown/точныйtarget — прежнюю mutation. Metadata показывают actual cohort attempts/accepted/changed members/multi-member attempts; ничего не добавлено в public JSON/UI.
- Независимое read-only ревью подтвердило модель/нативный контроль, затем feedback от реально выбранного parent, сохранение остальных операций и declared fallback; тяжёлые прогоны ревьюер не выполнял.

Формула/источники/harness заморожены, серия исполняется без overrides:

```powershell
$env:PYTHONPATH='src;.'
.venv/Scripts/python.exe -u tools/benchmark_dynamic.py --requests .cache/dynamic-stability-2026-11-17/melee-42.request.json .cache/dynamic-stability-2026-11-17/melee-202.request.json .cache/dynamic-stability-2026-11-17/mixed-42.request.json .cache/dynamic-stability-2026-11-17/mixed-202.request.json .cache/dynamic-stability-2026-11-17/mixed-magic-42.request.json .cache/dynamic-stability-2026-11-17/mixed-magic-202.request.json --output .cache/adr135/candidate-short.json
```

## Все шесть поисков: feedback отклонён

Выполнены все672trials, по112на запрос (6×8screening +2×32validation), без overrides и execution failure. Первые рекомендации есть во всех шести строках; проверены текущие result schemas, полные sources, accounting и telemetry. Проценты ниже относятся к отдельным32-trial validation, не к объединённой вероятности разных составов.

| Партия/seed | Победы reference→candidate | Wilson95% candidate | NPC candidate | Раунды reference→candidate | Search+encoding reference→candidate, s | Unknown во всём поиске |
| --- | --- | --- | --- | --- | --- | --- |
| Melee42 |19→18/32 (59.375→56.25%)|39.33–71.83%|7|7.688→8.094|105.893→90.736|0→0|
| Melee202 |32→32/32 (100%)|89.28–100%|5|4.281→4.281|31.125→31.095|0→0|
| Mixed42 |20→20/32 (62.5%)|45.25–77.07%|5|6.250→6.250|145.380→142.512|0→0|
| Mixed202 |19→15/32 (59.375→46.875%)|30.87–63.55%|5|8.500→7.562|150.188→122.560|0→0|
| Mixed-magic42 |23→23/32 (71.875%)|54.63–84.44%|8|6.094→6.031|194.597→186.816|0→1|
| Mixed-magic202 |32→32/32 (100%)|89.28–100%|6|3.531→3.344|89.959→78.987|0→0|

Mean absolute win error по шести первым рекомендациям25.521→23.958п.п. Два улучшения достигнуты, регрессий первых win estimates нет; широкие интервалы не позволяют назвать это статистически установленным общим улучшением. Оба исходных stuck202остались100%: gate выхода хотя бы одного не пройден. Кроме того, mixed-magic42получил1unsupported вместо0: у второго validation-финалиста, trial21, `pc_magic_miscast_unresolved/random_transport`, actor`mage`, total17. Этот финалист исключён из рекомендаций; исход сохранён в знаменателе и не стал поражением. Сам первый рекомендованный состав supported. Во всех поисках5round-limits (mixed42:3, mixed202:2), proposal cap0. Duration включает censored prefixes по прежнему контракту.

Сумма search+encoding717.143→652.706s (10.88мин), ниже заранее заданного предела; это один замер, не отдельный benchmark ускорения. Diagnostic replays в эту стоимость не входят. Небольшой выигрыш macro/времени не отменяет два проваленных gates. Mixed505и fullUI202не запускались; формула/веса после данных не менялись.

Telemetry подтверждает8numeric sampling attempts, все приняты,43изменённых NPC по всем attempts,8multi-member attempts. По строкам attempts2/0/1/1/2/2. В melee202оператор не исполнялся; в mixed-magic202два resample изменили по3NPC, но сложная область не найдена. Это предел интеграции с прежним поиском, не опровержение192-trial native контроля и не доказательство недостижимости цели.

Raw candidate, frozen snapshots, проверка и сравнение — `.cache/adr135/candidate-short.json`, `candidate-short.run.log`, `short-comparison.json`, `compare_short.py`. Сам developer harness и четыре изменённых feedback-файла возвращены побайтно к `*.sampler-baseline.py` после проверки совпадения live с candidate snapshot. Итоговый source снова `1beb53fc42061ebe2ea88db2f6351096acfde6a5167dbccfc7dff9368064bdae`. Сохранены sampler/API/9unit tests и прежняя наблюдаемость ADR-0134; экспериментальные feedback helper/metadata/tests удалены из runtime. Cache не заменяет переносимую документацию: основные результаты/решение находятся здесь; для точного повтора переносить raw artifacts отдельно.

После возврата адресный составной запуск59tests:55прошли,4ошибки Windows TEMP в sandbox в `tests.unit.test_dynamic_benchmark` (`restored-validation.log`). Весь этот14-test module повторён вне sandbox:14OK/4.601s (`restored-benchmark-validation.log`). Это составная проверка, не один зелёный59-test run; все45остальных тестов первого запуска прошли. Full/wheel не повторялись: сборка/доставка/ядро не изменены, JSON/process проверки до измерений уже пройдены, snapshot восстановлен точно.

Следующий шаг — спроектировать поиск по управляющему bias с сохранением наблюдений/интервала между пробами и гарантированной экспозицией такого поиска. Сначала дешёвые deterministic случаи и критерии сравнения; затем отдельный замороженный эксперимент. Не перенастраивать отклонённую формулу по этим шести строкам. Модель не обещает монотонности любого конкретного боя, поэтому двоичный поиск без проверки направления не обоснован. Штатный генератор/UI продолжает прежний алгоритм ADR-0128; нового поля JSON или игрового правила нет.

Промежуточный result/log `candidate-short.json`/`candidate-short.run.log`, исходники `*.candidate.py`. `compare_short.py` проверяет schema/source/accounting/telemetry и заранее заданные gates после всех6строк. Новая developer telemetry меняет harness hash, исторический hash сохраняется отдельно. Наблюдаемость не расходует RNG и не превращает descriptor distribution в новую игровую механику.
