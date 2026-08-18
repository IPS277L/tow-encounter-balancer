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
