# Тестирование

Правила проверяются детерминированно через заданные последовательности d10. Monte Carlo-тесты не должны зависеть от точного процента побед.

Основная команда:

```powershell
$env:PYTHONPATH = "src"
py -3.12 -m unittest discover -s tests -v
```

Минимальные группы тестов M1:

- валидация профиля и особое правило одного куба;
- все исходы встречной проверки;
- границы `damage` относительно RES;
- обычное накопление stagger и ограниченный stagger за промах;
- сброс stagger при ране;
- немедленное завершение боя и отсутствие хода погибшего;
- одновременная гибель;
- предел раундов;
- воспроизводимость seed.

Группы K1 Test kernel:

- Characteristic + Skill и готовый inline-профиль NPC;
- динамический предел в два значения Characteristic и явное исключение из предела;
- книжное минимальное правило, когда модифицированный пул стал меньше одного;
- таблица результата Basic Test;
- обязательный Grim и добровольный Glorious с явной decision policy;
- отмена Grim и Glorious и запрет повторного переброса;
- фиксированные модификаторы успехов и полный `RollTrace`;
- победа по успехам, контекстный tie-break и отдельный результат `0:0` для Opposed Test.

Группы K1 Attack/Impact:

- попадание при ненулевой ничьей и промах при `0:0`;
- обязательный успех unopposed атаки;
- Damage из базового значения и разницы/общего числа успехов;
- профильный коэффициент Damage за успех;
- строгая граница `Damage > Resilience` для Wound;
- временное игнорирование брони и фазовые модификаторы Damage/Resilience;
- Staggered атакующего только за промах в Close Range и только при отсутствии состояния.
- `DamageImpactSpec` без изменения обычного Damage/Resilience поведения;
- Condition вместо Damage без фиктивных числовых значений;
- повторный Staggered replacement через общую decision policy;
- Hazard вместо Damage как typed exposure с рейтингом и Skill;
- replacement impact не применяется при промахе.

Группы K1 Hazards:

- успехи, равные рейтингу, полностью избегают Hazard;
- shortfall задаёт базовые кубы Wounds Table до untreated Wounds;
- shortfall становится числом Wounds для профильных NPC;
- Condition-only Hazard не создаёт Wound;
- failure Conditions применяются после Wound и не отменяются Near Miss;
- результат постороннего Test нельзя передать другой экспозиции.

Группы K1 Secondary effects:

- secondary effects не срабатывают при промахе;
- Prone применяется до repeated-Staggered и тем самым запрещает Give Ground;
- конкретный эффект может исключить Monstrosity;
- Blunderbuss создаёт typed request для других существ в Close Range от цели;
- multi-target request ставится после последствий основной цели;
- Rule ID применённых secondary effects сохраняются в результате.

Группы K1 Staggered:

- первое получение состояния без дополнительного выбора;
- явная decision policy при повторном Staggered;
- Give Ground не чаще раза за раунд и только при допустимом перемещении;
- запрет Give Ground и повторного Prone для уже лежащей цели;
- автоматический запрос Wound, если других вариантов нет;
- сохранение Staggered до окончательного принятия или отмены Wound.

Группы K1 Injury и сквозного kernel:

- все границы Wounds Table от `1–3` до `27+`;
- один куб плюс untreated Wounds и фазовые модификаторы, минимум один куб;
- смертельные результаты, снятие Staggered и сохранение состояния при Near Miss;
- общая policy Player/Champion;
- Minion, профильный лимит Brute/Monstrosity и преобразование extra table die в Wound;
- владелец решения Monstrosity Wound/Reaction для обоих порогов Damage;
- полный путь `Attack → Impact → Staggered/Wound → state + follow-ups`;
- отсутствие скрытого выбора при Glorious, повторном Staggered, Near Miss и Monstrosity Reaction.

Группы K1 Wound effects:

- явная спецификация каждой строки Wounds Table `1–27+`;
- однократное применение строки и сохранение источника/срока каждого эффекта;
- безусловные Conditions, ограничения до Treat/Heal и постоянные последствия;
- порядок немедленных consequences и Endurance Test;
- успешный и неуспешный Endurance с Condition либо внешним consequence;
- обе ветви обязательного выбора `Spilling guts`;
- сквозная фиксация `WoundEffectResult` в результате kernel.
