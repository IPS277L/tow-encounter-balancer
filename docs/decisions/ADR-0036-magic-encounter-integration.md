# ADR-0036: состояние и обязательные продолжения первого боя с магом

Статус: принято как ограниченный технический контракт, 2026-09-29. Реализация encounter ещё отсутствует. Направление «магия в боевой симуляции» уже выбрано пользователем. [ADR-0035](ADR-0035-cowardly-flight-casting-boundary.md) закрывает только одно Casting-действие; этот ADR определяет зависимости до первого runner.

## Проверенные источники

Непосредственно прочитан локальный извлечённый текст выбранных редакций:

| Источник | Следствие для интеграции |
| --- | --- |
| BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91; Champions, стр. 92 | Minion выбывает от одной Wound; Champion использует Wounds Table как персонаж. Единый счётчик Minion wounds для мага недопустим. |
| Та же книга, Allies and Antagonists / Hermit Witch, стр. 130 | Книжный пример — Champion, Level 2, со своим списком spells и opposition. Curse of Cowardly Flight в этом списке нет. Авторский Wizard со свободно заданными профилями не называется Hermit Witch. |
| BOOK-PLAYER-GUIDE 1.4, Rules / Combat Actions / Recover, стр. 118 | Удаление Condition заменяет стандартные преимущества Recover; нельзя одновременно бесплатно уменьшить Miscast Pool. |
| Та же книга, Rules / Attack Tests / Giving Ground, стр. 119 | Уход зависит от текущей позиции, препятствий, Conditions и истории раунда. При изменении позиции старые факты нельзя считать актуальными. |
| Та же книга, Rules / Wounds & Conditions, стр. 121; Wounds Table, стр. 190 | Wound требует броска с учётом untreated Wounds и обработки конкретных последствий. Staggered снимается при Wound; не всякая Wound означает defeat. |
| Та же книга, Rules / Conditions / Broken, стр. 122 | Broken тратит ход на максимально быстрый уход в Zone без врагов, включая Manoeuvres при необходимости; Recover возможен после достижения такой Zone. Broken не означает defeat. |
| Та же книга, Magic in the Old World / Casting a Spell / Interrupted Casting, стр. 156; Spell Potency / Miscasts and the Rule of Nine, стр. 157 | Casting переносит successes, Potency берётся из последнего roll; пропуск Casting и отказ от него имеют последствия. Miscast обязателен при pool > Level; допустимый desperate cast — отдельный выбор. Pool очищается после эффекта. |
| Та же книга, Magic in the Old World / Miscast Table, стр. 159 | Разные строки требуют пространственных, injury, inventory или GM consumers. Сам lookup таблицы не завершает эффект. |

Curse сохраняет правило BOOK-PLAYER-GUIDE 1.4, Battle Magic / Curse of Cowardly Flight, стр. 162, проверенное в ADR-0035: все враги в выбранной Zone сначала Give Ground, если могут, затем проходят Willpower против Potency, иначе Broken. Новых Rule IDs и house rules нет.

## Инвентаризация реализации

| Готовый код и проверка | Граница готовности / требуемая связь |
| --- | --- |
| [NpcRoster](../../src/towr/domain/npc_roster_models.py), [tests](../../tests/unit/test_m2_npc_roster.py), [ADR-0008](ADR-0008-npc-roster-boundary.md) | Хранит Champion с CharacterInjuryState и Minion с ProfileInjuryState; сам не владеет WizardMagicState, Casting receipts или автоматическим удалением погибших. |
| [Roster attack](../../src/towr/rules/npc_roster_attack_execution.py), [models](../../src/towr/domain/npc_roster_attack_models.py), [tests](../../tests/unit/test_m2_npc_roster_attack_execution.py) | Готовы source/replay guards для Minion → Minion. Champion как target этим API не поддерживается. |
| [Wound lifecycle](../../src/towr/rules/wound_lifecycle_resolution.py), [tests](../../tests/unit/test_k1_wound_lifecycle_resolution.py), [kernel cycle](../../tests/integration/test_k1_npc_attack_kernel_cycle.py) | K1 имеет отдельные Character/Champion injury и pending Wound phases. Нужна привязка к текущему roster, применение последствий и блокировка следующего действия до completion. |
| [Casting executor](../../src/towr/engine/cowardly_flight_casting.py), [integration tests](../../tests/integration/test_m8_cowardly_flight_casting.py) | Один action receipt и exact magic/target snapshots. Нет actor-bound владельца состояния и потребителя результата в NpcRoster. |
| [Free movement](../../src/towr/rules/free_movement_resolution.py), [Recover](../../src/towr/rules/recover_resolution.py), [tests](../../tests/unit/test_k1_recover_resolution.py) | Есть отдельные запросы/результаты; Recover запрещён Broken в Zone с врагом. Нет политики обязательного Broken turn, выбора быстрейшего пути и общего переноса результатов в roster/позиции. |
| [Miscast preparation/roll](../../src/towr/rules/miscast_resolution.py), [effect reducers](../../src/towr/rules/miscast_effect_resolution.py), [tests](../../tests/unit/test_k1_miscast_effect_resolution.py) | Отдельные reducers не образуют полного encounter consumer. Например, nausea возвращает application request; wounds, transport, objects, recent spells и rifts требуют своего контекста/применения. |

