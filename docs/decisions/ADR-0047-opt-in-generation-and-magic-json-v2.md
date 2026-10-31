# ADR-0047: opt-in generation и Magic JSON/CLI v2

Дата: 2026-10-31. Статус: **этапы1–2 реализованы: native generation и simulation JSON v2; balance v2 ещё не реализован**. [Аудит этапа1](../audits/m8-opt-in-generation-readiness.md), [аудит этапа2](../audits/m8-simulation-v2-readiness.md). Основа — закрытые [generation ADR-0042](ADR-0042-magic-composition-generation.md), [wire v1 ADR-0043](ADR-0043-magic-json-cli-v1.md) и [opt-in runner ADR-0046](ADR-0046-opt-in-miscast-runner-and-prone.md). Native guard требует explicit matching family policy; v1 refusal сохраняется. Следующий implementation-срез — balance v2, затем общий installed audit.

## Граница решения

Открыть существующую explicit Miscast continuation policy для генерации составов и отдельной версии magic JSON. Игровые переходы остаются ADR-0046: decline → один table roll → только Wind21–22, scoped Prone, остальные mandatory effects/unsafe Broken — honest unsupported. Нет новых spells, saved battles, runtime pending на входе, default decline или inference GM facts.

Это архитектурное решение, не новое извлечение правил. Нормативная база прежнего consumer: BOOK-PLAYER-GUIDE1.4, гл.V / Free Actions116, Attack119, Prone123; гл.VIII / Casting156, Miscasts157–159; BOOK-GM-GUIDE1.1, гл.VII / Minions91, Champions92. Полная source matrix — ADR-0046. Книги в этом контрактном срезе заново целиком не читались, новых Rule IDs/house rules нет.

## Native generation: отдельное утверждение для семейства

Последним полем `MagicCandidateGenerationRequest` добавить:

```python
miscast_continuation: NpcMagicMiscastContinuationPolicy | None = None
```

Это **отдельное явное подтверждение для каждого generated subset и его supplied frames**, по аналогии с существующими family facts/scene_frames. Policy не выводится из `template_scenario`, `CAST_WHEN_READY`, no_additional_rules либо численности. Caller явно передаёт полную policy второй раз для семейства; неизменяемый объект разрешено переиспользовать.

Preflight до перебора/проекции:

- Тип — existing `NpcMagicMiscastContinuationPolicy` либо None; чужая family/строка/dict/bool — TypeError.
- Полное равенство `request.miscast_continuation == template_scenario.miscast_continuation`; mismatch — ValueError. Opted template + omitted/None family и legacy template + opted family запрещены. Equal immutable copies допустимы.
- Existing policy требует explicit choice, five strict-True facts и prone_policy. Неполная/False policy не дополняется из прежних scenario facts. Геометрические противоречия всех supplied frames проверяет existing scenario admission.
- При None старые positional constructors, C/budgets и exact generated sources сохраняются. Ни enumeration, ни новый N×S materialization в preflight не появляется.

В каждом `_project_candidate` полная **family policy** передаётся в новый `NpcMagicScenario`. Та же projection function остаётся источником expected values в `MagicCandidateGenerationResult`; подмена candidate policy на None при прежнем ID/seed недопустима. Source/staged/service/report guards сохраняют весь объект, не только choice.

Удалённые reserve actors **вообще отсутствуют в конкретном сценарии**; они не становятся внешними наблюдателями в Short Range. Если в реальной сцене такие существа остаются рядом, caller не может подтвердить `no_external_short_range_creatures=True` для этого семейства. Требуется другой scope, не автоматическое сокращение Wind targets. All-combatants/no-external/без mounts/immunity/cross-Zone Close assertions остаются ответственностью caller; software admission не доказывает их истинность.

Все прочие правила ADR-0042 прежние: fixed Wizard/вся perspective side, prefix counts/обе perspective, независимые orders/полные definitions, fresh owner/day/graph, архивы/все frames, route filtering и full-equal collapse. Новых candidate IDs/seed schemes нет; opted RNG draw count может изменяться по ADR-0046. Любой недопустимый subset прерывает всё семейство с прежним candidate/counts/cause, без skip/partial/понижения бюджета.

## Wire v2: только явная версия

Существующие `simulate-magic INPUT` и `balance-magic INPUT` принимают версии `'1'` и `'2'`. CLI выбирает family, parser — версию из `schema_version`, не из наличия policy. Нет нового subcommand, auto-upgrade или флага, скрыто переопределяющего policy. Остальные шесть команд не начинают принимать v2.

V1 остаётся точным ADR-0043: schemas/URN/fields прежние; новое поле запрещено **даже со значением null**; parsed source получает None; opted source не сериализуется в v1. V2 c null — та же игровая semantics None, но **не тот же wire document** и не повод вывести v1.

| Место | v1 | v2 |
| --- | --- | --- |
| `scenario.miscast_continuation` (simulation) | Поля нет | Required: null или полный policy object |
| `reserve.scenario.miscast_continuation` (balance) | Поля нет | Required: null или полный policy object |
| `generation.miscast_continuation` (balance) | Поля нет | Required: null или полный policy object; exact equality с reserve |
| Envelope `schema_version` и echoed request | `'1'` | `'2'` во всех связанных envelopes |

