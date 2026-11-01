# M8: контракт stationary family / Magic JSON v3

Дата: 2026-11-01. Проверяется проектирование [ADR-0051](../decisions/ADR-0051-stationary-wound-generation-and-magic-json-v3.md) и конечное ручное отображение. **Production generation/v3 schemas/parser/CLI ещё не реализованы.** Основа — закрытый [native ADR-0050 audit](m8-native-stationary-wound-readiness.md).

[Probe](../examples/m8/stationary_wound_transport_contract_probe.py), [сохранённый stdout](../examples/m8/stationary_wound_transport_contract_probe.output.txt), [copied-bundle test](../../tests/integration/test_m8_stationary_wound_transport_contract_probe.py).

**Последующий пункт1 реализован:** [native generation audit](m8-stationary-wound-generation-readiness.md). Текущий probe теперь вызывает production opted generator и family preflight, сравнивает20full projections с manual project, восстанавливает полноценный typed generation request. Ручным остаётся только finite wire3 mapping; старые wire отказы сохраняются. Ниже — первоначальная контрактная evidence до реализации, а не актуальный implementation report.

## Что проверено

| Граница | Конечная evidence / ограничение |
| --- | --- |
| Независимые permissions | Четыре сочетания None/opted Miscast и stationary. Отдельные finite assertions template/family до projection; mismatch и raw-string template/family отвергаются этими assertions. Это ещё не production generation preflight |
| Полные subsets | 4 friendly prefix-count vectors и1 opposite vector ×4 сочетания =20 ручных projections. Полное equality с исходными legacy projections плюс явно сохранённые обе policies; ordered roster/scenes/IDs и indexed seeds совпадают |
| Полное proposed wire | 2 perspectives ×4 сочетания ×2 families =16 finite JSON round-trips. Проверяется весь baseline document и required nullable fields. Balance reconstruction сохраняет весь прежний generation request и отдельно полный новый template/family permission; будущий typed family model не подменён фиктивным production объектом |
| Существующий staged source chain | Public native staged service исполняет4 явно сформированных manual candidates,1stage,4полные source-bound rows. Это evaluation явного списка, не вызов opted composition generator |
| Существующий native runtime | 8 scripted trials /138 d10: actual9/stand/6 continuation при permission и None controls, исход round_limit/unsupported. Denominator2 на источник, unsupported rate1/2 или1; это finite outcomes, не вероятности |
| Существующий lossless transport | Stationary template отвергается current generation; public JSON1/2 parser не принимает новое поле даже null; opted source не кодируется старыми simulation encoders. Current3 остаётся unsupported |
| Отсутствие скрытого downgrade | Genuine legacy v2 echoes созданы до opted sources. Ни opted native source, ни opted document не очищается для старого parser/encoder. JSON reconstruction явно ограничен полным конечным fixture, а не generic codec |
| Неизменяемость | Fixtures, authored sources/staged request и глобальный RNG до/после равны; randomness внедрена в scripted native API |

Ручной `restore_finite` сверяет документ целиком с известным fixture и явно восстанавливает две typed policies. Это не admission произвольного пользовательского JSON; malformed/unknown/value/clock и trusted-version acceptance matrix будущего v3 должны проверяться production tests. Ни корректность будущего family guard, ни actual generated stationary trace, ни console3 этим примером не доказаны.

Existing `assess_magic_candidate` отвергает same-ID подмену stationary policy при прежнем summary. V1 parser negatives изолируют новое поле от Miscast, включая отдельный balance family-only case. В текущем v2 balance negative поле присутствует одновременно в reserve и generation; отдельный family-only v2 case остаётся в production acceptance, а не выдаётся за проверенный этим probe.

## Независимое ревью и inventory для реализации

Read-only ревью контракта и actual APIs не выявило противоречий. Уточнения внесены до реализации: strict enum checks обеих сторон equality и candidate; поддерживаемые версии по конкретной family на промежуточном simulation3 этапе; nullable schema без запрещающего null строкового `const`; обновление прежних registry/audit counts12 на18magic schemas.

Дополнительное read-only ревью замороженных probe/test/отчёта подтвердило finite counts, source/order/seed assertions, полный copied bundle и отсутствие скрытого legacy downgrade. Будущие production guards не выдаются за реализованные assertions конечного примера.

