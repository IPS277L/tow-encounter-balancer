# ADR-0049: stationary continuation после Leg Spasm stand

Дата: 2026-11-01. Статус: **пункты1–4 завершены, ADR закрыт low-level аудитом**. Следует за закрытым [ADR-0048](ADR-0048-source-bound-leg-spasm-stand.md) и его [аудитом](../audits/m8-leg-spasm-stand-readiness.md). Веха — source-bound low-level Casting, incoming Shooting/Protection и end-turn при сохранённом Leg Spasm terrain. Автоматический runner, native scenario policy и transport подключаются отдельным следующим контрактом.

## Книжное основание

Непосредственно прочитаны локальные постраничные тексты выбранных редакций, не changelog:

| Источник | Следствие для контракта |
| --- | --- |
| BOOK-PLAYER-GUIDE1.4, приложение Wounds Table190, строка9 | Free move/Recover снимают Prone; до treatment все движения считаются Difficult Terrain. Ни снятие Prone, ни stationary action не лечат рану и не удаляют restriction. |
| Та же книга, гл.V Rules / Difficult Terrain115, Free Actions116 | Crossing на своём ходу требует Athletics; stand выполняется вместо free movement. Stationary Casting и обычный Opposed Test защиты не являются crossing и не создают дополнительный terrain Test. |
| Та же книга, Attack Tests118, Giving Ground119 | Защищаться можно Athletics либо Defence при подходящем вооружении. Give Ground запрещён через области, которые персонаж считает Difficult Terrain. Следовательно, untreated Leg Spasm запрещает Give Ground даже после stand; обычное движение не становится вообще невозможным. |
| Та же книга, Conditions122/Drained и Prone123 | Учитываются все сохраняющиеся причины Condition. Drained запрещает bonus dice и обычный Glorious, сохраняя penalties/Grim. Снятие Prone убирает именно Prone Shooting modifier, а не terrain restriction. |
| Та же книга, Wounds Table190, строка6 | Stomach Blow даёт Drained до конца следующего собственного хода. Ни чужой end-turn, ни следующий раунд сами по себе этот эффект не снимают. Запись Wound после expiry остаётся untreated/unhealed. |
| Та же книга, Wounds Table190–191, строки10/13/14/17 и другие | Next-Test Grim, Critical-on-removal, action restrictions и иные последствия не эквивалентны movement-only restriction9. Их нельзя включить общей whitelist. |
| Та же книга, гл.VIII Casting156 / Miscasts157 | Casting расходует action, сохраняет накопление и обязательные pending Miscast; stationary admission не даёт права их пропустить или очистить Pool. |
| BOOK-GM-GUIDE1.1, гл.VII Champions92 | Champion использует Wounds Table и полный lifecycle/daily registration. |

Это уточнение RULE-HEALTH-003/005/008 и RULE-COMBAT-014 в пределах существующих правил; нового house rule или игрового вопроса к пользователю нет. Книги не задают техническую opt-in policy и устройство source witness — ниже это архитектурные решения.

## Почему нельзя ослабить существующие guards

- `NpcRosterCastingRequest` отвергает любой restriction effect; его result уже сохраняет caster injury/expiry/history без временного очищения.
- `NpcChampionAttackRequest` отвергает Drained и все active Wound effects. Его `NpcChampionAttackState` не содержит полного spatial/magic/expiry owner: сам по себе lower-level state недостаточен для новой области.
- `prepare_npc_roster_shooting` сейчас вычисляет эффективную возможность Give Ground только с учётом Prone. После stand она снова стала бы True при authored departure=True. Для Wound9 нужно отдельно учесть запрет Giving Ground119.
- `NpcWoundTurnEndRequest` отвергает restrictions, а дальнейшая проверка независимых причин читает `e.condition` без проверки типа. Простое расширение whitelist приведёт к ошибке при terrain + timed Drained.
- `_injury_supported`, diagnosis, journal policy и runner не знают нового consumer. Этот ADR их не расширяет: существующие None/opted unsupported stops остаются прежними.

Подмена injury временной копией без terrain, ручное копирование чужих expiry и исполнение lower-level результата как будто это уже full-owner transition запрещены.

