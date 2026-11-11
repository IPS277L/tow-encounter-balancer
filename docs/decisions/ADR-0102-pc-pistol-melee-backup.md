# ADR-0102: Pistol и melee backup при недоступном Reload

Дата: 2026-11-07. Статус: **принят пользователем; M60 реализована**. Выбран переход только при недоступном Reload, а не после первого shot при двух пригодных руках.

## Задача и источники

В native разборах M56–M58 живой PC после раны16/18 сохранял одну пригодную руку, но trial останавливался перед действительно нужным Reload. M54/M55 разрешают loaded shot одной рукой, однако Pistol-PC пока не может объявить carried melee backup. M20 уже реализует необратимый переход с непригодного2H primary на запасное1H.

Адресно сверены BOOK-PLAYER-GUIDE1.4: IV Equipment92–93 и Ranged Weapons94; V incidental actions116 и Recover118. Переиспользованы Armour97, Wounds190–191 и принятые M20/M53/M54/M55 решения. PG92 задаёт число carried weapons до Strength, не более одного2H; превышение вызывает Burdened, а не абсолютный запрет ношения. PG116 разрешает draw/swap в собственный ход; pickup рядом с enemy требует Recover. Число рук Reload остаётся принятой two_available_hands GM/scenario policy, не новой цитатой книги.

Новая граница — явная тактика сценария: книга разрешает запасное оружие, но не выбирает момент перехода на него. Новый public loadout/trigger согласован пользователем отдельно от книжных правил; он не выводится из отсутствующего второго hand fact.

## Принятая законченная граница

Разрешить один carried1H melee backup у Pistol-PC, с optional прежним shield. Поддержать все шесть нынешних1H Close weapons: Dagger, Staff, Axe, Sword, Warhammer, Morning Star. Нет второго Pistol/резервного2H/dual wield/обратного перехода на пистолет в этом бою. Обычный Pistol без backup и прежний2H→1H путь M20 сохраняются.

В первом fresh source требуется Strength≥2 для двух weapons без начального Burdened. Это ограничение среза, а не запрет книги носить больше оружия со штрафом. Shield сохраняет прежний отдельный loadout, не становится третьим weapon; условия разумного carried kit/trappings не меняются. Начальный Pistol загружен и held, backup carried, shield при наличии held противоположной рукой. Lore/kit/supplies и явные BS/Shooting/I/Dexterity/Melee/WS/Strength остаются полными исходными данными.

### Триггер: только empty Pistol + недоступный Reload

После mandatory Wound/Near Miss/body/expiry, на ближайшем собственном незанятом ходу:

1. Loaded Pistol сохраняет приоритет перед выбором backup, а необходимый Prone/weapon Recover по M54/M55 всё ещё предшествует выстрелу. Если нужен обычный regrip/pickup ради разрешённого one-hand shot, применяется прежний M54/M55 путь. Простая потеря предмета, неуспех Reload, рана12 или риск Critical не являются поводом отказаться от loaded shot/доступной перезарядки.
2. Пока обе руки пригодны для Reload, продолжать прежний Shoot→Reload3→Shoot цикл. Несколько безуспешных Reload Tests не переключают оружие.
3. Если Pistol **empty**, осталась **ровно одна пригодная рука** и backup объявлен, выполнить подтверждённый односторонний draw по M20 образцу до резервирования standard action. Триггер учитывает реальный weapon instance, а не только source weapon enum.
4. Если единственную пригодную руку занимает shield, сначала действовать по прежнему weapon-first release. Если empty Pistol ещё held — оставить его при draw; если уже dropped, не подбирать его и не создавать второй drop. Не нужен отдельный Recover ради пустого пистолета, который больше не будет применяться.
5. После draw обычный action остаётся доступен. Снимаемый Prone/другой необходимый standard Recover сохраняет приоритет над Attack. Как в M20, incidental draw происходит перед этим обычным Recover и может уже вызвать Critical; Recover его не отменяет. Иначе PC атакует выбранным backup через Melee.

