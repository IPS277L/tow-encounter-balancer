# Текущий статус проекта

Дата обновления: 2026-11-03.

## Текущий этап

**ADR-0058, шаг1 реализован: Crushed Rib generation family. JSON5 остаётся следующим шагом.** [Контракт и очередь](decisions/ADR-0058-crushed-rib-generation-and-magic-json-v5.md), [актуальный roadmap](roadmap.md).

Native57 закрыт: независимое разрешение, история первого consuming result из собственного prefix и mandatory pending/death priority. [Его приёмка](audits/m8-native-crushed-rib-readiness.md). MagicCandidateGenerationRequest теперь имеет append-last typed Crushed Rib family assertion; matching source проверяется до materialization/equality/enumeration, а projection сохраняет разрешение. Арифметический preflight остаётся без Scenario construction. GenerationResult и Balance command/report повторно проверяют original source/cache. Native механика не менялась; JSON1–4 losslessly отказывают выбранному разрешению.

## Последняя проверка

62целевых unit tests и12generation/wire/copy integration tests прошли. Включены12valid/4invalid, реальные generated3/4-actor сценарии, обе perspectives, sequential/process staged parity, JSON1–4 refusal и copied public bundle. Probe завершился успешно: exact stdout/empty stderr, SHA6source/copy bundle, original inputs/global RNG сохранены.647scripted d10 относятся к finite probe; seeded None balance отдельно, его draws не входят в647. Три application production files изменились; остальные475 из478 package files и старые101 public M8 examples совпадают с baseline57. Schema42 не менялась.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.integration.test_m8_crushed_rib_transport_contract_probe -v
```

Последняя полная runtime-проверка остаётся57:4201tests/1207,032с,33known errors/0failures/0skipped, все572integration прошли. Exact33ERROR headers совпали с56; весь набор не зелёный. [Исторический аудит57](audits/m8-native-crushed-rib-readiness.md) содержит installed478source/wheel/site paths,42schemas/444offline refs и12child commands. Для contract-only58 full/installed повторно не запускались;33старых Python3.12 expectation errors — отдельная задача.

## Ограничения

Native57 допускает одну canonical resolved/untreated/unhealed rolled10, optional prior superficial1–3 и только Drained; следующие Protection/Casting сохраняют первый полный witness. Несколько10,9/6/Wind coexistence, treatment/Fate/Lucky/Talents и другие Wizard Tests исключены.12valid/4invalid permission сочетания сохраняются, repeated требует stationary, Crushed Rib независим. JSON5 будет передавать fresh source permission, без current state/history/save-resume. Новых книжных правил/house rules нет.

## Точный следующий шаг

Начать шаг2 ADR-0058: simulation Magic JSON5 — собственные три schemas, mapper/type/version gates, command/error metadata, parser/encoder/service/CLI; simulation поддерживает1–5, balance остаётся1–4 на промежуточном этапе. Сохранить required nullable permissions, JSON1–4 lossless gates, default1, decoded request ID/error behavior и privacy. Затем выполнить шаг3 balance5 и единый installed/full audit на границе шага4; injury/phase scope57 не расширять.

Общие документы синхронизированы. Проверено1846local Markdown paths в16изменённых документах, broken0; diff/whitespace чистые (Git сообщает только LF→CRLF рекомендации для test fixtures).45незакоммиченных файлов,18untracked; новые ADR-0057/0058, native proofs и generation probe ещё не закоммичены. Scope evidence и ограничения зафиксированы в ADR и probe. Commit/push, `.gitignore` и книги не менялись.
