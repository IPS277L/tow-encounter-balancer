"""Descriptive Human Faith sources, PG1.4 VII138–149.

The ten Favours, their Strictures and thirty Prayers are source metadata, not
an effect interpreter or battle admission. A Prayer with an ongoing effect
uses PG138's battle/few-minutes default only when its text gives no exception.
Miracles require the particular intervention to be agreed with the GM.
"""
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from towr.domain.talent_models import DeityId


BOOK_ID='BOOK-PLAYER-GUIDE'
BOOK_VERSION='1.4'
CHAPTER='VII — Religion and Belief'
GENERAL_PRAYER_PAGE=138


class PrayerId(str,Enum):
    HOARFROSTS_CHILL='hoarfrosts_chill'
    HOWL_OF_THE_WOLF='howl_of_the_wolf'
    WINTERS_BITE='winters_bite'
    LORD_OF_THE_WILD='lord_of_the_wild'
    STAGS_LEAP='stags_leap'
    TANGLEFOOT='tanglefoot'
    RHYAS_SHELTER='rhyas_shelter'
    RHYAS_HARVEST='rhyas_harvest'
    RHYAS_CHILDREN='rhyas_children'
    HAMMER_OF_SIGMAR='hammer_of_sigmar'
    HEED_NOT_THE_WITCH='heed_not_the_witch'
    BEACON_OF_RIGHTEOUS_VIRTUE='beacon_of_righteous_virtue'
    DROWNED_MANS_FACE='drowned_mans_face'
    WINDS_FAIR_AND_FOUL='winds_fair_and_foul'
    WATERWALK='waterwalk'
    LAST_RITES='last_rites'
    STAY_MORRS_HAND='stay_morrs_hand'
    PORTALS_THRESHOLD='portals_threshold'
    AN_INVITATION='an_invitation'
    RICH_MAN_POOR_MAN_BEGGAR_THIEF='rich_man_poor_man_beggar_thief'
    RANALDS_LUCK='ranalds_luck'
    SHACKLES_OF_TRUTH='shackles_of_truth'
    SWORD_OF_JUSTICE='sword_of_justice'
    TRUTH_WILL_OUT='truth_will_out'
    EAGLES_EYES='eagles_eyes'
    BLAZING_SUN='blazing_sun'
    SHIELD_OF_MYRMIDIA='shield_of_myrmidia'
    # Preserve the printed PG149 heading, rather than silently fixing it.
    BITTER_CARTHASIS='bitter_carthasis'
    MARTYR='martyr'
    SHALLYAS_TEARS='shallyas_tears'


class PrayerTiming(str,Enum):
    ACTION='action'
    SESSION_START='session_start'


class PrayerDuration(str,Enum):
    DEFAULT_IF_ONGOING='default_if_ongoing'
    END_OF_BATTLE='end_of_battle'
    END_OF_TARGET_NEXT_TURN='end_of_target_next_turn'
    END_OF_CASTER_NEXT_TURN='end_of_caster_next_turn'
    CONDITIONAL='conditional'
    UNTIL_NEXT_DAWN='until_next_dawn'
    IMMEDIATE='immediate'
    SESSION='session'
    HEALING_OUTCOME='healing_outcome'


class PrayerEffect(str,Enum):
    STAGGERED_REACTION='staggered_reaction'
    SUMMON='summon'
    WEAPON_BLESSING='weapon_blessing'
    COMMAND='command'
    MOVEMENT='movement'
    TERRAIN='terrain'
    SHELTER='shelter'
    SUSTENANCE='sustenance'
    SENSE='sense'
    SPELL_WARD='spell_ward'
    CONDITION_RECOVERY='condition_recovery'
    OPPOSED_CONDITION='opposed_condition'
    VOYAGE_AND_WIND='voyage_and_wind'
    UNDEAD_CLEANSING='undead_cleansing'
    DEATH_PREVENTION='death_prevention'
    UNDEAD_BARRIER='undead_barrier'
    OBJECT_INTERACTION='object_interaction'
    DISGUISE='disguise'
    TEMPORARY_FATE='temporary_fate'
    TRUTH='truth'
    BLINDING='blinding'
    RESILIENCE='resilience'
    POISON_AND_DISEASE='poison_and_disease'
    WOUND_TRANSFER='wound_transfer'
    HEALING='healing'


def _text(value,label):
    if type(value) is not str or not value.strip():
        raise TypeError(label+' requires nonempty exact text')


