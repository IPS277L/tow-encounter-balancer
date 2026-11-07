# ADR-0094: Imperial Ogre / cap6 и наземный Pegasus

Дата: 2026-11-06. Статус: **принято пользователем и реализовано M49: оба профиля**. Выбраны canonical cap6 Ogre/Greathammer и явный наземный срез Pegasus.

## Задача и источники

Следующий совместимый чанк — два самостоятельных физических Brutes: Imperial Ogre с Greathammer и Pegasus, явно начинающий бой на земле. Это два профиля, а не обязательная квота3–5: другие рассмотренные кандидаты требуют самостоятельных пространственных или условных вторых атак. Не включать их ценой отключения применимых Abilities.

Непосредственно сверены полные локальные карточки BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists: Imperial Ogre103 и Pegasus176; общий раздел Understanding NPC Profiles93. BOOK-PLAYER-GUIDE1.4, гл.V Rules / Dice Modifiers107 задаёт cap2×Characteristic, Speed115 — пределы движения; пребывание в одной Zone не доказывает полёт или Close. Книжный WS и уменьшенный printed attack pool — разные факты.

## Imperial Ogre / Greathammer

Canonical enum `IMPERIAL_OGRE_GREATHAMMER = imperial_ogre_greathammer`, definition ID `pc-book-npc:imperial_ogre_greathammer`, source `BOOK-GM-GUIDE:1.1:p103:imperial_ogre_greathammer`.

- Brute3, Toughness5, Resilience6 armoured, без shield.
- WS3; Greathammer Close2d/4 Damage8,2H. Printed2d сохраняется без дополнительного PC weapon penalty/Traits.
- Attack `InlineProfile(dice=2, threshold=4, pool_cap=6)`; Athletics3d/3 Protection с прежним implicit cap6/null.
- Speed Fast при0Wounds и Normal при1–2, W3defeat. В неподвижной сцене смена Speed не создаёт action/Condition и не влияет на порядок ходов. Полные wound bands сохраняются в metadata; перемещение Ogre не заявляется поддержанным.

Rough Shove и Ogre Pistol — явно unselected attacks; их effects не переносятся на Greathammer. Ogre Charge требует Rough Shove в Charge, Mighty Throw — successful Rough Shove против Staggered; оба trigger отсутствуют в данном выбранном loadout/тактике. Fearsome срабатывает при Give Ground от его Melee; нынешняя стратегия выбирает SUFFER_WOUND, а не Give Ground. Эти Abilities сохраняют полные условия в metadata, не считаются глобально выключенными или исполненными.

### Узкое расширение существующего поля

Current PC JSON1 уже требует `test_profile.pool_cap`. Расширить schema enum `[null,8]` до `[null,6,8]`; native source admission разрешает6 **только** Attack полного canonical Imperial Ogre/Greathammer. Прежние cap8 Minotaur Greataxe/Bestigor сохраняются, остальные Attack/Protection и authored NPC — null.

Полный definition/source guard обязателен: одного совпавшего ID недостаточно. Null/4/8 у Ogre,6 у другого book/authored NPC или Protection, пропуск поля, bool/float/string aliases и частичные переименования отвергаются до RNG. Codec сохраняет переданное значение, не вычисляет его и не исправляет источник. Это не новое право caller задавать arbitrary caps.

## Pegasus: явный наземный срез

Canonical enum `PEGASUS_GROUNDED = pegasus_grounded`, definition ID `pc-book-npc:pegasus_grounded`, source `BOOK-GM-GUIDE:1.1:p176:pegasus_grounded`. Суффикс grounded — **исходный факт сценария**, а не книжная разновидность Pegasus и не новое правило существа.

- Самостоятельный unmounted Brute2/T3Res3, без брони, оружия и shield.
- Natural Hooves Close3d/3 Damage3, hands=null; Athletics4d/4 Protection. Оба pool_cap=null, implicit caps6/8.
- Начинает на земле, все противники действительно Close. NoMove/noExternal source сохраняется весь бой: Pegasus не взлетает и не переносится в midair другой способностью.
- W1 лишает flight и требует land на следующем собственном ходу. В этой сцене он уже на земле; дополнительного действия/движения/unsupported не возникает. W2defeat.

