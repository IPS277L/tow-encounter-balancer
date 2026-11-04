# Текущий статус проекта

Дата обновления: 2026-11-04.

## Текущий этап

**M12 завершена в выбранной границе.** Все PC Wounds11–23 продолжаются в нынешнем melee-бою с Minions/Brutes: body/hand/loss/clutch consequences, Critical end phase, actionless Defenceless turns и source-aware ongoing Conditions. Пользователь выбрал продолжение Attack/Recover с книжными осложнениями. [Контракт и составная приёмка ADR-0068](decisions/ADR-0068-pc-heavy-wound-continuation.md).

[Текущие примеры M12](examples/m12/README.md) запускаются прежними `simulate-pc-melee` / `balance-pc-melee`. Единственная PC JSON1 требует `random_side_policy` и `heavy_wound_policy: continue_fighting`; старое hand-only поле удалено. Magic остаётся6. Все8current M9–M12 requests/results обновлены.

## Последняя проверка

**Приёмка составная:** одна полная `.venv/Scripts/python.exe -m unittest discover -s tests -v` при `PYTHONPATH=src` — **4471 tests OK/1581.418s**, без failures/errors/skips; затем локальная PC source-binding коррекция и **59 затронутых checks OK/6.649s**, включая2новыхIDs/6native subcases и representative heavy process. Это не единый full run всех финальных файлов. Logs: `.cache/m12-full-regression.log`, `.cache/m12-final-pc-recheck.log`.

1019source/tests `.py/.json` не менялись во время full run. После него изменены только3PC projection/helper files и1unit-regression file для Critical sources при incidental HandSwap/clutch/regrip. Общий K1 остался тем же; проверены manifests `.cache/m12-source-manifest.json` / `.cache/m12-final-source-manifest.json`. Успешный full и дорогая CLI-матрица не повторялись; wheel/install без изменения поставки не запускались.

До checkpoint149PC tests OK/41.748s,72engine OK/4.597s,53common K1 OK/0.009s,28wire/schema OK/2.103s. Все8requests выполнены настоящими CLI с lossless echo; M12 simulation/balance после последней коррекции повторно совпали с сохранёнными ответами. Подробные команды/состав, source guards и закрытые review gaps находятся в ADR-0068.

Документация:15изменённых Markdown-файлов/1045локальных targets и все8current request/result пар проверены. UTF-8/newline/whitespace и `git diff --check` успешны; CLI help и current schema paths согласованы.

В M12 simulation прежние12generic heavy stops заменились4objective/6party_defeated/2round_limit, unsupported0;9trials с подтверждёнными потерями. Balance:0,1 и1,1 —8objective из8,2,1 —6objective/2round_limit; выбран2,1 затем0,1. Это наблюдения конкретных seeds/trials/policies, не фиксированные вероятности.

## Ограничения

Здоровая initial party со Staff/Sword, обычные numeric Melee Minions/Brutes без on-Wound abilities, одна Close Zone и фиксированные порядки/priorities. Полный supplied Fate сохраняется с явным optional decline. Поддержаны Wounds1–23 и lethal24+ lifecycle; Defenceless жив, не действует/не Oppose и не входит в outnumbering, но получает обязательные end-turn Tests. Потери при limit/unsupported — только подтверждённые до остановки.

Физически невозможная повторная анатомическая потеря без существующей цели сохраняет actual pending `unavailable_anatomical_target`: GM замена не выбрана. Unsupported остаётся в denominator и запрещает selection. Лечение, post-healing Endurance22, active Fate, ally Recover/Help, Champions/Monstrosities, общее inventory/campaign/save-resume и остальные тактики не добавлены.

## Точный следующий шаг

Обязательного остатка M12 нет. Рекомендуемое следующее направление — первая активная Fate policy для PC Near Miss. Сначала выбрать условия burn/предел ресурса и конечную границу по существующему K1; M13 ещё не согласована. Не включать автоматически все Fate/AI решения, лечение или общий campaign.

Перед M12 рабочее дерево было чистым, M11 закоммичена пользователем. Изменения M12 остаются незакоммиченными; commit/push выполняет пользователь.
