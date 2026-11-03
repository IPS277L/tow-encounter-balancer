# Приёмка Battered Leg generation и JSON6, ADR-0062

Дата: 2026-11-03. Статус: **ADR-0062 завершён; regression закрыт составно, финальный installed audit пройден**.

[Контракт](../decisions/ADR-0062-battered-leg-generation-and-magic-json-v6.md) передаёт существующий native61 consumer без изменения его injury/phase scope. Нормативные источники наследуются: PG1.4 Characteristics/Skills68–70, Wounds/Conditions121/123, Wounds Table190/5; GM1.1 Champions92. Нового чтения книги, версии/hash, Rule ID или house rule нет.

## Что реализовано

Append-last family field `MagicCandidateGenerationRequest.battered_leg_continuation` сохраняет полный authored Endurance profile. Permissions/facts-only arithmetic preflight проверяет original policy/profile и точное matching до collections/equality. Factory/result отдельно проверяют полный source/subsets, все candidate profiles до vectors/projection и исходный derived cache до пересоздания. Проекция явно передаёт family policy. Прежние counts/C, actors/frames/definitions/objectives, seeds, budgets, ranking и denominator сохраняются.

JSON6 использует required nullable `{"endurance_profile":{"dice":2,"threshold":5}}` в Scenario/reserve/family. Dice strict integer≥1 без нового maximum10, threshold1..10, без cap/дополнительных полей. Все пять permissions сохраняются; repeated по-прежнему требует stationary. Balance matching сравнивает целый profile и сообщает `/generation/battered_leg_continuation` при isolated mismatch. None6 остаётся6; default1 прежний. Старые1–5 отказывают новому key дажеnull и nonNone при encoding до projection.

Известная6 сохраняет version/request_id на shape/semantic/phase errors; lexical failures дают прежний fallback1/null, неизвестная7 остаётся неизвестной. Generic MagicInputError1/2 и legacy magic_v2 не расширены. Result echo, cached requests и typed phase errors проверены без replay trials в encoders.

Native61 domain/engine не менялись. First5/sourced Prone и scope stops60/61 прежние; treatment/healing, mixed injuries, Prone5 removal и save/resume не добавлены.

## Целевые проверки и review

- Generation:9new unit +5actual integrations прошли;47existing generation checks также прошли. Actual3/4actors, полный5actor Wizard-opposite, sequential/realspawn stages, late valid-profile/raw cache corruption и arithmetic/source разделение.
- Schemas:10new +32existing schema checks OK,26.092s. Измерено **54package/36magic schemas,573bundled refs, cache36**; offline lookup всех refs, own closed Scenario6 без allOf закрытогоScenario5.
- Wire:14new unit OK,7.982s, и9integration OK,48.524s. Обе families module/console×sequential/process, exact source/report echo, обе perspectives, None6, lexical/error identity/privacy, malformed profile до backend и late cache checks.
- 112affected legacy JSON behavior checks OK,43.278s. Прежние unknown-version sentinels обновлены6→7; предыдущие APIs не расширены за пределы нового magic6.
- [Production public proof239d10](../examples/m8/battered_leg_transport_contract_probe.py), [stdout](../examples/m8/battered_leg_transport_contract_probe.output.txt), [copied test](../../tests/integration/test_m8_battered_leg_transport_contract_probe.py):1test OK,25.558s.98production JSON6 parses/full echoes и97matching-profile candidates сверены с независимым manual oracle,5genuine None controls сохранены. Native61 success/failure/normal1d5/full-five и sequential/realspawn сохраняют полные sources/seeds/denominator2. Дополнительный seeded balance2trials и simulation summary/result echo проверены отдельно от239scripted draws.

Independent review разделено по generation/source/cache и schemas/wire/error boundaries; production blockers не выявлены. Изменения старых field-order/unknown-version tests сделаны до full regression.

## Публичные requests

[Simulation6](../examples/m8/json/magic-simulation-v6.request.json) и [Balance6](../examples/m8/json/magic-balance-v6.request.json) сформированы production mapper и проверены production parser на exact command equality. Профиль2d/5 и остальные четыре permissions явно заданы/null, family assertion независим. Для других backends execution задаётся в request; runtime не меняет seed/budget/source.

## Full/installed граница

Полный набор через project Python3.12 с actual tempfile/subprocess/spawn: **4340tests за1519.165s,4339passed/0failures/1ERROR/0skipped**; ignored log `.adr62-full.log`. Единственный ERROR — старый copied ADR54 transport probe, где schema_version6 использовалась как неизвестная. Sentinel и saved stdout исправлены на7, затем ровно этот test повторён: **1test OK,5.437s**, `.adr62-recheck.log`. Сопоставлены все4340test IDs: каждый закрыт успешной проверкой. Это составной результат; исходный full не объявляется зелёным. Предыдущий4292composite61 не подменяет текущую проверку.

Offline wheels62 собраны без сети через `tools/prepare_m8_transport_audit.ps1` с локальным setuptools dependency wheel; pip check OK. **495 Python/JSON files** source/wheel/installed совпали по путям/SHA-256.54schemas/573refs разрешились из установленного пакета offline. PDF/references в wheel нет. Initial wheel до help fix: `1b802e07e951b25b5a827e33395aeeca8887c3e912f0010164c35e0a5e83e8b9`. **Финальный wheel:** `9cec952654676cbd022154c3b7a25db08b70f6b408b1eb956679e78bdced8051`.

Copied installed47new tests прошли одним run через `python -I`: **47tests OK**,144.230s, включая real spawn и CLI. На финальном wheel повторены9wire integrations и добавлены обновлённый help test/исправленный исторический ADR54 probe: **11tests OK,49.657s**. Это два отдельных run, не единый final47 run.

Финальный production public proof239d10 на installed -I дал exact saved stdout. Оба настоящих JSON6 requests выполнились в8комбинациях module/console×sequential/process; exact request echo, aggregate/report equality и пустой stderr подтверждены без PYTHONPATH/source imports. Проверены495production hashes и локальные Markdown targets. Локальные manifests/logs находятся в ignored `.cache/adr0062-final-installed-audit/checks/`; воспроизводимые requests/proof/tests и этот отчёт находятся в репозитории.

Поздняя проверка нашла два старых help-описания CLI с перечнем1–5. Они обновлены до1–6; точечный source test справки прошёл1/1,1.162s. Сравнение initial/final wheel выявило единственный изменённый production file `towr/cli.py`: после нормализации ровно двух help keyword literals AST идентичны. Контрольный поток/аргументы/симуляция не менялись. Full run уже содержал предыдущий help-test; финальный wheel, новый help и CLI проверены отдельно. Весь full не перезапускался ради двух строк справки; это дополнение к общей проверке, не новый full финального tree.

Следующий шаг — отдельный контракт sourced Prone5 removal с адресной сверкой Free Actions/Prone. Существующие ограничения61/60 и native refusal после новых injuries не ослаблены.
