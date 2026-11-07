# ADR-0096: Great Stag, Crown of Antlers и Trample

Создано: 2026-11-06. Принято пользователем и реализовано: **2026-11-07, M51 завершена**. Все три рекомендованных решения выбраны явно: Brawn/cap10 и PC Endurance; новый Prone от последствий первой Antlers Attack; та же поваленная цель без переназначения.

## Источники и неизменные факты

Непосредственно сверены локальные BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Great Stag176 / NPC Profiles93; BOOK-PLAYER-GUIDE1.4, гл.III Skills68–69, гл.V Attack118 / Wounds Table190–191. Dice Modifiers107 и общий предел действий116 переиспользуются из прежних вех. Поиск Trample в извлечённом тексте книг не дал отдельного нормативного определения Skill; похожие Stomp profiles других существ не устанавливают правило по аналогии.

Great Stag: WS4/S5/T5/Ag5, Fast Brute3, Resilience5 без armour/shield, natural attacks. Mighty Antlers Close4d/3 Damage6; успешный **Charge** этой атакой накладывает Prone до Give Ground. Trample Close5d/3 Damage5 допускает только Prone enemy. Athletics5d/4 Protection. W0–1 без эффекта, W2Drained, W3defeat.

Crown of Antlers: после атаки, заставившей enemy упасть Prone, разрешено второе действие Trample. Отдельно Ability выбирает destination, если attack заставила enemy Give Ground. Fearsome даёт Broken после Give Ground. Great Stag Knights требует всадника. В current noMove/unmounted/SUFFER_WOUND сцене Charge, destination и rider triggers отсутствуют; не добавлять их effects в ordinary Antlers Attack.

## Решение 1: Skill/cap и Opposition Trample

Карточка печатает5d/3, но не Skill. Значения соответствуют S5/Brawn3; WS4/Melee3 тоже объясняет threshold, но не доказывает происхождение пятого куба. Числа пула сами по себе не являются основанием назначать Skill.

**Принято:** Trample использует Brawn, printed5d/3 Damage5, cap10 отS5 (`pool_cap:null`, поскольку base5). Это интерпретация данной карточки, не дословное указание Skill. PG69 прямо задаёт Athletics или Endurance как Opposition Brawn/unarmed; для первого среза PC выбирает **Endurance**, без автоматического подбора более выгодного Test. Defenceless PC не Oppose. Printed Damage5 — специальное свойство Trample, не обычный выбор grapple/shove из Brawn.

При Brawn реализации требуется соответствующая ветвь NPC preparation/Protection: natural Brawn Close с явным выбранным профилем, Endurance/Athletics Opposition по PG69. Существующая PC тактика Defence при оружии относится к Melee и не переносится автоматически на Trample. Fate/Glorious используют фактический Endurance Test; прежний Protection Help не переназначается на другой Skill. Другие families не получают разрешение на произвольные authored Brawn NPC в PC source.

Альтернатива: считать Trample специальной Melee attack, оставить5d/3 и cap8 отWS4, с прежней PC Defence/Athletics тактикой. Тогда нужен explicit `pool_cap:8` только canonical Trample; Brawn/Endurance branch не добавляется. Выбор должен быть единым в текущем контракте, а не скрытым default или двумя совместимыми версиями.

## Решение 2: какое падение Prone запускает Crown

**Принято:** actual первая Antlers Attack запускает Crown при подтверждённом переходе цели **не Prone → Prone**, включая accepted Wound/немедленные последствия этого Wound. Например, Wound9 Leg Spasm, Wound13 Torn Leg, Wound17 Shattered Knee либо Wound5 Battered Leg с проваленным Endurance — если они действительно добавили Prone. Полный список берётся из исполнившихся consequences, не из чисел таблицы отдельно от journal.

Проверять transition после Near Miss/Endurance/body и mandatory expiry. Near Miss, отменивший единственную Wound-причину Prone, не даёт grant. Успешный Battered Leg Endurance не даёт grant. Уже Prone цель не «падает» ещё раз; новый Wound с Prone по такой цели не даёт grant. Падение от прежней атаки/другого actor/Warped Form/собственного Recover не переносится в Crown source. MISS не даёт grant.

Это конкретизация causal wording GM176; текст отдельно не перечисляет Wounds Table/Endurance. Альтернатива — до реализации Charge считать доказанным только явный Antlers Charge effect, оставив Crown недоступной в нынешней неподвижной сцене. Такой выбор не следует выдавать за поддержанную ordinary-Antlers → Wound → Trample цепочку.

## Решение 3: цель optional Trample

GM176 требует Prone enemy, но не говорит «тот же» или «другой».

**Принято:** топтать только поваленную первой Attack цель, если после всех её последствий она жива и остаётся Prone. Living Defenceless допустим; dead — нет. Если исходная цель недоступна, optional Trample пропускается без переназначения.

Альтернатива: после доказанного Crown trigger выбрать первого живого Prone PC по existing enemy_target_priority, включая исходную цель. Это отдельная тактика, а не применение Bear different-target ограничения. Non-Prone цель в обоих вариантах недопустима.

## Принятый source/JSON контракт

Один canonical `GREAT_STAG = great_stag`, ID `pc-book-npc:great_stag`, source `BOOK-GM-GUIDE:1.1:p176:great_stag`. Native NpcDefinition содержит две полные natural Attack profiles в фиксированном порядке: Mighty Antlers, Trample. Fresh snapshot хранит оба available IDs/noWeapon/noShield. Текущие book/authored NPC сохраняют ровно одну Attack; произвольные multi-attack definitions не разрешаются.

