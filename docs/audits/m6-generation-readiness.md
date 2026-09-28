# Аудит готовности генерации Melee-составов

Дата: 2026-09-29. Контракт: [ADR-0026](../decisions/ADR-0026-melee-composition-generation.md).

**Генерация из явного резерва готова в границе неподвижного numeric Minion-сценария.** Preflight, полная materialization, защита результата и композиция с existing staged evaluator согласованы. Это не готовность общего боя, каталога NPC или внешней Melee JSON/CLI границы. Поэтапная оценка отдельно закрыта [аудитом ADR-0025](m6-staged-evaluation-readiness.md).

## Контракт, реализация и проверки

| Область | Проверено |
| --- | --- |
| Вход | [Frozen/slotted group/request](../../src/towr/application/melee_candidate_generation_models.py), tuple copies, exact IDs/bounds, typed Melee, shared ObjectiveRateWindow и Melee stages. [13 model tests](../../tests/unit/test_m6_melee_candidate_generation_models.py) проверяют TypeError/ValueError, отказ ranged, bool/coercion, frozen/replace, uint64 seed и все stages |
| Резерв | Groups ровно разбивают opposing reserve: без unknown/friendly/omitted/повторных actors. Полные definitions внутри группы равны, включая ID; между группами могут отличаться. Вся perspective-сторона сохраняется. Проверены обе стороны, reversed group reserve и maximum меньше размера резерва |
| Family facts | Отдельный обязательный NpcMeleeScenarioFacts; та же Zone, при can_leave_zone=True требуется adjacent Zone. False не выводится из графа. Caller утверждает применимость ко всем составам и достижимым состояниям. Невыбранные резервисты отсутствуют в конкретном начальном бою |
| Preflight бюджета | C вычисляется произведением диапазонов за вычетом полностью нулевого вектора. C=0, превышение max_candidates и полного staged budget отклоняются до перебора. Проверены 5/250 против 4/249, positive/fixed/zero bounds, keep без повторного роста семейства, огромный C=2**40−1 без materialization/RNG. Seed проверяется одним simulation request |
| Construction | [Генератор](../../src/towr/application/melee_candidate_generation.py) даёт lexicographic prefix-count vectors; нет перестановок, новых actors или dedup. Стабильные candidate/initial IDs. Fresh roster/combat/spatial/policies/objective проходят public scenario admission; сохраняются независимые порядки, immutable snapshots, весь graph, max_rounds, family facts и Staggered choice |
| Решения GM | Полные defeat decisions фильтруются, не создаются заново. Outnumbering True/False сохраняется для каждого actor. [14 construction/result tests](../../tests/unit/test_m6_melee_candidate_generation.py) проверяют identity snapshots/decisions, независимые приоритеты и подмену GM flag/facts/disposition. Numeric bonus не сохраняется в definition |
| Result/source | MeleeCandidateGenerationResult хранит generation source и точный staged input; сверяет common parameters, C, ordered IDs и полный scenario каждой ожидаемой проекции. Проверены foreign/missing/reordered/duplicate composition, profile/facts/GM flag/position/objective/round ID, equal copies и frozen result. Проекции для проверки строятся по одной |
| Ошибки | [MeleeCandidateGenerationError](../../src/towr/application/melee_candidate_generation_errors.py) сохраняет candidate ID/counts и исходный cause/notes. Ошибка второго состава прекращает вызов без partial/retry/skip. BaseException проходит напрямую; ошибки final staged/result constructors не получают вымышленный candidate context |
| Staged integration | [5 integration tests](../../tests/integration/test_m6_melee_candidate_generation.py): пять составов, stages 2/4 keep 2/1, полный budget 18, равные sequential/real-spawn reports и selected IDs. Повтор generation/execution и rename prefix сохраняют seeds/observations; input/global RNG неизменны, дети завершены. Никаких точных Monte Carlo процентов в assertions |
| Динамика боя | Те же integration tests с SequenceRandom проверяют initial 2×1/2×2/2×3, появление бонуса после defeat врага и исчезновение после defeat союзника, True/False approval, +1d ровно один раз, точные pools/RNG calls/defeat decisions. Completed/Staggered союзник считается; defeated исключается existing engine |
| Архитектура | AST-проверка не обнаружила импортов application/balance в domain/engine/simulation. Application строит admitted domain inputs, pure balance получает input/aggregates. Нет нового runner/pool/scheduler/wire; генерация не вызывает RNG, симулятор или IO |

Всего **32 теста ADR-0026**: 13 preflight + 14 construction/result/error + 5 integration. Для существующей обработки стадии/unsupported/error chain дополнительно действует аудит ADR-0025; этот аудит не подменяет его контракт.

## Самостоятельный пример