def _texts(values,label):
    if type(values) is not tuple or not values:
        raise TypeError(label+' requires a nonempty tuple')
    for value in values:
        _text(value,label)
    if len(set(values))!=len(values):
        raise ValueError(label+' must contain distinct entries')


@dataclass(frozen=True,slots=True)
class PrayerDefinition:
    id:PrayerId
    deity:DeityId
    name:str
    page:int
    effect_category:PrayerEffect
    duration:PrayerDuration
    targets:str
    effect:str
    dependencies:tuple[str,...]
    duration_detail:str
    timing:PrayerTiming=PrayerTiming.ACTION

    def __post_init__(self):
        if type(self.id) is not PrayerId or type(self.deity) is not DeityId:
            raise TypeError('Prayer source requires its exact typed Prayer and deity')
        if type(self.page) is not int or not 140<=self.page<=149:
            raise ValueError('Human Prayer source comes from PG1.4 VII140–149')
        if (type(self.effect_category) is not PrayerEffect or type(self.duration) is not PrayerDuration
                or type(self.timing) is not PrayerTiming):
            raise TypeError('Prayer effect category, duration and timing require typed metadata')
        for name in ('name','targets','effect','duration_detail'):
            _text(getattr(self,name),'Prayer '+name)
        _texts(self.dependencies,'Prayer dependencies')

    @property
    def book(self):return BOOK_ID

    @property
    def version(self):return BOOK_VERSION

    @property
    def chapter(self):return CHAPTER

    @property
    def timing_detail(self):
        return ('At the beginning of the session; a game of chance with the GM (PG146).'
            if self.timing is PrayerTiming.SESSION_START else
            'An action to intentionally commune with the deity, as specified by PG138.')

    @property
    def rule_id(self):return 'RULE-FAITH-003:'+self.id.value


@dataclass(frozen=True,slots=True)
class DeityDefinition:
    id:DeityId
    name:str
    page:int
    favoured_lores:tuple[str,...]
    strictures:tuple[str,...]
    favour:str
    prayer_ids:tuple[PrayerId,...]
    miracle_scope:str

    def __post_init__(self):
        if type(self.id) is not DeityId:
            raise TypeError('Faith deity source requires its exact typed deity')
        if type(self.page) is not int or not 140<=self.page<=149:
            raise ValueError('Human deity source comes from PG1.4 VII140–149')
        for name in ('name','favour','miracle_scope'):
            _text(getattr(self,name),'Deity '+name)
        _texts(self.favoured_lores,'Favoured Lore alternatives')
        _texts(self.strictures,'Deity Strictures')
        if (type(self.prayer_ids) is not tuple or len(self.prayer_ids)!=3
                or any(type(value) is not PrayerId for value in self.prayer_ids)
                or len(set(self.prayer_ids))!=3):
            raise TypeError('each deity has its three distinct named Prayers')

    @property
    def book(self):return BOOK_ID

    @property
    def version(self):return BOOK_VERSION

    @property
    def chapter(self):return CHAPTER


_DEFAULT='No separate duration printed; apply PG138 only if the effect is ongoing: end of battle or a few minutes.'
_BATTLE='Until the end of the current battle.'
P=PrayerId
D=DeityId
E=PrayerEffect
U=PrayerDuration


