# ADR-0053: native повторный Leg Spasm с journal witnesses

Дата: 2026-11-01. Статус: **пункты1–4 выполнены, ADR закрыт в принятой native границе**. [Итоговый аудит](../audits/m8-native-repeated-leg-spasm-readiness.md). Prerequisites: [low-level52](ADR-0052-source-bound-repeated-leg-spasm-stand.md), [его аудит](../audits/m8-repeated-leg-spasm-stand-readiness.md), [native50](ADR-0050-native-stationary-wound-policy.md) и [transport51](ADR-0051-stationary-wound-generation-and-magic-json-v3.md).

## Граница и источники

Подключить существующий stand52 к native scenario/journal/diagnosis/runner при отдельном явном разрешении и с точными свидетелями собственного журнала. Low-level48/49/52 не расширять. Разрешён только один repeated stand после stand48 и одной новой rolled9, затем existing stationary context49. Сосуществование6/Wind/Grim при самом repeated stand, последующие repeated stands, treatment/Recover/ordinary movement остаются за границей52. Уже поддержанные пути6 через49/50, в том числе после завершённого stand52, сохраняются.

Нормативные источники прежние: BOOK-PLAYER-GUIDE1.4, гл.V Rules / Free Actions116, Giving Ground119, Conditions122/Prone123, приложение Wounds Table190; BOOK-GM-GUIDE1.1, гл.VII Champions92. Они проверены при ADR-0052; при подготовке53 нового чтения страниц/книг нет. Одна Condition, одна free move без enemy Close и retained terrain до treatment сохраняют смысл RULE-COMBAT-014 / RULE-HEALTH-005/008. Native permission, приоритет автоматического stand и journal admission — технический контракт эксперимента, не новое игровое правило или house rule.

## Отдельное разрешение и ранняя admission

Append-last поле `NpcMagicScenario.repeated_leg_spasm_continuation: NpcMagicRepeatedLegSpasmPolicy | None = None`. Новый enum содержит ровно `STAND_ONCE_WITH_JOURNAL_WITNESSES = 'stand_once_with_journal_witnesses'`.

- `None` оставляет прежние traces/stops/RNG для валидных входов: даже прежняя stationary policy не разрешает repeated stand. Старый `NpcMagicStationaryWoundPolicy` не получает нового значения или смысла. Исправление ранней admission повреждённых facts не обещает сохранять их прежний ошибочный путь.
- Новое nonNone требует именно typed `stationary_wound_continuation is LEG_SPASM_STAND_AND_CONTINUE`: оно разрешает first stand/context, от которых зависит52. Без base stationary policy — ранний ValueError, не no-op и не неявное включение.
- `miscast_continuation` независим. Проверить6допустимых сочетаний трёх nullable permissions и2недопустимых сочетания repeated-on/stationary-None; raw strings/bool/int вместо enum отвергаются до equality/RNG/worker dispatch.
- Shared pure native admission повторно проверяет original `scenario.facts` и обе прежние/new permissions, включая nested Miscast facts. Не заменять испорченные source объекты нормализованными clones. Runner, reconstructed Result, diagnosis/policy и parent-side trial/process preflight должны получить одинаковый strict отказ до RNG/publication/pool.

При подготовке контракта найден gap: runner делал `replace(scenario)`, но не `replace(scenario.facts)`, поэтому detached `no_external_condition_sources=1` мог дойти до RNG. Shared native admission53 теперь перепроверяет original facts/permissions в runner, Result, diagnosis/policy и parent/worker paths. Application boundary и generation arithmetic contract сохраняются; это программное исправление, не изменение книги. Исходный proof обновлён на фактический runner/noRNG guard после реализации.

## Ограниченный cursor вне battle root

Не добавлять archive/history поля к `NpcRosterCastingState`, не менять projections48/52 и не хранить копию произвольного журнала в каждом step. Нужен frozen/slotted `NpcMagicRepeatedLegSpasmHistory` в новом `domain/npc_magic_repeated_leg_spasm_policy.py` с четырьмя полями:

| Поле | Тип и смысл |
| --- | --- |
| `state` | Полный current `NpcRosterCastingState`, к которому относится cursor |
| `previous_stand` | `NpcRosterLegSpasmStandResult | None`, ровно первый recorded stand48 |
| `wound_attack` | `NpcRosterChampionAttackResult | None`, первый qualifying recorded Attack с новой9 после этого stand |
| `repeated_stand` | `NpcRosterRepeatedLegSpasmStandResult | None`, полное свидетельство уже израсходованного однократного разрешения |

Это bounded cursor, **не доказательство членства в журнале и не токен разрешения**. Constructor проверяет typed slots, source/actor/dependency consistency и strict original witnesses чисто, без reducers/RNG. Точная достижимость current из произвольной прошлой истории им не обещается. Подставленный caller cursor не может заменить derived cursor при publication или reconstruction.

