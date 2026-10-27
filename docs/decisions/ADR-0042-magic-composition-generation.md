# ADR-0042: ограниченная генерация magic-составов

Статус: контракт подготовлен в согласованном направлении M8, 2026-10-27. **Frozen production group/request реализованы; construction/result/error ещё не реализованы.** Основа — [ADR-0037](ADR-0037-magic-scenario-runner.md), [ADR-0041](ADR-0041-staged-magic-evaluation.md) и [общий аудит staged evaluation](../audits/m8-staged-evaluation-readiness.md); технический ориентир — [генерация mixed-составов ADR-0033](ADR-0033-mixed-composition-generation.md). Отдельные magic types сохраняют existing admission; generic generator/framework не вводится.

## Источники и граница

Непосредственно проверены локальные страницы выбранных книг:

| Книга / глава / страницы | Применение |
| --- | --- |
| BOOK-PLAYER-GUIDE1.4, Equipment / Ranged Weapons, стр.94 | Ограничения ranged weapons и враг в Close; отбор не добавляет Aim/Reload/смену оружия |
| Та же книга, Rules / Combat, стр.112 | Полный ход перед передачей actor; генератор строит fresh inputs, не продолжает текущий turn |
| Та же книга, The Battlefield / Range / Speed, стр.114–115 | Дистанции и маршруты остаются explicit facts; одна Zone не доказывает Close |
| Та же книга, Giving Ground, стр.119; Conditions / Broken, стр.122 | Возможность ухода и fastest/safe route не выводятся из одного соседства; Broken не defeat |
| Та же книга, Magic in the Old World / Casting a Spell / Interrupted Casting, стр.156; Spell Potency / Miscasts, стр.157 | Wizard/caster/spell и обязательные pending не подменяются Minion-моделью; этапы не resume |
| Та же книга, Battle Magic / Curse of Cowardly Flight, стр.162 | Give Ground если возможно, затем Willpower исходных целей против Potency |
| Та же книга, Wounds Table, стр.190–191 | Champion использует Wounds и обязательные effects, включая Stomach Blow expiry |
| BOOK-GM-GUIDE1.1, Allies and Antagonists / Minions / Champions, стр.91–92 | Minion defeated от Wound с attacker/GM disposition; Champion не Minion |

Генерация — техническая область поиска начальных сценариев, не книжная формула сложности. Новых Rule IDs/house rules нет. Single-run scope ADR-0037 прежний: один authored Champion-Wizard/Curse, здоровые numeric Shooting Minions, explicit facts/frames/routes/policies и существующие unsupported stops. PC, другие spells/NPC abilities, новые Wound/Miscast consumers, auto tactics, JSON/CLI и prefix reuse вне контракта.

## Резерв и семейство

Caller передаёт полностью допущенный fresh NpcMagicScenario с ordered резервом. **Все actors perspective_side и единственный Wizard фиксированы**, независимо от стороны Wizard. Только Minions противоположной perspective стороны разбиваются на непересекающиеся группы. Wizard никогда не входит в group и не удаляется. Для количества n берутся первые n actor IDs группы; остальные отсутствуют в начальном бою, не скрыты/архивированы/defeated и не вступят позднее. Нет клонирования, каталога, перестановок или перебора всех сочетаний.

Каждая группа непуста и содержит одинаковое **полное значение NpcDefinition**, не только ID/название/Skill. Иные definitions требуют разных групп; отдельные группы могут иметь равные definitions. Порядок group.actor_ids независим от roster/activation/policies/placements. Maximum может быть меньше размера резерва. Groups образуют exact partition всех non-perspective Minions; Wizard, friendly/foreign/missing/repeated IDs запрещены.

Обе perspective допустимы. Если Wizard принадлежит perspective, fixed actors включают его allied Minion; отбор оставляет минимум одного opposing Minion. Если Wizard на другой стороне, fixed perspective Minions остаются все, Wizard остаётся opposing actor/objective, а отбор обязан оставить минимум одного **его allied Minion**. Поэтому all-zero counts исключён в обеих ветвях, даже когда противоположная сторона ещё содержит Wizard: existing admission требует у Wizard allied и opposing Minion.

