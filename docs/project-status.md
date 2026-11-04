# Текущий статус проекта

Дата обновления: 2026-11-04.

## Текущий этап

**M11 завершена: группа PC против Minions и обычных числовых Brutes.** Supplied NPC wound limit, nonterminal Wound acknowledgement, defeat только на фактическом пределе, mixed count search и явные policy/limit в текущем JSON1 реализованы через существующие слои. [Контракт и приёмка ADR-0067](decisions/ADR-0067-pc-melee-profile-brutes.md). M10 завершена ранее: [приёмка ADR-0066](decisions/ADR-0066-pc-party-melee-encounter.md).

[Смешанный roster M11](examples/m11/README.md), [Minion-группа M10](examples/m10/README.md) и [одиночный M9](examples/m9/README.md) выполнены настоящими CLI-командами. Команды прежние: `simulate-pc-melee`, `balance-pc-melee`; current1 требует `party` и явные NPC `injury_policy`/`wound_limit`, без старых shapes/compatibility. Magic сохраняет6.

## Последняя проверка

M11: **181 tests OK/51.332s**, один адресный run всей PC family M9–M11 и ближайших K1 injury/kernel/Attack, shared schemas/CLI. Реальные mixed sequential/process trials, full source/counters, count search и representative module/console подтверждены. Windows process/temp cases сразу выполнены вне sandbox из-за известного WinError5. Набор и результаты — в ADR-0067; log `.cache/m11-subsystem.log`. Это адресный набор, не полный regression проекта.

Все6 public M9/M10/M11 requests исполнены реальными командами; request echo сверены, результаты сохранены.7PCschemas/90offline refs и shared bundle проверены. Full/wheel M11 не запускались: K1 reducers и доставка не менялись; последние полные/installed проверки M9 не выдаются за новую приёмку.

Документация:13изменённых Markdown-файлов/887локальных targets и все6current request/result пар проверены; UTF-8/newline/whitespace и `git diff --check` успешны. CLI help отражает mixed Minion/Brute roster.

Фактические наблюдения: слабая M11 party —12unsupported из12, в одном prefix подтверждена casualty; сильная party/Brute-only —8objective из8, с1Minion —6objective/2unsupported, с2Minions —2objective/6unsupported. Только Brute-only выбран, denominator не фильтруется. Это не фиксированные вероятности; тяжёлые PC-раны остаются главным ограничением оценки трудных боёв.

M10 закоммичена пользователем (`44ef3ab`); перед M11 рабочее дерево было чистым. Commit/push агент не выполняет.

Изменения M11 остаются незакоммиченными.

## Ограничения

Непустая здоровая initial party со Staff/Sword против обычных numeric Melee Minions/Brutes, одна явная Close Zone, фиксированные порядки/target priorities и policies, независимый полный Fate каждого PC. Brutes только static profile без on-Wound behaviours/abilities. PC Wounds1–10/repeated/mixed поддержаны;11–23дают actor-bound pending lifecycle stop до completion/daily/effects; lethal24+ завершается после Near Miss decline. Active Fate, помощь/ally Recover, Champions/Monstrosities, общий inventory, другие оружие/Talents/тактики, treatment/campaign/save-resume не подключены. Потери при limit/unsupported — только подтверждённые до остановки. Unsupported остаётся в знаменателе и исключает кандидата из selection.

## Точный следующий шаг

Согласованная M11 закрыта, обязательного остатка нет. Приоритет следующей функции — продолжение тяжёлых PC-ран, ограничивающих оценку сложных боёв; прежде реализации определить конечный диапазон и решения для Critically Injured/Defenceless, использования повреждённой руки и обязательных поз. Конкретная M12 ещё не согласована; не подставлять house rules или автоматически добавлять весь каталог. Full/wheel ради перехода сессии не нужны.

Commit/push выполняет пользователь.
