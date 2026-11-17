# Независимая финальная оценка с планированием точности

Дата:2026-11-18. Developer-only продолжение [стенда allocation](search-allocation-2026-11-18.md). Игровой source/public JSON/UI/score не меняются. Цель — проверить явное распределение ограниченного ресурса между поиском и независимой fixed-n confirmation, вместо32прогонов при любом бюджете.

## Протокол до панели

Две процедуры при одинаковых work caps и одинаковых candidate/observation tapes: прежняя uniform-search + CS32 и uniform-search + fixed precision. Стратегия uniform выбрана до новой панели, racing index не перенастраивается. Меняются allocation search/confirmation **и** вид final bounds; это сравнение протокола целиком, не причинный эффект одной формы интервала.

Панель: те же8fixtures/32варианта,64seed indices0–63; budgets112/256/512/**1024**, pools6/12/24,2procedures —12288поисков. Между policy/budget/pool общие paired tapes, а между explore/confirm независимые streams. Корреляцию результатов учитывать; это64повтора на ячейку, не12288независимых подтверждений. Исследовательские цели/допуски прежние:50%/5раундов, win band±10п.п., round band±1. Продуктовые defaults/совместная objective не выбираются.

## План ресурса, фиксируемый до final outcomes

Запрос precision `epsilon=.10`, alpha=.05. Это требование к радиусу оценки при полностью наблюдаемых исходах, не мощность теста и не обещание сертификата попадания в win band.

1. До поиска mcap=min(2,K). Требуемый conservative размер на финалиста `n_req(m)=ceil(log(2m/alpha)/(2*epsilon²))`. При m2это220, при m1—185.
2. Минимальный search —4наблюдения каждого arm с объявленной стоимостью. Cost — фиксированные условные единицы стенда, не ETA игры.
3. `n_reserved=min(n_req(mcap),floor((B−search_min)/(mcap*max_cost_pool)))`; escrow=`n_reserved*mcap*max_cost_pool`. При n_reserved<1явная ошибка недостаточного бюджета **до** первого наблюдения. Остаток B−escrow используется прежним uniform-search.
4. После screening фиксируются до2eligible finalist IDs. При actual m/costs пересчитываются n_req и `n=min(n_req,escrow/sum_finalist_costs)` с округлением вниз. Это может использовать свободную ёмкость escrow, но выполняется **до** открытия final tapes. При m0нет ни выборки, ни заявления о точности.
5. Все выбранные mполучают ровно nfresh trials, включая случай обнаруженного unknown. IDs/m/n/alpha не меняются после final outcomes. Неиспользованный escrow не возвращается search задним числом. Повторное ранжирование поддержанных финалистов прежнее; новые поля имеют только developer artifacts.

Примеры cost1: B112/pool6→search24+2×44final; B256/pool6→search24+2×116; B512/pool6→search72+2×220. B112/pool24→search96+2×8final, поэтому ширина может съесть доступную точность. Такой результат явно диагностируется; схема не объявляется оптимальным выбором split или pool.

Если n<n_req, показываются `n_requested/n_reserved/n` и `nominal_half_width=sqrt(log(2m/alpha)/(2n))`. Это консервативная граница для fully observed Bernoulli, не attained power. Фактическая ширина interval измеряется отдельно; она может быть меньше bound. При unknown интервал дополнительно охватывает необъяснённые исходы. Попадание вероятности в полосу и требуемая точность — отдельные метрики.

## Fixed-n bounds и область гарантии

Для q=s/n инвертируется `n*D(q||p)<=log(1/tail_alpha)`, где D — Bernoulli KL. Lower/upper вычисляются outward bisection в log-space; s0/s=n и n0обрабатываются явно. Каждая односторонняя ошибка≤tail_alpha при заранее фиксированном n. Это fixed-sample Chernoff bound, не anytime-CS. [Howard и соавторы, различие pointwise/sequential bounds](https://arxiv.org/html/1810.08240v9).

На финальной стадии tail_alpha=alpha/(2m). Для unknown по-прежнему Y=confirmed win, Z=win или unknown: lower для Y, upper для Z. Условно на screening выбранные m/nфиксированы, fresh samples независимы, поэтому union bound относится к этим mи двум сторонам. mвыбирается до unknown exclusions и не уменьшается по результатам. Final guarantee не зависит от правильности search CS; совместной гарантии search+final при одном alpha не объявляется. Каждый этап маркируется отдельно.

Pinsker/Hoeffding даёт радиус≤sqrt(log(2m/alpha)/(2n)) вокруг соответствующих empirical endpoints; при unknown ширина может доходить до unknown_fraction+2radius. n_reqпланирует precision, а не вероятность сертифицировать любой true pвнутри полосы. При epsilonравном половине win bandместо для случайного сдвига среднего мало; на границе полосы высокая power не обещается. После просмотра final outcomes добавление/остановка потребуют другого заранее определённого sequential протокола.

## Проверки и интерпретация

Детерминированные проверки: closed-form KL endpoints; точное суммирование биномиальных вероятностей каждой tail error при фиксированном n; радиус для всех s0…220; unknown bounds; budget degradation/variable costs; заморозка m/nдо first final draw; сохранение m/nпосле unknown; m0/no precision; ошибка недостаточного бюджета до oracle; прежние18checks и новый harness smoke. Legacy CS32parity сравнивается с сохранённой предыдущей панелью без игровых боёв.

Report включает старые coverage/hit/regret/resource metrics, final interval coverage/ширину и её denominator, размер final plan, requested precision feasibility, observed precision, win-band certificates. Missing/unsafe сохраняются с прежней безусловной penalty, не исключаются из среднего. Guarantee coverage и качество allocation рассматриваются отдельно. Panel index/formulas/fixtures после результата не перенастраивать; автоматического основания для production-внедрения или игровой MC-серии нет.

```powershell
$env:PYTHONPATH='src;.'
.venv/Scripts/python.exe -m unittest tests.unit.test_confirmation_planning tests.unit.test_search_allocation -q
.venv/Scripts/python.exe -u tools/benchmark_confirmation_planning.py --output .cache/confirmation-planning-2026-11-18/panel.json
```

Hash tools/game, frozen protocol/snapshots, полный artifact и результаты адресной проверки сохраняются в `.cache/confirmation-planning-2026-11-18/`; переносимые результаты будут ниже. Full/wheel/игровые regression не требуются для developer-only изменений.

## Проверка и замороженный результат

31адресный тест прошёл за0.604s (`unit-validation.log`). До панели независимое read-only ревью проверило формулы/reserve/holdout. Сохранённые72uniform-CS32строки seed0по всем прежним budgets/pools совпали по всем прежним метрикам с первой панелью (`legacy-parity.json`). Это проверка нейтральности legacy path, не новый игровой baseline.

Завершены все12288искусственных поисков за10.050s;6,223,348учтённых наблюдений с paired reuse. Проверены уникальность/точное покрытие всей матрицы, work caps/unused reserve, полная экспозиция пула, frozen m/n и final denominator `sum(search_n)+m*n`. Источники после freeze не менялись. Игровой hash прежний `1beb53fc42061ebe2ea88db2f6351096acfde6a5167dbccfc7dff9368064bdae`, hash трёх tools `bc941edbb894e288e7e75f3b36936ce291b3293ca3da43c24fa7e370d4507ebf`. Artifacts/protocol/snapshots/log/verification — `.cache/confirmation-planning-2026-11-18/`. Числа независимо сверены read-only без повторения панели.

## Точность стала явным результатом плана

На budget512/pool6и12, а также1024при всех pool, все512из512запусков каждой ячейки смогли выделить nominal precision±10п.п.; все selected intervals также имеют ширину≤20п.п. Это8задач×64повтора, не512независимых игровых подтверждений. На меньших budgets метод честно сообщает, что conservative n_reqне достигнут. Например112/pool6: n44вместо220, nominal bound≈22.3п.п.;256/pool6: n116, bound≈13.7п.п.

При512/pool24не все получили n208: variable-cost освобождает escrow, поэтому встречаются208и220. Nominal request выполнен в64/512запусков, observed selected width≤20п.п. — в263/512. Фактический interval может быть уже conservative bound, особенно при pблизком к0/1; budget-limited не равнозначен математическому запрету сертификата.

Получено106win-band certificates против0CS32. На этой панели нет certificate с истинным win-hit=false, но это не доказывает coverage theorem по эксперименту. Максимум final-family violations2/64на ячейку у нового метода; theoretical guarantee относится к frozen final family отдельного поиска. Суммы/повторы разных budgets/pools коррелированы. Оценка pне удостоверяет отсутствие будущих unknown, длительность или качество найденного состава.

## Качество выбора: весь парный результат

Все12комбинаций budget/pool ниже. Равный вес восьми искусственных задач;512пар в строке. Delta penalized win error — fixed precision−CS32 в процентных пунктах, отрицательное лучше. Hit delta относится к описательному win band. Feasible — число выполненных conservative precision requests, certificates — число включённых в win band final intervals новой процедуры.

| Budget scale | Pool | Delta error, п.п. | Delta win hits | Feasible /512 | Certificates |
| --- | --- | --- | --- | --- | --- |
|112|6|+2.047|−25|0|0|
|112|12|+0.023|0|0|0|
|112|24|−2.571|+23|0|0|
|256|6|+2.720|−40|4|0|
|256|12|+3.594|−58|4|0|
|256|24|+2.962|−45|4|0|
|512|6|+0.001|−6|512|15|
|512|12|+2.541|−48|512|16|
|512|24|+4.497|−73|64|2|
|1024|6|−0.502|+11|512|23|
|1024|12|−0.478|+7|512|22|
|1024|24|−0.368|+8|512|28|

Финальный бюджет улучшил точность, но отнял ресурс у поиска. В narrow512/pool24coverage45/64у обеих процедур; CS32выбрал цель45/64, fixed precision25/64. Search уменьшился448→96наблюдений, confirmation увеличилась64→416(n208на финалиста). Средняя ширина выбранного interval уменьшилась примерно.591→.152, но точнее оценивается уже плохо выбранный вариант. Это провал отбора при равном coverage; узкий interval сам по себе не означает хороший бой.

При1024search и final precision помещаются вместе, и описательное среднее новой процедуры немного лучше при всех pool. Это не доказательство общего преимущества: один synthetic development panel, без fresh игровых данных, и сравнивается весь protocol. Ни одна ячейка не выбиралась основанием для нового default.

## Unknown и пределы вывода

Missing recommendations:0у нового метода против3уCS32; все сохранены в безусловных penalty averages. Один выбранный вариант имеет ненулевую истинную частоту unknown, хотя наблюдаемых unknown не было: informative_unknown/seed63/budget112/pool24, arm:08, n8, **без** win-band certificate. Это показывает, что отсутствие замеченного unknown в малой выборке не доказывает отсутствие риска. m2иalpha после результатов не пересчитывались; Y/Z full-probability bounds сохранены.

Fixed-n формулы/планировщик принимаются как developer-инструмент. Агрессивное резервирование под n_reqне принято в игровой генератор: качество отбора на ограниченном ресурсе ухудшается. Выбранная epsilonзадаёт радиус, не power сертификата; особенно при истинной pна границе целевой полосы. Истина unknown/полная длительность не восстанавливаются статистикой из остановленного prefix. Игровой поиск, public fields, score и допуски прежние; новых игровых MCпрогонов/full/wheel не было.

## Следующий шаг

Перед production-интеграцией согласовать смысл подходящего боя: нынешний жёсткий приоритет доли побед либо одновременное попадание в допуски побед/длительности. Отдельно различать «лучший найденный с оценкой неопределённости» и «подтверждённое попадание в полосу». Эти продуктовые решения не подставляются из toy fixtures. Затем подготовить один конкретный протокол совместного планирования ширины поиска и финальной точности с явным недостатком бюджета, не подбирать index/reserve по увиденной таблице.