Caller отдельно передаёт обязательные facts: NpcMagicScenarioFacts и scene_frames: tuple[NpcMagicSceneFrame,...]. Facts утверждаются для каждого состава; no_additional_rules не разрешает стирать известные Abilities книжного NPC. Для frames preflight требует полного равенства ordered tuple с template.scene_frames, включая keys/placements/live IDs, pair orientation/order/GM approvals, zone ranges, routes/flags/plans/departures. Equal immutable copies допустимы, новые факты задаются другим template.

Это **явное утверждение применимости ко всему семейству и всем проецируемым состояниям**. Полнота состава, awareness/LOS, no external changes, geometry, can_leave_zone, impossibility, fastest routes, actor policies/target priorities/полные defeat decisions сохраняют смысл после удаления резервистов. Graph/admission проверяет согласованность, но не истинность всех supplied assertions. Если caller не может подтвердить общую применимость — отдельные templates/families. Генератор не назначает новые GM approvals/маршруты по численности и не исправляет invalid Broken plan на Recover.

## API и preflight

Генерация находится в application: собирает domain inputs для existing simulator; balance получает готовые inputs/aggregates. Group/request реализованы в [application/magic_candidate_generation_models.py](../../src/towr/application/magic_candidate_generation_models.py); magic_candidate_generation.py и magic_candidate_generation_errors.py следуют отдельно.

| Тип / функция | Контракт |
| --- | --- |
| MagicCompositionGroup(group_id, actor_ids, minimum_count, maximum_count) | Frozen/slotted, непустой ordered tuple уникальных IDs, включённые bounds |
| MagicCandidateGenerationRequest(template_scenario, groups, facts, scene_frames, candidate_id_prefix, max_candidates, master_seed, stages, max_total_trials, window) | Frozen/slotted; typed magic inputs/stages, existing ObjectiveRateWindow; derived candidate_count/planned_trials |
| generate_magic_candidates(request) | Полная bounded materialization через public constructors без runner/RNG/pool/IO |
| MagicCandidateGenerationResult(source_request, evaluation_request) | Frozen/slotted, exact source-bound MagicStagedEvaluationRequest |
| MagicCandidateGenerationError(candidate_id, counts) | Candidate/count vector context, исходный cause/notes; partial result отсутствует |

Ordered fields принимают только tuple/list с копированием в tuple; generator/set/dict/str не потребляются. IDs/prefix — непустые строки без неявного trim/coercion; group IDs и IDs внутри/между группами уникальны. Bounds — exact int без bool, 0<=minimum<=maximum<=len(actor_ids). Хотя бы одна группа обязательна. Foreign scenario/group/stage/Enum families или неправильные типы → TypeError; диапазон/пустота/несогласованность → ValueError. Shared classes/import/pickle paths не меняются.

До enumeration/materialization/RNG проверяются typed template/facts/frames и ordered exact frame equality, partition/definitions/bounds, uint64 seed и **все** MagicBalanceStage, window, positive exact max_candidates/max_total_trials. Переиспользуются stage validation/budget ADR-0041 и один NpcMagicSimulationRequest для seed/trial admission без исполнения. Матрица C×S requests не строится; group/request не проверяет все subsets.

Для bounds [lo_i,hi_i]:

```text
C = product(hi_i-lo_i+1) - int(all(lo_i == 0))
U[0] = C
U[i+1] = min(U[i], keep[i])
planned_trials = sum(U[i] * N[i])
```

C=0 или C>max_candidates — отказ до iterator; planned_trials>max_total_trials — также до iterator. Exact Python integers без uint64 cap произведения/суммы. Полные повторные пакеты ADR-0041: 10→100 стоит110, не100/90. C считает все ненулевые vectors bounds, **не число допустимых subsets**. Успешный request preflight не обещает допустимость каждого состава. Нельзя сократить C/budget, пропустить invalid vector или вернуть успешно построенный префикс.

