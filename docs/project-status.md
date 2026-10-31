# Текущий статус проекта

Дата обновления: 2026-10-31.

## Текущий этап

**M8 / ADR-0047 этап3: balance JSON v2 реализован и проверен.** [Контракт](decisions/ADR-0047-opt-in-generation-and-magic-json-v2.md), [аудит balance v2](audits/m8-balance-v2-readiness.md), [публичный вход](examples/m8/json/magic-balance-v2.request.json). Native generation и [simulation v2](audits/m8-simulation-v2-readiness.md) готовы. Общий installed audit ещё не выполнен.

Обе magic CLI-команды принимают1/2, шесть nonmagic routes — только1. Balance v2 требует nullable policy отдельно в `reserve.scenario.miscast_continuation` и `generation.miscast_continuation`; полное равенство проверяется до generation preflight, mismatch pointer — `/generation/miscast_continuation`. Full generation/staged source chain, command/result/error version и phase context сохраняются. Временный отказ balance error2 заменён полноценным encoding2.

Все12 magic schemas доступны через local registry; старые шесть v1 schemas неизменны. До complete strict decode error1/requestIDnull, после распознанной2 — error2; runtime version берётся из command. V1 запрещает policy field даже null; v2null сохраняет legacy gameplay, но не понижает wire до1. [Public proof](examples/m8/opt_in_transport_contract_probe.py) использует настоящий generator и обе v2 families без temporary legacy views.

## Готовность и ограничения

- PG1.4/GM1.1 — primary; [источники](source-index.md), [трассировка](rule-traceability.md), [открытые вопросы](open-questions.md). Этап3 меняет transport, не правила; domain/engine/rules/simulation/balance и seed schemes прежние.
- M2–M7 закрыты для ограниченных numeric Minion scenarios. M8 — authored Champion-Wizard/Curse + Shooting Minions, не универсальный бой.
- [ADR-0046](audits/m8-opt-in-miscast-readiness.md) поддерживает opt-in preparation→один roll→Wind21–22 и scoped Prone; other-row сохраняет Pool/pending/MISCAST_EFFECT. None сохраняет прежние traces/IDs/draws/stops.
- Не добавлены desperate cast/abandonment, прочие Miscast consumers, ongoing Prone Wounds, unsafe Broken escape, Run-after-spent-free-move, standard Recover fallback или помощь союзника. Fresh-only input не является save/resume.
- Facts/GM decisions всегда explicit. Unsupported остаётся в denominator; eligibility не доказывает полноту тактики. Family policy подтверждается отдельно; удалённые reserve actors отсутствуют в subset, не становятся external Short bystanders.
- Source-only проверки этапов1–3 не заменяют новый source/wheel/installed audit. Предыдущий installed audit ADR-0046 — исторический. Performance/cross-platform claims нет.
- HEAD `39792f6 M8 P17`, рабочая копия перед этапом3 была чистой. Текущие code/tests/docs не закоммичены; commit/push выполняет пользователь.

## Следующий шаг

**Этап4 ADR-0047, общий аудит:** field/guard matrix; свежий wheel/offline install и exact source/wheel/installed parity; все12 magic schemas/local refs; public stored v2 simulation/balance outputs и copied examples; installed module/console для двух magic и шести прежних CLI routes; dependency/runtime context и full regression с отдельным учётом known errors. Не повторять успешные source-only проверки без новых изменений/риска, не расширять gameplay и не объявлять весь ADR закрытым до завершения installed evidence.

## Последняя проверка

**24 новых tests прошли:**18unit OK/14,533с (уточнённая geometry fixture отдельно OK/0,393с),6integration OK/46,373с вне sandbox. 78 смежных unit OK/17,767с; copied public proof1 OK/2,873с. Independent review блокеров не выявил. Команды и границы — в [аудите](audits/m8-balance-v2-readiness.md).

**Полная регрессия: 3796 tests /33 известных errors /0 failures /0 skipped,766,473с**, Windows x64/CPython3.12.4, вне sandbox. Команда: `$env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest discover -s tests -v`; log `.cache/adr0047-balance-v2-regression.log`. Все33 sorted error headers точно совпали с `.cache/adr0047-simulation-v2-regression.log`:16+16 K1 Aim-loss frozen/slotted TypeError и один M5 replace(init=False) ValueError. Все24новых tests прошли; новых ошибок нет. Suite с errors не считается зелёным; исправление expectations — отдельная задача.

1199 local Markdown paths в13актуальных документах и `git diff --check` — OK. V1 schemas не изменены. Source-only проверки не объявляются installed readiness.

Коммиты и push не выполнялись. Локальные `.cache` logs/wheel/venv переносить не требуется.
