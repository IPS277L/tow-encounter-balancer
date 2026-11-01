# ADR-0054: repeated Leg Spasm family assertion и Magic JSON/CLI v4

Дата: 2026-11-02. Статус: **реализован и закрыт [итоговым аудитом](../audits/m8-repeated-leg-spasm-transport-readiness.md)**. Основа: [закрытый native53](ADR-0053-native-repeated-leg-spasm-continuation.md), [его аудит](../audits/m8-native-repeated-leg-spasm-readiness.md), [generation/wire3 ADR-0051](ADR-0051-stationary-wound-generation-and-magic-json-v3.md).

## Граница

Передать существующее `NpcMagicRepeatedLegSpasmPolicy.STAND_ONCE_WITH_JOURNAL_WITNESSES` через bounded generation и новый versioned wire. Никакого нового gameplay: один repeat после stand48 и одной новой rolled9, точные journal witnesses, post-stand context49 и supported6/expiry остаются ровно в native53. Третья9, coexistence6/Wind при repeated stand, Wound10/Grim, movement/Recover/treatment и произвольный бой не открываются. Все unsupported trials остаются в denominator.

Это контракт передачи разрешения и полного источника, не новое извлечение правил. Нормативная база прежняя: BOOK-PLAYER-GUIDE1.4, гл.V Free Actions116/Giving Ground119/Conditions122–123, приложение Wounds Table190; BOOK-GM-GUIDE1.1, гл.VII Champions92. Новых страниц/полного чтения книг, Rule IDs и house rules в54 нет. Domain/engine и semantics native53 не зависят от codec/CLI/generation.

## Native generation family assertion

Append-last поле `MagicCandidateGenerationRequest.repeated_leg_spasm_continuation: NpcMagicRepeatedLegSpasmPolicy | None = None`. Это отдельное подтверждение разрешения для **всех** generated subsets и supplied frames, а не значение, автоматически взятое из template. Omitted означает None. Source Scenario уже имеет свой отдельный field53.

До materialization/collection traversal/count-vector enumeration/projection/RNG проверить:

- На обеих сторонах все три permissions имеют настоящие типы; original nested facts/Miscast facts проходят strict admission до equality. Raw string, bool/int/dict, иной enum не принимаются даже при same-value equality.
- Полное matching template/family для Miscast, stationary и repeated. Новый selected template с omitted/None family и обратное несовпадение — ValueError. Не менять default, source или candidate, чтобы скрыть mismatch.
- Repeated nonNone требует на обеих сторонах base stationary `LEG_SPASM_STAND_AND_CONTINUE`. Miscast независим. Шесть valid и два invalid сочетания сохраняют native53 смысл; новый field не включает base или Miscast неявно.
- Утверждения facts/frames обязательны для каждого subset; удалённые actors не превращаются во внешних наблюдателей. Нельзя угадывать отсутствующие scenes/routes, пропускать неудобную цель или чинить projected frame.

Request admission остаётся **арифметической**: permissions/facts, groups/counts, seed/trials/stages/window и bounds. Не вызывать полную Scenario construction/subset projection через seed/trial helper. Полная original source/template admission выполняется в factory/result перед enumeration и при construction каждого реального subset. Разделение native53 arithmetic/execution preflight сохраняется.

`_project_candidate` создаёт fresh Scenario и должен **явно передавать family repeated field**, как два прежних permissions; defaultNone здесь недопустим для opted family. Не менять enumeration, count vectors, ordered IDs/actors/definitions/policies/frames, objectives, retained sides, seed scheme, budgets или ranking.

GenerationResult до `_count_vectors`, `_project_candidate` и equality проверяет **все** candidate.scenario: original typed facts/permissions и matching со всеми family assertions. Затем точный полный projection сравнивается с source. Factory/source reconstruction/unpickled request и все generation→staged→report/derived cache→assessment→summary→encoder edges повторно проверяют original sources до equality; compare=False cache не заменяется заново вычисленным значением для сокрытия порчи. Изменение типов или mismatch в последнем candidate должно отвергаться до enumeration любого вектора.

Old positional constructors и явный None сохраняют прежние результаты; новый field добавляется только последним. Лимиты C/upper trial cost, retained source order и arithmetic-only guarantees проверяются детерминированно, включая огромные counts без materialization.

