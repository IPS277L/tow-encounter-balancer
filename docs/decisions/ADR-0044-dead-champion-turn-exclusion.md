# ADR-0044: исключение оставшегося хода погибшего Champion-Wizard

Статус: реализован и закрыт [итоговым аудитом](../audits/m8-dead-champion-readiness.md), 2026-10-28. Frozen models/pure consumer, journal/runner и propagation проверены в этой ограниченной границе. [Инвентаризация](../audits/m8-continuation-inventory.md) и [конечный probe](../examples/m8/dead_champion_contract_probe.py) проверяют выбор границы через существующие public API. Порядок M8 сохраняется.

## Причина и источники

До интеграции свежий допустимый ADR-0037 сценарий воспроизводил пробел: три Minion Attack дают Wizard поверхностные Wounds 1, 2 и lethal 25. Champion lifecycle уже завершён, pending отсутствует, но Wizard на стороне Opposition ещё должен ходить. После остальных живых участников runner возвращал `unsupported_chronology`: мёртвый Wizard не выбирается, а его ход не completed/excluded. Если Wizard уже завершил ход, такого пробела нет. Наличие живых союзников Wizard не позволяет объявить его смерть победой.

Непосредственно прочитаны локальные извлечённые страницы выбранных книг:

| Источник | Основание |
| --- | --- |
| BOOK-PLAYER-GUIDE 1.4, гл. V Rules / Combat, стр. 112 | Один ход участника за раунд; ход атакующего полностью завершается до передачи следующему. |
| Та же книга, Rules / Wounds & Conditions, стр. 121; Wounds Table, стр. 190–191 | Untreated Wounds увеличивают следующий бросок; строки 24–27+ смертельны. Строка 26 допускает dying words, а не дополнительное боевое действие. Необязательный трофей строки 27+ требует Close и свободной руки; текущий Shooting scope его не выбирает. |
| BOOK-GM-GUIDE 1.1, гл. VII Allies and Antagonists / Champions, стр. 92; PG1.4, Wounding NPCs, стр. 191 | Champion использует Wounds Table, а не Minion disposition. |

Exclusion — техническое представление уже установленной смерти в текущем scheduler; книга не задаёт имя такого receipt. Новых Rule IDs или house rules нет. Нормализованные основания: RULE-COMBAT-001/002, RULE-NPC-004 и [Wounds](../rules/wounds-and-conditions.md). Near Miss, Last Stand, Miscast death, смерть действующего и произвольное saved state не входят в этот контракт.

## Вход и полный источник

Новые frozen/slotted модели в `src/towr/domain/npc_roster_dead_champion_models.py`:

- `NpcRosterDeadChampionExclusionRequest(id: str, state: NpcRosterCastingState, attack: NpcRosterChampionAttackResult)`.
- `NpcRosterDeadChampionExclusionResult(source: NpcRosterDeadChampionExclusionRequest)` с чистым derived `state`.

`id` — непустой stable phase ID. В запросе хранится полный завершённый bound Attack result, включая исходный root, request, execution, roll, daily registration и Wound completion. Совпадения ID или только post-state недостаточно для journal provenance.

Preflight до проекции:

1. Строгие typed models и `state == attack.state`, включая все поля обоих owners, histories, spatial, magic, expiries и receipts. Только непосредственный post-state этой атаки; другой полный источник с теми же IDs отклоняется.
2. Цель — единственный связанный Wizard/Champion; атакующий — живой вражеский Minion и текущий active actor. Round/actor/execution совпадают с результатом атаки. В активном ходу ровно один standard Attack slot, уже исполненный именно этим execution receipt.
3. Wound completion существует, имеет `ACCEPTED`, завершающий lethal Wound и разрешённый effect; актуальный injury цели имеет `dead=True`. Допускаются только четыре lethal WoundEntryId. Для них injury обязан точно равняться rolled injury с единственным изменением effect_resolved новой Wound; один слабый WoundEffectResult DTO не доказывает этой проекции. Не подходят miss, Stagger, поверхностная Wound или отменённая Near Miss.
4. `attack.pending_follow_ups` пуст; `champion_attack.pending`, `pending_minion_attack`, `pending_miscast`, `pending_movement`, `pending_interruption` отсутствуют. Pending нельзя закрыть побочным exclusion.
5. Цель присутствует в текущих participants и ещё должна ходить: не active, не completed и не excluded. Already-completed или already-excluded request отклоняется. Dispatcher для completed цели пропускает фазу, сохраняя completed; no-op result не создаётся.

Не требуются Endurance profile, GM decision, inventory или RNG. Новый persistent death receipt не нужен в этой границе: excluded marker запрещает повтор, а точное применение результата привязано к полному исходному root. Это не защита от намеренного восстановления старого immutable snapshot и не доказательство подлинности внешнего forged object.

## Единственная проекция и применение

В результате изменяются только:

```python
combat = replace(source.state.round_state,
    excluded_turn_entity_ids=(*source.state.round_state.excluded_turn_entity_ids, wizard_id))
champion = replace(source.state.champion_attack, round_state=combat)
state = replace(source.state, round_state=combat, champion_attack=champion)
```