## Порядок и свежий owner

Counts идут лексикографически по ordered groups и возрастающим количествам, последний индекс меняется быстрее; all-zero исключён. Нет dedup по равным профилям. Candidate/scenario ID — prefix + ':counts:' + counts через запятую. Group names/IDs не входят в candidate ID; координаты определяет source_request. Это локальная идентичность, не глобальный content hash. У CombatRoundState нет отдельного round ID: он не изобретается и не переносится из M7.

Retained IDs — все fixed actors и выбранные prefixes групп. Строятся public snapshots:

- roster с полными исходными participant snapshots/definitions, в прежнем roster order;
- fresh CombatRoundState(1, roster.turn_participants) с обычным side_order; activation_order — независимая исходная подпоследовательность;
- fresh SpatialBattleState с **всем исходным graph**, включая пустые Zones, и filtered placements в прежнем независимом порядке;
- новый NpcChampionAttackState для нового roster/round и пустого DailyWoundState с прежними day_id/Wizard actor ID; прежний полный NpcCastingWizardState/caster/fresh magic, spell и histories/pending-free bootstrap сохраняются. Initial minion_attack=None как в template, runtime owner добавляет existing bootstrap;
- actor policies в roster order: target_actor_ids и полные MinionDefeatDecision фильтруются по retained IDs в прежнем порядке; прочие поля, Willpower/Speed/attack/Casting/Zone priorities и True/False flags неизменны;
- objective — прежняя подпоследовательность opposing targets, включая retained Wizard при opposite perspective; perspective_side/max_rounds/repeated_stagger_choice и отдельно supplied family facts сохраняются.

Новая initial/current state не продолжает исходный бой. Каждая проекция повторно проходит полный NpcMagicScenario admission: Wizard и оба Minion-союза/врага, здоровые profiles, initial frame/complete ordered policies, все live hostile pairs, доступная initial Shooting цель и Wizard Zone, факты и планы. Удаление последней допустимой цели может сделать subset invalid, даже при допустимом template.

## Проекция scene frames

Проецируются **все** supplied frames в исходном порядке, включая потенциально недостижимые/empty-live. Генератор не ищет достижимость и не достраивает coverage; отсутствие future frame остаётся existing unsupported_path во время боя.

Для каждого frame:

1. Key.placements фильтруется по retained IDs с сохранением полного архива retained actors и исходного placement order; key.live_actor_ids — прежняя live подпоследовательность. Удалённые резервисты исчезают и из архива.
2. Pair ranges оставляют оба retained endpoints; source order/orientation/value и directed GM approvals не меняются. Zone ranges сохраняются полностью: Wizard/graph остаются.
3. Give Ground/Broken plans/attack departures оставляют retained actors в прежнем порядке. В каждом non-None route.path_entity_ids фильтруются только удалённые IDs; порядок остальных/obstacle/terrain flags и все zone sequences/destinations/impossibility/fastest/departure assertions сохраняются.
4. Если projected key уже встречен, **полностью равный projected frame** объединяется с первым в порядке источника. Same key с любым отличием оставшегося frame — ошибка всего candidate/family. Нельзя выбрать первый конфликтующий frame, объединить его планы или построить новый факт.

Фильтрация не снимает проверку Broken безопасности: удаление врага может сделать moving plan недопустимым либо изменить самую быструю route. Existing admission отвергает известное противоречие; caller family assertions остаются необходимы для остального. Нельзя отбросить invalid/unreachable frame ради successful generation. Empty-live frame сохраняет placements/zone ranges и не является пустым scenario.

## Ошибки и source-bound result

Любой Exception при построении конкретного candidate (включая scene collision/repeated admission) оборачивается MagicCandidateGenerationError с ID/counts, __cause__ и сохранёнными notes. Ошибка первого/позднего vector прерывает весь вызов без skip/retry/partial/fallback. KeyboardInterrupt/SystemExit и прочие BaseException проходят напрямую. Preflight и ошибки финальных staged/result constructors проходят напрямую без вымышленного candidate context.