177 существующих tests из 13 модулей этой таблицы и M8 выполнены успешно. Это проверка существующих компонентов, не тест реализованного encounter.

## Первый планируемый состав и тактика

Один явно описанный Champion-Wizard на одной стороне, хотя бы один союзный Minion и хотя бы один вражеский Minion. Число, actor IDs, стороны, профили, порядок активаций и приоритет целей задаёт caller. Wizard — авторский профиль с source provenance, Wizard Level 1–4, Battle Magic и memorised Curse. Его NpcDefinition и CastingCasterDefinition остаются разными описаниями, связанными явным actor ID. Wizard может быть целью вражеской атаки на тех же основаниях, что остальные участники; фиктивной неуязвимости нет.

У Minions первоначально только обычные числовые Shooting profiles без reload, Aim и hidden preparation. У мага одна offensive policy CAST_WHEN_READY из ADR-0035, без weapon Attack; нет opposition, Mixing, Magic Resistance, armour/bulky casting modifiers, иных spells или способностей книжного NPC. Это область поддержки конкретного сценария, не изменение книжных профилей. Исходные injury/Conditions отсутствуют; полученные в бою состояния должны сохраняться и влиять на допуск следующих действий.

Сценарий явно задаёт graph, placements, pair facts и target priorities. При изменении состава или позиции facts перепроверяются; незаданные новые отношения не выводятся из названий Zones. Нет автоматической осведомлённости или универсального поиска тактики. Любая цель Curse, способная Give Ground, требует completion соответствующего ухода: ограничение ADR-0035 нельзя превращать в постоянный запрет движения для боя.

## Владелец состояния и порядок исполнения

Неизменяемые определения отделены от текущего состояния. Узкая M8 orchestration хранит NpcRoster, actor-bound WizardMagicState, RoundState, SpatialState, историю потреблённых execution IDs и одно текущее обязательное продолжение. Это состояние только данного сценария, без общего battle aggregate или шины событий.

1. Проверить полное текущее состояние и pending continuation до выбора actor/action. Pending не исчезает при смене раунда или достижении лимита.
2. Из актуального roster построить snapshots выбранного действия. История завершённых/исключённых ходов не служит фильтром живых участников.
3. Исполнить ровно один соответствующий узел с внедрённым RNG: Casting, Attack, Recover или обязательное движение. Не преобразовывать spell в weapon Attack.
4. Применить результат к тому же source snapshot ровно один раз: magic, injury, Conditions, позиции, action receipt и continuation переносятся согласованно. Не делать повторный бросок при применении.
5. Закрыть обязательные последствия, затем завершать ход/менять раунд и проверять objective/round limit.

Планируемый dispatch: обязательное continuation → Broken turn → действие выбранной тактики. Defenceless/ограничения injury проверяются до действия. Если Wizard из-за другого действия пропустил Casting или отказался от накопленного cast, применяются существующие interruption/abandonment правила; successes/pool не обнуляются произвольно.

## Остановка и обязательные продолжения

Неверный исходный запрос отклоняется до RNG. Законный, но ещё не поддержанный путь после исполнения возвращает отдельный `unsupported_path`: phase/reason, actor/source IDs, последний согласованный snapshot и полный pending payload/уже полученные traces. Это не победа, defeat, round_limit или повод повторить бросок. Исключение/ошибка реализации не маскируется этим статусом.

