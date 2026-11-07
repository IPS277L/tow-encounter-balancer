# ADR-0093: Skin Wolf, Blood Rage и Warped Form в end phase

Дата: 2026-11-06. Статус: **принято и реализовано M48**. Пользователь выбрал полный Skin Wolf, одну собственную цену Staggered с волной остальным и NPC-focus Brewguard=Skin Wolf. Исходная рабочая копия была чистой после пользовательского commit `872dbe0` (M47).

## Источники и новый профиль

BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Skin Wolf187: Fast Brute3, WS5/T4/Res5 armoured, Claws and Fangs Close5d/3 Damage5/natural, Athletics4d/3 Protection. W0 без дополнительного эффекта, W1–2 Warped Form, W3defeat. Blood Rage позволяет перед Attack добровольно получить Staggered при его отсутствии; любой Staggered Skin Wolf получает+1d Melee.

Warped Form: в конце своего хода не-Staggered Skin Wolf может получить Staggered и вылечить одну Wound; при этом Staggered получают все creatures в Close Range. Огневую Wound регенерировать нельзя. BOOK-PLAYER-GUIDE1.4, гл.V Range114 различает Close и нахождение в одной Zone; Staggered119/123 задаёт повторную цену и снятие Condition при получении Wound, Near Miss112 сохраняет право PC отрицать Wound после table roll. Heal сам по себе не является получением Wound и не снимает заплаченный Staggered.

Реализован canonical `PcBookNpcProfile.SKIN_WOLF = skin_wolf`, ID `pc-book-npc:skin_wolf`, source `BOOK-GM-GUIDE:1.1:p187:skin_wolf`. Natural attack hands=null/noWeapon/noShield, Armour bonus1. Ordinary caps10/8, explicit pool_cap=null. Нет PC weapon Traits, mounted/Charge или общего shapeshifting.

## Принятый публичный контракт

Текущий `npc_blood_rage_actor_ids` расширить только canonical Skin Wolf, сохранив Bestigor. Прежняя семантика выбора/typed pre-Test proof/+1d от фактического Staggered не меняется. Bestigor W1 Glorious не переносится Skin Wolf. Отсутствие Skin Wolf в Rage list не отключает бонус от Staggered, полученного из иной причины.

Добавить обязательный `npc_warped_form_policies` в native `PcMeleeScenario` и текущий PC JSON1. Это exact tuple/list закрытых записей для уникальных opposition Skin Wolves:

```json
"npc_warped_form_policies": [
  {
    "actor_id": "skin_wolf1",
    "close_actor_ids": ["pc1", "pc2", "flagellant_flails1"],
    "npc_defeat_decisions": [
      {
        "attacker_id": "skin_wolf1",
        "target_id": "flagellant_flails1",
        "disposition": "killed",
        "gm_approved": true
      }
    ]
  }
]
```

Наличие записи означает выбор Warped Form всякий раз, когда она доступна в собственную end phase. `[]` явно отказывается от этой optional способности. Запись не добавляет второго action, NPC Recover или Test. Профиль/actor/enum/bool/IDs readmit до RNG, default не подставляется.

`all_opponents_close` доказывает Close PC↔NPC, но не NPC↔NPC. Поэтому `close_actor_ids` — явный **полный** неизменный список остальных близких creatures и порядок разрешения их последствий. Он содержит всех source PCs ровно по одному; остальные source NPCs включаются только по подтверждённому Close факту. Caster в этот список не входит: он платит собственный Staggered один раз и не является целью волны. Неизвестные IDs, дубли и пропуск обязательного PC отвергаются. Для двух настроенных Skin Wolves факты Close друг к другу симметричны; противоречащие списки отвергаются.

`npc_defeat_decisions` использует existing typed GM disposition shape, с attacker_id именно caster. Записи покрывают NPC из close list в том же относительном порядке; для PCs они не нужны. Если NPC погиб от волны, PC не приписывается фиктивный финальный удар. Dirty Coward/fleeing defeat сохраняет собственную причину, а не подменяется выбранным killed. Defeat и подтверждённая смерть различаются.

В момент activation owner фиксирует source-bound ordered snapshot допустимых целей: confirmed dead PCs, defeated NPCs и exited NPCs исключаются, живой Defenceless PC остаётся. После snapshot цель не переназначается другой. При count search исключённые NPC удаляются из close lists/decisions, а запись исключённого caster удаляется полностью; party фиксирована. Отсутствие NPC в close list означает факт дальности, а не возможность игнорировать известную близкую цель.

