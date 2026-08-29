# ADR-0005: исторические Wounds и source-aware healing lifecycle

Статус: принято 2026-08-22, дополнено 2026-08-30.

## Контекст

Player’s Guide 1.4 на странице 121 различает treatment и healing. Treatment прекращает `+1d` за Wound и её effects «until treated». Полное healing происходит после указанного времени, прекращает все непостоянные effects, но может оставить постоянные изменения. Wounds Table на страницах 190–191 назначает каждой строке одну из категорий healing; результаты `1–7` используют `Catch Your Breath` и автоматически перестают быть проблемой после непосредственной опасности.

До этого K1 хранил только `WoundRecord.treated`. Удаление записи при healing нарушило бы provenance её effects и повторно использовало бы sequence, а смешивание healing с treatment не позволило бы независимо проверять временной источник и повторное применение.

## Решение

- Добавить к исторической записи `WoundRecord.healed`; healed-запись обязана быть treated и иметь уже разрешённый первичный Wound effect.
- Не удалять и не перенумеровывать healed Wounds. `CharacterInjuryState.active_wounds` считает только не healed записи, а следующий Wound продолжает монотонную последовательность.
- Запретить непостоянный active effect, ссылающийся на healed Wound. Постоянные последствия, включая утраченные части тела, остаются допустимыми.
- Оставить treatment и healing разными неизменяемыми переходами. `EndEncounterHealingOpportunity` подтверждает завершение encounter, окончание непосредственной опасности, target и точный injury snapshot. Он может включать совпадающий `EndBattleWoundTreatmentResult`, но не требует нового treatment-result, если выбранные Wounds уже treated; каждая фактически исцеляемая Wound всё равно обязана быть treated и иметь resolved effect.
- Перед применением заново сверять `entry_id` и `table_total` каждой записи с нормативной Wounds Table и требовать полный ordered набор всех и только treated/resolved, ещё не healed Wounds категории `CATCH_YOUR_BREATH`. Не готовая запись не исцеляется и не блокирует другие ready Wounds.
- При healing удалять все непостоянные effects выбранной Wound, независимо от прежнего duration, и сохранять `PERMANENT`, effects других Wounds и несвязанные Conditions.
- Для общей Condition требовать точный `WoundConditionSourceSnapshot`; известный remaining wound-effect source нельзя отрицать, внешний источник можно явно подтвердить.
- Погашать opportunity ID один раз во внешней ordered chain и не создавать action slot, receipt, Test или RNG: это lifecycle application boundary.
- Представить `A Night’s Respite` отдельным `NightsRespiteHealingOpportunity` с точным target/injury snapshot и тремя книжными фактами: персонаж провёл период спокойно, завершил ранний ночной отдых, и наступило утро. Не задавать число часов.
- Для `NIGHTS_REST` (`8–15`) переиспользовать тот же full-ready-set resolver, общий переход effects/Conditions и ordered consumed-source chain. Обычная ночь не создаёт Endurance Test; optional досрочная проверка остаётся отдельной будущей policy boundary.
- Представить `Rest and Recovery` двумя фазами: `RestAndRecoveryEndeavourRequest → Result` исполняет Endurance Test в точном downtime/target/injury context, затем application request выбирает одну, и только одну, ready Wound категории `REST_AND_RECOVERY` (`16–19`). Успешный Endeavour ID погашается один раз.
- На успешной Test возвращать отдельный `FesteringWoundsRecoveryRequest` для всех Festering Wounds. Пока Infection/campaign state отсутствует, не имитировать их удаление внутри `CharacterInjuryState`.
- Не пропускать `SURGERY_AND_RECOVERY` (`20–23`) через обычный Rest and Recovery consumer без успешного `DowntimeSurgeryResult` для той же Wound/target/state/downtime. Surgery proof не мутирует injury state, добавляется в trace и погашается перед Endeavour ID; строки `16–19` лишний proof отвергают.
- Ordinary surgery требует Anatomy Lore у surgeon, theatre, specialist medical tools, time, recovery supports и Basic Dexterity Test. Не выводить из наличия NPC автоматический успех или цену услуги.
- Провал не выбирает permanent disfigurement/death: вернуть GM-owned `SurgeryFailureRiskRequest` с обоими книжными рисками и оставить state неизменным до внешнего ruling (`AMBIGUITY-009`). Combat Surgeon с Exacting Dexterity `8` является будущим отдельным action adapter.

## Последствия

Injury history остаётся проверяемой и пригодной для воспроизведения, а treatment нельзя спутать с полным healing. Реализованы `Catch Your Breath`, `A Night’s Respite`, успешная `Rest and Recovery` и ordinary downtime surgery для строк `20–23`. Применение Festering/surgery-failure follow-ups, Combat Surgeon и optional early Endurance Test остаются отдельными будущими границами.
