"""Common NPC acquisition sources and admission by actual execution owner."""
from dataclasses import replace
import unittest

from tests.support.talent_sources import free_talent, paid_talent
from tests.unit.test_generated_inventory_source import source as generated_source
from tests.unit.test_m8_npc_magic_scenario import owner, transform_actor
from tests.unit.test_m2_npc_roster_attack_execution import request as minion_attack_request
from towr.domain.attack_models import ResilienceProfile
from towr.domain.npc_roster_models import NpcDefinition, NpcRoster
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.talent_actor_models import (
    npc_definition_acquired_talents, validate_npc_definition_talent_scope,
)
from towr.domain.talent_catalog import TalentId, TalentOrigin
from towr.domain.talent_models import (
    AcquiredTalent, DeityChoice, DeityId, TalentAcquisition, TalentAcquisitionPhase as Phase,
    TalentFunding as Funding, TalentLoreFact, TalentOwnerFacts,
)


def definition(**changes):
    return replace(owner().roster.participant('wizard').definition, **changes)


def wizard_talent(count=2):
    return AcquiredTalent(TalentId.WIZARD, tuple(TalentAcquisition(Phase.ADVANCEMENT,
        Funding.XP) for _ in range(count)))


WIZARD_FACTS = TalentOwnerFacts(origin=TalentOrigin.HUMAN,
    lores=(TalentLoreFact('elementalism', True),))


