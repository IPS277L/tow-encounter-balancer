# Текущий статус проекта

Дата обновления: 2026-11-04.

## Текущий этап

**M22 завершена в выбранной границе.** Brigand с явным Axe-only loadout и Craven Opportunist подключён к PC native/trials/process/подбору и текущему JSON1. [Контракт ADR-0077](decisions/ADR-0077-pc-brigand-craven-opportunist.md), [книжное правило](rules/npc-profile-catalog.md#brigand-craven-m22), [factory/JSON/CLI-примеры](examples/m22/README.md).

GM1.1 стр.97: Minion1Wound, Toughness3/Resilience4 armoured, Axe Close3d/3 Damage3,1H, Athletics3d/2. Warbow из полной карточки сохранён как unselected; выбор carried Axe до боя разрешён GM93. PC weapon Traits не добавлены NPC по названию. Footpad/Townsfolk остаются прежними; каталог теперь содержит три registered combat loadouts.

Craven заменяет обычный +1d на +2d при фактическом Melee superiority и GM approval. Считаются все пригодные союзники обеих сторон, не только Brigands; defeated/Defenceless исключаются, Staggered и завершившие ход продолжают считаться. Бонус пересчитывается перед каждой Attack. Без approval или превосходства нет modifier; +1 и +2 не складываются. Остальные NPC и PC сохраняют обычные правила, existing Drained filter снимает положительные bonuses.

Явный pure helper выбирает modifier после exact book definition validation. Rule ID RULE-PROFILE-TALABEC-004:craven-opportunist сохранён в actual TestRequest/journal; full-source replay отвергает altered/stacked/false-source modifiers. Metadata содержит active/inactive Abilities и unselected gear, не исполняется как программа. Fact no_additional_abilities исключает неподдержанные применимые effects, разрешая реализованный Craven.

Wire/метрики/CLI-команды не менялись; новых полей/version и миграции нет. Metadata Python API использует общий PcBookNpcAbility и явные active/inactive tuples. Count search сохраняет exact definitions/gear/party/Fate/policies и вычисляет способность в реальном составе каждого боя.

## Последняя проверка

При `PYTHONPATH=src` `.venv/Scripts/python.exe .cache/m22_check_subsystem.py` — **209 tests OK/23.000s**,21модуль,0failures/errors/skips. Log `.cache/m22-pc-npc-subsystem.log`. Включены все M21/M22, ближайшие PC source/execution/party/Minion-Brute trials/balance и K1 Protection/Attack execution. Код/тесты заморожены до запуска; после него менялась документация. Это единый зелёный адресный прогон, не полный regression PC/проекта.

Добавлены5catalog/loadout tests,10native/pure/request-guard и4integration. Детерминированно проверены ровно5d Brigand без stacking, смешанные союзники/обычный Footpad+1, GM withholding, равенство и PC superiority, динамическая потеря бонуса после defeat союзника, отсутствие неуказанного NPC Axe Damage trait. Drained и исключение Defenceless — явно pure preparation boundaries; fresh Brigand Minion такой Drained prefix в нынешнем native path не получает. Real Windows process совпал с sequential; actual ability proofs, cached bonus forgery, full JSON echo и fixed canonical source в count search проверены.

Локальные `.cache` scripts/logs не являются частью репозитория. В [ADR-0077](decisions/ADR-0077-pc-brigand-craven-opportunist.md#проверка) есть адресная unittest-команда для новой копии. Shared K1, другие families, CLI mechanism, schema/resource discovery/dependencies/entry points не менялись; тяжёлые не затронутые PC paths, full regression/wheel не запускались повторно.

Оба M22 requests выполнены настоящим CLI на финальном коде с exact full request echo. Simulation содержит5objective/1limit из6trials, без party defeat/unsupported, с частичными PC losses; подробности и результаты count search — в README/JSON примеров. Малые наблюдения не объявляются вероятностями/пользой Ability/оптимумом. Старые26request/result pairs M9–M21 неизменны относительно HEAD; текущие схемы и source roundtrip проверены без пересчёта старых Monte Carlo результатов.

`.cache/m22_verify_docs.py` проверил13изменённых Markdown/1120локальных targets, все28current request/result pairs M9–M22 и UTF-8/newline/whitespace изменённых файлов. `git diff --check` успешен.

## Ограничения

Три registered combat loadouts: Footpad, Townsfolk, Brigand Axe. Книжная карточка Brigand целиком и Warbow не исполняются; это PC-family расширение, не автоматическое включение Craven в M6/другие NPC-сценарии. Неподдержанные применимые Abilities других NPC не отбрасываются. Authored numeric profiles с собственными identifiers остаются обычными caller inputs, не становятся проверенными книжными профилями или носителями Craven по совпадению чисел.

Одна aware Close Zone, fixed orders/priorities, здоровая initial party,13Close primary weapons и optional1H backup; прежние Wounds1–23/lethal24+, source-aware Conditions, mandatory Critical/Defenceless end phases и actual anatomical GM-stop сохраняются. Нет ambush/pickpocket, новых ranges/spatial/loadout switching/Champions, произвольного inventory/Brawn/лечения/campaign/optimal AI. Greatsword требует уточнения бонуса. Costs/losses при stop/limit отражают только исполненный prefix.

## Следующий шаг

Предложение — первый книжный Brute с изменением состояния после раны. Сначала сверить полную карточку/Abilities, выбрать конечный loadout/продолжение в нынешней сцене; необходимую GM/AI policy запросить явно. M23 ещё не согласована, остальные профили/действия/ranges/spatial и весь бестиарий не включать автоматически. [Очередь](roadmap.md), [индекс вопросов](open-questions.md).

Перед M22 рабочее дерево было чистым; пользователь сохранил M21 в Git. Изменения M22 незакоммичены; commit/push выполняет пользователь.
