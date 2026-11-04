# Текущий статус проекта

Дата обновления: 2026-11-04.

## Текущий этап

**M19 завершена в выбранной границе.** Семь двуручных Close weapons — Pickaxe, Flail, Billhook, Halberd, Glaive, Greataxe, Greathammer — работают вместе с шестью прежними одноручными. [Контракт ADR-0074](decisions/ADR-0074-pc-two-handed-close-weapons.md), [правила](rules/equipment.md#исполняемая-pc-граница-m19), [JSON/CLI-примеры](examples/m19/README.md).

BOTH grip отделён от анатомических LEFT/RIGHT. В текущем JSON1 `initial_weapon_hand` обязан быть `both` для2H и `left`/`right` для1H. Source/state/schema/codec проверяют эту связь. Actual Attack/Defence и нынешний weapon-assisted Help требуют обе пригодные руки; травмированная рука12 вызывает Critical при использовании, в том числе при Recover с восстановлением хвата. Drop4/8/12 роняет весь предмет независимо выбранной руки; Recover возвращает BOTH, сохраняя остальные self/ally benefits.

Пользователь выбрал сохранять полный результат раны и завершать trial как UNSUPPORTED_PATH при недоступном2H хвате. После фактических16/18/20, Near Miss window и всей immediate queue canonical owner возвращает `two_handed_grip_unavailable` с actor/Wound/source. При18 явный drop/clutch выполнен;16/20 не подставляют решение о дальнейшем удержании предмета одной рукой. Raw roll и отменённая Near Miss рана не вызывают stop. Последующие journal steps запрещены. Это не автоматическое поражение или ROUND_LIMIT.

Trials/process/search сохраняют полную party/оружие/хват/Fate/support policies и прежние метрики. Unsupported остаётся в знаменателе, кандидаты с actual unsupported не выбираются. JSON1 расширяет enum/grip без новых полей/версии, compatibility ветвей и миграции старых примеров.

## Последняя проверка

При `PYTHONPATH=src` `.venv/Scripts/python.exe .cache/m19_check_subsystem.py` — **528 tests OK/86.109s**,54модуля PC M9–M19 и связанных K1 Attack/Protection/Help/Recover/Turn/Test/Fate/Wounds;0failures/errors/skips. Log `.cache/m19-pc-subsystem.log`. Код/тесты заморожены до запуска, после него менялась документация. Это единый зелёный адресный прогон, не полный regression проекта.

В составе9новых pure traits tests,13native grip/Wounds/Fate tests,6codec/schema и4integration. Детерминированно проверены семь Damage profiles, actual Flail/Greathammer/Glaive modifiers, armour boundary, drop обеих сторон/RecoverBOTH, Critical12 в Recover/Defence/Help, Glorious, полные stops16/18/20 и их отмена Near Miss, forged stop/single grip/replay/пропуск шага. Реальный Windows spawn совпал с sequential. Actual unsupported observations/candidate exclusion проверены отдельно от fake summaries; source/typed cached proof guards сохранены.

Локальные `.cache` scripts/logs не являются частью репозитория. В [ADR-0074](decisions/ADR-0074-pc-two-handed-close-weapons.md#проверка) есть адресная unittest-команда для новой копии. Общий Recover/K1 не менялся, M8 callers не запускались повторно; сборка/dependencies/resources/entry points не менялись. Full regression/wheel не запускались.

Оба M19 requests выполнены настоящим CLI на финальном коде, с exact full request echo. Simulation показывает смешанную2H party; balance — отдельно слабого Pickaxe PC и actual unsupported при части составов. Наблюдения — в README/JSON примеров, не оценки истинной вероятности/оптимума. Все20прежних M9–M18 request/result pairs и29candidate scenarios прошли schema/source roundtrip; их JSON неизменен относительно HEAD.

`.cache/m19_verify_docs.py` проверил12изменённых Markdown/1041локальный target, все22current request/result pairs M9–M19 и UTF-8/newline/whitespace изменённых файлов. `git diff --check` успешен.

## Ограничения

Здоровая initial party с одним из13Close weapons на PC, numeric Melee Minions/Brutes без on-Wound abilities, одна Close Zone и fixed orders/priorities. Greatsword не подключён: тип буквального `+1 to Defence` требует уточнения. Запасное оружие/переключение, dual wield, другие ranges/Charge/mounts и общий inventory не входят в M19. Pickaxe harvesting и Billhook mounted trait вне текущей сцены; numeric armour bonus трактуется только без shields/Abilities.

Wounds1–23/lethal24+, source-aware ongoing Conditions, mandatory Critical/Defenceless end phase и прежние1H hand swaps сохраняются. Для2H недоступный хват16/18/20 — выбранная остановка; невозможная повторная анатомия сохраняет прежний pending GM-stop. Ally Recover снимает допустимые Staggered/Prone и не лечит раны/Defenceless/Critical. Другие Help/Fate/Lucky, лечение/campaign, полный NPC catalog и optimal AI остаются за границей. Costs/losses при stop/limit относятся только к исполненному prefix.

## Следующий шаг

Предложение — запасное одноручное оружие и явное переключение после утраты2H возможности. Сначала определить carry limit, способ смены/подбора и приоритет относительно Recover/Help/обязательных последствий; это пока не согласованная M20. Greatsword можно уточнять отдельно. [Очередь](roadmap.md), [индекс вопросов](open-questions.md).

Перед M19 рабочее дерево было чистым; пользователь сохранил M18 в Git. Изменения M19 незакоммичены; commit/push выполняет пользователь.
