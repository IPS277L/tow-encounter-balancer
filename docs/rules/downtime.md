# Downtime и Endeavours

Источники: `BOOK-PLAYER-GUIDE`, версия 1.4, глава Between Adventures, страницы 131–136; `BOOK-GM-GUIDE`, версия 1.1, Handling Downtime, страница 47. Статус области: `partial`; Rest and Recovery Endeavour реализована как самостоятельная Test/healing boundary, весь каталог и GM-side cadence проверены, campaign clock и persistent progression в коде отсутствуют.

## RULE-DOWNTIME-001 — структура

GM объявляет Downtime при достаточной передышке, обычно раз в 2–3 sessions. Сначала происходит Event, затем каждый персонаж выбирает по одному Endeavour за каждую session после прошлого Downtime, максимум три. Exacting progress можно сохранять между повторными выборами Endeavour. В конце Coin reset к трём Coin текущего Status.

Каждая Endeavour Test также развивает проверяемый Skill: все failure dice добавляются в Improvement Track, а при превышении rating повышают Skill на 1 и полностью сбрасываются; максимум обычно 6.

Источник: страницы 131–132.

## RULE-DOWNTIME-002 — каталог Endeavours

| Endeavour | Test / cost | Нормативный результат |
|---|---|---|
| Aid Contact | обычно primary Skill Contact | Success гасит свой долг либо создаёт favour Contact; новый Contact — Exacting 4, одна Test/Endeavour |
| Bank Money | Charm | success хранит по Coin своего Status; 3 successes могут хранить один Coin tier выше; withdrawal требует Endeavour без Test |
| Change Career | GM-chosen Skill, success + 3 XP | применяет полный переход Career при prerequisites и narrative permission |
| Craft Trapping | Exacting Dexterity/Toil | Brass 2; Silver 4 и Brass expense/Test; Gold 8 и Silver expense/Test; Trade Lore+tools обязательны, workspace `+1d` |
| Formalise Spell | Exacting Recall 4 | Wizard+Literacy; вписывает известный/увиденный spell в grimoire; improvised CV становится вдвое меньше |
| Gather Information | Recall/Awareness/Leadership | success даёт сведения; связанный Clue следующего adventure автоматически раскрывает Insights |
| Help Ally | подходящий Skill | каждый success даёт `+1d` следующей Endeavour Test до общего cap |
| Invest Money | 3 Coin + contextual Test | success даёт trapping/service tier выше самого дешёвого Coin; Asset — GM-approved Exacting 2/4/8+ с 3 Coin и Endeavour за Test |
| Lay Low | Awareness/Stealth | Secret Hideout `+1d`; success опережает подходящих mundane pursuers, но результат context-dependent |
| Memorise Spell | Exacting Recall 8, либо 4 из своего grimoire | Wizard; formal spell без grimoire; improvised CV вдвое меньше |
| Prolonged Labours | Career Skill | next adventure `+2 Coin` при success, иначе `+1 Coin` |
| Practice Skill | выбранный Skill | обычные failure marks плюс ещё одна mark |
| Rekindle Fate | Exacting 4; одна Test/Endeavour и spend Fate/Test | при rating ниже starting, но выше 0, восстанавливает permanent Fate на 1 до starting maximum |
| Rest and Recovery | Endurance | success лечит одну Wound и все Festering Wounds; surgery prerequisite сохраняется |
| Study Lore | обычно Exacting Recall 4 | prerequisites категории; Magic требует дополнительно 4 successes за каждую уже известную Magic Lore |
| Test Might | Opposed physical Skill | success даёт раз в next adventure Glorious Fellowship перед впечатлённым NPC |
| Wander the Wilds | Survival | next adventure временно получает relevant Environment/Provincial Lore либо `+1d` при уже известном |

Источник: страницы 132–136. Suggested Skills могут заменяться при правдоподобном подходе с разрешения GM.

В первом исполняемом срезе `RestAndRecoveryEndeavourRequest` требует именно книжную Endurance Test и точный downtime/target/injury snapshot. Успех позволяет отдельным reducer исцелить одну выбранную treated/resolved Wound и создаёт typed запрос на снятие всех Festering Wounds; провал не создаёт ни одного из этих эффектов. Строки `20–23` дополнительно требуют успешный ordinary surgery proof из того же downtime либо более ранний completed Combat Surgeon battle proof той же Wound. Festering follow-up имеет собственный target-bound one-shot consumer и очищает весь отдельный state; этот state создаётся end-of-day Infection producer из day-scoped принятых Wounds, если день не был закрыт automatic success после Anatomy Recall. Общая GM-возможность заменять Suggested Skill пока не применяется к этому специализированному healing contract. Campaign allocation Endeavours, paid NPC service и применение surgery-failure follow-up остаются внешними границами.

## RULE-DOWNTIME-003 — favour Contact

Favour — направленный долг между персонажем и Contact. Contact, который должен favour, может рисковать безопасностью, тратить время/ресурсы, давать trappings, Clues или bonus dice будущей Endeavour. Конкретная форма определяется NPC; долг не является универсальной валютой и не гарантирует выбранный игроком эффект.

Источник: Player’s Guide 1.4, страница 132; Gamemaster’s Guide 1.1, страница 21.

## RULE-DOWNTIME-004 — частота Endeavours

Для еженедельной игры GM следует выдавать эквивалент одной Endeavour за каждую session. При более редких встречах GM может выдавать больше. Накопленные Endeavours разрешено объединять в окна по две или три; во время путешествия их можно сохранить до следующего Downtime, адаптировать к доступной деятельности или разыграть flashback. Общий максимум накопления остаётся равным трём.

Это campaign scheduling policy, а не действие персонажа. Число прошедших sessions и накопленных Endeavours должно храниться с состоянием кампании.

Источник: Gamemaster’s Guide 1.1, страница 47; Player’s Guide 1.4, страница 131.

## RULE-DOWNTIME-005 — Event перед Endeavours

Во время Downtime сначала определяется один Event. Для кампании в Talagaad GM бросает `d100` по таблице из 21 непересекающегося результата. Состояние кампании хранит ранее выпавшие Events. Повтор можно:

- пропустить и перебросить, если событие не должно повторяться;
- использовать как эскалацию прежней ситуации.

Сами записи таблицы задают публичную ситуацию и заинтересованных Contacts, но не накладывают автоматических modifiers, Conditions или обязательных приключений. В другом месте GM адаптирует Talagaad Event либо создаёт собственную таблицу на основе конфликтов поселения.

Источник: Gamemaster’s Guide 1.1, страницы 67–69; порядок Event перед Endeavours подтверждён Player’s Guide 1.4, страница 131.
