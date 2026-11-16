# ADR-0123: боевые таланты PC и сохранение намерения перед проверкой

Дата: 2026-11-16. Статус: принято пользователем; полный срез с Melee Help и Character Creation provenance реализован.

## Источники и действующие решения

Player’s Guide1.4, гл.III Talents73/Defensive Stance74/Wild Attack81; гл.V Fate111, Attack Tests118/Failed Attacks119, Conditions122–123; Appendix Wounds Table190. Адресно перечитаны требования и бесплатное получение при Character Creation, два эффекта, запрет повторного Glorious/Fate reroll, ongoing Conditions и раны12–15. Это не новое чтение всей книги.

По [ADR-0122](ADR-0122-generated-npc-combat-talents.md) NPC уже используют оба таланта. Выбранная пользователем трактовка Defensive Stance сохраняется для всех участников: обмен допустим только при действительно доступном новом Staggered атакующему. Уже Staggered атакующий,0v0 и Athletics не дают обмена; повторного вопроса по этому правилу не требуется.

## Принятый полный срез

Добавить Оборонительную стойку (Defensive Stance) и Дикую атаку (Wild Attack) к фактам PC в нынешнем automatic all-Close melee против Minions. Существующие оружие/щит, руки, раны, Help/Recover, зелья, магия и Fate продолжают исполняться. Новый ranged/Short/Brute-срез этими талантами не объявляется; прочие прежние сцены без новых талантов сохраняются.

Wild Attack рассматривается и для собственной Melee Attack, и для собственного Melee Help. Defence/Athletics Help, Casting и прочие Skills его не получают. Это соответствует тексту «next Melee Test», а не искусственному weapon-hit бонусу. В нынешнем динамическом срезе нет incoming Shooting/Melee Protection; такой дополнительный контекст не отключается молча, но не включён в новый public admission.

Defensive Stance применяется после настоящей успешной Defence против Melee: при собственном снимаемом Staggered PC предпочитает обмен по ADR-0122. Это реакция без нового Test/action/Fate. Если атакующий уже Staggered от собственного Wild Attack, обмен недоступен — тот же выбор применяется обеим сторонам.

## Приобретение и Requirements

При обычном приобретении проверяются WS≥3 для Defensive Stance и S≥4 для Wild Attack. Проверяются базовые исходные характеристики, не временный Enhancement в бою. Оба таланта однократные, дополнительных ranks нет.

PG73 явно разрешает игнорировать Requirements у бесплатно полученного при Character Creation таланта. Для PC поддерживается этот факт сразу, не симулируя создание/XP progression. Существующий `party[].talents` остаётся списком тегов. Новый необязательный `party[].talent_acquisition` задаёт provenance только для выбранных боевых талантов:

```json
"talents": ["wild_attack", "defensive_stance"],
"talent_acquisition": {"wild_attack": "creation_free"}
```

Отсутствие записи означает обычное приобретение с проверкой Requirements; явное `earned` эквивалентно ему. `creation_free` — факт персонажа, не тактическая настройка и не автоматический способ исправить невалидный источник. Запись для отсутствующего/неподдержанного таланта, дубликат или неверный тип отклоняются. Для Lucky/Wizard и других талантов этот срез не вводит новую систему provenance.

UI сохраняет привычные теги. Для этих двух талантов доступна компактная отметка «Бесплатно при создании (Character Creation)»; без неё Requirements проверяются. Изменение характеристики не удаляет талант и не включает waiver автоматически. Некорректный draft можно сохранить по прежним правилам, но расчёт блокируется до MC. Native current PC JSON1 хранит полный typed combat-talent source с методом приобретения; current replay его воспроизводит. Никаких compatibility-ветвей/новой wire version.

Генерация NPC по ADR-0122 продолжает соблюдать Requirements без Character Creation waiver: её принятый scope этим не меняется. Magic Resistance у PC пока не подключается: NPC spellcasting не добавляется в нынешний путь.

## Автоматический выбор Wild Attack

Advisor сравнивает обычные и Wild Attack варианты Attack/Melee Help по ожидаемому прогрессу/пользе помощи, с неотрицательным штрафом за прирост ожидаемого входящего давления после получения Staggered. Использует реальные Conditions, weapon modifiers/cap и текущий ресурс/пороги Fate. При равенстве выбирает вариант без добровольной цены. Это ограниченная эвристика по текущему состоянию, не поиск оптимальной стратегии всего боя.

