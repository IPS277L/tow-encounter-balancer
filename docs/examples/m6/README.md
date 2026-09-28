# Проверка совместимости для контракта M6

[ADR-0021](../../decisions/ADR-0021-melee-minion-scenario.md) определяет будущий неподвижный Melee Minion-сценарий. Его production-вход и run_npc_melee_scenario реализованы; этот первоначальный probe по-прежнему проверяет только низкоуровневую композицию. [contract_probe.py](contract_probe.py) использует только уже существующие public K1/M2 constructors и executors, без импорта tests.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m6/contract_probe.py
```

Ожидаемый вывод:

```text
Footpad 2x2: attack dice 3 -> 4 after defeat; 2 attacks, 13 RNG calls; 4 rejections OK
```

Источник профиля: BOOK-GM-GUIDE 1.1, Allies and Antagonists / Brigands & Footpads / Footpad, стр. 97: Dagger Close 3d/3, Damage 2, Athletics 3d/3, RES 3. Lurker относится к Awareness вне боя. В примере явно заданы Close всех вражеских пар, осведомлённость, отсутствие высоты/прочих эффектов и решение GM применять обычный бонус численного преимущества (BOOK-PLAYER-GUIDE 1.4, Rules / Attack Tests / Attack Modifiers, стр. 118–119). Физическая возможность Give Ground здесь задана False; её не выводят из выбора Wound или неподвижной тактики.

Две настоящие атаки и два подтверждения GM/exclusion меняют 2:2 на 2:1, затем 2:0. Следующий actor/раунд после последнего поражения не запускается. Проверены неизменность входа, ровно два execution IDs и 13 RNG calls. Отклоняются acknowledgement с чужой Attack, повторное acknowledgement, нулевой и boolean бюджет.

Это небольшой fixture для проверки существующих компонентов. Он не проверяет `NpcMeleeScenarioFacts` (их допуск покрыт отдельными unit/integration tests), не является автономным Melee runner, не поддерживает произвольные профили/раскладку и не доказывает факты GM. Полная матрица будущего admission и execution находится в ADR; game engine и ranged v1 этим примером не расширены.
