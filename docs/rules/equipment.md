# Equipment, Coin и Assets

## PC Hochland, Aim и Fate Second Action (M70)

<a id="pc-hochland-m70"></a>

RULE-EQUIPMENT-004/007, Aim/Second Action: BOOK-PLAYER-GUIDE1.4 III70, IV95, V111/116; Lucky78, Shaking Grip190. [ADR-0112](../decisions/ADR-0112-pc-hochland-aim-and-fate-second-action.md), [CLI](../examples/m70/README.md).

Hochland Long Rifle:2H, optimum Medium–Extreme, Damage6/ignores armour, mandatory Aim, Wounds Table+1d, Reload4 после HIT/MISS. В текущем Short opening действует−1d; любой Close enemy запрещает Shoot. Wounds Table bonus не становится Damage и не применяется к numeric Minion injury policy; соответствующий shared K1 PLAYER/Champion путь сохраняется. Source содержит10required ranged fields:9ordinary firearm facts плюс Awareness, связанную с Initiative. Repeater policy/shield запрещены, initial grip=BOTH.

PC выполняет настоящий standard Aim/Awareness Test по первой живой цели.0success — выполненный Aim с нулевым бонусом. Optional Awareness Glorious в этом срезе отклоняется; Shooting Glorious прежний. Действующий CANNOT_AIM от Shaking Grip8 блокирует новый Aim до RNG, даже после обычного Recover. Hand/mandatory/Critical/Defenceless/terminal priorities сохраняются.

При явной per-participant aim_second_action_policy={minimum_remaining_session_spends:N} и configured Fate после Aim оплачивается настоящий Second Action/slot2 для Shoot по той же цели. Резерв проверяется после фактической стоимости: Lucky free0 либо session1.0Aim не запрещает spend; нет скрытого success threshold. Shoot Glorious может тратиться только после оплаты Second Action по собственным критериям/остатку ресурса. Lucky разрешён только Hoc-source и сохраняет бесплатную первую трату также для другого выбранного Glorious, если Second Action не использован; остальные источники не получают новый Talent автоматически.

Без policy/funding выше резерва PC завершает обычный Aim. После NPC approach на своём ходу выбирает прежний backup, а не free Shoot. Aim одноразовый: actual next own ranged Attack той же цели применяет его, другое собственное действие (Recover/melee/другой Aim) теряет его; incoming Protection/end phase не являются таким action. Actual action receipt и consumed follow-up записываются до следующего перехода/terminal. При доступном выбранном Second Action преждевременный TurnEnd отвергается, даже с корректным общим clock receipt. Critical end phase завершается после фактически выполненных действий.

Aim bonus проходит обычный cap/Drained и восстанавливается в PC/K1 bridge ровно один раз. Ресурс, actor/session/round/slot/target и source/result сохраняются полностью, replay запрещён. После Shoot retained empty4 отделён от active Sword; полный fresh Shoot→Reload4→новый Aim→Shoot в этом Short-срезе не заявляется. Все13PG ranged profiles теперь допущены в ограниченном PC исполнении, без расширения NPC/дистанций.

## PC Blunderbuss и nearby Staggered (M69)

<a id="pc-blunderbuss-m69"></a>

RULE-EQUIPMENT-004/007 и RULE-EFFECT-006, BOOK-PLAYER-GUIDE1.4 IV94–95, прежние Blackpowder/Exacting/Conditions. [ADR-0111](../decisions/ADR-0111-pc-blunderbuss-cluster-and-nearby-stagger.md), [CLI](../examples/m69/README.md).

Blunderbuss —2H, optimum Short/maximum Medium, Damage4 с обычной бронёй, +2d Shooting на Short, каждый HIT/MISS открывает Reload3. Обычный cap действует, Drained запрещает положительные dice, но не расход заряда или Trait при HIT. Source —9required ranged fields как ordinary Handgun, true Blackpowder Lore/kit/ammunition/loaded, явные BS/Shooting/I/Dex и two_available_hands. Repeater policy запрещена, BOTH/no shield, прежний carried1H backup.

При HIT другие существа в Close от основной цели получают Staggered, даже если основной цели не нанесена Wound. Primary не получает повторного secondary impact. MISS волны не создаёт. Сначала завершаются primary consequences/GM acknowledgement, затем ordered secondary impacts; поражение primary или последних NPC не позволяет потерять completion. Второй Staggered использует прежний SUFFER_WOUND, у текущих numeric Minions W1 подтверждается caller/GM disposition. Это не новые Attack/Protection Tests или actions.

Текущая сцена подтверждает initial NPC cluster через scenario.blunderbuss_nearby: exact initial_npc_clustered_confirmed=true и target_priority всех NPC ровно один раз. Поле требуется iff есть Blunderbuss, без него отсутствует. Из одной Zone взаимный Close не выводится. На HIT PcAttackProof.nearby_snapshot фиксирует full cluster source и ordered request со всеми живыми secondary NPC, исключая primary и defeated. Политика/порядок/target states после HIT не подменяются; отдельный nearby receipt содержит все результаты и точные GM acknowledgements. Пропуск/replay/foreign source/добавление или перестановка целей отвергаются. Generation фильтрует порядок по текущему составу.

При разрешённом выстреле все PC остаются на Short от NPC; любой живой подошедший NPC запрещает Shoot по PG94. Поэтому в этом срезе secondary — NPC исходной группы, а PC не входят в волну по actual scene premises. Это не общее исключение friendly fire; смешанные Close-группы не добавлены. После полной волны действует прежний NPC approach→own-turn backup, retained empty cycle3 сохраняется отдельно от melee. Source ограничен simple authored numeric Minions без Abilities; shared K1 resolver прежний.

## PC Sling и Close restriction независимо от рук (M68)

<a id="pc-sling-m68"></a>

