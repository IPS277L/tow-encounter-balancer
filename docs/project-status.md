# Текущий статус проекта

Дата обновления: 2026-11-04.

## Текущий этап

**M8 — завершающая приёмка ограниченной магической симуляции.** Функциональная граница реализована; конечный scope, свидетельства и две оставшиеся контрольные работы закреплены в [checklist M8](m8-completion.md). Веха ещё не объявлена завершённой. Полный каталог книжной магии и последствий не входит в её условия закрытия.

Последняя реализованная функция — [standard self Recover после Battered Leg](decisions/ADR-0064-battered-leg-prone-removal.md#дополнение-2026-11-04-standard-self-recover): явный `recover_self` расходует один action slot и снимает sourced Prone, сохраняя Wound, completed Endurance, free move и histories. Enemy Close допустим. Уменьшение Pool и последующий skipped-Casting contribution применяются последовательно. Free self-stand остаётся отдельным выбором без автоматического Recover fallback.

## Последняя проверка

2026-11-04: исходный M8 scope сопоставлен с реализацией и прежними ADR. Исправлено устаревшее ожидание Battered object в существующей simulation CLI6 матрице: добавлено обязательное `prone_policy:null`.

При `PYTHONPATH=src`: `.venv/Scripts/python.exe -m unittest tests.integration.test_m8_magic_json_v6.M8MagicJsonV6IntegrationTests.test_module_console_and_both_backends_echo_full_v6_source_with_equal_aggregates -v` — 1 test OK/10.324s, module/console×sequential/process; лог `.cache/m8-closure-cli-simulation.log`. Подробные успешные адресные проверки Recover сохранены в [ADR-0064](decisions/ADR-0064-battered-leg-prone-removal.md#дополнение-2026-11-04-standard-self-recover).

Проверены 4909 локальных ссылок в 208 Markdown-файлах, отсутствующих targets нет; пять контрольных test methods найдены статически. `git diff --check` успешен. Текущий полный набор и установленный пакет после серии64/Recover ещё не проверены; единый зелёный full не заявляется. Их проверка — R1/R2 ниже.

## Ограничения

Один authored Wizard/Curse и numeric Shooting Minions; явные scene/GM facts. Точные ограничения opt-in последствий перечислены в checklist и соответствующих ADR. Allied removal, arbitrary mixed injuries/treatment/save-resume не подключены. Новые неподдержанные последствия сохраняют явный stop, mandatory continuations имеют приоритет. UNSUPPORTED_PATH остаётся в знаменателе trials и запрещает итоговый выбор кандидата при подборе. Magic поддерживает только JSON6, другие families — свой единственный1.

## Точный следующий шаг

Выполнить R1 из [конечного checklist M8](m8-completion.md): один завершающий полный source regression и адресное закрытие найденных нарушений текущего контракта. Затем R2 — одна установленная delivery проверка стабилизированного current6 пакета/CLI. Для ограниченной M8 обязательных новых игровых consumers не осталось; весь каталог книги — дальнейший backlog.

Следующая installed-проверка — R2 финальной контрольной точки M8 после R1. Commit/push выполняет пользователь.
