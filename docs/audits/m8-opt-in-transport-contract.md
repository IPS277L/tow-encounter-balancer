# M8: проверка контракта opt-in generation / JSON v2

Дата: 2026-10-31. Проверяется **проектирование ADR-0047 и конечное ручное отображение**, не реализация opted generator/v2 wire. [Контракт](../decisions/ADR-0047-opt-in-generation-and-magic-json-v2.md), [probe](../examples/m8/opt_in_transport_contract_probe.py), [stdout](../examples/m8/opt_in_transport_contract_probe.output.txt), [subprocess test](../../tests/integration/test_m8_opt_in_transport_contract_probe.py).

Последующие этапы1–2 реализованы и описаны отдельными аудитами: [native generation](m8-opt-in-generation-readiness.md), [simulation v2](m8-simulation-v2-readiness.md). Текущий public probe вызывает production opted generator и simulation v2 parser/encoder; balance v2 остаётся ручным. Ниже сохранён результат первоначальной contract-only проверки, не новая implementation evidence.

## Решения и evidence

| Граница | Контракт / проверенный факт |
| --- | --- |
| Family policy | Отдельное required для opt-in подтверждение, full equality с template; будущий append-only native field default None. Guard ещё предстоит реализовать |
| Полная projection | Четыре ручных opted subsets совпадают с existing legacy generator плюс полной policy. Opposite perspective отдельно сохраняет fixed Wizard. IDs/indexed seeds прежние |
| JSON round-trip | Simulation и balance reserve/family с null и complete policy проходят ручной json round-trip. Existing public v1 parsers восстанавливают базовую часть; policy сохраняется отдельно и восстанавливается до opted execution |
| Source binding | Существующие summary/assessment и generation-result guards отвергают same-ID подмены None/opted source |
| Legacy compatibility | Current native generation отвергает opted template; v1 encoders не стирают policy; current parsers отвергают v2 и extra v1 fields, включая null |
| Runtime proof | Восстановленный fresh opted source исполняет настоящий Wind: 16 d10 в journal и ещё 16 d10 в отдельном native trial; равны полные sources/outcome/counters |
| Versioning | ADR явно разделяет command/error metadata и domain; v2-null не понижается до v1. Trusted-version/fallback error table, default-v1 validators и magic-only strict reader заданы, production ещё нет |

Probe получает request echoes из **настоящих исходных legacy** simulation1/balance4 trials. Их результаты не объявляются opted observations. Temporary legacy views внутри mapping не исполняются; globals/input snapshots неизменны. RNG внедрён только в два opted исполнения для доказательства конкретного пути. Нет вероятностных утверждений или закреплённого Monte Carlo winner.

Для копирования нужны четыре соседних файла: `opt_in_transport_contract_probe.py`, `generation_contract_probe.py`, `magic_scenario.py`, `opted_miscast.py`; dependencies — установленный текущий пакет либо абсолютный PYTHONPATH на src. Test копирует bundle в отдельный cwd и требует полный saved stdout, пустой stderr и успешный exit.

## Проверки

Windows x64 / CPython3.12.4:

```powershell
$env:PYTHONPATH = "src;tests"
.venv/Scripts/python.exe -m unittest integration.test_m8_opt_in_transport_contract_probe -v
```

**1 test OK (1,783 с)**. Sandbox блокировал работу TemporaryDirectory; тот же test вне sandbox прошёл. Это ограничение окружения, не игровой failure. Installed wheel/new schemas/CLI v2 этим тестом не проверяются.

Независимое read-only ревью контракта, actual adapters/services/reader/registry и finite proof блокеров не выявило. Уточнено сохранение прежних parser/encoder signatures и default v1 mapper calls. Production `src/` и существующие tests/probes в этом контрактном срезе не менялись; незакоммиченные изменения ADR-0046 сохранены.

Полная регрессия на границе контрактной вехи: **3729 tests / 33 известных errors / 0 failures / 0 skipped (591,365 с)**. Новый copied-bundle test и прежняя исправленная Broken-plan fixture прошли. Команда:

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Локальный log: `.cache/adr0047-contract-regression.log`. Все 33 ERROR headers отсортированы и сравнены с `.cache/adr0046-audit-c5af23d6873c4b0f956bb61185fa767e/full-regression.log`: различий нет. Это 16 ошибок `test_k1_registered_aim_loss_prepared_attack`, 16 `test_k1_registered_aim_loss_ranged_attack` и одна `test_m5_ranged_evaluation`; причины описаны в [открытых вопросах](../open-questions.md#проверки-dataclasses-на-python-312). FAIL headers и skipped отсутствуют. Полный suite с известными errors не называется зелёным.

Локальные Markdown paths и `git diff --check` проверены. Новые файлы этой вехи: ADR-0047, этот аудит, probe/stdout и один integration test; актуализированы README, docs index, архитектура, roadmap, open questions, example README и текущий статус. Existing dirty source/tests/docs других завершённых этапов сохранены. Новый installed wheel не собирался: контрактная веха не меняет production или packaged schemas, прошлый installed audit не объявляется v2 evidence.

## Что ещё не доказано

Нет production family-policy preflight, opted `_project_candidate`/result validation, v2 schemas/strict parser/encoder/service/CLI или installed transport audit. Ручное отображение не валидатор недоверенных документов; family assertions не доказывают реальные внешние обстоятельства. Удалённые резервисты отсутствуют из конкретного мира сценария, иначе no-external-Short assertion неприменим. Полная implementation acceptance matrix — в ADR-0047. При реализации v2 negative assertion текущего probe об отказе version2 заменяется public round-trip; v1 refusal и отказ opted template без family assertion остаются обязательными.

Следующий шаг: native generation целиком — append family field, exact template equality, lossless projection/result guards, deterministic subset/failure/None tests и generated runtime/sequential/process integration. Затем simulation v2, balance v2 и общий installed/full audit. Новых книжных правил/effect consumers или default tactics нет; commit/push не выполнялись.
