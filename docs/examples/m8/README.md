# Первый контракт интеграции магии M8

[ADR-0035](../../decisions/ADR-0035-cowardly-flight-casting-boundary.md) задаёт границу одного Casting-действия с Curse of Cowardly Flight. Production M8 admission/executor ещё нет. Существующие mixed JSON/CLI не принимают мага или spell.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m8/casting_contract_probe.py
```

Пример использует public K1 APIs и локальный scripted RNG. Он связывает action receipt, post-Test/CAST/WAIT, target preflight и конкретный Zone/Willpower effect. Первая активация даёт 1 success и WAIT; следующая получает returned magic state, добавляет 2 successes и создаёт CV3 spell с Potency2. Одна Minion-цель сопротивляется, другая получает Broken. Они находятся в изолированной Zone без пути Give Ground; это явный контекст, а не запрет движения по воле resolver.

Проверяются также нулевая Potency при достаточных накопленных successes, пустая Zone, равенство/превышение Wizard Level и отказ повторного слота/чужого actor до RNG. Все 24 d10 заданы явно, каждый использован ровно один раз. При обязательном Miscast сохраняются активное Casting state и pending roll; выбор немедленного spell, preparation, таблица и очистка пула не исполняются.

Числа caster `3d/3`, Level 2 и целей `3d/3` — authored inputs для проверки композиции, не профиль Hermit Witch или полный персонаж. Caster здесь не получает Minion injury model. Две активации заданы caller; полного battle loop, промежуточных ходов, следующего хода Broken, objective или Monte Carlo оценки нет.

Источники: **BOOK-PLAYER-GUIDE 1.4**, Rules / Combat Actions, стр. 116–117; Magic in the Old World / Casting a Spell, Spell Potency, Miscasts, стр. 155–159; Formal Spells, стр. 160; Battle Magic / Curse of Cowardly Flight, стр. 162; Conditions / Broken, стр. 122. **BOOK-GM-GUIDE 1.1**, Allies and Antagonists / Champions, стр. 92; Hermit Witch/Daemonologist, стр. 130–131. Hermit Witch и Daemonologist остаются Champions; этот пример не переписывает их профили.

Следующий шаг — typed input models/preflight ADR-0035. Проверка полного battle scenario с магией потребует отдельного контракта после этого узла интеграции.
