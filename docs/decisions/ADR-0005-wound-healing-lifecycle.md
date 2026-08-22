# ADR-0005: исторические Wounds и source-aware healing lifecycle

Статус: принято, 2026-08-22.

## Контекст

Player’s Guide 1.4 на странице 121 различает treatment и healing. Treatment прекращает `+1d` за Wound и её effects «until treated». Полное healing происходит после указанного времени, прекращает все непостоянные effects, но может оставить постоянные изменения. Wounds Table на страницах 190–191 назначает каждой строке одну из категорий healing; результаты `1–7` используют `Catch Your Breath` и автоматически перестают быть проблемой после непосредственной опасности.

До этого K1 хранил только `WoundRecord.treated`. Удаление записи при healing нарушило бы provenance её effects и повторно использовало бы sequence, а смешивание healing с treatment не позволило бы независимо проверять временной источник и повторное применение.

## Решение

- Добавить к исторической записи `WoundRecord.healed`; healed-запись обязана быть treated и иметь уже разрешённый первичный Wound effect.
- Не удалять и не перенумеровывать healed Wounds. `CharacterInjuryState.active_wounds` считает только не healed записи, а следующий Wound продолжает монотонную последовательность.
- Запретить непостоянный active effect, ссылающийся на healed Wound. Постоянные последствия, включая утраченные части тела, остаются допустимыми.
- Оставить treatment и healing разными неизменяемыми переходами. Первый `Catch Your Breath` reducer принимает точный завершённый `EndBattleWoundTreatmentResult` и его post-treatment injury snapshot; source result ID погашается один раз во внешней ordered chain.
- Перед применением заново сверять `entry_id` и `table_total` каждой записи с нормативной Wounds Table и требовать полный ordered набор всех и только ещё не healed Wounds категории `CATCH_YOUR_BREATH`.
- При healing удалять все непостоянные effects выбранной Wound, независимо от прежнего duration, и сохранять `PERMANENT`, effects других Wounds и несвязанные Conditions.
- Для общей Condition требовать точный `WoundConditionSourceSnapshot`; известный remaining wound-effect source нельзя отрицать, внешний источник можно явно подтвердить.
- Не создавать action slot, receipt, Test или RNG: это lifecycle application boundary.

## Последствия

Injury history остаётся проверяемой и пригодной для воспроизведения, а treatment нельзя спутать с полным healing. Первый consumer закрывает только `Catch Your Breath`. `A Night’s Respite`, `Rest and Recovery`, surgery, optional early Endurance Test и общий end-encounter source для случая без нового treatment result остаются отдельными будущими границами.
