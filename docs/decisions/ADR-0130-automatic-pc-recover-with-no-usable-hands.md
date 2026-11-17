# ADR-0130: продолжение automatic боя без пригодных рук

Дата: 2026-11-17. Статус: принят пользователем и реализован. Выбрано продолжение через настоящий standard Recover.

## Подтверждённая причина

Оба `ranged_grip_unavailable` из [полного process-плана](../benchmarks/dynamic-process-execution-2026-11-17.md#результат) воспроизведены. В обоих случаях правая рука не используется из-за Slashed Forearms16, левая занята Spilling Guts18. Пистолет (Repeater Pistol) загружен, но выпал; Меч (Sword) carried. Нет руки для законного draw/pickup/выстрела. Это не ошибка выбора между доступными оружиями и не случай недоступной Перезарядки (Reload). ID состояния оружия с `:reload:` не доказывает выбранный Reload; фактический fallback пытается Attack и встречает предел хвата.

PG1.4 Appendix190–191:16 запрещает использовать пострадавшую руку до healing;18 требует сразу освободить руку и прижимать живот либо получить Defenceless, а также сохраняет Critically Injured/Burdened/Drained. Принятая continue-fighting policy выбирает clutch при наличии пригодной руки. Ни переносимое оружие, ни смена предмета не создают новую руку. PG1.4 V118 описывает standard Recover для себя/ближнего союзника без требования держать оружие; взаимодействие с предметами всё равно требует реальной пригодной руки.

## Принятая тактика

Для `automatic_combat` с ranged primary, если физически пригодных рук нет, сохранить уже доступные полезные решения (Recover союзнику/себе, разрешённые другие действия). Когда ни одно не выбрано, выполнить настоящий standard Recover вместо попытки недоступного Shoot/Reload. Recover допустим и без полезного removable effect как защитное ожидание; это выбранная тактика, не утверждение об оптимальности. Вручную заданные Attack/Reload policies сохраняют прежний точный stop.

Оружие остаётся dropped/carried, loaded/cycle/progress не сбрасываются, clutch не отпускается. Инвентарь/зелья не используются без руки, фиктивная атака не создаётся. Союзники и NPC продолжают ходы; PC может защищаться лишь реально разрешёнными Skills. Defenceless/dead и mandatory последствия имеют прежний приоритет. Critically Injured/end-phase продолжают исполняться; один standard Recover занимает одно действие. Одинокий PC без возможности победить может дойти до round limit либо умереть — это не автоматическое поражение и не победа.

Поля/версии JSON, входы UI, правила ран и предметов не расширяются. Пользователь согласовал изменение automatic fallback и его наблюдаемых outcomes/counters по AGENTS.md. Рассмотренная альтернатива — сохранить прежний UNSUPPORTED_PATH.

## Реализация и проверка

`select_pc_tactic` даёт нулевую utility настоящему standard Recover как исходному решению только automatic ranged PC без пригодных рук; полезные существующие кандидаты продолжают сравниваться. Одна пригодная рука с недоступной перезарядкой (Reload) сохраняет прежний выбор backup/stop. Ручные policies и committed intent не переопределяются. Нового proof или action kind нет: используются существующие Recover owner/projection и mandatory end-phase.

Prepared tests покрывают16→18/18→16, loaded/empty, carried/dropped backup для Pistol/Repeater Pistol/Repeater Handbow, отсутствие незаконного draw/pickup и положительный one-hand backup. Native literal tests выполняют настоящие Wounds1/2/16/18 и проверяют Recover receipt, отсутствие новых рук/лечения/заряда, CI/death, продолжающихся союзников/NPC, solo round limit и прежний manual stop. Каждый детерминированный журнал воспроизводится; одна party source сравнивается в sequential/process.

Адресная команда (`PYTHONPATH=src`, `.venv/Scripts/python.exe -m unittest ... -q`): `tests.integration.test_pc_no_hand_recover tests.unit.test_pc_ranged_advice tests.unit.test_pc_recover_incidental_pickup tests.unit.test_pc_weapon_inventory tests.unit.test_pc_tactics tests.unit.test_pc_tactical_reuse tests.unit.test_pc_ranged_magic tests.integration.test_dynamic_pc_ranged_json` —78OK/33.843s, лог `.cache/adr130-addressed-validation.log`. До этого real spawn в sandbox получил WinError5; повтор выполнен вне sandbox. Полный regression/wheel/436-trial поиск не запускались: изменён один fallback, правила/формат/доставка прежние.

Оба исходных наблюдавшихся trials адресно повторены: раньше UNSUPPORTED_PATH, теперь PARTY_DEFEATED; раненый PC выполняет один no-hand Recover в каждом. Recover других участников не входит в этот счётчик. Исходные63/108шагов до stop сохранены по значениям; для разделяемого DAG журнала использован memoized structural fingerprint вместо повторного рекурсивного equality. Проверены прежние body facts/раны/inventory/loaded/potions/Fate у его Recover и отсутствие object interaction. Это реальные проигрыши, не автоматическая победа или скрытый пропуск тяжёлой раны. Старый полный process benchmark остаётся историей до ADR-0130; обновлённые win rates всего поиска из двух replays не выводятся.
