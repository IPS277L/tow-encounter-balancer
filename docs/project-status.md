# Текущий статус проекта

Дата обновления: 2026-11-03.

## Текущий этап

Организация работы упрощена: короткие точки входа, история отдельно, ADR только для существенных решений, законченные функциональные вехи, адресные проверки и небольшие общие test builders. Постоянные инструкции — в [AGENTS.md](../AGENTS.md); навигация — в [индексе документации](README.md). Шесть обзорных документов сокращены с 405919 до 18677 символов; исходные тексты сохранены в [архиве](archive/README.md).

Последняя функциональная веха — [ADR-0063](decisions/ADR-0063-single-current-magic-contract.md): единственный Magic JSON6. Код симулятора, игровые правила, API, зависимости и сборка при текущем упрощении не менялись.

## Последняя проверка

Четыре JSON unit-модуля переведены на [общие fixtures](../tests/support/magic_json_fixtures.py). 81 test ID закрыт составно: 79 прошли сразу, два оставшихся обращения к прежнему helper исправлены; ровно два повтора OK за 0.532s. Это не единый зелёный прогон81. Проверены независимость mutable fixtures, равные но разные policy objects, сохранность source/неизвестных полей без исправления версии. Import-only discovery собрал4266tests без loader errors; это не их исполнение.

Команда исходного набора: `.venv/Scripts/python.exe -m unittest tests.unit.test_m8_magic_json tests.unit.test_m8_magic_balance_json tests.unit.test_m8_magic_json_v2 tests.unit.test_m8_magic_balance_json_v2 -v`, при `PYTHONPATH=src`. Успешные проверки без нового влияющего изменения не повторять. Проверены 4859 локальных ссылок в 206 Markdown-файлах и `git diff --check`; отсутствующих targets нет. Full regression и wheel не запускались. Результаты прошлой wire-приёмки сохранены в ADR-0063.

## Ограничения

M8 ограничен Wizard/Curse и явными opt-in continuations. Battered Leg: первая ordinary Attack Wound5, resolved/untreated/unhealed, normal Endurance Test и explicit unmounted/no-external-Conditions facts. Failure сохраняет sourced Prone без removal consumer. Новые последствия после success ограничены exact-injury gate60; arbitrary mixed injuries/treatment/save-resume не открыты. UNSUPPORTED_PATH остаётся в знаменателе trials. Прежние Magic1–5 не поддерживаются; другие families имеют собственный единственный формат1.

## Точный следующий шаг

Следующая законченная функция — снятие sourced Prone после Battered Leg в поддерживаемом M8. Сначала адресно сверить Free Actions/Prone/Wound5 в книгах, определить полный owner transition и сохранение Wound/completion/history при gate60; затем реализовать нужные слои и адресные проверки одной вехой. Новый ADR нужен только при новом архитектурном решении. Эта задача по организации работы не начинала реализацию Prone.

Следующая installed-проверка доставки — перед внешним выпуском либо при изменении соответствующего механизма/риске. Commit/push выполняет пользователь.
