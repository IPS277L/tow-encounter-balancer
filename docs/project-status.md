# Текущий статус проекта

Дата обновления: 2026-11-04.

## Текущий этап

**M23 завершена в выбранной границе.** Empire Official с Dagger — первый книжный Brute2 с последствием раны в PC native/trials/process/подборе и текущем JSON1. [Контракт ADR-0078](decisions/ADR-0078-pc-official-first-wound-broken-boundary.md), [правило](rules/npc-profile-catalog.md#official-broken-m23), [factory/JSON/CLI-примеры](examples/m23/README.md).

GM1.1 стр.98: Toughness3/Resilience3, Dagger Close2d/3 Damage2,1H, Athletics3d/3, W1Broken/W2defeated. Pistol явно unselected. Heard It All Before сохранён как inactive для нынешней family без Persuade/Distract. Catalog wound_bands описателен; factory теперь берёт injury limit из exact definition. Прежние три combat loadouts сохраняют свои definitions/snapshots, у metadata лишь добавлен пустой wound_bands.

Фактический living Brute0→1 PcProfileWoundProof ACK применяет Broken один раз после raw Attack. Другие PC могут продолжить, Official защищается обычной Athletics; вторая рана до собственного хода даёт нормальный defeat. По выбору пользователя stop наступает перед TurnStart именно следующего живого Broken Official, после всей pending queue/предыдущих Critical/end phases. Другие участники, party death, final budget и новая разрешённая PC-side сохраняют свой порядок. Бегство, route/Recovery и автоматический flee/defeat не подставляются.

PcNpcBrokenTurnUnsupported — отдельный native variant: actor, actual причинившая рану Attack execution ID, exact Brute0→1 change и source RULE-PROFILE-TALABEC-007:first-wound-broken. Фиктивных PC table_total нет. Полный replay отличает причины одинаковых changes двух NPC и запрещает дальнейшие steps после actual stop. Прежние PC unsupported variants сохраняют данные/приоритет.

Trials/process сохраняют actual prefix; unsupported остаётся в знаменателе и исключает candidate из выбора. JSON1/команды/метрики прежние, новых wire fields/version и миграции старых пар нет. Python catalog metadata/native result API расширен в текущей development family.

## Последняя проверка

При `PYTHONPATH=src` `.venv/Scripts/python.exe .cache/m23_check_subsystem.py` — **262 tests OK/34.984s**,28модулей,0failures/errors/skips. Log `.cache/m23-pc-npc-subsystem.log`. Включены M21–M23, ближайшие PC source/Attack/Protection/party/Minion-Brute trials/balance и прежние M19/M20 unsupported paths с process-проверками. Код/тесты заморожены до запуска; после него менялась документация. Это единый зелёный адресный прогон, не полный regression PC/проекта.

Добавлены6catalog/wound-band tests,10native/pure/cause guards и4integration. Детерминированно проверены W1ACK→Broken, ordinary Athletics/W2victory до окна, stop после PC turn/end phase, другие NPC до Official, обязательный Critical tail, party death до окна, unchanged authored static Brute и actor-specific parent cause двух одинаковых0→1 changes. Missing/duplicate/forged/replayed receipts отвергаются. Final-budget/new-round priorities явно pure, без заявления о reachable fresh prefix. Source review замечаний не оставило; real Windows process совпал с sequential, typed cached NPC-stop alias не стал observation.

Локальные `.cache` scripts/logs не являются частью репозитория. В [ADR-0078](decisions/ADR-0078-pc-official-first-wound-broken-boundary.md#проверка) есть адресная unittest-команда для новой копии. Shared K1, другие families, schema/CLI mechanism/dependencies/resource discovery/entry points не менялись; full regression/wheel не запускались.

Оба M23 requests выполнены настоящим CLI на финальном коде с exact full request echo. Simulation дала3objective/3unsupported из6trials, без PC losses/party defeat/limit; проверка тех же native seeds подтвердила все3причины npc_broken_turn. Balance сохранил unsupported в знаменателе и не выбрал ни одного из4кандидатов. Подробности/наблюдения находятся в примерах, это не истинная вероятность/оптимум и не поражение игроков. Старые28request/result pairs M9–M22 неизменны относительно HEAD, текущие схемы/source roundtrip проверены без пересчёта их Monte Carlo.

`.cache/m23_verify_docs.py` проверил13изменённых Markdown/1140локальных targets, все30current request/result pairs M9–M23 и UTF-8/newline/whitespace изменённых файлов. `git diff --check` успешен.

## Ограничения

Четыре registered combat loadouts: Footpad, Townsfolk, Brigand Axe, Official Dagger. Последний исполняет первую рану/Broken и вторую рану до своего хода, но не собственное бегство. Единственный can_leave_zone не задаёт safe/fastest route. Снятие Broken при сохраняющейся profile Wound отложено; supported Ability/Condition нельзя игнорировать ради Attack.

Одна aware Close Zone/fixed orders/priorities, здоровая initial party,13Close primary weapons и optional1H backup. Сохраняются Wounds1–23/lethal24+, source-aware Conditions, mandatory Critical/Defenceless end phases, actual anatomical/2H stops и static authored Brutes. Нет новых ranges/spatial/Champions/общего inventory/Brawn/лечения/campaign/optimal AI. Greatsword требует уточнения бонуса. Costs/losses при stop/limit отражают исполненный prefix.

## Следующий шаг

Предложение — конечное продолжение Broken NPC по явно заданному маршруту. Сначала выбрать safe/fastest-path facts и значение ухода для caller objective; будущее recovery при сохраняющейся Wound отдельно не подставлять. M24 ещё не согласована; общий spatial/AI и другие профили автоматически не включать. [Очередь](roadmap.md), [индекс вопросов](open-questions.md), [Broken continuation details](open-questions-details.md#продолжение-broken-npc).

Перед M23 рабочее дерево было чистым; пользователь сохранил M22 в Git. Изменения M23 незакоммичены; commit/push выполняет пользователь.
