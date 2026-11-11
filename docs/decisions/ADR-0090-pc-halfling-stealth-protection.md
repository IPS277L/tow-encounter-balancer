# ADR-0090: Halfling Thief и книжное разрешение Stealth Protection

Дата: 2026-11-06. Статус: **принято пользователем и реализовано в M44**. Выбран полный Dagger/Stealth срез.

## Источники

BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Halfling Thief103: Normal Minion, T2/Res2 без брони, Dagger Close2d/3 Damage1/1H, Protection Stealth3d/5. Now You See Me разрешает Stealth для Oppose атак, о которых Thief знает. Skills: Default3, Dexterity4, Stealth5, Charm4. Printed характеристики: WS2/BS4/S2/T2/I5/Ag3/Re3/Fel4. Полная карточка адресно перечитана вместе с Understanding NPC Profiles93.

BOOK-PLAYER-GUIDE1.4, гл.V Rules / Attack Tests118: обычная защита Athletics либо Defence при подходящем вооружении; unaware и Defenceless не могут Oppose. Специальное разрешение Thief расширяет выбор Skill для осознаваемой атаки, не отменяя Defenceless. Это книжная Ability, не новый house rule.

Throwing Knives Short4d/3 Damage2/1H сохраняются unselected. Полный Thieving Blighter позволяет исчезнуть без cover/concealment и при Move Quietly пытаться украсть не удерживаемый trapping/Asset/Coin в Close через Dexterity против Awareness владельца. Fixed Attack/noMove сцена не вызывает эти условия; способность сохраняется в metadata.

## Принятая публичная граница

Добавить canonical `PcBookNpcProfile.HALFLING_THIEF_DAGGER = halfling_thief_dagger`, definition ID `pc-book-npc:halfling_thief_dagger`, source `BOOK-GM-GUIDE:1.1:p103:halfling_thief_dagger`. Выбранный loadout: Dagger-only, Stealth Protection, без щита. Printed числа используются напрямую, без PC Dagger Traits/повторного weapon penalty. Attack/Protection pool_cap=null, обычные вычисляемые caps4/6.

В **текущем PC JSON1** существующее поле `definition.protection.skill` допускает `stealth` только у этого canonical loadout. Schema связывает исключение с canonical ID/source; native admission дополнительно проверяет полный неизменённый definition graph и source IDs. Authored NPC и все прежние loadouts сохраняют Athletics/Defence. Новый Skill не становится свободным выбором для PC, Help или Glorious policy.

Новых JSON полей, версии, счётчиков и обязательных policy не требуется. Существующие140JSON documents M9–M43 и43catalog entries остаются без миграции. Count search использует обычное включение/исключение Thief; источник каждого кандидата содержит полный выбранный профиль.

## Разрешение Protection

Низкоуровневые `NpcProtectionProfile` и `ProtectionTestOption` смогут представлять Stealth. Представление само по себе не разрешает его выбирать: `ProtectionPreparationRequest` получает отдельное typed разрешение Now You See Me, связанное с defender ID и полным canonical NPC definition. Без него выбранный Stealth отвергается. Свободный boolean либо строка Rule ID не заменяют подтверждённый источник; универсальная система произвольных Skill overrides не вводится.

PC owner создаёт это разрешение только для фактического защищающегося Thief и сохраняет его в source proof. Preparation проверяет canonical источник, actor и numeric base profile выбранного Test; applied rule trace содержит `RULE-PROFILE-PEOPLES-002:now-you-see-me`. Replay проверяет разрешение вместе с прежним полным prefix, а не доверяет cached alias. Обычная Athletics/Defence/Melee eligibility остальных участников сохраняется.

Awareness и Defenceless проверяются прежде выбора opposition: unaware либо Defenceless остаётся unopposed, без Stealth Test и без применения разрешения. Ability не требует оружия или щита для самого Stealth. В текущем fixed PC-сценарии awareness уже явно true; добавлять скрытые атаки, исчезновение или автоматическую смену тактики не требуется. Thief продолжает Attack по существующему NPC priority и защищается выбранным printed Stealth.

