# Конечный аудит M4

Дата: 2026-09-28. На старте сохранены незакоммиченные CLI, entry point, тесты и документация предыдущего среза (17 файлов). Аудит проверяет рабочее дерево, а не только HEAD; production-код и тесты в ходе аудита не менялись.

**Вывод: все четыре критерия M4 выполнены для текущего неподвижного ranged Minion-сценария. Техническая граница готова к первому ограниченному M5.** Определение продуктовой сложности для M5 отдельно предложено в [ADR-0017](../decisions/ADR-0017-ranged-candidate-assessment.md); аудит M4 не утверждает пресеты сложности или поддержку PC-сценариев.

## Матрица roadmap

| Критерий | Реализация | Проверка | Вывод |
| --- | --- | --- | --- |
| JSON Schema и адаптеры | [Три packaged schemas](../../src/towr/adapters/schemas/), [strict parser/result/error encoders](../../src/towr/adapters/ranged_simulation_json.py), локальный schema registry | [14 unit](../../tests/unit/test_m4_ranged_json.py): lexical types, UTF-8, duplicate/unknown keys, version/seed, admission, order/source/lossless projection; [4 error tests](../../tests/unit/test_m4_ranged_error_json.py): категории, pointers, Unicode, отсутствие cause/partial records | Выполнено; Schema отдельно не доказывает семантическую корректность или происхождение результата |
| Application services | [Frozen command/options](../../src/towr/application/ranged_simulation_models.py), [execute_ranged_simulation](../../src/towr/application/ranged_simulation_service.py), typed errors | [5 unit](../../tests/unit/test_m4_ranged_service.py): explicit dispatch/options, source/type, cause/notes, отсутствие retry/fallback, interrupts; [5 integration](../../tests/integration/test_m4_ranged_json.py): real sequential/spawn и ошибки до/после начала исполнения | Выполнено; standard RNG, request-bound complete result; input error отделён от execution failure |
| CLI simulate | [cli.py](../../src/towr/cli.py), guarded [__main__.py](../../src/towr/__main__.py), console script в [pyproject.toml](../../pyproject.toml) | [7 unit](../../tests/unit/test_m4_cli.py) и [8 subprocess tests](../../tests/integration/test_m4_cli.py): file/stdin, ASCII host streams/Unicode, spawn, help/usage, input/execution/I/O, closed stdout/stderr | Выполнено на Windows / Python 3.14.5; оба installed entry points проверены вне repo без PYTHONPATH |
| Примеры входа и выхода | [Request/result и команды](../examples/m4/README.md), [README](../../README.md#запуск-симуляции) | Golden JSON сравнивается после замены descriptive runtime; arrays и records сохранены. Установленные module/console × sequential/process дают те же records/summary | Выполнено; пример одного seed не является оценкой вероятности или профилем полного NPC |

В M4 43 теста: 30 unit и 13 integration. Повторный полный набор: **1840 tests OK**, Python 3.14.5, 44,292 с, включая настоящий spawn. Compileall, pip check, локальные ссылки и git diff --check успешны. Установленный ранее wheel повторно проверен без переустановки: `python -I -m towr` и `towr.exe`, оба режима, cwd вне репозитория. Benchmark не повторялся: engine/simulation не менялись.

## Границы результата аудита

- Сохраняются admission и scope [ADR-0013](../decisions/ADR-0013-ranged-minion-scenario-input.md): здоровые Minions, ограниченный numeric Shooting, явные facts/policies и общий бюджет. CombatSide не превращает Minion в PC. Полный каталог, общий бой, движение/Reload и автономный Blunderbuss вне этого входа.
- JSON v1 проверяет структуру, типы и существующие семантические ограничения; source_rule_id не загружает правило из книги. Full journal/receipts не принимаются и не выдаются wire API. Отдельного importer для чужого JSON result нет.
- Сохраняются четыре исхода M3: objective_achieved, side_defeated, round_limit, unsupported_path. Лимит и unsupported не становятся ничьей или победой; CLI code 0 означает завершение симуляции, а не достижение цели.
- Replay требует тех же входов, правил/кода, seed scheme, RNG и runtime. Runtime metadata — описание среды, не доказательство происхождения. Полный M3 result содержит compact records; это ещё не отдельный aggregate-only вход балансировщика.
- Parsing/admission/execution errors не дают partial simulation result. Для ожидаемых ошибок JSON идёт в stdout, краткая диагностика — в stderr; I/O/usage имеют отдельное поведение по [ADR-0016](../decisions/ADR-0016-ranged-simulation-json-v1.md#cli-simulate). Получатель проверяет exit code: при обрыве pipe доставка bytes не атомарна.
- Весь request/result хранится в памяти. Timeout/quotas/streaming, retry/fallback и автоматический выбор workers отсутствуют. Завершение process runner ждёт уже выполняющиеся задачи; hard-kill не обещан.
- Минимальная заявленная версия Python 3.12 в этой среде отсутствует; остальные ОС и огромные входы этим аудитом не проверены. Они не выдаются за подтверждённые результаты.

## Переход к M5

Исходный дизайн, разделы 19–22, описывает приблизительные player-win окна, желаемую длительность, staged search и генерацию составов. Эти продуктовые предложения не меняют книжные правила и не доказывают, что текущий Minion-result уже содержит метрики полноценной группы игроков.

[ADR-0017](../decisions/ADR-0017-ranged-candidate-assessment.md) выделил первый M5 над aggregate-only summary. После аудита реализованы summary, pure assessment и bounded evaluation явного списка с бюджетом/top_k (1876 tests OK). Пользователь [подтвердил метрику](../open-questions.md#первая-метрика-m5) цели за лимит с отдельными остановками и явным окном без пресетов. [ADR-0018](../decisions/ADR-0018-staged-ranged-evaluation.md) реализован: staged models/helper/service с 23 тестами. Генератор численности по [ADR-0019](../decisions/ADR-0019-ranged-composition-generation.md) реализован: явный резерв участников, неизменные профили/решения, предел составов и полный staged budget. Первый M5 закрыт [аудитом](m5-readiness.md) в текущем scope; [typed пример](../examples/m5/README.md) проверен в sequential/process. Контракт [JSON balance v1 / CLI balance](../decisions/ADR-0020-ranged-balance-json-v1.md) реализован полностью в текущем scope: Schema/adapters, application service, кодирование ошибок и CLI balance. Следующий срез — конечный аудит внешней границы M5 и актуализация roadmap. Ограниченная генерация реализована; CLI balance пока отсутствует.
