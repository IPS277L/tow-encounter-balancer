# M8 / ADR-0051: native stationary-wound generation

Дата: 2026-11-01. **Пункт1 [ADR-0051](../decisions/ADR-0051-stationary-wound-generation-and-magic-json-v3.md) реализован и проверен, native generation этап закрыт.** [Исходная контрактная проверка](m8-stationary-wound-transport-contract.md) сохраняется отдельно. Simulation3/balance3/schema/CLI и общий installed audit — последующие пункты2–4; весь ADR ещё не закрыт.

**Последующий пункт2 реализован:** [simulation3 audit](m8-simulation-v3-readiness.md). Текущий public probe уже использует production simulation3 и8actual round-trips; ручными остаются8balance3 mappings. Ниже сохранена проверка native generation этапа до wire3; она не является новым installed/console evidence.

## Контракт и исполнение

`MagicCandidateGenerationRequest.stationary_wound_continuation: NpcMagicStationaryWoundPolicy | None = None` добавлено последним полем. Это отдельное утверждение для всех subsets, независимо от template и Miscast family permission. Caller явно подтверждает обе политики; omitted не наследуется. Удалённые резервисты отсутствуют в конкретном сценарии. Никаких новых игровых переходов, нормализованных Rule IDs или house rules нет; используются PG1.4/GM1.1 и готовая граница ADR-0050. Книги заново не читались.

| Граница | Реализация / evidence |
| --- | --- |
| Request preflight | Оба конца template/family имеют strict typed policies до equality/чтения коллекций. Miscast choice/facts/prone_policy повторно проверяются; raw string не считается enum |
| Перенесённый source | `_validate_generation_source` до `_count_vectors` повторяет pure template/request admission и сравнивает с исходным объектом. Нормализация исходного списка в tuple не разрешает повреждённый request |
| Вложенные модели request | Facts семейства/template, группы, stages и objective window повторно проходят собственные constructors. Это узкая проверка собственных моделей generation, не универсальный recursive validator всех K1 объектов |
| Полная projection | `_project_candidate` явно передаёт обе **family** policies каждому `NpcMagicScenario`; enumeration/ordered IDs/seeds/C/budget прежние |
| Result reconstruction | Source повторно проверяется до enumeration; candidate policy types — до сравнения с полной expected projection. Same-ID None/opted или чужой source не проходят. Прежняя диагностика exact source projection сохраняется |
| Native balance/staged | Полные generation→staged→report sources и command metadata сохраняются. Никакого implicit wire3 выбора, downgrade, skip/retry/partial family |
| JSON1/2 | Полный stationary source по-прежнему явно отвергается mapper/encoder; nullable wire field этих версий не расширен. V3 ещё unsupported |

Отдельная read-only проверка получила настоящий `execute_magic_balance` result с matching stationary+Miscast family и проверила отказ `encode_magic_balance_result` для metadata1/2: оба ValueError указывают stationary Wound/losslessly, permission не удаляется, RNG в encoder запрещён patch. Evidence `.cache/adr0051-generation-wire-guard.log`. Это прежняя wire граница, не simulation3/balance3 implementation.

Код: [модели/preflight/result](../../src/towr/application/magic_candidate_generation_models.py), [построение](../../src/towr/application/magic_candidate_generation.py). Domain/engine/simulation и packaged schemas на этом этапе не менялись.

## Детерминированная evidence

[19 unit-тестов](../../tests/unit/test_m8_stationary_wound_generation.py): четыре combinations, все4 prefix-count vectors, обе стороны Wizard/perspective, старые positional/None forms, полные ordered источники/C/budgets/indexed seeds, typed template/family/candidate и вложенные Miscast enum/facts. Pickled/forged sources отвергаются до enumeration, не исправляются normalization. Включены equality copies, same-ID source substitution, equal-frame collapse, late conflict/invalid Broken route/OSError с точными candidate/counts/cause без RNG и частичного результата.

Read-only ревью выявило shallow re-admission вложенных facts/groups/stages. После исправления добавлены два parametrized regression tests: family/template no-external-condition fact=False, group minimum=True, stage keep=True, window target=float. Request constructor, factory и result отвергают их до `_count_vectors`, исходный объект и global RNG сохраняются. Это исправление source admission, не изменение игровых правил.

