# ADR-0081: Drained от попадания и независимые источники Conditions

Дата: 2026-11-05. Статус: принято. Пользователь выбрал контракт и два существа, сохранив нынешнюю Attack/standard Recover стратегию.

## Задача и источники

Текущий PC owner поддерживает Conditions от Wounds, но отвергает secondary attack effects. Giant Spider по GM1.1, Allies and Antagonists137 накладывает Drained при попадании. Это отдельная причина Condition, которую нельзя терять при завершении временного Wound effect или отмене раны через Near Miss.

Источники: GM1.1 Profiles93 / White Wolf136 / Giant Spider137; PG1.4 Near Miss112 / Recover118 / Conditions122–123. Existing K1 ConditionOnHitSpec и resolve_kernel_attack уже дают типизированную condition application; нужен законченный PC consumer, а не новый универсальный язык правил.

## Граница M29

Согласованы один общий контракт Drained и два совместимых профиля. Здесь новая механика и source lifetime важнее квоты3–5; дублирующие loadouts для количества не добавляются.

| Profile | Selected attack / Protection | Injury и другие эффекты |
|---|---|---|
| Giant Spider | Poisonous Fangs3d/3 Damage3,natural / Athletics4d/3 | Fast Minion,T3Res3; on-hit Drained |
| White Wolf | Clamping Jaws3d/4 Damage5,natural / Athletics4d/4 | Fast Brute2,T5Res5; W1Drained/W2defeat; цель не может Give Ground |

Оба самостоятельные unmounted бойцы уже в Close Range. Spider terrain/rider abilities inactive. White Wolf Rending Claws явно unselected; Pin and Tear требует Charge, которого текущий owner не делает. Fearsome требует Give Ground от атаки White Wolf, невозможного при выбранной Clamping Jaws с запретом. Полные условия остаются в metadata. NPC Recover/profile-Wound ongoing-cause вопросы не включаются.

## Source/wire контракт

В текущем PC JSON1 введено обязательное attack.secondary_effects: список из0–1типизированного condition_on_hit/drained descriptor с полными rule_id/classification. Поддержан только ConditionOnHitSpec(Drained, classification=UNCLASSIFIED); других эффектов/Conditions/psychological classification этот срез не обещает. В существующем EffectClassification нет physical, новый enum не выдумывается.

Старые input/echo/candidate sources получают явный пустой список; текущие код/схемы/примеры/тесты мигрируются вместе без version bump и compatibility ветвей. None hands M27 сохраняет свой смысл. Полный descriptor входит в numeric definition, source guards и canonical replay, а не восстанавливается скрыто по имени Spider.

## Порядок применения

1. Attack и Protection Tests завершаются с их реальными исходными Conditions/Fate. Новый Drained не пересчитывает уже брошенные кубы или потраченный Fate.
2. Обычный Damage/Stagger/Wound branch разрешается существующим kernel. Попадание вызывает Drained независимо от того, привело ли оно к ране.
3. Exact on-hit condition application и её правило/target/actual attack сохраняются в PC projection. Miss не создаёт источник. Повторный hit по уже Drained цели всё равно сохраняет новую причинную application, в том числе при was_already_present=true.
4. Near Miss отменяет только рану. On-hit Drained сохраняется; последующие Wound Endurance Tests и действия PC видят новое состояние. Снятие старого Staggered от раны и Fate rollback продолжают обычную жизнь.

## Независимые источники

Введён отдельный типизированный runtime источник Condition в PC participant state, связанный с actual Attack execution/target/rule и подтверждённой application. Нельзя записывать hit effect как фиктивную WoundConditionEffect или придумывать wound_sequence/deadline.

При независимой W6 Drained expiry состояние остаётся, пока есть источник hit Drained. Источники сохраняются и при попадании по уже Drained цели; Condition flag при этом один, штраф не складывается и ложная рана не возникает. Все mutation/expiry/Fate paths должны сохранять этот инвариант; malformed/cached source нельзя молча чинить перед observation. Полный replay подтверждает once-only применение, принадлежность и отсутствие подмены causal receipt.

## Выбранная стратегия Recover

PG123 разрешает Endurance для кратковременного Drained. Название Poisonous Fangs само по себе не создаёт disease/ongoing poison или срок действия. PG118 требует **альтернативный** Recover вместо стандартных преимуществ, а не бесплатный Test во время обычного Recover.

Пользователь выбрал сохранить нынешнюю Attack/standard Recover стратегию и отказаться от нового альтернативного Endurance решения в этом срезе. Это не запрет книжного восстановления. Отдельная будущая recovery policy должна определить приоритет стандартного/альтернативного Recover и запрет удаления независимого ongoing Wound cause. Сейчас hit источники сохраняются в рамках боя; post-battle автоматический Recover не исполняется.

## План проверки

- Hit со Staggered impact и с Wound, miss, duplicate/replayed/foreign receipts.
- Near Miss и сохранение hit Drained при отменённой ране; без ретроактивного изменения Attack/Protection Tests.
- W6expiry отдельно и перекрывающиеся Drained sources, в том числе was_already_present=true; сохранение штрафа на последующих Tests, разрешённый explicit Fate Glorious.
- Standard Recover не удаляет Drained; альтернативный Endurance consumer проверяется только при выбранной стратегии.
- White Wolf W1 Drained/обычный own turn/bonus-dice suppression/W2defeat и actual Give Ground ban.
- Полный JSON/source/candidate echo, строгий поддержанный набор effect descriptors, aggregate-only подбор и один sequential/process сценарий с фактическим hit effect.

Фактические команды/результаты и ограничения — в [статусе](../project-status.md), текущие payloads — в [примерах M29](../examples/m29/README.md). Старые payloads мигрированы явными пустыми secondary_effects без изменения прежних игровых параметров и наблюдений.
