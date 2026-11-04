# ADR-0068: продолжение PC melee после тяжёлых ран

Дата: 2026-11-04. Статус: **M12 реализована и проверена в указанной границе**. Пользователь выбрал все раны11–23 и продолжение боя с книжными последствиями.

## Задача и варианты

После M11 пользователь поручил продолжить работу с тяжёлыми PC-ранами. Они ограничивают оценку трудных боёв: слабая M11 party остановилась во всех12trials; более устойчивая группа также получает unsupported при добавлении Minions. Не считать эти остановки поражением или исключать их из denominator.

Выбранная пользователем граница:

1. Все результаты11–23 Wounds Table; generic stop на тяжёлой строке больше не требуется.
2. Продолжать Attack/Recover, принимая книжные осложнения; по возможности использовать здоровую руку и прижимать живот свободной. Это выбор поведения симуляции, не изменение правил ран. Политика передаётся явно для каждого PC.

Сохраняются нынешние Staff/Sword, numeric Minion/Brute, одна Close Zone, индивидуальные состояния/Fate, fixed orders/priorities и decline optional Fate. Лечение, campaign, общий inventory, дополнительные оружие/Abilities и активное Fate сюда не включаются. Defeat группы по-прежнему означает гибель всех PC; Defenceless не равняется смерти, и бой может продолжаться до death либо round budget.

## Проверенные источники

Адресно прочитаны локальные extracted Player’s Guide1.4: Rules / Combat Actions116, Recover/Attack Tests118, Conditions122–123 и Wounds Table190–191. Полного повторного чтения книг или смены версий нет.

- Critically Injured: Endurance в конце каждого собственного хода. Провал даёт Defenceless; провал при уже имеющемся Defenceless даёт смерть. Успех сам по себе не снимает Condition. Несколько источников одной Condition не умножают её end-turn Test.
- Defenceless: нет действий, движения и Opposition; обязательные Tests, вызванные эффектом/Condition, остаются. Любая успешная атака наносит Wound, независимо от обычного сравнения Damage/Resilience.
- PG116 допускает incidental swap удерживаемых предметов. В рамках текущего одного1Hоружия можно явно выбрать перекладывание в пригодную свободную руку, без общего inventory. Перекладывание не легализует использование утраченной/непригодной руки; использование травмированной руки12 для pickup/Attack/Defence требует её последствия.
- W18 допускает immediate drop/clutch либо Defenceless. Выбор пригодной свободной руки позволяет сохранить оружие в другой; занятая прижиманием рука больше не доступна для оружия. Если прижимать нечем, нельзя объявить успешное clutch.
- W15/19 создают ongoing Staggered until healed; W17 — ongoing Prone until treated. По PG122 ongoing Condition нельзя снять, пока причина не устранена. Специализированный срок Wounds Table имеет приоритет над общим удалением Staggered при новой Wound; удержать соответствующий источник, не создавать повторное получение Condition. Near Miss/негативная Wound сохраняет прежнее состояние по своему правилу.
- Для W14/15 action включает объявленные Combat Actions и добровольные incidental/free actions PG116, например отдельный HandSwap и выбранное clutch/regrip. Взаимодействие с предметом в составе Recover остаётся частью освобождённого Recover для14; отдельный swap — нет. Forced drops4/8/12 не являются добровольно взятыми actions. Opposition Test сама по себе не объявленное действие; у W12 формулировка шире — использование травмированной руки включает и защиту оружием.

## Обнаруженные пробелы реализации

Открыть gate11–23 недостаточно. K1 содержит таблицу эффектов и requests follow-ups, но не весь следующий игровой цикл:

1. Нет consumer конца хода Critically Injured. Обычный `end_combat_turn` требует standard action и отвергает пустой ход; для Defenceless нужен явный incapacity path с сохранёнными end-turn Tests, без фиктивного Attack/Recover и без исключения живого PC как погибшего.
2. Protection учитывает запрет Opposition, но kernel ещё не применяет automatic Wound при успешной атаке по Defenceless. Нет consumer `PHYSICAL_STAGGER_BECOMES_WOUND` раны22. Нельзя подменять Resilience/Damage для получения нужного исхода: нужен actual source-bound переход.
3. Не исполняются в PC owner follow-ups зубов/пальца/глаза, random arm/leg и immediate clutch. Требуются ordered proofs реальных Tests/d10/выборов, отдельные для каждого PC/sequence; не заменять последствия пустым acknowledgement.
4. Нет runtime consumers ограничений12–15 и непригодной руки16/20. Нужны точная связь с использованной рукой/действием/снятием Prone, сохранение source Conditions и ограничений, явное поведение при отсутствии пригодной руки.
5. Текущий character Wound roll удаляет Staggered без проверки ongoing source; Recover также должен выбирать только допустимые снятия Conditions. Для тяжёлых источников нужна адресная коррекция, сохраняющая обычный случай и Near Miss.

