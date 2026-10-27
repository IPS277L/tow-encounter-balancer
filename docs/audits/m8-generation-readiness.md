# M8: аудит ограниченной генерации magic-составов

Дата: 2026-10-27. Проверены [ADR-0042](../decisions/ADR-0042-magic-composition-generation.md), три application modules, 41 implementation test и самостоятельный production example. На старте HEAD 1c2b91e и 19 dirty/untracked файлов прежних срезов; они сохранены как исходные изменения. Production и прежние tests/tools/examples/probes в этом аудите не менялись.

**Генерация magic-кандидатов готова в границе authored Champion-Wizard/Curse и numeric Shooting Minions ADR-0037/0042.** Typed reserve → complete admitted family → staged evaluation проверены. Базовый staged evaluator отдельно закрыт [аудитом ADR-0041](m8-staged-evaluation-readiness.md). M8 JSON/CLI и новые gameplay consumers этим выводом не закрываются.

## Матрица готовности

| Обязанность | Реализация и проверка |
| --- | --- |
| Typed reserve/preflight | [Models](../../src/towr/application/magic_candidate_generation_models.py), [15 tests](../../tests/unit/test_m8_magic_candidate_generation_models.py): frozen/slotted group/request, strict tuple/list/int/IDs без bool/coercion/consumption, exact partition non-perspective Minions без Wizard, full definitions. Все perspective actors и Wizard фиксированы независимо от стороны; separate facts/ordered exact scene frames обязательны |
| C и бюджет | C=product(width)-all-lo-zero, C>0/max_candidates и полный sum(U×N) до enumeration; рост keep не восстанавливает отсеянных. Проверены4/5/1/0, budgets240/250/110/1140/4×uint64max и C=2**40−1 без enumeration/projection/candidate/RNG/pool. Одна seed admission, все stages валидируются заранее |
| Construction | [Generator](../../src/towr/application/magic_candidate_generation.py), [19 tests](../../tests/unit/test_m8_magic_candidate_generation.py): lexicographic prefix-count vectors/IDs без all-zero/dedup/клонирования; полные snapshots и независимые orders roster/activation/placements/policies/targets/objective. Fresh roster/round/spatial/Champion owner с прежними Wizard/caster/day_id/whole graph; нет вымышленного round ID |
| Scene projection | Все supplied frames, включая unreachable/archive/empty-live, сохраняются без coverage inference/pruning. Filter placements/live/pairs/plans/departures и все три route.path_entity_ids; geometry/flags/zone ranges не меняются. Same projected key объединяется только при полном равенстве frame; first/late conflict и invalid Broken route прерывают всё семейство |
| Повторный admission | Каждый subset проходит NpcMagicScenario constructor. Потеря initial Shooting target и unsafe/safe Broken plan не исправляются новым target/GM approval/маршрутом. Group/request принимает C всех vectors и не обещает допустимость каждого subset; generation не фильтрует invalid составы |
| Source-bound result | Полный staged source/ordered candidates/C/seed/stages/window/cap и каждая ожидаемая projection проверяются той же внутренней функцией по одной. Same-ID Wizard Level/Willpower/profile/day/objective, frames/routes/pairs/flags/graph/order substitutions отвергаются. Equal immutable copies/frozen/replace/pickle допустимы; result хранит inputs без observations/records/RNG/options |
| Ошибки | [MagicCandidateGenerationError](../../src/towr/application/magic_candidate_generation_errors.py) сохраняет candidate ID/counts/original cause/notes. Второй admission failure не запускает следующий vector; нет skip/partial/retry/fallback. Wrong root, BaseException и final staged/result constructor errors проходят напрямую |
| Backend integration | [3 tests](../../tests/integration/test_m8_magic_candidate_generation.py): полные sequential/spawn reports/selection/parent source/repeat/rename равны; natural winner/проценты не фиксируются. Scripted existing RNG boundary оплачивает4×2+2×4=16 на backend, exact requests/options/native counts/counters, child PID/input/global RNG/cleanup |
| Generated encounters | [4 tests](../../tests/integration/test_m8_magic_generated_encounters.py):1..3 retained Curse targets в roster order, все movements до Willpower, Broken→Recover. Defeat до target turn сохраняет full supplied decision/оба owners/архив placement, следующий Casting видит только live targets. Missing scene сохраняет exact pending/staged prefix без ранних draws; оба backend дают native unsupported2/2 и early actual8/planned16 |
| Public/installed boundary | [3 новых example tests](../../tests/integration/test_m8_magic_balance_example.py): two-file external-cwd/stdout parity и поздние generation/evaluation failures без partial stdout. Fresh installed package проверяет те же три paths без PYTHONPATH, production files совпадают побайтно |

