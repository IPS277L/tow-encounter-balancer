# M9: один PC против Minions

Книжный немагический персонаж с Staff/Sword против numeric Minions в одной Zone. [Контракт и граница](../../decisions/ADR-0065-first-pc-melee-encounter.md). Источники: Player’s Guide1.4 / Skills68–69, Equipment92–93, Fate111–112, Combat118–123, Wounds190–191. Профили противников здесь authored, а не переименованные записи бестиария.

Из корня репозитория после установки:

```powershell
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m9/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m9/pc-melee-balance.request.json
```

Console entry point: `towr simulate-pc-melee INPUT` и `towr balance-pc-melee INPUT`; `-` читает UTF-8 stdin. Текущая family — только JSON1; Magic сохраняет собственный JSON6. Семь [PC-схем](../../../src/towr/adapters/schemas/) разрешают ссылки offline.

## Что задано во входах

[Simulation request](pc-melee-simulation.request.json) задаёт PC с WS3, Strength3, Toughness3, Agility3, Melee5, Defence5, Athletics4, Endurance4, Sword и armour bonus0. Melee/Defence используют реальный `TestProfile(WS,Skill)`, cap2×WS; Sword даёт +1d Defence, пока PC не Staggered, а Drained подавляет этот бонус. Два Minions атакуют по указанному порядку; PC выбирает первую живую цель из priority. Seed42,8 trials, максимум4раунда.

[Balance request](pc-melee-balance.request.json) фиксирует более устойчивый пример PC: WS4, Strength4, Toughness4, Agility4, Defence6, Endurance5; остальные поля заданы во входе. Reserve содержит трёх одинаковых Minions, поиск перебирает counts1–3. Каждый subset берёт префикс ordered group, сохраняя activation/target/defeat order из template. Явные generation facts подтверждены для всего семейства. Бюджет: 3 состава × 8 trials = 24; target окна 1/2, допустимый диапазон 0–1, top_k2. Все составы допускаются до первого RNG/worker.

Обязательные policies:

- `attack_or_recover_self`: Attack, либо Standard Recover при Prone/потере собственного оружия. Пока оружие на земле, PC защищается Athletics; Recover возвращает его в исходную руку, снимает допустимые Staggered/Prone и сохраняет ongoing эффекты ран.
- `decline_optional_fate`: заранее выбранный отказ от optional spends/burns. Полный FateSessionState сохраняется; пример имеет rating3 и allowance3. На PLAYER Wound actual Near Miss window закрывается до регистрации за день, эффекта и определения смерти. Нет автоматического refresh между независимыми боями.
- Повторный Staggered: `SUFFER_WOUND`. Это выбранная стратегия, а не утверждение недоступности остальных книжных choices.
- `d10_low_left_high_right`: для требуемой случайной руки1–5означаетleft,6–10right. Если выбрана пустая рука, оружие из другой не выпадает.

Порядок сторон фиксирован книжным правилом без ambush: PC, затем Minions. Scene/Close/awareness/отсутствие внешних эффектов подтверждаются явно. Outnumbering пересчитывается по живому составу, если GM разрешил бонус; Prone учитывается отдельно от отсутствия terrain modifiers.

## Результаты и ограничения

Simulation возвращает полный request и aggregate summary. Outcome `objective_achieved` означает defeat всех целей; `pc_defeated` здесь означает завершённую lethal PLAYER Wound после Near Miss decline. `round_limit` и `unsupported_path` учитываются отдельно в общем числе trials. Counter actions включает Recover, а не только Attack.

Balance возвращает полный исходный request, каждый реально оценённый candidate source/counts/summary, точные rational rates, assessment и выбранные IDs. Любое observed unsupported делает кандидата `unsupported_observations`, `window_match:null` и исключает его из selection. Оценка относится к указанным policies и конечному числу прогонов; они не изображают оптимальную игру персонажа.

Сохранённые результаты получены настоящими CLI-командами на указанном runtime: [simulation](pc-melee-simulation.result.json) содержит 7 objective/1 unsupported из 8 trials; [balance](pc-melee-balance.result.json) оценивает 3 состава за 24 trials и выбирает counts3, затем1. В данном balance-примере у counts3 наблюдались 6 objective/2 round limit, у counts1/2 — 8 objective. Это иллюстрация заданного входа и ранжирования, а не фиксированные игровые вероятности.

Исполняются Wounds1–10 с immediate Endurance/drop/Prone, temporary Drained/Blinded expiry, next-Test Grim и repeated/mixed источниками. Lethal24+ завершается через PLAYER lifecycle. Результаты11–23 сохраняют actual pending Wound до её completion/daily/effects и дают unsupported. Начальный Wound/daily журнал пуст; прежние campaign-раны и receipts не переносятся. Общий inventory, все виды оружия, Talents, магия, лечение, campaign и save/resume находятся вне этого среза. Имеющиеся поля sheet/resource — авторский готовый профиль, без создания персонажа или проверки всей истории advancement.

JSON строгий: неизвестные поля, duplicate keys, float/exponent/nonfinite tokens и некорректный UTF-8 отвергаются. Seed — canonical decimal string uint64. Fractions окна несократимы, с положительным denominator;0представляется как0/1. Все допущенные request JSON-значения возвращаются без скрытой нормализации. `execution` задаётся явно: `{"mode":"sequential"}` либо `{"mode":"process","workers":2,"batch_size":3}`. Ошибки входа дают exit2, исполнения — exit3, I/O — exit4; stdout содержит JSON ответа, stderr — краткую диагностику.
