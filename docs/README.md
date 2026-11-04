# Документация проекта

Для восстановления контекста достаточно [README](../README.md), [инструкций](../AGENTS.md), [статуса](project-status.md) и [индекса вопросов](open-questions.md). Остальное читать по задаче; закрытые этапы не задают текущую очередь.

| Задача | Что читать и обновлять |
|---|---|
| Проверить границу M8 | [Scope и результаты финальной приёмки](m8-completion.md) |
| Запустить бой группы PC против Minions/Brutes | [M25 State Trooper Halberd/Defence](examples/m25/README.md), [правило](rules/npc-profile-catalog.md#state-trooper-m25); [M24 JSON/CLI и выход Broken NPC](examples/m24/README.md), [контракт](decisions/ADR-0079-pc-broken-npc-adjacent-exit.md); [M23 Official/Broken](examples/m23/README.md), [контракт](decisions/ADR-0078-pc-official-first-wound-broken-boundary.md); [Brigand/Craven M22](examples/m22/README.md), [Footpad/Townsfolk M21](examples/m21/README.md), [запасное оружие M20](examples/m20/README.md), [двуручное оружие M19](examples/m19/README.md), [одноручное оружие M18](examples/m18/README.md), [ally Recover M17](examples/m17/README.md), [контракт](decisions/ADR-0073-pc-ally-standard-recover.md); [Protection Help M16](examples/m16/README.md), [Melee Help M15](examples/m15/README.md), [Glorious/Near Miss M14](examples/m14/README.md), [тяжёлые раны M12](examples/m12/README.md), [состав NPC](examples/m11/README.md), [Minion-группа](examples/m10/README.md), [одиночный пример](examples/m9/README.md) |
| Продолжить реализацию | [Статус и точный следующий шаг](project-status.md), [roadmap](roadmap.md) |
| Изменить правило | [Иерархия источников](source-policy.md), соответствующий раздел [нормализованных правил](rules/), при необходимости книга по [индексу источников](source-index.md) |
| Проверить неоднозначность | [Индекс вопросов](open-questions.md) → соответствующие [подробности](open-questions-details.md); [противоречия](contradictions.md) |
| Изменить взаимодействие слоёв | [Обзор архитектуры](architecture/overview.md), [resolution kernel](architecture/resolution-kernel.md), относящиеся [ADR](decisions/) |
| Изменить внешний формат | [Текущий Magic JSON](examples/m8/json/README.md), [решение об одном контракте](decisions/ADR-0063-single-current-magic-contract.md), [схемы](../src/towr/adapters/schemas/) |
| Добавить проверки | [Тестирование](testing.md), [общие test builders](../tests/support/) |
| Проверить реализацию книжного правила | [Трассировка](rule-traceability.md), код и соответствующие тесты |
| Исследовать производительность | [Benchmarks](benchmarks/README.md) |
| Найти прежнее решение или отчёт | [Архив](archive/README.md), [ADR](decisions/), [аудиты](audits/) |

Текущие документы описывают поведение и ограничения. Числа тестов, wheel hashes и подробные протоколы завершённых проверок хранятся в соответствующем отчёте или ADR. Их не нужно повторять во всех обзорных файлах.

Исходный [дизайн-док](TOWR_Combat_Simulator_&_Encounter_Balancer_—_Context_and_Technical.md) и [правила прототипа](game-rules.md) сохранены как материал миграции; при конфликте действуют книги выбранной редакции. [Лор](lore/README.md) отделён от нормативных правил.