## Конечный результат и интерфейсы

`PcMeleeParticipant.random_hand_policy/PcRandomHandPolicy` заменяются на `random_side_policy/PcRandomSidePolicy`: тот же явно выбранный протокол `d10_low_left_high_right` охватывает обе стороны тела. При двух допустимых сторонах бросается один d10; при одной сторона определена, при отсутствии допустимой стороны результат не выдумывается. Обязательное поле `heavy_wound_policy: PcHeavyWoundPolicy.CONTINUE_FIGHTING` со значением `continue_fighting` располагается перед `initial_weapon_hand`. Старые field/class aliases и wire shape не сохраняются.

Bound body facts имеют закрытые типы и источник PC/Wound sequence: injured hand, unusable/lost arm, lost leg/eye/finger/teeth, clutch stomach. Нет переносимого campaign inventory. Если оружие нельзя использовать, выбирается только допустимый self Recover без невозможного pickup; незаявленный Brawn не добавляется. Если обязательной анатомической потере уже не соответствует ни одна существующая часть тела, остаётся actor/source-bound `unavailable_anatomical_target` stop на actual pending consequence. Это ограничение физически невозможной повторной комбинации, а не отказ поддержать отдельную строку11–23. Unsupported по-прежнему входит в denominator и запрещает selection.

Общий kernel получает явный `KernelAttackRequest.physical_attack: bool=False` как признак подтверждённой физической атаки; PC ordinary Melee builder задаёт True. Pure `condition_forces_wound(request,attack)` использует фактическую успешную Damage Attack и target source: Defenceless либо physical Staggered при permanent restriction22. Исходный AttackResult, Damage/Resilience и его trace не переписываются. Психологические Condition/Hazard Attack ветви за пределами этого среза не объявляются физическими.

`CriticalInjuryTestRequest(id,actor_id,state,test_id)` и `resolve_critical_injury_test(request,test)` исполняют последствие уже выполненной Endurance Test без новых RNG/Wound/daily. PC owner отдельно связывает actual TestProfile/trace/Fate и после-Test Grim consumption. End phase имеет явный источник; пустой incapacity turn не проходит как обычная выполненная атака. Обязательная Critical проверка текущего PC не пропускается из-за победы над последним NPC.

- Actual pending PLAYER Wound сначала закрывает Near Miss, затем daily registration/effects и все обязательные follow-ups. Поддержанный результат не оставляет старый generic heavy-wound stop.
- Bound body/hand/loss facts хранятся только в нынешнем fresh battle owner: injured/unusable/lost sides, clutch и выпадение одного известного оружия. Это не создание персонажа, универсального inventory или campaign save.
- Endurance/случайные последствия и переключения рук не погашают чужой next-Test Grim, expiry или Fate. Невозможное действие не исполняется и не заменяется незаявленным Brawn/лечением.
- В конце собственного хода обязательные Tests, возможные Defenceless/death, source-aware expiry и общий clock применяются однократно в явном порядке. Живой Defenceless сохраняет свои ходы/обязательные проверки, но не может выполнить action.
- Успешные атаки по Defenceless/ограничению22 исполняют настоящий Wound lifecycle. PC смерти от end-turn Condition учитываются в прежних loss metrics, с источником; лишение возможности действовать не считается смертью.
- Trials, aggregate-only balance, denominator и selection сохраняют прежний смысл. Один текущий PC JSON1 требует `random_side_policy` и `heavy_wound_policy`, обновлён вместе со схемами/примерами, без legacy branch.

## Проверка

До реализации — конечная матрица поддержанных строк и обязательных/условных последствий. Затем детерминированные Tests/hand/loss/critical/death/Defenceless cases, повторные и смешанные источники, full-prefix/replay/forgery guards, actual party continuations и один representative sequential/process/CLI путь. Не проверять все комбинации большой матрицей module/console/backend.