Current PC JSON1 сохраняет `definition.attack` для primary Antlers и добавляет **условное** `definition.trample_attack` только Great Stag. Оно required для полного canonical Great Stag и запрещено всем остальным definitions. Для старых168JSON M9–M50 поле не добавляется; missing вторую атаку у Great Stag нельзя восстановить из ID/default.

Полная форма secondary profile для принятого Brawn решения:

```json
"trample_attack": {
  "id": "trample",
  "source_rule_id": "BOOK-GM-GUIDE:1.1:p176:great_stag:trample",
  "skill": "brawn",
  "test_profile": {"dice": 5, "threshold": 3, "pool_cap": null},
  "damage": {"base": 5, "success_multiplier": 1},
  "range_max": "close",
  "hands": null,
  "secondary_effects": []
}
```

Это closed object с required полями. Допускается только выбранная полная canonical Brawn форма; Melee/cap8 альтернатива отклонена. Primary Antlers сохраняет4d3/capnull8, Damage6, без Charge descriptor; Protection5d4/capnull10. Полный source guard защищает оба nested profiles, их порядок, skills/caps/gear и reserved identities после частичного переименования.

Existing required `npc_extra_attack_actor_ids` расширяется на Great Stag: наличие actor выбирает optional Crown всякий раз, когда она доступна по принятым решениям. `[]` отказывается от optional Trample. Новой верхнеуровневой policy/версии/counters нет; existing extra-Attack counts считают фактически исполненный Trample slot2. Тактика первого действия — всегда Antlers, включая уже Prone initial target; свободный выбор ordinary Trample пока не добавляется.

## Порядок и границы слоёв

Первый Antlers Attack проходит обычные Test/Protection/Damage/Stagger/Wound/Fate/body. После полного actual prefix owner подтверждает новый Prone именно этой атаки и допустимую текущую цель. Новый typed **CrownOfAntlersGrant** привязывает actor/round, receipt slot1, source target, выбранный target и Trample profile. Clock хранит узкое разрешение, owner доказывает trigger по полному journal; IDs/флаг Prone сами по себе его не заменяют.

Это отдельный grant от EnduringStrengthGrant: Bear требует другую цель, Crown такого условия не имеет. Reservation, готовый Turn/Round state и Attack executor/result admission проверяют соответствующий тип и source. Одновременно выбрать оба grants нельзя. Третий action, повторный grant/Trample, stale round/actor/receipt и пропуск mandatory work отвергаются.

Slot2 исполняет настоящий selected Trample profile и фактический Skill/Protection, со своими Test/action IDs и receipt. Не подменять Antlers Damage/Test/RuleID и не приписывать unused Help второму Test. После второй Attack и её обязательных последствий — один TurnEnd. Pending/unsupported сохраняют наблюдённый prefix; неисполненная optional Attack не считается выполненной. Existing Bear path не меняет semantics.

W2Drained самого Stag накладывается на actual1→2 profile-Wound ACK, включая Warped Form, и подавляет bonus dice обеих Attack modes. W1Drained не изобретается. Никаких Charge/ground movement, rider effects, Fearsome без Give Ground, camp/healing/оптимального AI.

## Адресная приёмка

1. Полная карточка/два fresh profiles/typed skills/caps/Protection/W0–3, noWeapon/noShield. Сохранность55прежнихentries/metadata и168старыхJSON без миграции. Conditional wire field, unknown/partial sources, порядок profiles, malformed caps/types до RNG.
2. Literal actual first Attack → accepted Wound9/13/17 или failed Battered Leg Endurance → Crown; Near Miss/successful Endurance/already Prone/MISS/чужая причина не дают grant по принятой границе. Проверки outcomes следуют actual completed journal.
3. Target policy: только та же поваленная цель без переназначения; dead/не-Prone недопустимы, living Defenceless поддержан. Second Test использует Trample, нужный higher ground/Drained/cap, actual Skill/Protection/Fate; Help не копируется.
4. Typed clock/reservation/executor/application/replay: wrong/stale source/attack/target/round, pending lifecycle, duplicate/third action, mutation aliases, unsupported prefix; existing Bears сохраняют different-target grants.
5. Current JSON1 roundtrip/full root/candidate echoes, compact extra counts, trials/count search/CLI. Подбор фильтрует actor list без переназначения. Проверить общий NPC preparation/Protection и новые Endurance consumers; изменение общего clock требует адресного checkpoint ближайших dependent families. Process cases заранее отделить от Windows sandbox; wheel только при изменении доставки.

## Согласование и реализация

Пользователь явно выбрал все три рекомендации. Это конкретизация Skill/causal trigger/тактики данной карточки по [AGENTS.md](../../AGENTS.md), не назначение Skill по совпадению чисел и не универсальное правило Trample всех существ. Полный source и typed Crown grant реализованы без миграции прежних JSON.

При интеграции исправлен общий Protection gate по PG69: против Brawn разрешены Athletics/Endurance, а не обычная Defence. Явное профильное исключение Stealth сохраняется; Endurance не становится защитой против обычной Melee/ranged атаки. [Закрытое расхождение](../contradictions.md#code-conflict-004--protection-против-brawn-исправлено-2026-11-07).

Проверены literal Wound/Fate/Endurance/clock/источники, native admission, JSON/search и один фактический sequential/process Trample. Результаты и команды — в [статусе](../project-status.md), пользовательский вход — в [CLI-примерах](../examples/m51/README.md), дальнейшая [очередь](../roadmap.md). Full/wheel ради ADR не требуются.
