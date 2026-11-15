"""Character facts reach actual equipment/resource behavior without user policies."""
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.application.encounter_character import EncounterCharacter, EncounterArmour, EncounterTalent
from towr.application.dynamic_encounter import automatic_npc_search_space
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.pc_melee_models import PcMeleeWeapon, PcWeaponHand, PcTwoHandedGrip
from towr.domain.pc_melee_result_models import initial_pc_melee_state, PcAttackProof
from towr.domain.pc_shield_models import pc_shield_resilience, pc_defence_hand
from towr.domain.fate_models import FateSpendFunding
from towr.domain.test_models import Skill, TestRequest
from towr.domain.fate_models import FateGloriousSpendRequest
from towr.rules.fate_resolution import spend_fate_for_glorious
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


def character(**changes):
    return replace(EncounterCharacter('pc', 3, 3, 3, 3, 5, 5, 4, 4,
        PcMeleeWeapon.SWORD, EncounterArmour.NONE, False, PcWeaponHand.RIGHT, (), 3), **changes)


def scenario(character):
    source = make_pc_melee_scenario(max_rounds=1)
    member = character.participant('session', NpcDefeatDisposition.KILLED)
    return replace(source, party=(replace(member, target_priority=source.party[0].target_priority,
        defeat_decisions=source.party[0].defeat_decisions),))


class EncounterCharacterTests(unittest.TestCase):
    def test_armour_and_shield_are_separate_executable_equipment(self):
        state = initial_pc_melee_state(scenario(character(armour=EncounterArmour.LIGHT, shield=True)))
        self.assertEqual(pc_shield_resilience(state, 'pc').total, 5)
        self.assertEqual(state.source.party[0].pc.armour_bonus, 1)
        self.assertIs(pc_defence_hand(state.party[0], Skill.SHOOTING), PcWeaponHand.LEFT)
        bare = initial_pc_melee_state(scenario(character()))
        self.assertIsNone(pc_defence_hand(bare.party[0], Skill.SHOOTING))

    def test_grip_is_derived_and_invalid_shield_loadout_is_rejected(self):
        member = character(weapon=PcMeleeWeapon.GREATAXE).participant('session', NpcDefeatDisposition.KILLED)
        self.assertIs(member.initial_weapon_hand, PcTwoHandedGrip.BOTH)
        with self.assertRaises(ValueError):
            character(weapon=PcMeleeWeapon.GREATAXE, shield=True)

    def test_automatic_glorious_uses_real_failed_roll_and_lucky_at_zero_fate(self):
        source = scenario(character(fate=0, talents=(EncounterTalent.LUCKY,)))
        rng = ScriptedD10([10,10,10,1,1,1,10,10])
        result = run_pc_melee_scenario(source, rng)
        rng.assert_exhausted()
        proof = next(step.proof for step in result.steps if isinstance(step.proof, PcAttackProof))
        self.assertEqual(proof.glorious.source_request.initial_roll.initial_values, (10,10,10))
        self.assertIs(proof.glorious.spend.funding, FateSpendFunding.LUCKY_FREE)
        self.assertEqual(result.state.party[0].fate.remaining_spends, 0)
        self.assertFalse(result.state.party[0].fate.lucky_free_spend_available)
        record = run_pc_melee_trial(PcMeleeSimulationRequest(source, 42, 1), 0,
            rng_factory=lambda _: ScriptedD10([10,10,10,1,1,1,10,10]))
        self.assertEqual(record.glorious_spend_counts[0].count, 1)
        self.assertEqual(source.party[0].fate.spends, ())

    def test_lucky_subsequent_spend_is_paid_and_cannot_be_reused(self):
        member = character(fate=1, talents=(EncounterTalent.LUCKY,)).participant('session', NpcDefeatDisposition.KILLED)
        first = spend_fate_for_glorious(FateGloriousSpendRequest('one', member.fate,
            TestRequest('test:one', member.pc.melee_profile)))
        second = spend_fate_for_glorious(FateGloriousSpendRequest('two', first.state,
            TestRequest('test:two', member.pc.melee_profile)))
        self.assertIs(first.spend.funding, FateSpendFunding.LUCKY_FREE)
        self.assertIs(second.spend.funding, FateSpendFunding.SESSION_POOL)
        self.assertFalse(second.state.can_spend)

    def test_automatic_space_tracks_party_without_granting_authored_abilities(self):
        party = (character().participant('session', NpcDefeatDisposition.KILLED),)
        space = automatic_npc_search_space(party)
        self.assertEqual(space.weapon_skill, (2,3,4))
        self.assertEqual(space.melee, (4,5,6))
        self.assertEqual(space.abilities, ((),))
        strong = replace(party[0], pc=replace(party[0].pc, strength=7))
        self.assertEqual(automatic_npc_search_space((strong,)).strength, (6,7,8))

    def test_character_facts_are_strict_and_independent_per_battle(self):
        for changes in ({'fate': True}, {'talents': ('lucky',)}, {'shield': 1},
                {'armour': 'heavy'}, {'strength': True}, {'melee': 11}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                character(**changes)
        source = character()
        one = source.participant('one', NpcDefeatDisposition.KILLED)
        two = source.participant('two', NpcDefeatDisposition.KILLED)
        self.assertNotEqual(one.fate.session_id, two.fate.session_id)
        self.assertEqual((one.fate.spends, two.fate.spends), ((), ()))
        object.__setattr__(source, 'shield', 1)
        with self.assertRaises(TypeError):
            source.participant('forged', NpcDefeatDisposition.KILLED)


if __name__ == '__main__':
    unittest.main()
