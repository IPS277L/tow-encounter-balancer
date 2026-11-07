# ADR-0100: PC Pistol со щитом и порядок Reload/Recover

Дата: 2026-11-07. Статус: **принят пользователем; реализована тактика возврата щита после Reload**.

## Основание и источники

M53 реализует held/dropped/unavailable shield, weapon-first и restore_before_attack. M54 реализует loaded Pistol, настоящий Exacting Reload и выбранную пользователем two_available_hands policy. До M55 их совместный loadout запрещался в typed source и schema; простого снятия запрета недостаточно: прежний self Recover восстанавливал бы щит перед каждой попыткой Reload.

Переиспользованы источники [ADR-0098](ADR-0098-pc-shield-and-hand-equipment.md) и [ADR-0099](ADR-0099-pc-pistol-and-exacting-reload.md). Дополнительно адресно сверены локальные BOOK-PLAYER-GUIDE1.4: IV Ranged Weapons94/Armour97; V Actions116/Recover118; Wounds Table190 и прежние последствия191. PG94 требует действие на каждую Dexterity Test Reload; PG97 отличает held shield от worn armour; PG116/118 требуют Recover для подбора предмета при Close enemy. Free drop и Critical14/15 сохраняют уже согласованное чтение M53. Нового полного чтения книги нет.

Две пригодные руки Reload — уже выбранная GM/scenario конкретизация, а не новое требование книги. M55 не пересматривает её. Порядок действий PC — тактика сценария, которую книга не выбирает вместо пользователя.

## Принятый публичный контракт

Разрешён существующий optional participant `shield` вместе с `pc.weapon=pistol` и полным `pc.pistol` из M54. Щит первоначально held в руке, противоположной Pistol. Сохраняются значения `hand_conflict_policy=weapon_first`, `recovery_policy=restore_before_attack`, `reload_hand_policy=two_available_hands`.

```json
"shield": {
  "initial_hand": "left",
  "hand_conflict_policy": "weapon_first",
  "recovery_policy": "restore_before_attack"
}
```

Это фрагмент party participant с `initial_weapon_hand=right`; полные source fields обязательны по нынешнему PC JSON1. Новых полей, wire version, default shield, null-объекта, запасного оружия или counters не предлагается. Pistol-PC остаётся на ordinary Attack/self Recover, без собственных Help/ally Recover policies. NPC требуют прежнюю законную выбранную ranged Protection. Не добавляются Aim/Rapid Reload/второй Pistol/общий inventory.

184прежнихJSON M9–M54 не требуют миграции; отсутствие щита и прежние melee/shield sources сохраняют поведение. Каталог57NPC не меняется. Обновляются разрешение сочетания в typed source/schema, admission и примеры, без compatibility-only ветвей.

## Принятая тактика: Reload перед возвратом щита

После обязательных последствий, проверки terminal/Defenceless и на собственном ещё не занятом ходу:

1. Сохранить weapon-first release/swap/pickup, если здоровая shield-рука действительно нужна Pistol. Выпавшее оружие восстанавливается настоящим standard Recover. Снимаемый Prone также сохраняет нынешний приоритет self Recover. Loaded/progress/cycle предмета не меняются.
2. При пустом Pistol не выбирать Recover только ради щита и не подбирать его как дополнительный object interaction другого Recover. Пистолетный pickup остаётся первым, Condition benefits сохраняются. Это исключает даже скрытый pickup/release цикл при промежуточном Recover.
3. Когда выбран реальный Reload и доступны обе руки, оставить held shield подтверждённым free release до резервирования действия. Если ранее нужен был Recover, щит не сбрасывается заранее только ради будущего Reload. Release не даёт новый action slot; Critical14 и injured-hand consequences применяются, исключение15 для самого drop сохраняется.
4. Выполнять по одной Dexterity Test за Reload action, пока не накоплены3successes. Щит всё это время dropped, его защиты нет. Завершивший Reload action не поднимает щит и не стреляет автоматически.
5. После завершения Reload возвращать dropped shield отдельным standard Recover до следующего Shoot, если есть свободная здоровая рука, как в M53. Если вернуть щит нельзя, продолжать разрешённый loaded shot без него. Unavailable shield не становится dropped и не получает выдуманный pickup.

Обычный цикл при Reload за одну Test: **Shoot со щитом → free release + Reload → Recover щита → Shoot со щитом**. При нескольких Tests между release и pickup выполняется несколько Reload actions. Если выпали оба предмета, weapon pickup и последующий shield pickup остаются разными действиями. При пустом Pistol между ними сначала выполняется Reload.

