# Аудит ограниченной mixed generation (M7)

Дата: 2026-09-29. Контракт — [ADR-0033](../decisions/ADR-0033-mixed-composition-generation.md), сценарий — [ADR-0028](../decisions/ADR-0028-mixed-minion-scenario.md), staged оценка — [ADR-0032](../decisions/ADR-0032-staged-mixed-evaluation.md) и её [аудит](m7-staged-evaluation-readiness.md).

Генератор готов в границе явного конечного резерва неподвижных numeric Minions. Group/request, construction/result/error, integration и самостоятельный пример согласованы с контрактом; production исправлений не потребовалось. Этот вывод не означает поддержку произвольного mixed боя, движения, смены оружия или каталога Abilities.

## Матрица контракта и реализации

| Область | Проверенная реализация и свидетельства |
| --- | --- |
| Типы и резерв | [Models](../../src/towr/application/mixed_candidate_generation_models.py), [15 tests](../../tests/unit/test_m7_mixed_candidate_generation_models.py): frozen/slotted, tuple copies из tuple/list, exact nonempty IDs/bounds, полный partition противоположной стороны, одинаковые полные definitions внутри группы. Все perspective actors фиксированы; обе стороны поддержаны. Set/mapping/string/iterator, foreign family, overlap/missing/friendly/unknown actors отклоняются |
| Family facts/pairs | Facts и полный ordered tuple пар передаются отдельно, без default из template. Пары должны точно совпадать с template, включая порядок/ориентацию; равные копии допустимы. Facts и GM policies утверждаются caller для всего семейства и его достижимых состояний. Невыбранные reserve actors отсутствуют в конкретном начальном бою, а не скрыты/defeated/ожидают вступления |
| Preflight бюджета | C — произведение размеров диапазонов минус all-zero vector; C=0/max_candidates и весь staged budget проверяются до перебора. Проверены 4/240 против 3/239, расширенный C=5/250, fixed/all-zero bounds, keep без повторного роста, огромный C=2**40−1 без enumeration/projection/RNG. Seed admission вызывается один раз |
| Construction | [Generator](../../src/towr/application/mixed_candidate_generation.py), [17 tests](../../tests/unit/test_m7_mixed_candidate_generation.py): lexicographic prefix-count vectors/IDs без all-zero, перестановок, новых actors или dedup. Сохраняются независимые roster/combat/turn/spatial/pair/policy/target orders, original snapshots/definitions, весь graph, round budget, отдельные facts, полные decisions и True/False outnumbering/can_leave_zone flags |
| Mixed admission | Каждый subset заново проходит public NpcMixedScenario constructor: обе роли, начальная доступная цель каждого actor, отсутствие Close-врага у Warbow, все enemy pairs/Zone constraints и objective. Реальный bow-only subset без Close-цели отклоняется первым либо после двух допущенных составов; удаление единственного Shooting actor также отклоняется. Ни silent skip, ни уменьшение C, ни partial result не допускаются |
| Result/source | MixedCandidateGenerationResult сохраняет generation source и exact staged input. Проверяет общие seed/stages/budget/window, C, ordered IDs и полную ожидаемую projection каждого вектора. Проверены foreign/missing/reordered/duplicate composition, подмена pairs/order/orientation, profile, policies/flags/decisions, geometry/objective/round ID; equal copies и frozen/no records. Для проверки проекции строятся по одной |
| Ошибки | [Error](../../src/towr/application/mixed_candidate_generation_errors.py) сохраняет candidate_id/counts, исходный __cause__ и его notes. Второй admission failure прекращает вызов; BaseException проходит напрямую. Final staged/result constructor errors не получают вымышленный candidate context. Нет retry/fallback |
| Staged integration | [6 tests](../../tests/integration/test_m7_mixed_candidate_generation.py): четыре generated candidates → stages 2/4 keep 2/1, равные полные sequential/real-spawn reports и selection. Repeat/rename prefix сохраняют seeds/observations/выбранные составы после нормализации source IDs. Scripted промахи подтверждают полный budget 4×2+2×4=16 на backend; natural observations не закреплены точными процентами |
| Динамика боя | Те же tests проверяют шесть generated составов с local 2:1/2:2/2:3 и удалёнными стрелками. Точные trace/pools/RNG calls, True/False GM approvals, изменения 2:2→2:1 после поражения врага и 2:1→1:1 после поражения союзника, полные disarmed_and_surrendered acknowledgements. Удалённые стрелки не увеличивают численность другой Zone; Shooting не получает Melee-бонус |
| Границы | Application собирает domain snapshots; balance получает input/aggregates. AST-проверка domain/engine/rules/simulation не обнаружила зависимостей на application/balance. Генератор не вызывает RNG, симуляцию, pool или I/O. Новых executors/scheduler/wire нет |

Всего **38 tests ADR-0033: 15 preflight + 17 construction/result/error + 6 integration**. Прежние сценарные и staged tests продолжают проверять весь execution/unsupported/source-chain контракт; этот аудит не подменяет их отдельные границы.

## Самостоятельный пример

[mixed_balance.py](../examples/m7/mixed_balance.py) использует public generator/staged APIs и builder из [mixed_scenario.py](../examples/m7/mixed_scenario.py), без imports из tests/private helpers. E3 явно добавлен во входной резерв до генерации. Pbow@rear и P1/P2@arena фиксированы; A=(E2,E1) Footpad Dagger @arena, counts 1..2; B=(E3) Brigand Warbow @far, counts 0..1. Получаются четыре состава. Graph — треугольник rear/arena/far; enemy pairs заданы явно Close/Medium, полного совпадения Zones недостаточно для вывода Close.