Сохраняются active turn атакующего, все completed/excluded prefixes, participants, roster/definitions/injuries, полный spatial archive и once-per-round usage, Wizard/casting/pool, оба attack ledgers, daily receipts, consumed Wound rolls/executions, expiries и end-turn receipts. Ни одна Wound, Condition или application не исполняется повторно. Исключение не заканчивает ход атакующего и не делает дополнительного action receipt. Dead actor не удаляется из архивов и не добавляется в completed.

В `src/towr/rules/npc_roster_dead_champion_resolution.py`:

- `exclude_npc_roster_dead_champion(request) -> NpcRosterDeadChampionExclusionResult` — чистое создание результата, без RNG и обращения к kernel.
- `apply_npc_roster_dead_champion_exclusion(state, result) -> NpcRosterCastingState` — проверка typed result и точного `state == result.source.state`, затем перенос `result.state`; повтор, stale source и изменённый unrelated field отклоняются.

Existing Minion-only `NpcRoundExclusionRequest`/`NpcRoundRequest` не расширяются и не обходятся фильтрацией Champion из roster. Общая иерархия turn-exclusion handlers не создаётся. Допустима маленькая явная проекция полного root.

## Journal и runner

На интеграционном срезе новый result добавлен в закрытый `NpcMagicStepResult`/`_RESULT_TYPES`. `before` берётся из `source.state`, `after` — derived state, `id` — `source.id`; actor шага остаётся атакующим. Это continuation его Attack, не ход погибшего Wizard.

`NpcMagicScenarioResult` обязан требовать, чтобы **непосредственно предыдущий шаг** содержал полный `NpcRosterChampionAttackResult`, равный `result.source.attack`. Одна state-chain equality не исключает подмену иного броска с тем же итоговым состоянием. Guard нужен и на границе публикации runner. Его можно добавить явной проверкой predecessor в существующем обходе журнала; общий event bus и новая универсальная policy API не требуются.

Проверка двусторонняя: после подходящей lethal Attack с awaiting Wizard **следующий шаг обязан быть matching exclusion**. Другой шаг, включая end-turn, и завершение журнала до exclusion отклоняются. Поэтому прежний журнал Attack → end-turn → chronology stop после интеграции не остаётся допустимым обходом обязательной фазы. Ожидание выводится из полного предыдущего Attack result при обходе и публикации; отдельного persistent pending/receipt не требуется. Для completed Wizard такого ожидания нет.

Runner публикует exclusion сразу после завершённого lethal Champion Attack, если target awaiting, до end-turn атакующего, terminal check и следующей активации. Если target completed, не публикует ничего. Следующий end-turn исполняет прежний `NpcWoundTurnEndRequest`; оставшиеся живые участники продолжают через обычный scheduler.

Для exclusion не нужен scene frame: он ничего не перемещает. Для следующего живого action требуется authored post-death frame с полными архивными placements и только live actor IDs. Missing frame сохраняет `MISSING_SCENE`, неизвестный маршрут и остальные stops не исправляются автоматически. Round advance продолжает использовать существующую live projection.

`executed_actions` и число начатых раундов от самой фазы не меняются. Она может позволить закончить ранее зависавший раунд; completed/outcome выводятся прежними формулами. Смерть Wizard сама по себе не является objective/perspective defeat при живых союзных Minions. Дополнительный журналовый шаг может сдвинуть последующие phase IDs; seed scheme, порядок RNG и trial indices не меняются.

## Граница propagation

Simulation/process/evaluation/staged/generation и JSON/CLI получают новое законченное поведение только через существующий runner. Новых wire fields, counts/outcomes, request policies или версии Schema не требуется. Одинаковый seed после расширения consumer может дать иной итог formerly-unsupported trial; это ожидаемое расширение исполнения, а не обещание прежних sampling results. Старые Minion families не меняются.

Все прочие Wound effects, Miscast preparation/application, ordinary Attack Give Ground, actor/target/end-turn injury restrictions и общие chronology gaps остаются неподдержанными. Этот consumer не является полным death lifecycle, recovery/campaign/corpse engine или решением открытых Miscast ambiguities.

## Проверки и последовательность

1. **Модели и pure consumer:** guards выше, детерминированный результат и exact-source apply; positive awaiting case, completed/excluded rejection, pending/nonlethal/wrong actor/slot/stale source, full archive/ledger/clock equality, input immutability и отсутствие RNG/kernel calls. Сначала этот законченный срез.
2. **Journal и runner:** двусторонний immediate predecessor/result guard, запрет другого шага/конца журнала до mandatory exclusion, namespace/uniqueness/chain, exclusion до end-turn и terminal; fresh admitted lethal traces при обеих сторонах Wizard, completed skip, новый раунд, post-death missing frame, живые союзники и четыре existing outcomes/counters. Иные stops сохраняются.
3. **Propagation и аудит:** real sequential/spawn records/summary parity, source/input/RNG/cleanup guards и проверка existing JSON/CLI без изменения форматов; public production example вместо ручной проекции, матрица правил/контракта, полная регрессия с отдельным сравнением известных ошибок окружения.