## Явный контекст полного источника

Новый узкий модуль `domain/npc_stationary_wound_models.py`:

```python
NpcStationaryWoundContext(
    state: NpcRosterCastingState,
    actor_id: str,
    no_external_condition_sources: bool,
)
```

Frozen/slotted модель хранит только полный исходный snapshot, actor ID и обязательный strict-True факт. Нет default для факта; отсутствие известного effect не доказывает отсутствие внешней причины. Первый scope требует этот факт от caller, как authored сцена уже требует отсутствие внешних Condition sources. Опциональный контекст в action API — явное разрешение использовать эту узкую границу, а не автоматический выбор действия.

Вычисляемые views: исходная injury, ordered canonical terrain effects, ordered condition effects, active/expired Stomach Blow sources и `can_give_ground=False`. Нельзя передать caller-supplied очищенную injury, готовый список effects или произвольную способность двигаться. Нет общего effect dispatcher, нового языка правил или копии owner.

### Admission

- Actor — живой Wizard/Champion полного owner. Conditions — только Staggered/Drained; Prone/Broken/Defenceless/другие Conditions требуют отдельного consumer. Нужен минимум один Leg Spasm.
- Все Wounds resolved, untreated, unhealed; entries только superficial1–3, Leg Spasm9 и Stomach Blow6. Строгие integer/roll/origin проверки и canonical totals; fixed-entry provenance не превращается в вымышленные dice.
- Для каждого9 после stand остаётся ровно terrain/UNTIL_TREATED того же sequence, без Prone effects. Для superficial effects отсутствуют. Multiple9 допускаются с полной проверкой каждой записи; порядок effects сохраняется.
- Для активного6 нужен ровно Drained/END_OF_NEXT_TURN, совпадающий с одним existing `NpcStomachBlowExpiry` и его actual attack/daily/roll witness. Missing/duplicate/foreign expiry, неподходящие durations, overdue clock и pending phases отвергаются до RNG.
- Исторический6 без active effect допустим только с доказанным expiry: matching daily receipt канонической записи и end receipt, содержащий соответствующий attack ID. Existing Champion bridge задаёт registration request ID `attack_id + ':daily-wound'`, а receipt ID — `attack_id + ':daily-wound:receipt'`; kernel задаёт wound request `…:wound` и lifecycle roll `…:wound-lifecycle`. Проверять точное равенство receipt ID, `receipt.source_request_id + '-lifecycle'` в consumed roll IDs, sequence/entry/total/rolls/origin и оба execution histories, не извлекать части произвольного ID. Отсутствие effect само по себе не считается expiry. Fixed-entry6 без actual bound expiry/history в первый scope не входит.
- Общий набор active effects должен в точности совпадать с доказанными canonical terrain и активными6; дубликаты/пропущенные/чужие effects отвергаются. При указанном факте отсутствия внешних causes Drained присутствует **тогда и только тогда**, когда есть хотя бы одна доказанная active6: нельзя допустить ни Condition без причины, ни активную причину без Condition. Staggered может быть обычным состоянием от атаки.
- Для active6 source round не future, completed/excluded sets не исчезают в пределах того же раунда, а при active Wizard deadline совпадает с текущим раундом. Полное совпадение IDs не позволяет подменить срок witness из другой хронологии.
- Existing `_validate_phase_source` и полные owner/round/receipt guards сохраняются. Контекст не разрешает обход pending Attack/Wound/Casting/Miscast, live exclusion или пропуск обязательной expiry.

Контекст признаёт canonical post-stand состояние, но не утверждает, что stand произошёл именно на текущем ходу. На следующих ходах free movement может быть вновь доступен; проверка его расхода принадлежит самому stand. Это structural validation snapshot, а не внешняя защита от намеренного восстановления старого snapshot.

### Сохранение доказательства истёкшего источника

