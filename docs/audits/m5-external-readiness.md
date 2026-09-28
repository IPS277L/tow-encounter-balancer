# Итоговый аудит JSON/CLI M5

Дата: 2026-09-28. Рабочее дерево на старте чистое. Проверены [ADR-0020](../decisions/ADR-0020-ranged-balance-json-v1.md), application/adapters/CLI, packaged schemas, tests и examples. Production-код, тесты и зависимости в этом аудите не менялись.

**Внешний запуск первого M5 готов в заявленной границе:** `towr balance INPUT` принимает явный резерв неподвижных numeric ranged Minions и возвращает полную агрегированную оценку составов либо отдельный error envelope. Это завершение внешнего слоя над [готовым typed M5](m5-readiness.md); полноценная PC-группа, ближний бой, движение и полный NPC-каталог этим выводом не объявляются готовыми.

## Матрица внешнего контракта

| Обязанность | Реализация | Свидетельство | Вывод |
| --- | --- | --- | --- |
| Структура request/result/error и локальные refs | [Три balance Schema](../../src/towr/adapters/schemas/), [validator](../../src/towr/adapters/ranged_json_schema.py); reuse неизменённого M4 scenario/facts/execution/seed | [JSON unit](../../tests/unit/test_m5_ranged_balance_json.py): `test_all_packaged_schemas_and_five_contract_examples`, unknown/missing request/result/error fields; installed probe | Выполнено; Schema не заменяет lexical/domain/source validation |
| Строгий ввод и preflight до генерации | [Shared reader](../../src/towr/adapters/_ranged_json_common.py), [scenario codec](../../src/towr/adapters/_ranged_scenario_json.py), [balance parser](../../src/towr/adapters/ranged_balance_json.py) | JSON unit: strict tokens/Unicode/duplicates/versions/seeds, explicit facts, group definitions/partition/ranges, stages/C/budget без materialization | Выполнено; facts резерва и всего семейства обязательны отдельно, автоматической осведомлённости/LOS нет |
| Immutable command и точная цепочка источников | [Command/result](../../src/towr/application/ranged_balance_models.py), existing generation/staged models | JSON unit: copied orders/frozen/foreign source, missing/reordered stage reports, unrepresentable placement order; [JSON integration](../../tests/integration/test_m5_ranged_balance_json.py) с разными definitions/независимыми orders | Выполнено; encoder сохраняет выразимый input без потери значений и порядков, не принимает произвольный report JSON |
| Aggregate-only output, окно и отбор | [Result encoder](../../src/towr/adapters/ranged_balance_json.py), existing assessment/continuation | JSON unit: exact Fraction/canonical normalization, все четыре исхода, ties, outside-window continuation, early stop/final unsupported, saved output из typed fixtures | Выполнено; каталог всех составов и все исполненные stage reports сохранены, records/journals не выходят в JSON |
| Application orchestration и backend | [Service](../../src/towr/application/ranged_balance_service.py) над existing generation/staged APIs | [12 service/error unit](../../tests/unit/test_m5_ranged_balance_service.py): exact options/source/type, success/early stop; 2 JSON integration в real sequential/spawn | Выполнено; один generation → staged вызов, штатный RNG и явный backend |
| Фазы ошибок и остановка без partial result | [Errors](../../src/towr/application/ranged_balance_errors.py), [error encoder](../../src/towr/adapters/ranged_balance_json.py) | Service/error unit: known/unknown context, cause/notes, interrupts, error examples; [2 failure integration](../../tests/integration/test_m5_ranged_balance_service.py): второй состав и late trial после полного первого этапа | Выполнено; candidate/counts/stage передаются при известном контексте, retry/fallback и partial reports отсутствуют |
| CLI file/stdin/UTF-8/exit protocol | [CLI](../../src/towr/cli.py), guarded [module](../../src/towr/__main__.py), console entry point | [8 CLI unit](../../tests/unit/test_m5_balance_cli.py) и [6 subprocess tests](../../tests/integration/test_m5_balance_cli.py): input/usage/pool/I/O, Unicode, closed stdout/stderr, no second JSON, unexpected encoder failure | Выполнено для локального процесса; byte delivery при I/O failure не атомарна |
| Установка, examples и регрессия simulate | [JSON-примеры/команды](../examples/m5/json/README.md), installed package, прежние M4 tests | Сопоставлены все 299 Python/Schema-файлов installed package с текущим src; module/console × sequential/process вне repo без PYTHONPATH; полный unittest набор | Выполнено в Windows / CPython 3.14.5; остальные платформы/runtime этим аудитом не проверены |

Внешнему слою M5 соответствуют **52 теста: 42 unit + 10 integration**: JSON 22+2, service/errors 12+2, CLI 8+6. В сумме с 69 тестами исходного typed M5 это **121 тест: 103 unit + 18 integration**. Два JSON integration уже используют новый service и не посчитаны повторно. Десять M3 summary tests относятся к M3 и в 121 не включены.

## Связь с четырьмя критериями roadmap

| Критерий M5 | Готовность typed API | Готовность внешнего слоя |
| --- | --- | --- |
| Ограничения кандидатов | Group partition/count prefixes, C и staged budget, повторное admission каждого состава | JSON явно задаёт reserve/groups/family facts/max_candidates/max_total_trials; ошибки до materialization либо отдельный generation_failed |
| Конфигурируемые окна сложности | Подтверждённая доля достижения цели за лимит, точный Fraction window | minimum/target/maximum без defaults/presets; знаменатель всех rates — все trials; unsupported observations не исчезают |
| Этапный поиск и оценка | Полные повторные пакеты, пригодные outside-window могут продолжать, exact stage chain | Полный echo input, каталог candidate IDs/count vectors, stage reports/status/planned и actual trials; ранняя остановка — допустимый полный result |
| Несколько лучших кандидатов | Последний этап, только внутри окна, точное distance и stable tie order | Итоговые selected IDs отделены от промежуточных selected/continuation; пустой выбор не заменяется произвольным кандидатом |

