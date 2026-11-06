# ADR-0086: canonical cap8 для Minotaur Greataxe

Дата: 2026-11-06. Статус: **принято пользователем и реализовано**. Выбрана узкая граница: cap8 только для книжной Greataxe Minotaur; authored NPC не расширяются.

## Задача и уточнение предыдущего анализа

BOOK-GM-GUIDE1.1, Allies and Antagonists / Minotaur147: WS4, Greataxe Close3d/5 Damage8,2H; BOOK-PLAYER-GUIDE1.4, Dice Pools107: maximum8 от Characteristic4. Printed3d уже включает особенность оружия, второй штраф не применяется.

В M37 неправильно описана wire структура: current PC JSON1 **уже требует** поле pool_cap в attack/protection test_profile. Codec использует asdict/InlineProfile(**source), значение сохраняется при roundtrip. Ограничения — schema type:null и domain _readmit_inline, отклоняющий любой non-null cap. Старые requests/echo содержат pool_cap:null; их миграция и новый формат не нужны. Исправление описания не меняет завершённую M37: Axe4d/5 cap8 и прежние результаты корректны.

## Принятая граница M38

Добавить один loadout MINOTAUR_GREATAXE = minotaur_greataxe, book source BOOK-GM-GUIDE:1.1:p147:minotaur_greataxe. Brute3/T5Res6/noShield; Greataxe Close3d/5 Damage8,2H; Athletics4d/4. Наследуются W1/W2 ordinary+1/+2d Melee, Devour и текущие Attack/SUFFER_WOUND/noMove ограничения. Dual Damage+1 к этому варианту не применяется.

Полное описание атаки содержит:

```json
"test_profile": {"dice": 3, "threshold": 5, "pool_cap": 8}
```

Protection сохраняет pool_cap:null; прежние34loadouts и authored numeric NPC сохраняют null в обоих профилях. None означает прежний implicit cap=2×printed dice. Caller не получает новое произвольное управление cap для authored NPC.

Domain readmission явно допускает non-null cap **только для attack canonical Minotaur Greataxe**. Полная canonical definition validation проверяет ID, source, printed dice/threshold/Damage/руки/Protection и cap8, включая bool/string aliases и partially renamed sources. Иное значение, null под новым book ID, non-null Protection или non-null cap другого/authored NPC отвергаются до RNG.

Schema inline_profile расширяется от type:null до enum:[null,8]; значения4/6/7/9 по-прежнему отвергаются структурно. Ограничение8 только canonical attack остаётся в domain, как существующие canonical Damage/gear restrictions. Поле остаётся обязательным, closed object прежний. Codec не вычисляет cap из ID, не чинит source и не подставляет default при пропуске. Current JSON1/метрики/команды неизменны.

## Альтернатива большей публичной границы

Рассматривалось разрешить explicit positive pool_cap также у authored numeric NPC и/или выбранной Protection. Это самостоятельное расширение source API: caller смог бы моделировать modified printed pools с иным maximum без книжной identity. Пользователь выбрал узкую canonical-only границу выше; authored-cap rejection tests сохранены.

## Адресная приёмка

1. Printed3d/5 Damage8/2H и cap8, fresh graphs/full source/точные nested types; отсутствие второго weapon penalty и dual Damage modifier.
2. Actual W0/W1/W2 pools3/4/5 до прочих бонусов, W3defeat, ordinary bonuses capped8 и отдельный Help bypass, Drained filter и сохранение Devour table die.
3. Source caps null/6/7/9/bool/raw strings, Protection cap, other book/authored cap, partial rename и cached equivalent aliases отвергаются; отсутствие поля отвергается schema.
4. JSON1 roundtrip/schema/semantic error, native journal/Wounds/Fate, trials/count search и исполняемый CLI-пример.
5. Прежние34entries и116JSON documents M9–M37 сохраняются без миграции. Ближайшие PC model/schema/codec/Attack/Wound/Test/Help consumers; full project/wheel/повторная backend matrix без изменения соответствующего механизма не требуются.

Согласование нужно по [AGENTS.md](../../AGENTS.md), раздел «Автономная работа до согласованной вехи»: «Спрашивать при существенной неоднозначности правил, смене согласованного контракта или блокере с решением пользователя». Здесь меняются допустимые значения публичного source pool_cap; книжное число8 неоднозначности не содержит.

Реализация: [catalog](../../src/towr/domain/pc_npc_catalog.py), [attack/Protection cap admission](../../src/towr/domain/pc_melee_models.py), [Rage/Devour registry](../../src/towr/domain/pc_npc_ability_models.py), [schema enum](../../src/towr/adapters/schemas/pc-melee-common.schema.json). Codec не менялся. Проверки: [catalog/source](../../tests/unit/test_m38_pc_greataxe_catalog.py), [native cap/rage/Help/Drained/guards](../../tests/unit/test_m38_pc_greataxe_execution.py), [JSON/trials/search](../../tests/integration/test_m38_pc_greataxe_cap.py), [CLI-примеры](../examples/m38/README.md). Контроль17модулей/213tests прошёл за12.406s; включая23новыхtests. Текущее состояние — [project-status](../project-status.md), исходная граница — [ADR-0085](ADR-0085-pc-devour-and-wound-rage.md).