Result проверяет typed source/staged request, C, ordered candidate IDs/full scenario projections, seed/stages/window/cap. Подмена Wizard/caster/profile/policies/graph/placements/frames/route paths/GM flags/decisions/objective/day_id/ID, missing/duplicate/reordered candidates запрещены. Equal immutable copies допустимы без rebinding. Одна внутренняя projection function используется construction и result guards; ожидаемые проекции строятся по одной без второй сохранённой копии семейства. Result содержит только source и staged inputs, без outcomes/records/journals/RNG/options. Structural guards не доказывают истинность facts или книжное происхождение numeric profiles.

## Finite probe и матрица реализации

[Probe](../examples/m8/generation_contract_probe.py) и [stored output](../examples/m8/generation_contract_probe.output.txt) вручную задают конечный резерв/векторы и используют public domain/staged constructors, без production generation API/runner/RNG/pool. Для копирования нужен также magic_scenario.py. Локальные arithmetic assertions/equality/collision checks демонстрируют выбранные semantics, **не реализуют production request/result/error guards**.

Wizard+ally fixed; roster order wizard,ally,E1,E2,E3, groups A=(E2,E1) bounds1..2 и B=(E3) bounds0..1. Четыре vectors (1,0),(1,1),(2,0),(2,1); retained enemies в roster order E2 / E2,E3 / E1,E2 / E1,E2,E3, pair counts2/4/4/6. Stages10keep2/100keep1 требуют240. Отдельный second frame двигает только E1: удаление E1 объединяет полностью равные projections, retained E1 сохраняет два frames. Conflicting retained facts при key collision отклоняются. Broken route после удаления врага не исправляется. Проверяются обе perspective и обязательное сохранение Wizard, subset admission и budget239 refusal. Counts/projections не являются simulation observations.

| Срез | Обязательные deterministic checks |
| --- | --- |
| Group/request | Frozen/slots/strict containers/replace, IDs/полные definitions/partition без Wizard, обе perspective, family facts/ordered frame equality, все stages/seed/window, C/caps/big integers/all-zero/fixed bounds, до enumeration/projection/candidate/RNG |
| Construction | Все vectors/IDs/independent orders/full snapshots/caster/day/graph/policies/objective; route filtering и archives, equal-key collapse/full conflict, invalid Broken plan/initial target; все supplied frames включая empty-live/unreachable; обе perspective, no runner/RNG/pool/IO, fail first/later/cause/notes/no-skip, BaseException/final boundaries |
| Result | Exact source/full projection и общие staged fields; equal copies; foreign types/пропуски/duplicates/order, same-ID Wizard/profile/frame/plan/flag/day substitutions; frozen/aggregate-free inputs |
| Integration | Generation → existing staged evaluator, full sequential/spawn reports, repeat/rename seeds, parent input/RNG/cleanup, scripted Curse multi-target/defeat/archive/scene selection для разных составов без закрепления Monte Carlo winner |
| Аудит | Public production example/stored output, late generation/evaluation failure без partial stdout, external cwd/installed parity, сохранение previous APIs/boundaries |

Порядок: (1) frozen MagicCompositionGroup/MagicCandidateGenerationRequest с полным preflight/derived C/planned_trials и tests, **без materialization**; (2) construction/result/error; (3) integration; (4) public example/общий аудит. Каждый срез проверяется отдельно, веха не расширяет игровые rules. Текущий контрактный probe не заменяет этих последующих implementation tests.


## Проверка контрактного среза

2026-10-27, CPython3.12.15/macOS arm64: [один новый subprocess test](../../tests/integration/test_m8_magic_generation_contract_probe.py) — **OK (0,240 с)**, two-file external-cwd/stdout parity, stderr пуст. Независимое read-only ревью ADR/probe/output и прямых книжных ссылок блокеров не выявило. Production source и прежние tests/tools не менялись; ручные projection assertions не объявляются реализованными production guards.

