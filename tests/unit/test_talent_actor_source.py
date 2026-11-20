"""Actual initial actor prerequisites and one native free-creation Casting run.

Source rejection tests construct fresh immutable definitions. They do not forge
projected battle states or claim ownership metadata executes unconnected rules.
"""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.pc_magic_scenarios import magic_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_ranged_scenarios import make_pc_ranged_scenario
from tests.support.pc_tactics_fixtures import automatic_source
from tests.support.talent_sources import free_talent, paid_talent
from towr.domain.armour_models import ArmourLoadout
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedRangedFacts, GeneratedWeapon
from towr.domain.pc_magic_models import PcCastingProof
from towr.domain.pc_magic_source_models import PcSpellId
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.domain.talent_catalog import TalentId as T, TalentOrigin
from towr.domain.talent_models import (
    AcquiredTalent, TalentAcquisition, TalentAcquisitionPhase as P,
    TalentFunding as F, TalentLoreFact, TalentOwnerFacts,
)
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


def player():
    return automatic_source(pc_count=1, enemy_count=1, rounds=1).party[0]


def npc():
    return GeneratedNpc(3, 4, 3, 3, 4, 4, initial_generated_weapons(GeneratedWeapon.STAFF),
        ArmourLoadout(), defence=4)


def repeated_wizard(count, *, free=False):
    return AcquiredTalent(T.WIZARD, tuple(TalentAcquisition(
        P.CREATION if free else P.ADVANCEMENT, F.FREE if free else F.XP)
        for _ in range(count)))


