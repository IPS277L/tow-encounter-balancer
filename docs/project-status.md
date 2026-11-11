# Текущее состояние проекта

Дата: 2026-11-12. **M70 завершена: PC Hochland/Aim/Fate Second Action и отдельные counters.** Нормативные книги — Player’s Guide1.4 и Gamemaster’s Guide1.1. [Правило](rules/equipment.md#pc-hochland-m70), [Fate](rules/fate.md#pc-second-action-m70), [ADR-0112](decisions/ADR-0112-pc-hochland-aim-and-fate-second-action.md), [CLI-примеры](examples/m70/README.md), [очередь](roadmap.md#после-m70), [вопросы](open-questions.md).

## Что работает сейчас

Ограниченные ranged/melee/mixed Minion families, M8 Wizard и PC группа против Minions/числовых Brutes сохраняются. Wounds1–23/lethal24+, Critical/Defenceless, Glorious/Near Miss, Help/ally Recover, shields/backup, NPC Pistol/Reload, Protection choice/Help, Blunderbuss nearby действуют в принятых границах. NPC каталог59/shared ranged14 прежние. Все13PG ranged profiles допущены в ограниченном PC исполнении; это не полная реализация всей книги.

M70 добавляет Hochland2H/Damage6/ignores armour/mandatory Aim/Reload4 с10required ranged facts (ordinary firearm9+Awareness от Initiative). На Short−1d; Wounds Table+1d применяется только к подходящей shared PLAYER/Champion policy, не к нынешним numeric Minions. Initial grip=BOTH/no shield, другие12profiles и их source shapes сохраняются.

PC выполняет actual standard Aim/Awareness Test, затем по configured aim_second_action_policy и фактическому funding/reserve оплачивает Second Action/ATTACK slot2 и стреляет до NPC approach. Aim0success тоже удовлетворяет prerequisite; bonus подчиняется cap/Drained. Awareness Glorious в первом срезе отклоняется, Shooting Glorious может тратиться после Second Action по своему остатку/критериям. Без policy/funding обычный Aim не создаёт free Shoot; следующий Close→backup прежний.

Hoc-source может явно иметь Lucky: первая Fate трата бесплатна даже при rating0, включая выбранный Glorious после backup, если Second Action не использован. Остальные PC loadouts сохраняют запрет Lucky в source. Canonical paid/free funding и reserve одинаково проверяются в выборе и бюджете статистики, Second Action и Glorious делят actual ledger. Это spend, не burn.

PcAimProof/PcAimSecondActionProof/PcAimConsumptionProof сохраняют actual action/roll/source/slot/resource/one-use APPLIED или LOST. Другой собственный action/Recover/melee теряет Aim, incoming Protection/end phase не потребляют его. Consuming receipt завершается до другого перехода/terminal; обычный TurnEnd не может пропустить выбранный доступный Second Action. Реальная Wound8/CANNOT_AIM блокирует новый Aim до RNG, даже после Recover. Hand/mandatory/CI/Defenceless/endphase guards сохраняются.

Aim считается действием, ресурсный spend не третьим действием. Glorious counters теперь считают только GLORIOUS_TEST, Second Action отдельно. Typed compact records/summary содержат conditional .aim с rows всех PC и totals для Aim/SECOND_ACTION events только при Hoc-capable source. Counts включают Lucky-free events, не являются числом оплаченных session points. Current JSON1/остальные families прежние, compatibility aliases/новой wire version нет.

## Последняя проверка

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

Подготовить конкретную границу пространственного PC encounter: Medium/Long opening, реальные Zone/movement и выбранная тактика NPC. Учесть speed/Manoeuvre/Charge/Range; новая дистанция сама не гарантирует безопасный Aim→Shoot. Public scope ещё не выбран; не добавлять фиктивное ожидание NPC или setup prelude без решения пользователя. Альтернативные направления перечислены в roadmap.

Реализация и документация M57–M70 сохранены пользователем в commitf24abbe (M70 P1), следующем после0299d6b. После него незакоммичен только этот project-status.md: добавлены окончательные результаты статической/source/pickle сверки и актуальная база. Commit/push выполняет пользователь.