Проверка actual expired6 показала, что одних daily/end IDs недостаточно: они не сохраняют исходный deadline. Поэтому `NpcWoundTurnEndReceipt` получает keyword-only `expired_sources: tuple[NpcStomachBlowExpiry, ...] = ()`. Новый context end сохраняет точный ordered expiry witness; receipt проверяет actor/attack IDs/deadline, root — current Wound/daily/consumed linkage. Context требует этот witness для каждого expired6 и сравнивает его receipt/record целиком. Старые ID-only receipts не становятся доказательством новой области: None-путь их сохраняет без изменения поведения, а новый context их отклоняет. Это узкое расширение существующего typed receipt, не общая шина событий/архив нового формата.

## Изменения существующих API

В `NpcRosterCastingRequest`, `NpcChampionAttackRequest` и `NpcWoundTurnEndRequest` добавить keyword-only optional `stationary_wounds: NpcStationaryWoundContext | None = None`. Preparation helpers получают одноимённый keyword-only параметр и передают его без изменений. Все прежние positional аргументы сохраняются.

`None` выполняет прежние guards без расширения admission. Ненулевой контекст требует полного `context.state == request.state` у root-bound Casting/end. У lower-level Champion attack требуется `context.state.champion_attack == request.state`, matching Wizard/target/current injury/round и полная phase validation контекста. Outer `NpcRosterChampionAttackRequest` дополнительно требует `context.state == outer.state`: нельзя заменить magic/spatial/expiry owner, сохранив тот же lower-level child.

Role binding обязательно: `context.actor_id` равен Casting caster, target incoming Champion attack или actor end-turn соответственно. Wizard context нельзя использовать как authority для Minion end. Другой actor завершает ход прежним None-путём, который сохраняет Wizard terrain/expiry и не удаляет чужой Drained.

Проверяется весь source и prepared Test/trace, не только ID или конечное отсутствие Prone. Result хранит исходный request с его контекстом; equality/reconstruction включает новый контекст. Domain не импортирует rules/engine, не вызывает reducers/RNG при validation. Локальные импорты/TYPE_CHECKING допустимы для уже существующего цикла типов root/child; runtime объектный граф конечен и хранит pre-action owner.

### Casting

Один existing Casting executor получает прежний полный source, расходует action и сохраняет injury/terrain/history. Успех, waiting, Curse и mandatory Miscast/movement pending сохраняют существующую семантику; последствия движения других Minion targets не дают Wizard права двигаться. Первый scope использует текущие normal Tests без бонусов, Glorious/Fate и сторонних modifiers. При Drained такие Tests уже удовлетворяют ограничению; расширение на бонусы потребует existing Drained pre-Test reducer в отдельном контракте, не молчаливого игнорирования Condition.

### Incoming Shooting / Protection

Только существующий ordinary Minion Shooting → Wizard/Champion. Полная source injury передаётся без очищения. Protection использует неизменённые authored base profiles и normal Tests без бонусов/Glorious/Fate; неподдержанные контекстные modifiers отклоняются. Drained разрешён только по доказанному источнику6.

Authored `can_target_leave_zone`/scene departures сохраняются как внешние факты. В kernel, где этот флаг определяет **Give Ground eligibility**, передаётся effective False из canonical Wound9. Это не утверждение, что обычное движение невозможно. `target_has_given_ground_this_round` берётся из полного spatial owner. После stand нет Prone Shooting−1d; если цель снова Prone, текущий stationary scope прекращается.

Атака исполняется один раз и полностью сохраняет новые Wounds, daily receipts, roll/execution IDs и старый terrain. Actual новая Wound6 добавляет существующий bound expiry с правильным deadline. Новая9 снова даёт Prone;10/13/иные effects или mandatory follow-ups сохраняются как реальные результаты и дают stop для следующей неподдержанной операции. Нельзя откатывать удачную атаку или отбрасывать новую рану ради admission следующего шага. Новый контракт не обещает замкнутость всех будущих Wounds.

ADR-0048 stand по-прежнему не принимает историю с6. Повторный stand после новой9 при таком history — отдельная граница, а не повод ослабить этот guard здесь.

### End-turn и независимые causes

Один existing scheduler end; затем projection удаляет только точные due expiry effects. Внешние источники в первом scope запрещены explicit фактом; `condition_sources` должны точно отражать другие **известные** неистекающие `WoundConditionEffect` данного Condition. Terrain не является источником Drained: проверять тип до обращения к `.condition`.

