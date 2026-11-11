# ADR-0112: PC Hochland, обязательный Aim и Fate Second Action

Дата: 2026-11-12. Статус: **принято и реализовано M70**. Пользователь выбрал Aim + Fate Second Action в прежнем Short-сценарии.

## Книжные источники и достижимая функция

Адресно прочитаны BOOK-PLAYER-GUIDE1.4 III70, IV95, V111/114/116–117; переиспользуются прежние ranged94/Blackpowder82/99/Conditions/Wounds. Сверены shared Hochland/Aim/preparation/consumption/FateSecondActionSpend и PC action selection/Fate ledger/compact results. Новых книг/версий/house rules нет.

Hochland Long Rifle:2H, optimum Medium–Extreme, Damage6/ignores armour, mandatory Aim, +1d на Wounds Table, Reload4. На исходном Short разрешён выстрел с−1d; при любом Close enemy стрелять нельзя. Wounds Table bonus применяется только там, где используется эта таблица: в нынешней numeric Minion-сцене её нет. Trait не отключается и не превращается в дополнительный Damage, incoming NPC Wounds или bonus Sword.

Aim PG116 — настоящее действие с Awareness Test (Initiative/Awareness по PG70); каждый успех даёт+1d на следующий ranged Attack по той же цели, если между ними нет другого собственного действия. Даже0успехов — выполненный Aim с нулевым бонусом; повторять Aim до успеха автоматически не нужно. Бонус подчиняется cap/Drained; mandatory Aim при Drained остаётся обязательным.

В нынешнем Short opening NPC подходят после первого обычного Aim: PC обычно достанет backup до выстрела. PG111 прямо разрешает **spend Fate на Second Action: Aim→Attack**. Выбранный M70 реализует этот путь на собственном ходу, сохраняя прежнюю тактику NPC. Это session spend, не permanent burn и не бесплатный второй action. Вторая Attack/третье действие запрещены.

Книжная альтернатива PG116 — setup turn до того, как противники заметили группу. Она требует отдельного scenario premise/prelude/границы awareness и не вводится бесплатно ради оружия. Medium opening также не решает задачу сам по себе: обычное free movement позволяет NPC пройти одну Zone за turn и атаковать; spatial расширение требует полноценного источника движения.

## Рекомендуемая тактика первого среза

1. Обычные mandatory/Recover/hand/Defenceless/terminal priorities прежние. Если loaded Hochland реально пригоден и нет Close enemy, PC выбирает первую живую цель по существующему target_priority и выполняет стандартный Aim.
2. Для Awareness первого среза optional Glorious отклоняется явно; это не автоматическое расширение существующего Glorious selector на новый Skill. Aim использует actual Initiative/Awareness и held2H; Critical/ранения/конец хода не пропускаются.
3. После Aim по явной aim_second_action_policy и фактическому остатку Fate резервируется второй ATTACK slot через existing composite FateSecondActionSpend. Резерв применяется после оплаты этого spend; Lucky free funding сохраняет обычный резерв. Даже0успехов Aim разрешают такую попытку Shoot. Нет скрытого success threshold/оптимизации.
4. Сразу следующий собственный action — Shoot по той же ещё доступной цели. Сначала оплачен Second Action, затем existing optional Shooting Glorious по своим критериям и оставшемуся ресурсу. Это независимые policies, не общий оптимальный распределитель Fate.
5. Без policy или доступного funding выше резерва PC завершает обычный Aim без Shoot. На следующем ходу действует прежний Close→backup. При допустимом сохранившемся Aim/Short его можно употребить только на действительно следующий собственный ranged Attack той же цели; другой action, Recover или melee теряет Aim по existing consumption rules. Bank нельзя переносить к другому actor/target/новому действию после потери или повторно использовать.
6. После фактического Shoot primary empty/cycle4 сохраняется; NPC approach→backup прежний. Полный fresh Aim→Shoot→Reload4→новый Aim→Shoot не обещается, safe repeated ranged cycle/новая тактика NPC не добавляются.

