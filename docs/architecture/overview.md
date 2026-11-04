# Архитектура

Этот обзор описывает актуальные слои и инварианты. Подробная [хронология](overview-history.md) и [ADR](../decisions/) читаются только для соответствующего решения. Текущий функциональный scope и следующий шаг — в [статусе](../project-status.md).

## Направление зависимостей

```text
CLI / JSON / future GUI
          |
          v
 application services
          |
          +---------> balance
          |              |
          v              v
       engine <----- simulation
          |
          v
        rules
          |
          v
        domain
```

Внутренние слои не импортируют CLI/JSON/GUI или балансировщик. Application связывает вход, generation, simulation и агрегированный результат; адаптеры только отображают внешний формат и ошибки.

## Карта кода

| Слой | Ответственность |
|---|---|
| [domain](../../src/towr/domain/) | Типизированные definitions, состояния, requests/results, проверка источников и инвариантов |
| [rules](../../src/towr/rules/) | Одно детерминированное разрешение правила с внедрённым RNG |
| [engine](../../src/towr/engine/) | Применение действий и обязательных продолжений к полному состоянию боя |
| [simulation](../../src/towr/simulation/) | Независимые trials, seeds, sequential/process исполнение и агрегаты |
| [balance](../../src/towr/balance/) | Оценка и ранжирование по агрегатам; без управления боем |
| [application](../../src/towr/application/) | Commands/services, генерация составов, бюджеты и фазовые ошибки |
| [adapters](../../src/towr/adapters/) | Строгое чтение JSON, схемы, отображение typed API и полный result echo |
| [controllers](../../src/towr/controllers/) | Выбор доступного действия в поддерживаемом сценарии |

## Инварианты

- Определение существа отделено от состояния экземпляра и состояния конкретного боя. P1 `CombatantDefinition`/`BattleEngine` — прототип, а не универсальная реализация книги.
- [Resolution kernel](resolution-kernel.md) исполняет один Test/Attack/effect; orchestration отвечает за порядок, action slots и follow-ups. Не добавлять универсальный язык правил или event bus.
- RNG передаётся явно. Trial получает собственный поток; воспроизводимость зависит от input/seed/runtime, а не глобального random state.
- Prepared request, result, receipt и journal witness связываются с полным источником. Совпадение ID или равенство projected state не заменяет admission исходного объекта. Результат применяется один раз к актуальному owner.
- Mandatory continuations разрешаются до обычного следующего действия. Неизвестные GM facts и неподдержанный обязательный путь дают явный stop, а не выдуманный игровой исход. UNSUPPORTED_PATH остаётся в знаменателе trials.
- Балансировщик использует общий бюджет, вход симулятора и агрегаты. Report/cache/source chain проверяется до пересоздания derived данных; encoder не переигрывает trials.

## Текущие внешние и игровые границы

Magic поддерживает только JSON6: [контракт](../decisions/ADR-0063-single-current-magic-contract.md), [публичные примеры](../examples/m8/json/README.md). Шесть request/result/error схем используют общий offline definitions file. Прежние wire formats удалены. Другие families имеют собственный единственный формат1.

Generation требует независимые matching family permissions и передаёт полный authored source в каждый допустимый subset. Arithmetic preflight не строит огромные коллекции; factory отдельно проверяет полный source и actual projections.

M8 — ограниченный Wizard/Curse сценарий с opt-in продолжениями. Для текущей Battered Leg границы важны [owner invariants60](../decisions/ADR-0060-battered-leg-owner-bridge.md), [native journal61](../decisions/ADR-0061-native-battered-leg-continuation.md) и delivery62, superseded только в части wire compatibility решением63. [Free self-stand64](../decisions/ADR-0064-battered-leg-prone-removal.md) хранит один bound stand в completion witness; собственный native prefix подтверждает его членство. Gate принимает точную injury после этого перехода, сохраняя stop для новых последствий. Standard self Recover также использует отдельный bound action proof в том же witness/history; расходует action slot и связывает уменьшение Pool с post-action skipped Casting. Allied removal пока не реализован. Полный каталог, arbitrary injury combinations, общий campaign loop и save/resume не следуют из наличия отдельных K1 consumers.