Fly сохраняется в metadata с ограничением начала движения рядом с ground-based enemy. Pegasus Knights требует всадника; он отсутствует. Ни воздушный старт, ни rider/Charge/landing executor этим профилем не разрешаются. Для будущей пространственной сцены ground/air placement должен стать явным spatial source/state, а не выводиться из старого названия loadout.

Такое именование позволяет caller явно подтвердить исходную границу без нового обязательного поля во всех прежних сценариях. Обычный `pegasus` без ground premise в этот срез не добавляется. Неизвестный/частично переименованный source не превращается автоматически в наземный.

## Интеграция и сохранность

Оба профиля проходят существующий PC owner/journal, direct/repeated Staggered, profile-Wound ACK/GM disposition и Warped Form как явные same-side Close targets. Pegasus использует своё noWeapon natural состояние; Ogre не получает чужих Rage/Devour или PC weapon traits. При их defeat сохраняются actual cause и GM disposition выбранного producer.

Новые policies/counters/команды/wire version не нужны. Count search сохраняет полный canonical definition и уже имеющиеся ordered policy filters. Каталог52→54;52прежних entries/definitions/snapshots/metadata и160JSON documents M9–M48 сохраняются без миграции. Добавить один полезный factory/JSON/CLI пример чанка с настоящими результатами.

## Адресная проверка

1. Полные карточки, Armour/natural/gear/printed pools/selected и unselected Abilities/wound bands; независимые fresh graphs; сохранность52прежних профилей.
2. Ogre base2, explicit cap6 отWS3: generic Test с ordinary modifiers достигает6, Help bypass остаётся отдельным, Drained фильтрует бонусы по прежним правилам. Greathammer не получает повторный штраф или PC Traits. Source/schema exact-type/canonical guards для новых6 и прежних8/null.
3. Native direct/repeated-Staggered wounds и поражение обоих Brutes с actual target ACK/GM decision. Pegasus W1 продолжает наземный ход без выдуманного landing action; при0/1Wound не меняются natural Protection/Attack. Warped Form NPC-target path сохраняет те же причины и очередь.
4. Current JSON1 roundtrip/semantic rejection/full echoes, compact trials/count search и один CLI-пример.160старыхJSON допускаются и сохраняют значения; source/offline schema refs проверяются.
5. Адресные PC catalog/admission/cap/Test/Wound/JSON/generation consumers. Процессный backend и доставка не меняются; полного regression/wheel/backend matrix по факту появления ADR нет.

## Согласование

По [AGENTS.md](../../AGENTS.md), раздел «Автономная работа до согласованной вехи»: «Спрашивать при существенной неоднозначности правил, смене согласованного контракта или блокере с решением пользователя». Здесь расширяется ранее ограниченное поле cap и впервые допускается canonical profile с явным ground premise.

Пользователь выбрал оба профиля с указанной узкой границей. Меньшая альтернатива — только Imperial Ogre/Greathammer с cap6, отложив Pegasus до общей spatial модели — отклонена. Число6 следует из книги; выбор касается публичной границы и объёма, не house rule. [Статус](../project-status.md), [очередь](../roadmap.md).

Реализация: [catalog](../../src/towr/domain/pc_npc_catalog.py), [cap admission](../../src/towr/domain/pc_melee_models.py), [schema](../../src/towr/adapters/schemas/pc-melee-common.schema.json). [Native/cap tests](../../tests/unit/test_m49_pc_ogre_pegasus.py), [JSON/trials/search](../../tests/integration/test_m49_pc_ogre_pegasus_json.py), [CLI-примеры](../examples/m49/README.md). Фактическая адресная приёмка и следующий шаг — в [статусе](../project-status.md); новых обязательных полей/метрик/версии нет.
