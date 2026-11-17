# Ограниченный реальный контроль совместных целей

Дата:2026-11-18. Диагностика принятого [ADR-0137](../decisions/ADR-0137-joint-encounter-targets.md), не сравнение нового solver со старым win-first и не подбор objective по результатам.

## Протокол до первого боя

Три партии из текущих public examples: melee; ranged PC с melee союзником; та же mixed-партия с Elementalism mage. Все используют **автоматическое** пространство допустимых NPC-компонентов, count1–10, stationary Close, новые совместные допуски±10п.п./±1раунд (Round), targets50%/5, round budget15. В прежнем melee-примере explicit Staff/Dagger space снят до запуска: это новая fullauto-серия, не matched comparison с историческим restricted-melee.

Master505не использовался для прежних игровых прогонов. Mixed-вход сохраняет полный JSON-объект зарезервированного `.cache/adr132/mixed-505.request.json`; равенство полей проверено до копирования. Два остальных входа получают505до измерений. Один seed на три разные партии — не три независимых seed replicates и не оценка частоты успеха генератора.

Каждый план6×8exploration +до2×32validation: максимум112MC trials, вся серия максимум336. Если supported exploration меньше2, validation законно короче; не дополнять бюджет боями. Execution process4, один pool на поиск, запросы последовательно. Точные source/request hashes — `.cache/joint-control-2026-11-18/frozen.json`. Вся серия допущена parser до первого боя.

Никаких изменений score/proposals/targets/budget/native rules во время серии. Каждый exact input выполняется один раз. Нет условного full436или добавочных финалистов по удачным промежуточным значениям. Это диагностический baseline принятого joint score, не gate для отката авторизованного пользовательского решения.

## Метрики и область выводов

Existing developer harness получает postprocess `joint_target_metrics` без новых публичных полей и RNG. Candidate partitions на каждой стадии: both/win_only/rounds_only/neither/unsupported. Они непересекающиеся и в сумме равны числу составов; unsupported имеет приоритет даже при численном совпадении осей. Это количество **составов**, не trials.

Screening→validation связываются по полному **упорядоченному** source GeneratedNpc, включая характеристики, навыки, снаряжение (Equipment), таланты (Talents), способности (Abilities) и ranged confirmations. Для каждой пары сохраняются оба статуса и win/mean_started_rounds estimates. Это пары одинаковых составов с независимыми stage seeds, не paired battle observations.

Отдельно показать: сколько screening point-matches проверялось, сколько сохранилось, сколько появилось только на validation; status/оценки/интервалы выбранного финалиста; все actual unsupported/round-limits, стоимость и proposal attempts/duplicates/cap. `target_match_found` только по supported validation.

Наблюдаемое совпадение на8/32боях не является true-probability coverage или95%сертификатом. При отсутствии совпадений формулировать «среди измеренных составов совпадение оценок не обнаружено»: причина может быть в proposals, шуме оценки или ограничениях сцены. Контроль не изолирует эти причины. Duration остаётся started-round prefix metric; unknown не становится поражением.

Для строгого контроля расхода `--unsupported-samples 0`: дополнительных diagnostic native replays нет. Все unknown indices/seeds/prefixes сохраняются в `unsupported_observations`, а aggregate counts остаются полными. Typed причины без replay не выдумывать. Search/encoding и диагностическое время показываются отдельно; process startup/shutdown входят в search.

## Проверка и воспроизведение

16адресных harness tests прошли за4.498s (`harness-validation.log`): полное source matching, partition/transition counts, отсутствие мутации входа, пустая validation, zero-replay CLI и сохранение полного native public result при трассировке. Исправлена shallow-copy ошибка в новом тестовом fixture; production metrics не подгонялись. Game source не меняется этой задачей. Full/wheel/повторный browser/game regression не нужны.

```powershell
$env:PYTHONPATH='src;.'
.venv/Scripts/python.exe -u tools/benchmark_dynamic.py --requests .cache/joint-control-2026-11-18/melee-505.request.json .cache/joint-control-2026-11-18/mixed-505.request.json .cache/joint-control-2026-11-18/mixed-magic-505.request.json --unsupported-samples 0 --output .cache/joint-control-2026-11-18/measurements.json
```

После серии проверены source/schema/accounting/полный набор3unique request IDs/actual diagnostics и неизменность hashes без новых симуляций. Исходы разных составов не объединяются в одну вероятность победы.505теперь является development-контролем текущего score и больше не считается неиспользованным holdout. Commit/push выполняет пользователь.