Cursor current может законно содержать pending Miscast/Attack/movement или уже поддержанную Wound6: его собственная admission не должна глобально навязывать узкую active-Wizard phase/границу52. Проверки52 применяются к candidate/request в нужной фазе; historical witnesses сохраняют свои полные источники. Иначе cursor сломает существующие mandatory consumers до их dispatch.

Pure initial/advance helpers получают scenario; при новом None cursor=None и старые paths сохраняются. При opt-in начальное `state` — **`scenario.initial_runtime_state`**, не произвольный fresh snapshot. Advance проверяет `step.before == cursor.state`, затем обновляет state до полного `step.after`:

1. Первый admitted stand48 сохраняется целиком; не выбирать более удобный предыдущий result и не заменять его совпавшим ID/state. Второй stand48 не создаёт новое разрешение.
2. После него сохраняется первый completed, accepted, non-pending outer Attack с одной новой rolled9, удовлетворяющий low-level52 provenance относительно previous stand. До начала собственного хода проверяются только соответствующие attack/prefix guards: конструировать полный StandRequest52 на чужом активном ходу нельзя. Qualifying detection не исполняет executor и не выдумывает scheduler tail.
3. Admitted stand52 требует неиспользованный slot, точное полное equality обоих его source witnesses с cursor slots и source.state с cursor.state. После применения сохраняется full `repeated_stand`, а не bool `used` или один execution ID.
4. Прочие admitted steps продвигают только current state, сохраняя slots. Их нельзя очищать при смене round, окончании хода, отсутствии Prone или death. Более поздние9/6/Wind не переписывают уже выбранные witnesses и не открывают второе разрешение. Новую рану сначала полностью зарегистрировать; если дальнейший путь неподдержан, вернуть обычный stop, не исключение исполнения из-за cursor update. Уже поддержанный context49 путь6/expiry после repeated stand продолжает работать; новый cursor не создаёт для него stop.

Валидный completed Attack, не подходящий prefix scope52 (например9 при уже имеющейся history6), не является ошибкой cursor advance: обновить current, не заполнять qualifying slot и сохранить честный последующий stop. Ошибка types/source membership отделена от неподдержанной игровой ветви.

Не копировать/сканировать полный prefix после каждого step: размер cursor ограничен, один проход journal имеет O(n) обновлений. Это не общий event replay/DSL.

## Shared eligibility и публичные границы

Новые pure helpers: typed policy/dependency admission, repeated family/eligibility, построение proposal Request52 и cursor advance. Family требует bound current history и неиспользованные qualifying witnesses; eligibility дополнительно проверяет exact supplied frame, отсутствие enemy Close и unused free move. Request/executor52 остаются authoritative для всех canonical/provenance/clock guards.

`diagnose_npc_magic_unsupported(..., *, repeated_history: NpcMagicRepeatedLegSpasmHistory | None = None)` и `validate_magic_step_policy(..., *, repeated_history=...)` получают explicit cursor, не выводят его из wounds/receipt IDs. DefaultNone сохраняет прежние unwitnessed stops. Типизированный, но foreign-current cursor отвергается; отсутствие cursor не является положительным доказательством возможности repeated stand. Неверные типы/facts — ошибки admission, а не игровой UNSUPPORTED_PATH.

Standalone diagnosis с caller-supplied cursor — **проверка текущего состояния с явными finite witnesses**, не подтверждение валидности полного журнала. Для подтверждённого journal path caller использует reconstructed `NpcMagicScenarioResult`; именно его prefix validation обеспечивает membership. Не рекламировать cursor constructor или один positive diagnosis как замену этой проверке.

Порядок: существующие pending Miscast/Attack/movement и lethal Attack→dead exclusion имеют прежний приоритет; затем active turn, injury family и exact scene. Потенциальная повторная family с отсутствующим frame даёт MISSING_SCENE как existing stand path; unsafe/spent move/неподдержанная history даёт ACTOR_INJURY, без fallback к standalone Prone/Recover/Casting. При eligible repeated stand исполнение обязательно перед target/action selection и legacy stand. После него Casting/Protection/end получают прежний context49; terrain/история и Give Ground=False сохраняются. Новых unsupported labels нет.

## Runner и reconstructed journal