PRAYER_DEFINITIONS=(
    PrayerDefinition(P.HOARFROSTS_CHILL,D.ULRIC,'Hoarfrost’s Chill',140,E.STAGGERED_REACTION,U.END_OF_BATTLE,
        'Anyone upon whom the praying character actually inflicts Staggered.',
        'Each such target must immediately pass Willpower or become Broken.',
        ('actual_staggered_trigger','willpower_test','broken'),_BATTLE),
    PrayerDefinition(P.HOWL_OF_THE_WOLF,D.ULRIC,'Howl of the Wolf',140,E.SUMMON,U.END_OF_BATTLE,
        'A summoned spectral White Wolf joins the praying character in combat.',
        'Use the White Wolf profile from the Gamemaster’s Guide; it vanishes at battle end.',
        ('white_wolf_profile','participant_summoning','battle_expiry'),_BATTLE),
    PrayerDefinition(P.WINTERS_BITE,D.ULRIC,'Winter’s Bite',140,E.WEAPON_BLESSING,U.END_OF_BATTLE,
        'An axe the praying character is actually holding.',
        '+1 Damage; the axe counts as magical for damaging ghosts and other unnatural foes.',
        ('held_axe_source','damage_bonus','magical_weapon','battle_expiry'),_BATTLE),
    PrayerDefinition(P.LORD_OF_THE_WILD,D.TAAL,'Lord of the Wild',141,E.COMMAND,U.DEFAULT_IF_ONGOING,
        'A beast; the entry supplies no numeric Range.',
        'Willpower success commands the beast within its understanding. Great danger or travelling far '
        'from its natural hunting grounds is not obeyed; Complications can mean misunderstood instructions.',
        ('willpower_test','beast_identity','gm_command_scope','command_control'),_DEFAULT),
    PrayerDefinition(P.STAGS_LEAP,D.TAAL,'Stag’s Leap',141,E.MOVEMENT,U.DEFAULT_IF_ONGOING,
        'The praying character.',
        'In battle Speed becomes Fast; jumping the height of a single-storey hovel is easy.',
        ('speed','jumping','scene_geometry'),_DEFAULT),
    PrayerDefinition(P.TANGLEFOOT,D.TAAL,'Tanglefoot',141,E.TERRAIN,U.DEFAULT_IF_ONGOING,
        'A Zone within Long Range containing vegetation, including a lawn.',
        'The Zone becomes Difficult Terrain except for the praying character and others bearing Taal’s Favour.',
        ('zone_range','vegetation_fact','difficult_terrain','deity_scoped_exception'),_DEFAULT),
    PrayerDefinition(P.RHYAS_SHELTER,D.RHYA,'Rhya’s Shelter',142,E.SHELTER,U.CONDITIONAL,
        'A natural shelter less than a minute’s walk away in the wilds, in the chosen direction.',
        'Find natural shelter and nearby means to light a fire. It lasts while resting there and cannot '
        'be found again after departure.',
        ('wilderness_scene','shelter_site','departure_event'),
        'The shelter remains as long as the travellers rest there; departure ends access.'),
    PrayerDefinition(P.RHYAS_HARVEST,D.RHYA,'Rhya’s Harvest',142,E.SUSTENANCE,U.CONDITIONAL,
        'Soil touched by the praying character; food for self and a handful of companions.',
        'Fresh fruit, vegetables and mushrooms grow. This Prayer is not answered again until all '
        'created food has been eaten or returned to the earth.',
        ('touch','food_inventory','consumption_or_return','prayer_specific_reuse_lock'),
        'No repeat until all food from the previous use is consumed or returned; no battle reset is stated.'),
    PrayerDefinition(P.RHYAS_CHILDREN,D.RHYA,'Rhya’s Children',142,E.SENSE,U.DEFAULT_IF_ONGOING,
        'Living things within Short Range, optionally extended by one Zone per Willpower success.',
        'Learn number, locations and species; not actions, thoughts or motivations. The Willpower Test is optional.',
        ('living_targets','species','spatial_sensing','optional_willpower_test'),_DEFAULT),
    PrayerDefinition(P.HAMMER_OF_SIGMAR,D.SIGMAR,'Hammer of Sigmar',143,E.WEAPON_BLESSING,U.END_OF_BATTLE,
        'A hammer the praying character is actually wielding.',
        'The hammer counts as magical for ghosts and unnatural foes; its first foe struck is immediately Ablaze.',
        ('held_hammer_source','magical_weapon','first_hit_receipt','ablaze'),_BATTLE),
    PrayerDefinition(P.HEED_NOT_THE_WITCH,D.SIGMAR,'Heed Not the Witch',143,E.SPELL_WARD,U.DEFAULT_IF_ONGOING,
        'Any spell affecting the praying character or an ally within Short Range.',
        'Any Test to cast an affected spell is Grim; the text does not restrict this to hostile spells.',
        ('actual_spell_targets','short_range_aura','casting_quality'),_DEFAULT),
    PrayerDefinition(P.BEACON_OF_RIGHTEOUS_VIRTUE,D.SIGMAR,'Beacon of Righteous Virtue',143,E.CONDITION_RECOVERY,U.IMMEDIATE,
        'Self and allies within Short Range.',
        'Remove Broken from self and all such allies. Then test Willpower and remove Staggered '
        'from self or one such ally per success.',
        ('short_range_targets','broken_removal','willpower_test','staggered_removal'),
        'The removals resolve on invocation; independently ongoing Condition causes remain subject to their rules.'),
    PrayerDefinition(P.DROWNED_MANS_FACE,D.MANANN,'Drowned Man’s Face',144,E.OPPOSED_CONDITION,U.END_OF_TARGET_NEXT_TURN,
        'A foe within Long Range.',
        'Willpower opposed by Endurance. On success, inflict Staggered and forbid Give Ground '
        'until the end of that target’s next turn; those slain appear drowned.',
        ('willpower_endurance_opposition','staggered','give_ground_lock','target_turn_expiry'),
        'The Give Ground prohibition lasts until the end of the target’s next turn; Staggered uses ordinary recovery.'),
    PrayerDefinition(P.WINDS_FAIR_AND_FOUL,D.MANANN,'Winds Fair & Foul',144,E.VOYAGE_AND_WIND,U.CONDITIONAL,
        'A blessed boat, or a ship the praying character can see.',
        'Bless its next voyage with prompt, safe natural conditions (not protection from pirates or wreckers); '
        'alternatively becalm a visible sail-dependent ship.',
        ('boat_or_ship_source','voyage_scope','line_of_sight','wind_propulsion','elapsed_time'),
        'Blessing covers the next voyage; becalming lasts at least one hour after line of sight is lost.'),
    PrayerDefinition(P.WATERWALK,D.MANANN,'Waterwalk',144,E.MOVEMENT,U.DEFAULT_IF_ONGOING,
        'The praying character on any body of water.',
        'Walk on the surface exactly as on ground.',
        ('water_surface','movement_medium'),_DEFAULT),
    PrayerDefinition(P.LAST_RITES,D.MORR,'Last Rites',145,E.UNDEAD_CLEANSING,U.CONDITIONAL,
        'A corpse; or an undead Minion within Close Range; other undead suffer a Wound instead.',
        'A corpse cannot be raised by Necromancy. Destroy a targeted undead Minion instantly; '
        'inflict a Wound on other undead. No damage-versus-Resilience comparison is prescribed.',
        ('corpse_source','necromancy_prevention','undead_type','minion_defeat','actual_wound'),
        'The attack on undead resolves immediately; the corpse’s protection has no printed expiry.'),
    PrayerDefinition(P.STAY_MORRS_HAND,D.MORR,'Stay Morr’s Hand',145,E.DEATH_PREVENTION,U.CONDITIONAL,
        'A person upon whom the praying character keeps their hands.',
        'Prevent death while conscious and maintaining touch; pain, suffering and further injuries are not prevented.',
        ('touch','consciousness','death_prevention','injury_continuation'),
        'Only while the praying character remains conscious and keeps their hands on the target.'),
    PrayerDefinition(P.PORTALS_THRESHOLD,D.MORR,'Portal’s Threshold',145,E.UNDEAD_BARRIER,U.UNTIL_NEXT_DAWN,
        'A drawn line of any shape crossing or enclosing no more than two Zones.',
        'Mindless undead cannot cross. Sentient undead must win Willpower opposed by the praying character’s '
        'Willpower; crossing still leaves them Drained until they return across the threshold.',
        ('zone_boundary','undead_mind','movement_interception','willpower_opposition','drained_source'),
        'Barrier until the following dawn; crossing Drained lasts until the creature returns across the line.'),
    PrayerDefinition(P.AN_INVITATION,D.RANALD,'An Invitation',146,E.OBJECT_INTERACTION,U.IMMEDIATE,
        'A chosen knot, lock or latch within Short Range.',
        'Undo it as though opened by a careful hand or matching key.',
        ('object_source','short_range','object_opening'),
        'The opening occurs on invocation; no ongoing duration is specified.'),
    PrayerDefinition(P.RICH_MAN_POOR_MAN_BEGGAR_THIEF,D.RANALD,'Rich Man, Poor Man, Beggar, Thief',146,E.DISGUISE,U.DEFAULT_IF_ONGOING,
        'Self; an optional Willpower Test includes one additional ally within Short Range per success.',
        'Appear to fit into the present social setting through dress, gait and manner, without changing actual Status.',
        ('social_setting','appearance','optional_willpower_test','short_range_allies'),_DEFAULT),
    PrayerDefinition(P.RANALDS_LUCK,D.RANALD,'Ranald’s Luck',146,E.TEMPORARY_FATE,U.SESSION,
        'The praying character at the beginning of the session, playing a game of chance with the GM.',
        'Winning provides one temporary Fate point that can be spent normally but never burned. '
        'The text supplies no automatic win or fixed probability for the game.',
        ('session_start','gm_game_result','temporary_spend_only_fate'),
        'One extra temporary point for that session; no rule grants this resource to an NPC.',
        timing=PrayerTiming.SESSION_START),
    PrayerDefinition(P.SHACKLES_OF_TRUTH,D.VERENA,'Shackles of Truth',147,E.TRUTH,U.CONDITIONAL,
        'A target within Short Range whose gaze is held.',
        'The target cannot speak a direct lie but need not answer or reveal the truth; omissions and verbal '
        'trickery remain possible.',
        ('short_range_target','gaze','spoken_truth'),
        'As long as the praying character holds the target’s gaze.'),
    PrayerDefinition(P.SWORD_OF_JUSTICE,D.VERENA,'Sword of Justice',147,E.WEAPON_BLESSING,U.DEFAULT_IF_ONGOING,
        'A sword the praying character is actually wielding; criminal status is determined by the GM.',
        'The sword ignores armour. A criminal actually Wounded by it becomes Defenceless or otherwise defeated; '
        'crimes against an unconscious criminal breach Verena’s Strictures.',
        ('held_sword_source','ignores_armour','actual_wound','gm_criminal_status','defenceless_or_defeat'),_DEFAULT),
    PrayerDefinition(P.TRUTH_WILL_OUT,D.VERENA,'Truth Will Out',147,E.SENSE,U.IMMEDIATE,
        'Deception around the praying character; no numeric Range is supplied.',
        'Immediately recognise deception, including speech, writings, magical illusions and miraculous tricks; '
        'this does not necessarily reveal the underlying truth.',
        ('deception_facts','illusions','miraculous_tricks','gm_information'),
        'Awareness of the present deception is immediate.'),
    PrayerDefinition(P.EAGLES_EYES,D.MYRMIDIA,'Eagle’s Eyes',148,E.SENSE,U.DEFAULT_IF_ONGOING,
        'A spectral eagle directed anywhere within one mile of the praying character’s current location.',
        'Summon the eagle and see through its eyes instead of one’s own while the Prayer is in effect.',
        ('spectral_eagle','remote_vision','mile_scale_scene','local_vision_replacement'),_DEFAULT),
    PrayerDefinition(P.BLAZING_SUN,D.MYRMIDIA,'Blazing Sun',148,E.BLINDING,U.END_OF_CASTER_NEXT_TURN,
        'Everyone else in the praying character’s Zone, including allies.',
        'Inflict Blinded on all those targets.',
        ('same_zone_targets','blinded','caster_turn_expiry'),
        'Until the end of the praying character’s next turn.'),
    PrayerDefinition(P.SHIELD_OF_MYRMIDIA,D.MYRMIDIA,'Shield of Myrmidia',148,E.RESILIENCE,U.END_OF_BATTLE,
        'Self and allies who remain within Short Range.',
        '+1 Resilience to self and qualifying nearby allies; range is an ongoing condition of the ally benefit.',
        ('resilience_bonus','dynamic_short_range_aura','battle_expiry'),_BATTLE),
    PrayerDefinition(P.BITTER_CARTHASIS,D.SHALLYA,'Bitter Carthasis',149,E.POISON_AND_DISEASE,U.CONDITIONAL,
        'Another individual whom the praying character touches.',
        'Test Endurance; each success cures one disease or counteracts one poison. A Complication '
        'transfers the symptoms to the praying character until dawn.',
        ('touch_other','endurance_test','poison_and_disease_sources','complication_transfer'),
        'The cure resolves immediately; transferred symptoms last until the following dawn.'),
    PrayerDefinition(P.MARTYR,D.SHALLYA,'Martyr',149,E.WOUND_TRANSFER,U.END_OF_BATTLE,
        'A chosen target within Long Range.',
        'Whenever that target would roll on the Wounds Table, the praying character rolls instead.',
        ('long_range_target','character_wound_table_transfer','recipient_wound_source','battle_expiry'),_BATTLE),
    PrayerDefinition(P.SHALLYAS_TEARS,D.SHALLYA,'Shallya’s Tears',149,E.HEALING,U.HEALING_OUTCOME,
        'A Wounded target within Close Range; the chosen injury is tracked independently.',
        'Test Willpower: 0 successes permits retry only after dawn; 1 grants healing after the next downtime '
        'without Rest and Recovery; 2 heals after one night; 3+ immediately heals one chosen Wound. '
        'Only one successful use per specific injury; a severed limb is not restored.',
        ('close_range_wounded_target','willpower_test','stable_injury_identity','per_injury_use_ledger',
            'downtime_or_night_healing','actual_healing','anatomical_loss_persistence'),
        '0: retry after next dawn; 1: next downtime; 2: one night; 3+: immediate healing.'),
)