RULE-EQUIPMENT-004/007, BOOK-PLAYER-GUIDE1.4 IV92/94–95; прежние Shooting/Conditions/Fate/руки. [ADR-0110](../decisions/ADR-0110-pc-sling-free-reload-and-close-backup.md), [CLI](../examples/m68/README.md), [Short opening](combat.md#pc-short-opening-m65).

Sling —1H, Damage=Strength, optimum только Medium, maximum Long, обычная броня. Reload бесплатен в составе Attack; нет Exacting cycle/loaded/Reload action. На исходном Short действует−1d с обычным minimum pool exact1. BS/Shooting задают Test, Strength — Damage; общие cap/Drained/Fate прежние. Нет Blackpowder prerequisite, Repeater bonus, Crossbow armour Trait или ignores armour.

Sling source содержит ровно BS/Shooting/ammunition_supply_confirmed=true. I/Dexterity/initially_loaded/reload_hand_policy/Lore/kit/repeater_bonus_policy запрещены. Initial grip=left/right, optional shield на другой руке по M53. Backup — прежние6существующих1H melee/preferred hand/Strength≥2; без backup Strength1 допустим.

По PG94 любой Close enemy запрещает ranged, если Close не входит в actual optimum, независимо от числа рук. В текущем Short opening NPC подходят, затем на собственном ходу PC достаёт объявленный melee backup. Наличие другой Short-цели запрет не снимает; при отсутствии Close enemy сама потеря второй руки не заставляет менять пригодный Sling. All-Close fresh source Sling запрещён, прежние Close-capable1H Pistol/Repeaters сохраняют разрешение.

Для draw выбирается пригодная рука backup по его policy без сохранения руки primary как скрытого приоритета. Если preferred backup hand занята held shield, сначала проходит weapon-first shield release, затем draw; щит возвращается допустимым standard Recover в свободную здоровую руку по прежней restore_before_attack policy. Free reload не удерживает вторую руку для Exacting. Incidental hand use/ранения/mandatory/Critical/Defenceless/terminal priorities прежние. Free state/instance primary сохраняется отдельно от active melee. Без backup — actual PcRangedCloseUnsupported/ranged_close_enemy, без выдуманной Wound; уже необходимый Recover имеет прежний приоритет.

M68 сохраняет текущую restricted Short-сцену: ranged party против simple authored numeric Melee Minions/Athletics в одной Zone. Medium opening, другие Zone, movement/kiting, NPC ожидание/новые policies, другие профили не добавляются.

## PC Handgun и Repeater Handgun (M67)

<a id="pc-handguns-m67"></a>

RULE-EQUIPMENT-004/007, BOOK-PLAYER-GUIDE1.4 IV94–95/99, III82; V107/110/123. [ADR-0109](../decisions/ADR-0109-pc-handguns-opening-volley.md), [CLI](../examples/m67/README.md), [Short opening](combat.md#pc-short-opening-m65).

Handgun:2H, optimum Medium–Long, Damage5/ignores armour, каждый HIT/MISS открывает Reload3. На исходном Short применяется −1d вне optimum с обычным minimum pool. Repeater Handgun:2H, optimum Short–Long, Damage5/ignores armour, optional +3d к одному Shooting Test открывает Reload5. Явный when_available выбирает бонус до initial roll/Fate, если PC не Drained; never/Drained оставляет ordinary loaded shot без нового cycle. Обычный cap не отменяет цену выбранного бонуса. Drained сохраняет отрицательный range modifier Handgun. Crossbow armour Damage Trait этим firearms не принадлежит.

Оба используют текущий pc.ranged: явные BS/Shooting/I/Dex, true Blackpowder Lore/kit/ammunition/initially_loaded и two_available_hands. Handgun запрещает repeater_bonus_policy, Repeater требует when_available/never. Lore здесь prerequisite, автоматический бонус специалисту не добавляется. Initial grip=BOTH, shield запрещён. Две руки Reload — ранее принятая scenario policy.

В нынешнем публичном срезе NPC подходят после залпа; при любом Close enemy на своём ходу PC переходит на declared1H backup. Retained loaded/empty3/5 primary сохраняется, active melee не наследует ignores armour/bonus. Без доступного backup действуют actual grip stop либо общий PcRangedCloseUnsupported/ranged_close_enemy без выдуманной Wound. Старые bow/Crossbow stops используют то же нейтральное имя. Ordinary Recover/mandatory/Defenceless/terminal priorities прежние. Полный повторный Shoot→Reload→Shoot в fresh encounter не заявляется; focused PC→K1 Reload проверяет реальный spent state отдельно.

## PC Crossbow и Repeater Crossbow (M66)

<a id="pc-crossbows-m66"></a>

RULE-EQUIPMENT-004, BOOK-PLAYER-GUIDE1.4 IV94–95; прежние Shooting/Dexterity/Drained/Fate/руки. [ADR-0108](../decisions/ADR-0108-pc-crossbows-opening-volley-and-reload-state.md), [CLI](../examples/m66/README.md), [Short opening](combat.md#pc-short-opening-m65).

| Weapon | Hands / optimum | Damage | Заряд |
|---|---|---|---|
| Crossbow | 2H / Short–Long | 4, +1 по armoured target | HIT/MISS открывает Reload2 |
| Repeater Crossbow | 2H / Short–Medium | 4 | optional+1d → Reload3 |

Repeater Crossbow не получает ordinary Crossbow armour Damage Trait и не игнорирует броню. Оба используют полную Resilience. Crossbow Trait смотрит на full is_armoured, не просто положительный bonus; явный armoured=false его запрещает. Drained запрещает bonus dice, но оставляет Damage Trait обычного Crossbow. Repeater when_available выбирает +1d до initial roll/Fate, never/Drained не открывают новый cycle; cap/instance/cycle/history правила M64 сохранены.

Оба2H initially loaded, требуют явных BS/Shooting/I/Dexterity/ammunition/two_available_hands. Только Repeater требует repeater_bonus_policy, ordinary Crossbow его запрещает; обоим запрещены Blackpowder Lore/kit facts. Free-reload bows остаются отдельной группой3оружий. Shield запрещён, initial grip=BOTH; carried6supported1H backup требует Strength≥2.

В текущем M65 Short opening достигается первый volley и melee continuation. NPC подходят на своём ходу, после чего Crossbow-PC выбирает backup при любом Close enemy, включая loaded Repeater never. Owned empty cycle2/3 либо loaded/no-cycle state сохраняется после draw; оно не вызывает Shoot/Reload у active Sword. При недоступном2H хвате применяется доступный1H backup, иначе точный own-turn stop. Recover/mandatory Wound/critical/Defenceless/terminal priorities прежние. В прежней all-Close сцене оба Crossbow запрещены.

Сам Close Shoot guard не становится запретом законного Dexterity Reload. Shared K1 и PC builder связывают required successes2/3 с настоящим spent instance; focused проверка alternative Reload в подходящем собственном K1 контексте не является fresh public Shoot→Reload→Shoot trial. Новая NPC wait/approach policy не добавлена.

Current PC JSON1/key ranged прежние. Optional authored NPC definition.resilience.armoured теперь принимает exact boolean: True/False сохраняются, отсутствие оставляет прежнее None/вывод из bonus. Fresh current_resilience должен полностью совпадать с definition, включая metadata. Canonical Net требует прежний true, другие canonical book profiles по-прежнему не принимают дополнительный wire flag. Это обеспечивает полноту Crossbow source при JSON roundtrip; числовые NPC и остальные families не получают новой Ability.

## PC bows, Short opening и melee backup (M65)

<a id="pc-bows-m65"></a>

RULE-EQUIPMENT-004, BOOK-PLAYER-GUIDE1.4 III68, IV94–95; Conditions123 и прежние hand/Wound rules. [Принятый ADR-0107](../decisions/ADR-0107-pc-bows-short-opening-and-melee-backup.md), [бой с подходом NPC](combat.md#pc-short-opening-m65), [CLI-примеры](../examples/m65/README.md).

| Weapon | Hands / optimum | Damage | Trait |
|---|---|---|---|
| Shortbow | 2H / Short–Medium | 3 | +1d Shooting по Short |
| Warbow | 2H / Medium–Long | 3 | по Short −1d вне optimum |
| Longbow | 2H / Medium–Long | 4 | по Short −1d вне optimum |

Зарядка всех трёх бесплатна в составе выстрела; отдельного Reload action/progress/cycle нет. Ammunition supply подтверждается явно. Броня и shield входят в обычную Resilience; Strength не меняет fixed bow Damage. Shortbow +1d подчиняется cap/Drained, штраф Warbow/Longbow сохраняется. Ни один лук не стреляет при любом Close enemy, даже если выбранная цель ещё Short. Все три запрещены в прежнем all-Close source.

В текущем PC JSON1 `pc.ranged` для bows содержит только ballistic_skill/shooting/ammunition_supply_confirmed=true. Initiative/Dexterity/initially_loaded/reload_hand_policy/repeater_bonus_policy/Blackpowder facts запрещены, а не подставляются null/false. Initial grip=BOTH, shield запрещён. Старые три1H ranged source shapes и NPC pistol не меняются. Native owned state — shared FreeReloadWeaponState; shot proof обязателен и при неизменившемся state.

В выбранной M65 тактике на собственном незанятом ходу, после mandatory Wound continuations, bow-PC использует объявленный1H backup при любом Close enemy или невозможном2H хвате. Draw односторонний/incidental, Strength≥2, preferred hand и6старых1H weapons сохраняются. Drop старого grip и draw учитывают actual hand/critical consequences. Retained bow state не превращает backup Attack в Shooting/Reload. Без backup остановка typed unsupported происходит на реальной границе недоступного Shoot; если сначала выбран обычный Recover (например, после выпадения лука), он исполняется. Dead/Defenceless/terminal и обязательные последствия имеют прежний приоритет; wound/grip stop не создаёт фиктивных Close-причин.

Pistol/Repeater1H могут участвовать в Short opening; Close для них разрешён и сам по себе не включает backup. Их прежние bonus/Reload/shield policies действуют. Старый2H-melee fallback не расширяется. Crossbow/Aim/kiting/автоматический возврат к луку не добавлены.

## PC Repeaters и единый ranged source (M64)

<a id="pc-repeaters-m64"></a>

`RULE-EQUIPMENT-004`/`RULE-EQUIPMENT-007`, BOOK-PLAYER-GUIDE1.4 III68/70/82/88, IV94–95/98–99, V107/110/123. [Принятый контракт](../decisions/ADR-0106-pc-repeaters-and-generic-ranged-profile.md), [CLI-примеры](../examples/m64/README.md).

В текущей Close-сцене PC доступны Repeater Handbow (1H, Damage4, обычная броня) и Repeater Pistol (1H, Damage5, ignores armour), optimum Close–Short. Явная policy `when_available` выбирает обычные +1d/+2d Shooting до initial roll/Fate, если PC не Drained; `never` их не выбирает. Бонус подчиняется обычному cap. Даже при насыщенном cap выбранный бонус требует Reload; скрытой оптимизации тактики нет.

Выстрел с бонусом, HIT или MISS, открывает ровно один собственный Reload3 cycle. Без бонуса weapon остаётся loaded без нового cycle, но новый Test/action/preparation/receipt всё равно обязателен. Drained → обычный shot без modifier/flag/cycle. Уже начатый пустой cycle надо закончить и при Drained. Partial/failed/overshoot Reload, действие Dexterity и следующий отдельный Shoot переиспользуют K1 Exacting. Обычный Pistol по-прежнему требует Reload после каждого выстрела.

Один актуальный PC JSON1: `party[].pc.ranged` вместо прежнего PC `pistol`, для трёх ranged weapons. Общие BS/Shooting/I/Dexterity, initially loaded, ammunition supply и `two_available_hands` задаются явно. Firearms требуют true Blackpowder Lore/kit; Handbow запрещает эти поля, Engineering Lore/Kit для обычного Reload не требуются. `repeater_bonus_policy` обязателен только для Repeaters. Non-ranged PC запрещает ranged object. Native API — PcRangedProfile/State.ranged/PcRangedShotProof/PcRangedReloadProof; старых aliases нет. NPC `enemies[].pistol` не меняется.

Прежние shield/backup политики распространяются на оба Repeaters: shield release только перед необходимым доступным Reload, shield Recover после completion. Loaded one-hand shot не включает backup; empty и одна пригодная рука — односторонний draw существующего1H backup либо unsupported. Retained ranged state после draw не запускает Shoot/Reload. M63 Melee opposition не активирует бонус и не расходует заряд. Shooting/Reload учитывают прежние Critical/Wounds/Fate; Handbow сохраняет полную armour/shield Resilience, pistols используют Toughness. PC собственной Shooting Help роли нет.

Смена PC key выполнена в36из220прежнихJSON точным semantic transform, остальные184 сохранены побайтно; числовые результаты/seed/NPC source не пересчитывались. Разделы M54/M55/M60 ниже сохраняют историю внедрения; текущие имена source/runtime определены здесь. Raw snapshots не save/resume API.

## PC Pistol и carried melee backup (M60)

<a id="pc-pistol-backup-m60"></a>

`RULE-EQUIPMENT-002`/`RULE-EQUIPMENT-003`/`RULE-EQUIPMENT-004`, BOOK-PLAYER-GUIDE1.4 IV92–94; incidental actions116, Recover118 и Wounds190–191. Статус implemented. [Принятый контракт](../decisions/ADR-0102-pc-pistol-melee-backup.md), [current JSON1/CLI](../examples/m60/README.md). Это расширение M20/M54/M55; их первоначальные запреты Pistol backup ниже описывают прежние границы.

Существующий `party[].backup_weapon_policy` допускает Pistol + один carried Dagger/Staff/Axe/Sword/Warhammer/Morning Star, с optional shield в противоположной начальной руке. В fresh source требуется Strength≥2 для двух weapons без initial Burdened. PG92 разрешает overcarry со штрафом; это граница входа, а не общий запрет книги. Начальный Pistol загружен, Lore/kit/supplies и ordinary Attack/self Recover роль сохраняются. NPC roster проверяется для initial Shooting до RNG; backup не разрешает незаконную начальную Protection.

Пользователь выбрал переход **только при пустом Pistol и недоступном Reload из-за одной пригодной руки**. Loaded one-hand shot и необходимый ему Recover предшествуют fallback; две пригодные руки, частичный/неуспешный Reload и риск Critical не запускают draw. После mandatory последствий, на собственном unreserved turn сначала освобождается нужная held shield-рука, затем выполняется единственный incidental draw. Пустой dropped Pistol не подбирается; held оставляется с подтверждённым previous_hand. Здоровая рука приоритетнее травмированной12; clutch18 сохраняется. Ноль рук, Defenceless, terminal result или уже исполненный slot не дают ложного draw.

Draw не занимает action/Test/RNG, но сохраняет Critical12/14/15. Далее обычный Recover/Attack использует actual backup instance и его Melee/WS/Strength/Damage/Traits; NPC получает обычную Protection вместо Close Shooting override. Thief Stealth остаётся применимым. Pistol instance/loaded/progress/cycle/history сохраняются отдельно; повторного Reload/Shoot/возврата к primary нет. Pickup после drop относится к backup, не к оставленному Pistol. Shield follows прежний weapon-first, без третьей руки или снятия независимых Conditions.

Fate/W10/Glorious относятся к настоящему Test; W10 не тратится incidental draw. Другой PC может Help Melee только после фактического переключения получателя, без предсказания будущего draw; собственные Help/ally Recover роли Pistol-PC не расширяются. Канонический owner проверяет actor/предыдущий хват/новую руку/однократность и полный replay. Прежние2H→1H и null paths сохранены, новых полей/версии/метрик нет;204старыхJSON не мигрируются.

## PC Pistol со щитом (M55)

<a id="pc-pistol-shield-m55"></a>

`RULE-EQUIPMENT-004`/`RULE-EQUIPMENT-006` (BOOK-PLAYER-GUIDE1.4, IV94–95/97), Actions116/Recover118 и Wounds190–191. Статус implemented. [Принятый контракт](../decisions/ADR-0100-pc-pistol-shield-reload-priority.md), [JSON/CLI](../examples/m55/README.md). M55 расширяет первоначальную границу M54 на сочетание одного Pistol и одного shield, сохраняя two_available_hands и остальные ограничения стрелка.

Используется существующий participant shield object, initially held в противоположной Pistol руке, weapon_first/restore_before_attack. Новых полей/версии/предметов по умолчанию нет. Щит даёт+1Resilience и разрешает Defence против Net лишь пока реально held и пригоден; Sword Trait у Pistol отсутствует. После drop используется Athletics против Net, по Brawn остаётся Endurance. Предыдущая атака не пересчитывается задним числом.

Принятая тактика: необходимый weapon pickup/снимаемый Prone Recover → release щита непосредственно перед доступным Reload → Reload actions до готовности → отдельный standard Recover щита → следующий Shoot. Пока Pistol пуст, щит не подбирается даже дополнительным object interaction другого Recover. Это сохраняет вторую руку свободной и исключает Recover/release цикл. Если выпали оба предмета, первым возвращается weapon; если он пуст, до shield pickup сначала завершается Reload. Если он loaded, действует прежний порядок weapon Recover → shield Recover → Shoot.

Release не занимает нового slot, но сохраняет Critical14/12; сам drop разрешён при15, последующие Reload/Recover/swap имеют свои последствия. Reload completion не поднимает щит и не стреляет; dropped shield остаётся отдельным предметом в owner, его наличие не блокирует Reload. W12 допускает использование руки для Reload с Critical, но shield pickup травмированной рукой по прежней тактике запрещён. Недоступный16/20 shield не превращается в ground object;18 сохраняет clutch/занятость рук. При невозможном Reload бесполезного release нет, loaded one-hand shot после необходимого weapon-first продолжения разрешён. Terminal objective не требует возврата щита или перезарядки.

184прежнихJSON M9–M54 и каталог57 сохранены. Melee/shield и Pistol без щита сохраняют свои policies. Backup/второй firearm/новые Help роли/Aim/Rapid Reload/универсальный inventory не добавлены. Hand/source/replay guards и costs обычных действий остаются прежними.

## PC Pistol и Exacting Reload (M54)

<a id="pc-pistol-reload-m54"></a>

`RULE-EQUIPMENT-004`/`RULE-EQUIPMENT-007`, BOOK-PLAYER-GUIDE1.4, гл.III Shooting68/Dexterity70/Lore82; IV Weapons94–95/Tools98–99; V Exacting110/Actions116–118/Failed Attacks119/Conditions123; Wounds190–191. Статус implemented в ограниченном Close-сценарии. [Принятый контракт](../decisions/ADR-0099-pc-pistol-and-exacting-reload.md), [source/CLI](../examples/m54/README.md).

Один initially loaded Pistol:1H, Damage5, ignores armour; Close firing разрешён. Shooting использует Ballistic Skill, Reload — Dexterity на Initiative. Blackpowder Lore, полный Blackpowder Kit и достаточное снабжение боеприпасами подтверждаются в fresh source. Kit без снабжения не создаёт запас. Числа Skills передаются явно; WS/Agility их не заменяют. Pistol-PC без shield/backup и собственных Help/ally-Recover policies; mixed party с прежними melee/shield PCs допустима.

После обычного необходимого self Recover PC стреляет заряженным оружием, иначе выполняет Reload. Одна Dexterity Test стоит обычное действие Improvise/Skill; требуется3накопленныхsuccesses. Неуспех сохраняет прошлый progress, overshoot завершает Reload, новый выстрел доступен лишь следующим действием. HIT и MISS расходуют один заряд и начинают новый цикл конкретного weapon instance. Drop/regrip/Recover и смена раунда не сбрасывают progress и не заряжают оружие. Rapid Reload/Aim/новый ranged Help не добавлены.

**Принятая GM/scenario policy two_available_hands:** одна пригодная рука держит Pistol, вторая свободна для зарядки. Книга не определяет число рук Reload; эта конкретизация передаётся явно и не объявляется RAW. Рука12 допустима с Critical; недоступная16/20 и прижимающая живот18 не подходят. Loaded shot одной рукой остаётся возможен. Невозможный Reload останавливает trial как UNSUPPORTED_PATH лишь на собственном ещё не занятом ходу, когда после обязательных последствий и восстановления действительно требуется Reload, до Test/действия. Grip/pickup имеет собственную точную границу. Конечный objective не требует дозаряжания. Stop сохраняет wound/weapon/cycle source и исполненные costs/losses, а не превращает ограничение в поражение.

Выстрел остаётся Shooting: нет Melee outnumber/higher-ground или Melee Help; по Prone–1d. Close miss даёт Staggered только при его отсутствии. Ignores-armour использует текущую Toughness цели. NPC сохраняет выбранную lawful Protection: Athletics либо Defence с настоящим shield; возможная книжная Melee opposition не выбирается автоматически. Full source/template с Defence без shield, Stealth или отсутствующим fallback отклоняется до RNG. Pistol в руке разрешает обычную Defence против Melee без Sword Trait; по Net у этого PC Athletics, по Brawn Endurance.

Actual Shooting/Dexterity Test учитывает Drained/Blinded/W10 и настроенный Glorious ровно один раз; Protection Help привязывается к реальному входящему Test. Раны4/8/12 роняют фактический предмет; W12 при использовании раненой руки, W14/15 при Shoot/Reload вызывают существующий Critical/end phase. Near Miss отменяет соответствующие body facts раньше их применения. Лечение, свободная смена оружия и новые aggregate counters не добавлены.

В исходном M54 использовался PC `pistol`; M64 заменил его текущим `party[].pc.ranged` для всех трёх ranged weapons (см. выше). Null/частичный объект не допускается; Pistol требует все подтверждения true. Wire version остаётся PC JSON1. Runtime journal связывает preparation, Test, weapon instance/cycle и action receipt; raw snapshots не являются save/resume API.

## PC со щитом (M53)

<a id="pc-shield-m53"></a>

`RULE-EQUIPMENT-006`, BOOK-PLAYER-GUIDE1.4, гл.IV Armour97; Defence68, weapons92–93, Actions116/Recover118, Wounds190–191. Статус implemented. [Принятый контракт](../decisions/ADR-0098-pc-shield-and-hand-equipment.md), [factory/JSON/CLI](../examples/m53/README.md).

В нынешнем fixed Close owner PC может начать с одним shield в руке, противоположной одноручному Dagger/Staff/Axe/Sword/Warhammer/Morning Star. Источник явно задаёт initial hand, weapon_first и restore_before_attack. Нет2H/backup shield/dual wield/bash. Authored armour_bonus обозначает прежнюю броню без щита; рабочий shield отдельно даёт+1Resilience и делает цель armoured. Ignores-armour использует Toughness. Damage первой атаки сохраняет её исходную Resilience; последующий drop меняет только следующие подготовки.

Рабочий shield разрешает Defence против Throwing/Shooting, но сам не даёт куба. Действующий wielded Sword добавляет+1d Defence при not-Staggered и против Throwing тоже; dropped/unusable Sword его не даёт. PC с shield, но без оружия, сохраняет Defence без Sword Trait. По Melee выбирается Defence при рабочем weapon или shield, иначе Athletics; по Net — Defence только с shield, иначе Athletics; по Brawn/Trample — Endurance. Defenceless/Unaware не Opposes. Drained/Fate/Help используют фактический Skill/Test.

Shield имеет held/dropped/unavailable состояние и настоящую руку.4failedEndurance/8/12 роняют предмет выбранной random hand; пустая рука не роняет weapon другой руки.16/20 делают shield соответствующей руки unavailable: защиты нет, ground drop/бесплатный pickup не выдумывается.18 drop/clutch и последующая relocation учитывают shield в занимаемой руке. Near Miss не создаёт отменённых body/drop consequences. На травмированную12руку shield не поднимается, поэтому passive-use Critical не назначается молча.

Если здоровая shield-рука нужна weapon, на своём unreserved turn PC сначала подтверждённо оставляет shield, затем меняет руку или подбирает weapon. После чужой атаки внеочередной swap не разрешён. Free release — действие для14 Critical;15 явно позволяет сам drop, но дальнейший swap/Recover вызывает его Critical. Actual arm/clutch restrictions сохраняются.

Dropped shield возвращается настоящим standard Recover в Close enemy, когда есть свободная здоровая рука. Это самостоятельная причина self Recover, без бесполезного цикла при недоступной руке. При выпадении обоих предметов первым возвращается weapon; один Recover имеет один object interaction. Прежние стандартные Condition benefits и self/ally recipients сохраняются; помощь союзника не подбирает предмет получателя автоматически. Независимые Net/Wound причины не исчезают. Unavailable shield не возвращается как dropped.

Current PC JSON1 допускает optional closed participant shield object только при выбранном loadout; отсутствие прежнего поля не создаёт предмета и не меняет176JSON. Полный current prefix связывает drop/body/release/pickup/руку/снаряжение; stale/replay/typed alias и возврат защиты без actual receipt отвергаются при admission. Новых версий/агрегатных counters нет; Recover учитывается обычным действием, free drop/swap — без нового slot.

Источник: `BOOK-PLAYER-GUIDE`, версия 1.4, глава Equipment, страницы 90–105. Статус области: `draft`; числовые профили проверены, существует только минимальный carried-inventory snapshot для Retreat, а полный inventory/economy/action model отсутствует. Боевые Traits реализованы лишь точечно.

## RULE-EQUIPMENT-001 — Coin и покупки

Персонаж начинает с тремя Coin своего Status. Coin — абстрактное число существенных покупок, а не точный подсчёт монет:

- покупка своего tier расходует 1 Coin;
- покупки более низкого tier обычно бесплатны, но GM может объединить множество мелких покупок в одну более высокую expense;
- покупка более высокого tier недоступна без дополнительного Coin, обмена или успешного barter;
- в каждый Downtime Coin сбрасывается к 3: недостаток восполняется Career, избыток теряется, если не инвестирован Endeavour.

Barter — Opposed Charm против Willpower. Он либо заменяет Coin при покупке своего tier, либо снижает expense на один tier; Brass не может таким способом купить Gold. Успех всегда несёт один скрытый GM-chosen cost: низкое качество, stolen goods или будущая услуга. Провал не запрещает обычную покупку, если она доступна.

Источник: страницы 90–91.

## RULE-EQUIPMENT-002 — перенос и владение

Персонаж может носить outfit и armour, число weapons до Strength (не более одного two-handed), а прочие trappings — в согласованном с GM разумном количестве. Превышение либо особо тяжёлый/громоздкий груз накладывает Burdened.

В руках помещается одно `2H` melee weapon либо по одному `1H` на каждую руку. При dual wield Traits обоих weapons могут применяться к одной Attack Test, а бонусы к одной Test складываются.

Источник: страница 92. Общая carried-weapon вместимость и число занятых рук — разные ограничения.

Полный inventory/carry-capacity reducer ещё не реализован. Первый минимальный immutable контракт `CarriedInventoryState` хранит только владельца и stable ordered `TrappingSnapshot`; каждая запись содержит instance/definition identity и внешнюю оценку `is_valuable`. Эта оценка не выводится автоматически из Cost tier: она нужна узкому materiel-price consumer Retreat страницы 120. Тот же snapshot использует специализированный Run For Your Lives `Robbed` consumer: он требует explicit GM-selection как минимум одного carried item для каждого PC и удаляет все выбранные записи одним ordered batch. Оба consumer возвращают dropped facts, но пока не размещают предметы в Zone, не вычисляют «самый тяжёлый» trapping и не обслуживают equip/hand/capacity rules.

## RULE-EQUIPMENT-003 — melee weapon profiles

Damage `S` использует Strength; `S±N` модифицирует её. Таблица воспроизводит нормативные поля страницы 93.

| Weapon | Cost | Range | Damage | Hands | Traits |
|---|---|---|---|---|---|
| Unarmed | n/a | Close | n/a | n/a | Brawn; success даёт Staggered вместо Damage |
| Knuckledusters | Brass | Close | S-1 | 1H | `+1d` Stealth conceal; Brawn |
| Dagger | Brass | Close | S-1 | 1H | `+1d` Stealth conceal |
| Staff | Brass | Close | S | 1H | `+1d` Athletics при crossing Difficult Terrain |
| Foot Spear | Brass | Short | S | 1H | `+1d` Defence против Charge; `+1 Damage` в 2H |
| Cavalry Spear | Brass | Short | S | 1H | `+1d` Melee на mounted Charge |
| Axe | Brass | Close | S | 1H | `+1 Damage` против armoured |
| Pickaxe | Brass | Close | S+1 | 2H | `+1d` Toil при harvesting resources |
| Sword | Silver | Close | S | 1H | `+1d` Defence, если не Staggered |
| Warhammer | Silver | Close | S | 1H | `+1d` Melee против Staggered |
| Morning Star | Silver | Close | S+1 | 1H | `-1d` Melee при Staggered; нельзя dual wield |
| Polearm | Silver | Short | S | 1H | `+2 Damage` в 2H |
| Flail | Silver | Close | S+3 | 2H | `-2d` Melee при Staggered |
| Billhook | Silver | Close | S+2 | 2H | `+1d` Melee против mounted |
| Halberd | Silver | Close | S+2 | 2H | `+1 Damage` против armoured |
| Glaive | Silver | Close | S+2 | 2H | `+1d` Defence, если не Staggered |
| Greataxe | Silver | Close | S+3 | 2H | `-1d` Melee; `+1 Damage` против armoured |
| Greatsword | Gold | Close | S+3 | 2H | `-1d` Melee; `+1 to Defence` если не Staggered |
| Greathammer | Gold | Close | S+3 | 2H | `-1d` Melee; `+1d` Melee против Staggered |
| Lance | Gold | Close | S+1 | 1H | `+1d` Melee и `+1 Damage` на mounted Charge; нельзя dual wield |

`Greatsword` намеренно записан как `+1 to Defence`, без `d`, как в актуальном источнике. Тип модификатора требует отдельной сверки с контекстом/версткой перед кодированием.

### Исполняемая PC-граница M18

Статус этого среза: `verified`. BOOK-PLAYER-GUIDE1.4, гл.IV Equipment92–93; взаимодействия — гл.V Helping108, Attack118–119 и Drained123. M18 ввела набор `staff`, `sword`, `dagger`, `axe`, `warhammer`, `morning_star`, одно одноручное оружие на PC. M19 расширяет текущий каталог ниже. [Примеры JSON/CLI](../examples/m18/README.md).

- Dagger использует Damage S−1, включая базовый Damage0 при S1; нижний предел1 не добавляется.
- Axe использует Damage S и отдельный `DamageModifier` +1 против бронированной цели. Броня и Resilience сохраняются; это не ignores armour. Trace: `RULE-EQUIPMENT-003:axe-armour`.
- Warhammer использует Damage S и +1d в настоящем Attack по Staggered enemy (`RULE-EQUIPMENT-003:warhammer-staggered-target`). Его собственный Help Test не имеет enemy target, поэтому такой бонус не получает.
- Morning Star использует Damage S+1 и −1d к собственным Melee Tests при Staggered, включая физический Melee Help (`RULE-EQUIPMENT-003:morning-star-staggered`).
- Прежний Sword +1d Defence без Staggered применяется и к соответствующему Defence Help. Staff сохраняет Damage S.

Drained удаляет положительные dice modifiers до cap, сохраняя отрицательные; Axe Damage modifier не является dice bonus. Действуют прежние предел2×Characteristic, forced minimum die/threshold1 и actual initial-roll окно Glorious. Подготовка привязана к актуальным Conditions/цели и полному source; hit/miss/tie проходят прежнюю каноническую проверку Damage/trace без нового RNG.

В этом native-сценарии без shields/дополнительных Abilities положительный `ResilienceProfile.bonus` означает броню. Это ограничение входа: PG119 допускает также другие источники Resilience, поэтому проверку `bonus > 0` нельзя переносить на произвольное снаряжение как доказательство wearing armour. Для такого расширения потребуется различать источники бонуса.

Все шесть видов используют прежние hand/drop/swap/pickup и Wounds1–23 последствия, Help/Fate/ally Recover и fixed-party count search. Stealth conceal Dagger и terrain trait Staff не исполняются в этой сцене без Stealth/terrain; это не полный каталог Traits. Две руки, dual wield, другие ranges, mounted/Charge и общий inventory сюда не входят. Поля party, метрики и wire version остаются прежними; старые JSON-примеры не мигрируются.

Реализация: [явная подготовка](../../src/towr/domain/pc_weapon_models.py), [PC owner](../../src/towr/domain/pc_melee_result_models.py), [каноническая проекция](../../src/towr/domain/_pc_melee_projection.py). Проверки: [детерминированная механика](../../tests/unit/test_m18_pc_weapons.py), [допуск и генерация](../../tests/unit/test_m18_pc_weapon_admission.py), [сквозной путь](../../tests/integration/test_m18_pc_weapons.py).

### Исполняемая PC-граница M19

Статус: `verified`. Книжные профили PG1.4, гл.IV Equipment92–93; хват и последствия — гл.V Recover118 и Wounds Table190–191. [ADR-0074](../decisions/ADR-0074-pc-two-handed-close-weapons.md), [JSON/CLI](../examples/m19/README.md).

| Новый weapon | Damage | Исполняемый Trait |
|---|---|---|
| `pickaxe` | S+1 | Harvesting Toil вне combat-сцены |
| `flail` | S+3 | −2d Melee при Staggered |
| `billhook` | S+2 | Mounted target bonus неактивен при нынешних пеших NPC |
| `halberd` | S+2 | +1 Damage против брони |
| `glaive` | S+2 | +1d Defence, если не Staggered |
| `greataxe` | S+3 | −1d Melee; +1 Damage против брони |
| `greathammer` | S+3 | −1d Melee; +1d Attack против Staggered enemy |

Actor Melee modifiers применяются и к собственному физическому Help Test; Glaive действует в Defence Help. Targeted Greathammer bonus требует actual enemy target и отсутствует у собственного Help Test. Положительный и отрицательный modifiers сохраняют отдельные Rule IDs, чтобы Drained убирал только бонус. Armour bonus не игнорирует Resilience и ограничен сценой без shields/Abilities, как в M18. Прежние cap/minimum die/Glorious сохраняются.

Текущий JSON1 принимает эти семь2H и шесть1H из M18, один предмет на PC. Поле `initial_weapon_hand` равно `both` только для2H; для1H — `left`/`right`. Тип `PcTwoHandedGrip.BOTH` отделён от анатомического `PcWeaponHand`; source, state, schema и codec проверяют связь с оружием. Боевая готовность2H требует обе пригодные руки, включая нынешний weapon-assisted Help. Любая травмированная рука12 вызывает Critical при использовании обеих рук, в том числе Recover с восстановлением хвата; просто переложить предмет в здоровую недостаточно.

Drop4/8/12 роняет весь предмет при выборе любой руки. Recover подбирает его с восстановлением2H хвата, сохраняя независимые self/ally benefits. Drop/clutch18 также роняет весь предмет. После полной lifecycle/immediate queue раны16/18/20, делающие2H хват невозможным, дают точный `two_handed_grip_unavailable` и UNSUPPORTED_PATH по выбранной пользователем границе. Wound, daily record, body facts и расход Fate сохраняются; продолжение/лишние Tests не выдумываются. Near Miss, отменивший рану, не создаёт stop.

При16/20 последний BOTH marker не становится утверждением о дальнейшем удержании/переноске предмета одной рукой; это уже граница исполнения. В отличие от явного drop18, падение всего предмета20 не подставляется. Это не правило обязательного проигрыша. Unsupported trials остаются в знаменателе; кандидаты с ними не выбираются. Запасное оружие, Brawn fallback, dual wield, другие ranges/Charge/mounts и Greatsword пока вне scope.

Реализация: [профили/модификаторы](../../src/towr/domain/pc_weapon_models.py), [хват и Critical](../../src/towr/domain/pc_heavy_wound_models.py), [drop/body projection](../../src/towr/domain/_pc_heavy_wound_projection.py), [owner/stop](../../src/towr/domain/pc_melee_result_models.py). Проверки: [pure traits](../../tests/unit/test_m19_pc_weapon_traits.py), [native бой/руки/Fate/stop](../../tests/unit/test_m19_pc_two_handed.py), [codec/schema](../../tests/unit/test_m19_pc_weapon_json.py), [process/подбор](../../tests/integration/test_m19_pc_two_handed.py).

### Исполняемая PC-граница M20

Статус: `verified`. BOOK-PLAYER-GUIDE1.4, гл.IV Equipment92–93, гл.V Actions116/Recover118 и Wounds190–191. [ADR-0075](../decisions/ADR-0075-pc-backup-weapon-policy.md), [JSON/CLI](../examples/m20/README.md).

Nullable `backup_weapon_policy` явно задаёт один из шести1H Close profiles и preferred_hand LEFT/RIGHT; требуется2H primary и Strength≥2 для двух carried weapons. Основное оружие/Characteristics/Skills остаются в immutable definition; состояние хранит только подтверждённое переключение. Null сохраняет M19-stop. Это fixed strategy, не произвольный inventory/dual wield.

Когда actual рана16/18/20 лишает2H хвата, configured backup с одной пригодной рукой позволяет дождаться собственного хода. До draw входящий удар отражается Athletics, старый Defence Help не переназначается. В свой unreserved turn живой не-Defenceless PC оставляет primary и выхватывает backup отдельным incidental proof; здоровая рука предпочтительнее травмированной12. Clutch18 сохраняется; Defenceless20 не может draw и продолжает обязательные end phases. Free draw вызывает Critical14/15 и последствия реально использованной руки12, не расходуя standard slot/Test и не создавая action count.

После единственного draw active Damage/Traits/Help/Protection используют backup; вернуть primary нельзя. При drop Recover подбирает только backup с отдельным instance ID. Если до draw не осталось пригодных рук, actual unsupported связан с последней закрывшей руку раной по sequence, а не порядку body facts после clutch reconciliation. После draw прежний primary2H не создаёт ложный stop: работает существующая1H стратегия. Near Miss применяется раньше и не создаёт ложный draw.

Текущий PC JSON1 требует `party[].backup_weapon_policy`: null либо `{weapon, preferred_hand}`. Все22прежние пары M9–M19 дополнены null с сохранением прежних gameplay/counters; omitted-field compatibility нет. Метрики и wire version не меняются, fixed-party search сохраняет оба предмета/настройку. Реализация: [typed source](../../src/towr/domain/pc_melee_models.py), [active-weapon helpers](../../src/towr/domain/pc_backup_weapon_models.py), [proof/owner](../../src/towr/domain/pc_melee_result_models.py), [canonical projection](../../src/towr/domain/_pc_melee_projection.py). Проверки: [native](../../tests/unit/test_m20_pc_backup_weapon.py), [admission/carry](../../tests/unit/test_m20_pc_backup_weapon_admission.py), [codec/schema](../../tests/unit/test_m20_pc_backup_weapon_json.py), [process/подбор](../../tests/integration/test_m20_pc_backup_weapon.py).

## RULE-EQUIPMENT-004 — ranged weapon profiles и reload

`1H` ranged имеет Max Range Long, `2H` — разумный предел GM. Вне Optimum Range применяется `-1d`. При любом враге Close ranged weapon запрещён, кроме weapon с Close в Optimum. Только если сама выбранная цель находится в Close, она может Oppose через Melee, а miss накладывает на атакующего Staggered как в Melee. Два shooting weapons не объединяются в одну attack.

Reload — Exacting Dexterity Test, одна Test за action. Если target successes не указан, reload бесплатен в составе attack. Ammunition считается достаточным после Downtime в месте снабжения либо при явном предварительном запасе.

Исполняемая K1-граница использует полный reload-подкаталог таблицы ranged weapons страницы 95: `RangedWeaponId`, `RangedWeaponReloadProfile` и factory `create_initial_ranged_weapon_reload_state`. Каталог покрывает все 13 строк и разделяет три книжных режима: бесплатная подготовка в составе атаки, обязательная Exacting-перезарядка после каждого выстрела и Exacting-перезарядка Repeater только после применения его опционального Shooting-бонуса. Factory привязывает `weapon_instance_id` к `weapon_id`; числовая цель больше не принимается извне и проверяется по профилю.

Полный нормативный combat-каталог представлен `RangedWeaponCombatProfile` и `RANGED_WEAPON_COMBAT_PROFILES`. Для каждой из 13 строк он типизированно фиксирует границы Optimum Range, Strength/fixed Damage, `1H`/`2H` и отдельные именованные поля всех боевых Traits таблицы. Max Range вычисляется из правила страницы 94: `1H` даёт Long, `2H` возвращает GM-defined предел, а Blunderbuss использует явное исключение Medium. Поле `reload` связывает запись с существующим reload-каталогом по тому же `RangedWeaponId`, не копируя trigger, target или Repeater bonus.

`RangedWeaponAttackPreparationRequest → Result` применяет combat profile к одному ещё не исполненному `AttackActionExecutionRequest` без RNG. Вход явно хранит weapon state, range band, Strength, наличие Blackpowder Lore, reload/Repeater choice, optional завершённый Aim и подтверждение GM для дальней границы. Внутри Optimum дополнительное range approval не нужно; для `2H` за верхней границей Optimum требуется явное подтверждение GM, `1H` ограничено Long, Blunderbuss — Medium, а Extreme требует и Aim, и GM approval. Close Range разрешён только оружию, Optimum которого включает Close.

Preparation заменяет placeholder Damage точным fixed/Strength значением, выставляет Close flag и ignores armour, добавляет `-1d` вне Optimum, Shortbow/Blunderbuss bonus, Crossbow bonus Damage против armoured цели, Wounds Table bonus Hochland Long Rifle для Player/Champion и typed nearby-Stagger secondary effect Blunderbuss. Внешние непротиворечивые modifiers/effects сохраняются; повтор уже добавленного профильного эффекта отклоняется. Blackpowder weapon без Lore и Hochland Long Rifle без Aim не создают результат. Optional Aim применяется после профиля через существующую follow-up-логику, поэтому result содержит exact `profile_attack`, `AimFollowUpResult` и готовый `RangedWeaponAttackExecutionRequest`; кубы, secondary target selection и consumed-ID mutation остаются следующим фазам.

Числовая ветвь представлена `ReloadableWeaponState` и `ReloadActionExecutionRequest → Result`. Состояние привязано к конкретным `weapon_instance_id`, `weapon_id` и активному `reload_cycle_id`, хранит immutable историю уникальных cycles, общий `ExactingTestProgress` и точную книжную цель successes. Каждая попытка — matching non-attack Skill Improvise для этого экземпляра оружия, ровно одна Dexterity Test и один action receipt; failure сохраняется как нулевой вклад. В активном цикле `loaded` становится `true` только одновременно с достижением цели, включая overshoot; исходно заряженное оружие может не иметь выдуманной истории reload. Бесплатная ветвь имеет отдельный `FreeReloadWeaponState` и не допускается в Exacting consumer.

`ReloadableRangedAttackExecutionRequest → Result` связывает числовое состояние с обычным Attack executor. Только явный `Skill.SHOOTING` и loaded weapon допускаются до RNG. Для Crossbow, Pistol, Handgun, Blunderbuss и Hochland Long Rifle любой завершённый Attack Test — hit либо miss — переводит тот же weapon instance в unloaded и открывает новый пустой Exacting cycle с книжной целью. Repeater без бонуса остаётся loaded; при явном применении ровно своего профильного `+1d/+2d/+3d` он после выстрела открывает cycle с целью `3/3/3/5`. Флаг бонуса, modifier и наличие нового cycle проверяются совместно, а повтор cycle ID запрещён по истории. Если вложенный Attack не проходит preflight либо не завершается, новое weapon state не создаётся. Бесплатная подготовка Sling и bows классифицирована, но остаётся частью обычной attack preparation. Боеприпасы, полный inventory/equip/capacity state и совмещение с отдельным Move Quietly opportunity consumer намеренно не моделируются.

`RangedWeaponAttackExecutionRequest → Result` является единым низкоуровневым entry point над обеими reload-ветвями. Для `FreeReloadWeaponState` он исполняет обычный Shooting Attack и сохраняет состояние оружия без cycle; для `ReloadableWeaponState` маршрутизирует тот же запрос через числовой composite. В обеих ветвях kernel и action receipt создаются ровно один раз. Free-профиль не принимает cycle ID или Repeater bonus. Preparation result теперь обязателен для верхнего `PreparedRangedWeaponAttackExecutionRequest`; низкоуровневый entry point остаётся доступен для специализированных композиций. Equipment/ammunition state остаются отдельными границами.

`MoveQuietlyHiddenRangedAttackExecutionRequest → Result` соединяет этот entry point с уже проверенным hidden-opportunity preflight. Hidden и ranged requests обязаны ссылаться на один exact unopposed Attack; executor запускает только profile-aware ranged path, а затем одним результатом раскрывает hiding position и дописывает opportunity ID в consumption chain. Free, ordinary reloadable и обе Repeater-ветви сохраняют свою обычную семантику. Неуспешное исполнение Attack не расходует opportunity и не меняет weapon state.

`PreparedHiddenRangedAttackExecutionRequest → Result` связывает существующий hidden preflight с `PreparedRangedWeaponAttackExecutionRequest` по точному final Attack, уже включающему профиль и optional Aim. Исполняется только `execute_prepared_ranged_weapon_attack`, ровно один раз; после полного результата погашается hidden opportunity и возвращается revealed hiding-position ID. Result хранит один nested prepared result, exact source и объединённый ordered trace подготовки/Move Quietly/execution. Hidden consumption chain хранится отдельно, Aim chain доступна из вложенного результата без копирования; hit и miss расходуют обе применимые возможности, а исключение не мутирует входные snapshots (RNG не откатывается). Текущие awareness/placement и обе consumption chains сообщает caller. Это consumer уже подтверждённой возможности, не dispatcher lifecycle скрытности.

Non-Attack continuation теперь сохраняет подтверждённую opportunity после Aim при неизменной позиции без раскрытия; departure/reveal погашают её отдельно. `CODE-CONFLICT-001` исправлен; подробности lifecycle — `combat.md`, RULE-COMBAT-014.

`AimRangedWeaponAttackExecutionRequest → Result` аналогично принимает уже разрешённый `AimFollowUpResult` с исходом `APPLIED_TO_RANGED_ATTACK` и точный подготовленный Shooting Attack. Он не вычисляет bonus повторно: `AimFollowUpResult.attack` обязан совпасть с profile-aware request, после чего исполняется один ranged resolver и follow-up ID дописывается в отдельную consumption chain. Нулевой bonus также погашает Aim. Aim и Repeater modifiers складываются до общего обычного pool cap; weapon transition остаётся профильным. Lost/Throwing/foreign/replayed follow-up отклоняются до RNG.

`PreparedRangedWeaponAttackExecutionRequest → Result` принимает завершённую подготовку и immutable snapshot уже использованных Aim follow-up IDs. Прямая ветвь вызывает unified ranged executor, Aim-ветвь — существующий Aim-bound executor, ровно один раз. Result хранит исходную подготовку, один nested execution выбранного типа и точный объединённый trace; свойство `ranged_attack` предоставляет общий доступ к Attack/weapon transition без дублирования данных. Без Aim consumption chain сохраняется, с Aim дополняется только его follow-up ID, включая нулевой бонус. Подмена ветви/source/trace/consumption отклоняется; ошибка исполнения не возвращает новый state и не меняет входные snapshots (RNG при этом не откатывается). Caller обязан сохранять и передавать актуальную цепочку; это не глобальное хранилище защиты от повторов.

`RangedWeaponAttackPreparationRequest.has_enemy_in_close_range` — обязательный bool без default: caller сообщает наличие любого врага в Close относительно стрелка, независимо от выбранной цели. При `true` профиль без Close в Optimum отклоняется до RNG; Aim, Lore и GM range approval запрет не снимают. Исключение покрывает Pistol, Repeater Pistol и Repeater Handbow. Факт не меняет `target_range`, Close flag атаки, выбор defender Test или последствия дальнего промаха; отдельная проверка Close выбранной цели сохраняется. `RULE-EQUIPMENT-004:close-enemy-restriction` входит в trace как при `true`, так и при `false`, а исходный факт сохраняется в preparation source. Spatial-поиск, классификация врагов и актуальность переданного факта принадлежат caller (PG 1.4, Equipment, стр. 94–95).

Одноручный Max Range Long проверяется независимо от Aim/GM approval.

| Weapon | Cost | Optimum | Damage | Hands | Traits |
|---|---|---|---|---|---|
| Sling | Brass | Medium | S | 1H | — |
| Shortbow | Brass | Short–Medium | 3 | 2H | `+1d` Shooting по Short |
| Warbow | Brass | Medium–Long | 3 | 2H | — |
| Longbow | Silver | Medium–Long | 4 | 2H | — |
| Crossbow | Silver | Short–Long | 4 | 2H | `+1 Damage` armoured; reload 2 |
| Pistol | Silver | Close–Short | 5 | 1H | ignores armour; reload 3 |
| Handgun | Silver | Medium–Long | 5 | 2H | ignores armour; reload 3 |
| Blunderbuss | Silver | Short | 4 | 2H | Max Medium; `+2d` Short; hit Staggers creatures Close к цели; reload 3 |
| Hochland Long Rifle | Gold | Medium–Extreme | 6 | 2H | must Aim; ignores armour; `+1d` Wounds Table; reload 4 |
| Repeater Handbow | Gold | Close–Short | 4 | 1H | можно `+1d` к одной Shooting, затем reload 3 |
| Repeater Crossbow | Gold | Short–Medium | 4 | 2H | можно `+1d`, затем reload 3 |
| Repeater Pistol | Gold | Close–Short | 5 | 1H | ignores armour; можно `+2d`, затем reload 3 |
| Repeater Handgun | Gold | Short–Long | 5 | 2H | ignores armour; можно `+3d`, затем reload 5 |

Все blackpowder firearms требуют Blackpowder Lore.

## RULE-EQUIPMENT-005 — throwing weapon profiles

M52 подключает [Weighted Net + carried Spear](npc-profile-catalog.md#night-goblin-net-spear-m52) к PC owner: Throwing и primary Burdened вместо numeric Damage, один фактически расходуемый предмет, free draw carried backup и source-bound Net cause. Сохраняются выбранные PC Attack/standard Recover и Spear против Defenceless; generic Net→Defenceless precedence не утверждается. PG1.4 IV96 / V116/118/123, GM1.1 VII93/156–157; [контракт](../decisions/ADR-0097-pc-weighted-net-and-carried-spear.md).

Throwing используется в Charge вместо Melee и тогда считается в Optimum Range. При Strength 4+ верхняя граница Optimum увеличивается на одну range step. За пределами Optimum атаковать нельзя.

| Weapon | Cost | Optimum | Damage | Hands | Traits |
|---|---|---|---|---|---|
| Rock | n/a | Short–Medium | n/a | n/a | не Wounds, кроме repeated Staggered |
| Throwing Spear | Brass | Close–Medium | S | 1H | — |
| Throwing Axe | Brass | Short | S+1 | 1H | `+1 Damage` armoured |
| Weighted Net | Brass | Close–Short | n/a | 2H | Burdened вместо Damage |
| Throwing Knives | Silver | Short | S | 1H | набора хватает на бой |
| Oil Flask | Silver | Short–Medium | n/a | 1H | hit даёт Ablaze цели и всем Close к ней |
| Blasting Charge | Gold | Short–Medium | n/a | 1H | hit: Endurance Hazard (3) всей target Zone; miss: то же в attacker Zone |

Обычные throwing weapons можно подобрать при наличии возможности; Oil Flask и аналогичные расходные — нельзя.

## RULE-EQUIPMENT-006 — armour и outfits

Resilience равна Toughness плюс armour/trapping bonus. Armoured — любой, у кого armour, shield или иной эффект поднял Resilience выше Toughness. `Ignores armour` временно использует Toughness вместо Resilience для этой attack.

| Item | Cost | Resilience | Traits |
|---|---|---|---|
| Peasant’s Garb | Brass | T | `+1d` Charm выглядеть harmless |
| Burgher’s Apparel | Silver | T | `+1d` Charm при haggling с Silver |
| Lordly Attire | Gold | T | `+1d` Leadership при orders Brass/Silver |
| Uniform | Brass | T | `+1d` Leadership civilians; под armour |
| Worker’s Leathers | Brass | T | `+1d` против physical Hazards; поверх outfit |
| Travelling Clothes | Brass | T | `+1d` против environmental Hazards/conditions |
| Concealing Clothing | Brass | T | `+1d` Stealth в одном environment; поверх outfit |
| Stage Costume | Brass | T | `+1d` attract attention |
| Shield | Silver | +1 | carried; Defence против Shooting |
| Light Armour | Silver | T+1 | — |
| Heavy Armour | Gold | T+2 | `-1d` Agility; Burdened при S < 3 |
| Barding | Gold | +1 | horse; `-1d` Agility mount/rider; также `+1 Resilience` rider |

Источник: страницы 97–98.

## RULE-EQUIPMENT-007 — tools, kits и услуги

Нужный kit разрешает Tests/actions, иначе невозможные. Импровизация возможна с GM permission и всегда получает difficulty penalty. Сам toolkit обычно не даёт bonus dice; Required Lore остаётся обязательным. Trade Lore не позволяет craft без соответствующих Trade Tools.

Полный data-каталог страниц 99–101 включает Game Set, Arcane Paraphernalia, Lighting/Hunting/Climbing kits, Traveller’s Pack, Thief Tools, Writing/Grooming/Physicker’s/Cartography kits, Monster Slayer’s Arsenal и девять Trade Tools, а также General Assistance, Food & Lodging, Transportation и Specialist Labour по трём Status tiers.

NPC service обычно стоит tier NPC; time-consuming, costly, illegal или dangerous повышает expense на tier. Нерутинная услуга требует Persuade, opposed Willpower. NPC может запросить favour вместо Coin.

## RULE-EQUIPMENT-008 — Assets

Asset может открыть Test, дать bonus dice или иметь собственные правила. Его нельзя купить обычным Coin: он приходит из creation/reward/narrative либо Invest Money Endeavour; обмен обычно связан с Change Career. Repair стоит по 1 Coin tier Asset за каждый Fault/issue.

Каталог:

- Animals/Vehicles: A Small but Vicious Dog, Hand Cart, Trade Cart, Travelling Stage, Rowboat, River Barge, Ship’s Passage, Horse and Stables, Coach;
- Buildings: Farm and Grazing Herd, Market Stall, Shop, Armoury, Workshop, Laboratory, Brewery, Tavern, Theatre, Secret Hideout, Religious Shrine, Temple, Barracks, Library, Luxurious Apartments, Chapterhouse, Noble Estate;
- Other: Secret Identity, Map of the Underground, Mark of Honour, Symbol of Office, Enchanted Arrows, Map of the Worldroots, Secret Society Membership, Printing Press, Trustworthy Banker, Full Plate Armour, Heirloom Wargear.

Особые числовые эффекты страниц 103–105:

- Small but Vicious Dog при отсутствии Staggered у хозяина запрещает Give Ground цели его Melee/Brawn attack;
- Enchanted Arrows: Hagbane даёт Drained, Moonfire — Ablaze, Trueflight игнорирует cover/concealment penalties; по одной стреле каждого типа/session без replenishment Endeavour;
- Trustworthy Banker отменяет Bank Money Endeavour для доступного lodge/withdraw;
- Full Plate: `T+3`, `-1d` Agility, Burdened при S < 4;
- Heirloom Wargear без конкретного magic item раз/session делает Test с ним Glorious.

Остальные описания Assets предоставляют доступ/ресурсы и campaign permissions, но не должны получать выдуманные числовые бонусы.
