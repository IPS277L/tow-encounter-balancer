# Текущий статус проекта

Дата обновления: 2026-11-04.

## Текущий этап

**M10 завершена в выбранной границе: общий бой группы PC против Minions.** Uniform party, индивидуальные injury/Fate/daily/weapon/expiry, общий clock/journal, retarget после смерти, продолжение выжившими, independent trials и статистика подтверждённых потерь работают через подбор и действующий PC JSON1/CLI. [Контракт и приёмка ADR-0066](decisions/ADR-0066-pc-party-melee-encounter.md).

[Группа M10](examples/m10/README.md) и обновлённый [одиночный пример M9](examples/m9/README.md) выполнены настоящими CLI-командами. Команды прежние: `simulate-pc-melee`, `balance-pc-melee`; обязательный `party` заменяет старый single shape, current version остаётся1 без compatibility. M8 закрыта ранее; её результаты — в [checklist M8](m8-completion.md).

## Последняя проверка

M10: **190 уникальных адресных IDs закрыты составно**, не единый full run. Основной набор188:182 passed,6 cases заблокированы sandbox Windows process/temp permissions; только они повторены вне sandbox —6OK. После усиления source/history guards36затронутых checks OK, включая2новых, затем один зависимый real party spawn OK. Команды/состав и времена — в ADR-0066; logs `.cache/m10-subsystem.log`, `.cache/m10-process-recheck.log`, `.cache/m10-source-binding-recheck.log`, `.cache/m10-final-party-spawn.log`.

Все4 public M9/M10 requests исполнены реальными командами, request echo проверен;7 PC schemas/90 offline refs, shared bundle и help проверены. Full/wheel M10 не запускались: общие правила K1 и доставка не менялись. Последние полные4404 tests/installed495files относятся к M9 и описаны в ADR-0065; они не выдаются за проверку новых изменений.

Документация:14изменённых Markdown-файлов,961локальная ссылка и все4current request/result пары проверены. `git diff --check`, UTF-8/newline/trailing-whitespace проверки изменённых текстовых файлов успешны. Из logs подтверждены190уникальных IDs с успешным результатом; незакрытых failures нет.

Перед M10 рабочее дерево было чистым; изменения M10 остаются незакоммиченными. Commit/push агент не выполняет.

## Ограничения

Непустая здоровая initial party со Staff/Sword против обычных numeric Melee Minions, одна явная Close Zone, фиксированные порядки/target priorities и policies, независимый полный supplied Fate каждого PC. Common Wounds1–10/repeated/mixed поддержаны;11–23дают actor-bound pending lifecycle stop до completion/daily/effects; lethal24+ завершается после Near Miss decline. Active Fate, помощь/ally Recover, Brutes/Champions, общий inventory, другие оружие/Talents/тактики, treatment/campaign/save-resume не подключены. Потери при limit/unsupported — только подтверждённые до остановки. UNSUPPORTED_PATH остаётся в знаменателе trials и исключает кандидата из selection. Magic сохраняет JSON6; PC и другие families — свой единственный1.

## Точный следующий шаг

Согласованная M10 закрыта, обязательного остатка нет. Следующее продуктовое направление — более широкий NPC roster (первый Brute) либо уменьшение unsupported после Wounds11–23; конкретная следующая граница ещё не выбрана. Перед расширением сопоставить реальные остановки party-прогонов и полезность для оценки боя группы с монстрами, затем закрепить одну конечную функцию. Повторный full/wheel ради перехода сессии не нужен.

Commit/push выполняет пользователь.
