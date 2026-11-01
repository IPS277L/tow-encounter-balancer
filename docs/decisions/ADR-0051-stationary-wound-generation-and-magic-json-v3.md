# ADR-0051: stationary-wound family policy и Magic JSON/CLI v3

Дата: 2026-11-01. Статус: **пункты1–2 реализованы; balance3 и общий аудит ещё предстоят**. Основа — [native policy ADR-0050](ADR-0050-native-stationary-wound-policy.md), [generation/v2 ADR-0047](ADR-0047-opt-in-generation-and-magic-json-v2.md) и [native audit](../audits/m8-native-stationary-wound-readiness.md). [Generation audit](../audits/m8-stationary-wound-generation-readiness.md), [simulation3 audit](../audits/m8-simulation-v3-readiness.md), [public probe](../examples/m8/stationary_wound_transport_contract_probe.py)/[stdout](../examples/m8/stationary_wound_transport_contract_probe.output.txt). [Исходная контрактная проверка](../audits/m8-stationary-wound-transport-contract.md) остаётся исторической evidence; актуальная проверка реализации записывается в профильных аудитах.

## Граница

Провести существующую `NpcMagicStationaryWoundPolicy.LEG_SPASM_STAND_AND_CONTINUE` через генерацию составов и новый versioned wire. Никаких новых игровых переходов: canonical first9 stand, context49 Casting/Protection/end и active/expired6 остаются ровно в границе ADR-0050. Miscast permission независима. Повторная9 после stand, Wind Prone с retained terrain, ordinary movement, Recover/treatment и прочие mandatory effects этим контрактом не открываются. Unsupported остаётся в общем знаменателе.

Это решение о передаче разрешений и полном источнике, не новое извлечение правил. Нормативная база прежняя: BOOK-PLAYER-GUIDE1.4, гл.V Rules / Difficult Terrain115, Free Actions116, Giving Ground119, Conditions122–123; гл.VIII Casting156, Miscasts157–159; приложение Wounds Table190. BOOK-GM-GUIDE1.1, гл.VII Champions92. Нового чтения книг, Rule IDs или house rules в этой вехе нет.

## Native family assertion

Добавлено последним полем `MagicCandidateGenerationRequest`:

```python
stationary_wound_continuation: NpcMagicStationaryWoundPolicy | None = None
```

Поле задаётся отдельно от `template_scenario.stationary_wound_continuation` и отдельно от family Miscast policy. Оно подтверждает применение разрешения ко **всем** generated subsets и supplied frames. Не выводить permission из template, `CAST_WHEN_READY`, no-additional-rules facts или численности; omitted равен None, а не opted template. Существующие family facts и exact ordered frames остаются обязательными. Policy не делает внешние обстоятельства истинными: caller отвечает за scope каждого subsets; удалённые резервисты отсутствуют в конкретном сценарии, а не остаются внешними наблюдателями.

До enumeration/projection/materialization/RNG проверить:

- Template и family содержат настоящий `NpcMagicStationaryWoundPolicy` либо None. Raw string, bool, dict и чужой enum отвергаются независимо от равенства значений.
- Полное typed equality template/family. Opted template + omitted/None family и None template + opted family — ValueError. Не заменять несовпадение default или исправлением template.
- Существующий Miscast preflight применяется независимо. Все четыре сочетания policies допускаются при отдельном matching assertion каждой; stationary policy не означает decline/Prone policy для Miscast.
- Старые positional constructors и явное None дают прежние C, budgets, ordered IDs/seeds и полные projections. Новая policy не меняет enumeration или ранжирование.

Повторить pure permission/source validation на публичной границе `generate_magic_candidates` **до** `_count_vectors`, в reconstruction `MagicCandidateGenerationResult` и в цепочке command/result encoding. Frozen dataclass не является доказательством валидности объекта после unpickle/`object.__setattr__`. Equality строкового enum с raw string недостаточно; invalid source нельзя «починить» проекцией в валидный child. Проверять существующие поля исходного request, а не молча создавать нормализованный replacement.