| Место | Предстоящая проверка / изменение |
| --- | --- |
| `application/magic_candidate_generation_models.py` | Append-last field, typed template/family equality до enumeration; source и candidate validation перед result reconstruction/equality |
| `application/magic_candidate_generation.py` | Preflight factory до `_count_vectors`; явная family policy в `_project_candidate`; all-or-error subset admission прежний |
| `application/magic_*_models.py`, `magic_*_errors.py` | Command metadata и три phase errors допускают3; default/positional compatibility; native source checks не сводятся к wire version |
| `adapters/_magic_scenario_json.py` | Явное чтение/вывод обеих policies по версии;1/2 lossless rejection и strict native enum; свежий полный source до admission |
| `adapters/magic_simulation_json.py`, `magic_balance_json.py` | Full command reconstruction, independent reserve/family equality/pointers, exact generation→staged→report; обе error/result versions совпадают с command |
| `adapters/_json_common.py`, `magic_json_errors.py` | Magic-only family version selection после полного lexical decode; malformed fallback1/null ID и supported3 trusted metadata |
| `adapters/magic_json_schema.py`, `adapters/schemas/` | 6 новых local-reference schemas, registry18magic/36total, default1, корректный null, отсутствие обращения к отсутствующей balance3 Schema на этапе simulation3 |
| `application/magic_*_service.py`, `cli.py` | Собственная версия command при runtime failure, phase context, encode-before-write; actual module/console и sequential/spawn |
| `tools/audit_m8_transport_install.py` и installed helpers | Обновить hardcoded12-schema assumptions, добавить v3 обеих families/independent combinations и новые public outputs; прежние1/2 и6legacyroutes сохранить |

`src/`, production schemas, старые tests и старые fixtures в этой контрактной вехе не редактировались. Существующие незакоммиченные изменения ADR-0047–0050 сохранены. Новое чтение книг/версии/хэши/Rule IDs/house rules не заявляются: transport использует уже проверенную нормативную базу ADR-0050.

## Воспроизведение

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe docs/examples/m8/stationary_wound_transport_contract_probe.py

$env:PYTHONPATH = 'src;tests'
.venv/Scripts/python.exe -m unittest integration.test_m8_stationary_wound_transport_contract_probe -v
```

Для другого cwd/компьютера нужны установленный текущий пакет с зависимостями и пять соседних файлов: `stationary_wound_transport_contract_probe.py`, `generation_contract_probe.py`, `magic_scenario.py`, `opted_miscast.py`, `stationary_wound_runner.py`. Test копирует только этот bundle в отдельный cwd и требует exact saved stdout, пустой stderr и exit0. Ни PDF, ни git history, ни fixtures из рабочего каталога при исполнении не нужны.

Windows x64 / CPython3.12.4: copied-bundle test **1test OK /5,071с** после финальных source/isolated-v1 уточнений. Первоначальная sandbox попытка встретила известный Windows PermissionError при работе с temporary directory; тот же test вне sandbox прошёл. Новый installed wheel не собирался для контрактного среза без изменения production; прежний installed audit не выдаётся за v3 evidence.

Полная регрессия на границе контрактной вехи:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

**3902tests /33known errors /0failures /0skipped,971,355с**, вне sandbox. Новый copied-bundle test прошёл. Log: `.cache/adr0051-contract-regression.log`; все33 отсортированных exact `ERROR:` headers совпали с `.cache/adr0050-regression.log`. Нет новых errors, `FAIL:` или skipped.32прежних subtest errors относятся к frozen/slotted Aim property,1 — к `dataclasses.replace(init=False)`; причины описаны в [открытых вопросах](../open-questions.md#проверки-dataclasses-на-python-312). Suite с этими errors не называется зелёным. После этого production/tests/probe не менялись, повторная регрессия не нужна.

Проверены локальные Markdown-пути (без anchors), `git diff --check` и совпадение прежних saved v2 results с generated baseline при нормализации переводов строк. Новые файлы этой вехи: ADR-0051, этот отчёт, probe/stdout и один integration test. Навигация, архитектура, roadmap, актуальный статус и открытые вопросы синхронизированы. Новых нерешённых игровых вопросов нет.

## Следующий шаг

Пункт1 ADR-0051 целиком: native generation model/preflight/projection/result guards, source/None/forged-input tests и реальная generated stationary chain через staged sequential/spawn. Затем simulation3, balance3 и общий installed/full audit в указанном порядке. Production ADR закрывается после пункта4. Никаких новых gameplay consumers/save-resume; commit/push выполняет пользователь.