Приоритет союзников E3,E2,E1 отличается от roster/actor/group orders. У P2 outnumbering approval=False/can_leave_zone=True, у остальных True/False соответственно. Эти решения действуют для всего семейства; они не выбраны по численности. Defeat=knocked_out/GM approved, повторный Staggered→Wound. Все actors — Minions, включая сторону players_and_allies; нет PC stats, auto awareness или нового ruling.

Seed 42, два раунда, окно [1/4,1/2,3/4], stages=(8,keep=2),(32,keep=1), max_candidates=4; upper budget=4×8+2×32=96 на вызов. Скрипт сравнивает полные sequential/process reports/selected, проверяет parent source identity, input/global RNG и cleanup. Process workers=2/batch_size=5. Печать начинается только после двух успешных вызовов и проверок: резерв, facts/pairs/policies, составы и IDs, все четыре исхода/доли этапов, local selection/continuation и final selection/budget. Текстовый stdout не является wire format.

[Сохранённый вывод](../examples/m7/mixed_balance.output.txt), Windows/Python 3.14.5: на первом этапе варианты с E3 имеют unsupported и исключаются. Counts 1,0 и 2,0 получают по 7/8 целей, вне окна, но продолжаются для уточнения. На последнем этапе 1,0 даёт 30/32=15/16 целей, выше максимума 3/4; 2,0 даёт 24/32=3/4 целей и 4 unsupported. Итог COMPLETED с пустым выбором: unsupported исключает второй состав даже на границе окна, первый вне окна. Нет nearest fallback или гарантированного подходящего состава. Это наблюдение конкретного seed/runtime, не гарантированная вероятность/preset и не ожидаемый победитель assertions.

Actual=planned=96 на каждый backend, всего 192 trials на запуск. Каждый stage заново начинает trial index 0; prefix оплачен повторно. Counts этапов не складываются в финальную вероятность и не объявляются независимыми. Два проверочных запуска окончательного скрипта из корня и отдельного cwd дали одинаковый stdout и пустой stderr (384 trials суммарно).

Проверка ошибок через main:

- Реально допущенный source с A.minimum=0/C=5/budget=104 отклоняется при первом subset (0,1), где Melee actors теряют Close-цели. Stderr содержит candidate/counts/cause, stdout пуст, evaluator не вызывается.
- Инъекция ошибки второго этапа после 32 реальных trials первого сохраняет stage_index=1, фактический candidate ID, bounded→root cause с notes. Main пробрасывает исключение, stdout пуст; process backend после неуспешного sequential не запускается. Input/global RNG/children сохранены.

## Книги и ограничения

Непосредственно перечитаны BOOK-PLAYER-GUIDE 1.4, Equipment / Ranged Weapons, стр. 94; Rules / Combat/Ambush, стр. 112; The Battlefield / Range, стр. 114; Attack Tests / Attack Modifiers, стр. 118–119; Conditions / Staggered, стр. 123. BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91; Understanding NPC Profiles, стр. 93; Brigands & Footpads, стр. 97. Footpad Lurker относится к Awareness вне боя, Brigand Craven Opportunist — к Melee: в примере используется только Warbow, ветка Axe не подключается. Новых Rule IDs/house rules/противоречий нет.

Наличие обеих ролей/начальных целей, stationary facts и точные ordered family pairs — техническая область поиска, не новые правила книги. Префиксы групп не перебирают все сочетания конкретных actors. Для отличающихся геометрии, оружия, поведения или решений GM нужны другие явно подготовленные сценарии/семейства. Движение, PC, новые Abilities и полный каталог вне границы.

Admission полного резерва не гарантирует допустимость всех subset; preflight C/budget не фильтрует плохие векторы. Успешная генерация гарантирует начальный admission, но не отсутствие unsupported_path во всех будущих trial states. Потеря доступной цели в бою сохраняется как технический unsupported, а не поражение или разрешение на автоматическое ожидание/перемещение.

Source guards проверяют структурную согласованность, не истинность facts/GM decisions или книжное происхождение произвольного numeric definition. Caller сохраняет generation result для трассировки к резерву; staged report хранит входные сценарии. IDs локальны для request, не глобальные content hashes. Результат хранит все C сценариев и пары/policies; caps ограничивают число составов/trials, но не RAM, размер исходного резерва или время. Tracebacks могут удерживать промежуточные объекты. Предыдущие simulator benchmarks не являются измерениями генератора.

## Проверки и следующий шаг

Полная регрессия: **2515 tests OK (300,008 с)**, Windows/Python 3.14.5. Все 665 исходных src/tests/tools файлов неизменны. Команды и итог записаны в [project-status.md](../project-status.md#последняя-проверка). Проверены standalone пример в двух cwd/обоих backend, error boundary, AST imports, SHA-256 существовавших src/tests/tools, compileall, Markdown-пути и diff/whitespace. Production src/tests/tools в этом аудите не менялись; новых unittest tests нет. Python 3.12/другие ОС, installed wheel и новые benchmarks не проверялись. Commit/push не выполнялись.

Пользователь выбрал следующее направление: **JSON/CLI для смешанного боя**. Следующий законченный срез — контракт внешней границы simulation/balance по образцу ADR-0027: отдельные версии/discriminators/команды, явные mixed facts/pairs/policies и резерв, budgets/seed/stages/execution, aggregate/staged outputs и typed errors, Schema/adapters/application/CLI boundaries и конечные примеры. Существующие ranged/Melee formats сохраняются. Сначала контракт, реализация отдельно; новых боевых правил и автоматических approvals этот этап не добавляет.
