# Текущее состояние проекта

Дата: 2026-11-16. **Динамический генератор доступен через локальный UI, Python и JSON/CLI; M70 сохранена.** Нормативные книги — Player’s Guide1.4 и Gamemaster’s Guide1.1. [Правило](rules/equipment.md#pc-hochland-m70), [Fate](rules/fate.md#pc-second-action-m70), [ADR-0112](decisions/ADR-0112-pc-hochland-aim-and-fate-second-action.md), [CLI генератора](examples/dynamic/README.md), [очередь](roadmap.md#после-m70), [вопросы](open-questions.md).

## Приоритет после уточнения цели

2026-11-12 пользователь подтвердил исходную цель: динамически генерировать NPC с характеристиками, навыками, талантами/способностями и снаряжением и подбирать состав через Monte Carlo. Развитие после M8 сместилось к вручную допущенным книжным профилям/сетапам; это не заменяет генератор. Предыдущий следующий шаг про пространственный encounter снят с ближайшего приоритета.

Текущий PC search перебирает только количества supplied одинаковых definitions в группах. Числовые authored NPC возможны, но generator их параметры не создаёт, а abilities/admission часто привязаны к canonical IDs. Следующий результат — новые допустимые профили, отсутствующие во входном reserve/каталоге, и их сквозной поиск/оценка. Механики и строгая валидация сохраняются; IDs книжных NPC перестают быть способом выдачи abilities в новом пути. Уточнение реализовано в Python API и отдельном JSON1 генератора без смены прежних family-контрактов; [граница и решение](decisions/ADR-0113-dynamic-npc-generation-and-adaptive-search.md).

## Динамический генератор — первый срез

`GeneratedNpc` хранит WS/S/T/Agility, Melee/Athletics, Staff/Dagger, Light Armour и optional authored Drained-on-hit. Builder выводит attack/Protection/Damage/Resilience и независимый Minion state без ID dispatch. Application принимает партию/пространство параметров без готового NPC reserve; random restarts и мутации элиты создают новые составы, включая разные профили при фиксированном числе. Финалисты проходят независимую validation выборку; итог хранит полный source, компоненты, outcomes, интервалы, фактическую стоимость и proposal limit. [Пример](examples/dynamic/README.md), [ADR-0113](decisions/ADR-0113-dynamic-npc-generation-and-adaptive-search.md).

Граница NPC: stationary all-Close melee PCs против Minions, Athletics NPC Protection, без NPC-щита/других NPC weapon Traits/книжных NPC-талантов. PC equipment/Lucky/potions и первый магический путь описаны ниже. Authored Drained требует явного допуска, не является автоматически выданным талантом. Сохраняются Wounds/Fate/Recover и unsupported базового simulator. Duration = started rounds, включая censored prefix; ранжирование по близости к win target, затем duration. Это ограниченный поиск, не доказательство оптимума и не полный генератор книги. Старый каталог не переносился массово; kernel/backend не менялись.

## Текущий срез: магия персонажей в генераторе

[ADR-0120](decisions/ADR-0120-pc-elemental-magic-in-dynamic-encounters.md) принят и реализован. В существующей динамической партии доступны Маг (Wizard)1–4, Разум (Reason), Воля (Willpower), Elementalism и запомненные Lightning Blast/Fire Breath с настоящими Casting действиями. Exacting accumulation, last-roll Potency, locked9, Fate, Armour/Shield Grim, interruption/Recover и обязательные Miscasts исполняются в общем бою. Заклинания применяют прямой Damage, реальные Staggered/Wounds и defeat; они не превращены в оружейные атаки. Casting и предметы/зелья выбираются автоматически по текущему состоянию без вложенного Monte Carlo. [Пользовательский вход/пример](examples/dynamic/README.md#магия-персонажей).

Пользователь выбрал одну пригодную руку без отдельного освобождения; здоровая приоритетна, Hand12 вызывает настоящий Critical. Каждый trial получает независимое magic state. Полные native proofs, source/readmission/replay и clock guards сохраняют однократность и не позволяют победе обойти Miscast/Wound pending. Лечение зельем и expiry чужой причины не стирают независимые магические Conditions. Смерть мага в свой ход не создаёт нового действия или Critical.

Граница: дневная all-Close сцена без выхода против numeric/generated Minions, подходящие Arcane Paraphernalia, два Elementalism spells; без Mixing/Dispelling/grimoire/других школ и пространственных эффектов. Исполняются строки Miscast1–4/7–16/19–22/25–32/35–36/39+;5–6/17–18/23–24/33–34/37–38 сохраняют actual roll и останавливаются перед неподдержанным продолжением. Такой observed unsupported исключает состав из рекомендаций; на больших выборках это существенное ограничение, которое нельзя маскировать победой/no-op. Недоступная повторная анатомия сохраняет прежнюю точную границу.

Current Dynamic/PC JSON1 дополнены фактами мага, явным дневным premise в replay и source-ordered `magic_counts`, только для Wizard sources, включая нули. Casting actions/spell casts/Miscasts/unsupported Miscasts разделены; effects не увеличивают action budget. UI активирует Reason/Willpower через Wizard tag, редактирует факты и показывает средние расходы. Автоматический NPC envelope учитывает Lightning Blast; ручные диапазоны сохраняются. Отдельная Magic JSON6 family M8 не менялась.

Последние адресные проверки (`PYTHONPATH=src`, `.venv/Scripts/python.exe -m unittest`), отдельными наборами:

- PC magic sources/plan/probability/native/interactions/statistics, общие K1 Casting/Miscast/spell/Recover, PC tactics/potions/heavy wounds/backup/shield, M8 callers и current source/generator/replay —292проверки,24.751s. Сразу прошли284;6ошибок были в тестовой подготовке без обязательного daylight,2—в sandbox cleanup временных папок Windows. После исправления подготовки `tests.unit.test_pc_magic_statistics -q` —6OK,0.643s; production-проверка daylight сохранена.
- Вне sandbox: `tests.integration.test_m8_npc_magic_scenario_runner.MagicRunnerIntegrationTests.test_public_runner_probe_from_external_cwd_matches_saved_output tests.integration.test_m8_casting_example tests.integration.test_dynamic_pc_magic.PcMagicProcessParityTests tests.integration.test_local_ui_browser -q` — первые3OK, browser выявил устаревшее синтетическое событие dropdown после появления Wizard. Исправлен тест: при вводе перед Enter отправляется настоящий input event; UI не ослаблен.
- Итоговый `tests.integration.test_local_ui_browser tests.integration.test_dynamic_encounter tests.integration.test_dynamic_encounter_json tests.integration.test_local_ui tests.integration.test_dynamic_potions.DynamicPotionTests tests.unit.test_dynamic_encounter_progress -q` —56OK,33.206s вне sandbox. Включает Wizard facts/card/JSON, прежние file/theme/layout/Run/Cancel paths, transport/progress и немагический генератор.
- `tests.unit.test_m9_pc_melee_simulation tests.unit.test_m9_pc_melee_json tests.unit.test_m9_pc_melee_json_schemas tests.unit.test_m14_pc_glorious_statistics tests.unit.test_m15_pc_help_statistics tests.unit.test_m17_pc_ally_recover_statistics tests.unit.test_pc_potion_statistics tests.unit.test_encounter_character tests.unit.test_encounter_inventory -q` —98OK,7.451s: существующие summary/action/resource budgets и current schemas/admission без магов.
- Публичная команда `-m towr generate-encounter docs/examples/dynamic/elemental-mage.request.json` исполнила4trials за2.841s и вернула1selected. Screening:7Casting/5spells в2боях; validation:6Casting/4spells в2боях. Все4боя завершены без Miscast; строки таблицы проверены отдельно literal RNG, а не этим seed. Это smoke-пример, не репрезентативная оценка баланса.

Ошибки адресных наборов устранены/перепроверены отдельно; единый повторный зелёный292-run не запускался. Full regression/wheel не выполнялись: выбраны затронутые подсистемы, сборка/dependencies/discovery прежние. Полный regression остаётся на контрольной точке нескольких функций/перед выпуском по AGENTS.md; новая схема в прежнем JSON discovery не требует wheel.

## Предыдущий срез: зелья в динамических боях

Пользователь подтвердил оба вида и пригодную руку без отдельного сброса. Healing Potion исполняет standard Recover и лечит одну собственную рану1–23 текущего боя со связанными эффектами/анатомией; допускается при Defenceless. Независимые Conditions и другие раны сохраняются, dropped items не подбираются одновременно. Enhancement Potion изменяет настоящие WS/Strength/Toughness/Agility и соответствующие dice/cap/Damage/Resilience до заката, не подменяется универсальным бонусным кубом. Каждый trial получает независимый конечный запас. [Принятое решение ADR-0119](decisions/ADR-0119-pc-potions-in-dynamic-encounters.md), [правила](rules/magic-items.md#зелья-в-динамическом-melee-генераторе).

Автоматический selector сравнивает применение с другими действиями, выбирает предмет/рану/здоровую руку; травмированная12вызывает настоящий Critical. Once-per-Characteristic — согласованная тактика экономии, не утверждение о stacking. Native proof связывает актуальный запас, руку, Recover slot и полные before/after; strict projection отвергает повторы/подмены. Завершается обязательная Critical end-phase даже при сохранении недоступного2H хвата после лечения другой раны. Исходные профили остаются неизменны.

Текущие PC JSON1/Dynamic JSON1/replay дополнены запасом и source-ordered `potion_use_counts`, включая нули; без запаса поле отсутствует. Общие stock/turn/action budgets проверяются вместе с Help/ally Recover. UI использует прежний редактор, показывает средний расход в статистике состава и блокирует ещё неисполняемые четыре Characteristics до MC. Без NPC-зелий, кормления союзника, старых кампанийных ран или заката внутри боя; source поддерживает только автоматический melee-срез. [Пример](examples/dynamic/potions.request.json), [запуск](examples/dynamic/README.md#применение-зелий).

Последние проверки (`PYTHONPATH=src`, `.venv/Scripts/python.exe -m unittest`), отдельными перекрывающимися наборами:

- Общий Recover/healing, native11–23, щит/руки, Help/Recover и M8 callers —258OK,14.020s до финальных source/end-phase уточнений; dynamic application/JSON/HTTP/files/progress —60OK,25.701s. Это адресные подсистемные наборы, не полный regression.
- После последних исправлений: `tests.unit.test_potion_models tests.unit.test_pc_potion_execution tests.unit.test_pc_potion_enhancement tests.unit.test_pc_potion_statistics tests.unit.test_pc_tactics tests.unit.test_k1_recover_resolution tests.unit.test_k1_recover_completion tests.unit.test_m53_shield_execution tests.unit.test_m53_shield_core tests.integration.test_dynamic_potions.DynamicPotionTests -q` —110OK,9.294s. Включены14native cases с loop11–23, источники Conditions, Critical/Defenceless, hand use, ID collisions и source forgery, все4enhancements и counts.
- `tests.integration.test_dynamic_potions tests.integration.test_local_ui_browser -q` —5OK,8.143s вне sandbox: dynamic/replay/current wire, actual sequential/process cost parity и прежние browser-сценарии. Последующее end-phase уточнение2H отдельно покрыто новым literal native-тестом; этот браузерный прогон не выдаётся за повторную проверку после него.
- Публичная команда `-m towr generate-encounter docs/examples/dynamic/potions.request.json` исполнила4trials; screening расходы Healing/Enhancement=2/2, validation=1/2 по двум боям каждого этапа. Это проверка запуска, не оценка точности баланса.

Full regression/wheel не запускались: вместо full выбраны затронутые Recover/healing/PC и генератор; package discovery/зависимости/доставка прежние.

## Предыдущий срез: автоматическая melee-тактика PC

Динамический генератор сам выбирает Attack и цель, стандартный Recover себе/союзнику или Help конкретному будущему Test. Фиксированные получатели/роли во входе партии не нужны. Выбор использует текущие Conditions, caps, навыки, оружие и ожидаемую пользу ближайшего действия; стабильные tie-break сохраняют воспроизводимость. Нет RNG или дополнительных Monte Carlo-прогонов внутри выбора. Сохраняются native proofs, ongoing источники, actual Fate/Lucky и отдельные счётчики действий. Причина/оценка доступны в Python `PcMeleeScenarioResult.tactical_decisions`. [Граница и решение ADR-0118](decisions/ADR-0118-automatic-pc-melee-tactics.md).

Первый автоматический режим — all-Close melee PCs против обычных Melee Minions. NPC пока атакуют по прежнему приоритету. Fate сохраняет Glorious при0начальных успехов/Near Miss≥11; оптимизация ресурса на весь бой, зелья и магия не добавлены. Это ограниченная эвристика, не оптимальный ИИ. Текущий PC JSON1/replay допускает `automatic_melee`, Dynamic JSON1/UI новых полей не требуют; явные прежние роли остаются отдельными поддержанными стратегиями.

Последняя адресная проверка (`PYTHONPATH=src`, `.venv/Scripts/python.exe -m unittest`):

- `tests.unit.test_pc_tactics tests.unit.test_encounter_character tests.unit.test_encounter_inventory tests.unit.test_m15_pc_help tests.unit.test_m16_pc_protection_help tests.unit.test_m17_pc_ally_recover tests.unit.test_m15_pc_help_statistics tests.unit.test_m17_pc_ally_recover_statistics tests.unit.test_m13_pc_near_miss tests.unit.test_m14_pc_glorious tests.unit.test_dynamic_encounter_progress tests.integration.test_dynamic_encounter tests.integration.test_dynamic_encounter_json tests.integration.test_local_ui -q` —158OK,29.204s. Включает14новых deterministic tactics checks, прежние Help/Recover/Fate, dynamic pipeline, JSON и HTTP.
- `tests.integration.test_automatic_melee_tactics tests.integration.test_local_ui_browser -q` —2OK,7.799s вне sandbox: current replay/summary и sequential/process parity плюс существующие browser import/export/draft/generation paths.
- Локальный микрозамер:100решений для2PC/3Minions —0.324s; два боя seed42/43, max2rounds, по20/25journal transitions —0.156s с прежней тактикой и0.215s с автоматической. Это малый замер накладных расходов, не прогноз полного поиска. Число trials не увеличивается; поведение может менять длительность реальных боёв.

Итого160различных адресных тестов. Full regression/wheel не запускались: kernel правил, сборка и доставка не менялись.

## Предыдущий срез: отдельные файлы персонажей

В каждой PC/NPC-карточке есть иконки загрузки и скачивания одного профиля; рядом с добавлением игрока — импорт нового. Файлы используют существующие Dynamic JSON1 fragments (`party_member` и элемент `candidate.npcs`), без новой family/версии. Stateless `POST /api/character` проверяет строгий JSON и schema/inventory invariants; без компиляции loadout, RNG и запуска симулятора. Сохраняются rich player drafts: предметы/положение, расходники, таланты, Fate. Неверный вид/повреждённый файл/коллизия actor ID не изменяют данные. [ADR-0117](decisions/ADR-0117-granular-character-files-and-npc-drafts.md), [пользовательский сценарий и примеры](examples/dynamic/README.md#отдельные-файлы-игроков-и-противников).

Пользователь выбрал замену NPC в отдельном browser draft состава. Исходные `lastResult`, статистика, replay и JSON не изменяются. Для draft оценки подписаны как неактуальные, рекомендация снята, скачивание исходного replay отключено; есть сброс состава/восстановление исходного профиля. Отдельный NPC скачивается из draft, полный отчёт — исходный. Новый Run/валидный полный отчёт очищают drafts; изменение партии их сохраняет. Прямой расчёт ручного draft не добавлен: генератор по-прежнему выполняет новый поиск. Epoch/target snapshot guards отвергают late file read/response после смены контекста; во время Run все профильные действия заблокированы.

Адресные проверки (`PYTHONPATH=src`, `.venv/Scripts/python.exe -m unittest`):

- `tests.unit.test_character_files tests.integration.test_local_ui -q` —19OK,6.908s:5новых unit,2новых HTTP и12прежних HTTP-сценариев. Strict JSON/type/range/duplicate invariants, roundtrip rich draft, stateless validation/origin boundary без execution.
- `tests.integration.test_local_ui_browser -q` —1OK,5.741s вне sandbox: PC/NPC export/import, rich inventory/Fate, add/replace/ID collisions, draft/original отчёт, replay block/reset, invalid/oversized/late file, новый Run; плюс прежние UI-сценарии. Для расширенного async сценария виртуальное окно Edge увеличено15→30s; это не дополнительный таймаут генерации.
- Оба публичных `*.character.json` прошли `parse_character_file`.

Итого20различных адресных тестов. Внешний вид иконок и draft notice просмотрен в Edge1400px. Игровой kernel, зависимости, discovery и прежние JSON families не менялись; full regression/wheel не запускались. Очередь развития общего генератора не изменялась.

## Предыдущий срез: карточки результата UI

Убраны общие сводки кандидатов/seed/финалистов. У каждого состава отдельный блок статистики (оценки, интервал, исходы), затем отдельные NPC-карточки без объединения одинаковых противников. Показаны все8характеристик и16навыков PG1.4 в раздельных секциях: сетки в запросе, две таблицы в результате. Пробная книжная группировка отменена пользователем; отсутствующие значения — прочерки, без числовых догадок. Порядок полей запроса и результата зафиксирован по книге, а не порядку JSON-ключей. Сокращения только официальные у характеристик; навыки отображаются полными оригиналами. Заголовок состава и кнопка скачивания выровнены с внешними границами следующих блоков; оружие/броня/расходники/таланты/Abilities в результате показаны тегами с hover-подсказками. Пока отсутствующие расходники/таланты — теги с прочерком. Редакторы инвентаря запроса не заменялись. Перенос состава в запрос полностью удалён; в составе оставлена доступная SVG-иконка скачивания replay прежнего стиля. Полный JSON и правила поиска не менялись.

В запросе тоже показаны все8характеристик и16навыков; отсутствующие пока возможности — disabled-плейсхолдеры с прочерками, без привязки к source JSON. Теги результата и талантов запроса имеют единые высоту26px/шрифт12px/скругление14px и используют общий собственный tooltip:120мс для hover, focus/Escape, удержание курсора на подсказке, ограничение viewport и очистка при перерисовке/переключении вида. Браузерный title у этих тегов удалён. Модуль `_local_ui_tooltip.py` не имеет игровых зависимостей.

В двухколоночной раскладке JSON запроса и результата начинаются на одной высоте; первые карточки игрока и статистики результата также совпадают по верхним границам. Карточки и JSON используют одну линию начала во всех смешанных сочетаниях; при переключении вида положение содержимого сохраняется. Заголовок первого состава с replay download перенесён в полосу пояснений над карточкой (в JSON-режиме невидим и inert, но сохраняет место в раскладке); остальные составы сохраняют собственные заголовки. Общие строки заголовков/подсказок учитывают перенос текста и stale notice. На узких экранах панели остаются в одной колонке.

В заголовок результата возвращены загрузка JSON и форматирование (только JSON-вид); размер/hover совпадают с прочими иконками. Импорт отчёта не меняет запрос/seed и не запускает поиск, отличается source — stale notice. Некорректные family/данные составов сохраняют прежний результат; сборка карточек до замены идёт вне DOM. Во время Run кнопки блокируются, version guard игнорирует позднее чтение файла после нового запуска. Форматирование меняет только whitespace.

Добавлена общая светлая/тёмная палитра, переключатель справа сверху, начальный выбор по системной теме и сохранение явного выбора в localStorage. Запрет storage не ломает переключение; тема не меняет source/seed/results. Новый `_local_ui_theme.py` поставляется обычным package discovery, дополнительных зависимостей нет.

Адресные проверки, `PYTHONPATH=src; .venv/Scripts/python.exe -m unittest`:

- `tests.integration.test_local_ui_browser -q` —1OK,5.046s вне sandbox: обе темы/контраст/хранение, единая линия содержимого во всех4сочетаниях карточек/JSON при переносах/stale notice/переключении видов и мобильной колонке, возврат раздельных24полей в книжном порядке, единые размеры тегов, импорт/форматирование результата (валидный/ошибочный/чужой source/late file), disabled-плейсхолдеры без изменения JSON, внешнее выравнивание, быстрые custom tooltip (hover/focus/Escape/viewport/очистка), прежние Run/Cancel/export/reproducibility paths.
- `tests.integration.test_local_ui -q` —12OK,6.256s: HTTP-доставка UI и существующий generation/cancel/progress transport. Это результат предыдущего UI-шага; после локальной правки карточек/tooltip transport не менялся и повторно не прогонялся.

Итого13адресных тестов; не full regression, wheel не собирался. Внешний вид тёмной темы ранее просмотрен в Edge1400px; возврат раздельных полей и file controls проверен браузерным сценарием.

## Предыдущий срез: живой прогресс генерации

Во время Run отдельный компактный блок показывает создание состава, preliminary simulation, завершённые trials/победы и независимую проверку финалистов. Current+last assessment без полного лога; обновление через GET /api/progress примерно раз в секунду. App frozen progress получает реальные completed trial callbacks; source/seed/results прежние, observer не расходует RNG. [ADR-0116](decisions/ADR-0116-dynamic-generation-live-progress.md), [пользовательское описание](examples/dynamic/README.md#прогресс-генерации).

Отмена/завершение прекращают polling; token/sequence guards отсекают late responses. Сбой GET не прерывает generation POST. После success предварительная оценка заменяется actual selected validation из финального отчёта; если рекомендаций нет, процент не показывается. Cancel/error очищают per-candidate estimates. При конечном малом пространстве фактический объём может быть меньше budget: результат/счётчики не дорисовывают неисполненные trials. Новый public wire format/версии/dependencies не вводились.

Убрана обычная строка статуса под кнопкой Run/Cancel и её секундный таймер; ход генерации остаётся в отдельном блоке. Ошибки ввода и запроса по-прежнему видны. После правки `tests.integration.test_local_ui_browser -q` —1OK,5.974s вне sandbox.

Последняя проверка, `PYTHONPATH=src`, `.venv/Scripts/python.exe -m unittest`:

- `tests.unit.test_dynamic_encounter_progress tests.integration.test_dynamic_encounter tests.integration.test_dynamic_encounter_json tests.integration.test_local_ui tests.unit.test_m9_pc_melee_simulation -q` —57OK,23.030s.
- `tests.integration.test_local_ui_browser -q` —1OK,4.580s вне sandbox: реальные UI paths + контролируемые live snapshots, cancel/restart/late/error и final-assessment fallback.

Итого58различных адресных тестов, включая8новых unit и2HTTP progress cases. Предварительный browser прогон прошёл; после read-only review исправлена stale partial assessment при завершении между polls, browser повторён выше. Это не full regression; wheel не собирался. Новые Python-модули поставляются прежним package discovery, entry points/ресурсный механизм не менялись.

## Предыдущий срез: инвентарь и теги талантов

Equipment теперь состоит из weapons/armour списков с отдельными instance IDs и начальным положением: руки, обе руки, надето или carried. Можно описать два одинаковых меча в руках и глефу за спиной; body armour, обычный шлем и щит задаются независимо. Consumables — отдельная группа с типом/количеством и Characteristic для Enhancement Potion. Таланты редактируются add/remove tags, Lucky остаётся исполнимым. Карточки/JSON/файловые действия сохраняют введённые данные. [Текущий контракт и границы](decisions/ADR-0115-inventory-draft-and-talent-tags.md), [пример входа](examples/dynamic/README.md#данные-персонажей).

Описание инвентаря отделено от execution admission. Dual wield, произвольные spare loadouts, Heavy Armour, carry Burdened, potion consumption и неизвестные таланты не упрощаются: parser блокирует расчёт до trials с явным path/reason. Их можно описывать и сохранять, но это не обещание исполнения. Работают один active melee weapon, light armour/обычный шлем/optional shield и прежний2H→один carried1H backup. Обычному шлему не добавлен отдельный бонус; magical helmet не маскируется этим kind.

Последнее дополнение к UI: select использует свой chevron с отступом12px и padding-right36px; native select/keyboard сохранены, для forced colors возвращается системный вид. Числовые поля характеристик (Characteristics) и навыков (Skills) заполняют ширину своих колонок, значения выровнены слева; на desktop четыре поля в строке. Фиксированные80px убраны по уточнению пользователя. Поле характеристики (Characteristic) у зелья усиления (Enhancement Potion) занимает ту же колонку, что и выбор предмета. Для названий добавлены сокращённые английские обозначения характеристик (WS,BS,S,T,I,Ag,Re,Fel) и текущих навыков (Mel,Def,Ath,End), с полными оригиналами в tooltip/aria-label: четыре используемых характеристики/навыка, восемь potion choices, оружие (Weapons), броня (Armour), зелья и известные таланты (Talents); неизменённые wire IDs и пользовательские имена сохраняются. Конвенция «Русский (Original English)», включая устоявшиеся сокращения, закреплена в AGENTS.md.

Внешняя визуальная группа «Партия игроков» удалена: отдельные .player-card отображаются непосредственно в запросе, кнопка «Добавить» создаёт игрока, удаление работает на его карточке. Внутренний party/source контракт не менялся. Компактная кнопка88×36 получила белый фон и тонкую серую рамку (#ccd4df), сохраняя нейтральный вид. Характеристики (Characteristics) используют книжные сокращения PG14; Mel/Def/Ath/End обозначены в AGENTS.md как локальные UI-сокращения навыков (Skills), не как официальные сокращения книги.

Последняя правка оформления: удаление имеет тот же нейтральный белый фон/серую рамку, что добавление; крестик и размеры36/24px сохранены. Для ранних file/view/Run/Cancel кнопок добавлены hover/active styles, включая отдельные состояния выбранных вкладок и disabled guard. Сетка характеристик (Characteristics)/навыков (Skills) адаптирует число колонок по доступной ширине; подписи12px умещаются в одну строку, резерв пустых трёх строк убран. На1400px остаются четыре поля в строке, на узкой карточке сетка перестраивается, не обрезая имён.

Последнее уточнение: высота «Добавить» теперь36px, как у inputs; ранние file/view actions получают синий hover/active, новый add/remove стиль остаётся нейтральным. Root scrollbar gutter зарезервирован постоянно, поэтому Cards↔JSON не меняет горизонтальные координаты main/panels. Talent tags получили14px сверху/16px снизу, entry — дополнительный нижний отступ; пустой tag list скрыт. Все JSON exports (request/result/replay) теперь используют общий downloadFileName: UTC ISO timestamp с milliseconds + короткий UUID, без изменения source/seed.

Последнее уточнение: нейтральные add/remove buttons получают соответственно мягкий зелёный/красный hover и active; базовые цвета/размеры не менялись. У automatic search plan checkbox нижний отступ14px до поля кандидатов; у automatic NPC ranges checkbox отступы14px сверху/снизу. Группа «Возможные параметры противников» сохранена как единый раздел ручных ограничений компонентов; дополнительные группы не создавались без самостоятельной функции.

Текущая адресная проверка: `PYTHONPATH=src; .venv/Scripts/python.exe -m unittest tests.integration.test_local_ui_browser -q` —1OK,4.883s вне sandbox, viewport1400×1100. Проверены green/red hover с contrast≥4.5, реальные checkbox spacing по BoundingClientRect, add height36, blue hover file/view actions, стабильные horizontal coordinates при Cards/JSON, tag spacing, четыре уникальных dated exports через реальные handlers без изменения source, нейтральные add/remove styles, hover cascade через эквивалентный forced-state class для file/view/Run/Cancel/disabled, однострочные подписи с реальными Range bounds на широком экране и карточке260px, компактные add actions88×36 без SVG/длинной подписи, contextual aria-label/tooltip, нейтральные цвета с читаемым контрастом, все короткие подписи/полные tooltips, рамки кнопок, отсутствие внешней группы, добавление/удаление игрока с unique ID без изменения остальных, заполнение полями колонок, выравнивание четырёх значений в строке, реальные grid coordinates/chevron inset, оригинальные названия/tooltip и прежние tag/JSON/generation/cancel/seed сценарии. Игровые тесты и wheel повторно не запускались.

Сохранённое оформление UI: remove actions теперь с крестиком. Стандартные удаления36×36; исключение внутри talent tag —24×24 и SVG12px, чтобы тег оставался компактным. Add buttons для персонажа/оружия/защиты/расходников теперь компактные88×36, нейтральные, только «Добавить» без плюса; удаления оформлены в том же нейтральном стиле; проверка читаемости≥4.5 сохраняется. Standalone «Добавить талант» удалена: клик в dropdown сразу создаёт тег; Arrow/Enter/Escape и ввод собственного тега через предложение списка сохранены. Enter по partial query выбирает предложенный talent, не создаёт неполный тег.

Расходники упрощены до плоского списка с лёгкими разделителями: верхняя строка предмет/количество/крестик, ниже только Characteristic + краткое «+1 до заката» либо короткое описание лечения. Вложенные рамки, h5 «Эффект одного применения» и повторяющееся пояснение количества удалены. JSON/исполнение не менялись.

Адресная команда `PYTHONPATH=src; .venv/Scripts/python.exe -m unittest tests.integration.test_local_ui_browser -q` —1OK,4.601s вне sandbox: крестики/размеры с исключением для tags, мягкие цвета с contrast check, отсутствие отдельной talent add button, click/keyboard/custom/partial/duplicate tags, плоские разнородные consumables, JSON roundtrip и прежние edit/Run/Cancel/seed. Внешний вид дополнительно просмотрен в Edge900px на preview реального DOM. Игровые tests/wheel ради UI не запускались. Прежние источники визуальных принципов: [GOV.UK Buttons](https://design-system.service.gov.uk/components/button/), [WCAG Contrast](https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html), [Use of Color](https://www.w3.org/WAI/WCAG21/Understanding/use-of-color.html).

Предыдущая проверка inventory-среза, с `PYTHONPATH=src` и `.venv/Scripts/python.exe -m unittest`:

- `tests.unit.test_encounter_inventory tests.unit.test_encounter_character tests.integration.test_dynamic_encounter_json tests.integration.test_local_ui -q` —39OK,17.695s.
- `tests.unit.test_m20_pc_backup_weapon_admission tests.unit.test_m20_pc_backup_weapon tests.unit.test_m53_shield_core -q` —33OK,3.556s.
- `tests.integration.test_local_ui_browser -q` —1OK,4.791s вне sandbox: отдельные предметы/начальные позиции, potions, tags, duplicate/removal, JSON roundtrip и прежние Run/Cancel/fixed seed.

Итого73различных адресных теста. Полный regression/wheel не запускались; новых dependencies/entry points/resource inclusion нет. Ранее успешный30-test запуск повторён и расширен до39, отдельно не прибавляется к итогу. Ссылки изменённых документов и whitespace diff проверены.

## Предыдущий срез: данные партии и автоматический вход

Dynamic JSON1 теперь принимает actor_id/characteristics/skills/equipment/talents/resources вместо внутренних PcMeleeParticipant policies и Fate ledgers. В карточках раздельные характеристики/навыки,13melee weapons, none/light armour, щит и Lucky; есть добавление/удаление персонажей. Application выводит хват/бонусы/щит и реальные Fate Test/Wound decisions. Lucky разрешён независимо от PC weapon; проверяются фактический free-first spend, последующий paid spend и статистические bounds. [ADR-0114](decisions/ADR-0114-character-facts-and-automatic-generator-input.md), [текущий пользовательский вход](examples/dynamic/README.md#данные-персонажей).

Search_space можно не передавать: сервер строит bounded диапазоны по партии, цель боя оценивается прежними Monte Carlo/ranking. Результат сохраняет resolved_search_space и полные replay. Ручные ограничения остаются необязательным раскрываемым блоком. Старый participant-формат dynamic family удалён без compatibility-ветки; остальные low-level families сохраняют формат с расширенным Lucky admission.

Ограничения: сцена явно healthy/fresh-session, полный Fate/Lucky, Close/no ambush/open terrain. Heavy armour/неизвестные таланты/зелья/spellcasting не игнорируются, а отклоняются до trials. Автовыбор пока ограничен Attack/self Recover по состоянию, Glorious при0начальных успехов и Near Miss при ране≥11 с реальным ресурсом. Это не общий тактический ИИ. Настройка середины сессии, действия Help/расходников/магии и их общий выбор требуют следующего среза. Generated NPC по-прежнему используют Staff/Dagger/light armour, не весь книжный каталог.

Последние проверки: character/Fate/source/schema/Glorious/Hochland —75tests OK; dynamic search/JSON/HTTP —36tests OK; отдельно browser —1test OK вне sandbox. После добавления actual automatic-envelope→equipment→replay проверки JSON-модуль повторён:14tests OK. Финальный cached-character readmission проверен6unit+1automatic replay tests —7OK. Всего113различных адресных тестов; повторные прогоны не суммируются как новые. Это не full regression; wheel не собирался, установка/resources discovery не менялись.

Команды с `PYTHONPATH=src` (исполнитель `.venv/Scripts/python.exe -m unittest`, флаг `-q`):

- `tests.unit.test_encounter_character tests.unit.test_m9_pc_melee_models tests.unit.test_m9_pc_melee_json_schemas tests.unit.test_m14_pc_glorious tests.unit.test_m14_pc_glorious_statistics tests.integration.test_m70_pc_hochland_source tests.integration.test_m70_pc_hochland_json` —75OK.
- `tests.integration.test_dynamic_encounter tests.integration.test_dynamic_encounter_json tests.integration.test_local_ui` —36OK; затем отдельно `tests.integration.test_dynamic_encounter_json` —14OK с новым automatic replay case.
- `tests.integration.test_local_ui_browser` —1OK вне sandbox.
- Финальное readmission уточнение: `tests.unit.test_encounter_character tests.integration.test_dynamic_encounter_json.DynamicEncounterJsonTests.test_automatic_space_executes_with_compiled_equipment_and_replay` —7OK.

## Сохранённое поведение UI: файловые действия, отмена и seed

Иконки файловых действий и кнопки переключения вида выровнены по высоте32px. В панели запроса доступны SVG-иконки загрузки/скачивания/форматирования (format только в JSON). По последнему уточнению у результата оставлено только скачивание; result upload/formatter, их JS handlers и /api/validate-result удалены. Переключение карточки/JSON сохранено, сверху только Run/Cancel.

Последняя адресная проверка: `PYTHONPATH=src; python -m unittest tests.integration.test_local_ui -q` —10pass; отдельно `python -m unittest tests.integration.test_local_ui_browser -q` —1pass вне sandbox. Проверены отсутствие удалённых контролов, загрузка запроса, скачивание/просмотр результата и прежние cancel/edit/seed сценарии. Это11тестов; full/wheel не запускались.

Оформление формы: цели переставлены в порядок целевая длительность→лимит раундов→процент победы, свёрнутая строка тоже начинает с раундов. Верхние три группы растянуты до одинаковой высоты; строки подписей/inputs/пояснений выровнены (координаты и высоты проверены в Edge на1200и1400px, отклонение<1px), для промежуточной desktop ширины зарезервированы две строки подписи. Seed вынесен из «Поиск и точность» в компактную «Воспроизводимость»; четыре поля автоплана сгруппированы отдельно. В верхней строке стоят «Состав противников», «Цели боя» и «Воспроизводимость»; «Поиск и точность» ниже на всю ширину. На узком экране блоки идут друг под другом. Две дополнительные поясняющие фразы про ограничения плана/времени убраны по запросу пользователя. При ширине от1200pxчетыре поля поиска стоят в один ряд; ниже — в два столбца (на телефоне в один). Проверены HTML-порядок/ID и внешний вид в headless Edge; поведение генерации и связь данных не менялись, игровые тесты ради вёрстки не запускались.

2026-11-15 выполнено новое уточнение: checkbox fresh seed и автоматическая смена master_seed удалены. Значение seed редактируется явно; повторный Run того же запроса даёт тот же полный отчёт. Автоплан и computed budget сохранены.

Кнопка «Отменить генерацию» останавливает работу на сервере кооперативно, а не только browser fetch. UI transport token/UUID отличен от seed; Event относится к конкретному запуску, stale cancel не затрагивает следующий, early cancel учитывается bounded table128. Application cancel_requested checkpoint проверяется у кандидатов/возврата и перед бросками default RNG. Отмена не выдаёт partial report, слот освобождается в finally, UI ждёт confirmation и разрешает новый запуск. JSON1/CLI/kernel прежние. [Поведение](examples/dynamic/README.md#отмена-генерации).

Проверки: `PYTHONPATH=src; python -m unittest tests.integration.test_local_ui tests.integration.test_dynamic_encounter tests.integration.test_dynamic_encounter_json -q` —32pass. Отдельно `python -m unittest tests.integration.test_local_ui_browser -q` —1pass вне sandbox. Покрыты реальные остановленные броски, early/stale cancel, release/restart, неизменность RNG/result без отмены, structured errors, UI cancel state и fixed-seed повтор. Это33адресных теста; full/wheel/длинный800-trial прогон не запускались.

## Предыдущая проверка UI: автоплан и fresh seed

2026-11-15 выполнено уточнение пользователя: auto search по составу/целям, manual override параметров точности, бюджет только текстом и автоматически в JSON, fresh seed на каждый explicit Run. `_local_ui_planning` оценивает разнообразие пространства и workload, распределяя ограниченную ёмкость между screening и независимым validation. Для ui.request исходно получается24×12 +2×256=800; другие составы/цели меняют план. Эвристика не гарантирует точность/покрытие/время. Ручной режим сохраняет четыре параметра, но вычисляет бюджет; --request/file picker выбирают manual search. New seed mode независим, выключается для повтора. Actual uint64 сохраняется строкой в source/report; UI modes не меняют JSON family.

Правки/сворачивание/переключение не запускают расчёт и не меняют seed; JSON preview не сбивает курсор, derived числа записываются при blur/save/Run. Подробности — [UI документация](examples/dynamic/README.md#автоплан-и-рабочие-значения-ui). CLI/Python явные запросы не получают автоматически новый seed/план.

Проверки: `PYTHONPATH=src; python -m unittest tests.integration.test_local_ui -q` —7pass. Отдельно `python -m unittest tests.integration.test_local_ui_browser -q` —1pass вне sandbox. Browser покрывает auto/manual, реакцию на цели/workload, finite-space cap, computed budget без поля, fixed/new uint64 seeds, no RNG on editing, full-report repeat, а также прежние card/JSON/stale/run сценарии. RNG в тесте подменён детерминированно. Это8адресных проверок; full/wheel/полный800-trial прогон не запускались.

## Предыдущая проверка UI: сворачивание и defaults

2026-11-15 по запросу пользователя «Параметры поиска» сделаны expandable и изначально закрыты; summary показывает диапазон NPC/цели/бюджет, сворачивание не меняет запрос. Стандартный UI-файл теперь [ui.request.json](examples/dynamic/ui.request.json):1–10NPC, win target50%, duration5, round cap15. Пользователь выбрал допустимое ожидание10–15минут; стартовый профиль24×12 +2×256 =800trials, seed42. Существующий search.request.json сохранён как быстрый12-trial CLI/test пример; --request и загрузка файлов не переопределяются defaults.

Числа — оценочный компромисс:256validation trials дают Wilson95≈43,9–56,1% при observed50%;24candidates не гарантируют полноту поиска, screening12 остаётся грубым. Короткий замер12боёв (1/5/10NPC по4, fixed Staff3/4, cap15) дал0,027/1,081/2,266с за бой. Полный800-trial профиль не запускался; ожидание10–15мин не жёсткая граница времени. [Обоснование](examples/dynamic/README.md#рабочие-значения-ui).

Проверки: `PYTHONPATH=src; python -m unittest tests.integration.test_local_ui -q` —7pass, включая default profile admission без MC и сохранение явно выбранного файла. Отдельно `python -m unittest tests.integration.test_local_ui_browser -q` —1pass в headless Edge: начальное collapse, expand/collapse без изменения запроса и прежние edit/run/stale сценарии. Это8адресных проверок; benchmark12trials отдельно, full/wheel не запускались.

## Предыдущая проверка UI: карточки запроса и результата

2026-11-15 добавлены переключатели «Карточки / JSON» с сохранением данных. В запросе редактируются PC stats/skills/weapon/grip, NPC search-space choices, Судьба/тактика и дополнительные поля. Результат показывает найденные составы, validation/screening оценки, интервалы и replay download; исходный отчёт не изменяется. Первоначальный перенос NPC значений в пространство поиска удалён2026-11-16 по запросу пользователя. По уточнению пользователя расчёт идёт только по кнопке генератора: при правке запроса последний результат остаётся на экране с stale-уведомлением; JSON не теряется при ошибке/переключении. JSON family, engine и API прежние.

Проверки: `PYTHONPATH=src; python -m unittest tests.integration.test_local_ui -q` —6pass; отдельно `python -m unittest tests.integration.test_local_ui_browser -q` —1pass в headless Edge вне sandbox. Browser case проверяет PC/space editing, hidden-field preservation, tabs, seed precision, malformed edits, actual run, stale/no automatic fetch, transfer и повторный запуск. При первом прогоне исправлен общий setter: он теперь поддерживает путь через массив партии. Карточки запроса и рассчитанного результата визуально проверены. Это7адресных проверок, full/wheel не запускались. Новые зависимости/ресурсы не добавлены.

## Предыдущая проверка минимального UI

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

Расширить составляемые NPC в динамическом пути: выбрать небольшой совместимый набор общего снаряжения/талантов, описать prerequisites и вывести Attack/Protection/Damage/Resilience из компонентов без canonical-ID dispatch. Начать с контрактной сверки существующих weapon/shield consumers и предложить конкретный набор, затем реализовать его сквозным чанком. Каталог именных statblocks не является следующим этапом.

На реальных партиях с магами отслеживать долю и причины unsupported. Покрытие оставшихся Miscasts расширять по значимым остановкам; не объявлять частичный набор полным ядром магии или ослаблять exclusion ради рекомендаций. Новая функция/смена публичной границы согласуется по AGENTS.md; для завершённого ADR-0120 дополнительных решений нет.

Commit/push выполняет пользователь.
