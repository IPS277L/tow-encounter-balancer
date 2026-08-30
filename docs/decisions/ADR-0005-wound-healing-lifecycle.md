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
- Провал не выбирает permanent disfigurement/death: вернуть GM-owned `SurgeryFailureRiskRequest` с обоими книжными рисками и оставить state неизменным до внешнего ruling (`AMBIGUITY-009`).
- Разделить две ветви Combat Surgeon. После успешного Recover treatment отдельный triggered request выполняет дополнительную Recall Test и при успехе создаёт suppression всех `UNTIL_HEALED` effects этой Wound для одного `battle_id`. Не удалять effects/Conditions и не помечать Wound healed: suppression принадлежит будущему battle aggregate. Погашать treatment-result ID после первой попытки независимо от исхода Test.
- Battle surgery исполнять отдельным Ability-Improvise action adapter поверх общего immutable Exacting Basic-contribution progress. Каждая Dexterity Test создаёт один receipt и ordered contribution; цель равна 8, progress не уменьшается. Нулевой вклад создаёт GM-owned failure-risk request по той же политике, что ordinary surgery. Completed progress возвращает proof, но не healing transition.
- Talent отменяет operating theatre; action заменяет общий time-to-work gate. До решения `AMBIGUITY-010` сохранять отдельно перечисленные specialist tools и recovery supports.
- Completed battle proof подключать к Rest and Recovery только для той же цели и стабильной identity Wound (`sequence`, `entry_id`, `table_total`, `roll_values`, `origin`). Не требовать полного равенства давнего battle snapshot актуальному downtime state, но требовать точную привязку текущего state к Endeavour, treated/resolved/unhealed lifecycle и одноразовое погашение proof перед Endeavour. Ordinary surgery сохраняет exact state/downtime provenance.

## Последствия

Injury history остаётся проверяемой и пригодной для воспроизведения, а treatment нельзя спутать с полным healing, временным suppression или завершённой surgery. Реализованы `Catch Your Breath`, `A Night’s Respite`, успешная `Rest and Recovery`, ordinary downtime surgery и Combat Surgeon battle proof для строк `20–23`, а также обе непосредственные ветви Combat Surgeon. Применение Festering/surgery-failure follow-ups, aggregate-consumption suppression и optional early Endurance Test остаются отдельными будущими границами.
