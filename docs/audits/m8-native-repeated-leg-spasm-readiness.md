# M8: аудит native repeated Leg Spasm, ADR-0053

Дата: 2026-11-01. **ADR-0053 закрыт в принятой native границе.** [Контракт](../decisions/ADR-0053-native-repeated-leg-spasm-continuation.md), реализация, public/installed/spawn и финальная полная регрессия завершены. Generation/JSON1/2/3 новое разрешение пока не доставляют.

## Native контракт и полные источники

[Scenario/admission](../../src/towr/domain/npc_magic_scenario_models.py) содержит append-last nullable `repeated_leg_spasm_continuation`, одно значение `NpcMagicRepeatedLegSpasmPolicy.STAND_ONCE_WITH_JOURNAL_WITNESSES`. NonNone требует typed base stationary policy; Miscast независим. Шесть сочетаний разрешены, два repeated-on/base-None отвергаются. Валидные None/old policies сохраняют прежние traces/stops/RNG.

Shared pure admission повторно проверяет original nested Scenario/Miscast facts и permissions до equality/RNG/pool. Найденный в contract phase native `int1 == True` facts gap закрыт; испорченный источник не нормализуется. Trial и parallel parent проверяют запрос до `rng_factory`/pickle/pool; returned result/worker record source проверяется до сравнения и canonical parent substitution.

[Bounded cursor](../../src/towr/domain/npc_magic_repeated_leg_spasm_policy.py) хранит полный current и3typed witnesses: stand48, qualifying bound Attack, consumed stand52. Init использует `initial_runtime_state`. Нет root archive/flags/копирования prefix; cursor выводится последовательно из собственного admitted journal и не сбрасывает разрешение. Его constructor/standalone diagnosis с явными witnesses не обещают journal membership или общий replay. Membership подтверждают publication/reconstruction, сравнивая полные recorded results, а не ID или projected state.

[Step](../../src/towr/domain/npc_magic_step_models.py), [policy](../../src/towr/domain/npc_magic_journal_policy.py), [diagnosis/Result](../../src/towr/domain/npc_magic_scenario_result_models.py), [runner](../../src/towr/engine/npc_magic_scenario_runner.py) подключены к существующему executor52. Eligible repeated stand обязателен перед action selection. Результат не увеличивает actions/rounds; journal constructor не принимает caller cursor/cache и заново выводит его из prefix. Pending Miscast/Attack/movement и completed lethal Attack→death exclusion сохраняют приоритет.

Current cursor допускает законные pending phases и late6; узкая52 admission применяется к кандидатам и request в нужной фазе. Capture не строит Request52 на чужом ходу и не превращает допустимую, но неподдержанную для52 атаку в exception. Existing context49 после stand сохраняет оба terrain, Wounds/daily/roll history и поддерживает actual6/expiry. Третья9 регистрируется полностью, затем даёт ACTOR_INJURY; второго repeat не появляется. Старые48/49/52 scopes не расширены.

## Generation и wire остаются закрыты

[Generation](../../src/towr/application/magic_candidate_generation_models.py) отвергает opted template и все candidate sources до enumeration/projection/equality. Его арифметическая Request boundary использует permissions/facts-only admission; повторного Scenario construction до generation нет. [Shared mapper](../../src/towr/adapters/_magic_scenario_json.py) отвергает новое nonNone во всех simulation/balance1/2/3 documents/source echoes. При None old bytes сохраняются; closed schemas не принимают новый key даже null. Новых generation family fields/schema/version нет, flag не стирается ради обхода guards.

## Детерминированные проверки

- [14 unit](../../tests/unit/test_m8_repeated_leg_spasm_policy.py):6valid/2invalid permissions; raw enum/facts до RNG; exact scene/current/history; same-ID/different-dice full Attack membership; cursor consumed/no reset/overwrite; pending/death; post-stand6; third9 stop. Один Close-fixture сначала нарушал прежнее initial-scene правило, исправлен на отдельные valid initial/future frames без claim reachable journal.
- [5 integration](../../tests/integration/test_m8_repeated_leg_spasm_policy.py): actual trial counters; scripted sequential/spawn records/full source/summary/denominator; standard seeded3trial parity на одном runtime без cross-runtime oracle; parent malformed source rejection до RNG/pool; explicit-list staged sequential/process2+2+4=8trials/common seed prefix.
- [10 refusal tests](../../tests/unit/test_m8_repeated_leg_spasm_refusals.py): generation source/all-candidate preflight, detached aliases, unreadable collections, direct mapper/request/result обоих families1/2/3, closed unknown fields/null и exact None encoding. Arithmetic boundary проверена отдельно.
- [Copied example](../../tests/integration/test_m8_repeated_leg_spasm_runner_example.py): трёхфайловый public bundle и exact stdout. Новые native20checks прошли как19OK/1fixture error в `.cache/adr0053-targeted.log` и исправленный case1OK/0,675с в `.cache/adr0053-targeted-close.log`, вне sandbox.
- Прежний targeted набор39tests OK/4,217с: `.cache/adr0053-legacy-targeted.log`. Positional test учитывает новый append-last defaultNone. Старые manual/native-contract probes после расширения Step union проверяют **отказ policy**, а не прежний TypeError типа; native facts control теперь проверяет реальный runner/noRNG guard. Их намерение и old-stop traces сохраняются.

