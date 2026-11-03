# ADR-0063: единственный актуальный Magic JSON-контракт

Дата: 2026-11-03. Статус: завершён; адресная проверка закрыта составно.

## Причина и решение

Пользователь подтвердил отсутствие потребности в обратной совместимости на стадии разработки. Поддержка Magic JSON1–5 создавала ветвления, цепочки schema refs и повторную приёмку версий. Их исполняемая поддержка удаляется; действующим остаётся один контракт `schema_version="6"`. Это заменяет требования совместимости ADR-0043/0047/0051/0054/0058/0062, сохраняя их историю и игровые/архитектурные ограничения.

Номер6 — текущий идентификатор, а не начало нового накопления версий. Новые правила обновляют текущий shape вместе с кодом, примерами и тестами. Стратегия внешних версий потребуется перед выпуском для сторонних клиентов. Ranged/melee/mixed имеют собственный единственный контракт1; номер Magic на них не распространяется.

## Исполнение и схемы

Command metadata, input/execution errors, readers, mappers и validators поддерживают только6 и используют6 по умолчанию. Неподдержанная строковая версия даёт unsupported_version; ошибка сама имеет текущий формат6. Lexical failure сохраняет недоверенный request_id=null, после успешного lexical decode ID сохраняется. Нечисловые/нестроковые версии и отсутствующая версия проходят обычную строгую shape validation.

Все пять nullable permissions обязательны в Scenario и независимом generation family assertion. Полный Endurance profile, original-source admission, matching и report/cache guards сохраняются. Старые dispatch/lossless-version ветви удаляются; legacy converter отсутствует.

Остаются шесть request/result/error schemas6 и `magic-common.schema.json` с используемыми общими определениями. Registry разрешает только bundled refs offline, без загрузки старых версий. Текущие шесть shapes должны совпасть с прежними shapes6 после раскрытия refs. Механизм package-data `*.json`, entry points и зависимости не меняются.

## Примеры, тесты и история

Базовые публичные примеры используют имена `magic-simulation.*.json` и `magic-balance.*.json`; их source/seed/trials остаются прежними, формат становится6. Opted Battered Leg requests6 остаются дополнительными сценариями того же контракта. Устаревшие version fixtures и compatibility-only assertions удаляются. Уникальные проверки admission, numeric tokens, full-source/cache/report, фазовых ошибок и privacy переносятся в текущий формат. Имена некоторых test modules могут сохранять номер этапа, из которого пришла проверка; это не поддержка старого wire format.

Исторические ADR и результаты аудитов сохраняются. Их ссылки на удалённые fixtures/tests перенаправляются на актуальные материалы; старые wheel-audit инструменты, исполнявшие матрицы версий, больше не являются текущей проверкой.

## Проверка

Адресная приёмка: offline closure и semantic comparison schemas, затронутые Magic JSON/application/CLI tests, изменённые public probes и smoke строгого reader для nonmagic boundaries. Число проверок и фактический результат фиксируются в статусе. Дубли module/console×sequential/process сокращаются до репрезентативного набора текущего контракта.

Полный игровой regression и wheel не запускаются автоматически: domain/engine, packaging discovery, dependencies и entry points не меняются; проверяется затронутая внешняя подсистема. Перед выпуском остаётся контрольная точка доставки установленного пакета по [политике проверок](../../AGENTS.md#политика-проверок).

Фактическая проверка:

- Schema tests: 13 OK за 3.730s. Независимое раскрытие refs подтвердило равенство всех шести shapes6 до/после изменения. Осталось 25 packaged schemas / 329 refs, в том числе 7 Magic schemas / 162 refs; все разрешаются offline, validator cache6.
- Magic JSON/CLI: 215 test IDs закрыты составно. Unit: 156 tests, 152 OK / 4 fixture errors; после исправления 6 targeted OK за 1.188s (4 повтора и 2 новых version guards), всего 158 IDs. Integration: 57 tests, 55 IDs OK / 2 IDs с 18 failed subtests старого cross-family error expectation; после исправления 2 targeted OK за 34.045s. Два исходных прогона не объявляются зелёными.
- Original-source/policy/native guards: 24 IDs закрыты составно; один prerequisite fixture исправлен и повторён успешно. Общий strict reader проверен 172 nonmagic JSON tests, все OK за 17.101s.
- Шесть изменённых public probes прошли: base manual mapper, Miscast32d10, stationary138d10, repeated96d10, Crushed647d10 и Battered239d10; finite source/gameplay oracles и real spawn сохранены. Два изменённых copied loaders: 2 tests OK за 10.923s. Все 12 публичных JSON-документов валидны, 7 requests допускаются production parsers.
- Import-only discovery собрал 4266 tests без loader errors; сами 4266 tests не выполнялись. Независимое AST review пяти parser/mapper функций подтвердило сохранение поведения текущего6. Локальные ссылки документации и `git diff --check` проверены.

Локальные logs: `.cache/current-magic-behavior-{unit,integration}.log` и `.cache/current-magic-behavior-integration-recheck.log`. Воспроизводимый выбор behavior tests (по очереди для unit и integration):

```powershell
$env:PYTHONPATH = 'src'
$taskLayer = 'unit' # затем 'integration'
$taskModules = Get-ChildItem "tests/$taskLayer/test_m8_magic*.py" |
    Where-Object { $_.Name -match '(json|cli)' -and $_.Name -notmatch '(schemas|schema_|probe)' } |
    ForEach-Object { "tests.$taskLayer." + $_.BaseName }
.venv/Scripts/python.exe -m unittest $taskModules -v
```

Это команда воспроизведения затронутой подсистемы, не предписание повторять уже успешные проверки. Следующий игровой шаг — отдельный контракт снятия sourced Prone5 после книжной сверки; wire cleanup не расширяет injury scope.
