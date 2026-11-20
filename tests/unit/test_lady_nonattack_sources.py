"""Real non-Attack rule receipts over explicit prepared native observations.

Talent ownership and blessing resources are initialised from complete sources.
Prepared injury/task boundaries isolate these continuations; they do not claim
an invented complete Casting, Oil or aerial-dismount journal.
"""
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.oath_sources import lady
from tests.support.pc_magic_scenarios import magic_scenario
from tests.unit.test_pc_falling import view as falling_view
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.armour_models import ArmourLoadout
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon
from towr.domain.injury_models import ProfileInjuryState, WoundEntryId, FixedWoundTableSelection
from towr.domain.oath_context_models import OathBattleContext
from towr.domain.pc_actor_models import pc_actor_injury
from towr.domain.pc_falling_models import (
    expected_pc_falling_request, falling_hazard_request, _canonical_hazard as falling_canonical,
)
from towr.domain.pc_magic_miscast_plan import PcMagicTask, PcMagicTaskKind
from towr.domain.pc_magic_models import (
    PcMagicPending, build_magic_effect, project_pc_magic_step,
)
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.domain.pc_oath_models import (
    LadyWoundDecisions, actor_oath, initial_pc_oaths, lady_wound_rule, project_oath_aftermath,
)
from towr.domain.pc_warped_form_models import (
    PcWarpedFormActivationProof, PcWarpedFormTargetProof, WarpedFormDecisions,
    canonical_warped_form_impact, next_warped_form_target,
)
from towr.domain.pc_weapon_area_models import (
    ABLAZE_HAZARD_RULE_ID, BLAST_IMPACT_RULE_ID, PcWeaponHazardProof, _hazard_request,
    _canonical_hazard as area_canonical, weapon_hazard_resolution_request,
)
from towr.domain.talent_catalog import TalentId
from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleRollResult
from towr.rules.hazard_resolution import resolve_hazard
from towr.rules.stagger_impact_resolution import resolve_stagger_impact
from towr.rules.test_resolution import resolve_test


class AllTens:
    def randint(self, lower, upper):
        if (lower, upper) != (1, 10):
            raise AssertionError('this rule path only rolls actual d10s')
        return 10


def grant_context(actor):
    return OathBattleContext('gm:' + actor, True, lady_prayer_before_battle_confirmed=True)


def with_injury(state, actor, injury):
    if actor in state.source.pc_activation_order:
        return replace(state, party=tuple(replace(member, injury=injury)
            if member.actor_id == actor else member for member in state.party))
    return replace(state, enemies=tuple(replace(enemy, state=replace(enemy.state, injury=injury))
        if enemy.state.actor_id == actor else enemy for enemy in state.enemies))


def prepared():
    source = magic_scenario(reason=2, willpower=4, enemies=1)
    member = replace(source.party[0], talents=(*source.party[0].talents, lady(free=True)),
        oath_context=grant_context('pc1'))
    npc = GeneratedNpc(3, 3, 3, 3, 4, 4, initial_generated_weapons(GeneratedWeapon.STAFF), ArmourLoadout(),
        talents=(lady(free=True),), oath_context=grant_context('minion1'), endurance=4, defence=4)
    source = replace(source, party=(member,), enemies=(npc.participant('minion1'),))
    state = initial_pc_melee_state(source)
    for actor in ('pc1', 'minion1'):
        injury = pc_actor_injury(state, actor)
        state = with_injury(state, actor, replace(injury,
            conditions=injury.conditions.with_condition(Condition.STAGGERED)))
    return state


