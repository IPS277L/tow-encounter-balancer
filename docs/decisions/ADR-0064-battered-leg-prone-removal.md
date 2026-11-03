# ADR-0064: source-bound снятие Prone после Battered Leg

Дата: 2026-11-03; дополнено 2026-11-04. Статус: реализованы free self-stand и standard self Recover; адресные проверки завершены.

## Правило и граница

BOOK-PLAYER-GUIDE1.4, гл.V Free Actions116, Recover118, Conditions122, Prone123; Appendix / Wounds Table190/5. Локальные извлечения прочитаны адресно. Строка5 явно разрешает снять Prone свободным перемещением или Recover. Free self-stand выполняется в свой ход при unused free move и отсутствии enemy Close; сама Wound не требует лечения для снятия этого Condition.

Первоначальная функция подключила free self-stand единственного Wizard после провала существующего Endurance consumer. Сохраняется первая resolved/untreated/unhealed ordinary-Attack Wound5 и отсутствие иных Conditions/effects. Снятие Prone удаляет только её canonical UNTIL_REMOVED effect, сохраняет Wound, completed Test, action slot, magic state, placement и histories; расходуется одна free move. Recover добавлен дополнением ниже; помощь союзника, mounts и mixed injuries не подключены.

## Решение о доказательстве и scope

Общий standalone-Prone whitelist не расширяется. Отдельный full-owner Request/Result использует existing K1 FreeMoveProneRemovalRequest. Root completion witness60 хранит nullable `prone_stand` либо `prone_recover` — один actual bound result; поля взаимоисключающие. Его source хранит прежний completion без stand, поэтому доказательство конечно, без общего event archive. Execution gate сравнивает injury с завершённым Test либо с точным результатом stand/Recover; произвольное снятие effect/Condition без witness запрещено. Новое последствие после этого результата по-прежнему ограничивает exact-injury scope.

Native history61 хранит completed Endurance и nullable stand/Recover. Собственный журнал должен содержать actual stand между его полным source и resulting owner; detached receipt/history не заменяет membership. Pending continuations имеют прежний приоритет. Wizard встаёт на собственном ходе, не на ходе Minion сразу после Endurance.

## Выбор действия и текущий JSON

`NpcMagicBatteredLegPolicy.prone_policy` — nullable выбор `SELF_STAND_WHEN_SAFE` либо `RECOVER_SELF`. None оставляет Endurance-only stop; значение выбирает автоматический free self-stand при допустимой сцене/ресурсе. Разрешение независимо от Miscast policy, не открывает её пути. Если free stand невозможен, runner сохраняет явный unsupported stop; Recover автоматически не подставляется.

Current Magic JSON6 обновляется на месте: non-null Battered object требует `endurance_profile` и nullable `prone_policy`. Matching family assertion включает оба поля, encoders сохраняют полный policy. Новая wire version и legacy converter не вводятся.

## Проверка

Детерминированные owner tests: точное снятие cause, сохранность проекций/histories, отсутствие RNG/action receipt, enemy Close/spent usage/wrong turn, success/no completion, stale/repeated application и повреждённые nested sources. Native tests: actual failed Endurance → следующий Wizard turn → stand → normal Casting/end; permissionNone и Close stops, exact journal reconstruction/подмена witness, дальнейший injury scope. JSON/schema tests проверяют nullable/select policy, matching и original type guards; один generated source доказывает передачу выбора.

Полная regression и wheel не нужны для этой ограниченной вехи; проверяются изменённый owner/journal и ближайшие существующие consumers. Результаты и следующий шаг фиксируются в статусе, без отдельного standalone probe/аудита.

Результат: 11 новых owner tests и 15 прежних owner проверок прошли после исправления import нового теста; 21 прежний native unit test OK за 2.087s. JSON/schema: 31 tests OK за 9.504s, oracle-only null/selected × simulation/balance — 4 cases OK. Новый native module содержит 8 IDs, закрытых составно: исходный run7 имел 5OK/2ERROR (неверный Close fixture и sandbox WinError5 для spawn); после исправления late-scene fixture и адресных повторов каждый ID успешен. Один real-spawn trial прошёл с разрешённым multiprocessing pipe, новые Staggered/pending Miscast после stand сохраняют receipt и прежние stops. Полный зелёный прогон8 или всей regression не заявляется. Дополнительно actual smoke одновременно выбранных Miscast/Battered Prone policies дал один source-bound stand и ни одного generic stand.

