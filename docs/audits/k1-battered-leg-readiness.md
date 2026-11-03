# K1 Battered Leg Endurance: ADR-0059

Дата: 2026-11-03. **ADR-0059 закрыт в указанной K1 границе.**

## Поддержанный срез

Одна Wound с actual table total5/roll `(5,)`, resolved, untreated, unhealed; пустые Conditions/active effects. Caller явно подтверждает `unmounted=True` и предоставляет numeric Endurance profile, actor ID и локально согласованный `WoundEffectResult` с единственным Endurance follow-up. Test normal, без modifiers и reroll locks. Полная граница — [ADR-0059](../decisions/ADR-0059-battered-leg-endurance-test.md).

Нормативные источники: BOOK-PLAYER-GUIDE1.4, Abilities / Characteristics & Skills67–72; Rules / Wounds & Conditions121, Conditions/Prone123; Appendix / Wounds Table190, строка5. Использованы локальные extracted pages, новые PDF/hash не добавлены. Endurance success предотвращает Prone; failure создаёт только wound-sourced Prone. Treatment/healing и стандартное снятие Condition здесь не исполняются.

## Исполнение и ревью

Тестовый источник проходит настоящий `resolve_character_wound` с rolled5, затем `resolve_wound_effect` и новый `execute_battered_leg_endurance_test`. Consumer вызывает существующие Test/wound reducers; чистые domain validators сверяют source/follow-up и весь normal trace с параметрами authored Test. Локальная совместимость не доказывает actual journal membership, chronology или character-sheet profile authority.

Независимое ревью обнаружило и повторно проверило исправления:

- Drained и прочие неподдержанные Conditions/effects отклоняются до RNG, чтобы не пропустить их Test modifiers/consumptions.
- Treated/healed/unresolved/foreign Wound отвергается до RNG.
- Полный effect witness связывает canonical follow-up, Test ID и injury snapshot.
- Одинаковый Test ID не скрывает чужие pool/threshold, success arithmetic, rerolls или raw enum aliases.
- Mounted context отклоняется: Prone на mount/vehicle требует отдельного dismount consumer.

Actor/profile source, battle journal/replay и все сочетания за текущей границей явно остаются у caller или следующего native contract. Существующий Characteristic enum ограничивает список допустимых semantic alternatives.

## Проверки

Source targeted: **26 tests, OK** (16 новых ADR59 + 10 existing wound-effect tests). Та же copied test bundle: **26 tests, OK** через свежий installed Python с `-I`; исходники репозитория не входят в import path.

Offline build использовал cached setuptools84.2.1. Wheel SHA-256: `2f4edc1f3503f058d6d7712dfb622174f644482a856571b376cd43e62c518510`. Source/wheel/installed: **486 Python/JSON paths and SHA-256 совпали**. Новые modules и public domain exports доступны из site-packages; private references/PDF не попали в wheel. `pip check` успешен. Schema files не менялись.

После full run повторная сверка сохранила те же 486 paths/hashes. Проверены пути локальных Markdown-ссылок: **190 files, 4633 links, 0 missing**. `git diff --check` прошёл.

Полный suite завершился в обычной Windows-среде с проектным `.venv`, Python3.12.4: **4239 tests, OK**, 0 errors/failures/skips, **1120.898 s**. Прерванные промежуточные запуски не считаются финальной evidence.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Следующая граница — отдельный ручной M8 full-owner bridge с authored Wizard Endurance profile, current owner/pending Wound5 и точным применением Test result. Native runner/journal идут после bridge, generation/JSON — после native integration. Коммиты и push выполняет пользователь.
