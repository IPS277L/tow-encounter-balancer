# Текущий статус проекта

Дата обновления: 2026-11-04.

## Текущий этап

**M20 завершена в выбранной границе.** Двуручный PC может иметь явное запасное1H Close-оружие и перейти на него после утраты2H возможности. [Контракт ADR-0075](decisions/ADR-0075-pc-backup-weapon-policy.md), [правила](rules/equipment.md#исполняемая-pc-граница-m20), [JSON/CLI-примеры](examples/m20/README.md).

Обязательное nullable `backup_weapon_policy` задаёт weapon/preferred_hand. Non-null требует2H primary и Strength≥2 для двух carried weapons; null сохраняет M19. Actual incidental draw происходит в свой unreserved turn, после immediate Wound/Fate consequences, при одной пригодной руке и отсутствии Defenceless. До draw Protection использует Athletics, старый Defence Help не переназначается. Clutch18 сохраняется; Defenceless20 продолжает обязательные end phases без draw.

Draw подтверждён отдельным source-bound proof и единственным using_backup_weapon receipt. Он не делает Test, не меняет clock/standard slots/action count, но вызывает Critical14/15 и последствия использованной руки12. Затем active weapon/grip/item ID определяют Damage/Traits/Help/Protection и pickup именно backup; возврата primary нет. При0hands до draw actual stop связан с последней вызвавшей это раной по sequence, независимо порядка переставленных body facts. После draw действует прежняя1H граница, исходный primary2H не вызывает ложный stop.

Текущий PC JSON1 требует поле policy у каждого участника: null либо закрытый объект. Пропуск отклоняется; Python source также требует явное значение. Все22прежние request/result pairs M9–M19 мигрированы null-policy во всех root/candidate sources, без изменения старых gameplay/counters. Версия и метрики не менялись; count search фиксирует оба оружия, preference, Fate и роли.

## Последняя проверка

Широкий адресный прогон при `PYTHONPATH=src`: `.venv/Scripts/python.exe .cache/m20_check_subsystem.py` —58модулей PC M9–M20 и связанных K1 путей,555tests/87.281s,554успешных и1failure,0errors/skips. Log `.cache/m20-pc-subsystem.log`. Failure — прежний invariant обязательных Python source fields: у нового поля был defaultNone. Default убран, общий fresh builder теперь явно передаётNone; игровые значения/переходы не изменились.

После исправления повторены упавший модуль и ближайшие зависимые M20/codec/process checks: **99 tests OK/10.643s**,7модулей,0failures/errors/skips. Команда:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.unit.test_m9_pc_melee_models tests.unit.test_m9_pc_melee_json tests.unit.test_m9_pc_melee_json_schemas tests.unit.test_m20_pc_backup_weapon tests.unit.test_m20_pc_backup_weapon_admission tests.unit.test_m20_pc_backup_weapon_json tests.integration.test_m20_pc_backup_weapon -q
```

Это составная приёмка с исправленным отказом, не единый зелёный прогон555 и не полный regression проекта. Успешные дорогие проверки не повторялись. После99tests код/тесты не менялись. Локальные `.cache` scripts/logs не являются частью репозитория.

Добавлены12native tests,4admission/carry,7codec/schema и4integration. Проверены actual draw16/18, Defenceless20 без draw, обе роли предметов в drop/Recover, Critical12/14/15, active Damage всех6backups/Defence/Help, Near Miss, replay/forged/skip guards и real process parity. Review выявил и закрыт регрессией случай clutch relocation: facts(4,3) не могут привязать новый0hands stop к старойране3. Source выбирается по actual Wound sequence.

Оба M20 requests выполнены настоящим CLI с exact full request echo; наблюдения находятся в примерах. После устранения constructor default повторены schema/source проверки:22старые пары/32candidate scenarios roundtrip, все прежние значения совпадают с HEAD после удаления нового null-поля. Public requests уже содержат явное поле; этот fix не меняет их игровые входы. Малые результаты не объявляются оценками вероятности/пользой backup или оптимумом.

Shared K1/Recover не менялись, M8 callers повторно не запускались; сборка/dependencies/resources/entry points не менялись. Full regression/wheel не запускались.

`.cache/m20_verify_docs.py` проверил11изменённых Markdown/1044локальных targets, все24current request/result pairs M9–M20 и UTF-8/newline/whitespace изменённых файлов. `git diff --check` успешен.

## Ограничения

Здоровая initial party,13Close primary weapons, optional один1H backup только для2H primary, numeric Melee Minions/Brutes без on-Wound abilities, одна Close Zone и fixed orders/priorities. Переключение только при actual недоступном2H хвате, не по произвольной выгоде, ране12 или простому drop. Нет off-turn draw, возврата primary, backup2H, dual wield, общего inventory/Brawn/других ranges/Charge/mounts. Greatsword требует уточнения бонуса.

Сохраняются Wounds1–23/lethal24+, source-aware ongoing Conditions, mandatory Critical/Defenceless end phases и невозможная повторная анатомия как pending GM-stop. Null policy оставляет M19-stop16/18/20; configured backup не гарантирует дальнейшую возможность действовать или выживание. Ally Recover не лечит раны/Defenceless/Critical. Другие Help/Fate/Lucky, лечение/campaign, полный NPC catalog и optimal AI остаются за границей. Costs/losses при stop/limit относятся только к исполненному prefix.

## Следующий шаг

Предложение — первый ограниченный каталог книжных NPC-профилей для PC balance. Сначала выбрать Minion/Brute, чьи механики полностью укладываются в текущий срез, с книгой/страницей/полным source; дополнительные Abilities не отбрасывать ради допуска. Если они нужны, отдельно определить конечный scope. M21 ещё не согласована. [Очередь](roadmap.md), [индекс вопросов](open-questions.md).

Перед M20 рабочее дерево было чистым; пользователь сохранил M19 в Git. Изменения M20 незакоммичены; commit/push выполняет пользователь.
