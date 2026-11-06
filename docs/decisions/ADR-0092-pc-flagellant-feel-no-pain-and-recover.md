# ADR-0092: два Flagellant loadouts, Feel No Pain и собственный Recover

Дата: 2026-11-06. Статус: **принято пользователем и реализовано в M47**. Выбран полный Feel No Pain + Recover для обоих loadouts.

## Источники

BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Flagellant122: Normal Brute2, WS3/T3/Res3 без брони, Athletics3d/3 Protection. Flails Close3d/4 Damage6/2H получают−2d Melee, пока Flagellant Staggered. Hooks and Chains Close3d/4 Damage3/1H этого штрафа не имеют. Default2, Melee4, Endurance5, Willpower5. W0 напоминает возможность Wound вместо Staggered, W1 — heal Wound через Recover, W2defeat.

Unbreakable даёт прямую immunity к Broken. Feel No Pain разрешает Wound вместо Staggered; Wounded Flagellant автоматически лечит одну Wound, когда выполняет Recover. BOOK-PLAYER-GUIDE1.4, гл.V Rules / Recover118: standard Recover снимает Staggered и Prone с выбранного себя/союзника, а альтернативные treatment/condition Tests заменяют стандартные benefits. Автоматическое лечение от отдельной Ability срабатывает при самом Recover, поэтому предлагаемый standard self Recover сохраняет обычное снятие собственных Staggered/Prone и лечит одну собственную Wound.

BOOK-PLAYER-GUIDE1.4, гл.V Attack-Staggered119: слабый hit накладывает Staggered, повторный требует выбрать цену; промах Close добавляет Staggered только при его отсутствии. GM Brutes92 не бросают PC Wounds Table. Feel No Pain не требует Endurance Test, PC Wounds Table, инструментов или treatment.

## Принятый полный срез

Два canonical профиля:

| Enum / wire ID | Attack | Общие свойства |
|---|---|---|
| FLAGELLANT_FLAILS / flagellant_flails | Close3d4Damage6/2H;−2d Melee при Staggered | Brute2/T3Res3/noShield, Athletics3d3 |
| FLAGELLANT_HOOKS_CHAINS / flagellant_hooks_chains | Close3d4Damage3/1H | Brute2/T3Res3/noShield, Athletics3d3 |

Definition IDs `pc-book-npc:<wire ID>`, sources `BOOK-GM-GUIDE:1.1:p122:<wire ID>`. Fixed оружие выбирается до боя, второе сохраняется unselected. Ordinary Attack/Protection caps6, explicit pool_cap=null. PC Flail Traits/повторные weapon penalties не добавляются.−2d относится только к Staggered Flails Melee, сохраняется при Drained и не меняет Hooks/Protection.

## Явная тактика

Принят required `npc_flagellant_policies` в native `PcMeleeScenario` и текущем PC JSON1: exact tuple/list закрытых `PcFlagellantPolicy` записей с уникальным actor ID, только canonical opposition Flagellants обоих loadouts.

```json
"npc_flagellant_policies": [
  {
    "actor_id": "flagellant1",
    "feel_no_pain": "wound_at_zero",
    "recover_when_wounded": true
  }
]
```

`feel_no_pain` — закрытый enum `decline` / `wound_at_zero`; `recover_when_wounded` — exact bool. Все поля обязательны, default не подставляется. `[]` означает отказ от обеих новых тактик у всех Flagellants сцены. Actor без записи продолжает нынешний Attack и не выбирает Feel No Pain. Count search удаляет запись исключённого actor без переназначения; порядок caller сохраняется в echo.

**Рекомендуемый выбор Feel No Pain:** когда actor с0Wounds должен впервые получить Staggered от incoming physical Attack либо собственного miss, заменить это получение одной профильной Wound. При1Wound такую добровольную замену не выбирать, поскольку она дала бы defeat. Это выбранная осторожная тактика, а не ограничение текста Ability только здоровыми Flagellants. Прочие моменты произвольного решения при уже имеющемся Staggered не включаются. Повторный Staggered сохраняет прежнюю SUFFER_WOUND price strategy; W2defeat не отменяется. Политика не заменяет прямую Wound от сильного hit и не прибавляет к ней вторую.

**Рекомендуемый Recover:** живой actor с1Wound и `recover_when_wounded=true` выбирает в свой обычный ход standard self Recover; иначе Attack по прежнему target priority. Снимаются собственные Staggered/Prone и автоматически лечится одна Wound1→0. Recover занимает один обычный slot/action, оставляет обычный TurnEnd, не даёт Attack в том же ходу, не тратит RNG или PC Fate. NPC/PC ally benefits, objects/mounts и общий NPC treatment не добавляются. Defeated actor не лечится и не возрождается; у0Wounds эта тактика Recover не выбирает.

Новый случай должен учитываться прежним NPC Help: если именованный beneficiary в этом раунде выберет Recover, helper использует свой Attack fallback, поскольку конкретного Melee Test получателя не будет. Остальные Help choices, Drained/free-success правила и PC стратегии сохраняются. Это необходимое взаимодействие нового действия, не общий оптимальный AI.

## Источник и порядок последствий

Incoming Staggered replacement задаётся явно до разрешения Attack через узкое typed rule/spec, связанное с canonical Flagellant, выбранной policy и актуальным W0. Raw HIT/Damage/impact сохраняются фактическими; отдельное решение объясняет, почему Staggered outcome привёл к profile Wound. Нельзя задним числом подменить завершённый обычный Attack либо накладывать и Staggered, и выбранную вместо него Wound.

