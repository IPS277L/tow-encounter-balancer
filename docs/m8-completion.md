# Конечный checklist M8

Дата: 2026-11-04. Статус: функциональная граница определена и реализована; финальная контрольная точка ещё не выполнена.

## Что закрываем

M8 — **ограниченная магия в боевой симуляции**, от одного боя до массовых прогонов, подбора составов и текущего JSON/CLI. Основа: [Casting35](decisions/ADR-0035-cowardly-flight-casting-boundary.md), [owner36](decisions/ADR-0036-magic-encounter-integration.md), [runner37](decisions/ADR-0037-magic-scenario-runner.md), [trials38](decisions/ADR-0038-independent-magic-simulations.md) и [внешняя граница43](decisions/ADR-0043-magic-json-cli-v1.md), с реализованными дополнениями до64 и заменой старых wire formats на JSON6 по63.

Ровно один authored Champion-Wizard Level1–4 на любой стороне, canonical Curse of Cowardly Flight и союзные/вражеские numeric Shooting Minions. Fresh initial state, один STANDARD slot, явные профили, порядок, scene frames, маршруты и GM facts. Сцена замкнутая; без PC, mounts, Fate/bonus slots, cover/terrain, других spells, opposition/Mixing/Magic Resistance и скрытого выбора фактов.

Неподдержанное последствие сохраняется и заканчивает trial исходом `UNSUPPORTED_PATH`. Неполные будущие frames и непокрытые Wound/Miscast consumers прямо допущены ADR-0037; их полная реализация не является условием закрытия этой M8. Правила книги не меняются ради этой границы.

## Реализованные критерии

«Есть» означает наличие реализации и адресных проверок; это не объявление текущего полного набора зелёным. Финальный запуск указан отдельно ниже.

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

2026-11-04: read-only сверка обнаружила одно устаревшее ожидание simulation CLI test: Battered object сравнивался без обязательного `prone_policy:null`. Исправлено; ровно этот existing matrix test прошёл, 1test OK/10.324s, log `.cache/m8-closure-cli-simulation.log`. Остальные ссылки — существующее evidence, не новые прогоны этой проверки. Полная регрессия далее включает контрольные наборы; отдельную дублирующую матрицу перед ней запускать не требуется без нового риска.

## Осталось две контрольные работы

- [ ] **R1. Завершающая регрессия текущего дерева.** Один полный source run после серии64/Recover. Разобрать реальные ошибки; повторять исправленные/зависимые проверки по [политике](../AGENTS.md#политика-проверок). Закрыть все test IDs актуального набора, отдельно учитывая environment errors. Единый либо составной результат назвать точно; известные errors нельзя замолчать или объявить зелёными.
- [ ] **R2. Одна проверка доставки после R1.** На неизменившемся после R1 дереве исходников один раз собрать и установить offline wheel, проверить включение текущих schemas/modules, offline refs и зависимости. Из внешнего cwd выполнить representative simulate-magic и balance-magic установленными module/console entry points; один process case достаточен для доставки. Проверить current6 echo/summary/report/error, отсутствие зависимости от source tree и согласованность пользовательских команд. Старые wire versions и полную повторную installed-копию всех unit tests не включать.

После R1/R2 записать фактические результаты и отметить **M8 завершена в этой ограниченной границе**. Новая игровая механика не является обязательным остатком. Исправление дефекта, нарушающего уже заявленную границу, входит в приёмку; новая способность/табличная строка не добавляется в неё автоматически.

Оценка остатка: две проверочные работы, обычно один контрольный заход при отсутствии существенных ошибок. Последний известный общий run занял около25минут; это ориентир стоимости одного запуска на этой машине, не обещание времени завершения. Объём исправлений до R1 заранее неизвестен. Процент готовности всей книги по этому checklist не вычисляется.

## После M8

Полный каталог spells/Wounds/Miscasts; arbitrary injury combinations, treatment/healing, ally removal, movement/inventory/mounts, PC/campaign, активная смерть Wizard от иных источников и save/resume — дальнейший backlog. Новые функции выбираются отдельно по источникам/ценности, а не бесконечно сдвигают финиш M8. Неподдержанные пути остаются видимыми в существующем симуляторе.