Policy object имеет ровно три обязательных поля, facts — ровно пять:

```json
{
  "choice": "decline_cast_before_miscast",
  "facts": {
    "all_combatants_in_roster": true,
    "no_external_short_range_creatures": true,
    "unmounted_combatants_only": true,
    "no_effect_immunities": true,
    "no_cross_zone_close": true
  },
  "prone_policy": "self_stand_when_safe"
}
```

Unknown/missing keys, false, 0/1, строки вместо bool, null внутри policy/facts, чужие enum values запрещены. Optional nested fields/defaults отсутствуют. Shape проверяет Schema, semantic equality/admission — typed constructors. Missing policy нельзя трактовать как null.

Остальные fields/kinds/ruleset/seed_scheme/runtime/summary/rates/catalog и error codes ADR-0043 неизменны. Round budgets, strict UTF-8/lexical integer/duplicate/surrogate guards, canonical uint64 seed string, arbitrary-precision budgets, reduced Fraction и ordered arrays сохраняются. Records/journals/individual seeds/RNG factories/import paths на wire не появляются. Полная policy выводится в normalized request echo; каталог candidates остаётся `{candidate_id,counts}`, его источник однозначно задаёт reserve+family. Отдельная policy на каждой catalog row не нужна.

Добавить шесть `magic-{simulation|balance}-{request|result|error}-v2.schema.json`, с `$id=urn:towr:magic-{simulation|balance}:{request|result|error}:2`. Старые шесть schemas не менять. V2 result ссылается на v2 request, balance reserve — на v2 scenario; неизменные fragments допустимо reuse локально. Registry/cache key включает family/kind/version, remote retrieval запрещён. Existing public `validate_magic_*_document(document, kind='request')` сохраняет default v1; добавить явный keyword-only `schema_version='1'`. Неподдержанная версия этого Python API — ValueError, не auto-detection.

## Python metadata, lossless mapping и ошибки

В конец `MagicSimulationCommand` и `MagicBalanceCommand` добавить `schema_version: str = '1'`, только exact string `'1'`/`'2'`. Это application boundary metadata, не field доменного scenario/simulation request и не новая seed dimension. Старые positional calls, class/import/pickle paths options/window сохраняются; совместимость сериализованных объектов прежних сборок не обещается.

Native command по-прежнему может содержать opted source с default v1, но **encoder отказывает**, как сейчас. Не переносить этот lossless guard в constructor, ломая существующих native callers. V2 parser всегда сохраняет версию в command, даже при null policy. Service не меняет боевой source по версии. Result encoder получает версию command, требует full source equality и reconstruct-check всего command, включая version/definition order. Нельзя сравнить только ID либо временно выкинуть policy для successful encoding. Balance сначала проверяет полный generation→staged chain.

Существующий узкий scenario mapper получает explicit version и path prefix; новый keyword-only version argument сохраняет default v1 для прежних `parse_scenario`/`scenario_document` calls. V2 связывает полную typed policy до финального scenario admission, включая cross-Zone-Close guard. Balance не создаёт fake simulation envelope. Public parse/encode signatures сохраняются: версия берётся из input/command/error metadata, новый обязательный аргумент не добавляется. Ошибка family-policy equality указывает `/generation/miscast_continuation`; ошибки policy shape/enum/facts имеют соответствующий `/scenario/...` либо `/reserve/scenario/...` pointer. Нет silent downgrade/v2→v1 fallback.

Magic input errors и три application phase errors получают keyword-only `schema_version='1'` с тем же closed набором. Services выставляют **собственную command version**, не копируют metadata случайного cause. Error encoders используют explicit error version, сохраняют прежние safe messages/context/null slots; raw cause/notes не выходят на wire.

| Момент отказа | Error envelope version |
| --- | --- |
| Невалидные bytes/JSON, duplicate keys, lone surrogate, non-finite, float/exponent token; strict decode не завершён | `'1'` fallback, даже если текст содержит `"schema_version":"2"` |
| Strict decode завершён, object содержит поддерживаемую string `'2'`, затем shape/semantic admission failure | `'2'` |
| Decode завершён, version отсутствует/не string/неизвестная string | `'1'`; unknown string — `unsupported_version` по `/schema_version`, остальные — `invalid_input` |
| Runtime failure admitted v1/v2 command | Точная версия command |

Request ID извлекается как прежде только после полного strict decode из nonblank string; до этого null. Trusted version устанавливается до shape validation и переносится через helper/admission errors. Частичный tolerant reparse ради version/request_id запрещён. Shared `_json_common.read_request` нельзя глобально ослабить до двух версий: нужно узкое magic-only расширение с прежним default v1 для остальных families и регрессионным доказательством.

CLI I/O/exit semantics прежние: 0 — полный результат (включая unsupported), 2 — input/usage, 3 — phase execution, 4 — I/O; usage/read failure без stdout. Result/error полностью кодируется перед записью; encoder failure не превращается в игровой исход, output failure не вызывает повторный error write. Process backend по-прежнему явный; generic scheduler/codec не добавляется.

