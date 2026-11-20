"""Real treatment/suppression receipts reach equipment consumers without healing.

The explicit boundary states below contain already resolved table Wounds;
medical actions and their follow-ups use the actual native proof projection.
"""
from dataclasses import replace
from unittest import TestCase

from tests.helpers import SequenceRandom
from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.talent_sources import paid_talent
from towr.domain.armour_models import ArmourLoadout,ShieldKind
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon
from towr.domain.injury_models import (CharacterInjuryState,WoundRecord,WoundEntryId,
    WoundConditionEffect,WoundRestrictionEffect,WoundRestriction,WoundEffectDuration)
from towr.domain.medical_preparation_models import MedicalPreparationFacts
from towr.domain.pc_heavy_wound_models import PcBodyFact,PcBodyFactKind,usable_hands
from towr.domain.pc_melee_models import (PcMeleeWeapon,PcWeaponHand,PcShieldLoadout,
    PcShieldHandConflictPolicy,PcShieldRecoveryPolicy,PcTwoHandedGrip)
from towr.domain.pc_melee_result_models import initial_pc_melee_state,PcFateDecline
from towr.domain.pc_medical_models import (build_medical_treatment,complete_medical_treatment,
    expected_medical_treatment_application,expected_medical_suppression,complete_medical_suppression,
    PcMedicalTreatmentProof,PcMedicalTreatmentApplicationProof,PcMedicalSuppressionProof,
    medical_effective_body,medical_suppressions)
from towr.domain._pc_medical_projection import project_medical_step
from towr.domain.pc_shield_models import pc_has_working_shield,pc_shield_resilience
from towr.domain.pc_weapon_inventory import pc_attack_weapon_use
from towr.domain.pc_npc_weapon_inventory import npc_attack_weapon_use,npc_has_working_shield
from towr.domain.pc_npc_resilience_models import npc_current_resilience
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.talent_catalog import TalentId
from towr.domain.tool_inventory_models import ToolItemSource,ToolKind
from towr.domain.turn_models import (CombatSide,CombatActionKind,CombatTurnStartRequest,
    CombatActionSlotRequest,CombatActionDeclaration,ActionSlotGrant)
from towr.domain.weapon_inventory_models import WeaponItemLocation
from towr.rules.turn_resolution import start_combat_turn,reserve_combat_action_slot
from towr.rules.recover_resolution import apply_recover_wound_treatment
from towr.rules.test_resolution import resolve_test


def _append(state,proof):
    return replace(state,**project_medical_step(state,proof),history=(*state.history,proof))


def _source(*,two_handed=False):
    source=make_pc_melee_party_scenario(pc_count=2,enemy_count=2)
    surgeon,patient=source.party
    medical=MedicalPreparationFacts(True,True,True)
    kit=(ToolItemSource('kit',ToolKind.PHYSICKERS_KIT,1,WeaponItemLocation.CARRIED,None),)
    surgeon=replace(surgeon,pc=replace(surgeon.pc,weapon=PcMeleeWeapon.SWORD,reason=3,recall=6,
        initiative=3,dexterity=5,medical=medical,tools=kit),initial_weapon_hand=PcWeaponHand.LEFT,
        talents=(paid_talent(TalentId.COMBAT_SURGEON),))
    shield=PcShieldLoadout(PcWeaponHand.RIGHT,PcShieldHandConflictPolicy.WEAPON_FIRST,
        PcShieldRecoveryPolicy.RESTORE_BEFORE_ATTACK)
    patient=replace(patient,pc=replace(patient.pc,weapon=PcMeleeWeapon.SWORD),
        initial_weapon_hand=PcWeaponHand.LEFT,shield=shield)
    if two_handed:
        patient=replace(patient,pc=replace(patient.pc,weapon=PcMeleeWeapon.GREATAXE),
            initial_weapon_hand=PcTwoHandedGrip.BOTH,shield=None)
    medic=GeneratedNpc(3,3,3,3,5,4,initial_generated_weapons(GeneratedWeapon.SWORD),ArmourLoadout(),
        defence=4,reason=3,recall=6,initiative=3,dexterity=5,medical=medical,tools=kit,
        talents=(paid_talent(TalentId.COMBAT_SURGEON),))
    champion=GeneratedNpc(3,3,3,3,5,4,initial_generated_weapons(GeneratedWeapon.SWORD),
        ArmourLoadout(shield=ShieldKind.SHIELD),defence=4,endurance=4,
        injury_policy=TargetInjuryPolicy.CHAMPION)
    if two_handed:
        champion=replace(champion,weapons=initial_generated_weapons(GeneratedWeapon.GREATAXE),armour=ArmourLoadout())
    return replace(source,party=(surgeon,patient),enemies=(medic.participant('minion1'),champion.participant('minion2')))


