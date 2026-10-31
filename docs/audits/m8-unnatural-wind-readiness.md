# M8: аудит source-bound Miscast и Unnatural Wind

Дата: 2026-10-28. Граница — [ADR-0045](../decisions/ADR-0045-source-bound-unnatural-wind.md): explicit decline → preparation → один table roll → actual Wind21–22. Закрыт low-level consumer с полным roster owner. Автоматическое продолжение боя, journal/Prone policy и JSON не входят в acceptance этой вехи.

## Книжная сверка

Непосредственно перечитаны локальные постраничные тексты выбранных редакций:

| Книга, глава и страницы | Нормативное следствие и граница |
| --- | --- |
| BOOK-PLAYER-GUIDE1.4, гл.VIII Magic in the Old World / Casting / Interrupted Casting, стр.156; Miscasts and the Rule of Nine, стр.157 | Triggered Pool сохраняется до effect; preparation теряет Casting successes. Доступный spell перед Miscast — явный выбор с дополнительной die. В этом scope принимается только explicit DECLINE без bonus; available spell не выбирается автоматически. |
| Та же книга, Disposing of Miscast Dice / Miscast Table, стр.158; Miscast Table, стр.159 | Бросается вся Pool, суммируются значения. Cleanup после полного effect по стр.157; lookup сам по себе не разрешает effect. Wind строго21–22, включая caster и allies, исключая Monstrosities. Иная строка не перенаправляется в Wind и не очищает Pool. |
| Та же книга, гл.V Rules / The Battlefield / Range, стр.114 | Short — same Zone; Close может пересекать границу соседних Zones. Scope требует отдельного no_cross_zone_close и отсутствия external Short creatures/bystanders. |
| Та же книга, Combat Actions / Recover, стр.118; Conditions / Prone, стр.123 | Prone сохраняет запрет ухода из Zone и modifiers атак по цели. Recover/free-move removal имеют свои prerequisites. У Prone нет end-turn upkeep; прежний END_TURN stop — ограничение интеграции, не новое книжное правило. |
| BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Minions, стр.91; Champions, стр.92 | Injury policies сохраняются раздельно; defeated Minions остаются в archive, но не входят в effect targets. Единственный Champion — Wizard, Monstrosities в текущий roster не допускаются. |

Новых Rule IDs, house rules или книжных ambiguities не выявлено. Спорные self-inclusion других строк1–2/3–4 не интерпретируются: строка21–22 включает caster явно. Книжные примеры/описания мира не использованы как отдельные нормативные правила.

## Матрица реализации и проверок

[Domain models](../../src/towr/domain/npc_roster_miscast_models.py) хранят frozen/slotted requests/results; [rules](../../src/towr/rules/npc_roster_miscast_resolution.py) соединяют существующие узкие K1 reducers. Domain не вызывает rules/RNG. Универсального Miscast framework, новой action receipt или боевого aggregate нет.

| Граница | Evidence |
| --- | --- |
| Explicit policy и пять required facts | [Preparation unit](../../tests/unit/test_m8_npc_roster_miscast_preparation.py): policy/facts без defaults, False/type mismatch, available spell decline и отказ от actual desperate preparation. Facts — assertions caller, не автоматическое доказательство полноты именованного NPC. |
| Полный raw origin / actual preparation | Те же tests проверяют living Wizard, completed standard action/last execution, canonical skipped-Test/increase/pool/history proof. [Integration](../../tests/integration/test_m8_npc_roster_miscast_preparation.py) подтверждает actual Casting и реальные bound Recover/Run origins, live Casting anchors против full round/defeated archive, Wound/daily/expiry/usage histories. Progress сброшен, Pool сохранён. |
| Один roll / complete recorded trace | [Roll unit](../../tests/unit/test_m8_npc_roster_miscast_roll.py): только prepared pending и canonical ID, strict tuple/d10/count/sum/total, exact magic/effect/Rule IDs. Wind21/22 iff canonical entry; known Wind нельзя замаскировать чужой строкой. Реальный level1 Pool2 не получает bonus и не может дать Wind. |
| Rolled pending и другие строки | [Roll integration](../../tests/integration/test_m8_npc_roster_miscast_roll.py): один existing K1 roll с injected RNG, другой row сохраняет actual values/effect request/Pool. Root меняет только prefix. Repeat/new-ID/stale source запрещены; RNG failure не даёт retry/cleanup/partial state, RNG не откатывается. |
| Полный Wind target set | [Wind unit](../../tests/unit/test_m8_npc_roster_unnatural_wind.py): caster первым, остальные live same-Zone в roster order; self/allies/enemies, outside/archive и already-Prone. Target policy/full injury берутся из root, caller не передаёт отфильтрованный список. |
| Exact actual applications до Pool0 | Те же tests: missing/reordered/duplicate targets, weak K1 Wind/target/Condition metadata и premature cleared magic отклоняются. Literalbool flags и typed Condition.PRONE проверяются отдельно от value equality. Полный injury меняет только Prone; Wounds/unrelated Conditions/effects не лечатся. Частичный сбой target2 не публикует cleanup и не мутирует source. |
| Whole-owner projection / source / replay | Все три набора проверяют полный source equality, stale IDs с чужими contexts/roll traces, frozen/replace/deepcopy/finite graph. Wind меняет только target injuries, roster references обоих child owners, wizard.magic и prefix; placements/round/definitions/equipment/receipts/ledgers/daily/expiries сохранены. Apply не повторяет reducer/RNG. |
| Mandatory guards и честная diagnosis | Prepared/rolled prefix блокирует все legacy actions/start/advance/end/defeat/death и terminal/fresh admission. Diagnosis raw/prepared/rolled — MISCAST_PREPARATION/MISCAST_ROLL/MISCAST_EFFECT с canonical source IDs; новый result не входит в closed journal. |
| Prone после effect | [Wind integration](../../tests/integration/test_m8_npc_roster_unnatural_wind.py): реальный END_TURN stop после actual effect; ACTOR_INJURY/TARGET_INJURY проверены отдельно на authored later snapshots. Это не resumed battle и не доказательство reachability поздних состояний через runner. |