class LadyNonAttackSourceTests(unittest.TestCase):

    def test_ablaze_and_blast_bind_current_actor_resource_and_cancel_before_wound_consequences(self):
        for actor in ('pc1', 'minion1'):
            for rule in (ABLAZE_HAZARD_RULE_ID, BLAST_IMPACT_RULE_ID):
                with self.subTest(actor=actor, rule=rule):
                    before = prepared()
                    # A rating-one exposure isolates full cancellation; source
                    # Hazard rating is explicit rather than a fake Test result.
                    request = _hazard_request(before, actor, 'actual:hazard', 1, rule)
                    self.assertEqual(tuple(option.rule_id for option in request.wound_negation_options),
                        (lady_wound_rule(actor),))
                    test = resolve_test(request.avoidance_test, AllTens())
                    result = resolve_hazard(weapon_hazard_resolution_request(request, test), AllTens(),
                        decisions=LadyWoundDecisions(WarpedFormDecisions()))
                    area_canonical(request, test, result)
                    self.assertEqual(result.state, request.target_injury)
                    self.assertTrue(result.state.conditions.has(Condition.STAGGERED))
                    actual = result.character_wound if actor == 'pc1' else result.profile_wound
                    self.assertEqual(actual.negated_by_rule_id, lady_wound_rule(actor))
                    proof = PcWeaponHazardProof(request, test, result)
                    after = project_oath_aftermath(before, with_injury(before, actor, result.state), proof)
                    self.assertFalse(actor_oath(after, actor).lady.available)
                    self.assertEqual(actor_oath(after, actor).lady.negated_wound_id, actual.request_id)
                    other = 'minion1' if actor == 'pc1' else 'pc1'
                    self.assertTrue(actor_oath(after, other).lady.available)
                    self.assertEqual(_hazard_request(after, actor, 'next:hazard', 1, rule).wound_negation_options, ())
                    with self.assertRaises(ValueError):
                        area_canonical(replace(request, wound_negation_options=()), test, result)

    def test_falling_options_reach_actual_character_or_profile_wound_and_canonical_validation(self):
        for npc in (False, True):
            with self.subTest(npc=npc):
                state = falling_view(npc=npc)
                actor = 'minion1' if npc else 'pc'
                # Reuse the actual prepared aerial/dismount boundary with a
                # complete acquired pre-battle source for this falling actor.
                source = state.source
                if npc:
                    old = source.enemies[0].definition.generated_components
                    generated = replace(old, talents=(*old.talents, lady(free=True)),
                        oath_context=grant_context(actor))
                    source = replace(source, enemies=(generated.participant(actor),))
                else:
                    member = replace(source.party[0], talents=(*source.party[0].talents, lady(free=True)),
                        oath_context=grant_context(actor))
                    source = replace(source, party=(member,))
                state.source, state.oaths = source, initial_pc_oaths(source)
                source = replace(source, battlefield=replace(source.battlefield,
                    airspace=replace(source.battlefield.airspace, fall_hazard_rating=1)))
                state.source = source
                request = expected_pc_falling_request(state)
                test = resolve_test(request.avoidance_test, AllTens())
                result = resolve_hazard(falling_hazard_request(request, test), AllTens(),
                    decisions=LadyWoundDecisions(WarpedFormDecisions()))
                falling_canonical(request, test, result)
                self.assertEqual(request.wound_negation_options[0].rule_id, lady_wound_rule(actor))
                actual = result.profile_wound if npc else result.character_wound
                self.assertEqual(actual.negated_by_rule_id, lady_wound_rule(actor))
                self.assertEqual(result.state.wounds, request.target_injury.wounds)
                if npc:
                    self.assertTrue(result.state.conditions.has(Condition.PRONE))
                with self.assertRaises(ValueError):
                    falling_canonical(replace(request, wound_negation_options=()), test, result)

    def test_direct_magic_and_miscast_tasks_use_actual_target_blessing_without_npc_fate(self):
        for actor, kinds in (('pc1', (PcMagicTaskKind.RANDOM_WOUND, PcMagicTaskKind.FIXED_EARS,
                PcMagicTaskKind.STAGGER)), ('minion1', (PcMagicTaskKind.DAMAGE,
                PcMagicTaskKind.FIXED_EARS, PcMagicTaskKind.STAGGER))):
            for kind in kinds:
                with self.subTest(actor=actor, kind=kind):
                    before = prepared()
                    value = 99 if kind is PcMagicTaskKind.DAMAGE else 11 if kind is PcMagicTaskKind.FIXED_EARS else 0
                    task = PcMagicTask('actual:magic-task', kind, actor, value)
                    before = replace(before, magic_pending=PcMagicPending('pc1', 'actual:effect', (task,)))
                    proof = build_magic_effect(before, AllTens())
                    projected = project_pc_magic_step(before, proof)
                    after = project_oath_aftermath(before, projected, proof)
                    self.assertEqual(pc_actor_injury(after, actor), pc_actor_injury(before, actor))
                    self.assertFalse(actor_oath(after, actor).lady.available)
                    self.assertEqual(len(actor_oath(after, actor).lady_uses), 1)
                    if kind is PcMagicTaskKind.FIXED_EARS and actor == 'pc1':
                        self.assertIs(type(proof.result), CharacterWoundLifecycleRollResult)
                        self.assertIs(type(proof.result.wound_result.table_roll), FixedWoundTableSelection)
                        self.assertEqual(proof.result.wound_result.table_roll.entry.id, WoundEntryId.EARS_RINGING)
                        self.assertEqual(proof.result.wound_result.table_roll.values, ())
                        self.assertFalse(pc_actor_injury(after, actor).conditions.has(Condition.DEAFENED))
                        self.assertEqual(after.participant(actor).daily_wounds, before.participant(actor).daily_wounds)
                    if actor == 'minion1':
                        self.assertFalse(hasattr(after.enemy(actor).state, 'fate'))

    def test_warped_form_target_bank_and_replay_preserve_cancelled_staggered_for_both_sides(self):
        for actor in ('pc1', 'minion1'):
            with self.subTest(actor=actor):
                before = prepared()
                # Prepared actual-wave target boundary isolates its target
                # owner. The full Skin Wolf activation is covered elsewhere.
                activation = PcWarpedFormActivationProof('actual:wave', 'skin_wolf',
                    ProfileInjuryState(1,2),
                    ProfileInjuryState(0,2,ConditionState(frozenset({Condition.STAGGERED}))), (actor,))
                before = replace(before, history=(activation,))
                request = next_warped_form_target(before)
                self.assertEqual(request.wound_negation_options[0].rule_id, lady_wound_rule(actor))
                result = resolve_stagger_impact(request, AllTens(),
                    decisions=LadyWoundDecisions(WarpedFormDecisions()))
                self.assertEqual(canonical_warped_form_impact(request, result), result)
                self.assertEqual(result.state, pc_actor_injury(before, actor))
                proof = PcWarpedFormTargetProof(activation.activation_id, request, result)
                after = project_oath_aftermath(before, with_injury(before, actor, result.state), proof)
                self.assertFalse(actor_oath(after, actor).lady.available)
                self.assertTrue(result.state.conditions.has(Condition.STAGGERED))


if __name__ == '__main__':
    unittest.main()