M9 вводит отдельные [PC input](../../src/towr/domain/pc_melee_models.py) и [battle owner/journal](../../src/towr/domain/pc_melee_result_models.py) по [ADR-0065](../decisions/ADR-0065-first-pc-melee-encounter.md). NpcDefinition не принимает PLAYER; PC использует Characteristics/Skills и PLAYER Wound lifecycle. В одном owner находятся общий clock, PC/Fate/daily state, Minion snapshots и источники последствий. Чистая проекция шагов проверяет actual K1 proofs и полный prefix, engine исполняет Attack/Recover/mandatory work. Independent trials отбрасывают journal, balance получает aggregate-only данные и перебирает bounded counts. PC имеет отдельный текущий JSON1/CLI; inverse compatibility с P1 или подмена PC Champion не вводятся. Общая inventory/campaign модель из этого bounded owner не следует.

Новые правила реализуются законченной функцией через нужные слои в рамках существующих инвариантов. Отдельный ADR создаётся при новом выборе или изменении границы, а не автоматически на каждый слой реализации.

M10 по [ADR-0066](../decisions/ADR-0066-pc-party-melee-encounter.md) расширяет тот же PC owner до uniform `party`, включая одиночную группу. Все участники имеют собственные definition/Fate/injury/daily/weapon/expiry; общий clock и journal определяют их взаимодействие. Pending PLAYER work содержит actor-владельца, а завершённая смерть исключает только погибшего. Ни временная подмена source, ни запуск отдельных дуэлей не используются. В compact trial остаются source-ordered IDs подтверждённых потерь; aggregate содержит per-PC counts и количество trials с потерями, включая observed prefix остановленного боя. Balance фиксирует всю party и проецирует enemy priority/defeat decisions каждого PC. Текущий PC JSON1 использует только uniform party shape; старый одиночный формат удалён.

M11 по [ADR-0067](../decisions/ADR-0067-pc-melee-profile-brutes.md) допускает static numeric Minion/Brute в том же owner. Target injury policy и предел происходят из полного NPC definition; `PcProfileWoundProof` подтверждает любой actual profile change. Nonterminal Wound сохраняет actor, terminal требует caller/GM defeat disposition; profile count не подменяет PLAYER lifecycle. Wire явно хранит policy/limit, generation сравнивает полный definition и фильтрует те же authored snapshots. Нового симулятора, версии wire или универсального описателя on-Wound behaviours нет.

M12 по [ADR-0068](../decisions/ADR-0068-pc-heavy-wound-continuation.md) хранит закрытые body facts и обязательные consequences каждого PC/Wound sequence в том же owner. End phase имеет bound Endurance/decline/результат и source-aware expiry; `PcIncapacitatedTurnEndProof` завершает настоящий actionless Defenceless turn, не подделывая standard action. Pure K1 Critical consumer не управляет RNG/clock/daily. Общий kernel выбирает forced Wound из фактического Damage Attack и target conditions/restrictions; признак physical_attack задаёт caller, а не выводится из numeric Damage. Canonical projections проверяют полные request/result types, prefix и обязательный Critical tail даже при последнем NPC defeat. Campaign/save и универсального body/inventory языка нет.

M13 по [ADR-0069](../decisions/ADR-0069-pc-near-miss-policy.md) сохраняет начальный Fate в source и разрешает текущему owner изменять его только фактическими lifecycle Near Miss proofs. Общий builder связывает включительный порог таблицы, резерв rating, текущий actor/roll и consumed history. Near Miss применяется до daily/effects/death; RNG повторно не исполняется. Compact trials/summary показывают только новые burns в полном порядке party, без переноса journal в balance. Перед извлечением observations проверяется полный result; cached ресурс не становится доверенным числом по одному ID или длине списка. В текущем PC JSON1 обязательный `near_miss_policy` явно связан с выбранной стратегией, остальные Fate options остаются declined.

