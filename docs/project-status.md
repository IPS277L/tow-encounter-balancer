# Текущий статус проекта

Дата обновления: 2026-11-04.

## Текущий этап

**M8 завершена в согласованной ограниченной границе.** Один Champion-Wizard/Curse, явные scene facts, opt-in последствия, independent trials, подбор составов и текущий JSON6 прошли финальную приёмку. [Checklist M8](m8-completion.md) хранит scope и подробные результаты R1/R2. Полный каталог книжной магии и последствий не входит в эту отметку готовности.

Последняя игровая функция — free self-stand и standard self Recover после Battered Leg по [ADR-0064](decisions/ADR-0064-battered-leg-prone-removal.md). Эта сессия выполнила только приёмку; исходники, правила и тесты не менялись.

## Последняя проверка

R1: при `PYTHONPATH=src` команда `.venv/Scripts/python.exe -m unittest discover -s tests -v` — **4312 tests, OK за 1597.756s**, единый полный прогон без failures/errors/skips. Windows, Python3.12.4, исходное чистое дерево `0c26270`.

R2: одна offline wheel-сборка и fresh install, `pip check`; все 470 `.py/.json` совпали source→wheel→installed, 25 schemas/329 refs разрешились offline. Установленные simulate-magic и balance-magic проверены module/console из внешнего cwd, включая один process case и current6 source/report/error. Приёмка R2 составная: исправлено неверное ожидание stderr в локальном аудиторе, затем проверены только три error cases; успешные CLI, сборка и полный набор не повторялись. Логи и hash wheel — в checklist.

После обновления документации проверены 4910 локальных ссылок в 208 Markdown-файлах, отсутствующих targets нет; `git diff --check` успешен.

## Ограничения

Один authored Wizard/Curse и numeric Shooting Minions; явные scene/GM facts. Точные ограничения opt-in последствий перечислены в checklist и соответствующих ADR. Allied removal, arbitrary mixed injuries/treatment/save-resume не подключены. Новые неподдержанные последствия сохраняют явный stop, mandatory continuations имеют приоритет. UNSUPPORTED_PATH остаётся в знаменателе trials и запрещает итоговый выбор кандидата при подборе. Magic поддерживает только JSON6, другие families — свой единственный1.

## Точный следующий шаг

Выбрать следующую законченную продуктовую веху: сопоставить оставшиеся ограничения с целью симулятора/балансировщика и предложить приоритетный пользовательский сценарий с конечными критериями готовности. Очередь новых игровых функций после M8 пока не утверждена; автоматически добавлять очередной Wound/Miscast consumer или повторять R1/R2 не требуется.

Commit/push выполняет пользователь.