Для miss используется его настоящий pending `AttackerStaggerRequest` и actor, а не NPC target предыдущей PC Attack. Typed proof содержит actual miss, точное profile-Wound result и его ACK. Обе ветви сохраняют однократность, removal Staggered раной, Wound/defeat/disposition и полный source prefix. Текущий `PcProfileWoundProof` исходит из раны target атаки; собственная miss-Wound не должна маскироваться под эту причину.

Recover имеет собственные typed request/result/receipt и полный before/after profile state, резервирует/исполняет настоящий Recover slot и применяет heal ровно один раз. W1↔W0 может повторяться в разные ходы; история действительных получений и лечений не сводится к одному текущему числу ран. Подмена heal без Recover, повтор receipt, чужой actor/source, незавершённая Wound перед действием и выдуманное end-turn лечение отвергаются.

Unbreakable относится к **значению Broken**, независимо от psychological classification. Использовать узкое canonical правило допуска/применения Conditions для этих двух профилей; не выдавать им immunity ко всем психологическим effects или к Staggered/Prone/Drained. Текущая fixed сцена не создаёт нового источника Broken против NPC; инвариант Flagellant не допускает injected Broken. Общая миграция Troll/spell/social Condition provenance и полная библиотека immunities этой функцией не требуются.

## Публичные результаты и совместимость разработки

Добавить отдельные NPC Recover costs по существующему образцу NPC Help: source-ordered `npc_recover_action_counts`, aggregate `npc_recover_action_trial_count` и `total_npc_recover_action_count`. Реальный NPC Recover входит в total executed actions; PC self/ally Recover counters остаются своими. Feel No Pain follow-up не считается новым действием. Compact records не получают journal или специальный набор raw dice.

Current PC JSON1 остаётся1.152прежнихJSON documents M9–M46 обновляются required пустыми policy arrays и нулевыми NPC Recover counters в соответствующих источниках/results; остальные наблюдения сохраняются.49прежнихcatalog entries не меняются. Новые поля обновляются одновременно в schema/codec/result validation/examples/tests, без compatibility defaults и нового deprecated периода.

## Отклонённая меньшая альтернатива

Добавить оба loadouts и Feel No Pain с тем же выбором Wound только при0, сохранив NPC Attack-only. Тогда NPC Recover/новые Recover counters не входят в M47, `recover_when_wounded` не вводится; automatic heal сохраняется как способность с невыбранным Recover trigger. Это меньшая законченная граница, но не демонстрирует книжное самолечение Flagellant. При выборе этой альтернативы переписать контракт вокруг неё до реализации.

## Проверенная граница

1. Exact catalog/full sources обоих loadouts, caps/hands/Resilience/Abilities/Wound bands; сохранность49прежнихentries.−2d Flails при Staggered, ordinary cap/minimum-one/Drained и отсутствие штрафа Hooks/Protection.
2. Required exact policies/enum/bool/unique actor/source/roles, closed schema, cached aliases до RNG; `[]`, независимые несколько actors, filtering без переназначения и полные root/candidate echoes.
3. Literal incoming weak hit и own miss W0→W1 вместо Staggered, declined branch, W1 отказ от самоубийственной замены, direct Wound без второй, repeated Staggered/W2disposition и незавершённые source guards. Miss cause не подменяет target предыдущего Attack.
4. Настоящий NPC Recover slot/receipt/standard self benefits+heal1→0, action cost/TurnEnd/no RNG, отсутствие same-turn Attack, no heal0/no revive, повторный цикл ранения/лечения и запрет replay/подмены actor/source.
5. Canonical direct Broken immunity/injected source checks при сохранении других Conditions; NPC Help fallback при выбранном Recover, прежние PC Recover/Help/Fate/Wound paths.
6. Native → compact trials/summary → count search → current JSON1/CLI, точные NPC Recover counts, сохранение остальных152JSON значений. Общий Stagger/Wound/owner/Recover seam требует адресного checkpoint этих подсистем; степень расширения определить по итоговому diff. Одна representative process parity новой policy/record shape; full project regression/wheel/полная backend matrix только при отдельном основании.

Согласование получено от пользователя; оно требовалось по [AGENTS.md](../../AGENTS.md), раздел «Автономная работа до согласованной вехи»: «Спрашивать при существенной неоднозначности правил, смене согласованного контракта или блокере с решением пользователя». Здесь выбираются voluntary Feel No Pain/NPC Recover, расширяются source/result контракт и взаимодействие с Help. [Статус](../project-status.md), [очередь](../roadmap.md).

Реализация: [policy](../../src/towr/domain/pc_flagellant_policy_models.py), [typed miss/recover](../../src/towr/domain/pc_flagellant_models.py), [K1](../../src/towr/rules/stagger_impact_resolution.py), [projection](../../src/towr/domain/_pc_melee_projection.py), [stats](../../src/towr/simulation/pc_melee_models.py), [CLI-примеры](../examples/m47/README.md).49новыхtests:12K1,9catalog,19native,8JSON/statistics/search,1process. Расширенный checkpoint109модулей/1044tests дал1038успехов и6Windows Pipe WinError5 в sandbox; только эти6 затем повторены вне sandbox вместе с новым process case —7tests OK за17.364s. Это составная адресная проверка, не единый зелёный full run. Найденный при review пропуск exact type readmission в miss-Wound witness исправлен и покрыт регрессией. Точные команды/ограничения/следующий шаг — в [статусе](../project-status.md).