class NpcTalentSourceTests(unittest.TestCase):
    def test_pc_battle_owner_does_not_silently_ignore_authored_talents(self):
        from tests.support.pc_melee_fixtures import make_pc_melee_scenario
        source=make_pc_melee_scenario(max_rounds=1)
        original=source.enemies[0]
        descriptive=replace(original.definition,talents=(free_talent(TalentId.FRIGHTENING),))
        self.assertEqual(npc_definition_acquired_talents(descriptive),descriptive.talents)
        enemy=replace(original,definition=descriptive)
        with self.assertRaisesRegex(ValueError,'execution is not connected'):
            replace(source,enemies=(enemy,))

    def test_toughness_requirement_uses_original_source_for_all_injury_types(self):
        for injury, limit in ((TargetInjuryPolicy.CHAMPION, None),
                (TargetInjuryPolicy.BRUTE, 2), (TargetInjuryPolicy.MINION, 1)):
            with self.subTest(injury=injury):
                npc = definition(injury_policy=injury, wound_limit=limit,
                    talents=(paid_talent(TalentId.HARDY),))
                self.assertEqual(npc_definition_acquired_talents(npc), npc.talents)
                self.assertIs(npc.injury_policy, injury)
                self.assertEqual(npc.wound_limit, limit)
                with self.assertRaises(ValueError):
                    replace(npc, resilience=ResilienceProfile(3))
                free = replace(npc, resilience=ResilienceProfile(3),
                    talents=(free_talent(TalentId.HARDY),))
                self.assertEqual(free.resilience.toughness, 3)

    def test_numeric_attack_is_not_an_invented_strength_or_origin_fact(self):
        with self.assertRaises(ValueError):
            definition(talents=(paid_talent(TalentId.WILD_ATTACK),))
        npc = definition(talents=(paid_talent(TalentId.WILD_ATTACK),),
            talent_facts=TalentOwnerFacts(strength=4))
        self.assertEqual(npc.talent_facts.strength, 4)
        with self.assertRaises(ValueError):
            replace(npc, talent_facts=TalentOwnerFacts(strength=4, toughness=5))

    def test_description_is_separate_from_connected_owner_admission(self):
        npc = definition(talents=(free_talent(TalentId.SHORT_SIZE),))
        self.assertEqual(npc_definition_acquired_talents(npc), npc.talents)
        with self.assertRaisesRegex(ValueError, 'execution is not connected'):
            validate_npc_definition_talent_scope(npc, frozenset((TalentId.HARDY,)))
        validate_npc_definition_talent_scope(npc, frozenset((TalentId.SHORT_SIZE,)))
        for allowed in ({TalentId.SHORT_SIZE}, frozenset(('short_size',)), ('short_size',)):
            with self.subTest(allowed=allowed), self.assertRaises(TypeError):
                validate_npc_definition_talent_scope(npc, allowed)

    def test_complete_exact_sources_reject_duplicates_aliases_and_cached_forgery(self):
        talent = paid_talent(TalentId.HARDY)
        for invalid in ([talent], (talent, talent), ('hardy',), (True,)):
            with self.subTest(invalid=invalid), self.assertRaises((TypeError, ValueError)):
                definition(talents=invalid)
        npc = definition(talents=(talent,))
        object.__setattr__(talent.acquisitions[0], 'funding', 'xp')
        with self.assertRaises(TypeError):
            npc_definition_acquired_talents(npc)
        valid = definition()
        object.__setattr__(valid, 'talent_facts', {'toughness': 4})
        with self.assertRaises(TypeError):
            npc_definition_acquired_talents(valid)

    def test_generated_components_are_authoritative_and_witnesses_must_match(self):
        npc = generated_source(talents=(paid_talent(TalentId.DEFENSIVE_STANCE),),
            talent_facts=TalentOwnerFacts(origin=TalentOrigin.HUMAN))
        participant = npc.participant('generated')
        self.assertEqual(participant.definition.talents, npc.talents)
        self.assertEqual(participant.definition.talent_facts, npc.talent_facts)
        self.assertEqual(npc_definition_acquired_talents(participant.definition), npc.talents)
        for changes in ({'talents': ()}, {'talent_facts': None},
                {'talent_facts': TalentOwnerFacts(origin=TalentOrigin.OGRE)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(participant.definition, **changes)

    def test_same_definition_id_cannot_hide_different_acquisitions(self):
        state = owner()
        ally = state.roster.participant('ally')
        enemy = state.roster.participant('enemy')
        changed = replace(enemy, definition=replace(enemy.definition,
            talents=(free_talent(TalentId.HARDY),)))
        with self.assertRaisesRegex(ValueError, 'conflicting definitions'):
            NpcRoster((ally, changed))
        self.assertEqual(NpcRoster((ally, enemy)).participants, (ally, enemy))

    def test_actual_casting_level_checks_explicit_wizard_acquisitions(self):
        state = owner()
        changed = transform_actor(state, 'wizard', lambda p: replace(p,
            definition=replace(p.definition, talents=(wizard_talent(), paid_talent(TalentId.HARDY)),
                talent_facts=WIZARD_FACTS)))
        self.assertEqual(changed.wizard.caster.wizard_level, 2)
        self.assertEqual(changed.roster.participant('wizard').definition.talents[0], wizard_talent())
        for count in (1, 3):
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, 'actual Casting level'):
                transform_actor(state, 'wizard', lambda p: replace(p,
                    definition=replace(p.definition, talents=(wizard_talent(count),),
                        talent_facts=WIZARD_FACTS)))
        self.assertEqual(state.roster.participant('wizard').definition.talents, ())

    def test_actual_caster_cannot_smuggle_faith_or_unconnected_effects(self):
        state = owner()
        faith = AcquiredTalent(TalentId.FAITH, (TalentAcquisition(Phase.CREATION, Funding.XP,
            DeityChoice(DeityId.SIGMAR)),))
        for talent, facts, message in ((faith, TalentOwnerFacts(origin=TalentOrigin.EMPIRE_HUMAN),
                'actual NPC spellcaster'), (paid_talent(TalentId.MAGIC_RESISTANCE), None,
                'execution is not connected')):
            with self.subTest(talent=talent.id), self.assertRaisesRegex(ValueError, message):
                transform_actor(state, 'wizard', lambda p: replace(p,
                    definition=replace(p.definition, talents=(talent,), talent_facts=facts)))

    def test_minion_attack_admits_only_actual_actor_target_and_preserves_inactive_sources(self):
        request = minion_attack_request()

        def with_talent(actor_id, talent):
            participants = []
            for participant in request.state.roster.participants:
                if participant.state.actor_id == actor_id:
                    definition = replace(participant.definition, id='individual:'+actor_id,
                        talents=(talent,))
                    participant = replace(participant, definition=definition,
                        state=replace(participant.state, definition_id=definition.id))
                participants.append(participant)
            return replace(request, state=replace(request.state, roster=NpcRoster(tuple(participants))))

        # This actor does not participate in this Attack. Its acquisition is
        # retained; this lower Minion owner does not execute or ban its Casting.
        inactive = with_talent('brigand:1', free_talent(TalentId.WIZARD))
        self.assertEqual(inactive.state.roster.participant('brigand:1').definition.talents[0].id,
            TalentId.WIZARD)
        for actor in (request.execution.actor_id, request.execution.target_id):
            with self.subTest(actor=actor):
                accepted = with_talent(actor, free_talent(TalentId.HARDY))
                self.assertEqual(accepted.execution, request.execution)
                with self.assertRaisesRegex(ValueError, 'execution is not connected'):
                    with_talent(actor, free_talent(TalentId.MIGHTY_BLOW))


if __name__ == '__main__':
    unittest.main()