- **Champion Wound:** сохранять точный Wound request/roll/completion и все нерешённые последствия. Пока невозможно применить требуемые Tests, dropped items, Conditions или ограничения профиля, обычный бой не продолжается. Смерть учитывается только после нужных completion; Minion one-Wound policy сюда не переносится.
- **Broken:** требуется конкретное исполнение ухода и, в безопасной Zone, допустимого Recover. Если маршрут/Manoeuvre либо ситуация без доступного выхода не поддержаны, остановиться перед неподдержанным действием. Не придумывать ожидание или Recover среди врагов. Уход в другую Zone сам по себе не удаляет участника из боя.
- **Miscast:** первый runner может останавливаться на точном MISCAST_REQUIRED до preparation, сохраняя pool/successes и доступный desperate choice. Поддержка полного encounter без таких остановок потребует отдельного policy для этого выбора, preparation → optional spell → table roll → effect application. Пока эффект не закрыт, очищенное промежуточное состояние reducer нельзя выдавать за завершённый encounter. Недостающий GM/context не заменять пустым эффектом.
- **Повторный Curse и выбывшие:** допуск ADR-0035 ограничен healthy targets и полным spatial набором round participants. Нужна отдельная адаптация актуальных Conditions/live projection до повторного применения в меняющемся roster. Старые target snapshots не переиспользуются.

Открытые вопросы Miscast `recently`, нехватки объектов и self-inclusion остаются в [open-questions](../open-questions.md). Их разрешение требуется при реализации затрагивающей их ветви, а не для безопасной остановки перед ней. Книжных неоднозначностей этим ADR не решаем.

Будущий objective задаётся отдельно от magic rules. На первом runner нужен явный objective и round limit; Broken, завершение spell или пустая target Zone не объявляют успех автоматически. Обработка pending имеет приоритет перед обоими terminal checks. Массовые прогоны, метрика баланса, JSON/CLI и генерация составов в этот ADR не входят.

## Порядок следующих срезов

1. **Actor-bound Casting → roster consumer.** Сначала frozen input/state/result и pure application одного существующего CowardlyFlightCastingResult. Один явный Champion actor, его CastingCasterDefinition и WizardMagicState; точное соответствие source roster/round/spatial, magic state и target injury snapshots. Применять target Conditions/magic/receipt атомарно, хранить consumed execution IDs, сохранять MISCAST_REQUIRED как блокирующий pending. Reject stale/replay/чужой actor без RNG. Пока только допуск ADR-0035, без loop, нового cast или расширения целей.
2. **Minion Attack → Champion bridge.** Подключить готовый kernel и Wound lifecycle к тому же roster; определить обработанные ветви и точные pending/unsupported для остальных. Сохранить действующий Minion → Minion API.
3. **Casting из актуального roster.** Live projection после defeat, повторные targets с Conditions, legality/effect modifiers и Give Ground completion. Неподдержанные состояния обнаруживать до следующего roll; source chain для всех переходов.
4. **Обязательный ход Broken и magic interruptions.** Узкий явный маршрут/Manoeuvre и Recover с обновлением фактов; полный запрет обычного dispatch при незакрытом продолжении. Нет автоматического выбора GM.
5. **Scenario/runner contract и реализация.** Собрать поддержанные переходы, objective/round limit и typed stop results. На Miscast и иных пока неисполняемых обязательных ветвях — exact unsupported; никаких summary об успешном завершении такого боя. Проверить scripted end-to-end победу, лимит и каждую остановку.
6. **Расширение обязательных Miscast continuations.** Вводить owners/effect consumers отдельными ограниченными срезами; до включения неоднозначных ветвей получить решение пользователя. После покрытия заявленных путей — самостоятельный пример и аудит encounter; затем отдельный план массовой симуляции.

Критерии первого consumer: WAIT/CAST/MISCAST_REQUIRED, обе стороны caster, caster definition ID != actor ID, несколько целей/пустая Zone, exact before/after, сохранение неучаствующих бойцов, replay/stale/source rejection и неизменность входа. Tests используют готовый executor и scripted RNG только для получения исходного результата; сам consumer не получает RNG. Конкретные имена новых классов уточняются при реализации, перечисленная граница является контрактом.
