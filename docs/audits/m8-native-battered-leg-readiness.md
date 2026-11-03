# Приёмка native Battered Leg, ADR-0061

Дата: 2026-11-03. Статус: **ADR-0061 закрыт в принятой native границе; regression составной, installed audit завершён**.

[Контракт](../decisions/ADR-0061-native-battered-leg-continuation.md) сохраняет механику59 и full-owner границу60. Нормативные источники: BOOK-PLAYER-GUIDE1.4, Characteristics/Skills68–70, Wounds/Conditions121/123, Wounds Table190/5; BOOK-GM-GUIDE1.1, Champions92. Новых правил/house rules, повторного чтения PDF или изменения версии нет.

## Реализованная граница

Append-last nullable `NpcMagicScenario.battered_leg_continuation` хранит отдельную typed policy с authored Endurance InlineProfile. Факты unmounted/no-external-Conditions приходят из повторно проверенного Scenario. Профиль не выводится из Casting, Protection или default. Независимые permissions имеют24valid/8invalid combinations; repeated по-прежнему требует stationary.

Новый Step содержит actual result60. Test actor — Wizard, active turn остаётся у Minion; action/free-move/Wound-roll budget не меняется. Runner/Result выводят bounded history из своего fresh prefix, требуют полного непосредственного Attack predecessor и exact first completion/receipt на всех descendants. Подмена trace при равных ID/successes/injury, profile, raw enums/facts, receipt stripping и replay запрещены.

Success позволяет прежние normal consumers в точной injury границе60. Failure завершает pending, сохраняет sourced Prone и останавливается при первом неподдержанном action/target. Новый Staggered или completed Wound после success сохраняется с receipt, затем даёт END_TURN scope stop до normal factory. Pending Wound/Miscast/movement tails имеют приоритет. Miscast standalone stand не снимает Prone5.

Смерть после единственной first5 не заявляется достигнутым native тестом: второй Wound бросает2d10 и имеет максимум20, а дальнейший consumer уже останавливается до третьей раны. Existing immediate death exclusion44 не менялся; dead bypass exact-injury gate60 не добавлен. Treatment/healing, повторная5, mixed injuries, Prone5 removal и current-state/save-resume остаются вне scope.

## Проверки и ревью

- [21 pure unit tests](../../tests/unit/test_m8_battered_leg_native.py): profile/facts/permissions, actor, predecessor/tail, history и source/trace/receipt/None admission. Validators не вызывают RNG.
- [15 native integration/boundary tests](../../tests/integration/test_m8_battered_leg_native.py): success/failure, completed Wizard turn, post-Test Staggered/Wound, pending Miscast, обе perspectives, sequential/real Windows spawn/staged evaluation, source/seeds/denominator и early generation/JSON1–5 refusal. Первый прогон15tests OK,39.967s; поздние проверки admission включены в full regression ниже.
- [2 copied public tests](../../tests/integration/test_m8_battered_leg_native_contract_probe.py): isolated cwd, exact saved stdout, source/SHA неизменны.2tests OK,23.212s.
- [Actual native228d10](../examples/m8/battered_leg_native.py), [stdout](../examples/m8/battered_leg_native.output.txt):11direct controls и sequential/spawn по2trials, round-limit + unsupported сохраняют denominator2.
- [Finite39d10](../examples/m8/battered_leg_native_contract_probe.py), [stdout](../examples/m8/battered_leg_native_contract_probe.output.txt): ручной oracle и действующие native61 helpers/None refusals. Исторический closed-union/gap control обновлён на реальные61 refusals и END_TURN; старый bypass не объявляется действующим.

Независимое ревью привело к исправлениям: typed predecessor до доступа к полям; оригинальные Attack enum до eligibility; detached child rosters и daily Wound records до equality; bounded prepared/rolled Miscast ancestry, чтобы скрытый старый receipt нельзя было отмыть удалением upper marker. Усиление `_owner60` сохраняет прежнюю механику и закрывает original-data admission. Других блокеров ревью не выявило.

## Внешние границы

Native trial/sequential/process и explicit/staged evaluation сохраняют полный Scenario/profile и прежнюю seed scheme. Parent admission отклоняет повреждённые профили до pool/worker; UNSUPPORTED_PATH остаётся в знаменателе. Generation требует отдельный family contract и рано отвергает nonNone61. Обе magic JSON families1–5 отказывают новому полю даже null при decode и nonNone при encode; schemas/registry/CLI не расширены. None сохраняет старый wire.

## Полный regression и установленный пакет

Полный набор завершён с project Python3.12.4/Windows x64, реальными tempfile/subprocess/spawn и логом `.adr61-full.log`: **4292tests,1522.401s;4290passed,2failures,0errors/skips**. Оба failures — старые metadata assertions в Miscast46/stationary50 tests: tail ожидал4optional policy fields, после append61 их5. Ожидания и выделение исходных positional arguments обновлены; проверка прежних constructors/None сохранена.

После изменения только этих двух test files обе affected группы повторно прошли: **21tests OK**,0.433s, лог `.adr61-recheck.log`. Сопоставление4292full IDs с21recheck IDs подтвердило успешное покрытие всех4292checks. Первоначальный full остаётся с2failures и не объявляется зелёным. Production после full не менялся; повторный полный набор не запускался. Все489production hashes сохранились. Это составной проверенный результат, не ещё один полномасштабный run.

Свежий offline wheel61 собран без сети через `tools/prepare_m8_transport_audit.ps1`; pip check OK. **489 Python/JSON files** source/wheel/installed совпали по путям/SHA-256, новых PDF/references в wheel нет. SHA-256 wheel: `c2ea9c7ab49981f3763fe4ebe7295fb00a45799bf775e479168c8b815581ee23`.

Copied21unit +15integration проверены через installed `python -I`:35checks прошли в первом36-прогоне, один decoder test не имел скопированных JSON example fixtures. После добавления этих fixtures только он повторно запущен и прошёл1/1,2.185s; ошибок production-кода не обнаружено. Это составной результат36checks, не утверждение о зелёном первоначальном36-прогоне. Обе copied examples228/39 выполнялись через installed -I и совпали с saved stdout, включая real spawn; source Python path не использовался.

Существующие публичные JSON5 requests также прошли на установленном пакете: `python -I -m towr simulate-magic` и console `towr.exe balance-magic`, exit0 и корректные version5 result kinds. Новое разрешение в эти requests не добавлялось; проверки lossless refusal нового поля находятся в integration tests.

Обновлённые21policy checks также скопированы и прошли на installed -I,0.418s. Итого57distinct installed checks закрыты составно:35initial +1fixture-retest +21policy checks; прежние успешные36 не переисполнялись. Final Markdown paths:194files/4705links/0missing, `git diff --check` OK. Raw logs, wheel, copied inputs и evidence JSON находятся локально в ignored `.cache/adr0061-installed-audit`; для восстановления рабочего контекста достаточно этого отчёта/ADR/тестов.

## Следующая граница

Отдельный generation/transport ADR: matching Battered Leg family permission с authored profile, явная projection каждого candidate и обе magic JSON families с lossless version gates. First5/native61 scope сохраняется. Prone5 removal, mixed injuries и current-state/save-resume потребуют других consumers.