Нормальный вариант учитывает действующую post-initial-roll Glorious policy и доступность ресурса, включая Lucky free spend. Реальный расход Fate по-прежнему возможен только в actual окне броска; оценка не списывает его и не читает будущие значения. У варианта Wild Attack не тратится дополнительный Fate на Glorious поверх таланта. Grim/Glorious отменяют друг друга по книге; повторных rerolls или stacking качества не создаётся. Эта политика не расширяет допустимые Fate решения общего ядра.

При Drained или уже Staggered Wild Attack не выбирается. Passive Defensive Stance при Drained сохраняется, если само состояние действительно снимаемо. Запрет снятия ongoing Condition из PG122 применяется независимо от источника способности.

## Сохранение намерения и порядок

До цены фиксируются выбранные действие, цель, конкретный Help recipient/policy и intended Melee Test. После получения Staggered advisor не может заменить уже выбранный вариант Recover/Casting, другой целью или другим получателем Help. Цена меняет настоящие Conditions до подготовки Test, поэтому Sword/Morning Star и остальные правила видят обновлённый snapshot. Она не является отдельным action, Test или использованием руки.

Native proof сохраняет source-bound committed intent и цену; актуальный журнал обязан провести именно следующий обещанный Melee Test с однократным Glorious, затем погасить entitlement. Source mismatch, повтор, пропуск цены/потребления и terminal outcome с незавершённой работой отвергаются. NPC используют тот же общий lifecycle; отдельный дублирующий rules engine для PC не вводится.

Раны12/14/15 продолжают давать реальные Critical/Drained/hand последствия на фактическом использовании руки/действии. Цена/реакция сами по себе не добавляют ещё одно действие либо дополнительный Critical Test. Рана15 даёт ongoing Staggered до исцеления: Defensive Stance не может снять его, Wild Attack при нём недоступен. Healing Potion может устранить действительную причину через прежний owner; неподдержанная анатомия не обходится талантом. Подбор оружия/щит/Recover сохраняют обязательный порядок.

## Альтернатива меньшего объёма

Только Attack-активация Wild Attack и Defensive Stance, со строгими Requirements без Character Creation provenance. Отказ от Wild при Help был бы явно ограниченной тактикой, а не запретом книги; легальные creation-free персонажи с невыполненным порогом оставались бы unsupported. Полный вариант включает Melee Help, provenance и сохранение намерения сразу.

## Адресный план проверки

- PC facts/tag/provenance: WS2/3, S3/4, free Character Creation, ordinary acquisition, дубликаты/лишняя metadata/типы, requirements не подменяются зельем; native/current JSON1/character-file roundtrip и до-MC отказ.
- Literal Wild Attack: Attack/Melee Help, реальные price/hand/weapon/Glorious/Fate windows, Drained, Grim, Lucky/reserve; не платится лишний Fate и нет повторного reroll. Defence/Athletics Help и Casting не получают эффекта.
- Committed action/target/help сохраняются после цены; чужой actor/Test, повтор, пропущенные переходы и неверный terminal result отклоняются. NPC-путь и его доказанные сценарии сохраняются.
- Literal Defensive Stance в обе стороны, выбранная трактовка already-Staggered,0v0/не-Defence/own fresh, Wound15 ongoing и лечение, injured hand12/Critical14–15/end-phase без лишних действий/тестов.
- Advisor/native по тем же фактам, normal versus Wild и Fate-aware сравнение; реальная dynamic generation/replay/агрегаты/один process parity и UI tags/provenance/прежние пути. Проверки адресные, full/wheel только при основании по AGENTS.md.

## Реализация и результат

Полный вариант принят пользователем. Typed acquisition facts, общий price/reaction owner, committed Attack/Melee Help, конечные Fate-aware распределения, current JSON1/replay/files/UI и публичный пример реализованы. Адресные игровые/транспортные проверки выполнены; [точные результаты и ограничения](../project-status.md#текущий-срез-боевые-таланты-персонажей-игроков). Full regression/wheel не требовались по действующей политике.