Рука выбирается по принятому M20 правилу: пригодная здоровая прежде травмированной12, preferred_hand разрешает равенство. Clutch18 не снимается ради оружия. Draw выполняется только у живого не-Defenceless PC; при нуле пригодных рук или отсутствии backup сохраняются точные прежние stops/end phases. Terminal objective не вызывает draw ради неисполняемого продолжения.

Это заменяет конкретный pistol_reload_hands_unavailable boundary только при действительном доступном fallback. Нельзя подавить stop одним наличием policy и затем продолжить с неработающим grip, пропущенным draw или двумя занятыми руками. После уже исполненного slot прежний TurnEnd не обходится ранним переключением/stop.

## Публичный source и формат

Использовать существующий required nullable `party[].backup_weapon_policy`:

```json
"backup_weapon_policy": {
  "weapon": "sword",
  "preferred_hand": "right"
}
```

Для primary=Pistol non-null означает выбранную fixed fallback стратегию выше; для прежнего2H primary сохраняется M20 grip-unavailable trigger. Null сохраняет прежнее поведение. Новый trigger field/format/version/counters не нужен: реализован один выбранный режим Pistol backup.204прежнихJSON M9–M59 не мигрируются.

Source/schema разрешают сочетание Pistol+backup и Pistol+shield+backup, сохраняя Strength≥2/opposite initial hands/один backup и ordinary Attack/self Recover роль Pistol-PC. Собственные Help/ally Recover policies стрелка не расширяются. Правила допустимой NPC Protection проверяются для полного initial Pistol roster до RNG; backup не маскирует неправильный Shooting source.

## Состояние, receipt и active weapon

Переиспользовать source-bound `PcBackupWeaponDrawProof` и using_backup_weapon, расширив допустимый previous_hand от2H/None до фактического1H/2H/None. Replay связывает actor/previous grip/new hand с полным owner и одним draw receipt; отдельный bool не является доказательством. Held empty Pistol становится оставленным/dropped по receipt, уже dropped не меняет расположение повторно. Общий inventory/save-resume не вводится; возвращения к primary в срезе нет.

Pistol instance/loaded/progress/cycle/history сохраняются отдельно от active weapon. После draw оружие — backup, его item ID actor:backup-weapon; последующий drop/Recover относится только к backup, не подбирает оставленный Pistol. Нельзя скрыто дозарядить/сбросить цикл или превратить собственный primary profile в другой definition.

Actual Skill/Traits/Damage берутся из active weapon: Shooting/ignores armour/shot consumption до draw, Melee/WS/Strength/соответствующие Traits после. NPC close-shooting policy больше не применяется к melee backup attack: возвращается его обычная Defence/иная selected Protection. Stealth Thief сохраняет исходное разрешение. Outnumber/higher-ground/Prone, Protection Help и Glorious связываются с реальным Test. Наличие pistol profile в immutable source не должно оставлять ложный Shooting/Reload/stop после переключения.

Shield/recovery helpers также смотрят на active weapon: empty Pistol, оставленный после draw, больше не означает «идёт Reload». Одна оставшаяся рука занята backup, shield не восстанавливается без свободной пригодной руки. Unavailable shield не становится ground object. Механика M53/M55 не даёт третью руку и не снимает Wound/Net Conditions.

## Critical и ресурсы

Incidental draw не тратит standard slot, не делает Test/RNG и не входит в action count, но сохраняет Critical14/15 и фактически используемую травмированную12руку. Сам drop при15 разрешён, последующий draw/Attack/Recover имеет обычные последствия. Освобождение непригодного primary grip не объявляется отдельным использованием повреждённой руки, как в M20; clutch/Defenceless/Near Miss приоритеты прежние.

W10 next-Test не расходуется бесплатной перестановкой, а Fate/Grim/Glorious относятся к следующему реальному Test. Spent Reload actions, предыдущие Wounds/losses/Fate и reload progress не отменяются. После draw стандартные Attack/Recover и их фактические outcomes/costs продолжают прежние агрегаты, включая existing backup draw observations. Не представлять fallback как лечение/победу или неоплаченный дополнительный Attack.

