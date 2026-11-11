# ADR-0110: PC Sling, free reload и запрет Close независимо от рук

Дата: 2026-11-11. Статус: **принято и реализовано M68**. Пользователь поручил продолжить рекомендованный полный вариант Sling с optional shield и melee backup.

## Источники и функция

Адресно прочитаны BOOK-PLAYER-GUIDE1.4 IV Ranged Weapons94–95 и carrying92; переиспользуются ранее прочитанные V107/110/114–119/123 и M53/M60/M64–M67. Сверены существующие shared Sling combat/reload profiles и PC owner/backup/shield/source. Новых PDF/версий/house rules нет.

Sling:1H, optimum только Medium, Damage=S (Strength), обычная броня, maximum Long по общему правилу1H. Reload не указан, поэтому бесплатен как часть Attack. Blackpowder Lore/kit и Exacting Dexterity не нужны. Short допустим с−1d; это не Medium opening и не новая Zone. Любой Close enemy запрещает стрельбу, поскольку Close не входит в optimum; запрет не зависит от1H/2H и действует даже при выборе другой Short-цели.

Sling подключён к нынешнему Short opening: первый выстрел→подход NPC→на собственном ходу declared1H melee backup. NPC/Zone/target priority прежние. Без backup — actual PcRangedCloseUnsupported/ranged_close_enemy после обязательных последствий и действительно выбранного standard Recover. Если враги ещё не подошли и не завершили бой, Sling остаётся доступен с free reload. Одна пригодная рука достаточна; сама потеря второй руки не создаёт2H stop и не заставляет перейти на backup.

Выбранный полный срез разрешает optional shield по M53: opposite initial hands, weapon-first и restore_before_attack. При конфликте preferred backup hand с held shield действует weapon-first: на собственном ходу щит оставляется перед draw, возвращается только при доступной свободной здоровой руке по прежней Recover policy. Нельзя молча игнорировать preferred hand, держать два предмета в одной руке или создавать Reload action для Sling.

## Текущий контракт

Добавлен PcMeleeWeapon.SLING в PC_RANGED_WEAPONS:10→11. Число двуручных ranged остаётся7, bows3 не переименовываются в Sling. Отдельный признак free reload охватывает bows и Sling; permission Close определяется actual shared optimum, а не числом рук. Это явные небольшие typed helpers/группы, без общего языка правил.

PC JSON1/key ranged сохраняются. Sling принимает ровно3поля:

```json
"weapon": "sling",
"ranged": {
  "ballistic_skill": 3,
  "shooting": 4,
  "ammunition_supply_confirmed": true
}
```

Source Strength берётся из существующего pc.strength для Damage, BS/Shooting — для Test; WS/Agility не подменяют BS. I/Dexterity/Lore/kit/initially_loaded/reload_hand_policy/repeater_bonus_policy запрещены, а не заполняются фиктивными значениями. Initial grip=left/right; both запрещён. Для backup сохраняются Strength≥2/6существующих1H melee/preferred hand. Без backup Strength1 допустим; optional shield разрешён по выбранному полному варианту.

All-Close fresh Sling запрещён аналогично non-Close ranged; Short opening использует прежний restricted source: ranged party и simple authored numeric Melee Minions/Athletics, без новых NPC policies/каталога. Shield PC не расширяет допустимые NPC. Новых полей/версий/compatibility aliases/миграции236прежнихJSON M9–M67 нет; каталог59NPC/shared14 прежние.

## Необходимые изменения взаимодействий