Команды для воспроизведения новых checks: `python -m unittest tests.unit.test_m8_battered_leg_prone_stand tests.unit.test_m8_battered_leg_prone_json tests.integration.test_m8_battered_leg_prone -v` при `PYTHONPATH=src`. В sandbox Windows real spawn требует разрешения на pipe; известная ошибка окружения не скрывается skip. Локальные native logs: `.cache/battered-prone-native.log`, `.cache/battered-prone-native-recheck.log`; последний исправленный Close case выполнен отдельно успешно.

## Дополнение 2026-11-04: standard self Recover

BOOK-PLAYER-GUIDE1.4, Rules / Recover118, Interrupted Casting156, Miscasts157 и Wounds Table190/5 адресно сверены по локальным извлечениям. `recover_self` явно выбирает Recover вместо Casting при failed Endurance Prone. `self_stand_when_safe` не получает автоматического fallback; Miscast continuation сохраняет только свой прежний self-stand mode.

Native scheduler резервирует один STANDARD RECOVER slot. Новый full-owner Request/Result вызывает existing `execute_recover_action` в STANDARD mode: снимает self Prone и уменьшает Miscast Pool на один до минимума0. Затем existing skipped-Casting reducer применяется к magic state уже после Recover, если Casting активно. Это один action receipt и один root consumed ID, без расхода free move, лечения Wound, выбора ally/mount/object или дополнительного Condition Test. Recover разрешён при enemy Close и spent free move. Self action не требует attack target/range frame; закрытый roster даёт enemy-in-Zone fact.

Root/history `prone_recover` сохраняет полный bound action и Endurance; stand/recover взаимоисключены, повтор и подмена source/consumption/slot отвергаются. Новые последствия после Recover сохраняют exact-injury stop. В текущем admitted owner WizardLevel>=1, pre-action Pool<=Level и pending continuations блокируют действие: поэтому Recover-1 затем skipped+1 сам не может создать Miscast trigger. При активном Pool1 проверен переход1→0→1; при нуле получится1. Новую ветку Recover-origin Miscast journal не открываем; последующее обычное Casting с Miscast использует прежний origin contract.

Current JSON6 Battered `prone_policy` допускает null, `self_stand_when_safe`, `recover_self`; matching и full echo включают выбор. Отдельная версия/миграция не нужны. [Owner](../../src/towr/domain/npc_roster_battered_leg_recover_models.py), [executor](../../src/towr/engine/npc_roster_battered_leg_recover.py), [owner tests](../../tests/unit/test_m8_battered_leg_recover.py), [native tests](../../tests/integration/test_m8_battered_leg_recover.py), [JSON tests](../../tests/unit/test_m8_battered_leg_recover_json.py).

Проверка дополнения: 10new owner tests OK/1.228s; 26stand/owner adjacent OK/0.943s; 23JSON/schema tests OK/5.225s; 32native/Miscast/две прежние free-path проверки OK/10.401s. Пять native checks прошли одним run за33.744s, шестой mandatory-Pool admission case — отдельно за6.674s. Это адресный результат нескольких прогонов; full regression и wheel не запускались. Native проверяет фактический Recover/end, active Casting, post-Recover Staggered и журнал, а Close/spent-free случай — actual full-owner transition в authored late scene, не заявленный fresh native путь с запрещённым initial Shooting Close.

Дополнительная проверка реально достижимого origin после Recover: обычное Casting на следующем ходе вызвало Miscast, actual preparation/roll сохранили bound Recover receipt и Casting origin; 1test OK/35.248s. Всего в новом native module7ID закрыты успешными адресными прогонами. Import-only discovery4312tests без loader errors; offline25schemas/329refs,4886локальных ссылок/207Markdown и diff проверены. Это не исполнение всех4312tests.