## Результаты завершённой серии

Все три поиска завершились без ошибки исполнения:336actual MC trials, ноль diagnostic replays. Среди18exploration и6validation оценённых составов **совпадение обеих целей не обнаружено**. Во всех трёх публичных результатах `target_match_found=false`; выбранные supported best-available составы имеют статус `outside_targets`.

Основная рекомендация каждого поиска после32независимых от screening боёв:

| Партия | PC / NPC | Победы игроков | Средние начатые раунды | Wilson95% для побед | Hoeffding95% для раундов |
| --- | --- | --- | --- | --- | --- |
| melee | 2 / 5 | 25/32;78.125% | 7.125 | 61.245–88.976% | 3.764–10.486 |
| mixed | 2 / 6 | 13/32;40.625% | 8.250 | 25.520–57.740% | 4.889–11.611 |
| mixed-magic | 3 / 7 | 32/32;100% | 4.09375 | 89.282–100% | 1–7.455 |

В mixed соблюдён win-допуск40–60%, но не duration4–6; в mixed-magic наоборот. Интервалы описывают отдельные оценки в существующем result contract; они не являются одновременной гарантией по выбранным составам и не доказывают попадание истинных параметров в обе полосы.32/32не означает истинную вероятность100%.

Непересекающиеся partitions, число **составов**:

| Партия / стадия | Обе цели | Только победы | Только раунды | Ни одна | Unsupported | Всего |
| --- | --- | --- | --- | --- | --- | --- |
| melee / exploration | 0 | 0 | 3 | 3 | 0 | 6 |
| melee / validation | 0 | 0 | 1 | 1 | 0 | 2 |
| mixed / exploration | 0 | 1 | 3 | 2 | 0 | 6 |
| mixed / validation | 0 | 1 | 1 | 0 | 0 | 2 |
| mixed-magic / exploration | 0 | 0 | 1 | 5 | 0 | 6 |
| mixed-magic / validation | 0 | 0 | 1 | 1 | 0 | 2 |

Screening point-matches, отправленных на validation:0. Сохранившихся:0; новых validation point-matches:0. Retention0/0**не определён**, это не0%успеха повторной проверки и не доказательство ошибки выбора финалистов. Полные составы сопоставлены по всем компонентам; каждая строка ниже — один неизменный состав, независимо оценённый на8и32боях:

| Партия / source exploration→validation | NPC | Win estimate до→после | Started rounds до→после | Статусы |
| --- | --- | --- | --- | --- |
| melee / 3→0 | 5 | 62.5%→78.125% | 7.375→7.125 | outside→outside |
| melee / 2→1 | 4 | 87.5%→96.875% | 5→4.8125 | outside→outside |
| mixed / 5→0 | 6 | 50%→40.625% | 7.75→8.25 | outside→outside |
| mixed / 1→1 | 4 | 100%→100% | 4.875→4.46875 | outside→outside |
| mixed-magic / 5→0 | 7 | 100%→100% | 4.375→4.09375 | outside→outside |
| mixed-magic / 3→1 | 5 | 100%→100% | 2.875→2.84375 | outside→outside |

Source IDs имеют вид `dynamic:explore:N` и `dynamic:validate:N`; validation ID обозначает исходный слот, а не позицию после финальной сортировки.

## Стоимость и ограничения

| Партия | Search, с | Encoding, с | Trials | Round limit | Unsupported | Посещённые NPC counts |
| --- | --- | --- | --- | --- | --- | --- |
| melee | 51.716 | 0.546 | 112 | 0 | 0 | 3,4,4,5,4,6 |
| mixed | 97.088 | 0.177 | 112 | 1 | 0 | 3,4,4,5,4,6 |
| mixed-magic | 81.375 | 0.210 | 112 | 0 | 0 | 3,4,4,5,4,7 |

Search+encoding всей серии231.113s, около3.85мин на этой машине. Единственный `ROUND_LIMIT` возник в mixed/exploration5; это отдельный исход в знаменателе8, он не засчитан как победа. На validation лимитов нет. Каждый поиск сделал6proposal attempts, принял6unique составов, без дубликатов и proposal cap. Ошибок исполнения/дополнительных replay не было.

