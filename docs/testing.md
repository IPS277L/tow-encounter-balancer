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
- основная цель и повторные secondary target IDs отклоняются;
- вторичные цели разрешаются слева направо с последовательным RNG;
- каждая цель использует собственный Stagger context и decision request ID;
- Player/Champion используют Wounds Table, а Minion/Brute/Monstrosity — профильные Wounds;
- Near Miss сохраняет исходное Staggered вторичной цели.
- after-Give-Ground Condition не срабатывает на первом Staggered или при другом выборе;
- Give Ground follow-up всегда предшествует Condition follow-up;
- отложенный reducer применяет Condition без преждевременной мутации состояния;
- тот же after-Give-Ground эффект доступен вторичным целям.
- Condition-on-hit требует обычный Damage и не срабатывает при промахе;
- Damage/Staggered/Wound полностью разрешается до on-hit Condition;
- Near Miss отменяет Wound, но сохраняет дополнительный Condition попадания;
- on-hit Condition появляется до отложенного Give Ground → Condition.
- Terrifying ставит Broken после Give Ground либо фактически принятой Wound;
- Near Miss, первый Staggered и Fall Prone не запускают Terrifying;
- условие принятой Wound одинаково работает в kernel и для профильной вторичной цели.

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
- Monstrous Flight после выбора Reaction возвращает Give Ground либо профильную Wound в зависимости от Give Ground в текущем ходу;
- Give Ground от Monstrous Flight сохраняет предпочтение вертикальной midair-зоны и ставит Terrifying после движения;
- Wound от повторной Monstrous Flight проходит общую профильную injury policy, включая дополнительные Wounds и Terrifying;
- полностью невозможный Give Ground завершается явной ошибкой неоднозначности, а не скрытым исходом;
- Unsteady сохраняется kernel как конкретный Reaction spec без строковой диспетчеризации;
- новое падение Giant накладывает Prone, сохраняет Staggered и создаёт Athletics Hazard (3) для всех существ в его Zone;
- уже Prone Giant не падает повторно и не создаёт повторный Zone Hazard;
- Give Ground context отклоняется для Unsteady как неприменимый к этой Reaction;
- Zone Hazard batch обязан включать реагирующего и иметь уникальные target/Test IDs;
- выбранные Zone-цели проходят Test и Hazard слева направо на общем RNG с отдельными trace и состояниями;
- Zone Hazard executor передаёт Test/Wound decisions, injury policy и failure Conditions в общие resolvers;
- Monstrous Regeneration сохраняется kernel как конкретный Reaction spec;
- Reaction Ghorgon/Troll Hag не меняет injury state и создаёт ровно один source-aware запрет регенерации на следующий ход;
- suppression не маскируется Condition и не запускает Terrifying;
- сохранённый suppression пропускает ближайшее end-turn окно, не вызывает decision provider и возвращается ровно один раз как consumed;
- suppression погашается даже при нуле Wounds, поэтому не переносится на более поздний ход;
- без suppression лечение требует решения Actor, блокируется при отсутствии неогненной Wound и уменьшает Wounds ровно на 1;
- Ghorgon/Troll Hag получает Staggered только при его отсутствии, а уже Staggered Monstrosity продолжает иметь право на лечение;
- Mother Knows Best даёт обычный +1d Casting modifier только при 0 Wounds и не обходит предел пула;
- Long Range и once-per-round снимки закрывают недоступную NPC Wizard opposition без готового Test result;
- завершённая opposition обязана содержать ожидаемые Casting/Willpower Test IDs, а её исход не влияет на подсчёт девяток Troll Hag;
- девятки создают typed увеличение собственного Miscast Pool, отсутствие девяток всё равно расходует round budget, а переброшенная исходная девятка отклоняется;
- немонтированный Bone Dragon при Reaction автоматически получает профильную Wound;
- Liche/Tomb King открывает явный выбор владельца Monstrosity между доступными Wound, Give Ground и Prone;
- недоступные Give Ground/Prone исключаются до decision policy, а неподдерживаемый выбор отклоняется;
- Give Ground и Wound от Undead Monstrosity запускают Terrifying, тогда как Prone не запускает;
- общий Condition application блокирует только совпавшую явную классификацию источника;
- психологическая иммунность сохраняет source/blocking Rule IDs и не удаляет уже существующий Condition;
- Bone Dragon блокирует психологический replacement Condition до прямого/Staggered reducer;
- одно значение Broken без психологической классификации не активирует иммунитет;
- психологический Condition-on-hit блокируется после обычного impact без отмены самого impact;
- Terrifying после принятой Wound блокируется без отмены Wound;
- Fearsome переносит classification/immunity через Give Ground follow-up и блокируется только после движения;
- Bone Dragon Reaction переносит immunity и блокирует психологический Terrifying после профильной Wound;
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
