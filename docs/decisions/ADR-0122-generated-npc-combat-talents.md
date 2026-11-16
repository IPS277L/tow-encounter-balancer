# ADR-0122: книжные боевые таланты динамических NPC

Дата: 2026-11-16. Статус: принято пользователем и реализовано. Выбраны все три таланта и предложенная автоматическая тактика; Defensive Stance обменивает только действительно доступное новое Staggered атакующему.

## Источники и выбор функции

Адресно прочитаны Player’s Guide1.4, гл.III Talents73, Defensive Stance74, Magic Resistance78, Wild Attack81; гл.V Attack Tests118/Failed Attacks119 и Conditions123. GM1.1 VII91 подтверждает defeated при первой Wound для Minions. Нормализованные RULE-TALENT-001/002/003 и существующие spell Potency/Conditions/Glorious reducers переиспользуются; код не является источником правила.

Реализован чанк из трёх совместимых талантов (Talents) для текущих generated Minions:

| Талант | Requirements / rank | Эффект книги в принятой сцене |
|---|---|---|
| Сопротивление магии (Magic Resistance), PG78 | Нет; единственное приобретение | −1 Potency у каждого затрагивающего cast spell; при0 нет эффекта |
| Оборонительная стойка (Defensive Stance), PG74 | Weapon Skill3+; единственное приобретение | После успешного противопоставления Melee через Defence можно отказаться от Staggered противнику и снять собственный Staggered |
| Дикая атака (Wild Attack), PG81 | Strength4+; единственное приобретение | Если владелец не Staggered, может сделать следующую Melee Glorious, немедленно получив Staggered до броска |

Hardy не выбран: его Wounds Table modifier не изменит поражение ordinary Minion от первой раны. Armour Bane требует отдельного общего состояния повреждённой брони PC; таланты движения/всадников требуют другой сцены. Инертные таланты не добавляются ради числа записей. Это не расширение каталога именных NPC.

## Факты и генерация

`GeneratedNpc.talents` — упорядоченный список уникальных идентификаторов выбранных талантов. У этих трёх нет дополнительных ranks/повторных приобретений: один ID означает единственное приобретение, дубликаты отклоняются. Полный список сохраняется в `NpcDefinition.generated_components`, result, character file и current replay; механика определяется типизированными компонентами, не именем/ID NPC.

Ручной `search_space.allowed_talents` задаёт разрешённые таланты, а не готовый перечень всех сочетаний. `[]` отключает их генерацию; automatic space разрешает все три. Генератор сначала выбирает характеристики/снаряжение, затем допустимый поднабор талантов с учётом Requirements. Поднабор может быть пустым. Не строится полный декартов product, число Monte Carlo trials не увеличивается автоматически ради каждого сочетания.

При мутации характеристик нельзя сохранить талант с нарушенными Requirements: выбирается допустимая мутация либо отдельным предложением меняется состав талантов. Перезапуски поиска позволяют исследовать другие сочетания. Parser/source validator не исправляет невалидные данные и не удаляет скрыто таланты перед симуляцией. Proposal generation и strict admission имеют разные обязанности.

В этой генерации соблюдаются напечатанные Requirements, как при приобретении за XP; история развития и XP-бюджет NPC не моделируются. Книга отдельно разрешает игнорировать Requirements для бесплатного таланта при Character Creation (PG73). Такой provenance/waiver этим срезом не вводится; это явное ограничение генерируемого набора, не отмена книжного исключения. У PC новые таланты не подключаются автоматически: отдельный вход/контракт партии пока не расширяется.

## Автоматическая тактика и порядок

**Magic Resistance.** Это target-scoped изменение Potency через существующий общий reducer. Lightning Blast использует уменьшенную Potency в Damage. Fire Breath выбирает до исходной Potency разных foes, затем проверяет сопротивление каждой цели отдельно: при нуле цель не затронута; положительная уменьшенная Potency не меняет фиксированный Fire Breath Damage. Нет повторного выбора цели после committed cast. Advisor и выбор spell учитывают те же условия; Miscast сам по себе не считается cast spell. Drained не выключает этот пассивный эффект.

**Wild Attack.** В первом срезе NPC автоматически использует талант перед собственной Melee Attack, если жив, не Staggered и не Drained. Цена применяется реальным source-bound переходом до подготовки/броска Test, поэтому Sword/Morning Star и остальные Conditions видят новый Staggered. Glorious действует ровно на следующую фактическую Melee Test; выбран reroll всех доступных провалов, без PC Fate. При Drained тактика не платит за недоступный Glorious. Дополнительный action/slot не создаётся. Это ограниченная тактика применения, не доказательство её оптимальности.

**Defensive Stance.** Выбор Defence/Athletics по ADR-0121 сохраняется. При фактически успешной Defence против Melee и собственном Staggered NPC предпочитает снять его, отказавшись от Staggered атакующему в пределах выбранной ниже трактовки. При отсутствии собственного Staggered сохраняет обычное последствие промаха. Успех требует настоящего результата opposition:0v0 не является успешной Defence. Применение не стоит action, не вызывает новый Test и не заменяет рану/попадание эффектом защиты. Drained не запрещает это снятие состояния. Сначала фиксируются реальные Test/Attack results и выбор последствия, затем однократно применяются Conditions; самовосстановление не исполняется поверх уже наложенного несовместимого miss consequence.

