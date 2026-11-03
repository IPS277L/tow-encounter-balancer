# Конечный checklist M8

Дата: 2026-11-04. Статус: **M8 завершена в описанной ниже ограниченной границе**; финальная регрессия и проверка установленного пакета выполнены.

## Что закрываем

M8 — **ограниченная магия в боевой симуляции**, от одного боя до массовых прогонов, подбора составов и текущего JSON/CLI. Основа: [Casting35](decisions/ADR-0035-cowardly-flight-casting-boundary.md), [owner36](decisions/ADR-0036-magic-encounter-integration.md), [runner37](decisions/ADR-0037-magic-scenario-runner.md), [trials38](decisions/ADR-0038-independent-magic-simulations.md) и [внешняя граница43](decisions/ADR-0043-magic-json-cli-v1.md), с реализованными дополнениями до64 и заменой старых wire formats на JSON6 по63.

Ровно один authored Champion-Wizard Level1–4 на любой стороне, canonical Curse of Cowardly Flight и союзные/вражеские numeric Shooting Minions. Fresh initial state, один STANDARD slot, явные профили, порядок, scene frames, маршруты и GM facts. Сцена замкнутая; без PC, mounts, Fate/bonus slots, cover/terrain, других spells, opposition/Mixing/Magic Resistance и скрытого выбора фактов.

Неподдержанное последствие сохраняется и заканчивает trial исходом `UNSUPPORTED_PATH`. Неполные будущие frames и непокрытые Wound/Miscast consumers прямо допущены ADR-0037; их полная реализация не является условием закрытия этой M8. Правила книги не меняются ради этой границы.

## Реализованные критерии

Критерии подтверждены реализацией, адресными проверками и финальной приёмкой ниже. Это не означает поддержку всех правил книги.

| Критерий | Наличие и проверяемое поведение |
|---|---|
| Допуск входа | [Scenario/facts](../src/towr/domain/npc_magic_scenario_models.py) сохраняют состав, spell, fresh state и явные факты; неверный источник отвергается до RNG |
| Один непрерывный бой | [Runner](../src/towr/engine/npc_magic_scenario_runner.py), [journal/result](../src/towr/domain/npc_magic_scenario_result_models.py): Casting/Curse/обязательный Give Ground/Willpower, Attack, defeat, Broken, end/advance; pending нельзя пропустить |
| Исходы и счётчики | Objective achieved, perspective defeated, round limit, unsupported различаются; Broken/другая Zone не становятся defeat; actions и rounds не подменяются числом journal steps |
| Независимые trials | [Sequential](../src/towr/simulation/npc_magic_simulation.py) и [process](../src/towr/simulation/npc_magic_parallel.py): indexed seeds, свежий RNG, полный source и одинаковые records/aggregates |
| Подбор сложности | [Assessment](../src/towr/balance/magic_assessment_models.py), generation и stages сохраняют источник/бюджет. Любое observed unsupported даёт `unsupported_observations`, `window_match=None` и запрещает итоговый выбор этого кандидата; все trials остаются в знаменателе |
| Текущий внешний контракт | Только Magic JSON6: strict request/result/error schemas, full echo, phase errors, simulate-magic/balance-magic, module/console и явный backend |
| Выбранные расширения | Поддержка ограниченных Wounds1–3/6, canonical9 и одного repeated stand, изолированного Crushed Rib10/next Test, Battered Leg5 Endurance/free self-stand/standard self Recover; scoped Unnatural Wind21–22, standalone Prone и подтверждённая смерть ожидающего Wizard после Attack. Точные сочетания ограничены соответствующими consumers, opt-in не разрешает произвольные combinations |
| Честные ограничения | Ошибка входа/исполнения не превращается в игровой outcome; stop сохраняет prefix/source/pending. Публичные примеры и [вопросы](open-questions.md) описывают scope, а не обещают весь каталог книги |

Существующий [saved balance example](examples/m8/json/magic-balance.result.json) содержит как eligible выбранного кандидата, так и строку `unsupported_observations`. Это пример конечных наблюдений указанного runtime, не доказательство истинной вероятности или отсутствия непокрытых ветвей при любых будущих бросках.

## Три контрольных набора

