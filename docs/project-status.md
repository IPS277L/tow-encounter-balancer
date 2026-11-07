# Текущее состояние проекта

Дата: 2026-11-07. **M56 завершена: явная NPC Melee/Athletics Protection против Close Shooting.** Нормативные источники — Player’s Guide1.4 и Gamemaster’s Guide1.1. [Контракт](decisions/ADR-0101-pc-close-shooting-npc-protection-choice.md), [очередь](roadmap.md#после-m56), [действующие вопросы](open-questions.md).

## Что работает сейчас

Ограниченные немагические ranged/melee/mixed Minion families, M8 Wizard и группа PC против Minions/числовых Brutes сохраняются. PC owner поддерживает Wounds1–23/lethal24+, Critical/Defenceless, Glorious/Near Miss, Help/ally Recover, shield/backup и книжные NPC Abilities в принятых границах. Каталог остаётся57fixed combat loadouts. Точные прежние границы — в [правилах](README.md) и относящихся ADR.

M56 добавляет optional npc_close_shooting_protection_policies: actor→Melee/Athletics для State Trooper Halberd/Spear, unmounted no-shield Empire Knight/Lance и Knight of the White Wolf/Wolf Hammer. Policy действует только против Close Shooting; mixed-party Melee использует прежнюю Defence. Механика не создаёт counterattack/Damage/собственное действие NPC. Melee3d/3/cap6 у Troopers и4d/4/cap8 у Knights сверена по WS/Skills; Athletics напечатана3d/3 и2d/3 соответственно.

[CODE-CONFLICT-005](contradictions.md#code-conflict-005--cap-невыбранной-athletics-knights) исправлен: alternate Athletics metadata двух unshielded Knights теперь InlineProfile(2,3,6), cap6 от Ag3. Уменьшение до printed2dice соответствует heavy armour PG97; второй штраф не применяется.57выбранных definitions/прежняя Defence не переписаны, произвольный authored Protection cap не разрешён.

Typed policy и profile factory проверяют полный canonical источник, actors/Skills/caps до RNG. Optional field при наличии закрытый и непустой; None/absence хранится как отсутствие. Full template проверяется до subset generation; при удалении NPC удаляется его policy, без переназначения, пустой остаток не сериализуется. Current PC JSON1 без смены версии/counters,188прежнихJSON M9–M55 побайтно сохранены. Canonical full-prefix proof связывает policy/actor/actual Test; raw snapshots не являются save/resume API.

Prone NPC даёт–1d Shooting, защитный Melee не получает Attack-only outnumbering/higher-ground/Charge/PC Traits/чужую Help. Knights W1Drained/W2defeat, Unaware/Defenceless и actual Fate prefix сохраняются. NPC Attack/Help/Recover/приоритет целей не меняются. M54/M55 Pistol+Shield cycle сохраняется: выстрел → release перед доступным Reload → Reload до готовности → отдельный Recover щита → следующий выстрел. Loaded one-hand shot разрешён до фактически недоступного Reload/grip; stop не превращает ограничение в смерть PC.

## Последняя проверка

**31новый тест — OK составными адресными прогонами**, не единый full run:9source,8JSON/services,13native execution и1actual process. Проверены обе Skills для всех4loadouts, caps, mixed party, tie/both-fail/no-counterattack, W1Drained→дальнейшая Protection→W2defeat, Fate, Prone/Defenceless и source/replay guards.

- `tests.unit.test_m56_close_shooting_source`: **9OK,0.036s**, exact/frozen/pickle/canonical source/optional tuple/actors и188old-input scope без миграции.
- `tests.integration.test_m56_close_shooting_json` + прежний `tests.unit.test_m30_pc_brute_catalog`: **16OK,3.275s**. Новая wire часть8tests включает strict optional object, actual sequential simulation/balance/offline schemas/full root/candidate echoes, actor filtering и zero-count full template. Начальный authored fixture ошибочно смешивал разные definitions в одной count group; исправлен на однородные группы, весь module повторён.
- `tests.unit.test_m56_close_shooting_execution`: **13native tests прошли составно**. Первоначальные10успешны;2исправленных ожидания проверяют Staggered/W1 после настоящего follow-up/ACK, а не до него: **2OK,0.309s**. Дополнительный actual Shooting Fate test: **1OK,0.038s**. Production дефектов независимые source/runtime reviews не выявили.
- Прежние M9models и K1Protection: **31OK,0.035s**. Optional scenario field отражён в field-required проверке, остальные обязательные поля сохранены.
- Ближайшая регрессия8modules: M25StateTrooper, M36SpearCatalog, M41ShieldCatalog, M11Brutes, M9JSON, integration M54/M55JSON и M55native. Первый прогон103tests за6.001s выявил2устаревших M9JSON ожидания после M54: enum без Pistol и Shooting как запрещённый Glorious criterion. Обновлены полноценный mixed-party firearm source/lawful Protection и invalid Toil criterion; весь M9JSON повторён: **38OK,2.592s**. Остальные65успешных cases не повторялись. Это составная регрессия, не единый зелёный103run.

Переносимая команда нового поведения:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.unit.test_m56_close_shooting_source tests.unit.test_m56_close_shooting_execution tests.integration.test_m56_close_shooting_json -v
```

Actual process вне Windows sandbox: `.venv/Scripts/python.exe -m unittest tests.integration.test_m56_close_shooting_process -v` — **1OK,4.144s**. Полные source policies, compact records/actions и summary совпадают sequential/process. Четыре native preflight trials (shots,reloads,actions,outcome): (2,6,16,limit), (2,6,16,limit), (3,5,15,objective), (2,6,16,limit). Каждый выстрел имеет реальную Melee opposition; NPC собственные Attack продолжаются с прежней PC Defence. Старую backend matrix не повторять без нового основания.

Оба [CLI-примера](examples/m56/README.md) выполнены sequential: mixed party Pistol+Shield/Sword+Shield против4NPC, seed42/6trials/8rounds:0objective/4party defeated/1limit/1unsupported,114actions,30started/25completed rounds. Native разбор trial1 установил прежний M54stop: W3/table16/unusable arm → фактически недоступный Reload, `pistol_reload_hands_unavailable`. Balance фиксирует2Troopers и варьирует двух Knights по0–1;4состава по2trials. Таблица/ограничения малой выборки — в примере, unsupported не исключён из знаменателя.

`.venv/Scripts/python.exe .cache/m56_verify.py`:96current request/result pairs M9–M56, offline schemas/native admission/full source echoes,188прежнихJSON byte-identical и каталог57. Проверены изменённые UTF-8/whitespace/Markdown local file targets и текущие затронутые anchors, `git -c core.safecrlf=false diff --check`. Это не проверка всех исторических fragments; локальные.cache helpers не входят в репозиторий.

Изменены source/policy selection/codec и subset filtering; общий K1Protection уже поддерживал Close ranged Melee. Нового clock/proofvariant/dependencies/package discovery/entry points нет. Выполнены новые и ближайшие проверки плюс один actual process. Full project regression/wheel и прежний209checkpoint M54 не повторялись; поставку проверять при изменении механизма или перед выпуском по AGENTS.md.

## Ограничения

Fresh fixed Close/noMove/noExternal/all-included physical source сохраняется. Новая NPC policy разрешена только4каноническим M56loadouts, не произвольным authored NPC/другим Skills. Для остальных Pistol NPC по-прежнему нужны готовые lawful Athletics либо Defence+shield. Нет автоматического выбора лучшего Skill/чужой Athletics. Counterattack/Aim/Rapid Reload/spatial ranged бой не добавлены.

Pistol без backup/второго firearm/finite-ammo simulation/собственных Help/ally Recover policies; mixed party с прежними policies допустима. Two_available_hands — выбранная GM/scenario конкретизация. Shield2H/backup/bash, passive injured-hand shielding, союзный pickup/передача и generic inventory вне среза. M52Net без pickup/Brawn освобождения; M51Crown требует actual нового Prone от первой Antlers Attack и той же живой цели. M48SkinWolf wave/focus/прежние stops сохраняются; Pegasus grounded, Ogre Rough Shove/Mighty Throw/campaign healing не добавлены.

Невозможная повторная анатомия и недоступный2H хват без продолжения имеют точные stops. Dragon Ogre ждёт [shield/Resilience уточнения](open-questions-details.md#dragon-ogre-shield-resilience), Greatsword Defence bonus открыт. Costs/losses при stop/limit относятся к фактическому prefix.

## Следующий шаг

Сверить следующий совместимый чанк той же policy: Orc Boy Choppas/Spear без щита и Big ’Un Choppas/Spear без щита. Проверить WS/Skills/Athletics/caps и Melee Help/Charge формулировки; определить, укладывается ли расширение в M56 образец, либо нужна конкретизация тактики. До сверки автоматического разрешения другим NPC нет. [Очередь](roadmap.md#после-m56). M56 завершена, её выбранный объём повторно не согласовывать.

Перед M48 рабочая копия была чистой после пользовательского commit `872dbe0` (M47 P1). Изменения M48–M56 остаются незакоммичены; прежние изменения сохранены. Commit/push выполняет пользователь.
