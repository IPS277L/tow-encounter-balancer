# ADR-0050: native policy для stationary Wound continuation

Дата: 2026-11-01. Статус: **пункты1–4 завершены, ADR закрыт в native границе**. Prerequisites: [ADR-0048](ADR-0048-source-bound-leg-spasm-stand.md), [ADR-0049](ADR-0049-stationary-leg-spasm-continuation.md) и [low-level audit](../audits/m8-stationary-leg-spasm-readiness.md). Итоговая evidence — в [аудите](../audits/m8-native-stationary-wound-readiness.md).

## Источники и граница

Непосредственно перечитаны BOOK-PLAYER-GUIDE1.4, гл.V Rules / Difficult Terrain115, Free Actions116, Giving Ground119, Conditions122/Drained и Prone123; гл.VIII Casting156/Miscasts157/Miscast Table159; приложение Wounds Table190. BOOK-GM-GUIDE1.1, гл.VII Champions92. Источники подтверждают stand вместо free movement, сохранение terrain9 до treatment, запрет Give Ground и срок Drained6 до конца следующего собственного хода. Wind21–22 сам по себе не открывает Wound consumers; книжные правила и существующие Rule IDs не меняются. Автоматический выбор — техническая policy эксперимента, не house rule.

Добавить append-last nullable `stationary_wound_continuation: NpcMagicStationaryWoundPolicy | None = None` к `NpcMagicScenario`. Enum имеет единственное значение `LEG_SPASM_STAND_AND_CONTINUE = 'leg_spasm_stand_and_continue'`. При None остаются прежние traces/stops/RNG; bool/string вместо enum отвергаются. `miscast_continuation` независим: проверить четыре сочетания двух nullable policies.

## Единая eligibility и dispatch

Новый чистый domain helper `npc_magic_stationary_wound_policy.py` использует canonical validators ADR-0048/0049, без reducers/RNG. Узкие non-throwing scope predicates преобразуют только ожидаемый отказ pure source validation в False; constructors/executors не перехватываются diagnosis. Не дублировать Wounds Table или стирать effects.

1. Stand family: живой active Wizard с одним неисполненным STANDARD slot, Prone/optional Staggered, только resolved untreated/unhealed superficial1–3/9, полная canonical Prone+terrain пара для каждой9. Unused free move и полный текущий supplied frame без enemy Close требуются для исполнения. Новый stand имеет приоритет над старым standalone Prone path и обязателен до action/target selection.
2. Post-stand family: ровно canonical context49 — retained terrain9, active/expired6 и существующие scoped Conditions, строгое no-external-causes assertion из scenario facts. Context передаётся в Wizard Casting/end и incoming Shooting/Protection; у другого Minion end остаётся None.
3. Новый result в закрытом journal union — только `NpcRosterLegSpasmStandResult`. Stand не расходует action и не увеличивает action counters. Context-bearing старые типы тоже требуют новой policy: совпадение типа result не является разрешением обойти opt-in.
4. Exact source/actor/scene/clock validation одинакова для runner publication и reconstructed journal. Existing pending Miscast, movement, Attack follow-ups, lethal Attack→dead exclusion и terminal order остаются приоритетными. Нельзя публиковать stand/action вместо mandatory continuation.
5. Shooting сохраняет authored departure fact и требует его присутствия; kernel Give Ground=False выводится из canonical terrain. После stand нет Prone−1d. Новые Wounds и unknown mandatory follow-ups сохраняются в полном owner, затем возвращается конкретный unsupported stop.

Для selected Leg Spasm family нельзя откатиться к более слабому legacy admission при отсутствии canonical terrain/context. Повреждённый transported StandResult повторно проверяется pure constructor validation, без исполнения reducer. Источник с raw string вместо enum отвергается в journal/diagnosis и worker normalization до source equality; strEnum equality не является проверкой типа.

Family recognition допускается до старого actor-injury guard, чтобы valid9 достигла scene/stand eligibility. Missing frame остаётся MISSING_SCENE; unsafe/spent-move stand не превращается в Casting с Prone Wound. Stationary context не открывает Broken, movement, Recover/treatment, modifiers/Glorious/Fate или другие wounds.

Повторная9 после уже выполненного stand не поддержана **даже без6**: прежняя9 уже не имеет Prone effect, а ADR-0048 требует полную пару каждой9. Повторная9 при history6 и Wind21, вновь давший Prone при retained terrain, также дают честный stop. Не ослаблять stand48 или context49, чтобы скрыть эту границу.

## Native propagation и неподдержанный transport

Trial/sequential/process/assessment используют полный Scenario с новой policy, прежние seeds и aggregate denominator. None не меняет legacy результаты. Explicit native candidate lists допустимы через существующие typed APIs.

Generation пока вручную реконструирует Scenario: `MagicCompositionGenerationRequest` рано отклоняет template с ненулевой stationary policy до materialization/RNG. Полная family assertion/projection — отдельный следующий контракт.

JSON v1/v2/schema/CLI не получают новое поле. Public `scenario_document` явно отвергает stationary policy вместо молчаливого пропуска, result/error lossless checks сохраняются. Fresh-only wire не становится save/resume. Generator/wire propagation, новый versioned формат и console-путь разрешения новой policy входят в последующую веху.

## План и приёмка

1. Выполнено: policy model/shared eligibility, strict typing/None, early generation/wire rejection;12новыхpolicy tests.
2. Выполнено: journal/source gating/diagnosis/runner, mandatory stand и exact unsupported boundaries;20новыхunit tests.
3. Выполнено: [public automatic flow](../examples/m8/stationary_wound_runner.py)/[stdout](../examples/m8/stationary_wound_runner.output.txt),3native integration tests, copied test. Four policy combinations и source/installed sequential/spawn pair проверены,220scripted d10; negative Miscast controls используют настоящие9.
4. Выполнено: copied/installed459file parity, native spawn, legacy transport95commands, saved v2 outputs прежние. Full regression3901tests/33known errors/0failures/0skipped; exact ERROR headers совпали с baseline, новых ошибок нет. Итог — в [аудите](../audits/m8-native-stationary-wound-readiness.md).

Следующий шаг — ADR-0051: explicit generation family propagation и отдельный versioned wire/CLI контракт новой policy. Не удалять native policy для обхода lossless rejection, не вводить save/resume и дополнительные игровые consumers под видом transport.

Commit/push выполняет пользователь. Полный suite с существующими33errors не объявлять зелёным; metadata ошибок и historical checks — в предыдущих аудитах.