M14 по [ADR-0070](../decisions/ADR-0070-pc-glorious-test-policy.md) добавляет отдельную Glorious configuration и общий mode `configured`, заменяя Near Miss-only имя. Pure PC selector/validator связывает собственный initial roll, навык и актуальные remaining spends с полным K1 spend proof; owner учитывает spend до последующего burn. Original Attack/Protection source сохраняется, effective Test получает только подтверждённый modifier. Общий `_resolve_attack_after_tests` завершает прежнюю арифметику без нового RNG. Все PC Tests, включая Wound/Critical/actionless end phase, используют один принцип. В compact/summary новые Glorious расходы отделены от Near Miss и supplied истории; balance остаётся aggregate-only. Текущая JSON1 требует обе nullable policies, прочие optional Fate uses остаются declined.

M15 по [ADR-0071](../decisions/ADR-0071-pc-melee-help-policy.md) добавляет `PcHelpProof` настоящего standard action и source-bound `help_applications` у намеченной PC Attack. Новой изменяемой очереди бонусов нет: applications строятся из точных предшествующих Help receipts того же owner и Test ID. Zero/multiple/capped/unused snapshots не теряют происхождение; старые бонусы не переназначаются другому actor/Test/round. Pure `_expected_help_execution` завершает прежние slot/bonus/clock transitions по actual Test, без RNG и зависимости домена от rules. Glorious/hand Critical/next-Test effects/end phase используют общий PC механизм, а clock PC-side→NPC-side сохраняется. Compact summary считает actual Help actions отдельно от Fate; generation фиксирует helper/beneficiary роли. Текущий PC JSON1 требует nullable `help_policy`.

M16 по [ADR-0072](../decisions/ADR-0072-pc-protection-help-policy.md) задаёт в Help configuration явные target и Protection Skill. Тот же generic application builder работает с actual attacker либо defender Test, связывая beneficiary/Skill/Test ID и всю предшествующую цепочку. Для Protection выбирается первый текущий live NPC при совпадении ожидаемой цели; original Protection options сохраняют Help до собственного Glorious. Equipment/target change, killed NPC и no-Test Defenceless оставляют snapshot unused. Выбор не хранит NPC ID в authored party, поэтому count projection не переписывает Help configuration. Новых owner banks, RNG, metrics или wire version нет.

M17 по [ADR-0073](../decisions/ADR-0073-pc-ally-standard-recover.md) оставляет один `PcRecoverProof`, но canonical standard choices могут затрагивать разные PC. Shared pure completion собирает прежние slot/clock receipts, PC projection применяет каждую change к её entity и сохраняет unrelated injury/Fate/daily/body. W13 consequence принадлежит поднятому получателю; receiving aid не является его действием14/15. Источники ongoing Conditions проверяются до выбора целей. Compact observations отдельно считают actual nonself Recover actions после exact result/journal admission, не число effects; source/turn/opening-round и joint support-action bounds проверяются в typed models. Role/beneficiary фиксируются в count search; текущий JSON1 требует nullable ally policy.

M18 расширяет существующую подготовку PC шестью одноручными Close weapons через [явные helpers](../../src/towr/domain/pc_weapon_models.py). Actor traits применяются к своему Test, targeted Warhammer trait — к actual Attack, Axe — отдельным DamageModifier без изменения Resilience. Каноническая проекция учитывает тот же полный impact spec/trace. [Нормализованная граница](../rules/equipment.md#исполняемая-pc-граница-m18) сохраняет прежние owner/hand/Help/Fate/Recover и JSON1, без нового языка правил, метрик и слоя inventory.