DEITY_DEFINITIONS=(
    DeityDefinition(D.ULRIC,'Ulric',140,('Mountaineering',),(
        'Obey your betters.','Defend your honour and never refuse a challenge.',
        'Outside an ambush, do not employ trickery or deception.',
        'Wear only pelts of wolves slain with weapons crafted by your own hands.',
        'Do not follow the ways of blackpowder, helmets, crossbows or technology.'),
        'Ignore cold penalties; wolves recognise a fellow hunter/rival. Suffering a Wound in combat '
        'makes the next Melee attack in that battle Glorious.',
        (P.HOARFROSTS_CHILL,P.HOWL_OF_THE_WOLF,P.WINTERS_BITE),
        'GM-agreed aid or judgement through winter, wolves or battle-fury; examples are not a fixed numeric effect.'),
    DeityDefinition(D.TAAL,'Taal',141,('Woodcraft',),(
        'Pray for every animal taken.','Spend a week alone in the wilderness each year.',
        'Use hides rather than metal armour.','Rely on skill rather than gunpowder or technology.',
        'Harm animals only in self-defence, for food or for sacrifice.'),
        'Hunting, tracking and wilderness Stealth Tests are Glorious; always know when followed in the wild.',
        (P.LORD_OF_THE_WILD,P.STAGS_LEAP,P.TANGLEFOOT),
        'GM-agreed wilderness intervention such as travel through forests, summoning beasts or altering paths.'),
    DeityDefinition(D.RHYA,'Rhya',142,('Farming','Cooking'),(
        'Protect families, children and crops.','Do not be ashamed of the body Rhya gave you.',
        'Do harm only to save another life.','Share your bounty when you have enough.'),
        'A modest meal is enough for each day; know the most welcoming home in a settlement.',
        (P.RHYAS_SHELTER,P.RHYAS_HARVEST,P.RHYAS_CHILDREN),
        'GM-agreed nurturing intervention in food, fertility or the land; Rhya’s Miracles are never harmful.'),
    DeityDefinition(D.SIGMAR,'Sigmar',143,('History','Orc & Goblin Tribes'),(
        'Obey orders.','Aid Dwarfs and do not harm them.','Promote the Empire’s unity.',
        'Remain loyal to the Imperial throne.','Show no mercy to Orc-kind, dark-god worshippers or foul witches.'),
        'Once per battle remove Staggered on one’s own turn without an action; any wielded hammer inflicts +1 Damage.',
        (P.HAMMER_OF_SIGMAR,P.HEED_NOT_THE_WITCH,P.BEACON_OF_RIGHTEOUS_VIRTUE),
        'GM-agreed righteous intervention, such as a comet, rallying the faithful or empowering a hammer.'),
    DeityDefinition(D.MANANN,'Manann',144,('Waterways','Sailing'),(
        'Do not whistle or swear at sea or on holy ground.','Never harm an albatross.',
        'Give the first catch to Manann.','Offer silver and fish at each Manannite shrine passed.',
        'Hunt Stromfels’s servants wherever they hide.'),
        'No seasickness or drowning after falling into open water; wind/current eventually brings a castaway '
        'to a boat or dry land. Fish bare-handed without the missing-net/rod penalty.',
        (P.DROWNED_MANS_FACE,P.WINDS_FAIR_AND_FOUL,P.WATERWALK),
        'GM-agreed intervention involving seas, floods, winds or rivers; no universal damage is prescribed.'),
    DeityDefinition(D.MORR,'Morr',145,('The Undead',),(
        'Respect and honour the dead.','Do not harm ravens.','Hunt Necromancers and undead.',
        'Attend to dreams.','Do not interrupt a funeral or refuse to conduct one when ordained.',
        'Do not aid raising the dead without Morr’s permission.'),
        'Know when a person being spoken with is near death; touching a corpse reveals time since death; '
        'wielded weapons inflict +1 Damage against undead.',
        (P.LAST_RITES,P.STAY_MORRS_HAND,P.PORTALS_THRESHOLD),
        'GM-agreed intervention in death or dreams, including a shade’s answers or a hero’s final battle.'),
    DeityDefinition(D.RANALD,'Ranald',146,('Criminal Underworld',),(
        'Give one coin in ten to Ranald.','Never inform the authorities about another.',
        'Use violence only in self-defence.','Prefer freedom even at the cost of life.',
        'Act honourably towards fellow Ranaldans.'),
        'Always find gambling opportunities; fall Hazard is halved (no rounding rule printed); '
        'witnesses of nefarious activity cannot agree on the character’s exact description.',
        (P.AN_INVITATION,P.RICH_MAN_POOR_MAN_BEGGAR_THIEF,P.RANALDS_LUCK),
        'GM-agreed subtle coincidence or impossible luck; examples do not assign a fixed probability or effect.'),
    DeityDefinition(D.VERENA,'Verena',147,('Law',),(
        'Arbitrate disputes when asked.','Tell the truth without fear or favour.',
        'Protect knowledge.','Use combat only after other approaches fail.',
        'Do not serve injustice or heresy.'),
        'While speaking only truth, listeners know the statements are true but may draw their own conclusions; '
        'in a library know where to find the needed reference.',
        (P.SHACKLES_OF_TRUTH,P.SWORD_OF_JUSTICE,P.TRUTH_WILL_OUT),
        'GM-agreed revelation, lost knowledge or judgement on a known criminal.'),
    DeityDefinition(D.MYRMIDIA,'Myrmidia',148,('Military',),(
        'Act honourably and with dignity.','Respect prisoners and never kill a surrendering foe.',
        'Show no mercy to unrepentant enemies of humanity.','Obey honourable orders.',
        'Protect the weak from war.'),
        'While holding a shield do not count as outnumbered; any wielded spear inflicts +1 Damage.',
        (P.EAGLES_EYES,P.BLAZING_SUN,P.SHIELD_OF_MYRMIDIA),
        'GM-agreed strategic intervention, such as distant command or concealment of a war host.'),
    DeityDefinition(D.SHALLYA,'Shallya',149,('Anatomy','Concoction'),(
        'Help according to need without judgement.','Kill only in self-defence or against the Fly Lord’s followers.',
        'Hunt servants of gods of suffering and decay.','Avoid self-indulgence.',
        'Do not take up arms; a walking stick and courage suffice.'),
        'Most Human attackers prefer another available victim, not universal immunity. Tests to identify, '
        'treat or alleviate illness or injury are Glorious.',
        (P.BITTER_CARTHASIS,P.MARTYR,P.SHALLYAS_TEARS),
        'GM-agreed mercy can heal missing limbs if the victim lives and the body is mostly intact/together, '
        'or cure/protect a community; it cannot restore the dead.'),
)