Counts1,2,8,9,10не посещены в коротком плане. При8exploration trials внутри win-полосы40–60% лежит только4/8: разрешение предварительной оценки грубое. Эти наблюдения не разделяют вклад числа кандидатов, шума, траектории поиска и достижимости двух целей. Три партии с одним master seed не устанавливают устойчивость генератора по seeds. Отсутствие unknown на336боях не снимает известные ограничения магических ошибок (Miscasts).

## Целостность артефактов

Private verifier `.cache/joint-control-2026-11-18/verify.py` завершён успешно:3точных запроса,24полных native sources и336trials. Проверены offline schemas, source echoes, automatic resolved space, GeneratedNpc→native source, независимость stage seeds, accounting/outcomes, eligibility/ranking/selected, target metadata, proposal telemetry и отсутствие diagnostic replays. Проверка не исполняет бои.

Production `source_sha256` до/после: `90123298cbe1622c57e10d63565dda8bafc2b534c9ade9a392a3c0f333961ff7`.

Developer harness SHA-256: `87e10d8caed5963fe48151ad5b47eafb37524f712e70c06c48a793b35ab5bd7e`.

Frozen manifest вычислил request SHA-256 по UTF-8 тексту с LF до Windows-записи с CRLF. Это обнаружено при проверке; исходный manifest/JSON-объекты не менялись, симуляции не повторялись. Два явно разных вида digest сохранены в `verification.json`:

| Запрос | UTF-8/LF SHA-256 из manifest | SHA-256 фактического CRLF-файла |
| --- | --- | --- |
| melee | `d442e124b3fa8101c34785d5b1f10c6df8c23de5af0d877f7ccb4bd534d67180` | `99baf41fd1831f05ef2b8e2cd16b72b7974f64afd8931d95d74d6d72de25daf2` |
| mixed | `8b2bbeaf861b24dee279d1e3f40ae321ed56f13e79306f5c6a4b921856dbcd4e` | `054a72bc3f6ec8473becc1448af4441a52f4971e30a79dddab7822cf6ab32659` |
| mixed-magic | `7e3b0f94be55dffe497617d60a6de4bd5ff5ddc3bb0132bedece91970c7d826f` | `0ddaf9f6657284766de566c5923dd46cf7e646edeb8149a39f9a551502d0b069` |

Сырые результаты/log/frozen manifest/verification остаются в локальной `.cache`. Для другой машины точные JSON-объекты воспроизводятся из текущих repository examples следующим кодом; полное равенство всем трём frozen inputs проверено без симуляций. Этот код только создаёт входные файлы. При изменившихся examples сначала восстановить соответствующий source revision, а не считать новый вход прежним.

```python
import json
from pathlib import Path
from tools.benchmark_dynamic import benchmark_input

folder = Path('.cache/joint-control-reproduction')
folder.mkdir(parents=True, exist_ok=True)
for case in ('melee', 'mixed', 'mixed-magic'):
    document = benchmark_input(case, 505, candidates=6, exploration=8,
        finalists=2, validation=32, minimum_npcs=1, maximum_npcs=10)
    document['request_id'] = ('stability:mixed:505' if case == 'mixed'
        else f'joint-control:{case}:505')
    document['search_space'] = None
    document['execution'] = {'mode': 'process', 'workers': 4}
    (folder / f'{case}-505.request.json').write_bytes(
        (json.dumps(document, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
```

## Решение и следующий шаг

ADR-0137 остаётся принятой целью продукта. Серия дала диагностический baseline; новый solver, precision reserve или ослабление unsupported по этим данным не вводятся.

Следующий законченный шаг — **один заранее зафиксированный полный текущий UI-автоплан для mixed-magic505** с теми же сценой/партией/целями. До первого боя извлечь фактические C/E/V из общего planner, заморозить точный запрос/максимальный расход и сохранить те же метрики, включая actual unknown. Это проверит обычный пользовательский режим после смены objective; исторический fullUI202использовал прежний win-first score.

Следующий поиск не входил в эту336-trial серию и здесь не запускался. Он будет сравнением двух планов на известном development-case: C/E/V меняются вместе, поэтому причинный эффект одного параметра не изолирован. При совпавших полном составе и stage/index тот же master505может переиспользовать indexed trial prefixes; результаты двух планов нельзя складывать как независимые наблюдения. Внутри каждого плана validation остаётся отдельной от screening. После этого измерения выбирать изменение поиска по фактическому поведению полного режима, сохраняя обе цели и source guards.
