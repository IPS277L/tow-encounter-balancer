# ADR-0129: процессное исполнение trials динамического поиска

Дата: 2026-11-17. Статус: принят и реализован; пользователь выбрал автоматическое исполнение до четырёх процессов. Backend, JSON/CLI, UI, прогресс и отмена проверены.

## Основание

[Полные планы](../benchmarks/dynamic-full-auto-plan-2026-11-17.md) заняли11.79/16.05мин; практически всё время — симуляция и агрегация. На финалиста осталось47/49trials с широкими интервалами. На измеренной машине16логических CPU. Native `pc_melee_parallel` уже сохраняет источники/индексы/seeds, но его batch32, pool-per-call и отсутствие progress/кооперативной отмены не подходят для прямого включения UI.

## Принятый публичный контракт

Один текущий dynamic JSON1, два явных режима:

```json
{"execution":{"mode":"sequential"}}
```

```json
{"execution":{"mode":"process","workers":4}}
```

Для process workers — точное целое1–61, как у существующего `SimulationExecutionOptions`; bool не принимается. Объекты закрытые, sequential не принимает workers. Размер batch в первом срезе — внутренний1trial, новое публичное поле не добавляется. Ошибка запуска worker не вызывает скрытый fallback на sequential, повтор trial или частичный успешный отчёт.

`DynamicEncounterCommand` получает типизированные execution options, отдельно от фактов/целей `DynamicEncounterRequest`. Python search получает keyword `execution` для стандартного исполнителя; явный custom simulator и execution options одновременно не допускаются, чтобы не игнорировать заявленный режим. Source echo проверяет и execution. Developer harness должен реально исполнять заявленный режим, включая точные экспортированные запросы.

Default нового UI-запроса — min(4,max(1,CPU−1)) workers; process используется, если получилось хотя бы2, иначе sequential. Файлы с явным execution сохраняют свой выбор; ручной JSON позволяет другой workers/sequential. Новых UI-полей в первом срезе нет. Рассмотренные альтернативы: cap8 либо только явный opt-in через JSON с прежним sequential UI default.

## Исполнение и жизненный цикл

Один spawn-pool на поиск, повторно используемый screening/validation. Одновременно вычисляется только один фиксированный состав; следующий кандидат по-прежнему строится после его aggregate. В полёте не более2×workers задач; одна задача — один trial с прежним `seed_for(index)`. Records проверяются/сортируются по индексу; одинаковый план обязан давать те же фактические результаты в обоих режимах.

Progress публикует родительский процесс по полученным завершённым records, а не по максимальному номеру trial; все счётчики монотонны, каждый record учитывается один раз. Режим не меняет proposals, ranking, порядок actor/targets или правила.

Отмена: отдельный межпроцессный сигнал на поиск; родитель регулярно проверяет пользовательскую отмену, worker проверяет сигнал перед trial и перед бросками RNG. Проверки не расходуют случайные числа. После отмены новые задачи не выдаются, pending отменяются, running завершаются кооперативно; pool освобождается до acknowledgement/освобождения UI job. Старый сигнал не затрагивает следующий запуск. Ошибка worker остаётся execution error; отмена — отдельным cancellation outcome без partial result.

Механизм остаётся в simulation/application/adapters, без зависимости домена от multiprocessing/UI. Существующие source/proof guards не отключаются. Native API для других PC consumers продолжает использовать тот же действующий backend; compatibility-версии не добавляются.

HTTP `/api/cancel` отвечает202при принятии запроса на отмену; это ещё не подтверждение остановки workers. До окончательного `dynamic_encounter_cancelled` активный job остаётся занятым, повторный запуск отвергается. Финальный ответ генерации и освобождение lock происходят после cleanup.

## Планировщик и оценка времени

Сначала измерить process на **том же фиксированном плане** и проверить parity, затем калибровать общий UI cost model по фактическому throughput/startup overhead. Не делить время механически на workers. Ориентир750s и ручной override остаются; более высокий автоматический бюджет разрешается только после измеренного ускорения. Если автоплан из-за execution изменился, это новый полный вход; backend parity сравнивается при одинаковых counts/trials/seed.

## Конкретная приёмка

- Admission/closed schema: оба режима, strict workers, недопустимые поля/комбинации, source echo и текущие exports/examples.
- Native: реальные spawn-trials, source/seed/index/records parity, обратный порядок завершения, ограничение in-flight и reuse pool, worker failure без fallback/partial report.
- Отмена до первого trial, в выполняющемся worker/при ожидающих задачах, во время validation; отсутствие дальнейших бросков после обнаружения сигнала, освобождение pool и успешный следующий запуск.
- Сквозные JSON/CLI/UI: настоящий process-запуск, монотонный progress, Cancel acknowledgement/новый Run, ручной execution и auto default; representative melee/ranged/magic/potions interaction.
- Адресные simulation/service/adapters tests; установленную matrix не повторять для каждого профиля. Wheel только при packaging-риске. На fixed-composition и фиксированном full-search входе измерить actual wall time; full sequential baseline повторять только при влияющем изменении.

## Реализация

`simulation.pc_melee_process.PcMeleeProcessSession` владеет spawn-pool и сигналом отмены; one-shot `pc_melee_parallel` использует тот же backend. Application открывает одну сессию на весь поиск. До публикации callback проверяется весь возвращённый batch, включая полные source/seed/index; финальный результат упорядочен независимо от порядка завершения workers. Ошибка observer также закрывает pool. Отмена проверяется перед сериализацией/запуском и при каждом броске; ошибочный источник не исправляется.

UI использует общий `executionCostEstimate` для ETA и бюджета. Консервативные credits для2/3/4workers —1.25/1.9/2.5, startup одного pool —3s. Выше4workers дополнительное ускорение не предполагается. Последовательный план сохранён; новый process-план является другим полным входом и проверяется отдельно от backend parity.

## Результаты приёмки

Два полных прежних плана194/174trials ускорились в2.71/2.75×; полные отчёты совпали после нормализации только source_request.execution. Увеличенный автоматический план436trials занял14.94мин с encoding, но качество попадания в цель на этом seed не улучшилось: редкие unsupported исключили одного финалиста. Scheduler/source/CLI/browser/HTTP cancel→новый Run и representative native consumers проверены адресно; full regression/wheel не запускались. [Числа, команды и ограничения](../benchmarks/dynamic-process-execution-2026-11-17.md).