Независимое read-only production review конкретных блокеров не оставило. Успешные проверки не повторялись без изменения; sandbox spawn/TEMP ограничения отделены от assertion failures.

## Public/installed/native spawn

[Public runner](../examples/m8/repeated_leg_spasm_runner.py), [stdout](../examples/m8/repeated_leg_spasm_runner.output.txt), [installed helper](../../tools/audit_m8_repeated_leg_spasm_runner_install.py). Bundle: runner, `stationary_wound_runner.py`, `magic_scenario.py`.

Один запуск примера содержит **330scripted d10**:48+48 при independent Miscast on/None,7/24old permission controls, post-stand6/expiry51, third9 stop42, sequential/spawn mixed48+7 по одному batch каждый. Spawn factory проверяет PID ребёнка. Полные records/source/summary совпали, round-limit+unsupported дают denominator2; RNG/global sources неизменны. Это finite paths, не вероятности.

Fresh wheel установлен отдельно, рабочая `.venv` не менялась. Installed Python3.12.4 `-I` исполнил copied bundle из внешнего cwd;2top-level child commands source/installed дали byte-identical stdout, оба с реальным spawn. **468package .py/.json paths+SHA256 source/wheel/installed совпали**; проверены конкретные consumer/cursor/context imports из audit site-packages. Source/fixture hashes до/после неизменны; PDF/references в wheel отсутствуют, `pip check` OK.

Финальная evidence: `.cache/adr0053-final-installed-audit/checks/evidence.json`. Wheel `.cache/adr0053-final-installed-audit/wheels/towr_encounter_balancer-0.1.0-py3-none-any.whl`, SHA256 `02778c9daf8c2943df4091fdc09061ba8277719f01e277dba7ba9812414e1c5f`. Windows11/CPython3.12.4; jsonschema4.26.0, referencing0.37.0, jsonschema-specifications2025.9.1, attrs26.1.0, rpds-py2026.9.1, typing-extensions4.16.0. Первоначальная `.cache/adr0053-installed-audit` сборка до admission boundary fix не используется как итоговая. Полный installed transport audit269commands здесь не повторяется и не заявляется; это отдельная native веха с refusal guards.

## Полная регрессия и следующий шаг

Первый полный прогон `.cache/adr0053-full-regression.log`:4044tests/34errors/4failures за1087,442с.33errors прежние; одна новая error и4failures разобраны. Полная Scenario admission косвенно попала в generation arithmetic через SimulationRequest seed check. Исправлено разделением: Request проверяет permissions/facts/seed/trials без Scenario reconstruction, execution entrypoints явно делают full admission до RNG/pool. Остальные fixtures обновлены под третий append-last field, actual shared preflight hook и инъекцию повреждённых facts после valid record construction. Пять точных проблемных tests прошли (5OK/0,215с); parent preflight и10refusal tests повторно прошли (11OK/3,326с). Независимое review подтвердило разделение и сохранение guards.

Финальный полный прогон вне sandbox: **4044tests /33known errors /0failures /0skipped,916,005с**. Log `.cache/adr0053-final-regression.log`. Все33 sorted ERROR headers точно совпали с `.cache/adr0052-full-regression.log`; новых errors нет. Все31native/refusal/proof test lines завершились OK (14unit+5integration+1public+10refusal+1contract probe). Полный набор не зелёный из-за известных33 expectations errors; они остаются отдельной задачей.

После final suite manifest468package .py/.json,4public fixtures и SHA256 wheel совпали с final-installed evidence. Все36JSON schema files byte-identical к52; новый wire не добавлен. Production/tests/public fixtures после финальных проверок не менялись. Markdown-пути и `git diff --check` проверены отдельно; anchors не проверялись.

После закрытия53 — отдельный контракт ADR-0054 для matching generation family assertion/projection и versioned wire/CLI доставки нового разрешения. До него generation/JSON1/2/3 по-прежнему отказывают при nonNone. Никакие Wound10/Wind/coexistence/recursive-repeat consumers не открыты.

Нормативные BOOK-PLAYER-GUIDE1.4 Rules116/119/122–123/Wounds190 и BOOK-GM-GUIDE1.1 Champions92 прежние, проверены при52. Новых страниц/полного чтения книг, Rule IDs или house rules при native интеграции нет.
