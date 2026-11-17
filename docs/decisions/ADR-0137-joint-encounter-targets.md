# ADR-0137: совместные цели динамического боя

Дата:2026-11-18. Статус: реализовано/проверено. Решение пользователя принято: одновременно попадать в допуски±10процентных пунктов по доле побед и±1по среднему числу начатых раундов (Rounds). Например50%/5означают40–60%и4–6. Это критерий продукта, не изменение книжных правил.

## Ранжирование и альтернативы

Прежний win-first score использовал раунды только при точном равенстве win error. Сумма ненормированных ошибок смешивала разные единицы; одна сумма нормированных ошибок позволяла бы компенсировать сильный промах одной оси другой. Выбран minimax: `d_win=abs(win_rate−target)/.1`, `d_round=abs(mean_started_rounds−target)/1`; сначала поддержанность, затем `max(d_win,d_round)`, затем `d_win+d_round`, затем прежний стабильный порядок. Это равноправие **относительно допусков**, не равная статистическая неопределённость и не доказательство оптимальности.

Обе границы включены. При целях у предела допустимого диапазона сравнивается отклонение от самого target; физические диапазоны вероятности[0,1]и длительности[1,max_rounds]сохраняются. Нормированные величины в окрестности1±1e−12приравниваются1, остальные округляются до12знаков; inclusion и ranking используют одну функцию. Тем самым within всегда имеет max≤1, outside — max>1.

Один assessment применяется к elite/search finalists, validator и повторному ранжированию независимой validation. Proposal RNG/budget/count±1/restart, правила, native trials и смыслы round-limit/unknown прежние. Эвристика направления count по наблюдаемой доле побед не становится доказательством монотонности длительности; компонентная мутация/restarts остаются доступны. В точном target по победам при промахе длительности доступен прежний fallback, без выдуманной численностной политики.

## Статусы и поддержанность

`within_targets` означает совпадение **точечных оценок** с обеими полосами; `outside_targets` — лучший найденный поддержанный вариант может не выполнить цель; `unsupported` — actual unknown исключает вариант независимо от численных совпадений. При отсутствии совпадения возвращаются поддержанные лучшие приближения с явным статусом, а не ложным «цель достигнута». `target_match_found` считается только по supported validation, не по exploration.

Это не95%сертификат и не обещание качества будущего боя. Wilson/Hoeffding intervals сохраняются с прежней областью применимости; фиксированный precision/резерв из математического стенда не переносится автоматически. Duration по-прежнему mean_started_rounds с видимыми censored prefixes; actual unknown не превращается в поражение/успех, а round-limit не считается победой. Полная латентная вероятность/terminal duration из остановленных префиксов не восстанавливаются.

## Текущий JSON1 и UI

Вход не меняется; допуски фиксированы выбранным продуктовым контрактом. В текущем результате обязательны:

```json
{
  "target_criteria": {
    "basis": "point_estimates",
    "win_rate_tolerance": 0.1,
    "started_rounds_tolerance": 1
  },
  "target_match_found": false
}
```

У каждого candidate обязательный `target_assessment`: status, win_rate_in_range, started_rounds_in_range, абсолютные win_rate_deviation/started_rounds_deviation, normalized_max_deviation/normalized_total_deviation. Axis flags — только численное совпадение; status unsupported имеет приоритет. Schema и semantic validation пересчитывают метаданные по target/агрегатам, не доверяют загруженному badge/score. `selected` сохраняет все supported validation в новом порядке, включая outside. Устаревшие result objects без metadata не являются вторым поддержанным форматом; wire version остаётся1по политике разработки.

UI показывает допуски и различает совпадение оценок/приближение/unsupported; не называет point match подтверждённой вероятностью. Stale request и изменённый NPC draft не переоценивают исходную статистику. Загрузка результата проверяет metadata до замены текущего отчёта/черновиков.

## Адресная проверка

Детерминированные assessment/ranking случаи: обе границы, цели0/1и крайние round budgets, выигрыш совместного кандидата над идеальным win с плохой длительностью, minimax и sum tie-break, стабильные ties, неизвестный исход при совпавших оценках, отсутствие joint validation при совпавшей exploration, outside best available. Native summary/result validation проверяет весь source/seed/trial accounting, а JSON — обязательность/подмену статусов/errors/criteria/overall и порядок selection. Один representative process/sequential результат должен совпасть; UI-проверки и один браузерный сценарий покрывают отображение/импорт/stale/draft.

Это согласованная замена целевой функции, не очередная эвристика с672-trial gate. Большой MC/full/wheel без отдельного риска не нужны. Проверки действующего count/progress/JSON/CLI и ближайших UI-компонентов выполняются адресно; статистические тесты не требуют точного Monte Carlo-значения. Исторические панели старого score не объявляются baseline нового score. Их индексы/данные не используются для подбора новой objective.

## Фактическая проверка

```powershell
$env:PYTHONPATH='src;.'
.venv/Scripts/python.exe -m unittest tests.unit.test_dynamic_joint_targets tests.unit.test_proposal_schedule tests.unit.test_directed_count_proposals tests.unit.test_dynamic_encounter_progress tests.integration.test_dynamic_encounter -q
.venv/Scripts/python.exe -m unittest tests.integration.test_dynamic_encounter_json tests.unit.test_dynamic_benchmark -q
.venv/Scripts/python.exe -m unittest tests.integration.test_dynamic_process_json.DynamicProcessJsonSmokeTests.test_spawn_matches_sequential_result_and_preserves_source_echo -v
.venv/Scripts/python.exe -m unittest tests.integration.test_local_ui tests.integration.test_local_ui_browser -v
```

- Core45OK/10.615s (`core-validation.log`), включая9новых deterministic joint tests: границы/float coherence, minimax/sum/stability, unsupported и match только validation.
- JSON/CLI/harness34OK/26.715s (`json-validation.log`). После добавления sum-outcomes/source-goal guards повторён затронутый metadata-forgery test:1OK/4.836s (`metadata-validation.log`). Проверяются обязательные criteria/assessment, ложные статусы/errors/overall/selected, accounting и NaN без пересимуляции.
- Representative real spawn/sequential equality1OK/2.874s (`process-validation.log`); полная повторная module/console×backend матрица не нужна.
- HTTP/UI15OK в составном запуске16tests; единственная browser-проверка осталась `running` на старом async granular-file import, без JS failure. Новые joint checks к этому моменту пройдены. Повторён только этот browser без изменения кода:1OK/12.224s (`browser-validation.log`). Это составная проверка, не один зелёный16-test UI run.
- Независимое read-only ревью подтвердило общий score/validator/metadata и отсутствие certificate claims; UI реализован независимым агентом в отдельных файлах, интеграция/проверки выполнены главным. Общий UI layout/card/JSON не менялся. Diff/ссылки проверены.

Логи — `.cache/joint-targets-2026-11-18/`; игровой kernel/книжные источники/dependencies/entry points прежние. Схемы продолжают поставляться прежним wildcard; выполнены source/offline JSON checks, wheel не нужен. Full regression и большая MC-серия не запускались без отдельного риска; это не заявление о полном покрытии каталога/статистическом выигрыше на любых партиях.

Реализация завершена до публичного UI/JSON результата. Следующий шаг — один ограниченный контроль нового joint-objective на реальных партиях с раздельными метриками: посещено ли совместно подходящее приближение, попало ли оно в validation, сохранило ли обе цели после неё. Формальное подтверждение вероятности/длительности и автоматический precision-план отдельно не согласованы; признанные проблемы allocation не устранены самой заменой score. Повторять старые известные seeds ради подбора objective не нужно, fresh505сохранён для следующего протокола.