## Тактика и порядок end phase

В пределах current fresh physical melee source нет огневых ран: выбранные PC weapons и поддержанные Staggered/Wound producers не наносят огневого урона. Это проверяемая граница текущего среза, а не общий has_non_fire=true для будущих spells/fire effects. Начальные неизвестные раны/внешние effects не допускаются.

У живого Skin Wolf с1–2Wounds, без Staggered и с policy в собственную end phase:

1. Завершить действие, его Wound/Fate и прочие mandatory continuations.
2. Подтвердить один typed Warped Form source, заплатить собственный Staggered и heal ровно одной неогненной Wound; сохранить отдельные cost/heal before/after facts.
3. Зафиксировать ordered target snapshot и последовательно разрешить Staggered каждой цели, заканчивая все её Wound/Fate/Endurance/body/profile follow-ups до перехода к следующей.
4. Закрыть обычный TurnEnd и только затем оценить terminal outcome/следующий ход.

Собственная возможность Warped Form существует **один раз на фактическую end phase**, даже если дальнейшие последствия снова сделали состояние формально подходящим. Не создаётся цикл повторного heal по неизменившимся Wounds/Conditions. W0/already Staggered/defeated actor не активирует способность; revival и лечение в чужой ход не допускаются. Отказ/недоступность не мешают обычному TurnEnd.

Рекомендуемые публичные примеры включают Skin Wolf в Warped Form list и исключают его из voluntary Rage list. Обе настройки независимы: caller может включить обе, но приобретённый перед Attack Staggered естественно блокирует лечение в конце этого хода. Автоматический оптимальный выбор между атакующим бонусом и лечением не подставляется.

Если Attack убила последнего PC, выбранная доступная end phase всё равно завершается: живые близкие NPC могут получить последствия волны. Уже начатая волна не обрывается из-за промежуточной смерти последнего PC. Неподдержанная обязательная body/GM ветвь сохраняет фактический prefix и UNSUPPORTED_PATH; будущие цели не считаются исполненными. Полные phased receipts предшествуют terminal result; generic clock не получает исполняемый effect bus.

## Self inclusion — принята одна собственная цена

GM187 отдельно задаёт собственный Staggered как цену и затем говорит all creatures in Close Range, без явного other. PG114 отдельно не разрешает, является ли сам источник целью этой волны.

**Выбранная пользователем конкретизация:** caster платит Staggered один раз, волна применяется к остальным creatures из close list. Себе он повторный Staggered не наносит. Это интерпретация формулировки для данного источника, не дословное уточнение книги.

Альтернатива: после cost/heal caster получает ещё один Staggered как первая цель волны, затем следуют close_actor_ids. При current SUFFER_WOUND price это даст ему Wound, отменяя net heal и снимая Staggered самой раной. Ограничение одной activation на end phase сохраняется; повторно активировать способность в том же ходу нельзя. Этот вариант отклонён пользователем; target discovery не включает caster.

## Последствия волны и существующие правила

Это непосредственный Staggered effect, а не Attack Test: нет fake attacker/Protection rolls, Damage или Devour бонуса к Wounds Table от Melee. Defenceless сам по себе не превращает первое Staggered в Wound: условие auto-Wound от successful Attack здесь отсутствует. Повторный Staggered разрешается по прежней выбранной цене SUFFER_WOUND.

PC Wound проходит настоящую Wounds Table/Near Miss/немедленные body effects и сохраняет pending owner конкретной цели. NPC Minion/Brute Wound имеет новый effect source/target-scoped ACK, а не причину последней PC Attack. Работают Dirty Coward/drop/fleeing defeat, profile W1 Conditions Merchant/Official/Big ’Un/Centigor и прочих, Bestigor W1 entitlement и actor-specific expiry. Non-Attack W1 Bestigor связывается с typed wave cause; поле Attack source не заполняется фиктивным ID.

M47 Feel No Pain `wound_at_zero` предлагается распространить на Staggered от этой волны: здоровый unstaggered canonical Flagellant с выбранной policy получает одну Wound вместо первого Staggered. Его последующий Recover остаётся обычным собственным действием; wave не лечит/не выполняет Recover за него. Unbreakable/другие Conditions не меняют значения.

## Brewguard: принят NPC focus

Первая рана Brewguard от повторного Staggered волны имеет NPC-causer и не является обычной PC Attack. GM104 не уточняет отдельно такой источник для W1 Attacker inflicts Distracted. M42 конкретизировала first actual Wound/focus/death в прежней PC-only сцене.

