# M8: инвентаризация обязательных продолжений

Дата: 2026-10-28. Состояние после [аудита JSON/CLI ADR-0043](m8-external-readiness.md). Это выбор следующего consumer, не аудит готовой новой механики. При исходной инвентаризации production/Python tests сохранялись; последующий первый production срез ADR-0044 добавил только отдельные модели/pure consumer и tests. Матрица stop labels фиксирует исходные prerequisites; journal/runner интеграция ADR-0044 теперь закрывает только dead-awaiting case, остальные labels сохраняются.

## Что именно останавливает runner

Проверены закрытый [enum](../../src/towr/domain/npc_magic_step_models.py), [diagnosis/terminal/result chain](../../src/towr/domain/npc_magic_scenario_result_models.py), [journal policy](../../src/towr/domain/npc_magic_journal_policy.py), [runner](../../src/towr/engine/npc_magic_scenario_runner.py), ADR-0036/0037, bound owners и deterministic tests. Один код причины может объединять несколько prerequisites. Количество enum labels не является количеством оставшихся правил или оценкой полноты игры.

| Причина | Фактическая граница и prerequisite |
| --- | --- |
| `missing_scene` | Нет supplied frame полного live/spatial key, включая промежуточный Curse prefix или состояние после смерти. Требуются факты caller, не auto geometry. |
| `missing_route` | Нет допустимого Curse destination/availability либо ordinary Attack departure fact. Route не выводится из adjacency. |
| `no_legal_target` | Текущая explicit policy/range не даёт цели. Нельзя подставлять wait, другую тактику или считать исход победой. |
| `unsupported_broken_route` | Нет supplied Broken plan. Existing safe Recover/free move/Run готовы; неизвестный plan требует caller. |
| `unsupported_actor_injury` | Текущие Conditions/Wound restrictions действующего не допущены конкретным action adapter. |
| `unsupported_target_injury` | Выбранная policy цель имеет неподдержанный injury; runner не перескакивает к удобной следующей цели. |
| `pending_wound_effect` | Champion owner хранит полный незавершённый Attack. Label не доказывает исключительно Wound: diagnosis возвращает его для любого Champion pending, включая low-level ordinary Give Ground. |
| `attack_give_ground` | Minion pending содержит ordinary Give Ground. Текущий admitted runner требует `SUFFER_WOUND`, поэтому этот defensive branch сам по себе не доказывает reachability из fresh v1. |
| `miscast_preparation` | Сохранён Casting-triggered либо interruption-triggered pending; нет encounter consumer preparation → roll → actual application → pool cleanup. |
| `unsupported_end_turn` | Исполненное action ещё не позволяет закрыть ход из-за неподдержанного injury/Condition. |
| `unsupported_chronology` | Некорректный clock/live exclusion либо нет следующего live actor при незавершённом раунде. Dead awaiting Wizard после завершённой lethal Attack закрыт ADR-0044; прочие clock/exclusion gaps остаются отдельными. |

Diagnosis сначала проверяет pending Miscast/interruption, затем Champion pending, Minion pending и Curse movement. Только после них — scheduling/action/end-turn. Mandatory prefix нельзя замаскировать terminal outcome. Непойманное исключение исполнения не превращается в один из этих stop-кодов.

## Карта существующих reducers и недостающих owners

| Кандидат | Что готово | Что ещё требуется / почему не выбран первым |
| --- | --- | --- |
| Dead awaiting Champion после lethal Attack | Bound Champion Attack полностью завершает Wound, daily/roll registration и `dead`; pending пуст. Следующий round advance уже фильтрует dead. | Исключение текущего раунда и journal/runner integration реализованы; [propagation/итоговый аудит](m8-dead-champion-readiness.md) завершены. Контракт [ADR-0044](../decisions/ADR-0044-dead-champion-turn-exclusion.md). |
| Superficial Wounds 1–3, Stomach blow 6 | Первые закрыты lifecycle без ongoing effect; для 6 готов full-source end-turn/expiry Drained. | Повторять существующую реализацию не нужно. |
| Wounds 4/5/7/11 | K1 описывает Endurance follow-ups. | В текущих authored actor policies нет Endurance profile. Для 11 Endurance предотвращает потерю 1d10 зубов; нельзя свести строку только к Deafened. Нужны профиль/consumer и downstream Conditions. |
| Wounds 8/12/16/18–23 | Typed K1 requests/effects и части consumers существуют. | Hand/item/limb/random choice, lasting restrictions или дополнительные Tests; Shooting profile не доказывает полный held inventory. Нельзя считать руку пустой или подбирать новый профиль автоматически. |
| Wounds 9/10/13–15/17 | K1 Conditions/restrictions существуют. | Prone, Difficult Terrain, next-Test Grim, action restrictions/Critical и длительные источники требуют bound применения и дальнейшего action/end-turn admission, а не одного снятия pending. |
| Ordinary Attack Give Ground | K1 movement и M2 execution/consumption wrappers готовы; низкоуровневый Attack может породить этот follow-up при иной policy. | M2 round wrapper Minion-only. M8 Curse plans anchored Wizard, не arbitrary attacker. Нужны отдельный full-owner bridge, live spatial projection с восстановлением архива, route policy и контракт wire/admission при расширении runner policy. |
| Miscast preparation и table roll | K1 сохраняет source, умеет explicit desperate cast/decline, preparation и один roll. | Нужны bound prepared/rolled prefix receipts, policy и сохранение неподдержанной строки без reroll/cleanup. Table lookup не завершает эффект. |
| Miscast Sense of Loss 1–2 / Nauseating Wave 3–4 | K1 возвращает application request и проектируемый cleared pool. | Требуется подтверждённое actual narrative application, полный owner и unresolved self-inclusion. «Нет числового эффекта» не разрешает silent noop и очистку pool. |
| Miscast Unnatural Wind 21–22 | Текст явно включает caster; K1 действительно применяет Prone к допустимым targets. | Перспективный позднейший consumer, но сначала нужен общий узкий bound preparation/one-roll prefix и downstream Prone policy/admission. Не закрывает остальные строки. |
| Остальные Miscasts | Различные K1 typed boundaries. | Inventory/campaign/lore/target/GM decisions, Wounds, Hazard, новые actors или death; не один готовый encounter reducer. |