- Добавить `NpcRosterRepeatedLegSpasmStandResult` в закрытые `NpcMagicStepResult`/`_RESULT_TYPES`. Он не получает Miscast `origin_witness`, не расходует action и не увеличивает executed_actions/round counters. Pure transported result admission проверяет типы и полный источник, не исполняет stand повторно.
- Runner держит локальный cursor с initial runtime state. До любого executor checks используют текущий cursor. `publish` проверяет source/state/policy/predecessors и полные witnesses **своего** cursor, затем обновляет cursor/current и публикует step. Внешний cursor не принимается аргументом runner.
- `NpcMagicScenarioResult.__post_init__` заново выводит cursor из собственного admitted prefix в существующем loop. Constructor signature не принимает history/cache; ни совпадение `_current`, ни caller-created cursor не заменяют проход по steps. Final unsupported diagnosis получает cursor этого же прохода. Проверки terminal order, namespace/ID uniqueness, exact source chain, death/Miscast predecessors и round budget сохраняются.
- Foreigndice Attack с теми же ID/before/after/current может быть допустимым low-level52 witness, но stand53 journal обязан отвергнуть его, если **полного** result нет в его prefix. Правило действует в обе стороны и для предыдущего stand48; detached scalar aliases тоже проходят strict admission до equality.

## Native propagation и явный отказ transport

Существующие trial/sequential/process и explicit candidate-list/assessment/staged APIs сохраняют полный новый Scenario/source/denominator. Новый selected path проверяется в parent и spawn normalization; None не меняет old prefix/seeds/results. Не менять seed policy, агрегаты, round budget или исключать unsupported из trials.

Generation и JSON/CLI **не получают поддержку** новой permission в53. Это требует обязательных lossless refusal guards при добавлении Scenario field:

- `MagicCandidateGenerationRequest`/result/source admission отвергают template или candidate с новым nonNone до enumeration/projection/equality. Отдельного family assertion для нового поля пока нет; не строить temporary legacy Scenario, удалив flag.
- Shared scenario encoder `_magic_scenario_json.py` и обе magic families1/2/3 отвергают nonNone до выдачи документа, включая native result/source echo. Closed schemas продолжают отвергать неизвестное новое поле даже null. При None все нынешние wire документы/versions/bytes сохраняются; новое поле не сериализуется. Schema/version4 не вводится.
- Domain/engine не импортируют generation/codec/CLI. Эти guards предохраняют прежние границы от silent field loss, не являются новым wire feature.

## Исполняемый finite proof

[Probe](../examples/m8/repeated_leg_spasm_native_contract_probe.py), [stdout](../examples/m8/repeated_leg_spasm_native_contract_probe.output.txt), [copied-bundle test](../../tests/integration/test_m8_repeated_leg_spasm_native_contract_probe.py). Копировать вместе с `stationary_wound_runner.py` и `magic_scenario.py`; только existing public APIs, никаких будущих permission/cursor types.

Четыре прежних сочетания stationary/Miscast сохраняют first9 stop7d10 либо second9 stop24d10:62d10. Их закрытые journals восстанавливаются. Actual stand48 и Attack предшествуют точному end/start tail; manual stand52 сохраняет terrain/history. После Step union расширения probe проверяет прежний отказ **policy** без нового разрешения вместо TypeError типа, а facts — реальным fixed runner guard. Ещё24d10 дают альтернативный действительный Attack с переставленными успешными dice: одинаковые ID/source/current, разные полные witnesses. Low-level52 принимает его finite lineage; native tests53 отвергают смешение journals. Всего86scripted d10; proof остаётся old-policy boundary, новый automatic пример вынесен в аудит.

Историческая contract-only проверка —1test OK/1,240с вне sandbox, без production changes; ориентир4013/33known относился к52. После реализации обновлённый probe прошёл вместе с прежними39targeted tests (4,217с). Это не объявление нового полного набора зелёным; итог полной проверки53 фиксируется в аудите.

## План реализации и приёмки

1. **Выполнено:** append-last permission/dependency, bounded cursor, pure admission/membership и strict facts guard; initial_runtime_state, foreign equal-state/different-dice, no reset/overwrite, raw aliases до RNG.
2. **Выполнено:** Step/journal/diagnosis/runner с одним executor52, mandatory order, actual repeated path и post-stand6 expiry, missing/unsafe/scope controls, pending/death priority. Старые48/49/52 whitelists не расширены.
3. **Выполнено:** native sequential/spawn/explicit-list/staged source/records/denominator; parent preflight; generation/JSON1/2/3 early lossless refusals без нового wire.
4. **Выполнено:** actual public330d10 и installed/native spawn,468package source/wheel/installed paths+hashes; финальный full4044tests/33known errors/0failures/0skipped,916,005с. Все33 ERROR headers прежние,31native/refusal/proof tests OK. После suite manifests/wheel неизменны;36schemas прежние. Первый неуспешный прогон и исправление admission boundary/fixtures описаны в итоговом аудите, не подменяют финальный результат.

Независимое read-only review контракта/probe блокеров не оставило. Уточнены фактическое имя generation API, отсутствие глобального52 phase gate у cursor и сохранение supported context49 путей6 после повторного stand. Production и proof после успешной проверки не менялись.
