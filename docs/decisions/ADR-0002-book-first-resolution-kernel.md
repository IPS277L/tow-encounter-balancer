# ADR-0002: book-first resolution kernel перед новым battle loop

Статус: принято, 2026-08-18.

## Контекст

Прототип P1 использует упрощённые WS/DEF, action economy, stagger и wound limit. Обе книги задают связанные механики Characteristic + Skill, контекстной защиты, Range, Wounds Table, типов NPC, выбора при повторном Staggered и специальных исключений Monstrosity.

Расширение существующего battle loop закрепило бы неверные предпосылки.

## Решение

Перед новым battle loop реализовать и проверить чистый resolution kernel:

- Test profile из Characteristic + Skill;
- модификаторы, динамический предел пула, Grim и Glorious;
- Basic и Opposed Test;
- выбор attack/protection profile из контекста;
- Damage и Resilience;
- Staggered с внешней policy выбора последствия;
- Wound application через отдельные injury policies для Player/Champion, Minion, Brute и Monstrosity;
- структурированные результаты и события без знания CLI, JSON или Monte Carlo.

Zones, порядок ходов, AI, encounter objectives и массовая симуляция подключаются после стабилизации kernel.

## Последствия

Существующий P1 сохраняется только как материал миграции и будет переписан без требования обратной совместимости. Новые тесты строятся по Rule ID и страницам книги. Контекстные параметры можно подавать в kernel до появления полного spatial engine.

## Уточнение 2026-09-27: Protection preparation

Контекстную проверку защиты выполнять чистым prepare_protection поверх AttackRequest. ProtectionTestOption связывает supplied Test с defender/Skill; frozen request/result хранят explicit facts/choice и exact source. Меняется только defender_test; eligible skills и unopposed причины типизированы. При нескольких разрешённых способах выбранный Skill задаёт caller; RNG, best-profile policy и equipment discovery не добавляются. Resolver/kernel сохраняют прежний контракт; preparation trace хранится отдельно от Attack trace до будущей композиции. Контекстная подготовка NPC Attack остаётся следующим срезом исходного решения. Источники: BOOK-PLAYER-GUIDE 1.4, Abilities / Skills / Defence и Throwing, стр. 68; Equipment / Ranged Weapons, стр. 94; Throwing Weapons, стр. 96; Rules / Attack Tests, стр. 118; BOOK-GM-GUIDE 1.1, Allies and Antagonists / Understanding NPC Profiles, стр. 93.

## Уточнение 2026-09-27: выбранная NPC Attack

Использовать immutable supplied numeric Melee/Shooting profile и отдельный actor-scoped availability snapshot. IDs профиля и фактически доступной атаки проверять до подготовки; source snapshot/target/profile сохранять и проверять в result. Не переносить traits PC оружия по имени. С Protection связывать полное значение Attack и Skill/target, не только ID; хранить два preparation results и общий trace, исполнять existing resolver отдельно. NPC Throwing/Brawn/non-damage/Extreme и multi-attack требуют отдельных поддержанных contracts, а не скрытых defaults. Исходная строка K1 закрыта для этой boundary сквозным integration с kernel и Wound completion (3 теста / 44 сочетания). Все пять критериев аудита выполнены; следующий этап — контракт состава M2, без нового executor в K1. Источники: BOOK-GM-GUIDE 1.1, Allies and Antagonists / Understanding NPC Profiles, стр. 93; Brigands & Footpads (Brigand, Town Watch), стр. 97; BOOK-PLAYER-GUIDE 1.4, Equipment / Melee Weapons, стр. 92–93; Ranged Weapons, стр. 94; Throwing Weapons, стр. 96; Rules / Range, стр. 114; Attack Tests, стр. 118.