## Конечная проверка до production

Этот раздел описывает первоначальный contract-only proof. После этапов1–2 текущий probe использует настоящий opted generator и simulation v2 parser/runner/encoder; ручным остаётся только balance v2. Negative «simulation parser отвергает2» заменён actual round-trip, v1 refusal и missing family opt-in guard сохранены. Актуальная implementation evidence — в аудитах этапов1–2, а не в первоначальных цифрах ниже.

[Probe](../examples/m8/opt_in_transport_contract_probe.py) / [stdout](../examples/m8/opt_in_transport_contract_probe.output.txt) и [subprocess test](../../tests/integration/test_m8_opt_in_transport_contract_probe.py) предназначены для ручного finite отображения полного источника и policy. Legacy view используется только внутри proof вместе с отдельно сохраняемой policy; это не разрешение production adapter стирать поле. Существующие guards не патчатся и остаются действующими.

Probe должен сравнить полные ручные subset projections с legacy projection плюс explicit policy, round-trip simulation/reserve/family, None и opted source, независимые orders/IDs/seed metadata, отказ existing v1/native generation и same-ID policy substitution. Он **не является** реализацией v2 reader/Schema/CLI, доказательством будущих family guards, performance или оценкой вероятностей. Production acceptance matrix остаётся отдельной работой ниже.

При реализации v2 текущую negative проверку «parser отвергает version2» в probe нужно заменить проверкой нового public round-trip, одновременно сохранив v1 refusal. Это ожидаемая смена границы, не повод оставить весь v2 unsupported ради старого test. Native отказ opted template **без отдельной family policy** сохраняется и после этапа 1; положительный opted family case получает собственные implementation tests.

## Порядок реализации и критерии приёмки

1. **Native generation реализован:** append family field, explicit equality preflight и projection/result guards в одном согласованном срезе. Tests обеих perspective/all vectors, omitted/mismatched family, exact None parity/seed IDs, full policy source substitution, collision/invalid route/late failure без skip. Scripted generated Wind включает только retained live targets; sequential/process/staged сохраняют sources и unsupported denominator. V1 refusal остаётся. [Evidence этапа1](../audits/m8-opt-in-generation-readiness.md).
2. **Simulation v2 реализован:** три schemas/local registry, versioned command/input errors, узкий mapper/strict reader, parser/result/error encoders, service version propagation и existing CLI route. Tests v1 unchanged, v2 null/opted, all required/unknown/type/enum/false facts/paths, exact source/echo, trusted-version error table, no RNG при parsing/encoding, actual sequential/process CLI. Ни одного промежуточного опубликованного v2 input с v1 output/error. [Evidence этапа2](../audits/m8-simulation-v2-readiness.md).
3. **Balance v2:** ещё три schemas и versioned command/phase errors, reserve+family mapping, source-bound result encoder и service/CLI. Tests separate assertion/mismatch, full catalog/reports/source chain, known candidate/counts/stage contexts, successful preflight vs later generation failure, real backends и v1/v2-null parity.
4. **Общий аудит:** field/guard matrix, installed package всех двенадцати magic schemas и local refs, public v2 simulation/balance examples/stored output, обе magic и прежние шесть CLI routes, full regression с отдельным учётом known assertions. Source/wheel/installed parity не заменяется source-only proof.

Каждый production этап заканчивается воспроизводимыми tests и обновлённым статусом. Контрактный proof закрывает только проектирование/finite mapping; реализация всей ADR-0047 после него не объявляется завершённой.

## Проверка контрактной вехи

[Аудит](../audits/m8-opt-in-transport-contract.md): four-file copied-bundle test — 1 OK; полная регрессия — 3729 tests / 33 прежних errors / 0 failures / 0 skipped, 591,365 с. Error headers точно совпали с предыдущим прогоном, ранее исправленная Broken-plan fixture прошла. Independent review блокеров не оставил. Production не менялся; следующий implementation-срез — этап 1 выше.

Последующее уточнение: этап1 реализован в двух application modules, без изменений domain/engine/rules или wire. 14 новых unit +4integration +1v1guard test; updated public probe сравнивает настоящий opted generator с manual/legacy projections. Полная регрессия этапа1: **3748 tests / 33 прежних errors / 0 failures / 0 skipped, 613,814 с**, exact error headers равны baseline. Исторический contract-only audit выше не является evidence новой реализации; проверки и границы — в [аудите этапа1](../audits/m8-opt-in-generation-readiness.md).

Этап2 добавил simulation v2 parser/Schema/metadata/service/errors на прежнем CLI route; version2/null не downgrade, full policy/source и lexical fallback проверяются отдельно. Interim native balance input error с metadata2 отвергается, поскольку balance v2 ещё не реализован. [Аудит этапа2](../audits/m8-simulation-v2-readiness.md) содержит текущие команды/результаты и ограничения installed evidence. Следующий implementation-срез — balance v2 целиком.
