# M63: PC Melee/Athletics против Close Shooting

В прежних явных policy PC выбирает навык для защиты от близкого выстрела. В automatic_combat после ADR-0124 законная защита выбирается автоматически. Без настройки действует прежний порядок Defence с рабочим shield, иначе Athletics. [Правило](../../rules/combat.md#pc-close-shooting-protection-m63), [принятый контракт](../../decisions/ADR-0105-pc-close-shooting-protection-choice.md).

Optional поле participant текущего PC JSON1:

```json
"close_shooting_protection_skill": "melee"
```

Допустимы `melee` и `athletics`; null/`defence`/прочие Skills не принимаются. Athletics выбирается и при held shield. По PG94 Melee opposition в Close доступен без отдельного weapon requirement. Для учёта рук принята fixed тактика: использовать пригодный active held weapon/grip, иначе защищаться без рук. Выбор не подбирает dropped предмет и не меняет оружие/loaded state. Throwing/Net, Brawn и incoming Melee сохраняют прежнюю защиту.

Melee Test получает общие Traits фактически удерживаемого оружия, но не Sword/Glaive Defence bonus или Attack-only Warhammer bonus. Нет counterattack/дополнительного action/Damage/расхода PC Pistol. Injury12 учитывает использованный grip; без рук новый Critical не создаётся. Действуют Drained/Blinded/W10/Fate и прежние mandatory Wound tails.

Protection Help теперь допускает:

```json
"help_policy": {
  "beneficiary_id": "pc2",
  "target": "first_incoming_protection",
  "skill": "melee"
}
```

Это настоящий Melee Help Test и обычное действие. Receipt адресуется конкретному NPC Protection Test, отдельно от `target:"attack"`. Неподходящий/неисполненный Test не переносит бонус. После ADR-0124 first-current-NPC тактика пропускает известный по текущему loaded state Reload. Будущие исходы и NPC Help она не предсказывает. В прежней explicit policy Pistol-PC не выбирает роль helper, но получает помощь в защите. Новый automatic mode допускает также [Помощь Стрельбе (Shooting Help)](../dynamic/README.md#стрельба-персонажей).

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m63/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m63/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): Sword+Shield PC1 помогает Staff+Shield PC2, который защищается Melee; PC1 для своей Shooting-защиты выбрал Athletics. Ogre действует первым среди NPC, Official имеет прежний explicit Broken exit. После исправления Help/Reload в ADR-0124 текущий CLI result для seed42/6trials/8rounds:6objective/0party defeated/0limit/0unsupported,82actions,28started/22completed rounds, без потерь PC.7PC Help, Official выходит в2trials.

Receipt по-прежнему адресуется конкретному Protection Test и не усиливает Dexterity Reload. Если NPC уже известен как unloaded, helper ищет первый действительно предстоящий Attack; если такого Test нет, действует его согласованный fallback. Поправка убрала заведомо неиспользуемую помощь в старом примере. Проверка со старым selector на том же seed воспроизводит прежние4objective/2limit/133actions/44Help, подтверждая причину изменения.

[Balance request](pc-melee-balance.request.json) и [CLI result](pc-melee-balance.result.json): Ogre1/Official0–1,2состава по2trials. После исправления: без Official2objective/23actions/2Help; с ним2objective/28actions/2Help. PC choice/Protection Help остаются в полном root/candidate source. Удаление последнего shooter также сохраняет party preferences; их неиспользование допустимо.

Выборки демонстрационные и не оценивают истинную вероятность/оптимальный состав. Unaware/другие ranges/general inventory не добавлены. Native NPC source мигрирован на ranged; появились npc_ranged_counts. Это текущий JSON1 без compatibility-ветки, canonical NPC definitions сохранены.
