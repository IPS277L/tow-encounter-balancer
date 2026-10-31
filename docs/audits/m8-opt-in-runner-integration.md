# ADR-0046: аудит интеграционного среза этапа 3

Дата: 2026-10-31. Это проверка journal/runner integration, не закрытие этапа 4 или всего M8.

## Проверяемая граница

Явный opt-in подключает preparation → один roll → Wind21–22 к full-owner runner. Other-row сохраняет Pool/pending/actual effect ID. Typed preparation witness равен полному непосредственно предыдущему Casting/Recover/Run result, а не только post-state. Обязательные predecessor/tail guards и прежний dead Champion guard используются и при публикации, и при валидации результата.

Scoped Prone stand/end и action adapters подключены совместно: exact scene до stand, unsafe Broken до stand/RNG, одна free move, incoming Shooting−1d, effective departure=False, обычные собственные Tests. Separate Wound whitelist/expiry guards сохранены. Alternative Recover не получает standard benefits. None сохраняет прежние runtime traces/IDs/draws/stops.

Источники не изменены: [ADR-0046](../decisions/ADR-0046-opt-in-miscast-runner-and-prone.md), BOOK-PLAYER-GUIDE1.4, гл.V Rules / Free Actions116, Recover118, Attack Modifiers119, Prone123; гл.VIII Casting/Interrupted Casting156, Miscasts157–159; BOOK-GM-GUIDE1.1, гл.VII Minions91/Champions92. Этот этап связывает уже проверенные consumers, не заявляет новое полное чтение книг или новый house rule.

## Evidence

- [Journal16](../../tests/unit/test_m8_miscast_journal.py): typed origin, actual Recover/Run, equal-post-state trace substitution, phase/tail/namespace/collision guards, exact other-row result, serialization.
- [Prone policy13](../../tests/unit/test_m8_prone_journal_policy.py): обязательное вставание, Close/used resource/unsafe Broken, current frame, legacy rejects, state-derived Casting/Shooting facts.
- [Runner14](../../tests/unit/test_m8_opted_miscast_runner.py): real fresh Wind21/22 → Prone end → stand → Shooting, последний budget round, следующий round stand→Casting→objective, no-Miscast legacy parity, failures без retry, chronology/ongoing cause priority.
- В том же runner module отдельный **authored-runtime harness** проверяет Recover/Run interruption → preparation/witness → other-row, а также Run→Wind→end→MISSING_SCENE. Подменяется только initial runtime property настоящим owner с зарезервированным ходом; executors и journal validation не подменяются. Это не доказательство fresh reachability этих origins и не saved-battle API.
- Независимое review выявило: journal принимал Attack без обязательного departure fact, хотя runner останавливался. Теперь оба согласованы; negative full-journal regression удаляет facts из исходного scenario. Старый hand-built Journal fixture теперь явно задаёт использовавшийся им факт can_leave=True. Legacy runner не меняется.
- Прежние tests, ожидавшие запрет самих result types stand/end/roll/Wind, теперь проверяют scenario-aware rejection без opt-in.

## Проверки

Windows x64 / CPython3.12.4. **304 tests / 0 failures / 0 errors, 1,764 с**, включая 43 новых tests. Итоговый прогон выполнен вне sandbox: тест внешнего примера в sandbox ранее упёрся в WinError5 при cleanup Windows Temp; отдельно и в итоговом прогоне он прошёл. Первые промежуточные прогоны выявили только устаревшие vocabulary/fixture ожидания, исправленные выше.

```powershell
$env:PYTHONPATH = "src"
$modules = @(
  "tests.unit.test_m8_miscast_journal", "tests.unit.test_m8_prone_journal_policy",
  "tests.unit.test_m8_opted_miscast_runner", "tests.unit.test_m8_miscast_continuation_policy",
  "tests.unit.test_m8_npc_roster_miscast_preparation", "tests.unit.test_m8_npc_roster_miscast_roll",
  "tests.unit.test_m8_npc_roster_unnatural_wind", "tests.unit.test_m8_npc_roster_prone_stand",
  "tests.unit.test_m8_npc_roster_prone_turn_end", "tests.unit.test_m8_prone_casting",
  "tests.unit.test_m8_prone_shooting", "tests.unit.test_m8_prone_broken_recover",
  "tests.unit.test_m8_npc_magic_scenario_result", "tests.unit.test_m8_npc_magic_scenario_runner",
  "tests.integration.test_m8_npc_magic_scenario_runner", "tests.integration.test_m8_miscast_continuation_admission",
  "tests.integration.test_m8_npc_roster_miscast_preparation", "tests.integration.test_m8_npc_roster_miscast_roll",
  "tests.integration.test_m8_npc_roster_unnatural_wind", "tests.integration.test_m8_npc_roster_prone_stand",
  "tests.integration.test_m8_npc_roster_prone_turn_end", "tests.integration.test_m8_prone_casting",
  "tests.integration.test_m8_prone_shooting", "tests.integration.test_m8_prone_broken_recover"
)
.venv/Scripts/python.exe -m unittest @modules -q
git diff --check
```

## Не закрыто этим аудитом

Этап 4: full opted source/result propagation через trial/sequential/process/assessment, denominator/error evidence, public opted example, source/wheel/installed parity и полная регрессия. Последний полный baseline до runtime integration: 3563 tests с 33 известными dataclasses errors, не зелёный suite. JSON/CLI v1 и generation продолжают lossless-reject opt-in. Остальные Miscast effects, unsafe Broken escape и universal engine не добавлены.