Первые примеры используют явный session ресурс и reserve0, без Glorious Awareness. Политика при отсутствии Fate законна, хотя в текущей сцене обычно не даёт Hochland shot до сближения; не подменять её новым ранним draw/free Aim или UNSUPPORTED только из-за отсутствия необязательной траты.

## Текущий source и JSON1

Добавлен PcMeleeWeapon.HOCHLAND_LONG_RIFLE в ranged12→13 и2H8→9, free4 прежняя. Exact firearm source —9ordinary fields плюс обязательный awareness, всего10: BS/Shooting/I/Dexterity/true Lore/kit/ammunition/loaded/two_available_hands и Awareness. I используется для обоих Skills, Awareness не выводится из Dexterity/Agility. Repeater policy/shield запрещены, initial grip=BOTH; source только прежний restricted Short opening/simple numeric Melee Minions/ATH.

Новые поля на примере relevant PC-фрагмента:

```json
"weapon": "hochland_long_rifle",
"ranged": {
  "ballistic_skill": 3,
  "shooting": 4,
  "initiative": 3,
  "dexterity": 4,
  "awareness": 4,
  "has_blackpowder_lore": true,
  "has_blackpowder_kit": true,
  "ammunition_supply_confirmed": true,
  "initially_loaded": true,
  "reload_hand_policy": "two_available_hands"
}
```

Per-participant optional exact object:

```json
"fate_policy": "configured",
"aim_second_action_policy": {
  "minimum_remaining_session_spends": 0
}
```

Объект допускается только у Hochland; отсутствие означает отказ от Second Action. Present null/extra keys/bool вместо exact nonnegative reserve запрещены. При наличии policy configured Fate считается настроенным даже без Near Miss/Glorious; без неё прежние configured/decline зависимости сохраняются. У остальных12weapons awareness и эта policy запрещены. Aim как новая свободная optional тактика всех bows/guns одновременно не добавляется. Generation сохраняет PC policy/Fate и фильтрует только нынешние NPC зависимости; новых actor pairs/Aim target field не нужно.

## Counters и один текущий контракт

Aim — настоящее действие: total_action_count учитывает Aim и Shoot по отдельности, Second Action spend не является третьим действием. Glorious/Near Miss counters не подменяют Second Action. Для текущих request с Hochland в summary добавлен обязательный capability block aim (также в candidate summary):

```json
"aim": {
  "action_counts": [{"actor_id": "pc1", "count": 4}],
  "total_action_count": 4,
  "second_action_spend_counts": [{"actor_id": "pc1", "count": 4}],
  "total_second_action_spend_count": 4
}
```

Rows содержат всех PC в исходном порядке, включая нули; totals согласованы с ними и actual action/Fate receipts. Spend counts включают Lucky-free spend как existing Glorious counts, а не обещают число оплаченных session points. Funding/remaining reserve подтверждаются native ledger/proof. В сценах без Hochland block отсутствует, а не добавляется с искусственными нулями: это один текущий feature-conditional контракт, не compatibility с прежней wire version. Поэтому прежние244JSON M9–M69 не требуют миграции. JSON1/остальные families/NPC59/shared14 прежние.

## Исполнение и source/proof инварианты

