# ADR-0080: естественные Melee-атаки и первый чанк существ

Дата: 2026-11-05. Статус: принято. Пользователь выбрал контракт вместе с тремя существами.

## Проблема

NpcAttackProfile требует1H/2H, а PC source — вооружённого fresh NPC. GM1.1, Allies and Antagonists135–137 содержит Hooves, Clamping Jaws и Goring Tusks без хвата. Подстановка фиктивного оружия искажает источник и Protection eligibility. По GM93 используется напечатанная Melee-атака, а не автоматически выведенный Unarmed/Brawn profile.

## Контракт

Обязательное Python поле NpcAttackProfile.hands принимает RangedWeaponHands либо None. None означает только **естественную Melee-атаку**, не неизвестное/пропущенное значение. Shooting по-прежнему требует1H/2H; RangedWeaponHands не расширяется значением natural.

В текущем PC JSON1 обязательное attack.hands принимает1h/2h/null с тем же смыслом. Parser/serializer сохраняют null явно. Прежние requests/results с1h/2h не мигрируются, версия и метрики не меняются. Cached source и full replay проверяют exact types и совпадение полного определения.

Для первого PC-среза естественная атака соответствует fresh state wields_weapon=false, holds_shield=false и Athletics Protection. Вооружённые профили сохраняют wields_weapon=true и прежние варианты Protection. Нельзя подать null и выдать NPC за вооружённого/способного к выбранной Defence. Это ограничение первого среза, не универсальное правило о любой естественной защите всех существ.

Вооружённый PC может защищаться Defence от естественной Melee-атаки (PG1.4 Skills/Defence68, Attack Tests118). При атаке PC по существу actual Protection preparation видит отсутствие оружия у цели. Зубы/копыта не становятся inventory item или потерянным оружием.

Общий low-level NPC attack preparation допускает естественную Melee-атаку и сохраняет напечатанный Test/Damage. Прежние bounded Melee/Mixed/Magic/Ranged families автоматически не расширяются: там, где их source/wire контракт требует вооружённые атаки, natural profile отвергается до исполнения/кодирования. Особенно проверить native Melee/Mixed guards и существующие `.hands.value` encoders; не оставлять поздний AttributeError.

## Чанк

| Существо | Источник | Атака | Protection | Resilience |
|---|---|---|---|---|
| Horse | GM135 | Hooves3d/3 Damage3 | Athletics4d/4 | Toughness3/Resilience3 |
| Giant Wolf | GM136 | Clamping Jaws3d/3 Damage3, цель не может Give Ground | Athletics4d/4 | Toughness3/Resilience3 |
| Giant Boar | GM137 | Goring Tusks3d/4 Damage3 | Athletics3d/3 | Toughness3/Resilience5 armoured |

Все — Fast Minions, самостоятельные участники без всадников, уже находящиеся в Close Range. Текущий owner не выполняет Charge или перемещение. Noble Steed/варианты mounts, rider benefits и Charge-бонусы Boar сохраняются как inactive с полными условиями. Обычный unmounted Horse — отдельный профиль; optional Bretonnian/Elven/Skeletal варианты не подставляются.

PG1.4 Equipment / Clothing & Armour97 явно относит к armoured любого врага с Resilience выше Toughness, в том числе за счёт свойства, отличного от надетой брони. Поэтому natural armour Boar(5 против Toughness3) даёт обычный PC Axe/Halberd/Greataxe bonus; особый house rule не требуется. GM93 также даёт снижение5→3 для ignores-armour attack. Собственный Charge-бонус Boar — отдельный attack trait, не только rider ability; в неподвижном срезе он не срабатывает.

Запрет Give Ground от Giant Wolf должен входить в actual KernelAttackRequest и canonical projection независимо от source facts.can_leave_zone. Его нельзя объявить неактивным лишь потому, что нынешняя fixed стратегия выбирает SUFFER_WOUND. Не переносить запрет на прочих NPC. Не добавлять универсальный язык attack traits: явный helper по существующему образцу Craven достаточен.

## Проверка

Пользователь согласовал контракт вместе с Horse/Giant Wolf/Giant Boar. Функция выполняется через source/domain/native/trials/count search/current JSON1. Независимая сверка карточек подтверждает напечатанные значения и Melee, без фиктивного хвата. У PcBookNpcEntry добавлен описательный unselected_variant_names для явного исключения optional Horse variants; у прежних восьми записей tuple пуст, их прежние поля сохраняются.

Проверки: null только для Melee, обязательность hands, отсутствие оружия/запрет неверной Defence, actual armed-PC Defence против natural attack, Wolf can_target_leave_zone=false при разрешённом уходе сцены, точные armour/Test/Damage/отсутствие неактивного Charge-бонуса, cached aliases/full-source/replay guards. Для shared модели нужны адресные прежние armed attack и bounded-family admission/codec tests; один сквозной sequential/process пример, не матрица каждого профиля. Full/wheel только при отдельных основаниях из AGENTS.md.

Фактическая проверка и текущие ограничения — в [статусе](../project-status.md); [общие примеры](../examples/m27/README.md). Другие bounded families сохраняют свои текущие wire contracts и отвергают natural profiles до исполнения/кодирования, включая повреждённые cached sources.