`_project_candidate` передаёт обе полные **family** policies явно в каждый новый `NpcMagicScenario`. Expected candidate в generation result строится тем же путём, но source preflight выполняется раньше. Перед equality проверяется настоящий enum также у каждого candidate, чтобы raw-string child не прошёл через равенство строкового enum. Проверяется весь исходный template/family и весь candidate, включая scenes/order/clock/facts/policies, а не только ID. Same-ID substitution None/opted или foreign scenario в generation→staged→assessment/report запрещена. Equal immutable source copies допустимы. Ни domain, ни engine не импортируют application/JSON ради этих проверок.

## Magic JSON v3

Обе существующие magic families получают отдельную версию `'3'`: request/result/error для `simulate-magic` и `balance-magic`. Версия задаётся явно; наличие policy не выбирает её. V1/v2 schemas и сохранённые outputs неизменны. Шесть прежних ranged/melee/mixed routes по-прежнему принимают только v1. Native gameplay и seed scheme версию wire не знают.

В v3 `scenario.stationary_wound_continuation` **обязателен**:

```json
"stationary_wound_continuation": "leg_spasm_stand_and_continue"
```

Либо explicit `null`. Это wire string для существующего enum, не object с новым смыслом/facts. Строка строго фиксированная; object/bool/number/unknown string/omission запрещены. В balance те же требования к `reserve.scenario.stationary_wound_continuation` и отдельному `generation.stationary_wound_continuation`; exact typed equality проверяется до generation preflight. Mismatch имеет pointer `/generation/stationary_wound_continuation`; ошибки значения — фактический scenario/reserve/family pointer.

Прежний `miscast_continuation` из v2 остаётся required nullable со всеми choice/facts/prone_policy fields. В balance reserve и generation содержат **оба независимых required nullable поля**, даже если одно или оба null. Никаких дополнительных state/journal/wound/history полей на входе: формат остаётся fresh-only. Result echo содержит полный request3, а aggregate/catalog/stages/phase contexts сохраняют прежнюю форму.

| Версия | Miscast permission | Stationary permission |
| --- | --- | --- |
| 1 | Любое wire поле запрещено; native non-None serialization отклоняется | Любое wire поле запрещено; native non-None serialization отклоняется |
| 2 | Required null или полный existing object | Любое wire поле запрещено, даже null; native non-None serialization отклоняется |
| 3 | Required null или полный existing object | Required null или точная enum string; balance требует отдельный matching family field |

Шесть новых packaged schemas с собственными version3 IDs используют только bundled локальные v1/v2 fragments и новый stationary definition. Nullable enum описывается `oneOf` null/const-string либо `enum` с null и строкой; один `const` строки не допускает null. Нельзя через закрытый `additionalProperties=false` v2 scenario незаметно добавить v3 field: v3 имеет собственный полный список scenario properties/required. Registry/cache различает family/kind/version; загружаются все нужные transitive references без сетевых resolver. В итоговой границе18 magic schemas/36 schemas всего; прежние audit/cache assumptions12 нужно явно обновить. Default validator/mapper version остаётся1.

## Parser, encoder, errors и CLI

Публичные signatures parser/result/error encoder сохраняются. Существующая command metadata и keyword-only error metadata расширяют закрытый набор с1/2 до1/2/3; default остаётся1. Shared scenario mapper получает explicit version3 и устанавливает обе typed policies **до** финального scenario admission. Узкий strict reader расширяется только для magic; название прежнего internal `magic_v2` option можно заменить осмысленным magic-only option с обновлением всех callers, без ослабления остальных families. На промежуточном этапе simulation3 reader/registry используют набор версий конкретной family: balance3 до своего этапа остаётся explicit unsupported с fallback1, без попытки загрузить отсутствующую Schema. Таблица trusted3 ниже относится к family, уже поддерживающей3.

