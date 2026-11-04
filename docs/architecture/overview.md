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