- pc_weapon_damage различает shared FIXED и STRENGTH, не пытается строить DamageProfile(None). K1 preparation подтверждает actual Strength Damage ровно один раз, без Crossbow/ignore-armour Traits; существующие fixed ranged Damage прежние.
- _held_pc_ranged/own-turn unsupported/backup/source admission используют одну согласованную Close permission. Sling1H нельзя ошибочно приравнять к Pistol, а ranged1H нельзя массово объявить запрещёнными в Close.
- Backup при фактическом Close для Sling не зависит от empty state: FreeReloadWeaponState не имеет loaded/Exacting cycle. Сохранить источник/instance после перехода; active melee не превращается обратно в Shooting.
- Full shield-вариант учитывает новый hand-conflict случай: обе руки пригодны, но preferred backup hand занята щитом. Явный shield-release receipt должен предшествовать draw; прежняя цена Recover/drop/critical и запрет подбора травмированной12рукой сохраняются. Это применение выбранной weapon-first policy, а не новая оптимизация AI.
- Wound/grip/Recover/mandatory/Critical/Defenceless/terminal priorities и full source/proof guards сохраняются. Нет выдуманных Wounds ради Close stop.

## Адресная приёмка

1. Source/native/current schema: exact3keys, Strength/BS roles, left/right, Short-only, malformed/cached/foreign/partial facts до RNG, optional shield по выбранному варианту. Прежние10ranged shapes и семь2H loadouts неизменны.
2. Literal выстрелы при Strength1/3/5 и BS, не совпадающем со Strength: Damage=S+successes против полной Resilience, Short−1d/minimum pool exact1, ordinary cap, Drained/Fate. HIT/MISS сохраняют тот же FreeReloadWeaponState без cycle/Reload action.
3. Настоящий NPC approach→own-turn backup; отсутствие Close enemy не вызывает преждевременный draw. Другой Short target при Close enemy не разрешает Shoot. No-backup neutral stop без fake Wound; Recover/mandatory/terminal прерывают его в прежнем порядке.
4. Одна пригодная рука ещё позволяет Sling вне Close; при сближении можно достать допустимый backup. Full shield: opposite hands/protection, release перед draw при занятой preferred hand, retained Sling/free source, оружие первым при drops/потере руки/clutch stomach, только допустимый последующий shield Recover. Без ложного обращения к free_state.loaded и без Exacting-подавления shield pickup.
5. Full preparation/projection/replay/independent actors, source/JSON/services/count search и actual CLI.236старыхJSON/59NPC/14shared profiles сохраняются. Модификаторы Sling не переносятся на Sword;1H Pistol/Repeaters сохраняют Close permission/Reload/shield.

Проверять новые случаи и ближайшие зависимости Close/free reload/backup/shield/fixed ranged Damage; не повторять автоматически196/247/419tests/full/wheel/backend matrix. Shared K1 не меняется без найденного дефекта; проверка сборки/доставки не требуется при прежнем discovery. Подготовка этого proposal проверяет документацию и ссылки, игровые тесты не запускает.

## Согласование и результат

Пользователь поручил продолжить рекомендованный полный вариант Sling с optional shield и прежним melee backup. Новый public weapon/source scope,1H Close-trigger и hand-conflict путь приняты по [AGENTS.md](../../AGENTS.md). Backward compatibility не вводилась, shared K1 rules не менялись.

12новых deterministic native tests — OK1.181s после исправления literal scripts/ожиданий в новых тестах.5integration source/schema/services/count search — OK2.411s; после добавления Strength1/noBackup/withShield roundtrip затронутый тест отдельно OK0.242s. Production defect в приёмке не обнаружен; независимое runtime review проверило hand intent/Close/free state/shield/critical и не выявило дефектов.

198tests ближайших зависимостей единым составным адресным прогоном — OK22.486s: текущие source/enum/schema, shield/source/Recover/Wounds, Pistol+shield/backup,1H Repeaters/Close, bows/Crossbows/Handguns и PC Protection source. Это отдельные17новых и198dependency checks, не единый215/full project run. Actual CLI simulation/balance завершены; фактические команды и актуальная сверка — в [статусе](../project-status.md), пользовательские результаты — в [примерах](../examples/m68/README.md).

Прежние236JSON/59NPC/14shared profiles сохраняются. Full/wheel/backend matrix не повторялись: delivery/backend mechanism прежние, новые enum/source проверяются адресно. [Следующий шаг](../roadmap.md#после-m68).