Наличие `PcShieldState` само по себе не запрещает Reload: после release состояние предмета сохраняется как dropped. Допуск проверяет фактическую занятость рук, а не удаляет щит из owner ради обхода прежней проверки M54.

## Раны, защита и точные остановки

- Пока shield действительно held/пригоден, он даёт+1Resilience и разрешает Defence против Net. Pistol не даёт Sword Trait. После release — Athletics против Net; по Brawn/Trample остаётся Endurance. Help относится к фактическому Test, не переносится при смене Skill. Damage уже исполняемой атаки не пересчитывается после последующего drop.
- Раны4/8/12 роняют предмет фактической выбранной руки; выпадение щита не разряжает Pistol. Near Miss отменяет соответствующие body facts. После12 щит не возвращается травмированной рукой; сама рука может участвовать в Reload с Critical по M54.
- W14: добровольный release вызывает Critical; W15 разрешает сам drop, последующие Reload/Recover/swap сохраняют свои последствия. Один TurnEnd разрешает обычный Critical путь, без повторного действия/броска.
- W16/20/clutch18 могут сделать руку недоступной. Loaded shot одной пригодной рукой остаётся возможен после необходимого weapon-first освобождения/swap/pickup. Не сбрасывать пригодный щит только ради уже невозможного Reload. Stop остаётся точной границей фактически нужного недоступного Reload/grip до RNG и нового действия, с wound/weapon/cycle source. После выполненного действия нельзя обходить TurnEnd ранним stop.
- Нет лечебного Recover, automatic refill, внеочередного pickup/release после чужой атаки или снятия независимых Net/Wound Conditions. Terminal objective не требует возврата щита или Reload.

## Альтернатива

**Не возвращать щит после добровольного release для Reload** до конца боя; вынужденные drops и hand-conflict release также не являются причиной отдельного shield Recover у Pistol-PC. Оружие и необходимые Condition benefits восстанавливаются как прежде, щит остаётся dropped. Это уменьшает число действий на снаряжение, но меняет M53 restore_before_attack для этого loadout. Для такой тактики нужен отдельный явный source policy, а не скрытая подмена прежнего enum. Поддерживать оба режима без запроса не предлагается.

## Реализация и адресная приёмка

Законченная функция включает source/schema → hand/recovery/reload selection и owner proofs → native/trials/count search/current JSON1/CLI. Используются существующие shield и Pistol states, без универсального inventory или нового clock. Admission связывает actor/hand/action/weapon/cycle и отвергает обход release, восстановление защиты без pickup и forged progress.

1. Полный допустимый Pistol+Shield source/echo и exact types; opposite hands, no backup/Help/ally Recover, closed/partial/null/unknown fields, invalid NPC Protection до RNG. Прежние184JSON и57NPC сохраняются.
2. Literal Shoot→release→Reload0/partial/overshoot/complete→shield Recover→Shoot. Нет pickup/release цикла, автоматической дозарядки, бесплатного pickup/shot или дополнительного slot.
3. Prone/weapon pickup перед Reload, запрет incidental shield pickup при empty Pistol, drops обеих рук и независимые instances; вынужденный drop не меняет ammo/progress. Выпавший loaded Pistol: weapon pickup прежде shield pickup.
4. Actual Defence/Athletics/Endurance, shield Resilience/armoured/ignores-armour, Help/Fate и W10; live dynamic sources до каждой атаки.
5. W12/14/15/16/18/20, Critical/end phase, loaded one-hand shot перед недоступным Reload, отсутствие бесполезного release и точный stop; Near Miss/Defenceless/terminal priority.
6. Replay/typed aliases/full-prefix guards; sequential simulation/balance/full source/candidate echoes и полезный CLI-пример. Один actual process representative при изменении передаваемого поведения; не повторять старую backend matrix.

По умолчанию новые tests и ближайшие M53/M54/PC Recover/Protection/Fate зависимости. Расширять checkpoint только при конкретном влиянии на общий owner. Full project/wheel автоматически не требуются; package/resource mechanism не меняется. Документационную подготовку игровые tests не проверяют.

## Согласование и результат

Пользователь выбрал отдельный возврат щита после завершения Reload. Two_available_hands из M54 сохранена. Source/schema допускают полный комбинированный loadout без новых полей. [Shield helpers](../../src/towr/domain/pc_shield_models.py) подавляют pickup при пустом Pistol и выбирают release непосредственно перед доступным Reload; [Reload](../../src/towr/domain/pc_pistol_models.py) проверяет фактически held shield, сохраняя dropped предмет в owner. Существующие proofs/receipts связывают расход заряда, руки, cycle и восстановление защиты; нового journal variant нет. [Фактическая проверка](../project-status.md), [CLI-примеры](../examples/m55/README.md), [очередь](../roadmap.md).
