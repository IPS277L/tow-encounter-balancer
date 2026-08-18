# Трассировка правил

Таблица связывает источник, нормализованное правило, реализацию и проверку.

| Rule ID | Источник | Статус | Код | Тесты | Примечание |
|---|---|---|---|---|---|
| RULE-TEST-001..004, 006 | Player’s Guide, 68, 106–110 | implemented | `domain/test_models.py`, `rules/test_resolution.py`, `rules/opposed_test.py` | `test_k1_test_resolution.py`, `test_k1_opposed_test.py` | Книжный Basic/Opposed pipeline и trace |
| RULE-TEST-005 | Player’s Guide, 108, 117 | draft | будущая Help orchestration поверх `SuccessModifier`/`DiceModifier` | новые тесты ещё не написаны | Помогающий сначала выполняет собственный Test |
| RULE-COMBAT-001..004 | Player’s Guide, 111–118 | draft | `engine/battle.py` требует пересмотра | текущие integration tests проверяют прототип | Turn/action economy |
| RULE-COMBAT-005..009 | Player’s Guide, 68, 92–97, 117–119 | implemented | `domain/attack_models.py`, `rules/attack_resolution.py`; выбор профиля пока передаётся вызывающей стороной | `test_k1_attack_resolution.py` | Одна opposed/unopposed атака, промах, Damage/Resilience и обычный impact |
| RULE-HEALTH-001..004 | Player’s Guide, 97, 112, 119–123 | partially implemented | Resilience в `attack_resolution.py`; Staggered в `condition_models.py` и `stagger_resolution.py`; принятие Wound ещё впереди | `test_k1_attack_resolution.py`, `test_k1_stagger_resolution.py` | Обычный impact и допустимые варианты повторного Staggered |
| RULE-HEALTH-005..007 | Player’s Guide, 112, 118, 121–123, 190–191 | draft | будущие injury/recovery policies | текущие P1 health tests не нормативны | Wounds Table, типы NPC и Recover |
| RULE-NPC-001..011 | GM Guide, 89–91; Player’s Guide, 191 | draft | новая injury policy и NPC profile model | новые тесты ещё не написаны | Типы NPC, Protection, атаки, Monstrosity |
| RULE-EFFECT-001..010 | Player’s Guide, 73–81, 92–97, 111–112; GM Guide, 89–185 | draft | фазовые `RuleEffect`, decisions и follow-ups в K1 | новые тесты ещё не написаны | Сквозная классификация Talents, оружия и NPC Abilities; не полный каталог |
| RULE-ENCOUNTER-001..003 | GM Guide, 60–62 | draft | будущие encounter objective и retreat policies | будущие simulation tests | Книжные ориентиры, не точная формула |
