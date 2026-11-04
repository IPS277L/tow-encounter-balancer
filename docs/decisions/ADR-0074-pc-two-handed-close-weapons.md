# ADR-0074: двуручное Close-оружие PC

Дата: 2026-11-04. Статус: принято.

## Задача и граница

M18 моделировала одно оружие в одной руке. Простое добавление Damage для2H позволило бы применять его после потери руки и обходить Critical12. M19 добавляет законченный срез: Pickaxe, Flail, Billhook, Halberd, Glaive, Greataxe, Greathammer через native бой, trials/process, подбор и текущий PC JSON1. Greatsword исключён до проверки буквального `+1 to Defence` без `d` в таблице.

Источники: BOOK-PLAYER-GUIDE1.4, гл.IV Equipment92–93; гл.III Skills68; гл.V Helping108, Actions116/Recover118; Wounds Table190–191. [Нормализованные правила](../rules/equipment.md#исполняемая-pc-граница-m19) хранят профили и Traits. Пользователь выбрал сохранять полный результат раны и останавливать trial как UNSUPPORTED_PATH при утрате возможности2H применения. Это конечная граница симуляции, не house rule о дальнейшем поведении персонажа.

## Решение

Сохраняем один предмет и прежнее поле `initial_weapon_hand`. Для2H оно обязано иметь значение `both`, представленное отдельным `PcTwoHandedGrip.BOTH`; для1H обязательны прежние `PcWeaponHand.LEFT/RIGHT`. Анатомические стороны всегда LEFT/RIGHT: BOTH не является третьей рукой. State `weapon_hand` хранит тот же тип хвата либо None после фактического drop. Source/state/codec/schema проверяют соответствие оружия и хвата; строковые/чужие enum aliases не становятся typed proof.

Готовность2H требует обе пригодные руки. Травмированная рука12 остаётся пригодной, но Attack, Defence, нынешний weapon-assisted Help и Recover с восстановлением хвата вызывают Critical, если используют любую такую руку. Переход в здоровую руку не обходит2H requirement. Это ограничение способа физической помощи, а не требование двух рук для любого книжного Help.

Drop4/8/12 затрагивает весь2H предмет при выборе любой руки; явное drop/clutch18 также освобождает обе. Recover может поднять предмет с восстановлением2H хвата, если обе руки доступны, сохраняя остальные self/ally benefits и их реальные consequences. Не вводим общий inventory или запрет переносить2H предмет одной рукой вне боя.

После завершения полного Wound lifecycle, Near Miss window и всех immediate consequences факты16/18/20 могут сделать2H хват недоступным. Тогда canonical `PcMeleeUnsupported` сохраняет actor, точные Wound sequence/table_total, source ID `RULE-EQUIPMENT-002:{actor}:w{sequence}:two-handed-grip` и reason `two_handed_grip_unavailable`. Дальнейшие journal steps запрещены. Raw table roll или отменённая Near Miss рана не вызывают stop. Это не поражение, смерть или ROUND_LIMIT; costs/losses относятся только к исполненному prefix.

При16/20 сохраняем последний зарегистрированный BOTH marker, уже не пригодный для применения; он не доказывает удержание или падение предмета оставшейся рукой после границы. При18 фактический drop известен и marker равен None. Для1H прежняя смена руки и продолжение сохраняются.

Явные weapon helpers готовят Damage и actor/target modifiers; прежние Drained/cap/minimum die/Glorious/Help и canonical Attack arithmetic не меняют ответственности. В текущей пешей сцене Billhook mounted trait и Pickaxe harvesting trait не применяются. Armour modifier использует только оговорённый numeric armour bonus без shields/Abilities.

JSON1 расширяет enum оружия и допустимый correlated grip без новых метрик/полей/версии. Полная party, хват, Fate и support policies фиксируются в count search. UNSUPPORTED_PATH остаётся в знаменателе и исключает соответствующего кандидата из выбора. Старые примеры сохраняются без миграции; backward compatibility слой не создаётся.

## Альтернативы

- Один LEFT/RIGHT marker для любого оружия скрывал бы вторую руку и давал неверные Attack/Critical/drop результаты.
- Добавление BOTH в анатомический PcWeaponHand допускало бы невозможную сторону в randomised body consequences.
- Запасное оружие/переключение, Brawn fallback и произвольное удержание требуют нового явного входа/тактики; пользователь выбрал остановку первого среза.
- Полная inventory/grip система и dual wield пока не нужны. Отдельная версия wire не обоснована расширением этой family во время разработки.

## Проверка

Адресно: [traits](../../tests/unit/test_m19_pc_weapon_traits.py), [native grip/Wounds/Fate и stop proofs](../../tests/unit/test_m19_pc_two_handed.py), [codec/schema](../../tests/unit/test_m19_pc_weapon_json.py), [process/observations/search](../../tests/integration/test_m19_pc_two_handed.py). Ближайшая регрессия — PC M9–M19 и связанные K1 Test/Attack/Protection/Help/Recover/Fate/Wounds; без повторения M8 callers, общий Recover не менялся. Команда для новой копии:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.unit.test_m19_pc_weapon_traits tests.unit.test_m19_pc_two_handed tests.unit.test_m19_pc_weapon_json tests.integration.test_m19_pc_two_handed tests.unit.test_m9_pc_melee_json tests.unit.test_m9_pc_melee_json_schemas -q
```

Проверить actual CLI примеры, полный source echo, current offline schema refs и неизменность прежних JSON-пар. Full regression назначается при широком риске, wheel — при изменении доставки/перед выпуском, согласно AGENTS. Фактическая приёмка и следующий шаг — в [статусе](../project-status.md).
