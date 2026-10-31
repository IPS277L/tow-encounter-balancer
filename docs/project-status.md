# Текущий статус проекта

Дата обновления: 2026-10-31.

## Текущий этап

**M8 / ADR-0047 этап2: simulation JSON v2 реализован и проверен.** [Контракт](decisions/ADR-0047-opt-in-generation-and-magic-json-v2.md), [аудит simulation v2](audits/m8-simulation-v2-readiness.md), [публичный JSON-вход](examples/m8/json/magic-simulation-v2.request.json). Native opt-in generation этапа1 готов; [его аудит](audits/m8-opt-in-generation-readiness.md). Balance v2 пока не реализован.

Прежний `simulate-magic INPUT` принимает1/2. V2 требует `scenario.miscast_continuation`: null либо полную explicit policy; command/result/error сохраняют версию. До complete strict lexical decode ошибки используют fallback1 и null request ID; после распознанной2 —2. Runtime service использует версию своего command, не cause. Полный source/command reconstruct-check не допускает потери policy. Три новые local schemas; старые шесть magic v1 schemas неизменны. Остальные семь CLI routes пока толькоv1.

[Public proof](examples/m8/opt_in_transport_contract_probe.py) использует настоящий opted generator и simulation v2 parser/runner/encoder; только balance v2 portion ещё ручной. V1 запрещает policy field даже null и отказывает native opted source. Shared balance input error с explicit2 временно отклоняется encoder, не понижается молча до1.

## Готовность и ограничения

- PG1.4/GM1.1 — primary; [источники](source-index.md), [трассировка](rule-traceability.md), [открытые вопросы](open-questions.md). Этап2 меняет transport, не боевые правила; domain/engine/rules/simulation и seed scheme прежние.
- M2–M7 закрыты для ограниченных numeric Minion scenarios. M8 остаётся authored Champion-Wizard/Curse + Shooting Minions, не универсальным боем.
- [ADR-0046](audits/m8-opt-in-miscast-readiness.md) обслуживает preparation → один roll → Wind21–22 с full journal witness и scoped Prone stand/end/Casting/Shooting/safe Broken Recover. Other-row сохраняет Pool/pending/MISCAST_EFFECT. None сохраняет прежние traces/IDs/draws/stops.
- Не добавлены desperate cast, abandonment, другие Miscast consumers, ongoing Prone Wounds, unsafe Broken escape, Run-after-spent-free-move, standard Recover fallback или помощь союзника. Fresh-only input не является сохранением/возобновлением боя.
- Scene/GM facts всегда explicit. Unsupported остаётся в denominator; aggregate eligibility не доказывает полноту тактики. Generated family требует отдельную matching template policy; удалённые резервисты отсутствуют в subset, не становятся external Short bystanders.
- Предыдущий installed audit ADR-0046 — исторический. Текущие generation/simulation-v2 изменения ещё не проверялись в новом wheel; общий source/wheel/installed audit предусмотрен этапом4. Performance/cross-platform claims нет.
- HEAD `b7d0a59 M8 P16`. Предыдущие пользовательские изменения сохранены; текущие code/tests/docs также не закоммичены. Commit/push выполняет пользователь.

## Следующий шаг

**Этап3 ADR-0047 целиком: balance JSON v2.** Ещё три schemas/local registry; append-only command/phase-error version metadata с defaultv1; required nullable policy в reserve и generation с exact equality; full generation/staged source chain; lossless parser/result/error encoders/service/CLI. Проверить separate assertion/mismatch pointer, candidate/counts/stage contexts, позднюю generation failure после успешного preflight, реальные sequential/process и v1/v2null parity. Заменить временный отказ balance encoder от metadata2 полноценным v2 error encoding; simulation v2 и шесть немагических families не ослаблять. Затем общий installed/full audit этапа4.

## Последняя проверка

**24 новых теста (18 unit +6 integration) прошли.** Focused: 85 смежных tests OK/19,455с, все6integration OK/31,844с, copied public proof1 OK/2,000с; новые unit прошли focused и full suite. Independent review блокеров не оставил. Sandbox WinError5/Pipe/temp-directory проверки повторены вне sandbox успешно. Точные команды/границы — в [аудите](audits/m8-simulation-v2-readiness.md).

**Полная регрессия: 3772 tests /33 известных errors /0 failures /0 skipped,651,243с**, Windows x64/CPython3.12.4, вне sandbox. Команда: `$env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest discover -s tests -v`; log `.cache/adr0047-simulation-v2-regression.log`. Все33 sorted error headers точно совпадают с baseline `.cache/adr0047-generation-regression.log`:16+16 K1 Aim-loss frozen/slotted TypeError и один M5 replace(init=False) ValueError. Новых ошибок нет; suite с errors не считается зелёным, исправление этих expectations — отдельная задача.

1172 local Markdown paths в12актуальных документах и `git diff --check` — OK. Старые шесть magic v1 schemas не изменены. Новый wheel/installed audit здесь не заявляется.

Коммиты и push не выполнялись. Локальные `.cache` logs/wheel/venv переносить не требуется.