Все четыре критерия закрыты для конечной области supplied резерва. Не утверждаются глобальный оптимум, вероятность победы полноценной PC-партии или статистическая гарантия попадания сложности в окно.

## Источники и граница правил

Для примера напрямую перечитан локальный extracted text:

- **BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91:** поражение при одной Wound и выбор последствия атакующим с решением ведущего. Сохранённые KNOCKED_OUT/gm_approved — явный input примера, не автоматически принятые решения генератора.
- **BOOK-GM-GUIDE 1.1, Allies and Antagonists / Understanding NPC Profiles, стр. 93:** готовые числовые Attack/Protection, выбор одной Attack и отсутствие автоматического переноса всех PC weapon benefits по имени оружия.
- **BOOK-GM-GUIDE 1.1, Allies and Antagonists / Brigands & Footpads / Brigand, стр. 97:** пример использует Warbow 3d/3, Dam 3, Medium–Long/2H, Athletics 3d/2 и armoured Resilience 4. Craven Opportunist относится к Melee; пример с Shooting не является полным исполнением Brigand или всего каталога.
- **BOOK-PLAYER-GUIDE 1.4, Rules / The Battlefield / Zones, Position, Range, стр. 114:** Medium соответствует соседней Zone, но сам граф не доказывает видимость/осведомлённость или точное положение внутри Zone. Эти facts остаются явными.

Нормализованные правила и трассировка: [NPC](../rules/npcs.md), [трассировка](../rule-traceability.md), граница автономного сценария — [ADR-0013](../decisions/ADR-0013-ranged-minion-scenario-input.md). Новых игровых правил, house rules или расхождений в проверенном срезе не выявлено. Метрика, window, count enumeration и JSON/CLI — ранее согласованные application policies, не новые правила книги.

## Практические ограничения

- Поддерживается прежний свежий stationary numeric Shooting Minion-сценарий; наличие K1 primitives для других типов, Melee, движения, оружия и эффектов не расширяет его admission автоматически.
- Генератор выбирает префиксы supplied групп, не клонирует участников, не подбирает stats/позиции/AI и не выводит applicability family facts из полного резерва. Меняющиеся с численностью дополнительные правила требуют другого контракта.
- Процессорное время/память не ограничены hard quotas; вход и output хранятся в памяти. Max_candidates и max_total_trials — числовые budgets, не таймаут или byte limit. Нет streaming/checkpoint/cancellation protocol, shared persistent pool и auto backend selection.
- Все повторные пакеты входят в actual budget. Shared seed prefixes и адаптивный отбор не делают этапы независимыми; confidence intervals/presets/target duration не добавлены.
- Source checks доказывают согласованность объектов, но не происхождение профиля из книги, истинность caller facts или RNG provenance произвольного low-level result. Runtime metadata не является hash кода. Result importer и доказательство replay на иных версиях Python не обещаны.
- Exit 0 означает завершённую оценку, включая no_eligible_candidates/пустой выбор/unsupported observations. Ошибки исполнения не превращаются в игровые исходы. При I/O failure полный stdout не гарантируется; частично доставленные bytes нельзя использовать как complete result.

## Следующий этап

**Решение пользователя, 2026-09-28:** после M5 расширять боевую симуляцию; первый шаг — ограниченный контракт ближнего боя Minions с проверкой по книгам. Это направление записано как M6 в [roadmap](../roadmap.md), не как уже реализованная механика.

Следующий законченный срез — ADR-0021: определить минимальный допустимый Melee-сценарий и явный positional/engagement context, Attack/Protection, обязательные последствия промаха и повторного Staggered, политику outnumbering/дополнительных NPC rules, цель/лимит/остановки. Сопоставить existing K1/M2 entry points и потребности executor; показать допустимый/отклоняемый вход на existing constructors. Ограничения могут исключать неподдержанные ситуации, но не отменять применимое книжное правило. Никакого автоматического Close из одной Zone, общего battle aggregate или молчаливого изменения ranged JSON v1. До implementation уточнить существенные неоднозначности.

PC, movement, mixed melee/ranged и полный каталог остаются дальнейшими расширениями; выбор M6 не означает их отмены. Порядок этих расширений требует отдельной оценки после первого контракта.

## Проверки этого аудита

Полный набор повторно: **1971 tests OK**, Python 3.14.5, 157,948 с. Existing integration tests включают полный JSON-пример с budget 136 и реальные процессы. Отдельный installed probe подтвердил совпадение 299 Python/Schema файлов установленного пакета с src (с нормализацией перевода строк), затем module/console × sequential/process вне repo без PYTHONPATH на пяти составах с короткими stages 1/keep 1 и 2/keep 1: planned=actual=7, aggregate reports равны. Для module использован файл, для console — stdin; text streams настроены ASCII, JSON идёт через binary UTF-8. Package build/install заново не выполнялись.

Compileall (src/tests/tools/docs/examples/m5), pip check, локальные ссылки и git diff --check успешны. Python 3.12/другие ОС, huge-input/resource benchmarks не проверялись. Изменения только в документации, roadmap и трассировке чтения книг; новых tests/production/schema/dependency изменений нет. Commit/push не выполнялись.