**Выбранное пользователем расширение:** focus — Skin Wolf, вызвавший эту Wound. Отдельный typed wave-W1 source сохраняет этот факт; PC attack-W1 source и Miner encounter source не подменяются. Brewguard получает−1d против остальных участников; поскольку его текущие цели — PCs, штраф применяется к их Melee/Protection. Ранивший caster сохраняет роль focus независимо от дальнейшей тактики.

Confirmed смерть NPC focus доказывается actual defeat ACK с GM disposition `killed`; knocked_out/disarmed_and_surrendered не означают смерть и не снимают focus. PC focus сохраняет прежнюю Near Miss/Defenceless/death семантику. NPC focus не появляется автоматически у других Distracted producers. Оставшаяся W1 не накладывает эффект заново.

Меньшая граница: сохранить настоящую Wound и остановить trial перед неразрешённым Brewguard W1/focus follow-up как UNSUPPORTED_PATH. Дальнейшие цели/TurnEnd не исполняются. Это честная ограниченная поддержка нового сочетания; NPC focus тогда не вводится в M48. Этот меньший вариант отклонён пользователем.

## Метрики, сохранность и развитие контракта

Добавить source-ordered `npc_warped_form_counts`, aggregate `npc_warped_form_trial_count` и `total_npc_warped_form_count`. Считается фактически выполненная cost/heal activation, включая observed prefix остановленного trial; одна activation лечит одну Wound до последствий волны. Это не action и не NPC Recover. Wave targets/Wound rolls не попадают в compact records/journal. ПК-потери/Fate и прочие counters сохраняются по фактическим завершённым последствиям.

В M47 действует lower bound2×NPC Recover≤total actions, поскольку каждая heal требовала отдельного предшествовавшего Attack. Warped Form может одной activation ранить несколько Flagellants, поэтому для нового source shape такой lower bound неприменим. Обновить validation по реальным action costs/round budgets, сохранив строгие роли/типы/нулевые значения остальных NPC и прежние ограничения в источниках без этой возможности. Не приписывать новой wave дополнительные actions ради прохождения старого bound.

Current PC JSON1 остаётся1;156старыхJSON documents M9–M47 мигрируются required пустыми Warped policies/нулевыми новыми metrics, остальные значения сохраняются.51прежнихentries неизменны, каталог станет52. Новое правило не требует wheel: resource discovery прежний; source/offline refs проверяются адресно. Никаких compatibility defaults/старых wire branches.

## Адресный план проверки

1. Exact Skin Wolf source/natural/Armour/caps/Abilities/Wound bands; сохранность51entries, prior Bestigor Rage/Glorious и прочих canonical guards.
2. Required exact policy/Close facts/order/GM dispositions, все source PCs, same-side snapshot/симметрия, roles/aliases/duplicates до RNG; subset filtering без переназначения и полные root/candidate echoes.
3. Literal Blood Rage/natural Staggered bonus, available/declined/end-phase healing, cost Staggered не исчезает от heal, no action/no RNG/no revival, once per end phase и отсутствие второго TurnEnd. Взаимная несовместимость pre-Attack Rage и heal следует из actual Conditions.
4. Несколько ordered PC/NPC targets, первый/повторный Staggered, Near Miss/Defenceless, NPC W1/defeat/Dirty Coward/Feel No Pain/Bestigor, chosen Brewguard boundary. Каждый target source и pending lifecycle проверяется отдельно; skip/replay/замены порядка/пропуски целей отвергаются.
5. Pending work/expiry и завершение уже начатой волны после смерти последнего PC; точный unsupported prefix, без притворного завершения остальных targets.
6. Compact metrics/Recover bound/PC losses/Fate/count search/current JSON1/CLI, migration156JSON, одна representative process parity. Выбрать checkpoint end phases/Stagger/Wounds/PC/summary и ближайших зависимостей по итоговому diff; full project/wheel/backend matrix только при отдельном основании. На Windows отделять реальные process tests от sandbox WinError5, не повторять успешную тяжёлую часть.

Согласование получено по [AGENTS.md](../../AGENTS.md), раздел «Автономная работа до согласованной вехи»: «Спрашивать при существенной неоднозначности правил, смене согласованного контракта или блокере с решением пользователя». Здесь меняются source/result, NPC end-phase/target policy, подтверждение non-Attack NPC causes и две конкретизации текста. [Статус](../project-status.md), [очередь](../roadmap.md).