class TalentActorSourceTests(unittest.TestCase):
    def test_pc_and_npc_share_paid_and_free_threshold_rules(self):
        for id, field, threshold in ((T.DEFENSIVE_STANCE, 'weapon_skill', 3),
                (T.WILD_ATTACK, 'strength', 4)):
            for value in (threshold - 1, threshold):
                with self.subTest(id=id, value=value):
                    member = player()
                    member = replace(member, pc=replace(member.pc, **{field: value}))
                    creature = replace(npc(), **{field: value})
                    if value < threshold:
                        with self.assertRaises(ValueError):
                            replace(member, talents=(paid_talent(id),))
                        with self.assertRaises(ValueError):
                            replace(creature, talents=(paid_talent(id),))
                    else:
                        self.assertEqual(replace(member, talents=(paid_talent(id),)).talents,
                            (paid_talent(id),))
                        self.assertEqual(replace(creature, talents=(paid_talent(id),)).talents,
                            (paid_talent(id),))
                    self.assertEqual(replace(member, talents=(free_talent(id),)).talents,
                        (free_talent(id),))
                    self.assertEqual(replace(creature, talents=(free_talent(id),)).talents,
                        (free_talent(id),))

    def test_cached_base_facts_cannot_overwrite_either_initial_definition(self):
        member, creature = player(), npc()
        for field in ('weapon_skill', 'strength', 'toughness', 'agility'):
            for owner, value in ((member, getattr(member.pc, field)),
                    (creature, getattr(creature, field))):
                with self.subTest(field=field, owner=type(owner).__name__):
                    foreign = TalentOwnerFacts(**{field: value + 1})
                    with self.assertRaisesRegex(ValueError, 'initial ' + field):
                        replace(owner, talent_facts=foreign)
                    # Even a waived prerequisite cannot smuggle a changed
                    # physical Characteristic through the acquisition view.
                    with self.assertRaisesRegex(ValueError, 'initial ' + field):
                        replace(owner, talents=(free_talent(T.WILD_ATTACK),), talent_facts=foreign)

    def test_matching_explicit_facts_are_retained_without_mutating_or_backfilling_source(self):
        member = player()
        facts = TalentOwnerFacts(weapon_skill=member.pc.weapon_skill,
            strength=member.pc.strength, origin=TalentOrigin.HUMAN,
            lores=(TalentLoreFact('anatomy'),))
        admitted = replace(member, talents=(paid_talent(T.DEFENSIVE_STANCE),), talent_facts=facts)
        self.assertIs(admitted.talent_facts, facts)
        self.assertIsNone(facts.toughness)
        self.assertEqual(admitted.pc, member.pc)
        self.assertEqual(admitted.fate, member.fate)
        forged = deepcopy(facts)
        object.__setattr__(forged, 'strength', True)
        with self.assertRaises(TypeError):
            replace(member, talent_facts=forged)

    def test_actual_ranged_characteristics_take_precedence_over_cached_facts(self):
        member = make_pc_ranged_scenario().party[0]
        ranged = GeneratedRangedFacts(4, 4,  True, None, None)
        creature = replace(npc(), weapons=initial_generated_weapons(GeneratedWeapon.REPEATER_HANDBOW),
            ranged=ranged, initiative=3,dexterity=4)
        for owner, profile in ((member, member.pc.ranged), (creature, ranged)):
            for field in ('ballistic_skill', 'initiative'):
                actual=(owner.pc.initiative if hasattr(owner,'pc') else owner.initiative) if field=='initiative' else getattr(profile,field)
                with self.subTest(owner=type(owner).__name__, field=field):
                    with self.assertRaisesRegex(ValueError, 'initial ' + field):
                        replace(owner, talent_facts=TalentOwnerFacts(**{field: actual + 1}))
                    admitted = replace(owner,
                        talent_facts=TalentOwnerFacts(**{field: actual}))
                    self.assertEqual(admitted.talent_facts, TalentOwnerFacts(**{field: actual}))

    def test_lucky_ownership_and_funding_must_match_in_both_directions(self):
        member = player()
        with self.assertRaisesRegex(ValueError, 'Lucky funding'):
            replace(member, fate=replace(member.fate, has_lucky=True))
        with self.assertRaisesRegex(ValueError, 'Lucky funding'):
            replace(member, talents=(paid_talent(T.LUCKY),))
        admitted = replace(member, fate=replace(member.fate, has_lucky=True),
            talents=(paid_talent(T.LUCKY),))
        self.assertEqual(admitted.talents, (paid_talent(T.LUCKY),))
        with self.assertRaisesRegex(ValueError, 'Lucky funding'):
            replace(admitted, talents=())
        with self.assertRaisesRegex(ValueError, 'Lucky funding'):
            replace(admitted, fate=replace(admitted.fate, has_lucky=False))

    def test_wizard_ownership_profile_and_purchase_count_are_one_source(self):
        member = magic_scenario(enemies=1, level=2).party[0]
        self.assertEqual(len(member.talents[0].acquisitions), 2)
        for count in (1, 3):
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, 'Wizard Level'):
                replace(member, talents=(repeated_wizard(count),))
        with self.assertRaisesRegex(ValueError, 'Wizard Casting source'):
            replace(member, talents=())
        with self.assertRaisesRegex(ValueError, 'Wizard Casting source'):
            replace(member, wizard=None, talent_facts=TalentOwnerFacts(origin=TalentOrigin.HUMAN,
                lores=(TalentLoreFact('elementalism', True),)))

    def test_paid_and_explicit_free_wizard_origins_use_common_acquisition(self):
        member = magic_scenario(enemies=1, level=1).party[0]
        for origin in ('dwarf', 'halfling'):
            with self.subTest(origin=origin):
                profile = replace(member.wizard, origin=origin)
                with self.assertRaisesRegex(ValueError, 'Requirements'):
                    replace(member, wizard=profile)
                admitted = replace(member, wizard=profile, talents=(free_talent(T.WIZARD),))
                self.assertEqual(admitted.wizard.origin, origin)
                self.assertIs(admitted.talents[0].acquisitions[0].funding, F.FREE)
        for origin in ('human', 'ogre'):
            with self.subTest(origin=origin):
                admitted = replace(member, wizard=replace(member.wizard, origin=origin))
                self.assertEqual(admitted.wizard.origin, origin)
                self.assertIsNone(admitted.talent_facts)

    def test_wizard_cannot_relabel_known_magic_lore_origin_or_reason(self):
        member = magic_scenario(enemies=1).party[0]
        with self.assertRaisesRegex(ValueError, 'actual Origin'):
            replace(member, talent_facts=TalentOwnerFacts(origin=TalentOrigin.WOOD_ELF))
        with self.assertRaisesRegex(ValueError, 'ordinary knowledge'):
            replace(member, talent_facts=TalentOwnerFacts(lores=(TalentLoreFact('elementalism'),)))
        with self.assertRaisesRegex(ValueError, 'initial reason'):
            replace(member, talent_facts=TalentOwnerFacts(reason=member.pc.reason + 1))
        for origin in (TalentOrigin.HUMAN, TalentOrigin.EMPIRE_HUMAN, TalentOrigin.BRETONNIAN_HUMAN):
            with self.subTest(origin=origin):
                facts = TalentOwnerFacts(origin=origin)
                admitted = replace(member, talent_facts=facts)
                self.assertEqual(admitted.talent_facts, facts)

    def test_npc_cannot_acquire_pc_fate_or_an_unconnected_caster(self):
        creature = replace(npc(), talents=(paid_talent(T.MAGIC_RESISTANCE),))
        participant = creature.participant('npc:no-fate')
        self.assertFalse(hasattr(creature, 'fate'))
        self.assertFalse(hasattr(participant.state, 'fate'))
        with self.assertRaisesRegex(ValueError, 'NPC Talent execution is not connected'):
            replace(creature, talents=(paid_talent(T.LUCKY),))
        with self.assertRaisesRegex(ValueError, 'NPC Talent execution is not connected'):
            replace(creature, talents=(paid_talent(T.WIZARD),),
                talent_facts=TalentOwnerFacts(origin=TalentOrigin.HUMAN,
                    lores=(TalentLoreFact('elementalism', True),)))

    def test_unconnected_and_untyped_talents_are_not_silently_active(self):
        for owner in (player(), npc()):
            with self.subTest(owner=type(owner).__name__):
                with self.assertRaisesRegex(ValueError, 'execution is not connected'):
                    replace(owner, talents=(free_talent(T.FEIGNED_FLIGHT),))
                for malformed in (('wild_attack',), (T.WILD_ATTACK,), [paid_talent(T.WILD_ATTACK)]):
                    with self.subTest(malformed=malformed), self.assertRaises(TypeError):
                        replace(owner, talents=malformed)
        with self.assertRaisesRegex(ValueError, 'PC Talent execution is not connected'):
            replace(player(), talents=(paid_talent(T.MAGIC_RESISTANCE),))

    def test_free_dwarf_wizard_casts_and_replays_one_real_native_battle(self):
        source = magic_scenario(reason=2, willpower=10, level=1, rounds=1, enemies=1,
            spells=(PcSpellId.LIGHTNING_BLAST,))
        member = source.party[0]
        member = replace(member, wizard=replace(member.wizard, origin='dwarf'),
            talents=(free_talent(T.WIZARD),))
        source = replace(source, party=(member,))
        rng = ScriptedD10([1, 1, 10, 10])
        result = run_pc_melee_scenario(source, rng)
        rng.assert_exhausted()
        self.assertIsNone(result.unsupported)
        casts = [step.proof for step in result.steps if type(step.proof) is PcCastingProof]
        self.assertEqual(len(casts), 1)
        self.assertIs(casts[0].spell_id, PcSpellId.LIGHTNING_BLAST)
        self.assertEqual(result.source.party[0].wizard.origin, 'dwarf')
        self.assertEqual(result.source.party[0].talents, (free_talent(T.WIZARD),))
        replay = initial_pc_melee_state(source)
        for step in result.steps:
            replay = apply_pc_melee_step(replay, step)
        self.assertEqual(replay, result.state)


if __name__ == '__main__':
    unittest.main()