Матрица опирается на **41 implementation test =15preflight+19construction+7integration**, плюс **3 новых example tests**; historical contract probe отдельно. Независимое read-only ревью контракта, кода, tests и нового example блокеров не выявило. Source guards доказывают структурную согласованность, не истинность GM facts или происхождение ручных aggregates.

## Самостоятельный пример

[magic_balance.py](../examples/m8/magic_balance.py) использует public generator/staged API и builder из прежнего [magic_scenario.py](../examples/m8/magic_scenario.py). Два файла копируются вместе; нет tests/private/probe imports. Новые numeric reserve actors авторятся до генерации, generator выбирает только заданные prefixes. Новый local printer сохраняет все native magic counters/rows и правильно описывает изменение численности, прежние printers/examples не меняются.

Authored Champion-Wizard Level2, Casting/Willpower3d/3, RES4, Curse; allied/enemy Shooting Minions3d/3, Dam3, RES3. Фиксированы Wizard+ally и perspective players_and_allies. Резерв E1/E2/E3, groups A=(E2,E1)1..2, B=(E3)0..1. Исходные attack/Willpower/Speed/policies/полные GM-approved KNOCKED_OUT decisions сохранены. Это не именованные книжные NPC и не назначенная по книге сложность.

Авторская finite scene family задаёт128keys: три enemy placements arena/shelter и16live subsets при фиксированном живом Wizard/архивных placements. Graph arena–shelter–boundary, Range/away-route/fastest Safe Recover/departures явно переданы. Нет автоматического определения LOS, маршрутов или новых GM facts по составу. Проекции четырёх кандидатов содержат8/32/32/128frames; отсутствие покрытия других scenes по-прежнему даёт unsupported, а не guessed continuation.

Seed42, B1, окно [1/4,1/2,3/4], stages=(8,keep2),(32,keep1), planned/max96 на backend. Process workers2/batch3. Пример сравнивает полные sequential/process reports/selected IDs, source identity, actual<=planned, input/global RNG и отсутствие детей до печати. Catalog всех четырёх составов и все выполненные stage rows/counts/rates/actions/started/completed/local selection/continuation/final выводятся только после успеха.

[Stored output](../examples/m8/magic_balance.output.txt), CPython3.12.15/macOS arm64:

| Counts / этап | Goal / defeated / limit / unsupported | Наблюдение |
| --- | --- | --- |
| (1,0), N8 | 3/0/5/0 | Eligible; продолжает |
| (1,1), N8 | 0/0/6/2 | Unsupported; остаётся в полном report/N |
| (2,0), N8 | 0/0/6/2 | Unsupported; не продолжается |
| (2,1), N8 | 0/0/5/3 | Unsupported; не продолжается |
| (1,0), N32 | 9/0/23/0 | Goal9/32 внутри окна, финальный selected=(1,0) |

Status COMPLETED, actual64 на backend (32 первого этапа +32 уточнения), planned96; **128 trials на запуск примера**. PrefixN8 вычислен заново внутри N32; stages не являются независимыми observations и не складываются в новую долю. Фактический survivor/процент не закреплён в assertions; наблюдение seed/runtime не является preset, доверительной границей или гарантией истинной вероятности/полноты тактики.

## Ошибки публичного entry point

[3 tests](../../tests/integration/test_m8_magic_balance_example.py) — **OK (2,363 с)**. Two-file bundle из external cwd даёт stored stdout/empty stderr.

Поздняя generation failure выполняет первый настоящий NpcMagicScenario admission, второй отказывает с OSError+original note: candidate ID берётся из actual projection, counts=(1,1), cause/notes сохраняются. Evaluation/process не запускаются, следующего vector/partial output нет. Marker подтверждает первую проекцию; input/global RNG/children сохранены.

Поздняя evaluation failure завершает реальные8trials первого generated кандидата, второй runner отказывает: stage_index0/candidate ID и полная staged→MagicBalanceEvaluationError→original OSError chain/notes доступны. Нет следующего runner/этапа/process или partial stdout; entry point пишет контекст в stderr и пробрасывает исходную цепочку. Assertions не закрепляют survivor, а marker подтверждает8trials.

## Установленный пакет

