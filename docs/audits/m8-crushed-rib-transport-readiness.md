# Crushed Rib generation and Magic JSON v5: boundary audit ADR-0058

Дата: 2026-11-03. **ADR-0058 шаги1–4 завершены** в согласованной transport/native границе. [Контракт](../decisions/ADR-0058-crushed-rib-generation-and-magic-json-v5.md), [актуальный статус](../project-status.md).

## Реализация

- Generation family имеет отдельное typed Crushed Rib assertion; full template match и strict permission checks выполняются до collection materialization/enumeration. Политика передаётся в generated subsets без source normalization.
- `simulate-magic` и `balance-magic` принимают v1–v5. В v5 поле required-nullable; Balance reserve и generation несут независимые значения, которые обязаны совпадать до генерации.
- Добавлено по три request/result/error schema на family. Полный registry: 30 Magic schemas, 48 package schemas, 507 разрешённых локальных refs.
- JSON1–4 продолжают lossless refusal Crushed Rib permission даже при null. Неизвестная версия v6 сохраняет `unsupported_version`; старые integration expectations обновлены на v6.
- [Public v5 requests](../examples/m8/json/README.md), [finite production probe](../examples/m8/crushed_rib_transport_contract_probe.py) и обновлённый [ADR-0054 transport probe](../examples/m8/repeated_leg_spasm_transport_contract_probe.py) проверяют exact source, отказные gates и generation/native paths.

## Source/wheel/installed/CLI

Свежая сборка использовала отдельную копию package metadata/README/LICENSE/src. Offline wheel собран и установлен в новый временный venv; `pip check` прошёл. Установленный Python запускался с `-I`, без `PYTHONPATH` и user site.

- Source/wheel/installed byte parity: **484 Python/JSON files**.
- Wheel SHA-256: `3393a637ae6a2290090cc28d24d93448f099a7e091bcd5729e5a9a18e5fc07ed`.
- Packaged schema closure: **48 schemas / 30 Magic / 507 local refs**.
- Simulation v5 и Balance v5: sequential/process source CLI, isolated module CLI и installed console script дали **12 точных сравнений**. Полный request echo совпал с отправленным request.
- Public copied Crushed Rib bundle прошёл exact stdout check. Обновлённый ADR-0054 probe также прошёл после замены unknown v5 на unknown v6.

Временные build/evidence файлы находятся вне репозитория в `%TEMP%`; они не являются runtime-зависимостью. PDF/`references/` в wheel не включались.

## Полная регрессия

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Результат: **4223 tests in 1057.176s; 33 errors, 0 failures, 0 skipped**. Точное число совпало с ADR-0057 baseline (4201 tests, 33 errors). Ошибки те же известные Python 3.12 expectations: 32 subcase errors из присваивания в frozen/slotted `.state` и один M5 `replace(init=False simulation_requests)` ожидал другой тип исключения. Все integration tests завершились успешно; новый error, который показал устаревший ADR-0054 unknown-v5 probe, устранён и перепроверен.

Итоговый Markdown link check: **189 файлов / 4615 локальных ссылок / 0 отсутствующих путей**. Набор из 4223 tests не называется полностью зелёным из-за baseline errors.

Commit/push не выполнялись. Пользовательские PDF, `.gitignore` и книжные материалы не менялись.
