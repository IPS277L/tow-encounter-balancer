"""Complete typed K1 receipts at prepared companion-source boundaries.

The independent NPC bodies are canonical immutable mount sources. These tests
do not claim native retention, target availability, tactical intent admission
or full encounter replay; the caller owns those separate boundaries.
"""
from copy import copy, deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.support.magic_weapon_battles import magic_battle
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.attack_models import AttackRequest, DamageImpactSpec, DamageProfile
from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    FixedWoundSelection, HEADSMAN_DECAPITATION_RULE_ID, MinionStaggerDefeatOutcome,
    MinionStaggerDefeatSpec, WoundEntryId,
)
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.pc_actor_models import pc_actor_inventory, pc_actor_npc_snapshot, pc_actor_npc_update
from towr.domain.pc_magic_weapon_models import (
    magic_weapon_intent_facts, pc_profile_wound_decision, prepare_magic_weapon_attack,
)
from towr.domain.pc_melee_result_models import PcAttackProof, PcMeleeState, PcMinionStaggerDefeatProof, initial_pc_melee_state
from towr.domain.pc_melee_models import PcMeleeScenario
from towr.domain.pc_minion_defeat_models import validate_pc_minion_defeat_equipment
from towr.domain.pc_mount_models import CombatMount, RiderKind
from towr.domain.pc_npc_ability_models import pc_npc_stagger_defeat_spec
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc
from towr.domain.pc_weapon_intent_models import PcAttackWeaponIntent
from towr.domain.protection_models import ProtectionPreparationRequest, ProtectionTestOption
from towr.domain.resolution_models import KernelAttackRequest
from towr.domain.test_models import InlineProfile, QualityModifier, Skill, TestQuality, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundState, CombatSide, CombatTurnParticipant, CombatTurnStartRequest,
)
from towr.domain.undead_minion_models import UndeadMinionSource, undead_minion_stagger_defeat_spec
from towr.domain.weapon_use_models import build_weapon_use
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.protection_preparation import prepare_protection
from towr.rules.turn_resolution import reserve_combat_action_slot, start_combat_turn


class Preparation(SimpleNamespace):
    participant = PcMeleeState.participant
    enemy = PcMeleeState.enemy
    live_party = PcMeleeState.live_party
    live_enemies = PcMeleeState.live_enemies
    exited_npc_ids = PcMeleeState.exited_npc_ids


class PreparedSource(SimpleNamespace):
    participant = PcMeleeScenario.participant
    enemy = PcMeleeScenario.enemy


def prepared(*, kind=CombatMount.SKELETAL_STEED, goblin=False, weapon='staff'):
    battle = magic_battle(weapon, npc_magic=weapon!='staff', pc_weapon=weapon,
        pc_toughness=3, npc_toughness=3, pc_strength=6)
    rider = RiderKind.HUMAN if kind in (CombatMount.PEGASUS, CombatMount.DEMIGRYPH) else None
    member = replace(battle.party[0], mount=kind, rider_kind=rider,
        defeat_decisions=tuple(replace(decision, disposition=NpcDefeatDisposition.KNOCKED_OUT)
            for decision in battle.party[0].defeat_decisions))
    generated = replace(battle.enemies[0].definition.generated_components, mount=kind, rider_kind=rider)
    enemies = (generated.participant(battle.enemies[0].state.actor_id),)
    battle = replace(battle, party=(member,), enemies=enemies,
        enemy_activation_order=tuple(row.state.actor_id for row in enemies),
        facts=replace(battle.facts, unmounted=False))
    actual = initial_pc_melee_state(battle)
    state = Preparation(**{name: getattr(actual, name) for name in actual.__dataclass_fields__})
    if goblin:
        # This deliberately mixed prepared roster is NOT admitted by the native
        # public family, which currently excludes book NPCs from a battlefield.
        # Canonical immutable profiles isolate this validator's cross-source bug.
        enemy = create_pc_book_npc(PcBookNpcProfile.GOBLIN_WARRIOR_SPEAR, 'actual:goblin')
        member = replace(member, target_priority=(*member.target_priority, enemy.state.actor_id),
            defeat_decisions=(*member.defeat_decisions, MinionDefeatDecision(member.actor_id,
                enemy.state.actor_id, NpcDefeatDisposition.KNOCKED_OUT, True)))
        values = {name: getattr(battle, name) for name in battle.__dataclass_fields__}
        values.update(party=(member,), enemies=(*battle.enemies, enemy),
            enemy_activation_order=(*battle.enemy_activation_order, enemy.state.actor_id))
        state.source = PreparedSource(**values)
        state.enemies = (*state.enemies, enemy)
    return state


