# Текущий статус проекта

Дата обновления: 2026-11-04.

## Текущий этап

**M18 завершена в выбранной границе.** Dagger, Axe, Warhammer и Morning Star дополняют прежние Staff/Sword в PC melee. [Правила и контракт](rules/equipment.md#исполняемая-pc-граница-m18), [запускаемые примеры](examples/m18/README.md).

Damage и Traits привязаны к актуальному actor/target: Dagger S−1 допускает базовый0; Axe получает +1 Damage против брони, сохраняя Resilience; Warhammer +1d Attack против Staggered; Morning Star S+1/−1d к собственным Melee при Staggered, включая Help. Sword сохраняет Defence bonus. Drained/cap/minimum die, Glorious initial roll и canonical Damage/trace сохраняются. Источник брони по numeric bonus трактуется только внутри нынешней сцены без shields/Abilities.

Все шесть видов используют существующий hand/drop/swap/pickup, Wounds1–23/lethal24+, Help/Fate/ally Recover. Trials/process/count search фиксируют полную party и оружие, меняя только NPC counts. Текущий PC JSON1 расширяет только enum `party[].pc.weapon`; новых полей, метрик, версии, compatibility ветвей или миграции старых примеров нет. Использован существующий механизм подготовки, отдельное архитектурное решение не вводилось.

## Последняя проверка

При `PYTHONPATH=src` `.venv/Scripts/python.exe .cache/m18_check_subsystem.py` — **496 tests OK/71.000s**,50модулей PC M9–M18 и связанных K1 Attack/Protection/Help/Recover/Turn/Test/Fate/Wounds;0failures/errors/skips. Log `.cache/m18-pc-subsystem.log`. Код и тесты заморожены до запуска; после него менялась документация. Это единый зелёный адресный прогон, не полный regression проекта. M8 Recover callers повторно не запускались: общий Recover в M18 не менялся.

В составе14новых детерминированных weapon tests,3admission/generation,3integration и54current codec/schema tests. Проверены hit/miss/tie и подделка Damage/trace/source, базовый Damage0, actual Staggered и физический Help, Drained/cap/forced minimum die, Glorious, тяжёлая рана руки/смена руки/drop/pickup. Pure preparation cases явно отделены от native encounter traces. Реальный Windows process совпал с sequential; поиск сохраняет оружие/Fate/support policy и aggregate-only границу.

Локальные `.cache` scripts/logs не являются частью репозитория. Адресная команда для новой копии:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.unit.test_m18_pc_weapons tests.unit.test_m18_pc_weapon_admission tests.integration.test_m18_pc_weapons tests.unit.test_m9_pc_melee_json tests.unit.test_m9_pc_melee_json_schemas -q
```

Первые integration попытки выявили ошибку имени поля в новом тесте и известный sandbox WinError5 для Windows spawn. Поле исправлено до checkpoint; настоящий process выполнен с разрешённым доступом, без skip/fallback. Структура исходников/зависимости/сборка/resources/entry points не менялись; full regression/wheel не запускались.

Оба M18 requests исполнены настоящим CLI на финальном коде, с exact full request echo. Все18прежних пар M9–M17 и27stored candidate scenarios прошли schema/source roundtrip; их JSON остался неизменным относительно HEAD. Новые результаты/наблюдения — в README/JSON M18; малая выборка не объявляется оценкой вероятности или оптимумом.

`.cache/m18_verify_docs.py` проверил10изменённых Markdown/978локальных targets, все20current request/result pairs M9–M18 и UTF-8/newline/whitespace изменённых файлов. `git diff --check` успешен.

## Ограничения

Здоровая initial party с одним из шести одноручных Close weapons на PC, numeric Melee Minions/Brutes без on-Wound abilities, одна Close Zone и fixed orders/priorities. Две руки/dual wield, mounted/Charge, другие ranges, Stealth conceal/Staff terrain и общий inventory не подключены. Numeric armour bonus не определяет wearing armour для произвольных shields/Abilities вне заявленного scope.

Сохраняются source-aware ongoing Conditions и mandatory Critical/Defenceless end phase; невозможная повторная анатомия даёт actual pending GM-stop. Ally Recover снимает лишь разрешённые Staggered/Prone, не лечит раны/Defenceless/Critical. Остальные Help/Fate/Lucky/optimal AI, лечение, campaign и полный NPC catalog остаются за границей. При limit/unsupported costs/потери описывают лишь observed prefix.

## Следующий шаг

Предложение — двуручное Close-оружие PC. Сначала определить конечный набор, хват и последствия ран рук/потери оружия/Recover; для Greatsword отдельно сверить тип Defence bonus. M19 ещё не согласована; остальной каталог не включать автоматически. [Очередь](roadmap.md), [индекс вопросов](open-questions.md).

Перед M18 рабочее дерево было чистым; пользователь сохранил M17 в Git. Изменения M18 незакоммичены; commit/push выполняет пользователь.