## Альтернатива: переход после первого выстрела

Переходить на carried melee backup после первого фактического расхода заряда, даже когда Reload доступен двумя руками. Переключение также выполняется лишь на следующем собственном незанятом ходу, без дополнительной Attack после уже исполненного shot. Это другая тактика: она меняет обычный бой каждого такого PC, а не только unsupported continuation, требует проверки hand/shield выбора при двух пригодных руках и порядка возврата shield. Loaded initial shot остаётся первым, пропущенная/отклонённая preparation переключение не запускает.

Если выбран этот вариант, реализовать только его явный fixed trigger для Pistol backup и отразить в source/описании. Скрыто включать оба режима или «оптимальный выбор» не предлагается. Предпочтителен первый вариант: сохраняется согласованный Shoot/Reload цикл при доступных руках и снимается уже наблюдавшийся stop.

## Адресная приёмка

1. Typed/schema source Pistol+каждый из6backup, с shield/без, Strength/type/canonical hand guards; null/прежний2H путь сохранены. Missing/forged/alias sources отвергаются до RNG,204старыхJSON byte-identical.
2. Literal loaded one-hand shot до draw; empty2hands/partial Reload не переключается; empty1hand16/18 после всех реальных последствий переключается. Empty dropped Pistol не подбирается бесполезным Recover; loaded dropped Pistol восстанавливается по прежней стратегии.
3. Actual receipt/actor/previous grip/hand/instance/cycle, однократный необратимый draw; replay/stale/flag-only/ложный Shooting или Reload после fallback отвергаются. Ноль рук/Defenceless/terminal/исполненный slot не получают ложное продолжение.
4. Shield hand conflict/release, weapon-first, subsequent backup drops/pickup,12/14/15/16/18/20, Critical/end phase/Near Miss. Корректные3hand запреты и отсутствие снятия независимых Conditions.
5. Actual Melee WS/Strength/Damage/Traits и NPC Defence вместо Shooting override; Thief Stealth; incoming Protection/Help/Fate/W10/Grim/Glorious, без повторного Test/hidden refill/лишнего action.
6. Trials/summary/count search/current JSON1/offline schemas/full root/candidate echoes и полезный CLI-пример реального fallback. Один representative actual process с подтверждённым draw/сменой Skill, без старой полной backend matrix.

Функция проходит необходимые слои целиком, а не отдельную веху на helper/codec. По умолчанию новые и ближайшие M20/M53–M59/Wounds/Fate/Protection проверки; расширять checkpoint при конкретном влиянии на общий owner. Full project/wheel не требуются автоматически: package discovery/resources/dependencies/entry points не меняются.

## Согласование

Пользователь выбрал **«Только недоступный Reload»**: empty Pistol/одна пригодная рука, optional shield и6существующих1H weapons. Вариант после первого shot отклонён, скрытого второго trigger нет. Carry/draw правила не объявляются неоднозначными и уже выбранная two_available_hands не пересматривается. Новых вопросов для реализации M60 не осталось.

## Реализация и проверка

[Draw guard](../../src/towr/domain/pc_backup_weapon_models.py), active Skill/Attack/Reload в PC owner и canonical projection отделяют сохранённый Pistol от выбранного оружия. Held shield release проверяется раньше draw; собственный слот draw не расходует. Прямой JSON codec возвращает INVALID_INPUT для неполного backup object вместо KeyError. [Правило](../rules/equipment.md#pc-pistol-backup-m60), [пример](../examples/m60/README.md).

24новых native/JSON теста вошли в адресный checkpoint201tests — OK; один отдельный actual process test — OK. Native включает все6weapons, loaded priority/partial Reload,16/18/shield/drop/pickup, Critical12/14/15, W10/Fate/Glorious/Help, Protection/Thief и replay. Source/schema/services подтверждают full root/candidate echoes и malformed/type/source guards.204прежнихJSON сохранены побайтно,104request/result пары M9–M60 проверены текущими offline schemas. Фактические команды, ограничения и результаты — в [статусе](../project-status.md). Full project/wheel не запускались: delivery mechanism не менялся.
