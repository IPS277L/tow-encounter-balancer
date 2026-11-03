# Текущий статус проекта

Дата обновления: 2026-11-03.

## Текущий этап

**ADR-0063 завершён: поддерживается только текущий Magic JSON6.** [Контракт и результаты проверки](decisions/ADR-0063-single-current-magic-contract.md). Удалены поддержка форматов1–5, 30 старых схем, 20 version fixtures и два исторических инструмента матричной приёмки. Остаются шесть актуальных схем и common definitions; все пять nullable permissions обязательны, full profile/source/cache/report guards сохраняются. Domain/engine, игровые правила и package discovery не менялись.

[Политика работы](../AGENTS.md#контракты-во-время-разработки): обратная совместимость разработки не требуется; текущий формат обновляется вместе с кодом/примерами/тестами. Full/wheel не запускаются для каждого ADR. Предыдущая функциональность Battered Leg закрыта в62; историческая приёмка — [здесь](audits/m8-battered-leg-transport-readiness.md).

## Последняя проверка

- Schemas:13tests OK/3.730s; все шесть shapes6 совпали с прежними после раскрытия refs. Package offline closure:25schemas/329refs; Magic7schemas/162refs, validator cache6.
- Magic JSON/CLI: 215 IDs закрыты составно. Unit:158 IDs (156run:152OK/4fixture errors, затем6targetedOK:4retry+2новых version guards). Integration:57 IDs (55OK/2IDs со старым cross-family error expectation; после исправления2targetedOK/34.045s). Исходные прогоны не объявляются зелёными.
- Затронутые policy/native source guards:24logical checks закрыты составно после исправления одного prerequisite fixture. Nonmagic JSON:172tests OK/17.101s.
- Все шесть изменённых public probes прошли, включая realspawn и прежние finite gameplay/manual source oracles. Два изменённых copied loaders:2tests OK/10.923s. Все12publicJSON валидны, все7requests допускаются production parsers.
- Import-only discovery:4266tests собраны без loader errors; это не их исполнение. Независимое AST review parser/mapper подтвердило сохранение поведения6.

Полная игровая регрессия и wheel не выполнялись: изменена ограниченная внешняя подсистема, правила упаковки и entry points прежние. Следующая установленная проверка доставки — перед внешним выпуском либо раньше при изменении соответствующего механизма/обнаружении риска. Адресные результаты не объявляются full regression.

## Ограничения

Первая Battered Leg5 от ordinary wounding enemy Attack, resolved/untreated/unhealed; normal Endurance Test, explicit unmounted/no-external-Conditions facts. None сохраняет pending stop. Failure сохраняет sourced Prone без removal consumer. Новые Staggered/Wounds после success ограничивают exact-injury scope60; actual death до этого stop недостижима. Treatment/healing/mixed injuries/save-resume не открыты. Retired Magic1–5 inputs отклоняются; остальные families имеют собственный единственный формат1.

## Точный следующий шаг

Адресно сверить Free Actions/Prone в книгах и подготовить отдельный full-owner контракт снятия sourced Prone5 после провала Endurance, сохраняя Wound/completion/history. Определить источник действия, порядок применения и границу exact-injury gate60 до реализации. Команды воспроизведения текущих JSON/CLI checks приведены в ADR-0063; заново запускать их без влияющего изменения не требуется.

Commit/push выполняет пользователь; книги и `.gitignore` не менялись.