1. **Бой и агрегаты:** [четыре фактических исхода](../tests/integration/test_m8_npc_magic_simulation.py), [real-spawn parity](../tests/integration/test_m8_npc_magic_parallel.py). Один и тот же input сохраняет source, seeds, счётчики и unsupported в общем N.
2. **Последствия и допустимый stop:** [missing intermediate frame/pending](../tests/integration/test_m8_npc_magic_scenario_result.py), [Battered Recover и последующий Casting→Miscast](../tests/integration/test_m8_battered_leg_recover.py), [unsupported запрещает selection](../tests/integration/test_m8_magic_staged_evaluation.py). Не требуется исполнять неподдержанный дальнейший Miscast, если stop точен и Pool/receipt сохранены.
3. **Публичный текущий контракт:** [simulation6](../tests/integration/test_m8_magic_json_v6.py), [balance6](../tests/integration/test_m8_magic_balance_json_v6.py): source/permissions echo, aggregates/полный staged report, module/console×sequential/process на репрезентативных inputs.

Предварительная сверка 2026-11-04 обнаружила устаревшее ожидание simulation CLI test: Battered object сравнивался без обязательного `prone_policy:null`. Исправление проверено адресно, затем эта же матрица и все три контрольных набора прошли в единой финальной регрессии.

## Финальная приёмка

- [x] **R1. Завершающая регрессия.** Один полный source run после серии64/Recover: **4312 tests, OK за 1597.756s**, без failures/errors/skips. Windows, Python3.12.4; исходное чистое дерево `0c26270`. Команда при `PYTHONPATH=src`: `.venv/Scripts/python.exe -m unittest discover -s tests -v`. Семь выбранных контрольных методов, включая четыре исхода, real spawn, missing frame, unsupported selection, обе CLI6 матрицы и Casting→Miscast после Recover, найдены успешными внутри этого единого прогона. Исправлений исходников не понадобилось.
- [x] **R2. Проверка доставки.** Одна сборка из свежей копии `src`, `pyproject.toml`, `README.md`, `LICENSE`; offline build и установка настоящих cached wheels в новый venv, `pip check` успешен. SHA256 всех 470 `.py/.json` совпали между source, wheel и installed. Доступны 25 schemas/329 offline refs, включая 7 Magic/162 refs и новые Prone/Recover modules. Импорты идут из нового venv, запуск — из внешнего временного каталога без `PYTHONPATH`/`PYTHONHOME`, не editable.

Installed CLI: использованы копии [simulation6 request](examples/m8/json/magic-simulation-v6.request.json) и [balance6 request](examples/m8/json/magic-balance-v6.request.json) с `prone_policy="recover_self"` в scenario и обеих matching balance projections. Sequential module/console запуски для simulate-magic и balance-magic сохранили полный current6 input, summary/полный staged report и побайтово равные результаты. Один console process simulation сохранил тот же summary при явном process echo. Три error cases проверили threshold11, несовпадающий generation profile и lexical float: exit2, current6, корректный trusted/null request ID и path.

R2 закрыт **составно**: первоначальный локальный проверочный скрипт ошибочно требовал пустой stderr для input errors. CLI штатно выдаёт одну строку диагностики; после исправления ожидания выполнены только три error cases. Пять успешных CLI запусков, сборка, установка и полная регрессия не повторялись; приложение и wheel не менялись. Это ошибка аудитора, не дефект поставки и не единый зелёный первый запуск R2.

Локальные evidence: `.cache/m8-final-source-regression.log`, `.cache/m8-final-delivery.log`, `.cache/m8-final-delivery-errors.log`, `.cache/m8-final-delivery-5f96786512/report.json`. Wheel: `towr_encounter_balancer-0.1.0-py3-none-any.whl`, SHA256 `6a90f5d048819c4f21d1352f1615122d95212de65d535da11286120a71e0dc17`. Повторяемая основа доставки: `pip wheel --no-index --find-links WHEELHOUSE --no-deps PACKAGE_COPY`, fresh `venv`, `pip install --no-index --find-links WHEELHOUSE WHEEL`, `pip check`, затем четыре module/console команды и один process case с public requests выше. Локальные аудиторы в `.cache` — вспомогательные артефакты, не часть публичного API.

Обязательного остатка для ограниченной M8 нет. Новая способность или табличная строка рассматривается как следующая функция; закрытие M8 не означает готовность всей книги или отсутствие unsupported при любых будущих бросках.

## После M8

Полный каталог spells/Wounds/Miscasts; arbitrary injury combinations, treatment/healing, ally removal, movement/inventory/mounts, PC/campaign, активная смерть Wizard от иных источников и save/resume — дальнейший backlog. Новые функции выбираются отдельно по источникам/ценности, а не бесконечно сдвигают финиш M8. Неподдержанные пути остаются видимыми в существующем симуляторе.
