"""Pure shield equipment, hand policies and exact anatomical consequences."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.domain._pc_heavy_wound_projection import body_consequence, reconcile_clutch
from towr.domain.attack_models import ResilienceProfile
from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    WoundConsequence, WoundConsequenceRequest, WoundEntryId, WoundRecord,
    WoundRecordOrigin, WoundRestriction, WoundRestrictionEffect, WoundEffectDuration,
)
from towr.domain.pc_heavy_wound_models import PcBodyFact, PcBodyFactKind as Body
from towr.domain.pc_melee_models import (
    PcShieldHandConflictPolicy, PcShieldLoadout, PcShieldRecoveryPolicy, PcWeaponHand as Hand,
)
from towr.domain.pc_melee_result_models import (
    PcBodyConsequenceProof, initial_pc_melee_state,
)
from towr.domain.pc_shield_models import (
    PcShieldLocation as Location, PcShieldReleaseProof, PcShieldState,
    expected_pc_shield_release, initial_pc_shield, pc_defence_hand,
    pc_has_working_shield, pc_shield_recover_hand, pc_shield_recover_needed,
    pc_shield_resilience,
)
from towr.domain.test_models import Skill
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlot,
    CombatSide, CombatTurnState,
)


def shield_source():
    source = make_pc_melee_scenario()
    loadout = PcShieldLoadout(Hand.RIGHT,PcShieldHandConflictPolicy.WEAPON_FIRST,
        PcShieldRecoveryPolicy.RESTORE_BEFORE_ATTACK)
    return replace(source,party=(replace(source.party[0],shield=loadout),))


def shield_state():
    return initial_pc_melee_state(shield_source())


def wounded(member, *totals):
    entries = {4:WoundEntryId.NICKED_ARM,8:WoundEntryId.SHAKING_GRIP,
        12:WoundEntryId.SMASHED_HAND,16:WoundEntryId.SLASHED_FOREARMS,
        18:WoundEntryId.SPILLING_GUTS,20:WoundEntryId.SEVERED_ARM}
    records = tuple(WoundRecord(index,entries[total],total,(),effect_resolved=True,
        origin=WoundRecordOrigin.FIXED_ENTRY) for index,total in enumerate(totals,1))
    return replace(member,injury=replace(member.injury,wounds=records))


def consequence(member, kind, side, sequence=1):
    request = WoundConsequenceRequest(sequence,kind,'fixture:shield:body')
    die = None if kind is WoundConsequence.DROP_ONE_HAND_ITEM_AND_CLUTCH_STOMACH else (1 if side is Hand.LEFT else 10)
    return body_consequence(member,PcBodyConsequenceProof(request,die,side,1))


class M53ShieldCoreTests(unittest.TestCase):
    def test_initial_equipment_is_optional_and_exact(self):
        self.assertIsNone(initial_pc_shield(None))
        self.assertIsNone(initial_pc_melee_state(make_pc_melee_scenario()).party[0].shield)
        self.assertEqual(shield_state().party[0].shield,PcShieldState(Location.HELD,Hand.RIGHT))
        with self.assertRaises(TypeError):
            initial_pc_shield({'initial_hand':'right'})

    def test_location_and_release_proof_reject_equal_aliases_and_impossible_hands(self):
        for location,hand in (('held',Hand.RIGHT),(Location.HELD,'right'),
                (Location.UNAVAILABLE,None),(Location.DROPPED,Hand.RIGHT)):
            with self.subTest(location=location,hand=hand), self.assertRaises((TypeError,ValueError)):
                PcShieldState(location,hand)
        for args in (('pc','action','right'),('pc','',Hand.RIGHT),(1,'action',Hand.RIGHT)):
            with self.assertRaises(TypeError):
                PcShieldReleaseProof(*args)

    def test_resilience_uses_actual_working_equipment_and_authored_armour_once(self):
        state = shield_state()
        source = replace(state.source,party=(replace(state.source.party[0],
            pc=replace(state.source.party[0].pc,armour_bonus=2)),))
        state = replace(state,source=source)
        self.assertEqual(pc_shield_resilience(state,'pc'),ResilienceProfile(3,3))
        dropped = replace(state.party[0],shield=PcShieldState(Location.DROPPED,None))
        state = replace(state,party=(dropped,))
        self.assertEqual(pc_shield_resilience(state,'pc'),ResilienceProfile(3,2))
        bare = shield_state()
        self.assertTrue(pc_shield_resilience(bare,'pc').is_armoured)
        bare = replace(bare,party=(replace(bare.party[0],shield=PcShieldState(Location.DROPPED,None)),))
        self.assertFalse(pc_shield_resilience(bare,'pc').is_armoured)

    def test_defence_uses_actual_attack_skill_and_available_equipment(self):
        member = shield_state().party[0]
        self.assertIs(pc_defence_hand(member,Skill.MELEE),Hand.LEFT)
        self.assertIs(pc_defence_hand(member,Skill.THROWING),Hand.RIGHT)
        self.assertIsNone(pc_defence_hand(member,Skill.BRAWN))
        unarmed = replace(member,weapon_hand=None)
        self.assertIs(pc_defence_hand(unarmed,Skill.MELEE),Hand.RIGHT)
        dropped = replace(member,shield=PcShieldState(Location.DROPPED,None))
        self.assertIs(pc_defence_hand(dropped,Skill.MELEE),Hand.LEFT)
        self.assertIsNone(pc_defence_hand(dropped,Skill.THROWING))

    def test_unusable_lost_clutch_and_occupied_shield_hands_do_not_work(self):
        member = shield_state().party[0]
        for total,kind in ((16,Body.UNUSABLE_ARM),(20,Body.LOST_ARM),(18,Body.CLUTCH_STOMACH)):
            blocked = replace(wounded(member,total),body_facts=(PcBodyFact(kind,1,Hand.RIGHT),))
            self.assertFalse(pc_has_working_shield(blocked))
        self.assertFalse(pc_has_working_shield(replace(member,weapon_hand=Hand.RIGHT)))
        self.assertFalse(pc_has_working_shield(replace(member,shield=PcShieldState(Location.UNAVAILABLE,Hand.RIGHT))))

    def test_recover_uses_free_healthy_hand_after_weapon_priority(self):
        member = replace(shield_state().party[0],shield=PcShieldState(Location.DROPPED,None))
        self.assertIs(pc_shield_recover_hand(member),Hand.RIGHT)
        self.assertTrue(pc_shield_recover_needed(member))
        self.assertFalse(pc_shield_recover_needed(replace(member,weapon_hand=None)))
        self.assertIsNone(pc_shield_recover_hand(replace(member,shield=PcShieldState(Location.UNAVAILABLE,Hand.RIGHT))))
        self.assertIsNone(pc_shield_recover_hand(replace(member,shield=PcShieldState(Location.HELD,Hand.RIGHT))))

    def test_recover_never_reuses_injured_unusable_lost_or_clutch_hand(self):
        member = replace(shield_state().party[0],shield=PcShieldState(Location.DROPPED,None))
        for total,kind in ((12,Body.INJURED_HAND),(16,Body.UNUSABLE_ARM),
                (20,Body.LOST_ARM),(18,Body.CLUTCH_STOMACH)):
            blocked = wounded(member,total)
            if total==12:
                blocked = replace(blocked,injury=replace(blocked.injury,active_wound_effects=(
                    WoundRestrictionEffect(1,WoundRestriction.USING_INJURED_HAND_CAUSES_CRITICAL,
                        WoundEffectDuration.UNTIL_TREATED),)))
            blocked = replace(blocked,body_facts=(PcBodyFact(kind,1,Hand.RIGHT),))
            self.assertIsNone(pc_shield_recover_hand(blocked))
            self.assertFalse(pc_shield_recover_needed(blocked))
        for injury in (replace(member.injury,dead=True),replace(member.injury,
                conditions=member.injury.conditions.with_condition(Condition.DEFENCELESS))):
            self.assertIsNone(pc_shield_recover_hand(replace(member,injury=injury)))

    def test_random_drop_preserves_item_in_other_hand_for_rows_four_eight_twelve(self):
        for total in (4,8,12):
            for side in Hand:
                with self.subTest(total=total,side=side):
                    member = wounded(shield_state().party[0],total)
                    before = deepcopy(member)
                    changed = consequence(member,WoundConsequence.DROP_RANDOM_HAND_ITEM,side)
                    self.assertEqual(member,before)
                    self.assertIs(changed.weapon_hand,None if side is Hand.LEFT else Hand.LEFT)
                    self.assertEqual(changed.shield,PcShieldState(Location.DROPPED,None)
                        if side is Hand.RIGHT else member.shield)
                    self.assertEqual(changed.body_facts,(PcBodyFact(Body.INJURED_HAND,1,side),) if total==12 else ())

    def test_empty_selected_hand_does_not_drop_other_item(self):
        member = replace(wounded(shield_state().party[0],8),weapon_hand=None)
        changed = consequence(member,WoundConsequence.DROP_RANDOM_HAND_ITEM,Hand.LEFT)
        self.assertEqual(changed.shield,member.shield)
        member = replace(member,weapon_hand=Hand.LEFT,shield=PcShieldState(Location.DROPPED,None))
        changed = consequence(member,WoundConsequence.DROP_RANDOM_HAND_ITEM,Hand.RIGHT)
        self.assertIs(changed.weapon_hand,Hand.LEFT)

    def test_sixteen_twenty_mark_matching_shield_unavailable_without_ground_pickup(self):
        for total,kind in ((16,WoundConsequence.RANDOMISE_INJURED_ARM),
                (20,WoundConsequence.RANDOMISE_SEVERED_ARM)):
            for side in Hand:
                member = wounded(shield_state().party[0],total)
                changed = consequence(member,kind,side)
                self.assertEqual(changed.shield,PcShieldState(Location.UNAVAILABLE,Hand.RIGHT)
                    if side is Hand.RIGHT else member.shield)
                self.assertIsNone(pc_shield_recover_hand(changed))
                if side is Hand.RIGHT:
                    self.assertFalse(pc_has_working_shield(changed))
                self.assertIs(changed.weapon_hand,None if total==20 and side is Hand.LEFT else Hand.LEFT)

    def test_lost_arm_does_not_move_already_dropped_shield_to_unavailable(self):
        member = replace(wounded(shield_state().party[0],20),shield=PcShieldState(Location.DROPPED,None))
        changed = consequence(member,WoundConsequence.RANDOMISE_SEVERED_ARM,Hand.RIGHT)
        self.assertEqual(changed.shield,member.shield)

    def test_clutch_drops_shield_in_actual_nonweapon_hand(self):
        member = wounded(shield_state().party[0],18)
        changed = consequence(member,WoundConsequence.DROP_ONE_HAND_ITEM_AND_CLUTCH_STOMACH,Hand.RIGHT)
        self.assertEqual(changed.shield,PcShieldState(Location.DROPPED,None))
        self.assertIs(changed.weapon_hand,Hand.LEFT)
        self.assertEqual(changed.body_facts,(PcBodyFact(Body.CLUTCH_STOMACH,1,Hand.RIGHT),))
        self.assertFalse(pc_shield_recover_needed(changed))

    def test_clutch_relocation_drops_colliding_shield_without_third_hand(self):
        member = wounded(shield_state().party[0],18,16)
        member = replace(member,weapon_hand=None,body_facts=(
            PcBodyFact(Body.CLUTCH_STOMACH,1,Hand.LEFT),PcBodyFact(Body.UNUSABLE_ARM,2,Hand.LEFT)))
        changed = reconcile_clutch(member)
        self.assertEqual(changed.shield,PcShieldState(Location.DROPPED,None))
        self.assertIn(PcBodyFact(Body.CLUTCH_STOMACH,1,Hand.RIGHT),changed.body_facts)
        self.assertIsNone(pc_shield_recover_hand(changed))

    def test_clutch_relocation_without_any_arm_preserves_defenceless_consequence(self):
        member = wounded(shield_state().party[0],18,16,20)
        member = replace(member,weapon_hand=None,shield=PcShieldState(Location.UNAVAILABLE,Hand.RIGHT),
            body_facts=(PcBodyFact(Body.CLUTCH_STOMACH,1,Hand.LEFT),
                PcBodyFact(Body.UNUSABLE_ARM,2,Hand.LEFT),PcBodyFact(Body.LOST_ARM,3,Hand.RIGHT)))
        changed = reconcile_clutch(member)
        self.assertTrue(changed.injury.conditions.has(Condition.DEFENCELESS))
        self.assertFalse(any(f.kind is Body.CLUTCH_STOMACH for f in changed.body_facts))
        self.assertEqual(changed.shield,member.shield)

    def test_release_is_only_own_unreserved_healthy_weapon_first_conflict(self):
        state = shield_state()
        member = wounded(state.party[0],16)
        member = replace(member,body_facts=(PcBodyFact(Body.UNUSABLE_ARM,1,Hand.LEFT),))
        state = replace(state,party=(member,),round_state=replace(state.round_state,
            active_turn=CombatTurnState('pc',CombatSide.PLAYERS_AND_ALLIES)))
        self.assertEqual(expected_pc_shield_release(state),
            PcShieldReleaseProof('pc','pc-melee:r1:pc:shield:release',Hand.RIGHT))
        healthy = replace(state,party=(shield_state().party[0],))
        self.assertIsNone(expected_pc_shield_release(healthy))
        self.assertIsNone(expected_pc_shield_release(replace(state,round_state=replace(state.round_state,active_turn=None))))
        defenceless = replace(member,injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.DEFENCELESS)))
        self.assertIsNone(expected_pc_shield_release(replace(state,party=(defenceless,))))
        dead = replace(member,injury=replace(member.injury,dead=True))
        self.assertIsNone(expected_pc_shield_release(replace(state,party=(dead,))))
        reserved = CombatActionSlot(1,CombatActionDeclaration(CombatActionKind.RECOVER),ActionSlotGrant.STANDARD)
        self.assertIsNone(expected_pc_shield_release(replace(state,round_state=replace(state.round_state,
            active_turn=replace(state.round_state.active_turn,action_slots=(reserved,))))))
        self.assertIsNone(expected_pc_shield_release(replace(state,round_state=replace(state.round_state,
            completed_turn_entity_ids=('pc',),active_turn=CombatTurnState('minion1',CombatSide.OPPOSITION)))))
        request = WoundConsequenceRequest(1,WoundConsequence.RANDOMISE_INJURED_ARM,'fixture:pending')
        self.assertIsNone(expected_pc_shield_release(replace(state,pending=(request,),pending_actor_id='pc')))

    def test_drop_rejects_changed_actual_die_side_and_count(self):
        member = wounded(shield_state().party[0],8)
        request = WoundConsequenceRequest(1,WoundConsequence.DROP_RANDOM_HAND_ITEM,'fixture:drop')
        for die,side,count in ((True,Hand.LEFT,1),(10,Hand.LEFT,1),(1,'left',1),(1,Hand.LEFT,True),
                (1,Hand.LEFT,2)):
            with self.subTest(die=die,side=side,count=count), self.assertRaises((TypeError,ValueError)):
                body_consequence(member,PcBodyConsequenceProof(request,die,side,count))

    def test_no_shield_uses_original_weapon_only_body_changes(self):
        member = wounded(initial_pc_melee_state(make_pc_melee_scenario()).party[0],8)
        self.assertEqual(consequence(member,WoundConsequence.DROP_RANDOM_HAND_ITEM,Hand.RIGHT),member)
        self.assertEqual(consequence(member,WoundConsequence.DROP_RANDOM_HAND_ITEM,Hand.LEFT),
            replace(member,weapon_hand=None))


if __name__ == '__main__':
    unittest.main()
