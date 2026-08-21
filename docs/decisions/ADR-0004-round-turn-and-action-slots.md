# ADR-0004: round/turn state и action slots до полного battle loop

Статус: принято, 2026-08-20.

## Контекст

Player’s Guide 1.4 на страницах 111–112 и 116 задаёт два уровня порядка: стороны действуют последовательно, а внутри текущей стороны участники каждый раунд выбирают порядок заново и полностью завершают свой ход. Обычно доступен один action; Fate или Ability могут дать второй, но не третий. Один action нельзя повторить, второе действие не может дать вторую атаку, а два разных Improvise возможны только с разрешения GM. Charge на странице 117 классифицирован как Manoeuvre, но включает атаку.

Существующие K1 attack, casting и spatial reducers имеют разные входы и состояния. Их немедленное объединение в новый монолитный `BattleEngine` смешало бы проверку бюджета, расход ресурсов, выбор целей и исполнение эффектов до определения устойчивых границ.

## Решение

- Хранить неизменяемый `CombatRoundState`: номер раунда, снимок участников двух книжных сторон, persistent `side_order`, завершивших ход actor и не более одного активного хода.
- Выбирать actor внутри доступной стороны внешней policy; открывать следующую сторону только после завершения всех участников текущей.
- Передавать новый eligible participant snapshot при явном переходе к следующему раунду и сохранять side order, включая opposition-first после засады.
- Хранить в `CombatTurnState` actor и максимум два `CombatActionSlot`.
- Типизировать шесть действий, четыре варианта Manoeuvre и три источника Improvise: Skill, spell либо Ability. Считать Attack, Charge и явно помеченный атакующий Improvise формами, производящими атаку.
- Первый slot разрешать только как `STANDARD`; второй — только с provenance `FATE` либо `ABILITY` с конкретным Rule ID. Scheduler не расходует Fate и не мутирует состояние Ability.
- Запрещать одинаковые actions и вторую атаку как инварианты. Для двух Improvise требовать разные approach ID; дополнительно резолвер принимает явное разрешение GM.
- Считать slot разрешением на следующую фазу, а не исполненным действием. Attack/casting/movement reducers подключать отдельными узкими адаптерами с проверяемой связью входа и результата.
- После успешного специализированного executor добавлять к slot универсальную неизменяемую `ActionExecutionReceipt`; до этого slot остаётся только резервацией.
- Для первого Attack adapter хранить actor, выбранный target ID, slot index, `KernelAttackRequest`, состояния хода до/после и вложенный `ResolutionResult`. Менять в round state только receipt выбранного slot; injury state не встраивать в scheduler.
- Для spell Improvise adapter хранить actor, slot index, `CastingTestRequest`, состояния хода до/после и вложенный `CastingTestResult`. Требовать совпадения stable approach ID с объявленным Lore и исполнять ровно один Casting Test, не применяя его follow-up и не принимая последующее решение `CAST`/`WAIT`.
- Подключать post-Test фазу отдельным контрактом: проверить provenance Rule of Nine, применить Miscast Pool threshold и только в normal-ветви принять готовый `CastingDecisionRequest` того же actor, Wizard Level и post-pool state. Triggered-ветвь не маскировать под `WAIT`: она сохраняет базовый Miscast roll request для обязательной preparation-фазы.
- Подключать triggered preparation ещё одним узким adapter над существующим `prepare_miscast`. Требовать точное совпадение post-Test actor/source roll/state; возвращать optional pre-Miscast spell и обязательный roll в книжном порядке, не исполняя их рекурсивно.
- Для interrupted Casting не встраивать magic state в Attack executor. Отдельный adapter принимает завершённый Attack и актуальный `WizardMagicState`, создаёт одно action-sourced увеличение Miscast Pool и применяет общий threshold. Различать provenance `TEST`/`ACTION`, а повторное потребление receipt оставить будущему battle aggregate.
- Добровольное прекращение уже активного Casting считать отдельным magic decision без нового action slot. При непустом пуле переиспользовать общую preparation-фазу, при пустом — очистить Casting snapshot без `MiscastRollRequest`; уже triggered pool принимает только прежний обязательный preparation path.
- Free move и его Prone-removal alternative считать incidental spatial-фазами без action slot. Composite requests используют round state только для проверки active actor и синхронизации номера round; изменяемый placement/target Condition и общий once-per-turn usage остаются вне turn state.
- Базовый Run исполнять отдельным composite adapter над зарезервированным Run slot и `SpatialBattleState`: сначала проверить и применить переход в одну соседнюю Zone, затем добавить receipt. Не помещать placement или free-move usage в turn state.
- Optional Athletics Run исполнять отдельной post-movement фазой над завершённым base result: не создавать второй receipt, на успехе менять только spatial state, а на провале применять первый Staggered. Явно запрещать её после Difficult Terrain Athletics Test того же turn.
- Запрещать завершение хода с зарезервированным, но неисполненным обычным Attack, базовым Run или spell Improvise. Для ещё не подключённых action kinds временно сохранять прежнюю границу резервации.

## Последствия

Порядок боя и action economy можно тестировать без RNG, карты, injury state и старого P1 battle loop. Конкретные действия сохраняют собственные типизированные контракты, а Fate/Ability state остаётся у будущего агрегирующего orchestration.

Срез пока не определяет Awareness-результат засады, прочие incidental actions, расход Fate, эффекты Aim/Help/Recover, остальные Manoeuvre, исполнение подготовленных Miscast follow-ups, target discovery, общий battle aggregate, окончание боя и AI выбора порядка. Обычный Attack, обе фазы Run, normal post-Casting, triggered preparation, добровольное прекращение Casting, skipped Casting consequence после Attack и обе ветви free move уже исполняются; соответствующий slot должен завершиться до конца хода. Charge остаётся Manoeuvre. Завершение активного хода требует зарезервировать standard action; если позднее книжный источник потребует явный pass/skip, он должен быть представлен отдельным нормативным действием или решением, а не пустым ходом.