После expiry сохраняются terrain и все Wound records/rolls/origin/treatment flags, daily/history/receipts; обе child roster references синхронизируются. Несколько активных6, другой actor end, already-completed/next-round deadlines и replay проверяются отдельно. Снятие одного источника не снимает Condition при сохраняющемся другом источнике. No Test/RNG, treatment, healing или terrain crossing на end-turn не добавляются.

## Runtime policy и последующая интеграция

В этой вехе opt-in задаётся обязательным typed context каждого low-level запроса. Ни новый scenario field, ни `NpcMagicStep` variant/dispatcher, ни versioned JSON не вводятся. Это сохраняет текущую None/opted runner семантику и позволяет отдельно проверить полноценную ручную цепочку новых bound consumers.

После её аудита следующий контракт определит самостоятельную `stationary_wound_continuation` policy и source-derived journal/diagnosis/runner integration. `miscast_continuation` не переопределяется как Wound permission. Generation/wire propagation этой новой policy — отдельный этап с lossless rejection до появления нового формата; fresh-only transport не становится save/resume.

## Исходный finite proof / сохранённый None path

[Probe](../examples/m8/stationary_wound_contract_probe.py), [stdout](../examples/m8/stationary_wound_contract_probe.output.txt), [copied-bundle test](../../tests/integration/test_m8_stationary_wound_contract_probe.py). Три файла: probe, `leg_spasm_stand.py`, `magic_scenario.py`; только существующие public APIs.

1. Actual Wound9 → ADR-0048 stand: terrain сохранён, None runner останавливается на ACTOR_INJURY; existing bound Casting отвергается до RNG.
2. Отдельный K1 Casting тратит3d10 и выполняет action в primitive result. Он не выдаётся за новое full-owner продолжение.
3. Отдельный K1 lifecycle на этой injury действительно получает Wound6 с2d10, создавая terrain + timed Drained. Ни новый root attack witness, ни срок expiry не выдумываются.
4. Независимый actual Wound6 runner control выполняется с25d10: полный attack witness, deadline round2, реальное end-turn expiry и сохранение записи раны.

Всего37scripted d10, immutable sources/global RNG. Этот probe не доказывает mixed full-owner chain; теперь её проверяет отдельный [actual example](../examples/m8/stationary_wound_continuation.py). Исходный direct run прошёл; copied-bundle test на contract stage — **1 test OK,1,865с**, Windows/CPython3.12.4, вне sandbox. Команда: `$env:PYTHONPATH='src'; .venv/Scripts/python.exe -m unittest tests.integration.test_m8_stationary_wound_contract_probe -v`. После реализации сохранён None admission, финальный stdout уточнён, чтобы не заявлять отсутствие уже реализованного consumer. Независимое read-only review контракта/proof блокеров не выявило.

## План реализации и приёмки

1. Выполнено: frozen context/canonical source view, включая active/expired6, strict facts и phase/clock guards.23 deterministic tests проверяют source/effects/receipts и full expired witnesses.
2. Выполнено: explicit context в Casting/end API, полное source binding, typed Condition filtering и immutable projections.6 новых tests normal Drained, causes/expiry, no RNG/re-execution и old None behavior.
3. Выполнено: incoming Shooting/Protection + lower/outer bridge, effective GiveGround=False, normal Tests и новые Wounds/expiry без потери terrain.9 новых tests foreign root, source, repeated Staggered, new unsupported Wounds/pending.
4. Выполнено: public actual-bound manual chain9→stand→Casting/end→incoming6→следующий Casting/end/expiry и Protection с retained terrain, copied/installed/transport/full checks.3865tests/33known errors/0failures/0skipped, exact baseline headers совпали; итог — в [аудите](../audits/m8-stationary-leg-spasm-readiness.md).

Останавливаться для вопроса только при новой существенной неоднозначности книги либо необходимости изменить этот контракт. Следующий шаг — ADR-0050 и finite proof native stationary-wound policy/journal/diagnosis/runner integration. Эта low-level веха закрыта; generator/wire и другие gameplay boundaries отдельно.