def struck(state, *, ally_target=False, original_target=None, stagger=False, outcome=None, decapitate=False):
    pc = state.source.pc_activation_order[0]
    npc = state.source.enemy_activation_order[0]
    actor = npc if ally_target else pc
    target = original_target or (pc if ally_target else npc) + ':mount'
    snapshot = pc_actor_npc_snapshot(state, target)
    conditions = snapshot.state.injury.conditions
    if stagger:
        conditions = conditions.with_condition(Condition.STAGGERED)
    if decapitate:
        conditions = conditions.with_condition(Condition.PRONE)
    body = replace(snapshot.state.injury, conditions=conditions)
    side = CombatSide.OPPOSITION if ally_target else CombatSide.PLAYERS_AND_ALLIES
    other = CombatSide.PLAYERS_AND_ALLIES if ally_target else CombatSide.OPPOSITION
    clock = CombatRoundState(2, (CombatTurnParticipant(actor, side), CombatTurnParticipant(target, other)),
        side_order=(side, other))
    clock = start_combat_turn(CombatTurnStartRequest('prepared:start', clock, actor)).state
    clock = reserve_combat_action_slot(CombatActionSlotRequest('prepared:slot', clock, actor,
        CombatActionDeclaration(CombatActionKind.ATTACK), ActionSlotGrant.STANDARD)).state
    identifier = 'prepared:attack:' + target
    quality = (QualityModifier(HEADSMAN_DECAPITATION_RULE_ID, TestQuality.GRIM),) if decapitate else ()
    attack = AttackRequest(identifier, TestRequest(identifier+':a', InlineProfile(1, 3), quality_modifiers=quality),
        None, DamageImpactSpec(DamageProfile(1 if stagger else 8), snapshot.state.current_resilience),
        True, False)
    protection_profile = snapshot.definition.protection[0]
    defender = TestRequest(identifier+':d', protection_profile.test_profile)
    protection = prepare_protection(ProtectionPreparationRequest(identifier+':protection', target, attack,
        Skill.MELEE, True, False, snapshot.state.wields_weapon, snapshot.state.holds_shield,
        protection_profile.skill, (ProtectionTestOption(target, protection_profile.skill, defender),)))
    spec = None
    if stagger:
        spec = (pc_npc_stagger_defeat_spec(snapshot.definition) if original_target else
            undead_minion_stagger_defeat_spec(UndeadMinionSource(target), target))
        if outcome is not None:
            spec = replace(spec, outcome=outcome)
    kernel = KernelAttackRequest(identifier+':kernel', target, protection.attack,
        snapshot.definition.injury_policy, body, False, False,
        physical_attack=True, minion_stagger_defeat=spec,
        fixed_character_wound=(FixedWoundSelection(WoundEntryId.DECAPITATION, 27,
            HEADSMAN_DECAPITATION_RULE_ID) if decapitate else None))
    request = AttackActionExecutionRequest(identifier+':execute', clock, actor, target, 1, kernel)
    inventory = pc_actor_inventory(state, actor)
    use = build_weapon_use(actor, inventory, inventory.items[0].id)
    # Visibility and single-combat queries are independent preparation owners;
    # their values here are explicit context facts, not native target admission.
    with patch('towr.domain.pc_magic_weapon_models._weapon_target_visible', return_value=True), \
            patch('towr.domain.pc_magic_weapon_models.single_combat_active', return_value=False):
        context, fire = magic_weapon_intent_facts(state, actor, target, use)
    intent = PcAttackWeaponIntent(identifier+':execute', actor, target, Skill.MELEE, use,
        protection_profile.skill, None, protection_profile, magic_context=context, dragon_fire=fire)
    rng = ScriptedD10([1]*(2 if decapitate else 1)+[10]*defender.profile.base_dice)
    execution = execute_attack_action(request, rng)
    rng.assert_exhausted()
    return PcAttackProof(request, protection, execution, None, weapon_intent=intent)


def after_impact(state, proof, *, acknowledge=True):
    changed = copy(state)
    result = proof.execution.resolution
    target = proof.request.target_id
    updates = pc_actor_npc_update(state, target, injury=result.target_state)
    for name, value in updates.items():
        setattr(changed, name, value)
    receipt = result.minion_stagger_defeat
    changed.history = (proof,)
    changed.pending = result.follow_ups
    if receipt is not None and acknowledge:
        ack = PcMinionStaggerDefeatProof(receipt.cause)
        changed.history = (*changed.history, ack)
        changed.pending = ()
        if target in changed.source.enemy_activation_order:
            changed.enemies = tuple(replace(row, state=replace(row.state,
                wields_weapon=False, available_attack_ids=())) if row.state.actor_id == target else row
                for row in changed.enemies)
    return changed