Общий Protection слой не зависит от CLI/JSON/балансировщика. Проверка конкретного разрешения использует типизированные доменные данные; metadata Abilities не исполняются как текст. Политики grudge/Help/extra Attack и NPC Conditions сохраняют прежние границы.

## Альтернативы

- **Рекомендовано:** полный Dagger/Stealth loadout и source-bound разрешение выше. Один профиль проверяет новую общую Protection механику; это обоснованное исключение из ориентира каталожных чанков3–5.
- Отложить M44 и выбрать другую законченную функцию из backlog. Замена printed Stealth на Athletics либо отключение применимой Ability не предлагаются.

## Проверенная граница

1. Catalog/source: все printed числа, caps, noShield/Minion, полные обе Abilities и unselected Throwing Knives. Сохранность43прежнихentries.
2. K1 Protection: Stealth с точным permission, запрет без него/при чужом defender/изменённом source/profile; unaware/Defenceless unopposed; независимость от armed/shield; applied rule trace. Сохранить обычную eligibility и Close ranged Melee exception.
3. Native PC: actual PC Attack использует Thief Stealth3d5, обычный cap/модификаторы и source replay; последующий NPC Attack по прежней стратегии. Несколько Thieves и состав без них; нет скрытых дополнительных actions/RNG.
4. Current JSON1/schema/full echoes: canonical-only Stealth в обоих requests и candidate/result sources, malformed/forged definitions/aliases отвергаются до RNG; прежний authored Athletics/Defence остаётся доступным.
5. Native → trials/summary → count search → JSON/CLI-примеры. Адресные K1 Protection/NPC preparation/roster и PC проверки по зависимостям: меняется общий Protection seam. Полный project regression/wheel/backend matrix только при отдельном основании, не автоматически из-за ADR.

Согласование получено от пользователя; оно требовалось по [AGENTS.md](../../AGENTS.md), раздел «Автономная работа до согласованной вехи»: «Спрашивать при существенной неоднозначности правил, смене согласованного контракта или блокере с решением пользователя». Здесь расширяется публичное значение Protection Skill и native preparation новым source-bound разрешением. [Очередь](../roadmap.md), [статус](../project-status.md).

Реализация: [typed permission/eligibility](../../src/towr/domain/protection_models.py), [catalog](../../src/towr/domain/pc_npc_catalog.py), [PC owner](../../src/towr/domain/pc_melee_result_models.py), [schema](../../src/towr/adapters/schemas/pc-melee-common.schema.json). [Catalog](../../tests/unit/test_m44_pc_halfling_catalog.py), [Protection](../../tests/unit/test_m44_halfling_protection.py), [native/replay](../../tests/unit/test_m44_pc_halfling_execution.py), [JSON/trials/search](../../tests/integration/test_m44_pc_halfling_json.py) дают27новыхtests. Единый checkpoint89модулей/840tests OK за41.405s включает PC M9–M44 и ближайших K1/M2/M6/M7/M8 Protection consumers; это не полный project regression. [CLI-примеры](../examples/m44/README.md), фактические команды/следующий шаг — в [статусе](../project-status.md).

## Pistol admission M59

Адресная сверка GM103 подтвердила, что Now You See Me относится ко всем aware attacks, включая Shooting. Общий typed permission/K1 eligibility и range/weapon/shield matrix уже поддерживали это в M44; после M54 оставалось только отдельное ограничение Pistol preflight. В M59 canonical Thief допускается через тот же полный actor/definition permission, без общего Stealth override, новых полей/версии/тактики. Actual Shoot/Reload/mixed party и source replay проверены; Unaware/Defenceless остаются без opposition, автоматический Thieving Blighter не добавлен. [Правило](../rules/combat.md#pc-close-shooting-protection-m59), [CLI](../examples/m59/README.md).