## Wire v4: обязательные nullable разрешения

Новый wire **только** для `simulate-magic` и `balance-magic`; ruleset остаётся `towr-pg1.4-gmg1.1`. JSON4 fresh-only: source permissions, не сохранённые battle state/журнал/cursor и не save/resume.

| Место | Контракт4 |
| --- | --- |
| simulation `scenario.repeated_leg_spasm_continuation` | Required, null либо точная строка `stand_once_with_journal_witnesses` |
| balance `reserve.scenario.repeated_leg_spasm_continuation` | То же; значение собственного native Scenario |
| balance `generation.repeated_leg_spasm_continuation` | Отдельное required nullable family assertion, строго matching reserve |

V4 также требует оба прежних поля: `miscast_continuation` (null/typed object формы2) и `stationary_wound_continuation` (null/точная строка формы3). Nullable не означает optional. Новое nonNone требует selected stationary; Miscast не выводится из него. При новом None и остальных None документ всё равно остаётся4, default wire version остаётся1.

Добавить6schemas `magic-{simulation,balance}-{request,result,error}-v4.schema.json`, итого24magic/42package schemas, validator cache24. Новые request4 имеют собственный закрытый список Scenario/generation properties с `additionalProperties:false`; нельзя расширять закрытый Scenario3 через `allOf`. Неизменённые фрагменты можно брать локальными bundled refs1/2/3, Scenario4 — собственный fragment, balance4 ссылается на него. Все refs разрешаются без сети из установленного wheel.

Структурная schema проверяет required nullable enums/types. Repeated→stationary dependency и reserve/family equality обязательно проверяются typed/semantic admission, до materialization/RNG. Изолированная новая dependency error относится к `/scenario/repeated_leg_spasm_continuation` либо `/reserve/scenario/repeated_leg_spasm_continuation`; isolated family mismatch — `/generation/repeated_leg_spasm_continuation`. Прежние поля сохраняют порядок и пути своих отказов при нескольких одновременных ошибках. Не добавлять неоговорённый schema-dependent приоритет ошибок.

## Lossless compatibility и mapper

JSON1/2/3 продолжают запрещать новый key **даже null** и отвергают encoding native nonNone до definitions/actors/source projection. При None прежние документы/echo/bytes на одинаковом runtime сохраняются. JSON1/2 по-прежнему не принимают stationary; старые Miscast правила1/2/3 не меняются.

В `_magic_scenario_json.py` разделить strict type/source validation и versioned lossless gate: typed helper должен разрешать уже валидную native repeated policy, а `scenario_document` запрещает её именно в1/2/3. Для4 parser явно создаёт третье typed permission до Scenario admission, encoder явно пишет required field. Не строить temporary legacy view удалением нового flag.

Balance parser отдельно читает family repeated field и проверяет matching/dependency до GenerationRequest; encoder отдельно отражает family assertion и reserve flag. Request/result echo сохраняет все три policy values, definition order, полный generation/source/report chain и requested version. Parser/encoder не исполняют generation/simulation, не создают RNG/pool и не нормализуют повреждённые original sources.

## Версии команд, ошибок и CLI

Две magic families принимают1/2/3/4 через explicit `magic_versions`; совместимый `magic_v2=True` остаётся1/2. Не вводить общий permissive reader или implicit upgrade. Шесть nonmagic routes остаются только1. Неизвестная следующая magic version5 не принимается.

`MagicSimulationCommand`, `MagicBalanceCommand`, их input subtypes и generation/evaluation/execution errors поддерживают4 при default1. Base `MagicInputError` может сохранить прежнюю область1/2. Полностью прочитанный requested4 остаётся4 во всех success/error envelopes, включая null permission и runtime failures.

- Lexical/UTF-8/duplicate-key/NaN/float/surrogate/trailing-data failures до полной strict decode дают fallback1 и null request_id.
- После полной decode recognised4 shape/semantic failures отражают4 и decoded nonblank string request_id. Не брать metadata из частично разобранного текста.
- Unsupported5, missing/non-string version дают fallback1; **полностью decoded nonblank request_id сохраняется**, как текущий reader. Для unsupported5 code/path — `unsupported_version`/`/schema_version`.
- Runtime phase errors берут own command4, а не version/request_id чужой cause. Generation/evaluation classification, exit codes, stage/count/candidate context и privacy сохраняются; никаких traceback/notes/private source/partial reports в public envelope.