[5 integration-тестов](../../tests/integration/test_m8_stationary_wound_generation.py) используют явный variable reserve с дополнительным ally2. Минимальный и полный generated subsets содержат3/4 actors; это фактическая projection, а не clone template:

- Actual9→stand→3Casting→incoming6→end/expiry:48/66 scripted d10, один stand, retained terrain, отсутствие Prone/Drained после expiry, две daily receipts/consumed rolls и archived expiry witness. None9 и Wound10 controls завершаются за7draws с прежним ACTOR_INJURY.
- Все4 combinations в sequential/spawn сохраняют source/seed и denominator2 на кандидата; mixed пакеты имеют4actual/8planned trials, unsupported rate1/2 или1 и no-eligible остановку stages.
- Положительные staged reruns оплачивают полные2+2+4=8trials, сохраняют indexed seed prefix и полные одинаковые sequential/spawn reports. Top-level picklable RNG factory проверяет настоящий child PID; child cleanup проверен.
- Default seeded sequential/spawn отчёты равны для обеих perspectives без ожидания конкретного Monte Carlo результата.
- Native balance metadata1/2 сохраняет одну полную source chain. Same-ID foreign generation source отвергается до evaluator с собственной версией command.

[Public probe](../examples/m8/stationary_wound_transport_contract_probe.py)/[stdout](../examples/m8/stationary_wound_transport_contract_probe.output.txt) теперь вызывает **настоящий** generator:20 full-source subsets совпадают с независимыми manual projections,16 finite proposed-wire mappings восстанавливают typed sources,4 generated candidates дают4staged rows. Прежние8scripted trials/138d10 остаются finite execution controls. Ручной wire3 inverse ограничен полным fixture и не является production parser/schema/CLI. Genuine legacy baselines создаются до opted sources, policy из opted объекта не удаляется.

## Проверки

Windows x64 / CPython3.12.4:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.unit.test_m8_stationary_wound_generation -v
.venv/Scripts/python.exe -m unittest tests.integration.test_m8_stationary_wound_generation -v
.venv/Scripts/python.exe -m unittest tests.unit.test_m8_magic_candidate_generation_models tests.unit.test_m8_magic_candidate_generation tests.unit.test_m8_opted_magic_generation tests.unit.test_m8_stationary_wound_policy -q
.venv/Scripts/python.exe -m unittest tests.integration.test_m8_stationary_wound_transport_contract_probe -v
```

19new unit OK/0,250с;5new integration OK/18,262с вне sandbox;60existing unit OK/0,630с после усиления nested-source guards; copied public bundle1test OK/3,425с вне sandbox. Прежние positional/omitted-family проверки адаптированы к append-last field; диагностика exact source projection сохранена.

Полная регрессия на границе этапа:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

**3926tests /33known errors /0failures /0skipped,787,439с**, вне sandbox. Все24новых tests и обновлённый copied-bundle test прошли. Log `.cache/adr0051-generation-regression.log`. Все33 отсортированных exact `ERROR:` headers совпали с `.cache/adr0051-contract-regression.log`; новых errors и `FAIL:`/skipped нет.32errors — прежние Aim frozen/slotted `.state` expectations,1 — `dataclasses.replace(init=False)`, см. [открытые вопросы](../open-questions.md#проверки-dataclasses-на-python-312). Полный suite с известными errors не считается зелёным.

После полного прогона production/tests/probe не менялись. Новый installed wheel и schemas не собирались на native этапе: проверка нового wheel/module/console относится к общему пункту4. Saved v2 JSON results, локальные Markdown-пути (без anchors) и `git diff --check` проверены отдельно.

## Следующий шаг

Пункт2 ADR-0051: simulation v3 целиком — три schemas/local registry, command/errors, magic-only family version selection, shared scenario mapper, parser/service/result+error encoder/CLI и actual sequential/process. Balance3 до пункта3 остаётся explicit unsupported без загрузки отсутствующей Schema. V1/v2 сохраняют прежний lossless отказ stationary policy. После simulation3 — balance3 и общий installed/schema/CLI/spawn/full audit.

Базовый commit: `6dd8711 M8 P19`. Новые файлы этапа: этот audit,19unit/5integration tests; изменены два application файла, два прежних unit файла для append-last/guard semantics и public probe/stdout. Навигация/статус/roadmap синхронизированы главным агентом. Изменения этапа оставлены незакоммиченными; commit/push выполняет пользователь.