Обычное Minion defeat acknowledgement уже поддержано; его GM disposition не применяется к Champion. Existing Minion exclusion wrapper нельзя расширить неявным удалением Champion из source roster. При Give Ground полный spatial archive содержит dead placements: прямой K1 вызов может ошибочно считать их живыми врагами и назначить Broken. Live projection и exact archive merge обязательны в отдельном будущем контракте.

## Прямая сверка книг

Прочитаны локальные постраничные тексты, не changelog:

- BOOK-PLAYER-GUIDE 1.4, гл. V Rules / Combat, стр. 112; Wounds & Conditions, стр. 121; Wounds Table, стр. 190–191. Строки 1–3 не имеют дополнительных эффектов; 6 задаёт Drained до конца следующего хода; 4/5/7/11 требуют Endurance; 24–27+ смертельны. Optional Close trophy не входит в текущий ranged scope; dying words строки 26 не дают нового action.
- Та же книга, гл. VIII Magic in the Old World / Casting a Spell / Interrupted Casting, стр. 156; Spell Potency / Miscasts, стр. 157; Disposing of Miscast Dice, стр. 158; Miscast Table, стр. 159. При triggered Miscast теряются successes, доступный desperate spell требует явного решения и дополнительного die. Pool обнуляется после разрешения эффекта. Для 21–22 caster явно включён; для 1–2/3–4 остаётся существующий [открытый вопрос](../open-questions.md).
- BOOK-GM-GUIDE 1.1, гл. VII Allies and Antagonists / Minions и Champions, стр. 91–92. Champion использует Wounds Table, а не Minion defeat/disposition.

Открытые ambiguities не закрывались предположениями. Новых house rules/противоречий не выявлено. Это не построчная полная оценка каталога всех игровых правил.

## Выбранный законченный consumer

[ADR-0044](../decisions/ADR-0044-dead-champion-turn-exclusion.md) ограничен завершённой lethal Minion → Wizard Attack, непосредственно следующим полным root и awaiting целью. Добавляется только exclusion текущего раунда с синхронизацией Champion owner. Полный Attack witness обязателен; journal дополнительно сверяет его с непосредственно предыдущим шагом. Completed цель пропускается dispatcher и отклоняется consumer.

[Finite probe](../examples/m8/dead_champion_contract_probe.py) строит свежий допустимый сценарий с тремя числовыми лучниками, союзным Minion и Wizard. Три Attack последовательно дают Wounds1/2/25 без промежуточного mandatory effect. До ADR-0044 awaiting Wizard оставлял chronology gap; теперь production runner публикует full-source exclusion, завершает ход атакующего и ход выжившего союзника, достигая round limit. Completed Wizard не получает новой фазы. Контроль без post-death frame сохраняет exact missing-scene stop уже после exclusion/end-turn и все архивные записи. [Сохранённый вывод](../examples/m8/dead_champion_contract_probe.output.txt) и [subprocess test](../../tests/integration/test_m8_dead_champion_contract_probe.py) проверяют текущую реализацию из external cwd; прежняя ручная проекция заменена actual journal evidence.

Модели/pure consumer и journal/runner реализованы двумя отдельными срезами; [propagation/итоговый аудит](m8-dead-champion-readiness.md) завершены. Следующий отдельный контракт рассматривает Miscast Unnatural Wind21–22 и его недостающие prerequisites. Full-witness predecessor guard двусторонний: нельзя подменить Attack даже при равном post-state, пропустить exclusion или завершить журнал до него. Список остальных кандидатов не меняет порядок roadmap и не разрешает их реализацию без собственных контрактов.