CLI help у двух magic commands отражает4; mode/workers/batch_size, exit statuses, stdin/file/output paths и closed pipes сохраняют смысл. Module/console/installed JSON4 должны совпадать на одном runtime.

## Исполняемый production proof

[Probe](../examples/m8/repeated_leg_spasm_transport_contract_probe.py), [stdout](../examples/m8/repeated_leg_spasm_transport_contract_probe.output.txt), [copied test](../../tests/integration/test_m8_repeated_leg_spasm_transport_contract_probe.py). Six-file bundle: probe, `generation_contract_probe.py`, `stationary_wound_runner.py`, `magic_scenario.py` и два genuine v3 request JSON.

Независимый finite inverse сохранён как oracle полного fixture, с canonical JSON различением bool/int. Production parser4/request echo сопоставляется с ним для12документов и6valid/2invalid policies. Production generator строит30полных subsets; source/IDs/order/C/budgets/seeds/permissions сравниваются с manual oracle. Новые unit tests дополнительно покрывают все4vectors обеих perspectives для каждой valid policy. Matching family assertion обязателен; permissions не наследуются.

Actual native journal first9→stand48→second9→stand52 расходует48d10. Отдельная scripted simulation48/summary кодируется в result4 с полным исходным scenario; standard seeded balance4 действительно исполняет generation/stages и проходит full result/source echo. Genuine legacy1/2/3 inputs создаются отдельно, новое поле отвергается даже null; native nonNone encoding даёт lossless refusal. Unknown5 даёт fallback1 с decoded ID, lexical failures сохраняют fallback1/null ID. Flag stripping и временных legacy views нет.

Direct proof и copied unittest прошли; wrapper1test/5,406с вне sandbox проверил exact stdout/empty stderr и SHA256 всех6source/copied files. Прежний secure TEMP/automatic-review timeout больше не является незавершённой проверкой этой версии.

[Generated runner](../examples/m8/repeated_leg_spasm_generation_runner.py) дополняет proof:1426scripted d10, actual generated3/4actors, post6 expiry/third9 stops, полные seq/spawn staged sources, бюджет и denominator. Новый helper проверяет его отдельно от прежнего native330; [Итоговый аудит](../audits/m8-repeated-leg-spasm-transport-readiness.md) подтвердил fresh installed/source/module/console/spawn и составной regression result:540integration +3538unit;33known errors без новых failures.

## Реализация и проверяемые этапы

1. Native generation field, strict3policy matching/dependency, arithmetic request/full-source factory guards и explicit projection. Детерминированные tests всех6valid/2invalid сочетаний, обеих perspectives, C/budgets/seeds, malformed template/family/first-last candidate до enumeration/equality; actual generated3/4actor first9→stand48→second9→stand52 и post6/third9 controls, sequential/spawn/explicit staged source parity.
2. Simulation4:3schemas, shared mapper/type-vs-version gates, command/error4 metadata, parser/encoder/service/CLI, public JSON. На промежуточном этапе supported versions разделены по family: simulation4 уже работает, balance4 ещё отказывает;21magic/39total/cache21 допустимы только как явно промежуточная граница.
3. Balance4:3schemas и полный registry24/42/cache24, independent reserve/family flags, all source/report/cache guards, service/phase errors4 и CLI. Definition/frame order и source counters/denominator не теряются.
4. Полный source/wheel/installed/module/console/spawn audit, public copied bundles и финальная регрессия. Проверить field-null refusals1/2/3,4dependency/mismatch/error paths/strict lexical fallback/unknown5,6old routes, privacy/late-stage failures и old source snapshots на одном runtime. Known33 Python3.12 expectations сверять exact ERROR headers отдельно, новых errors/failures быть не должно.

После каждого шага релевантные проверки, без запроса «продолжаем» между внутренними шагами. Полная регрессия/audit — на границе вехи. После закрытия54 следующий gameplay consumer выбирается отдельно по inventory и первичным источникам, а не добавляется под видом доставки policy.
