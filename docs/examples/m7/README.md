# M7: контракт смешанного боя

[ADR-0028](../../decisions/ADR-0028-mixed-minion-scenario.md) описывает отдельный неподвижный numeric Minion-сценарий с Melee/Close и Shooting/Medium. Production-вход и полный исполнитель пока не реализованы.

[mixed_contract_probe.py](mixed_contract_probe.py) проверяет совместимость existing public K1/M2 APIs на трёх фиксированных примерах. Он явно задаёт пары/дальности, осведомлённость, видимость, отсутствие применимых дополнительных правил, решения GM и недоступность отхода. Close не вычисляется по общей Zone.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m7/mixed_contract_probe.py
```

Проверки: Medium shot → Close attack с пулами 3/4 и 13 RNG calls; пять промахов с 30 RNG calls и Staggered только у Close-атакующих; после поражения последней Close-цели — NO_CANDIDATE без повторного RNG и исполнения slot. Это детерминированная проверка композиции, не Monte Carlo и не новый wire API.

Источники: BOOK-PLAYER-GUIDE 1.4, Equipment / Ranged Weapons, стр. 94; Rules / Range, стр. 114; Attack Tests / Failed Attacks / Attack Modifiers, стр. 118–119. BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91; Understanding NPC Profiles, стр. 93; Brigands & Footpads, стр. 97. Используются числовые проекции Footpad Dagger и Brigand Warbow; полный Brigand Melee с Craven Opportunist не поддержан.

Probe не является валидатором arbitrary input, не запускает полный battle loop и не доказывает ещё не реализованные mixed result/source guards. Следующий срез — typed admission и детерминированные проверки его границ.