def _wounded_state(*,npc=False,permanent=False,two_handed=False):
    state=initial_pc_melee_state(_source(two_handed=two_handed))
    actor,target=('minion1','minion2') if npc else ('pc1','pc2')
    injury=CharacterInjuryState((WoundRecord(1,WoundEntryId.SLASHED_FOREARMS,16,(10,6),effect_resolved=True),),
        ConditionState(frozenset((Condition.CRITICALLY_INJURED,))),(
            WoundConditionEffect(1,Condition.CRITICALLY_INJURED,WoundEffectDuration.UNTIL_TREATED),
            WoundRestrictionEffect(1,WoundRestriction.INJURED_ARM_UNUSABLE,WoundEffectDuration.UNTIL_HEALED)))
    facts=(PcBodyFact(PcBodyFactKind.UNUSABLE_ARM,1,PcWeaponHand.RIGHT),)
    if permanent:
        injury=replace(injury,wounds=(*injury.wounds,
            WoundRecord(2,WoundEntryId.SEVERED_ARM,20,(10,10),treated=True,effect_resolved=True)),
            active_wound_effects=(*injury.active_wound_effects,
                WoundRestrictionEffect(2,WoundRestriction.ARM_LOST,WoundEffectDuration.PERMANENT)))
        facts=(*facts,PcBodyFact(PcBodyFactKind.LOST_ARM,2,PcWeaponHand.LEFT))
    if npc:
        from towr.domain.pc_npc_champion_models import npc_champion_updates
        state=replace(state,**npc_champion_updates(state,target,injury=injury,body_facts=facts))
        # A prepared opposition-side turn; it does not grant an extra action.
        clock=replace(state.round_state,side_order=(CombatSide.OPPOSITION,CombatSide.PLAYERS_AND_ALLIES))
    else:
        state=replace(state,party=tuple(replace(m,injury=injury,body_facts=facts) if m.actor_id==target else m for m in state.party))
        clock=state.round_state
    clock=start_combat_turn(CombatTurnStartRequest('medical:turn',clock,actor)).state
    clock=reserve_combat_action_slot(CombatActionSlotRequest('medical:reserve',clock,actor,
        CombatActionDeclaration(CombatActionKind.RECOVER),ActionSlotGrant.STANDARD)).state
    return replace(state,round_state=clock),actor,target,injury


def _suppress(state,actor,target):
    request=build_medical_treatment(state,target,1)
    state=_append(state,PcMedicalTreatmentProof(request,complete_medical_treatment(request)))
    pending=expected_medical_treatment_application(state)
    state=_append(state,PcMedicalTreatmentApplicationProof(apply_recover_wound_treatment(pending)))
    request=expected_medical_suppression(state)
    test=resolve_test(request.recall_test,SequenceRandom([1]*20))
    decline=(PcFateDecline(actor,request.recall_test.id,'test',state.source.participant(actor).fate_policy)
        if actor in state.source.pc_activation_order else None)
    proof=PcMedicalSuppressionProof(request,complete_medical_suppression(request,test),decline)
    return _append(state,proof),proof


class MedicalEffectiveConsumersTests(TestCase):
    def test_actual_pc_suppression_restores_shield_hand_and_resilience_without_healing(self):
        state,actor,target,injury=_wounded_state()
        self.assertFalse(pc_has_working_shield(medical_effective_body(state,target)))
        before=pc_shield_resilience(state,target)
        final,proof=_suppress(state,actor,target)
        body=medical_effective_body(final,target)
        self.assertEqual(usable_hands(body),(PcWeaponHand.LEFT,PcWeaponHand.RIGHT))
        self.assertTrue(pc_has_working_shield(body))
        self.assertEqual(pc_shield_resilience(final,target).total,before.total+1)
        self.assertIsNotNone(pc_attack_weapon_use(final,target))
        self.assertEqual(body.injury.wounds[0],replace(injury.wounds[0],treated=True))
        self.assertFalse(body.injury.wounds[0].healed)
        self.assertEqual(medical_suppressions(final).suppressions,(proof.result.suppression,))
        self.assertIn(injury.active_wound_effects[-1],proof.result.suppression.suppressed_effects)

    def test_actual_champion_suppression_reaches_npc_shield_and_equipment_consumers(self):
        state,actor,target,injury=_wounded_state(npc=True)
        self.assertFalse(npc_has_working_shield(state,target))
        before=npc_current_resilience(state,target)
        final,proof=_suppress(state,actor,target)
        self.assertTrue(npc_has_working_shield(final,target))
        self.assertEqual(npc_current_resilience(final,target).total,before.total+1)
        self.assertIsNotNone(npc_attack_weapon_use(final,target))
        self.assertEqual(final.enemy(target).state.injury.wounds[0],replace(injury.wounds[0],treated=True))
        self.assertFalse(hasattr(medical_effective_body(final,target),'fate'))
        self.assertIsNone(proof.decline)

    def test_actual_suppression_reenables_two_handed_weapon_for_pc_and_champion(self):
        for npc in (False,True):
            with self.subTest(npc=npc):
                state,actor,target,injury=_wounded_state(npc=npc,two_handed=True)
                query=npc_attack_weapon_use if npc else pc_attack_weapon_use
                self.assertIsNone(query(state,target))
                final,_=_suppress(state,actor,target)
                use=query(final,target)
                self.assertIsNotNone(use)
                self.assertEqual(len(use.used_hands),2)
                self.assertFalse(medical_effective_body(final,target).injury.wounds[0].healed)

    def test_suppression_does_not_restore_permanently_severed_hand_or_erase_its_record(self):
        state,actor,target,injury=_wounded_state(permanent=True)
        final,_=_suppress(state,actor,target)
        body=medical_effective_body(final,target)
        self.assertEqual(usable_hands(body),(PcWeaponHand.RIGHT,))
        self.assertIn(PcBodyFact(PcBodyFactKind.LOST_ARM,2,PcWeaponHand.LEFT),body.body_facts)
        self.assertIn(injury.active_wound_effects[-1],body.injury.active_wound_effects)
        self.assertEqual(body.injury.wounds[1],injury.wounds[1])
