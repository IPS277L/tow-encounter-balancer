# ADR-0075: запасное одноручное оружие PC

Дата: 2026-11-04. Статус: принято.

## Задача и конечная граница

M19 останавливает бой после полной раны16/18/20, если двуручный хват стал невозможен. M20 добавляет явное запасное оружие и проверяемое переключение на своём ходу, сохраняя прежние source/clock/Wounds/Help/Fate и сквозной путь до подбора.

Источники: BOOK-PLAYER-GUIDE1.4, гл.IV Equipment92–93; гл.V Combat Actions116 / Recover118; Wounds Table190–191. PG92 допускает число carried weapons до Strength и не более одного2H. PG116 разрешает incidental draw/swap в свой ход; pickup рядом с врагом требует Recover. Off-turn incidental actions оставлены на усмотрение GM и здесь не включены. Это явная стратегия симуляции, не новое книжное ограничение.

## Решение

У участника есть nullable `PcBackupWeaponPolicy(weapon, preferred_hand)`: один из шести1H Close профилей и LEFT/RIGHT. Non-null допускается лишь с2H primary и Strength≥2; оба предмета помещаются в нынешнюю carry capacity без нового Burdened initial state. Null сохраняет M19. Общего inventory, dual wield или резервного2H не вводим.

Начальное оружие — primary. Fixed opt-in стратегия переключается только после утраты возможности2H применения, не ради выгоды Damage/Traits, простой потери предмета или раны12. До переключения primary непригоден: входящие Protection используют Athletics, существующие Defence Help snapshots не переназначаются.

После обязательных Wound/Fate/consequence steps, в ближайший собственный ход до резервирования standard slot, живой не-Defenceless PC с одной пригодной рукой оставляет primary и выхватывает backup. Предпочитается здоровая пригодная рука, затем травмированная12; caller preferred_hand разрешает равенство, затем рассматривается другая сторона. Clutch18 не снимается ради оружия. Defenceless20 не позволяет draw: обязательные actionless turns/end phases продолжаются.

Отдельный `PcBackupWeaponDrawProof` связан с полным исходным owner, actor и предыдущим/новым хватом. Он не меняет clock, не расходует standard action, не делает Test и не входит в action count. Это incidental action, поэтому применяются Critical14/15 и последствия фактически использованной руки12; отпускание primary не объявляется использованием непригодной руки. Следующий обычный Recover не отменяет уже полученный Critical.

`using_backup_weapon` — exact bool, подтверждённый единственным draw receipt в истории. После переключения оно необратимо в рамках боя. Нельзя пропустить обязательный draw и сразу зарезервировать Attack/Help/Recover, выхватить предмет вне своего окна или переиграть proof. Canonical replay связывает все transitions, не доверяя только флагу или ID.

Общие helpers определяют actual weapon, предпочтительный хват и instance ID. Damage/actor/target Traits, Protection/Help и Recover используют активный предмет, сохраняя primary/policy в immutable source. После drop подбирается только backup (`actor:backup-weapon`), а не оставленный primary (`actor:weapon`). Дальнейшая1H смена руки/раны/Recover сохраняет прежнюю стратегию; возврата primary нет.

До draw M19-stop подавляется только при configured backup и одной пригодной руке. Если до переключения исчезла последняя пригодная рука, сохраняется actual unsupported с последней вызвавшей это раной; источник выбирается по Wound sequence, не порядку переставляемых body facts. После draw исходный primary2H больше не вызывает этот stop: действует прежняя1H граница. Невозможная повторная анатомия остаётся отдельным pending GM-stop. Near Miss применяется до body consequences и не провоцирует ложное переключение.

## Текущий JSON1

`party[].backup_weapon_policy` обязательно присутствует: null либо закрытый объект `{weapon, preferred_hand}`. Schema/codec повторяют type/carry/primary ограничения. Пропущенное поле отклоняется; текущие M9–M19 examples обновлены явным null во всех root/candidate sources. Старые gameplay values/counters сохраняются, JSON version и метрики не меняются. Полный fixed-party count search сохраняет оба предмета и policy.

## Альтернативы

- Автоматическая подмена primary по одному флагу теряла бы реальное окно draw и давала Defence до собственного хода.
- Переключение сразу при любой потере предмета обходило бы прежний Recover и выбранную ограниченную тактику.
- Общий inventory, произвольное переключение, Brawn fallback и off-turn GM approvals требуют отдельного контракта.
- Новый wire version/compatibility слой не нужны для текущей стадии разработки.

## Проверка

[Native/proof tests](../../tests/unit/test_m20_pc_backup_weapon.py), [source/carry/count projection](../../tests/unit/test_m20_pc_backup_weapon_admission.py), [codec/schema](../../tests/unit/test_m20_pc_backup_weapon_json.py), [actual observations/process/search](../../tests/integration/test_m20_pc_backup_weapon.py). Ближайшая регрессия — PC M9–M20 и связанные K1 Test/Attack/Protection/Help/Recover/Fate/Wounds, без повторения M8 callers: shared K1/Recover не менялись.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.unit.test_m20_pc_backup_weapon tests.unit.test_m20_pc_backup_weapon_admission tests.unit.test_m20_pc_backup_weapon_json tests.integration.test_m20_pc_backup_weapon tests.unit.test_m9_pc_melee_json tests.unit.test_m9_pc_melee_json_schemas -q
```

Actual CLI примеры, full source echo, current offline schemas и миграция22прежних request/result pairs проверяются адресно. Full/wheel нужны лишь по согласованным контрольным точкам AGENTS, не автоматически для ADR. Фактические результаты и следующий шаг — в [статусе](../project-status.md).
