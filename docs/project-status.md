# Текущий статус проекта

Дата обновления: 2026-11-04.

## Текущий этап

**M9 завершена в выбранной ограниченной границе.** Один немагический PC против Minions, Wounds1–10, полный supplied Fate с явной стратегией отказа, source-bound бой, independent trials, подбор численности и отдельный JSON1/CLI реализованы и проверены. [Контракт и итоговая приёмка ADR-0065](decisions/ADR-0065-first-pc-melee-encounter.md).

[Публичные PC-примеры](examples/m9/README.md) выполнены настоящими командами и воспроизведены установленным пакетом. Основные команды: `simulate-pc-melee` и `balance-pc-melee`. M8 закрыта ранее; её результаты — в [checklist M8](m8-completion.md).

## Последняя проверка

При `PYTHONPATH=src` команда `.venv/Scripts/python.exe -m unittest discover -s tests -v` — **4404 tests, OK за 1353.865s**, единый полный run без failures/errors/skips. Исходники и tests не менялись во время прогона. Лог `.cache/m9-final-source-regression.log`.

Одна offline wheel-сборка и fresh install: `pip check`, hashes всех 495 `.py/.json` source→wheel→installed, 32 schemas/414 offline refs и 8 installed CLI cases успешны. Module/console, один real process и три input errors выполнены из внешнего cwd без source/editable paths; ответы совпали с сохранёнными source-примерами. Лог `.cache/m9-final-delivery.log`; report/hash wheel и подробные адресные проверки — в ADR-0065. Полный набор и сборка на границе M9 выполнены по одному разу.

Документация: 4954 локальные ссылки в 210 Markdown-файлах проверены, отсутствующих targets нет. `git diff --check` и whitespace/newline checks новых текстовых файлов успешны. В дереве 54 незакоммиченных файла M9; commit/push не выполнялись.

## Ограничения

M9: один здоровый initial PC/Staff или Sword, обычные numeric Melee Minions, одна явная Close Zone, фиксированные policies и полный supplied Fate. Common Wounds1–10/repeated/mixed поддержаны;11–23дают actual pending lifecycle stop до completion/daily/effects; lethal24+ завершается после Near Miss decline. Полноценная партия, общий inventory, другие оружие/Talents/тактики, treatment/campaign/save-resume не подключены. UNSUPPORTED_PATH остаётся в знаменателе trials и исключает кандидата из selection. Magic сохраняет JSON6; PC и другие families — свой единственный1.

## Точный следующий шаг

Выбрать следующую законченную продуктовую веху по оставшимся ограничениям M9: группа PC, более широкий NPC roster либо активные решения Fate/тактика. Сначала сопоставить пользу и конечные критерии, затем закрепить конкретную границу по книгам. Следующее направление ещё не выбрано; автоматически добавлять очередную Wound/сборку/полный прогон не требуется.

Commit/push выполняет пользователь.
