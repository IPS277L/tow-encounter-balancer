from copy import deepcopy
from dataclasses import replace
from itertools import product
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_m2_npc_roster import definition, participant
from towr.domain.condition_models import Condition
from towr.domain.npc_attack_preparation_models import NpcAttackPreparationRequest
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.protection_models import ProtectionPreparationRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.resolution_models import KernelAttackRequest
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatSide
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.npc_attack_preparation import prepare_npc_attack, prepare_npc_attack_protection


def roster():
    shared = definition()
    return NpcRoster(tuple(
        participant(f"brigand:{index}", profile=shared, side=side)
        for index, side in enumerate((CombatSide.PLAYERS_AND_ALLIES,) * 2 + (CombatSide.OPPOSITION,) * 2)
    ))


def attack_request(source, selected="axe"):
    attacker, target = source.participant("brigand:0"), source.participant("brigand:2")
    return NpcAttackPreparationRequest(
        id="prepare:roster", attack_id="attack:roster", attacker_test_id="test:attack",
        snapshot=attacker.attack_snapshot("snapshot:attack"), selected_attack_id=selected,
        target_id=target.state.actor_id,
        target_range=Range.CLOSE if selected == "axe" else Range.MEDIUM,
        target_resilience=target.state.current_resilience,
        has_enemy_in_close_range=selected == "axe",
        attacker_is_staggered=attacker.state.injury.conditions.has(Condition.STAGGERED),
        range_approved_by_gm=False,
    )


def protection_request(source, npc, aware=True):
    target = source.participant(npc.target_id)
    return ProtectionPreparationRequest(
        id="protect:roster", defender_id=target.state.actor_id,
        attack=npc.attack, attack_skill=npc.selected_profile.skill,
        defender_is_aware=aware,
        defender_is_defenceless=target.state.injury.conditions.has(Condition.DEFENCELESS),
        defender_wields_weapon=target.state.wields_weapon,
        defender_holds_shield=target.state.holds_shield,
        selected_skill=Skill.ATHLETICS if aware else None,
        options=target.protection_options("test:protection"),
    )


class M2NpcRosterPreparationTests(unittest.TestCase):
    def test_four_participants_share_profiles_but_only_selected_target_is_wounded(self):
        # GM 1.1 p97 numeric Brigand profiles; no outnumbering/Ability scenario.
        for selected, aware in product(("axe", "warbow"), (False, True)):
            with self.subTest(selected=selected, aware=aware):
                source = roster()
                before = deepcopy(source)
                npc = prepare_npc_attack(attack_request(source, selected))
                prepared = prepare_npc_attack_protection(npc, protection_request(source, npc, aware))
                target = source.participant("brigand:2")
                rng = SequenceRandom([1, 2, 10] + ([10] * 3 if aware else []) + [7])
                result = resolve_kernel_attack(KernelAttackRequest(
                    id="resolve:roster", target_id=target.state.actor_id, attack=prepared.attack,
                    target_policy=target.definition.injury_policy, target_state=target.state.injury,
                    can_target_leave_zone=True, target_has_given_ground_this_round=False,
                ), rng)
                self.assertEqual(rng.randint(1, 10), 7)
                self.assertEqual(result.attack.damage, 5)
                self.assertEqual(result.attack.effective_resilience, 4)
                self.assertTrue(result.target_state.defeated)
                self.assertEqual(result.target_state.wounds, 1)
                self.assertEqual(prepared.npc_attack.snapshot.actor_id, "brigand:0")
                self.assertEqual(prepared.protection.defender_id, "brigand:2")
                if aware:
                    self.assertEqual(result.attack.defender_test.trace.threshold, 2)
                    self.assertEqual(result.attack.defender_test.trace.request_id,
                                     "test:protection:brigand:2:athletics")
                self.assertIn(target.definition.source_rule_id + ":" + selected,
                              prepared.applied_rule_ids)
                # Explicit immutable reconstruction, not an automatic result consumer.
                changed = replace(target, state=replace(target.state, injury=result.target_state))
                updated = NpcRoster(tuple(changed if p is target else p for p in source.participants))
                self.assertEqual(source, before)
                for actor_id in ("brigand:0", "brigand:1", "brigand:3"):
                    self.assertIs(updated.participant(actor_id), source.participant(actor_id))
                    self.assertFalse(updated.participant(actor_id).state.injury.defeated)

    def test_availability_changes_are_taken_from_current_actor_snapshot(self):
        source = roster()
        actor = source.participant("brigand:0")
        actor = replace(actor, state=replace(actor.state, available_attack_ids=("warbow",)))
        current = NpcRoster((actor, *source.participants[1:]))
        with self.assertRaisesRegex(ValueError, "unavailable"):
            attack_request(current, "axe")
        self.assertEqual(prepare_npc_attack(attack_request(current, "warbow")).selected_profile.id, "warbow")
        self.assertEqual(source.participant("brigand:0").state.available_attack_ids, ("axe", "warbow"))

    def test_protection_from_another_instance_with_same_profile_is_rejected(self):
        source = roster()
        npc = prepare_npc_attack(attack_request(source))
        correct = protection_request(source, npc)
        wrong = source.participant("brigand:3")
        with self.assertRaisesRegex(ValueError, "another defender"):
            replace(correct, options=wrong.protection_options("test:protection"))
        # Even replacing all defender fields cannot change the prepared target.
        other = replace(correct, defender_id=wrong.state.actor_id,
                        options=wrong.protection_options("test:protection"))
        with self.assertRaisesRegex(ValueError, "exact prepared"):
            prepare_npc_attack_protection(npc, other)