Новые состояния/receipts и повторное чтение native proof должны сохранять полный source, исходные условия, actual Test IDs и однократность. Spell/Miscast/Attack pending нельзя обходить новой реакцией. Текущие PC potions/magic, Minion defeat, Shield, cap и negative modifiers сохраняются.

## Defensive Stance при уже Staggered атакующем

PG74 предлагает отказаться от наложения Staggered. PG119 прямо говорит, что обычный Close miss не добавляет штрафов уже Staggered атакующему. Текст таланта отдельно не поясняет, достаточно ли отказаться от потенциального последствия, если по общему правилу оно и так отсутствует.

Пользователь выбрал узкий вариант: обмен возможен только при действительном доступном наложении нового Staggered на атакующего; если атакующий уже Staggered, собственное состояние этим обменом не снимается. Альтернатива: после успешной Defence собственный Staggered снимается и в этом случае, поскольку выбран отказ от наложения, даже когда он фактически ничего не стоит. Альтернатива не выбрана. Это явно согласованная конкретизация сочетания PG74/119; нулевой обмен не исполняется.

## Публичная граница

Current Dynamic/PC JSON1 дополняются выбранными `talents` в компонентах и `allowed_talents` в search space. Codecs/schemas/examples/tests мигрируют вместе, compatibility-версии не вводятся. UI даёт ограничения разрешённых талантов в существующей advanced группе и настоящие теги/tooltip талантов результата; отдельный тактический редактор не добавляется. Условия сцен, seed, независимая validation и запрет рекомендации при observed unsupported сохраняются.

Выбран полный вариант с тремя талантами и их сочетаниями. Альтернатива только с Magic Resistance не выбрана. Полный source сохраняется без выключения применимых эффектов.

## Адресная проверка

- Requirements на WS2/3, S3/4, exact types, дубликаты/ranks, malformed nested source, допустимые поднаборы/мутации и независимость от NPC имени/ID; invalid source отвергается до RNG/MC.
- Literal RNG Wild Attack: цена до Test, однократный Glorious/reroll, сочетания Sword/Morning Star/Drained и отсутствие лишних actions/Fate spends.
- Literal Defensive Stance: успешная Defence, проигрыш/попадание/0v0/Athletics, собственный Staggered/его отсутствие, выбранная трактовка уже Staggered атакующего, реальные Conditions и повтор proof.
- Magic Resistance: P1→0/P2→1, Lightning Blast Damage, Fire Breath mixed targets/число targets, положительная Potency/полный no-effect, Drained и отсутствие сопротивления Miscast. Advisor/native и optional pre-Miscast spell используют один source.
- Full native source/projection/replay, реальные независимые trials, поиск при фиксированном NPC count с разными допустимыми talent-комбинациями, source echo/current schemas/character files, UI и один representative worker parity. Проверять изменённые общие reducer/owner зависимости; не запускать full/wheel по привычке.

## Реализация

`GeneratedTalent`/`GeneratedNpc.talents` проверяют уникальность/Requirements. `NpcSearchSpace.allowed_talents` — пул: sampler выбирает поднабор после характеристик; mutation отбрасывает только недопустимое предложение, сохраняя исходный NPC неизменным. Невалидный вход не исправляется. Полный component source и допустимость выбранного поднабора повторно проверяются в result admission.

`pc_generated_talents` хранит typed `PcWildAttackProof` и `PcDefensiveStanceProof`, вычисляет ожидаемую фазу и one-use source. Wild price меняет реальное NPC condition до подготовки Test; новый source даёт Glorious ровно на эту следующую Melee. Global projection guards не позволяют пропустить цену/потребление или выбранную реакцию. Defensive Stance заменяет ещё не применённый pending `AttackerStaggerRequest` после проверенных фактических Tests; уже наложенное состояние задним числом не отменяется. Result не может закончиться с обязательной работой.

Advisor учитывает добровольный Staggered/Glorious (включая Morning Star), а успешный Defensive Stance уменьшает ожидаемое непосредственное давление на NPC на стоимость снятого Staggered. Выбор самой Defence/Athletics сохраняет ранее согласованный критерий ожидаемых успехов. Нет lookahead по будущим броскам или вложенных Monte Carlo-прогонов.

Magic Resistance добавляется через общий target-scoped Potency reducer и реальный target snapshot. При P1 против всех resistant целей автоматический selector получает нулевую utility и не выбирает заведомо бесполезный cast; сам K1 P1→0/no-effect также проверен. Неизвестная GM/Miscast ветвь не становится заклинанием и не блокируется этим талантом.

[Generation/Requirements](../../tests/unit/test_generated_npc_talent_generation.py), [literal реакции/полный replay](../../tests/unit/test_generated_npc_reactions.py), [Magic Resistance](../../tests/unit/test_generated_npc_magic_resistance.py), [current JSON/process](../../tests/integration/test_generated_talents_json.py), [публичный пример](../examples/dynamic/talents.request.json), [последняя проверка](../project-status.md#текущий-срез-книжные-таланты-динамических-npc).