Прежний installed wheel побайтно совпал с current src по 420 Python/Schema files. Новый two-file probe без PYTHONPATH вне repo прошёл обычный и guarded запуск с запрещёнными RNG/runner/evaluator/pool calls. Свежая сборка не потребовалась; README metadata старого wheel не объявляется новой. Report `/private/tmp/towr-m8-generation-contract-installed-report.json`; временные evidence не нужны для использования проекта и не входят в Git. Другие runtime/ОС/performance/RSS не проверены.

Полная регрессия: **3241 tests / 33 прежних errors (104,698 с)**; точные error Counters равны предыдущей вехе, новых ошибок нет. Файловые проверки/команды и точный следующий implementation-срез — в [статусе](../project-status.md#последняя-проверка). Source/harness hash не изменился, новых benchmark-запусков нет. На старте 24 dirty/untracked файла учтены как исходные; добавлены ADR/probe/output/test, общие документы синхронизированы. Commit/push не выполнялись.


## Реализованный первый срез: group/request preflight

2026-10-27: [MagicCompositionGroup/MagicCandidateGenerationRequest](../../src/towr/application/magic_candidate_generation_models.py) реализованы без enumeration/materialization. Frozen/slotted модели проверяют strict tuple/list/IDs/bounds и magic TypeError/ValueError conventions, full definitions/partition non-perspective Minions без Wizard при обеих сторонах. Separate family facts и typed exact ordered scene_frames, window/все stages и одна NpcMagicSimulationRequest seed admission проверяются до арифметических caps. C/planned_trials используют exact Python integers и прежнюю stage budget formula; растущий keep не восстанавливает отсеянных.

[15 deterministic tests](../../tests/unit/test_m8_magic_candidate_generation_models.py) — **OK (0,024 с)**. Проверены C4/budget240, cap3/239, расширенные bounds C5/budget250, fixed/all-zero, keep growth1140 и total4×(2**64−1). Четыре сочетания Wizard-side/perspective, отказ Wizard/friendly/foreign/missing/overlap в groups, полные definitions и independent orders, mandatory facts/frames, equal copies, key/pair orientation/order/routes/GM flag substitutions и frozen/replace/pickle сохранены. Forty-group C=2**40−1 проверен при запрещённых enumeration/candidate/staged/projection/RNG/runner/pool и ровно одной seed admission.

Допущенный template с moving Broken plan, который станет invalid при удалении arena enemy, принимается group/request при запрещённой projection. Preflight считает все vectors и не обещает допустимость subsets. Construction/result/error, полная проекция frames/owner и сквозная evaluation следуют отдельными срезами; probe/output прежние. Новых Rule IDs/house rules/извлечения книг нет.

Независимое read-only ревью production и 15 tests блокеров не выявило. На старте 28 dirty/untracked файлов учтены отдельно; прежние src/tests/tools и public probe/output не менялись. Новый source/harness hash меняется из-за одного application module, simulation/engine/tools прежние, новых benchmarks нет. Installed wheel нового models API и другие runtime/ОС в этом срезе не проверялись; прошлый installed probe не доказывает установку нового файла. Полная регрессия: **3256 tests / 33 прежних errors (105,847 с)**, точные error Counters равны предыдущей вехе, новых ошибок нет. Compileall, 3144 Markdown-пути/83 anchors, import boundaries/purity, 794 исходных Python/JSON SHA и whitespace — OK. [Команды/ограничения](../project-status.md#последняя-проверка). Commit/push не выполнялись.

Следующий срез — magic_candidate_generation.py, MagicCandidateGenerationResult в models и magic_candidate_generation_errors.py: ordered count vectors/IDs, full fresh owner/scene projection с общей внутренней функцией для construction/result guards, equal-key full-equal collapse/conflict, repeated subset admission и error/cause boundaries без skip/partial. Integration/public production example/аудит затем; новые gameplay consumers/JSON/CLI/prefix reuse вне среза.
