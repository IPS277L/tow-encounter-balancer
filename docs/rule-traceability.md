# Трассировка правил

Таблица связывает источник, нормализованное правило, реализацию и проверку.

| Rule ID | Источник | Статус | Код | Тесты | Примечание |
|---|---|---|---|---|---|
| RULE-TEST-001..006 | Player’s Guide, 68, 106–110 | draft | `domain/stats.py`, `rules/dice.py`, `rules/opposed_roll.py` требуют пересмотра | текущие unit tests проверяют прототип | Базовые Test rules |
| RULE-COMBAT-001..004 | Player’s Guide, 111–118 | draft | `engine/battle.py` требует пересмотра | текущие integration tests проверяют прототип | Turn/action economy |
| RULE-COMBAT-005..009 | Player’s Guide, 68, 92–97, 117–119 | draft | `domain/actions.py`, `engine/resolution.py` требуют пересмотра | новые тесты ещё не написаны | Атаки, защита, урон |
| RULE-HEALTH-001..007 | Player’s Guide, 97, 112, 118–123, 190–191 | draft | `rules/health.py`, `domain/combatants.py` требуют замены | текущие health tests конфликтуют с книгой | Resilience, состояния и Wounds |
| RULE-NPC-001..011 | GM Guide, 89–91; Player’s Guide, 191 | draft | новая injury policy и NPC profile model | новые тесты ещё не написаны | Типы NPC, Protection, атаки, Monstrosity |
| RULE-EFFECT-001..010 | Player’s Guide, 73–81, 92–97, 111–112; GM Guide, 89–185 | draft | фазовые `RuleEffect`, decisions и follow-ups в K1 | новые тесты ещё не написаны | Сквозная классификация Talents, оружия и NPC Abilities; не полный каталог |
| RULE-ENCOUNTER-001..003 | GM Guide, 60–62 | draft | будущие encounter objective и retreat policies | будущие simulation tests | Книжные ориентиры, не точная формула |
