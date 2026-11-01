# Текущий статус проекта

Дата обновления: 2026-11-01.

## Текущий этап

**M8 / ADR-0051: контракт и finite proof проверены.** [Контракт](decisions/ADR-0051-stationary-wound-generation-and-magic-json-v3.md), [probe](examples/m8/stationary_wound_transport_contract_probe.py)/[stdout](examples/m8/stationary_wound_transport_contract_probe.output.txt), [отчёт](audits/m8-stationary-wound-transport-contract.md). Production propagation ещё не реализована.

Контракт задаёт независимую append-last stationary family assertion, strict enum/equality до enumeration и полную subset/source projection. Будущий JSON v3 обеих magic families получает required nullable enum string и отдельный matching balance family field; прежний Miscast nullable object остаётся независимым. Error trust/fallback и fresh-only scope прежние.

## Ограничения

- Native [ADR-0050](decisions/ADR-0050-native-stationary-wound-policy.md) закрыт [аудитом](audits/m8-native-stationary-wound-readiness.md): canonical first9 stand/context49, superficial1–3 и active/expired6, normal Tests, no external causes. Terrain/history сохраняются; Give Ground=False.
- None сохраняет legacy traces/stops. Повторная9 после stand, Wind Prone с retained terrain, другие wounds/Miscasts и unknown scene facts дают конкретный stop. Miscast и stationary permissions независимы.
- Production generation и JSON1/2 явно отвергают stationary policy. V3 пока unsupported: ручной finite mapping не является parser/schema/CLI или save/resume.
- M8 — authored Champion-Wizard/Curse + Shooting Minions; unsupported в denominator. Полный suite имеет33 прежние errors expectations Python3.12 и не считается зелёным.

## Последняя проверка

Windows/CPython3.12.4 вне sandbox: **3902tests /33known errors /0failures /0skipped,971,355с**. Все33 exact ERROR headers совпали с предыдущим baseline; новых errors/failures нет. Log `.cache/adr0051-contract-regression.log`.

Новый copied-bundle test прошёл отдельно и в full suite:20 ручных full-source subsets,16 finite wire mappings,4 настоящих staged rows;8 scripted trials/138d10 и same-ID source substitution controls. Inputs/global RNG неизменны. Source/installed/spawn аудит ADR-0050 остаётся действующим; новый wheel для contract-only среза не собирался. Saved v2 outputs и Markdown-пути проверены; `git diff --check` — OK.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

## Точный следующий шаг

Пункт1 ADR-0051 целиком: native generation model/preflight/projection/result guards и deterministic source/None/forged-input tests, затем generated stationary chain через staged sequential/spawn. До enumeration проверять typed template/family; до equality также typed candidate. Полный source сохранять в generation→staged→report.

После пункта1: simulation3 → balance3 → общий installed/schema/CLI/spawn audit и full regression. Не удалять policy ради старого encoder, не вводить gameplay consumers/save-resume под видом transport.

Все прежние незакоммиченные изменения сохранены. В текущем срезе добавлены ADR/probe/stdout/copied test и отчёт, обновлены навигация/архитектура/roadmap/открытые вопросы; production и старые tests/fixtures не менялись. Commit/push выполняет пользователь.