_PRAYER_INDEX=MappingProxyType({entry.id:entry for entry in PRAYER_DEFINITIONS})
_DEITY_INDEX=MappingProxyType({entry.id:entry for entry in DEITY_DEFINITIONS})
if len(_PRAYER_INDEX)!=30 or set(_PRAYER_INDEX)!=set(PrayerId):
    raise RuntimeError('the Human Faith catalog must contain all thirty unique Prayers')
if len(_DEITY_INDEX)!=10 or set(_DEITY_INDEX)!=set(DeityId):
    raise RuntimeError('the Human Faith catalog must contain exactly the ten source deities')
if {id for deity in DEITY_DEFINITIONS for id in deity.prayer_ids}!=set(PrayerId):
    raise RuntimeError('each named Prayer must be assigned to its actual deity')
for _deity in DEITY_DEFINITIONS:
    if any(_PRAYER_INDEX[id].deity is not _deity.id or _PRAYER_INDEX[id].page!=_deity.page
            for id in _deity.prayer_ids):
        raise RuntimeError('Prayer and deity disagree on their actual book source')


def prayer_definition(id:PrayerId)->PrayerDefinition:
    if type(id) is not PrayerId:
        raise TypeError('Prayer lookup requires its exact typed identifier')
    return _PRAYER_INDEX[id]


def deity_definition(id:DeityId)->DeityDefinition:
    if type(id) is not DeityId:
        raise TypeError('deity lookup requires its exact typed identifier')
    return _DEITY_INDEX[id]


def prayers_for_deity(id:DeityId)->tuple[PrayerDefinition,...]:
    return tuple(prayer_definition(prayer) for prayer in deity_definition(id).prayer_ids)