Всего75implementation tests:54unit+21integration. Независимое read-only ревью core/guards/test matrix и adversarial smoke не оставило блокеров; общий acceptance также проверяет public example и installed source ниже. Pure API не обещает подлинность произвольного externally forged DTO или запрет намеренного восстановления старого immutable snapshot.

## Самостоятельный production-пример

[unnatural_wind.py](../examples/m8/unnatural_wind.py) / [stdout](../examples/m8/unnatural_wind.output.txt) запускается одним скопированным файлом, импортируя только stdlib и public towr API. Числовые профили/scene/GM facts authored. Все три bound фазы публикуются через actual apply-функции, ручной post-effect root projection отсутствует. [Integration test](../../tests/integration/test_m8_unnatural_wind_example.py) проверяет external cwd/stored stdout/пустой stderr.

Семь случаев/63scripted d10: Wind21 и22; self+ally+enemy; outside enemy без изменения; actual Attack/defeat/archive до Casting; explicit decline при доступном spell; already-Prone с сохранённым Staggered; other30 с complete rolled pending/Pool3 и Wind rejection до effect. Проверяются input/global RNG, полные owners/histories, фазовые stops и реальный Prone END_TURN. Scripted numbers — regression witness, не вероятность сложности.

Fresh Casting и authored bound inputs разделены: уже Prone ally вводится явно в low-level input и не выдаётся за доступный fresh scenario (его admission требует healthy actors). Interruption origins доказаны отдельными actual bound Recover/Run tests, не этим свежим примером. [Исторический finite probe](../examples/m8/unnatural_wind_contract_probe.py) остаётся прежней K1-композицией с manual projection; он не подменяет production example.

## Установленный пакет

Wheel собран offline из temporary copy src/pyproject/README/LICENSE, без изменения build/lib рабочего репозитория. Все444Python/Schema files source/wheel/installed site совпали побайтно, наборы файлов также равны. Пример одним файлом прошёл из external cwd при `python -I`, без PYTHONPATH/PYTHONHOME, с проверкой import paths нового domain/rules API внутри isolated site. Stdout совпал, stderr пуст; pip check exit0. Зависимости скопированы offline из проверочного окружения.

Wheel SHA-256: `a92370976f44c315118b1dca2615e7222b8daa2b41104ab642f646f2cf7f7d3e`. CPython3.12.15/macOS26.5.1arm64; jsonschema4.26.0, referencing0.37.0, jsonschema-specifications2025.9.1, attrs26.1.0, rpds-py2026.9.1, typing-extensions4.16.0. Это не cross-platform/performance evidence. Reports `/private/tmp/towr-m8-wind-audit-installed-build.json`, `/private/tmp/towr-m8-wind-audit-installed-report.json`.

При аудите production/старые tests/probes/JSON/CLI/runner не менялись; сохранность относительно начального snapshot проверяется отдельно. Начальная попытка установки обнаружила наследуемый PYTHONPATH: pip видел source package вместо новой установки. Harness убрал переменную и принудительно установил wheel в новый venv; только эта повторная изолированная проверка считается installed evidence. Исходники проекта для этого не исправлялись.

121focused tests (75implementation+45existing K1 effects+1example) — OK (0,342с). Полная регрессия3547tests/33прежнихerrors (156,172с); точные Counters полных error headers/subtests/exception signatures равны предыдущим3546tests, новых ошибок нет. Все915existing Python/JSON сохранены, source/harness hash прежний `5c2e50aafba116c13f6b1b6ffffc6eb819cc0a86cc90dea8bbcf53824587f52b`. Compile двух новых Python files, Markdown/import315/whitespace и неизменный HEAD подтверждены. [Preservation/static report и команды](../project-status.md#последняя-проверка). Известные33Python3.12dataclasses assertions не объявляются зелёным suite.

## Итог и следующий контракт

Low-level ADR-0045 закрыт в согласованной границе; новых игровых решений не потребовалось. Не подключены desperate cast/abandonment, другие effects, mounts/Monstrosities/immunities, external creatures, cross-Zone Close, saved battle или автоматический decline. Остальные Wound/Miscast/scene/route stops и unsupported denominator прежние.

Следующий шаг — отдельный контракт automatic opt-in подключения готовой цепочки: explicit policy/facts, exact journal source chain и scoped Prone end-turn/action/target/Recover/free-move/Broken adapters с finite proof до production. Политика не выводится из existing CAST_WHEN_READY; fresh-only JSON/CLI admission также потребует отдельного решения. Наличие low-level effect не разрешает пропускать нынешние guards или объявлять универсальный бой готовым.
