# Текущий статус проекта

Дата обновления: 2026-11-04.

## Текущий этап

**M13 завершена в выбранной границе.** В существующем PC melee против numeric Minions/Brutes работает активный Near Miss с явно заданными порогом Wounds Table и минимальным остатком rating. Фактический burn меняет ресурс только своего PC через книжный lifecycle; начальный supplied Fate и его история сохраняются. [Контракт ADR-0069](decisions/ADR-0069-pc-near-miss-policy.md), [запускаемые примеры](examples/m13/README.md).

Trials начинают с независимых копий одного начального источника. Simulation/balance summary показывают новые burns по всей party, число боёв с расходом и общий расход; прежняя supplied история не включается. Балансировщик фиксирует policies и по-прежнему ранжирует по objective rate, без новой оптимизации стоимости Fate.

Единственная PC JSON1 требует `near_miss_policy`: null при `decline_optional_fate`, объект с `minimum_table_total`/`minimum_rating_to_keep` при `near_miss_at_threshold`. Python source тоже требует явного поля. M9–M12 примеры мигрированы без изменения игровых исходов; Magic JSON6 не затронута.

## Последняя проверка

При `PYTHONPATH=src`:

- `.venv/Scripts/python.exe .cache/m13_check_subsystem.py` —22модуля PC M9–M13 и K1 Fate Near Miss/Wound lifecycle, **197тестов:196успешно,1failure** на неявном default нового source-поля;0errors/skips. Log `.cache/m13-pc-subsystem.log`. Этот прогон не называется единым зелёным.
- После удаления default и явного `near_miss_policy=None` в builder: `.venv/Scripts/python.exe -m unittest tests.unit.test_m9_pc_melee_models tests.unit.test_m9_pc_melee_json tests.unit.test_m9_pc_melee_json_schemas tests.unit.test_m13_pc_near_miss tests.unit.test_m13_pc_near_miss_statistics tests.integration.test_m13_pc_near_miss -v` — **74теста OK/5.649s**. Log `.cache/m13-final-recheck.log`.
- После добавления отдельной проверки supplied burn history: `.venv/Scripts/python.exe -m unittest tests.integration.test_m13_pc_near_miss -v` — **5тестов OK/2.913s**, включая реальный Windows spawn, compact cached-source rejection и count search. Log `.cache/m13-final-integration.log`.
- Финальная проверка exact-type summary counters, включая null: `.venv/Scripts/python.exe -m unittest tests.unit.test_m13_pc_near_miss_statistics tests.unit.test_m9_pc_melee_json -q` — **26тестов OK/0.997s**. Log `.cache/m13-final-summary.log`.

Приёмка составная: неуспешная проверка и её зависимости перепроверены; успешная дорогая CLI-матрица не повторялась. Первый вспомогательный launcher без защиты `__main__` остановлен и исправлен до приведённого197-test run; это не ошибка production spawn. Общий K1, сборка/dependencies/resources/entry points не менялись; нового full regression/wheel нет. Исторический checkpoint M12 и его ограничения остаются в [ADR-0068](decisions/ADR-0068-pc-heavy-wound-continuation.md).

Оба M13 request выполнены настоящим `python -m towr` через `.cache/m13_execute_examples.py`, полный request echo совпал. Simulation12trials:7objective/0party_defeated/5round_limit/0unsupported,15новых burns в10боях,5подтверждённых смертей companion. Это наблюдения конкретного входа/политики, не фиксированные вероятности. Согласованность10пар request/result, схем, ссылок и изменённых документов проверена `.cache/m13_verify_docs.py`; `git diff --check` успешен.

## Ограничения

Здоровая initial party со Staff/Sword, ordinary numeric Melee Minions/Brutes без on-Wound abilities, одна Close Zone, фиксированные orders/priorities. Сохраняется M12 поддержка Wounds1–23 и lethal24+, mandatory Critical/Defenceless end phase и source-aware ongoing Conditions. Физически невозможная повторная анатомическая потеря даёт actual pending `unavailable_anatomical_target`; GM-замена не выбрана.

Near Miss отменяет новую рану, но не смерть от отдельного провала Critical Test. Другие optional Fate uses пока declined; лечения, campaign, общего inventory, ally Recover/Help, иных PC weapons и полного NPC catalog нет. Потери и burns при limit/unsupported отражают только наблюдённый prefix.

## Следующий шаг

Рекомендованная следующая функция — явная PC policy обычного расходования Fate на Glorious Test в том же бою. Сначала закрепить критерии выбора Tests и резерв обычных трат; они отличаются от постоянного rating и burn Near Miss. M14 ещё не согласована; не включать автоматически все Fate options или общий AI. [Очередь](roadmap.md), [индекс вопросов](open-questions.md).

Перед M13 рабочее дерево было чистым: пользователь уже сохранил M12 в Git. Изменения M13 остаются незакоммиченными; commit/push выполняет пользователь.
