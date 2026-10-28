# M8: аудит исключения оставшегося хода погибшего Champion

Дата: 2026-10-28. Граница — [ADR-0044](../decisions/ADR-0044-dead-champion-turn-exclusion.md). Аудит охватывает pure consumer, journal/runner, native simulation/summary и прежнюю JSON/CLI-границу. Полнота каталога Wounds/Miscasts или произвольного боя отсюда не следует.

## Книжное основание

Напрямую перечитаны локальные постраничные тексты выбранных книг:

| Источник | Проверяемое следствие |
| --- | --- |
| BOOK-PLAYER-GUIDE 1.4, гл. V Rules / Combat, стр.112 | Ход атакующего завершается полностью до передачи следующему участнику; exclusion не создаёт action. |
| Та же книга, Wounds Table, стр.190–191 | Четыре lethal строки24/25/26/27+ уже завершают смерть. Dying words строки26 не дают ещё одно боевое действие. Optional trophy27+ требует Close/free hand и не выбирается в текущем ranged scope. |
| BOOK-GM-GUIDE 1.1, гл. VII Allies and Antagonists / Champions, стр.92; PG1.4, Wounding NPCs, стр.191 | Champion использует Wounds Table; Minion disposition на него не переносится. |

Exclusion — техническое представление уже установленной смерти в текущем scheduler, не новое книжное правило или house rule. RULE-COMBAT-001/002 и RULE-NPC-004 сохраняются. Другие причины смерти, Miscast, recovery/campaign/corpse effects не подключаются.

## Матрица реализации и guards

| Граница | Реализация / evidence |
| --- | --- |
| Полный immediate post-Attack source | [Request/result](../../src/towr/domain/npc_roster_dead_champion_models.py) хранит полный NpcRosterChampionAttackResult. State equality включает magic/spatial/обоих owners/daily/roll/execution/expiry/end-turn histories. `test_request_and_apply_require_the_entire_post_attack_source`, `test_same_ids_with_changed_full_attack_source_are_rejected`. |
| Полностью завершённая смерть | Accepted completion, четыре lethal IDs, `dead=True`, resolved новая Wound. Exact injury совпадает с rolled injury плюс единственный effect_resolved marker: слабый WoundEffectResult DTO не может добавить Condition, обработать старую Wound или потерять последствия. `test_each_lethal_row_excludes_only_the_waiting_wizard`, `test_lethal_completion_cannot_change_other_wounds_conditions_or_effects`. |
| Текущий активный атакующий | Живой вражеский Minion, единственный completed standard Attack slot и exact execution round. Цель — связанный awaiting Wizard; completed/excluded и все pending отклоняются. `test_completed_and_previously_excluded_targets_are_rejected`, `test_pending_endurance_wound_cannot_be_closed_by_exclusion`. |
| Минимальная проекция и replay | [Pure functions](../../src/towr/rules/npc_roster_dead_champion_resolution.py) меняют только excluded prefix и Champion round. Apply требует exact source, без нового receipt/ledger/RNG. `test_projection_preserves_every_other_root_and_champion_field`, `test_replay_rejects_a_new_phase_id_and_a_stale_result`. |
| Closed journal vocabulary | [Step union](../../src/towr/domain/npc_magic_step_models.py) сохраняет source/id/before/after/attacker identity. Namespace/unique phase IDs и непрерывная full-owner chain прежние. `test_step_retains_full_source_and_attacker_identity`, `test_phase_namespace_and_collisions_are_checked_without_changing_state`. |
| Обязательная непосредственная последовательность | [Shared predecessor guard](../../src/towr/domain/npc_magic_journal_policy.py) и [result loop/tail](../../src/towr/domain/npc_magic_scenario_result_models.py) требуют matching Attack → exclusion, запрещают иную фазу и конец журнала до exclusion. Разные полные Attack traces не взаимозаменяемы даже при равном post-state. `test_distinct_full_attack_with_equal_post_state_cannot_replace_witness`, `test_old_continuous_attack_end_turn_chronology_chain_is_rejected`, `test_required_phase_cannot_be_replaced_by_end_turn_or_end_of_journal`. |
| Runner order и отказ | [Runner](../../src/towr/engine/npc_magic_scenario_runner.py) публикует exclusion до end-turn/terminal/новой активации; completed Wizard пропускается. `test_consumer_runs_once_between_lethal_roll_and_attacker_end` фиксирует exclusion/end на24draw, всего30; `test_consumer_failure_propagates_without_retry_end_or_new_rng`. |
| Outcomes, live/archive и сцена | Смерть Wizard не завершает бой при живых союзниках. Missing frame сохраняется после exclusion, следующие rounds используют existing live projection. `test_terminal_objective_and_perspective_follow_exclusion_and_attacker_end`, `test_surviving_allies_continue_and_next_round_keeps_dead_archive`, `test_missing_post_death_frame_is_a_stop_after_exclusion_not_before`. |