[melee_balance.py](../examples/m6/melee_balance.py) использует public generator/staged APIs и builder Footpad из [melee_scenario.py](../examples/m6/melee_scenario.py), без tests/private imports. E3 явно добавлен во входной резерв; генератор только выбирает из уже заданных actors. P1,P2 фиксированы, A=(E2,E1) 0..2, B=(E3) 0..1. Получаются пять составов; порядок roster/ходов P1,P2,E1,E2,E3, priorities союзников E3,E2,E1. У P2 bonus approval=False, у остальных True для всего семейства. Disposition=knocked_out, GM approval=True; повторный Staggered → Wound. Family facts заданы отдельно.

Seed 42, три раунда, window=[1/4,1/2,3/4], stages=(8,keep=2),(32,keep=1), max_candidates=5, полный upper budget=5×8+2×32=104. Скрипт сравнивает полные sequential/process reports/selected, проверяет input/global RNG/cleanup и parent source identity. Печатает reserve/groups/facts/policies, deterministic IDs и составы, все stage counts/rates/totals, local selection/continuation и final status/selection. Текстовый stdout не является wire format.

[Сохранённый вывод](../examples/m6/melee_balance.output.txt), Windows/Python 3.14.5: после первого этапа продолжены counts 0,1 и 1,0 (две разные группы с одинаковыми profiles, без dedup). На уточнении каждый дал 26/32=13/16 достижения цели, выше максимума 3/4, поэтому COMPLETED с пустым final selection. Раннее попадание не гарантирует финальный выбор; nearest fallback нет. Это наблюдение конкретного seed/runtime, не гарантия вероятности или preset. Assertions не требуют этого победителя/процента/пустого выбора.

Actual=104 на вызов, sequential+process исполняют 208 trials. Каждый финальный пакет 32 trials начинается с index 0; первые 8 повторяются и оплачены. Counts разных этапов не суммируются в финальную долю, статистическая независимость этапов не заявляется. Общий seed разных составов не означает одинаковых бросков одноимённых атак.

Инъекция generation и staged failures в main примера проверила stderr context, повторный выброс того же исключения, сохранение cause/notes, пустой stdout и отсутствие дальнейшего backend после ошибки. Это проверка оболочки примера; реальные failure boundaries находятся в указанных unit/integration tests.

## Книги и ограничения

Непосредственно перечитаны BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112; The Battlefield / Range, стр. 114; Attack Tests / Attack Modifiers, стр. 118–119; Conditions / Staggered, стр. 123. BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91; Understanding NPC Profiles, стр. 93; Brigands & Footpads, стр. 97. Сохраняются ordinary side order, explicit Close/awareness, текущий outnumbering, допустимый SUFFER_WOUND и решения о defeat. Footpad применим к aware battle: Lurker действует вне боя. Brigand нельзя превратить в обычный numeric Minion удалением Craven Opportunist. Новых Rule IDs/house rules/противоречий нет.

Готовность ограничена явным конечным резервом и неизменными family facts/GM policies. Поддерживаются только prefixes групп, не все сочетания конкретных участников. Если GM approval зависит от состава или достижимого состояния, нужны отдельно подготовленные сценарии/семейства; генератор не угадывает решение GM. PC, movement/Charge/Brawn, mixed battle, новые Abilities и полный каталог вне границы.

Source guards доказывают структурную согласованность проекции, а не истинность facts/GM решений или книжное происхождение произвольного numeric definition. ID уникален внутри одного request; это не глобальный hash/provenance token. Generation result хранит резерв; staged report хранит сценарии, поэтому для трассировки к резерву caller должен сохранить generation result.

Успешный generation result не содержит trial records/RNG/observations, но держит весь исходный резерв и все C начальных сценариев с pairwise policies. Конструктор результата повторяет проекции для проверки. Caps ограничивают количество составов и trials, не RAM, размер входа или время. Проверка огромного C без materialization не обещает возможности исполнить такое семейство. Exception traceback может удерживать промежуточные объекты. Memory/performance нового generator не измерялись; предыдущие simulator benchmarks не являются замерами этого слоя.

## Проверки и следующий шаг

Полная регрессия: **2164 tests OK (148,644 с)**, Windows/Python 3.14.5. Compileall, 1360 локальных Markdown-путей и git diff --check успешны. Команды записаны в [project-status.md](../project-status.md#последняя-проверка). Пример исполнился в двух режимах; full reports/selection и бюджет совпали. Production src/tests/tools в этом аудите не менялись. Python 3.12/другие ОС, wheel и новые benchmarks не проверялись; commit/push не выполнялись.

Пользователь выбрал следующий этап: **JSON/CLI для Melee**. Первый законченный шаг — ADR-0027 внешней границы simulation и balance: версии/discriminators и команды, явные numeric scenarios/reserve/facts/GM policies, execution options/seed/stages/budget, aggregate/staged outputs и typed errors, Schema/adapters/application/CLI boundaries и матрица допустимых/отклоняемых примеров. Сначала контракт, затем отдельные реализации. Существующие ranged v1 wire/CLI сохраняются; новых боевых правил, автоматических approvals, каталога или universal rules engine этот этап не добавляет.
