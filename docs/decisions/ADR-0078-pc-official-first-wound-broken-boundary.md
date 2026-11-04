# ADR-0078: Empire Official, первая рана и граница Broken turn

Дата: 2026-11-04. Статус: принято.

## Задача и выбранная граница

M23 добавляет первый книжный Brute с последствием раны: Empire Official с Dagger. Пользователь выбрал применить Wound/Broken, продолжить остальных участников до собственного хода Official, затем вернуть UNSUPPORTED_PATH для неисполняемого бегства. Вторая рана до этого окна даёт обычный defeat. Это ограничение среза, а не house rule, позволяющее игнорировать Broken.

Источники: BOOK-GM-GUIDE1.1, Allies and Antagonists / Brutes92 / NPC Profiles93 / Empire Official98; BOOK-PLAYER-GUIDE1.4, Conditions / Broken122. [Нормализованное правило RULE-PROFILE-TALABEC-007](../rules/npc-profile-catalog.md#official-broken-m23) сохраняет числа и Wound bands.

## Каталог и последствие раны

`EMPIRE_OFFICIAL_DAGGER` явно выбирает Dagger; Pistol остаётся unselected. Это Brute2, Toughness3/Resilience3, Dagger Close2d/3 Damage2,1H, Athletics3d/3. Printed Protection не использует число кубов атаки. Heard It All Before сохранён как inactive в нынешней сцене: она не исполняет Persuade/Distract, к которым относится Grim без bribe.

Catalog entry получает описательные `wound_bands`:0 — no effect,1 — Broken,2 — defeated. У прежних трёх профилей tuple пуст. Фабрика берёт wound_limit из exact definition, поэтому Official начинает0/2, прежние Minions0/1. Metadata не становится универсальным языком правил.

На фактическом living Brute0→1 `PcProfileWoundProof` подтверждает очередь и применяет Broken отдельным pure helper в PC projection. Raw Attack уже увеличил Wounds, но ещё не завершил профильное последствие. Повторное ACK запрещено существующей очередью; Broken не применяется на каждом snapshot или заново при W2. Авторские static Brutes сохраняют прежнее поведение. Общий K1 Profile Wound resolver не меняется.

Broken не запрещает Official Oppose через printed Athletics и не делает обычную защиту Grim. Эффект требует тратить **собственный** ход на движение в безопасную Zone. Остальные PC могут атаковать до этого окна; Broken остаётся combatant для обычного outnumbering. Не подставляем немедленный flee, defeat или новый Willpower roll.

## Точное окно остановки

Остановка возможна только после всех pending/Wound receipts, при отсутствии active turn, живых сторонах и незавершённом текущем round, когда следующим actor выбран живой Broken Official. Она возвращается **до TurnStart/reservation** этого NPC. End phase/Critical предыдущего PC и ходы других участников не пропускаются.

Official, получивший вторую рану раньше, исключается обычным defeat. Party death сохраняет обычный исход. Завершённый последний budget round остаётся ROUND_LIMIT; при разрешённом новом round сначала ходят PC, которые ещё могут победить. Synthetic проверки таких общих приоритетов не объявляются reachable fresh encounter traces.

`can_leave_zone` относится к существующим kernel choices и не предоставляет маршрут, безопасную Zone или fastest-path facts для Broken. M8 consumers требуют spatial state/подтверждённые routes, которых этот owner не имеет. Их нельзя подключить выдуманным маршрутом.

## Источник и публичная форма

Новый `PcNpcBrokenTurnUnsupported` хранит actor, actual parent Attack execution ID, exact Brute0→1 profile change, reason `npc_broken_turn` и source ID `RULE-PROFILE-TALABEC-007:first-wound-broken:{actor}:{attack_id}`. Attack — реальная PC-атака, причинившая рану. Два Official с одинаковыми значениями change различаются по target и parent receipt.

`PcMeleeScenarioResult.unsupported` допускает этот отдельный native variant наряду с прежним PC Wounds Table stop. NPC не получает фиктивный table_total/wound_sequence игрока. Exact типы и полный replay подтверждают причину и окно; дальнейшие journal steps после stop запрещены. Прежние PC stops сохраняют свой приоритет и данные.

Trials/process считают actual prefix и обычный UNSUPPORTED_PATH; кандидаты с ним исключаются из выбора, trials остаются в знаменателе. Current JSON1 уже выражает Brute definition/limit/Skill и агрегаты, поэтому новых полей/version/метрик нет. Старые request/result pairs не мигрируются. Python metadata/native result расширены в текущем development API.

## Отложенное решение

M23 не исполняет бегство, Leadership/Willpower recovery или post-battle поведение NPC. Возможность снять Broken при сохраняющейся profile Wound не выбрана: таблица задаёт последствие W1, а PG122 отдельно ограничивает снятие Conditions от ongoing causes. Этот вопрос не нужен для выбранной остановки и должен быть уточнён перед будущим Recover/route продолжением.

## Альтернативы

- Остановка сразу на W1 теряла бы законную вторую атаку PC и предыдущие end phases.
- Продолжение обычного Attack на Broken turn противоречило бы PG122.
- Автоматический defeat/escape менял бы objective и потери без явно выбранного контракта.
- Подмена NPC cause полями PC Wounds Table или generic marker теряла бы реальный источник.

## Проверка

[Catalog/wound bands](../../tests/unit/test_m23_pc_official_catalog.py), [native order/cause/replay и labeled pure priorities](../../tests/unit/test_m23_pc_official_wounds.py), [actual process/JSON/count search/cache](../../tests/integration/test_m23_pc_official.py). Ближайшие зависимости — M11 static Brutes, M21/M22 profiles/Attack, source/Protection/summary и прежние M19/M20 unsupported variants.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.unit.test_m23_pc_official_catalog tests.unit.test_m23_pc_official_wounds tests.integration.test_m23_pc_official tests.unit.test_m11_pc_melee_brutes tests.unit.test_m19_pc_two_handed tests.unit.test_m20_pc_backup_weapon -q
```

Actual CLI examples, full source echo, неизменность старых JSON-пар и ссылки проверяются адресно. Full/wheel автоматически не требуются: shared K1/сборка/доставка не менялись. Фактические результаты — в [статусе](../project-status.md).
