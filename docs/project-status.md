# Текущий статус проекта

Дата обновления: 2026-11-04.

## Текущий этап

**M21 завершена в выбранной границе.** Первые точные книжные боевые NPC-подпрофили — Footpad и Empire Townsfolk — подключены к PC native/trials/process/подбору и текущему JSON1. [Контракт ADR-0076](decisions/ADR-0076-first-pc-book-npc-catalog.md), [правила](rules/npcs.md#исполняемый-каталог-pc-m21), [factory/JSON/CLI-примеры](examples/m21/README.md).

Footpad GM1.1 стр.97: Dagger Close3d/3 Damage2,1H; Protection Athletics3d/3. Townsfolk стр.96: Dagger Close2d/2 Damage2,1H; напечатанная Athletics2d/2. Оба Minion, Toughness3/Resilience3 без брони, defeat после первой Wound. Protection не пересчитывается из Agility, PC weapon Traits не добавляются по названию NPC-оружия.

Typed каталог хранит книгу/версию/главу/страницу и inactive Ability name/scope/effect. Lurker Footpad — Grim spotting Awareness вне боя; Streetwise Townsfolk — +1d Awareness против pickpocket. В нынешнем aware/noambush бою этих ситуаций нет. Fact no_additional_abilities означает отсутствие дополнительных применимых effects, а не удаление способностей. Это боевые подпрофили для данной сцены, не полные NPC-карточки/весь бестиарий.

Factory каждый раз создаёт независимый здоровый armed opposition snapshot. Reserved definition IDs и известные root/attack/protection book source IDs принимаются лишь с exact canonical definition и nested types; переименование только root IDs не обходит защиту. Canonical baseline строится отдельно, не делит изменяемый через bypass граф с input. Обычные authored numeric profiles сохраняются и проходят cheap early return без создания canonical graphs.

NPC Protection теперь допускает Athletics/Defence и передаёт actual Skill общему preparation. Текущий PC JSON1 требует `definition.protection.skill`; parser не подставляет Defence, encoder не теряет Skill. Все24прежние пары M9–M20 дополнены явным defence без изменения остальных игровых значений/counters. Версия/метрики прежние, нового сокращённого wire input или скрытого resolve по имени оружия нет.

## Последняя проверка

При `PYTHONPATH=src` `.venv/Scripts/python.exe .cache/m21_check_subsystem.py` — **228 tests OK/54.937s**,23модуля,0failures/errors/skips. Log `.cache/m21-pc-npc-subsystem.log`. Включены все M21, ближайшие PC source/execution/party/Minion-Brute trials/balance/CLI, representative weapon/backup paths и K1 Protection/Attack execution. Код/тесты заморожены до запуска, после него менялась документация. Это единый зелёный адресный прогон, не полный PC M9–M21 и не полный regression проекта.

Добавлены9catalog/factory/provenance tests,4literal native,6codec/schema и3integration. Проверены exact printed3d/3 vs2d/2, NPC Damage2, actual Athletics в preparation, scene gating, known-ID spoof rejection до RNG, cached enum aliases, независимые canonical graphs, real Windows process parity, fixed definitions/Skill в mixed count search и aggregate-only граница. Review обнаружил и до checkpoint закрыл обход provenance с переименованными root IDs, но сохранёнными nested book sources; effect magnitudes также сохранены в metadata.

Локальные `.cache` scripts/logs не являются частью репозитория. В [ADR-0076](decisions/ADR-0076-first-pc-book-npc-catalog.md#проверка) есть адресная unittest-команда для новой копии. Успешные не затронутые тяжёлые подсистемы M12–M20, M8 callers и shared kernel не прогонялись заново полностью. Сборка/dependencies/resource discovery/entry points не менялись; full regression/wheel не запускались.

Оба M21 requests выполнены настоящим CLI на финальном коде с exact full request echo. Малые наблюдения находятся в README/JSON примеров и не объявляются вероятностями/оптимумом. `.cache/m21_verify_migration.py` подтвердил24прежние request/result pairs и35candidate sources roundtrip; после удаления нового explicit Defence поля все прежние значения совпадают с HEAD. Пересчёта старых Monte Carlo результатов не было и он не нужен для этой механической миграции.

`.cache/m21_verify_docs.py` проверил11изменённых Markdown/1064локальных targets, все26current request/result pairs M9–M21 и UTF-8/newline/whitespace изменённых файлов. `git diff --check` успешен.

## Ограничения

Два registered book combat profiles, здоровая initial party,13Close primary weapons и optional1H backup, numeric Minions/Brutes без неподдержанных применимых effects, одна Close Zone/fixed orders/priorities. Существующие авторские numeric NPC не становятся проверенными книжными профилями по произвольной подписи. Применимые Abilities Brigand/Peasant/Watch и другие NPC, ambush/pickpocket, новые loadouts/ranges/spatial/Champions не включены автоматически.

Сохраняются Wounds1–23/lethal24+, source-aware ongoing Conditions, обязательные Critical/Defenceless end phases, actual anatomical GM-stop и fixed backup policy. Greatsword требует уточнения бонуса. Dual wield, произвольная смена, Brawn, лечение/campaign, весь каталог spells/NPC и optimal AI остаются за границей. Costs/losses при stop/limit отражают только исполненный prefix.

## Следующий шаг

Предложение — первый книжный NPC с применимой боевой Ability: Brigand / Craven Opportunist (+2d вместо +1d при outnumbering), GM97. Сначала зафиксировать явный Melee-loadout Axe и границу применения, сохранив факт выбора из полной карточки с Warbow. M22 ещё не согласована; новые ranged/spatial пути и весь бестиарий не включать автоматически. [Очередь](roadmap.md), [индекс вопросов](open-questions.md).

Перед M21 рабочее дерево было чистым; пользователь сохранил M20 в Git. Изменения M21 незакоммичены; commit/push выполняет пользователь.