Свежий wheel собран offline из временной копии audited src/README и установлен в отдельное чистое venv вне repo. Все **423 Python/Schema files** побайтно равны src, wheel и installed site. Isolated imports towr/generator/models/error указывают в installed site; PYTHONPATH удалён, user site отключён.

Two-file пример из external cwd даёт stored stdout/empty stderr. Те же late generation/evaluation программы выполняют первый admission/8real trials, проверяют ID/counts/stage/cause/notes/input/global RNG/children/no-next и empty stdout на установленном API. Зависимости JSON/CLI в это audit venv не ставились: пример их не использует; installed wire/console scope не объявляется перепроверенным новым M8 format.

Wheel SHA-256 `b8a7a7bcf56edef488b2daab6b894e887a7ff50f5dfb4a071d16d416d2308f63`. Build/install/success/error evidence — `/private/tmp/towr-m8-generation-audit-pjycm1pl`; report `/private/tmp/towr-m8-generation-audit-wheel-report.json`. Временные evidence не нужны для использования проекта и не входят в Git.

## Книги и ограничения

Прямо перечитаны локальные BOOK-PLAYER-GUIDE1.4: Equipment / Ranged Weapons, стр.94; Rules / Combat, стр.112; The Battlefield / Range / Speed, стр.114–115; Giving Ground, стр.119; Conditions / Broken, стр.122; Magic in the Old World / Casting a Spell / Interrupted Casting, стр.156; Spell Potency / Miscasts and the Rule of Nine, стр.157; Battle Magic / Curse of Cowardly Flight, стр.162; Wounds Table, стр.190–191. BOOK-GM-GUIDE1.1: Allies and Antagonists / Minions / Champions, стр.91–92.

Нормативный Casting/Interrupted Casting текст отделён от примера. Сохранены полный ход/очередь, Curse movements→Willpower, Broken Recover и distinct NPC injury policies: Minion defeated от Wound с attacker/GM disposition, Champion использует Wounds Table. Broken и другая Zone не defeat; обязательные pending не обходятся подбором. Новых Rule IDs/house rules/противоречий нет.

Готовность ограничена fresh authored inputs ADR-0037. Остальные Wound/Miscast/chronology/обычный Attack Give Ground/неизвестные scene-route consumers остаются unsupported; все trials остаются в N. Отсутствие unsupported в выборке не доказывает полноту тактики. Полные NPC/spell/Talent/item каталоги, PC, auto tactics/scene facts, M8 JSON/CLI, prefix reuse/confidence presets/generic framework не добавлены. Budget не RSS quota; error traceback может удерживать объекты, cleanup ждёт начатую работу без rollback/mгновенного kill.

## Итоговая проверка

Полная регрессия: **3285 tests / 33 прежних errors (116,210 с)**. Counters полных headers/subtests и exception signatures точно равны предыдущему прогону 3282 tests; новых ошибок нет. Полный suite не зелёный: 32 ошибки frozen/slotted Aim .state и одна dataclasses.replace(init=False) на Python3.12 остаются отдельной задачей. Compileall, 3217 локальных Markdown-путей/94 anchors, import boundaries 311 core modules, purity пяти magic balance modules/public imports, SHA всех 801 исходных Python/JSON файлов src/tests/tools и whitespace — OK. [Команды/логи](../project-status.md#последняя-проверка). Другие runtime/ОС/RSS не проверены.

Source/harness SHA-256 `d4619ad9b4a7dda0464f2931161e95be3e3f5693a706af074ac38bd257afedd1` не меняется в этом аудите. Historical performance reports предшествуют outer balance/application modules; simulation/engine/fixtures/tools прежние, benchmark не повторяется. Старые локальные speedups не объявляются измерениями generator или installed wheel. Все исходные src/tests/tools сохранены побайтно; новые example/output/audit/test и общие документы — единственные изменения среза. Commit/push не выполнялись.

## Следующий шаг

Подготовить отдельный контракт M8 JSON/CLI для simulation и balance в прежней gameplay границе. Определить полный fresh scenario/family mapper, strict versioned request/result/error formats и отдельные команды, explicit execution options/seed/stages/caps/window. Сохранить numeric profiles, Wizard/caster/spell, independent orders, full scene keys/routes/GM facts/decisions и source-bound aggregate outputs/phase errors. Нельзя молча терять low-level поля или исправлять invalid subsets.

Сначала ADR/матрица и finite mapping probe без production wire реализации. Старые ranged/Melee/mixed formats/команды/seed schemes и shared classes сохраняются; новые gameplay consumers/auto facts/prefix reuse/универсальный rules framework не включать.