Текущий finite probe использует production runner и validated journal: awaiting цель автоматически исключается до end-turn, completed цель пропускается, missing frame сохраняется после исключения. Прежняя ручная проекция заменена production evidence без изменения authored inputs/dice. [Subprocess test](../../tests/integration/test_m8_dead_champion_contract_probe.py) проверяет его отдельный bundle и сохранённый stdout. Production acceptance tests добавлены на соответствующих срезах.


## Реализованный первый срез

2026-10-28: [request/result](../../src/towr/domain/npc_roster_dead_champion_models.py) и [pure consumer/apply](../../src/towr/rules/npc_roster_dead_champion_resolution.py) реализованы. Модель проверяет exact full post-Attack source, accepted lethal completion, полностью разрешённую новую Wound, active living enemy Minion и единственный executed standard Attack slot, отсутствие всех pending и awaiting Wizard. Результат выводит только excluded + Champion round; apply требует полный неизменённый source. No-op для completed/excluded не создаётся, дополнительного death ledger нет.

[Unit tests](../../tests/unit/test_m8_npc_roster_dead_champion.py) и [integration tests](../../tests/integration/test_m8_npc_roster_dead_champion.py) проверяют реальные bound lethal источники, source/replay/typed guards, archives/ledgers и передачу результата существующему end-turn. Точный результат проверок — в [статусе](../project-status.md#последняя-проверка). Domain получает только domain/stdlib imports, rules не вызывают RNG/kernel и не меняют прежние reducers.

Первый срез не подключал journal/runner и сохранял прежний chronology gap. Интеграция и последующий propagation/audit завершены ниже.


## Реализованная journal/runner интеграция

2026-10-28: новый result включён в закрытый [NpcMagicStepResult](../../src/towr/domain/npc_magic_step_models.py). [Journal policy](../../src/towr/domain/npc_magic_journal_policy.py) выводит обязанность exclusion из непосредственно предыдущего bound Champion Attack: цель dead/awaiting, Attack не имеет pending follow-ups. Строгие accepted/completion/injury/slot guards остаются в typed request. Это исключает обход malformed completion через отсутствие обязательной фазы и не подменяет Wound pending consumer.

`validate_magic_step_predecessor(previous, step)` проверяет обе стороны: подходящая Attack требует непосредственно следующего matching full-witness exclusion; exclusion требует подходящую Attack перед собой. `step=None` означает конец журнала и отклоняется при незакрытой обязанности. [Result constructor](../../src/towr/domain/npc_magic_scenario_result_models.py) вызывает общий guard на каждом шаге и на финальном tail; [runner publish](../../src/towr/engine/npc_magic_scenario_runner.py) использует тот же guard и публикует pure exclusion немедленно после lethal Attack. Completed цель не создаёт no-op phase. Нового persistent pending/receipt, scene lookup для exclusion или framework нет.

[Unit journal tests](../../tests/unit/test_m8_dead_champion_journal.py), [runner integration](../../tests/integration/test_m8_dead_champion_runner.py) и обновлённый [public probe](../examples/m8/dead_champion_contract_probe.py) проверяют source/namespace/mandatory order, два разных полных Attack traces с равным post-state, awaiting/completed, четыре lethal строки, remaining allies/new round и missing post-death frame после уже выполненного exclusion. Действие и RNG не дублируются. Прежние unsupported labels/diagnosis и остальные families не расширены. Точные проверки — в [статусе](../project-status.md#последняя-проверка). Real sequential/process/JSON propagation и итоговый аудит завершены следующим срезом, без новых wire fields/seed scheme.


## Propagation и итоговый аудит

[Аудит](../audits/m8-dead-champion-readiness.md) сопоставляет источники/guards с45implementation tests (25unit/20integration) и отдельным public probe. [7 новых propagation tests](../../tests/integration/test_m8_dead_champion_propagation.py) проверяют реальные trial/sequential/spawn records/source/seed/counters, обе стороны и perspective, unsupported denominator/prefix, JSON reconstruct/parse перед исполнением и default service/CLI. Новый [JSON request](../examples/m8/json/dead-champion-v1.request.json) / [result](../examples/m8/json/dead-champion-v1.result.json) — выбранный стандартный RNG witness: seed31, Wounds3/2/25, exclusion1, actions/started/completed4/1/1, не оценка вероятности сложности.

Изолированный актуальный wheel совпал по442Python/Schema files с source/installed site; public bundle и actual trace проверены без PYTHONPATH из external cwd. `simulate-magic` module/console ×sequential/process прошли death/missing-frame cases, `balance-magic` — прежний обычный fixture для совместимости. Все прежние source/Python tests/tools/fixtures сохранены; production при аудитном срезе не менялся. Full3470tests/33прежнихerrors/155,370с, точные error Counters неизменны. Ограничения runtime/подлинности DTO/прочих consumers и evidence — в аудите; новых Rule IDs/house rules/Schema/seed scheme нет. ADR-0044 завершён в заявленной narrow boundary.
