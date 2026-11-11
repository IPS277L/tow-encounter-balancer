# Текущее состояние проекта

Дата: 2026-11-12. **Динамический генератор доступен через локальный UI, Python и JSON/CLI; M70 сохранена.** Нормативные книги — Player’s Guide1.4 и Gamemaster’s Guide1.1. [Правило](rules/equipment.md#pc-hochland-m70), [Fate](rules/fate.md#pc-second-action-m70), [ADR-0112](decisions/ADR-0112-pc-hochland-aim-and-fate-second-action.md), [CLI генератора](examples/dynamic/README.md), [очередь](roadmap.md#после-m70), [вопросы](open-questions.md).

## Приоритет после уточнения цели

2026-11-12 пользователь подтвердил исходную цель: динамически генерировать NPC с характеристиками, навыками, талантами/способностями и снаряжением и подбирать состав через Monte Carlo. Развитие после M8 сместилось к вручную допущенным книжным профилям/сетапам; это не заменяет генератор. Предыдущий следующий шаг про пространственный encounter снят с ближайшего приоритета.

Текущий PC search перебирает только количества supplied одинаковых definitions в группах. Числовые authored NPC возможны, но generator их параметры не создаёт, а abilities/admission часто привязаны к canonical IDs. Следующий результат — новые допустимые профили, отсутствующие во входном reserve/каталоге, и их сквозной поиск/оценка. Механики и строгая валидация сохраняются; IDs книжных NPC перестают быть способом выдачи abilities в новом пути. Уточнение реализовано в Python API и отдельном JSON1 генератора без смены прежних family-контрактов; [граница и решение](decisions/ADR-0113-dynamic-npc-generation-and-adaptive-search.md).

## Динамический генератор — первый срез

`GeneratedNpc` хранит WS/S/T/Agility, Melee/Athletics, Staff/Dagger, Light Armour и optional authored Drained-on-hit. Builder выводит attack/Protection/Damage/Resilience и независимый Minion state без ID dispatch. Application принимает партию/пространство параметров без готового NPC reserve; random restarts и мутации элиты создают новые составы, включая разные профили при фиксированном числе. Финалисты проходят независимую validation выборку; итог хранит полный source, компоненты, outcomes, интервалы, фактическую стоимость и proposal limit. [Пример](examples/dynamic/README.md), [ADR-0113](decisions/ADR-0113-dynamic-npc-generation-and-adaptive-search.md).

Граница: stationary all-Close melee PCs против Minions, Athletics NPC Protection, без щита/других weapon Traits/книжных талантов. Authored Drained требует явного допуска, не является автоматически выданным талантом. Сохраняются Wounds/Fate/Recover и unsupported базового simulator. Duration = started rounds, включая censored prefix; ранжирование по близости к win target, затем duration. Это ограниченный поиск, не доказательство оптимума и не полный генератор книги. Старый каталог не переносился массово; kernel/backend не менялись.

## Минимальный UI — текущая проверка

Поля визуально разделены на3адаптивные группы: «Состав противников» (2поля), «Цели боя» (3) и «Поиск и точность» (6). Скрипт синхронизации/исполнения сохранён без изменений. Добавлены короткие приглушённые подсказки под всеми11полями формы; `aria-describedby` связывает их с соответствующими inputs. Проверены3группы/11полей, структура HTML и ссылки подсказок; группировка визуально проверена в headless Edge. Игровое исполнение не менялось, игровые тесты ради оформления не запускались.

По запросу пользователя реализован `towr ui`: форма основных параметров, связанный редактируемый JSON, загрузка/форматирование/скачивание запроса, настоящий запуск генератора и полный JSON результата/ошибок со скачиванием. Начальный файл выбирается через --request либо repo example, в браузере — file picker. Loopback-only стандартный ThreadingHTTPServer, один расчёт одновременно, busy/elapsed state; без новых dependencies/правил/wire version. [Запуск](examples/dynamic/README.md#локальный-ui).

`PYTHONPATH=src; python -m unittest tests.integration.test_local_ui tests.unit.test_m4_cli -q` —13pass. Отдельно `python -m unittest tests.integration.test_local_ui_browser -q` —1pass в headless Edge вне sandbox (browser launcher требует доступ ОС). Браузерная проверка: JSON→form и form→JSON, дробные targets, бюджет, точность seed, actual generation/result и malformed JSON. Windows Edge launcher первоначально завершался до child process; тест исправлен ожиданием дерева через Start-Process -Wait. Desktop screenshot проверен визуально. Это14адресных тестов в двух прогонах; full/wheel не запускались: packaging/resources и engine неизменны.

## JSON/CLI динамического генератора

Команда `towr generate-encounter INPUT` (или `-` для stdin), family dynamic_encounter_search JSON1. Вход содержит party без врагов/target_priority/defeat_decisions, facts/day, search_space, npc_count, рациональные targets, seed/budget и общий defeat disposition. Первый wire backend sequential. Closed request/result/error schemas и local registry связывают существующие PC fragments и PC JSON1 replay. Adapter не меняет правила; application result validator проверяет источник каждого кандидата, stage seeds, allowed components, выбор/порядок validation и budget без новых trials. Выход содержит точный source echo, все observations, selected IDs и full replay. [Самостоятельный вход](examples/dynamic/search.request.json).

Последняя проверка:27различных адресных тестов в нескольких прогонах. `PYTHONPATH=src; python -m unittest tests.integration.test_dynamic_encounter_json -q` —9pass после исправления схемы ошибок. Базовые10test_dynamic_encounter прошли в первом составном запуске (19тестов:16pass и3ошибки схемы, исправлены). `python -m unittest tests.unit.test_m4_cli tests.integration.test_m9_pc_melee_cli.PcMeleeCliIntegrationTests.test_input_errors_retain_command_family_and_lexical_errors_do_not_trust_id -q` —8pass. Новые проверки включают file/stdin, malformed/closed admission, source echo, forged reports, независимые replay и execution errors. Это адресный составной результат, не full regression. Module CLI smoke:3explored/2validated/2selected/12trials; `--help` содержит новую команду. Новые schema resources/offline refs проверены без wheel: entry point/package discovery не менялись.

## Предыдущая проверка Python-среза

Адресный составной результат:47различных тестов прошли. Команды с `PYTHONPATH=src`: `python -m unittest tests.integration.test_dynamic_encounter tests.integration.test_m9_pc_melee_balance tests.integration.test_m9_pc_melee_simulation tests.unit.test_m29_pc_hit_conditions -q` —31тест,28pass/3process errors из-за sandbox WinError5; три упавших process-теста повторены вне sandbox —3pass. После добавления source/component проверки: `python -m unittest tests.integration.test_dynamic_encounter tests.unit.test_m9_pc_melee_balance -q` —26pass (10повторных+16дополнительных). Это адресные прогоны, не full regression.

`docs/examples/dynamic/search.py --candidates 3 --trials 2 --finalist-trials 3 --top 2 --max-rounds 3 --allow-authored-drained`:3новых состава,2validation/selected,12trials. Все5replay документов прочитаны текущим JSON parser; один finalist повторно исполнен с совпавшей оценкой. Full/wheel не запускались: общий движок/сборка не менялись.

## Что работает сейчас

Ограниченные ranged/melee/mixed Minion families, M8 Wizard и PC группа против Minions/числовых Brutes сохраняются. Wounds1–23/lethal24+, Critical/Defenceless, Glorious/Near Miss, Help/ally Recover, shields/backup, NPC Pistol/Reload, Protection choice/Help, Blunderbuss nearby действуют в принятых границах. NPC каталог59/shared ranged14 прежние. Все13PG ranged profiles допущены в ограниченном PC исполнении; это не полная реализация всей книги.

M70 добавляет Hochland2H/Damage6/ignores armour/mandatory Aim/Reload4 с10required ranged facts (ordinary firearm9+Awareness от Initiative). На Short−1d; Wounds Table+1d применяется только к подходящей shared PLAYER/Champion policy, не к нынешним numeric Minions. Initial grip=BOTH/no shield, другие12profiles и их source shapes сохраняются.

PC выполняет actual standard Aim/Awareness Test, затем по configured aim_second_action_policy и фактическому funding/reserve оплачивает Second Action/ATTACK slot2 и стреляет до NPC approach. Aim0success тоже удовлетворяет prerequisite; bonus подчиняется cap/Drained. Awareness Glorious в первом срезе отклоняется, Shooting Glorious может тратиться после Second Action по своему остатку/критериям. Без policy/funding обычный Aim не создаёт free Shoot; следующий Close→backup прежний.

Hoc-source может явно иметь Lucky: первая Fate трата бесплатна даже при rating0, включая выбранный Glorious после backup, если Second Action не использован. Остальные PC loadouts сохраняют запрет Lucky в source. Canonical paid/free funding и reserve одинаково проверяются в выборе и бюджете статистики, Second Action и Glorious делят actual ledger. Это spend, не burn.

PcAimProof/PcAimSecondActionProof/PcAimConsumptionProof сохраняют actual action/roll/source/slot/resource/one-use APPLIED или LOST. Другой собственный action/Recover/melee теряет Aim, incoming Protection/end phase не потребляют его. Consuming receipt завершается до другого перехода/terminal; обычный TurnEnd не может пропустить выбранный доступный Second Action. Реальная Wound8/CANNOT_AIM блокирует новый Aim до RNG, даже после Recover. Hand/mandatory/CI/Defenceless/endphase guards сохраняются.

Aim считается действием, ресурсный spend не третьим действием. Glorious counters теперь считают только GLORIOUS_TEST, Second Action отдельно. Typed compact records/summary содержат conditional .aim с rows всех PC и totals для Aim/SECOND_ACTION events только при Hoc-capable source. Counts включают Lucky-free events, не являются числом оплаченных session points. Current JSON1/остальные families прежние, compatibility aliases/новой wire version нет.

## Предыдущая проверка M70

На финальном коде51tests — OK8.973s: Fate Glorious/statistics, все новые native16/source6/JSON8. Проверены Aim0/nonzero/I vs BS/cap/Drained/Glorious, paid/Lucky/reserve/decline, action budget/proofs/replay/source/target, loss/Recover/backup, CANNOT_AIM8/CI/terminal, строгие counters/combined funding/условный report/echoes/search. Один actual process comparison (2workers/batch1/2trials) — OK2.204s, sequential и process records/aggregates совпали. Всего31новая проверка включая этот process.

Предшествующий адресный checkpoint405tests дал402passed/3failed; это устаревшие pre-ranged catalogue/pre-M63 Help/pre-M54 Glorious expectations, они исправлены. После исправлений и source-policy TurnEnd guard адресные100tests — OK15.693s. Затем исправлен Lucky funding для later melee Glorious и повторены связанные51tests выше. Это несколько адресных прогонов, не единый зелёный405/full project regression.

В приёмке устранены Hoc-scoped Lucky admission, запрет Aim от Shaking Grip8, обход выбранного Second Action через общий TurnEnd, смешение всех Fate spends с Glorious и игнорирование бесплатного Lucky в Glorious selector. Shared K1 не переопределялся; новые regression cases подтверждают каждую границу.

```powershell
$env:PYTHONPATH='src'
.venv/Scripts/python.exe -m unittest tests.unit.test_m14_pc_glorious tests.unit.test_m14_pc_glorious_statistics tests.unit.test_m70_pc_hochland tests.integration.test_m70_pc_hochland_source tests.integration.test_m70_pc_hochland_json
.venv/Scripts/python.exe -m unittest tests.unit.test_m9_pc_melee_json_schemas tests.unit.test_m14_pc_glorious_statistics tests.unit.test_m9_pc_melee_execution tests.unit.test_m9_pc_melee_simulation tests.unit.test_m10_pc_party_statistics tests.unit.test_m64_pc_ranged_execution tests.unit.test_m69_pc_blunderbuss tests.unit.test_m70_pc_hochland tests.integration.test_m70_pc_hochland_source tests.integration.test_m70_pc_hochland_json
.venv/Scripts/python.exe -m unittest tests.integration.test_m70_pc_hochland_process -v
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m70/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m70/pc-melee-balance.request.json
```

Actual CLI: simulation seed42/4trials/4Minions→4objective/48actions/10started/6completed rounds, без потерь PC;8Aim/8Second events с rows4/4/0. Count search3–4Minions/2состава×2trials→по2objective/14и20actions/4Aim/4Second events в каждом. Эти выборки демонстрируют интерфейс, не истинные вероятности или оптимальный состав; каждый trial начинает с исходного ресурса.

Статическая/source/schema/pickle сверка:124current request/result pairs M9–M70 и268candidate echoes/offline schemas/full source — OK;244прежнихJSON побайтно прежние. NPC59/shared14 сохраняются.45Markdown/2620local targets/current anchors/99Python AST/UTF-8/whitespace — OK. New source/enum/armoured True-False/neutral stop pickle — OK; actual battle с6Aim/Fate/consumption proofs прошёл pickle roundtrip и projection replay. Локальный .cache/m70_verify.py воспроизводит сверку и не входит в репозиторий. Full/wheel/backend matrix не повторяются без оснований: backend/package discovery/resources/dependencies/entry points прежние, для новых compact fields выполнен один representative actual process. Предыдущие checkpoints сохранены в относящихся ADR.

## Ограничения

Short opening: одна Zone/две исходные группы, ranged PC и simple authored numeric Melee Minions/Athletics. Aim/Second Action policy только Hoc-source, optional Awareness Glorious не подключён. Setup turn до обнаружения группы, Medium/Long opening, другие Zone/PC movement/kiting/новая NPC тактика не добавлены. Blunderbuss остаётся одной explicit initial NPC-группой/atomic numeric impacts, не смешанными Close-группами/friendly fire model.

Named NPC/Abilities/Brutes/Champions сохраняются в прежних all-Close сценах; ranged без Close optimum в fresh all-Close запрещены. Текущая Short-политика после approach использует backup без возврата к primary, полный fresh Aim→Shoot→Reload4→новый Aim→Shoot не заявляется. Supply явный, finite magazine/campaign simulator отсутствует. Невозможная повторная анатомия и непринятые продолжения сохраняют actual prefix/точные stops. Raw snapshots не save/resume API.

## Следующий шаг

Расширить общее пространство генерируемых NPC: добавить совместимые weapon Traits и их typed исполнение/проверки prerequisites, затем тип NPC и таланты по полезности поиска. Сохранить единый вход generate-encounter и прямой путь компоненты→бой→Monte Carlo→финалисты; не возвращаться к очереди именных statblocks и отдельных сетапов. Ближайший кандидат — общие Close weapon-компоненты (Axe/Sword/Warhammer/Morning Star) с корректными Traits, а не копии книжных NPC.

Текущие изменения: local UI adapter/page, ui CLI dispatch, HTTP/browser integration tests и относящаяся документация/ADR-0113. Commit/push выполняет пользователь.