`scenario_document` сохраняет early lossless rejection stationary policy для1/2 и Miscast policy для1. V3 выводит оба поля также при None. Прямой mapper не принимает raw-string native permission. Request/result encoding reconstruct-check сравнивает весь command, definition order, exact source и выбранную версию. Balance сравнивает generation→staged→reports до serialization. Удалять permission из opted source ради старого encoder или парсить его временный legacy view запрещено.

| Условие | Версия error envelope / ID |
| --- | --- |
| Неполный strict decode: UTF-8/JSON, duplicate keys, surrogate, float/exponent/nonfinite | Fallback1 / null ID, даже если текст содержит3 |
| Полный strict decode, supported string3, затем shape/semantic failure | 3 / только полный nonblank request ID |
| Полный decode, отсутствующая/не-string version | Fallback1 / decoded допустимый ID; invalid_input |
| Полный decode, неизвестная string version | Fallback1 / decoded допустимый ID; unsupported_version, `/schema_version` |
| Runtime failure admitted command1/2/3 | Точная версия command; собственный request/phase context |

Trusted version устанавливается после полного lexical decode и до shape validation; safe metadata передаётся через helper/admission errors. Никакого tolerant reparse или извлечения версии/ID из частично декодированного текста. Services используют версию собственной command, а не metadata cause; cause/notes не выходят в JSON. Input schema failure не объявляется unsupported gameplay.

CLI сохраняет exit0 completed result (включая unsupported),2 input/usage,3 execution/generation,4 I/O; usage/read failure без stdout. Полное encoding до записи; error при encoding не превращается в игровой stop, при output failure нет повторной записи error. Sequential/process требуют прежнего explicit execution input; transport не добавляет default decisions.

## Этапы реализации после контрактного proof

1. **Native generation реализован и проверен:** append-last model, preflight входа/result, явная family projection и source guards.19unit+5integration tests проверяют finite vectors/обе perspectives, четыре combinations, positional/None IDs/seeds, omitted/mismatch/raw/nested enum, forged/unpickled request до enumeration, same-ID source substitution и late failure без partial family. Actual generated3/4actor chains48/66d10 и None controls проходят staged sequential/spawn с полным report/denominator. Full regression3926tests/33known errors/0failures/0skipped; exact ERROR headers прежние. [Evidence](../audits/m8-stationary-wound-generation-readiness.md).
2. **Simulation v3 реализован и проверен:** три schemas/registry, command/errors/shared reader+mapper, parser/service/result+error encoder/CLI вместе с version3 output.30newtests проверяют required/unknown/type/null/enum/paths, full source/echo/order, strict trust table, no RNG, int1 facts/raw enum laundering, old1/2 rejection и actual sequential/process/module CLI. Public request/result сохранены. Full3956/34errors включает33known и1исправленный старый CLI negative; targeted rerun прошёл, новый full3956/33 не заявляется. Balance3 явно unsupported до loader; interim15magic/33total. [Evidence](../audits/m8-simulation-v3-readiness.md).
3. **Balance v3:** ещё три schemas/command/errors, независимые reserve/family assertions и source-bound encoder/service/CLI. Native family preflight до materialization, mismatch pointer, catalog/stages/report chain, candidate/counts/stage error context, real backends. V1/v2 сохранены; v3-null не понижается.
4. **Общий аудит:** actual public v3 requests/results, all six schemas и local refs, source/wheel/installed path+hash parity, module/console и spawn, обе magic families1/2/3 с null/independent policies, прежние шесть routes. Saved v1/v2 stdout неизменны. Полная регрессия на production границе с exact сравнением прежних33 ERROR headers; известных errors недостаточно, чтобы объявить suite зелёным. В этот момент закрывается implementation ADR, не при наличии одного ручного proof.

Текущий public probe использует настоящий opted generator/family admission и simulation3 codec/service, сравнивает20full projections с independent manual project, выполняет8actual simulation3 round-trips и8finite manual balance3 mappings. Отказ simulation3 заменён реальной public round-trip проверкой; balance3 до пункта3 остаётся отказом. Installed/module/console общий proof — пункт4. Отказы старых версий и opted template без family assertion остаются.

Commit/push выполняет пользователь.