- Aim request/result имеет настоящий standard slot/Awareness roll/actor/target/round/receipt; fake initial Aim/precomputed successes не принимаются. Aim сохраняется между ходами как one-use bank, но не переживает другой собственный action. Чужие действия сами по себе Aim не потребляют.
- FateSecondActionSpend одновременно добавляет ledger record и резервирует slot2, привязанный к actor/session/round/declaration. Нельзя отдельно подделать grant FATE, списать ресурс без slot или выдать его без оплаты; replay/вторая Attack/slot3 запрещены до RNG.
- PC preparation включает full Aim follow-up до actual Conditions/Fate Shooting. Current owner использовал profile_attack без Aim: новый путь обязан учесть effective aim_follow_up.attack/execution attack, снять и восстановить source-owned Aim/range Traits ровно один раз и не дублировать dice. Drained не создаёт fake positive bonus; zeroAim остаётся полноценным prerequisite.
- Source/ledger/history фиксируют Awarenesstest, next own action, target, consumption/loss и spend. Mandatory Wounds/Critical14/15/hand restrictions и own end phase завершаются после действительного числа действий; между Aim и разрешённым вторым действием нельзя преждевременно закончить ход. Recover/backup/terminal guards прежние.
- Incoming NPC profiles и named NPC/Brutes/Champions/другие Zone не расширяются. Wounds+1d проверяется дополнительно existing focused K1 PLAYER/Champion preparation, не fake full PC scenario. Native proof/source и compact worker counters меняются вместе.

## Адресная приёмка

Literal Aim0/несколько successes, I/Awareness vs BS/Shooting, Short−1d/cap/Drained/Glorious Shooting, Damage6/armour/Reload4, actual standard Aim→paid/Lucky Second Action→Shoot до NPC approach. Отдельно funding exhausted/reserve/decline, spend before Shooting Glorious, no free slot/вторая Attack/третье действие/повтор actor/session/target, stale/missing/consumed Aim, loss при другом action/Recover/melee и retained charge/backup. Wounds/CI/Defenceless/terminal/drops/end-phase без пропуска mandatory проверяются детерминированно.

Strict native/wire10fields/policy/configured/current conditional summary/rows/totals, source/candidate echoes/проектирование составов, services/count search/actual CLI. Native pickle и один representative sequential/process comparison justified: меняются compact trial counters/source и PC action/resource path; не повторять полную module/console×backend матрицу. Existing Aim/FateSecondAction/preparation/PC Fate/hand/runner зависимости проверять по риску.244старыхJSON/NPC59/shared14 сохраняются. Full/wheel без иных оснований не запускать.

## Согласование и результат

Пользователь выбрал «Aim + Fate Second Action». Реализованы actual Aim/Awareness, one-use APPLIED/LOST consumption, canonical Fate slot2, ledger/funding/reserve и conditional counters без новой NPC тактики. Setup prelude не добавлен. Новыеsource/codec/schema/native owner/compact records/services/count search/CLI согласованы в текущем JSON1.

В приёмке исправлены старый blanket Lucky ban (Hoc-only source), CANNOT_AIM от реальной Wound8 (PG190) и source-policy bypass через преждевременный общий TurnEnd после Aim. Дополнительно Glorious selector приведён к canonical Lucky/paid cost: неистраченный Lucky позволяет бесплатный выбранный Glorious после backup, если Second Action не использован. Тесты проверяют actual funding/session_cost0 и раздельные counters; у остальных PC loadouts прежняя граница Lucky сохраняется.

Начальный адресный checkpoint405tests:402passed/3failed. Три failure — устаревшие ожидания pre-ranged каталога, pre-M63 Melee Protection Help и pre-M54 Shooting Glorious; они обновлены по текущему контракту. После исправлений/TurnEnd guard адресный100tests — OK15.693s. После финального Lucky/Glorious funding изменения повторены связанные Fate/native/source/statistics:51tests — OK8.973s, включая все30новых source6/native16/JSON8. Это несколько адресных прогонов, не единый зелёный405/full run.

Один actual process comparison (2workers/batch1/2trials) — OK2.204s: записи и агрегаты совпадают с sequential. Он проверяет новые compact counters/source; общая backend матрица не повторялась. Actual simulation/balance CLI выполнены; фактические команды/текущая сверка — в [статусе](../project-status.md), пользовательские результаты — [M70](../examples/m70/README.md).

Прежние244JSON/NPC59/shared14 сохраняются; все13PG ranged weapon profiles теперь допускаются в ограниченном PC исполнении. Это не полная книга или все возможные дальности/действия. Wheel/full не запускались без основания: package discovery/resources/dependencies/entry points прежние. [Следующий шаг](../roadmap.md#после-m70).
