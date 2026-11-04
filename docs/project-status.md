# Текущий статус проекта

Дата обновления: 2026-11-04.

## Текущий этап

**M24 завершена в выбранной границе.** Broken Official может покинуть PC encounter через один явно подтверждённый clear/fastest adjacent safe exit. [ADR-0079](decisions/ADR-0079-pc-broken-npc-adjacent-exit.md), [правило](rules/npc-profile-catalog.md#official-exit-m24), [JSON/CLI-примеры](examples/m24/README.md).

Пользователь выбрал objective «все NPC побеждены или ушли», с отдельным учётом ухода. Official движется только в свой собственный ход после предыдущих очередей/end phases; W2 до этого окна по-прежнему даёт defeat. Actual common FreeMovement proof сохраняет W1/Broken/not defeated, не расходует RNG/standard action и не создаёт фиктивный TurnEnd. Ушедший actor исключается из целей, численности, новых Help decisions и следующих ходов. Старый Help, адресованный его будущему Test, не переносится.

Source требует nullable npc_broken_exit_policy с destination_zone_id/path_clear_confirmed/fastest_route_confirmed; ненулевая policy требует can_leave_zone=true. При null сохраняется точная остановка M23 перед Broken turn. Trials хранят source-ordered npc_exit_counts, summary — также npc_exit_trial_count, total_npc_exit_count и objective_with_npc_exit_count. Частичный уход может предшествовать иному исходу; wound/defeat не подменяются выходом. Балансировщик сохраняет эти агрегаты без native journal.

Current PC JSON1 обновлён вместе со схемой/codec/tests. Все30прежних request/result pairs M9–M23 мигрированы обязательной null policy и нулевыми exit metrics; проверка against HEAD подтвердила сохранение всех остальных значений. Другие families/version не менялись.

## Последняя проверка

После source review код заморожен. При PYTHONPATH=src `.venv/Scripts/python.exe .cache/m24_check_subsystem.py` проверил58модулей/477tests за86.594s:458прошли,19Windows process/Temp checks столкнулись с sandbox WinError5. `.venv/Scripts/python.exe .cache/m24_process_recheck.py` вне sandbox повторил именно эти19: **19tests OK/50.843s**. Дополнительно прошли новый actual-exit process test и9общих FreeMovement tests. Исправление sandbox не меняло production; ошибки вспомогательного выбора test IDs исправлены до финального адресного rerun.

**Итого487уникальных успешных проверок — составной адресный результат, не единый зелёный full run.** Покрыты PC M9–M24, shared Attack/Protection и FreeMovement. Новый process test подтвердил полное равенство ненулевых exit records/summary с sequential. Новые24tests проверяют policy, actual own-turn exit, source/replay/alias guards, сохранение injury, targets/outnumbering/Help/round priorities, null-policy stop, trial/summary integrity и текущий JSON. Дефект exits>actions закрыт до checkpoint. Source review незакрытых замечаний не оставило.

Команда для новой копии без локальных .cache helpers:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.unit.test_m24_pc_npc_exit tests.unit.test_m24_pc_npc_exit_statistics tests.integration.test_m24_pc_npc_exit_json tests.unit.test_k1_free_movement_resolution -v
```

Оба M24 requests исполнены настоящим CLI. Simulation:6objective из6trials,3победы с уходом и3без него;26actions,12started/6completed rounds, без PC deaths/unsupported/limit. Balance:4состава по3trials, все observed objective, отдельные counts уходов; top_k2 выбрал первые два состава. Это малая воспроизводимая выборка, не истинные вероятности/оптимум.

Проверены все32current request/result pairs M9–M24, exact request echo и миграция60старыхJSON documents без изменения прежних значений. Markdown/local links/UTF-8/whitespace и git diff --check проверены. Full regression проекта и wheel не запускались: сборка/ресурсы/dependencies/entry points не менялись. .cache scripts/logs локальны и не входят в репозиторий.

## Ограничения

Четыре registered combat loadouts: Footpad, Townsfolk, Brigand Axe, Official Dagger. Exit — один свободный переход в закрытой двухзонной сцене без внешних участников; всеPC остаются в arena. Нет общего pathfinding/Run/Manoeuvre, преследования, возврата или Recover ушедшего NPC. Снятие Broken при сохраняющейся profile Wound ещё не разрешено.

Сохраняются aware Close arena/fixed orders/priorities, healthy initial party,13Close primary weapons/optional1H backup, Wounds1–23/lethal24+, source-aware Conditions и mandatory Critical/Defenceless end phases. Невозможная повторная анатомия/недоступный хват сохраняют точные stops. Нет общего inventory/Brawn/лечения/campaign/optimal AI; Greatsword требует уточнения бонуса. Costs/losses при stop/limit относятся к исполненному prefix.

## Следующий шаг

Рекомендация — следующий exact книжный NPC/loadout: адресно сверить полную карточку и все применимые Abilities, выбрать исполнимую конечную границу. M25 ещё не выбрана; не расширять автоматически бестиарий/spatial/AI. Альтернатива — дальнейшее поведение Broken; перед Recover Official при W1 отдельно решить ongoing-cause вопрос. [Очередь](roadmap.md), [индекс вопросов](open-questions.md).

Перед M24 рабочее дерево было чистым: M23 уже сохранена пользователем. Изменения M24 незакоммичены; commit/push выполняет пользователь.
