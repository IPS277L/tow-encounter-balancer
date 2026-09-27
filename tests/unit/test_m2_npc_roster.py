from dataclasses import FrozenInstanceError, replace
import unittest

from tests.unit.test_k1_npc_attack_preparation import brigand
from towr.domain.attack_models import ResilienceProfile
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.npc_roster_models import (
    NpcDefinition, NpcParticipantSnapshot, NpcParticipantState,
    NpcProtectionProfile, NpcRoster,
)
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatSide, CombatTurnParticipant


def definition():
    # GM 1.1 Allies and Antagonists / Brigands & Footpads p97.
    # Craven Opportunist is not triggered in the scenarios below.
    return NpcDefinition(
        "brigand", "RULE-PROFILE-TALABEC-004", TargetInjuryPolicy.MINION, 1,
        ResilienceProfile(3, 1), brigand().profiles,
        (NpcProtectionProfile("RULE-PROFILE-TALABEC-004:protection",
                              Skill.ATHLETICS, InlineProfile(3, 2)),),
    )


def participant(actor_id="brigand:a", *, profile=None, side=CombatSide.OPPOSITION):
    profile = profile or definition()
    injury = (CharacterInjuryState() if profile.injury_policy is TargetInjuryPolicy.CHAMPION
              else ProfileInjuryState(0, profile.wound_limit))
    return NpcParticipantSnapshot(profile, NpcParticipantState(
        actor_id, profile.id, side, injury, tuple(p.id for p in profile.attacks),
        profile.resilience, True, False,
    ))