class CompanionProfileContinuationTests(unittest.TestCase):
    def test_ordinary_companion_defeat_has_no_invented_gm_disposition_for_either_side(self):
        for ally in (False, True):
            state = prepared()
            proof = struck(state, ally_target=ally)
            with self.subTest(ally=ally):
                self.assertTrue(proof.execution.resolution.target_state.defeated)
                self.assertIsNone(pc_profile_wound_decision(state, proof))
                self.assertEqual(proof.execution.resolution.profile_wound.wounds_inflicted, 1)

    def test_original_pc_to_source_npc_preserves_its_explicit_knockout_decision(self):
        state = prepared()
        target = state.source.enemy_activation_order[0]
        proof = struck(state, original_target=target)
        self.assertEqual(pc_profile_wound_decision(state, proof),
            state.source.party[0].defeat_decision(target))
        self.assertIs(pc_profile_wound_decision(state, proof).disposition, NpcDefeatDisposition.KNOCKED_OUT)

    def test_actual_companion_decapitation_is_mandatory_killed_with_real_actor_and_target(self):
        for ally in (False, True):
            state = prepared(kind=CombatMount.PEGASUS, weapon='headsmans_axe')
            proof = struck(state, ally_target=ally, decapitate=True)
            with self.subTest(ally=ally):
                self.assertEqual(pc_profile_wound_decision(state, proof), MinionDefeatDecision(
                    proof.request.actor_id, proof.request.target_id, NpcDefeatDisposition.KILLED, True))
                self.assertEqual(proof.execution.resolution.target_state.wounds, 1)
                self.assertEqual(proof.execution.resolution.target_state.wound_limit, 2)
                forged = deepcopy(proof)
                object.__setattr__(forged.execution.resolution.target_state.defeat_cause, 'target_id', 'foreign')
                with self.assertRaises(ValueError):
                    pc_profile_wound_decision(state, forged)
                forged = deepcopy(proof)
                object.__setattr__(forged.request, 'actor_id', 'foreign')
                with self.assertRaises(ValueError):
                    pc_profile_wound_decision(state, forged)

    def test_destroyed_companion_is_not_a_goblin_fleeing_drop_even_when_goblin_is_present(self):
        for goblin in (False, True):
            for ally in (False, True):
                state = prepared(goblin=goblin)
                proof = struck(state, ally_target=ally, stagger=True)
                after = after_impact(state, proof)
                with self.subTest(goblin=goblin, ally=ally):
                    self.assertIs(proof.execution.resolution.target_state.defeat_cause.outcome,
                        MinionStaggerDefeatOutcome.DESTROYED)
                    self.assertEqual(proof.execution.resolution.target_state.wounds, 0)
                    validate_pc_minion_defeat_equipment(after)
                    self.assertEqual(after.enemies, state.enemies)
                    self.assertEqual(after.party, state.party)

    def test_acknowledgement_requires_exact_source_once_or_one_pending_cause(self):
        state = prepared(goblin=True)
        proof = struck(state, stagger=True)
        waiting = after_impact(state, proof, acknowledge=False)
        validate_pc_minion_defeat_equipment(waiting)
        complete = after_impact(state, proof)
        for history, pending in ((complete.history+(complete.history[-1],), ()),
                (tuple(reversed(complete.history)), ()), (waiting.history, ()),
                (complete.history, waiting.pending), (waiting.history, waiting.pending*2)):
            with self.subTest(history=history, pending=pending), self.assertRaises(ValueError):
                malformed = copy(complete)
                malformed.history, malformed.pending = history, pending
                validate_pc_minion_defeat_equipment(malformed)

    def test_wrong_outcome_kind_cached_spec_or_target_cannot_borrow_undead_source(self):
        state = prepared()
        proof = struck(state, stagger=True, outcome=MinionStaggerDefeatOutcome.FLED)
        with self.assertRaises(ValueError):
            validate_pc_minion_defeat_equipment(after_impact(state, proof))
        living = prepared(kind=CombatMount.HORSE)
        proof = struck(living, stagger=True)
        with self.assertRaises(ValueError):
            validate_pc_minion_defeat_equipment(after_impact(living, proof))
        state = prepared()
        proof = struck(state, stagger=True)
        malformed = after_impact(state, proof)
        object.__setattr__(proof.request.kernel_request.minion_stagger_defeat, 'outcome', 'destroyed')
        with self.assertRaises(TypeError):
            validate_pc_minion_defeat_equipment(malformed)

    def test_original_goblin_fleeing_receipt_keeps_its_own_equipment_drop(self):
        state = prepared(goblin=True)
        proof = struck(state, original_target='actual:goblin', stagger=True)
        after = after_impact(state, proof)
        validate_pc_minion_defeat_equipment(after)
        self.assertIs(proof.execution.resolution.target_state.defeat_cause.outcome, MinionStaggerDefeatOutcome.FLED)
        self.assertFalse(after.enemy('actual:goblin').state.wields_weapon)
        self.assertTrue(after.enemy('actual:goblin').state.holds_shield)
        self.assertEqual(after.companions, state.companions)

    def test_magic_context_and_scarab_charge_keep_companion_profile_role(self):
        state = prepared(weapon='scarab_knife')
        proof = struck(state)
        self.assertFalse(proof.weapon_intent.magic_context.target_is_pc_or_champion)
        receipt = prepare_magic_weapon_attack(state, proof.request, proof.execution, proof.weapon_intent)
        self.assertIsNotNone(receipt.scarab_charge)
        self.assertEqual(receipt.scarab_charge.profile_request.npc_type.value, 'minion')
        item = proof.weapon_intent.attack_use.primary_item_id
        self.assertEqual(receipt.after_inventory.item(item).charges,
            proof.weapon_intent.attack_use.inventory.item(item).charges+1)
        self.assertIsNone(pc_actor_inventory(state, proof.request.target_id))


if __name__ == '__main__':
    unittest.main()