Меняются общие kernel Damage→Wound и source-aware character Wound removal: после адресных детерминированных/сквозных проверок нужна одна широкая checkpoint regression по их фактическим зависимостям. Основание — изменение общего игрового ядра, не новый ADR. Wheel не нужен без изменения поставки. Успешные дорогие проверки не повторяются без влияющего изменения.

## Реализация и результаты

Общие [forced-Wound](../../src/towr/domain/resolution_models.py)/[kernel](../../src/towr/rules/kernel.py), [adrenaline/canonical source](../../src/towr/domain/injury_models.py) и pure [Critical consumer](../../src/towr/rules/critical_injury_resolution.py) подключены к PC owner. Закрытые [body facts](../../src/towr/domain/pc_heavy_wound_models.py), [consequences](../../src/towr/domain/_pc_heavy_wound_projection.py), [end phase](../../src/towr/domain/pc_heavy_turn_projection.py) и [runner](../../src/towr/engine/pc_melee_runner.py) сохраняют actual actions, Tests, source history и однократность.

Добавлены [10 common K1 cases](../../tests/unit/test_k1_heavy_wound_rules.py), [15 heavy/hand-use unit IDs](../../tests/unit/test_m12_pc_heavy_wounds.py), [3 actual trials/balance/process cases](../../tests/integration/test_m12_pc_heavy_wounds.py) и3wire/schema IDs. Прежние generic heavy-stop проверки перенесены на реальный no-eligible-anatomy stop, не удаляя source/replay/denominator guards. Real3-outcome прежний Minion источник сохраняет33actions/13started/11completed; native unavailable-arm case —5/1/0 и unsupported1/N1.

Приёмка **составная**, без утверждения единого полного run всех финальных файлов:

| Проверка | Фактический результат |
|---|---|
| Общие K1 heavy/injury/lifecycle/kernel |53OK/0.009s, включая10новых|
| Engine/источники/все тяжёлые строки |72OK/4.597s; `.cache/m12-engine-unit-final.log`|
| Pure wire/schema |28OK/2.103s,7schemas/90offline refs|
| Вся PC subsystem M9–M12, реальные process/CLI |149OK/41.748s; `.cache/m12-pc-subsystem.log`|
| **Одна полная checkpoint regression** |**4471 tests OK/1581.418s**, без failures/errors/skips; `.cache/m12-full-regression.log`|
| Финальная PC-коррекция incidental hand use |**59OK/6.649s**, включая2новыхIDs/6native subcases и1heavy process; `.cache/m12-final-pc-recheck.log`|

Полная команда: при `PYTHONPATH=src` — `.venv/Scripts/python.exe -m unittest discover -s tests -v`. Все1019source/tests `.py/.json` не менялись во время полного run; проверено `.cache/m12-source-manifest.json`. После него изменены только3PC projection/helper files и1unit-regression file: corrected source binding при переносе в травмированную руку и выбранном clutch/regrip, с14/15free-action consequences. До исправления2новыхтеста воспроизводили6native subcase failures; после — все успешны. Общие K1 файлы остались теми же; hashes/diff проверены `.cache/m12_verify_final_sources.py`, финальный manifest `.cache/m12-final-source-manifest.json`. Успешный full и дорогая CLI-матрица не повторялись.

Ревью также закрыло пропуск mandatory Critical tail в усечённом last-NPC victory, wrong-type aliases в отдельно скопированных requests, W12 без существующих рук и стирание independent Prone source при недоступном removal. Все исправления имеют детерминированные регрессии. Defenceless не считается смертью; Critically Injured death не добавляет Wound/daily receipt.

Все8current M9–M12 requests выполнены реальными CLI с lossless request echo; M12 simulation/balance повторно проверены после последней PC-коррекции и дали полные ответы, равные сохранённым. [M12 simulation](../examples/m12/pc-melee-simulation.result.json):4objective/6party_defeated/2round_limit из12, unsupported0,9trials с подтверждёнными потерями. [Balance](../examples/m12/pc-melee-balance.result.json):0,1 и1,1 —8objective из8,2,1 —6objective/2round_limit; выбран2,1 затем0,1. Прежние12generic heavy stops того же игрового входа не подменены поражениями — бой теперь продолжен до фактического исхода. Это observations конкретных seeds/trials/policies, не фиксированные игровые вероятности.

Wheel/fresh install не требовались: package discovery/resource inclusion/entry points не менялись. Full regression уже покрыла общий риск K1; post-healing optional Endurance22, лечение/campaign, active Fate, общий inventory и GM-замены невозможной анатомии не добавлены. Обязательного остатка в выбранной M12 нет.