class M2NpcRosterTests(unittest.TestCase):
    def test_shared_definition_keeps_independent_actor_state_and_existing_sides(self):
        profile = definition()
        first = participant(profile=profile, side=CombatSide.PLAYERS_AND_ALLIES)
        second = participant("brigand:b", profile=profile)
        roster = NpcRoster([first, second])
        changed = replace(first, state=replace(first.state,
            available_attack_ids=("warbow",), injury=ProfileInjuryState(1, 1, defeated=True)))
        updated = NpcRoster((changed, second))
        self.assertIs(updated.participant("brigand:b"), second)
        self.assertIs(changed.definition, profile)
        self.assertEqual(first.state.injury.wounds, 0)
        self.assertEqual(second.state.available_attack_ids, ("axe", "warbow"))
        self.assertEqual(roster.turn_participants, (
            CombatTurnParticipant("brigand:a", CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("brigand:b", CombatSide.OPPOSITION),
        ))
        # The roster does not silently schedule or filter defeated participants.
        self.assertEqual(updated.turn_participants, roster.turn_participants)
        with self.assertRaises(FrozenInstanceError):
            first.state = changed.state

    def test_projections_preserve_actor_profiles_and_explicit_availability(self):
        first = participant()
        first = replace(first, state=replace(first.state, available_attack_ids=("warbow",)))
        snapshot = first.attack_snapshot("snapshot:one")
        self.assertEqual(snapshot.actor_id, first.state.actor_id)
        self.assertIs(snapshot.profiles, first.definition.attacks)
        self.assertEqual(snapshot.available_attack_ids, ("warbow",))
        options = first.protection_options("test:one")
        self.assertEqual(options[0].defender_id, first.state.actor_id)
        self.assertIs(options[0].test.profile, first.definition.protection[0].test_profile)
        self.assertEqual(options[0].test.profile, InlineProfile(3, 2))
        self.assertNotEqual(options[0].test.id,
                            participant("brigand:b").protection_options("test:one")[0].test.id)
        self.assertNotEqual(options[0].test.id, first.protection_options("test:two")[0].test.id)

    def test_multiple_instances_cannot_redefine_shared_profile_id(self):
        first = participant()
        different = replace(first.definition, resilience=ResilienceProfile(5))
        with self.assertRaisesRegex(ValueError, "conflicting definitions"):
            NpcRoster((first, participant("brigand:b", profile=different)))
        with self.assertRaisesRegex(ValueError, "actor IDs"):
            NpcRoster((first, first))
        with self.assertRaisesRegex(ValueError, "unknown roster actor"):
            NpcRoster((first,)).participant("absent")

    def test_state_must_match_definition_availability_and_injury_policy(self):
        first = participant()
        for changes, message in (
            ({"definition_id": "other"}, "another definition"),
            ({"available_attack_ids": ("absent",)}, "unknown available"),
            ({"injury": ProfileInjuryState(0, 2)}, "wound limit"),
        ):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, message):
                replace(first, state=replace(first.state, **changes))
        with self.assertRaisesRegex(TypeError, "ProfileInjuryState"):
            replace(first, state=replace(first.state, injury=CharacterInjuryState()))

    def test_brute_and_champion_use_distinct_injury_contracts(self):
        for policy, limit in ((TargetInjuryPolicy.BRUTE, 3), (TargetInjuryPolicy.CHAMPION, None)):
            with self.subTest(policy=policy):
                profile = replace(definition(), id="synthetic", injury_policy=policy, wound_limit=limit)
                actor = participant(profile=profile)
                expected = CharacterInjuryState if limit is None else ProfileInjuryState
                self.assertIsInstance(actor.state.injury, expected)
                if limit is None:
                    with self.assertRaisesRegex(TypeError, "CharacterInjuryState"):
                        replace(actor, state=replace(actor.state, injury=ProfileInjuryState(0, 3)))

    def test_unsupported_policies_profiles_and_invalid_limits_fail_explicitly(self):
        for policy in (TargetInjuryPolicy.PLAYER, TargetInjuryPolicy.MONSTROSITY):
            with self.subTest(policy=policy), self.assertRaisesRegex(ValueError, "supports"):
                replace(definition(), injury_policy=policy)
        for limit in (0, 2):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                replace(definition(), wound_limit=limit)
        for limit in (True, None, 1.5):
            with self.subTest(limit=limit), self.assertRaises(TypeError):
                replace(definition(), wound_limit=limit)
        with self.assertRaisesRegex(ValueError, "no profile wound limit"):
            replace(definition(), injury_policy=TargetInjuryPolicy.CHAMPION)
        with self.assertRaises(TypeError):
            replace(definition(), attacks=(object(),))

    def test_collections_are_frozen_and_ambiguous_profile_choices_are_rejected(self):
        profile = definition()
        attacks, protection = list(profile.attacks), list(profile.protection)
        copy = replace(profile, attacks=attacks, protection=protection)
        attacks.clear()
        protection.clear()
        self.assertEqual(copy, profile)
        for changes in ({"attacks": (profile.attacks[0],) * 2},
                        {"protection": profile.protection * 2}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(profile, **changes)
        with self.assertRaises(ValueError):
            replace(participant().state, available_attack_ids=("axe", "axe"))

    def test_current_resilience_and_equipment_are_supplied_not_inferred(self):
        actor = participant()
        # E.g. an external equipment/effect reducer provides a new effective value.
        state = replace(actor.state, current_resilience=ResilienceProfile(3),
                        available_attack_ids=(), wields_weapon=False, holds_shield=True)
        updated = replace(actor, state=state)
        self.assertEqual(updated.definition.resilience, ResilienceProfile(3, 1))
        self.assertEqual(updated.state.current_resilience, ResilienceProfile(3))
        self.assertEqual(updated.attack_snapshot("snapshot:unarmed").available_attack_ids, ())
        self.assertEqual(updated.protection_options("test"), actor.protection_options("test"))

    def test_invalid_types_and_identifiers_do_not_become_silent_defaults(self):
        for changes in ({"actor_id": " "}, {"definition_id": ""}, {"side": "opposition"},
                        {"wields_weapon": 1}, {"holds_shield": None},
                        {"current_resilience": 4}, {"injury": 0}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(participant().state, **changes)
        for changes in ({"source_rule_id": ""}, {"skill": Skill.SHOOTING},
                        {"skill": "athletics"}, {"test_profile": (3, 2)}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(definition().protection[0], **changes)
        with self.assertRaises(ValueError):
            participant().protection_options("")
        with self.assertRaises(TypeError):
            NpcRoster((object(),))

    def test_roster_does_not_invent_an_encounter_or_require_both_sides(self):
        self.assertEqual(NpcRoster(()).turn_participants, ())
        first = participant()
        self.assertEqual(NpcRoster((first,)).turn_participants, (first.turn_participant,))
