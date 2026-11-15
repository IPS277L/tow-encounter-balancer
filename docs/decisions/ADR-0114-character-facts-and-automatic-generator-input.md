# ADR-0114: данные персонажа на входе генератора

Дата: 2026-11-15. Статус: принято и реализовано в первом ограниченном срезе по запросу пользователя.

Текущая структура equipment/consumables и тегов уточнена в [ADR-0115](ADR-0115-inventory-draft-and-talent-tags.md): описание полного инвентаря отделено от допуска к расчёту. Ниже сохранена исходная граница первого среза.

## Проблема и решение

UI показывал внутренний `PcMeleeParticipant`: ledger Судьбы, nullable policies и ручные диапазоны NPC. Это требовало от пользователя собирать настройки исполнителя вместо описания партии. В текущем dynamic JSON1 партия теперь содержит `actor_id`, `characteristics`, `skills`, `equipment`, `talents`, `resources`. Старый participant-вход этой family удалён без compatibility-ветки. Другие families сохраняют свои низкоуровневые форматы; их Lucky admission расширен независимо от оружия.

`application.encounter_character.EncounterCharacter` отделяет факты от состояния боя и собирает существующий typed participant. UI/JSON не вычисляют игровые бонусы. Поддержаны четыре характеристики, четыре навыка, прежние13 melee weapons с их Traits, none/light armour, щит для допустимых1H и Lucky. Оружие определяет хват; щит занимает противоположную руку. Light Armour даёт+1 Resilience, щит добавляет ещё+1 через actual held state, сохраняет Defence против Shooting и прежние drop/Recover/hand-conflict последствия. Heavy Armour отклоняется: его −1d Agility/Burdened пока нельзя заменить числовым+2.

Нормативные источники прежние: PG1.4 IV Equipment93,97–98; III Talents/Lucky78; V Rules/Fate111–112. Снято историческое ограничение Lucky только Hochland: kernel funding и статистические bounds уже учитывают один бесплатный spend. Gambling отсутствует в боевой сцене; бесплатный spend не является бесплатным Near Miss burn.

## Состояние, решения и честная граница

`scene` явно задаёт Close, отсутствие засады, открытую местность и `session_start: fresh`. Персонажи начинают здоровыми, Fate pool равен введённому rating, Lucky не использован. Середина сессии не представляется этим входом. Каждый trial получает независимое состояние. Пользователь не вводит session IDs, spend/burn histories, target bindings или tactics.

Первый автоматический controller использует существующий выбор Attack/self Recover по фактическому состоянию, weapon-first и восстановление щита. Glorious выбирается после собственного initial roll при0успехов, наличии полезного изменения Test и доступного Fate; Near Miss — при actual Wounds Table total≥11 и наличии permanent rating, без резервирования. Выбор расходует текущий ресурс и сохраняет proofs; остальные optional Fate actions не выбираются. Пороги — явная эвристика симулятора, не правило книги и не оптимальная тактика. Эта функция убирает ручной ввод внутренних policies, но ещё не решает общий выбор Help/магии/расходников или планирование действий на несколько ходов. Конкретные policies сохраняются в executable replay для воспроизведения.

Ввод неизвестных талантов, spells, consumables, heavy armour, Short/ambush/terrain modifiers отклоняется до trials. Декоративных полей с игнорируемым влиянием нет. Магический M8 остаётся отдельным сценарием.

## Автоматическое пространство NPC

`search_space` необязателен; отсутствие или null включает серверный `automatic_npc_search_space`. Для каждого из WS/S/T/Agility/Melee/Athletics берётся диапазон от минимального значения партии−1 до максимального+1. Эвристические границы поиска: характеристики1–10, NPC навыки2–6. Это пределы автоматического поиска, не новые книжные ограничения персонажей. Staff/Dagger и none/light armour остаются доступными; authored Drained автоматически не добавляется. Цели побед/длительности ранжируют симулированные составы, а не преобразуются в недоказанный множитель характеристик.

Полный explicit search_space остаётся необязательным ограничением эксперта. UI прячет его в отдельном раскрываемом блоке и позволяет вернуться к автоматическому режиму. Client planning использует предварительную оценку envelope; только сервер допускает и строит исполняемое пространство. Результат дополнен `resolved_search_space`, поэтому фактические диапазоны сохраняются и при автоматическом входе. Оптимум за пределами исследованного envelope не обещается.

## Проверка

Адресно: character compilation/strict types/hand conflict, actual shield protection/Resilience, literal Glorious dice с Lucky при rating0 и последующий paid spend, статистические bounds; parser/schema/echo/replay/CLI и automatic/explicit search space; прежние Fate/Glorious/Hochland tests и актуализация устаревших Lucky-only guards; HTTP/cancel/seed и реальный browser edit/JSON/generation. Полный regression и wheel для этого среза не требуются. Фактические результаты — в project-status.
