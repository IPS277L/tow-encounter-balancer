# Текущий статус проекта

Дата обновления: 2026-11-04.

## Текущий этап

**M16 завершена в выбранной границе.** Нынешний PC melee поддерживает Help для конкретного incoming Protection Test союзника, с явным Defence/Athletics, вместе с прежними Melee Help/Fate/ранами. [Контракт ADR-0072](decisions/ADR-0072-pc-protection-help-policy.md), [запускаемые примеры](examples/m16/README.md).

При выборе защиты берётся первый текущий live NPC в enemy activation order, только если его ожидаемая цель по enemy target priority — выбранный PC. Snapshot связывается с точными beneficiary/Test/Skill этого NPC в данном раунде. Получатель может уже завершить ход. Self Recover помощника имеет прежний приоритет, недоступная помощь возвращает Attack/Recover; optimal AI не добавлен.

Original Protection options содержат actual Help до собственного initial roll/Glorious. При гибели NPC, смене Skill после pickup или Defenceless бонус не переназначается. Подтверждённые unused snapshots не блокируют outcome; новых owner banks/RNG/metrics нет. Count search фиксирует роли и выбирает первый оставшийся NPC внутри конкретного candidate, не переписывая authored Help policy.

Единственный PC JSON1 требует у ненулевого `help_policy` три поля: beneficiary_id, target и protection_skill. Melee mode — `melee_attack`/null, защита — `first_incoming_protection`/defence либо athletics. Обычный `help_policy: null` не изменён. Четыре M15JSON-документа мигрированы без смены gameplay/counters; M9–M14 файлы не менялись. Старый объект только с beneficiary не поддерживается. Magic JSON6 и остальные families не затронуты.

## Последняя проверка

При `PYTHONPATH=src` `.venv/Scripts/python.exe .cache/m16_check_subsystem.py` — **393 tests OK/69.786s**,39модулей PC M9–M16 и ближайших K1 Protection/Help/Turn/Test/Fate/Drained/Wound consumers;0failures/errors/skips. Log `.cache/m16-pc-subsystem.log`. Production и tests заморожены до запуска; после него менялась только документация. Это единый зелёный адресный прогон, не полный regression проекта.

В составе11новых native/pure Protection Help tests,4model/generation,4integration с actual Windows spawn/count search/cache guards и46current codec/schema tests. Нативно проверены Defence Help, earlier beneficiary, zero/multiple/cap, Sword/Glorious обоих PC, гибель выбранного NPC при другом живом, Wound4/drop→Recover/pickup→skill mismatch и Wound15→Critical failure→Defenceless без Protection. Положительная Athletics application и Drained проверены отдельно через чистую preparation с реальным предшествующим Help receipt, без заявления об отдельном таком native бою.

Независимое review не нашло source/target/skill/timing дефекта. Общий K1 и сборка/dependencies/resources/entry points не менялись; full/wheel и повтор дорогой матрицы не запускались. В ADR-0072 есть адресная unittest-команда для чистой копии без локальной `.cache`.

Оба M16 requests фактически исполнены CLI через `.cache/m16_execute_examples.py` с полным совпадением request echo. Production с первого рабочего прототипа до freeze не менялась, сохранённые reports относятся к финальному поведению. Результаты фиксированной тактики находятся в README/JSON примеров, не объявляются фиксированными вероятностями или оптимумом. `.cache/m16_verify_docs.py` проверил14изменённых Markdown/998локальных targets,16current request/result pairs/схемы/UTF-8; `.cache/m16_verify_wire_examples.py` подтвердил сохранение14старых пар и их gameplay/prior counters относительно HEAD. `git diff --check` успешен.

## Ограничения

Здоровая initial party со Staff/Sword, numeric Melee Minions/Brutes без on-Wound abilities, одна Close Zone и fixed orders/priorities. Сохраняются Wounds1–23/lethal24+, source-aware ongoing Conditions и mandatory Critical/Defenceless end phase; невозможная повторная анатомия даёт actual pending GM-stop.

Help — same-Skill Melee для конкретной Attack или Defence/Athletics для первого ожидаемого Protection. Не поддержаны произвольный выбор NPC/другие relevant Skills/GM approval/chains/optimal AI. Protection skill не навязывается получателю, bonus не переносится на другого actor/Test/Skill/round. Help counters считают actual failed/unused actions, а не добавленные кубы.

Остаются отдельные Glorious/Near Miss criteria без auto refresh, остальные Fate/Lucky options не подключены. Near Miss не отменяет смерть от отдельного Critical Test. Нет лечения, campaign/general inventory, ally Recover, других PC weapons и полного NPC catalog.

## Следующий шаг

Рекомендован стандартный Recover для союзного PC в Close Range. Перед реализацией закрепить явную тактику выбора целей/Conditions и ограничения ongoing Wounds; это не лечение ран или optimal AI. M17 ещё не согласована, прочие действия не включать автоматически. [Очередь](roadmap.md), [индекс вопросов](open-questions.md).

Перед M16 рабочее дерево было чистым; пользователь сохранил M15 в Git. Изменения M16 незакоммичены; commit/push выполняет пользователь.