Матрица первых двух срезов: [15 pure unit](../../tests/unit/test_m8_npc_roster_dead_champion.py), [4 pure integration](../../tests/integration/test_m8_npc_roster_dead_champion.py), [10 journal unit](../../tests/unit/test_m8_dead_champion_journal.py), [9 runner integration](../../tests/integration/test_m8_dead_champion_runner.py) —38implementation tests. Отдельный [public two-file probe](../examples/m8/dead_champion_contract_probe.py) / [stdout](../examples/m8/dead_champion_contract_probe.output.txt) проверяет текущий runner на87scripted d10 через [subprocess test](../../tests/integration/test_m8_dead_champion_contract_probe.py).

## Propagation

[Integration tests](../../tests/integration/test_m8_dead_champion_propagation.py) передают новый outcome/actions/started/completed через existing trial/sequential/real spawn, полные records/source/seed и summary. Обе стороны Wizard и обе perspective сохранены. Missing-frame/Wound/Miscast unsupported остаются в N; prefix расширенного пакета и input/global RNG/children проверяются. Public encoder создаёт request, parser заново принимает его, затем оба backend действительно исполняют reparsed source; result Schema/request reconstruction и same-ID чужой scene source проверяются.

Новых production files/изменений simulation/application/balance/adapters/CLI/Schema/seed scheme для propagation не требуется. Record не передаёт journal в parent и не считает exclusion как действие. Source-bound aggregates не доказывают подлинность произвольного forged manual DTO; immutable snapshot restoration вне гарантии replay API.

## Стандартный RNG и JSON/CLI

Новый конечный [request](../examples/m8/json/dead-champion-v1.request.json) / [result](../examples/m8/json/dead-champion-v1.result.json) задаёт authored numeric profiles и master seed31, trials1, round budget1. Это выбранный regression witness, а не именованный NPC или оценка вероятности сложности. Необычные числа attack1d/10, Damage10 и Wizard Protection1d/1 указаны явно и не выводятся из книги.

При стандартном `random.Random` первый indexed trial имеет seed `87287040705765783024077942935633788642484196062029871242471308383141015621429`: Wounds3 (`3`),2 (`1,1`),25 (`7,9,9`); одна matching exclusion до end-turn, outcome `round_limit_reached`, counters actions/started/completed=`4/1/1`. Сохранённый результат содержит native aggregate и полный исходный request; отдельный trace того же source/seed подтверждает сам exclusion, которого нет в aggregate wire.

Scripted propagation и этот default-RNG CLI witness — разные доказательства. Поле runtime.rng само по себе не доказывает достижение смерти. JSON не получает custom RNG policy, новых fields/outcomes или версии. Stdout CLI остаётся aggregate-only.

## Установленный пакет и пределы

Изолированная сборка выполняется из temporary copy `src`/pyproject/README/LICENSE, без изменения `build/lib` рабочего репозитория. Проверяются все442Python/Schema files source/wheel/installed site, public probe bundle из external cwd без PYTHONPATH, actual default-RNG trace и CLI module/console × sequential/process: `simulate-magic` на death witness и missing-frame control, `balance-magic` на прежнем обычном fixture для совместимости. Отдельный death-case через balance здесь не заявляется. Dependencies copied offline из текущего проверочного окружения; версии фиксируются в report. Это CPython3.12.15/macOS arm64, не cross-platform/performance evidence.

Аудит закрыт без блокеров. 45implementation tests (38первыхсрезов+7propagation) и отдельный public probe — OK. Полная регрессия3470tests/33прежнихerrors (155,370с); точные Counters error headers/subtests/exception signatures равны предыдущим3463tests, новых ошибок нет. Suite не зелёный. Source/harness hash `80c52042e3c8ebf0fdc9d85f478c8fb748e39ddeb4ac9b95b317f73db99cba3f` сохранён.

Installed wheel SHA-256 `a665edd60a131d90fabe98dd53b53fd97218e31987109ed0fd06eb73cafcccf2`; все442files равны source/site,12CLI calls прошли, pip check exit0/пустой stderr. Report `/private/tmp/towr-m8-dead-champion-installed-report.json`; exact versions/среда и scope указаны в нём. Production и все прежние Python/JSON файлы при этом срезе не менялись. Точные команды и итоговые статические сверки — в [актуальном статусе](../project-status.md#последняя-проверка). Отдельные audit helpers/reports размещены в temporary directory; contract/source/tests/probe/fixtures остаются в репозитории. Commit/push выполняет пользователь.

## Сохраняющиеся ограничения

Закрыт только ordinary completed lethal Minion → Champion-Wizard Attack и его owed current-round turn. Не подключены Miscast death, death действующего, Near Miss/Last Stand, другие Wound/Condition consumers, ordinary Attack Give Ground, общий scheduler framework или saved battle. Прочие chronology/scene/route stops сохраняются. Authoring full source не доказывает полноту именованного NPC, а finite traces не оценивают истинную вероятность сложности. Полный suite с33известными Python3.12 dataclasses assertions не объявляется зелёным.
