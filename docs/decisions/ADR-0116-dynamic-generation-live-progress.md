# ADR-0116: краткий прогресс динамической генерации

Дата: 2026-11-15. Статус: реализовано по запросу пользователя.

## Решение

Вместо полного журнала боя показываются текущий этап, номер состава/финалиста, фактически завершённые симуляции, наблюдаемые победы и последняя завершённая оценка. История событий не копится. Итоговый результат, его source/seed и игровые JSON families не меняются.

`run_pc_melee_simulation(..., on_trial_complete=None)` уведомляет наблюдателя после каждого завершённого immutable trial record. `search_dynamic_encounter(..., on_progress=None)` создаёт frozen `DynamicEncounterProgress`: generating, simulating, candidate_complete, selecting, complete; exploration и validation различаются. Счётчики текущего состава сбрасываются при переходе, общий completed count монотонен. Победы считаются по actual OBJECTIVE_ACHIEVED, unsupported отдельно, denominator включает все завершённые trials. Прогресс не читает чужие будущие броски, не расходует RNG и не выбирает игровые действия.

Default simulator даёт per-trial updates. Внешний injected simulator сохраняет прежнюю сигнатуру и сообщает только границы кандидатов; не имитируются отсутствующие промежуточные данные. Exceptions callback прекращают работу; cancellation checkpoints стоят до/после публикации. Это callback-наблюдение, не новая шина игровых событий.

## Доставка в UI

Выбран polling примерно раз в секунду через loopback GET `/api/progress` с существующим `X-TOWR-Run-ID`. SSE/WebSocket не нужны для небольшой сводки. Server хранит только current и last_candidate под state lock, sequence и текущий token; source/battle logs не отправляются. После завершения/отмены состояние освобождается. Ранний запрос до регистрации POST возвращает waiting, чужой active token —409, malformed token —400; origin/host guards прежние.

Client не перекрывает polling-запросы в обычном цикле. Run token/sequence и busy guards отвергают старые ответы. Окончание POST останавливает timer и abort текущего GET; отмена генерации по-прежнему кооперативна на сервере. Сбой status GET не отменяет расчёт. Прогресс обновляет отдельный компактный блок, не перерисовывает source/cards и не делает auto Run.

Промежуточный процент отмечен как предварительный. При завершении используются actual selected validation outcomes из финального отчёта, не последний возможный устаревший poll. При отсутствии рекомендаций процент не придумывается. Success bar завершается по фактическому total, исходный budget upper bound указан отдельно: поиск может закончиться раньше плана. Cancel/error очищают per-candidate estimates, сохраняя лишь подпись последнего наблюдавшегося общего count. Live progress не является partial encounter report.

## Проверка

Детерминированно: callback once/immutable/actual outcomes, finite search space, actual finalist count, stage resets, monotonic accounting, injected simulator boundary, cancellation before next trial, полный seeded result с/без observer. HTTP: настоящий completed trial виден во время работающего POST, bounded snapshot без source/log, token/origin guards, last assessment и cancellation/cleanup. Browser: polling/error/recovery/stale guards, validation reset, between-polls completion, no-finalists fallback и прежние seed/export/Run/Cancel сценарии. Общий simulation loop проверен ближайшими existing tests; full regression/wheel не нужны. Команды/результаты — в project-status.
