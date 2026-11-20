"""Actual native Oath receipts, action ceilings and current JSON observations."""
from copy import deepcopy
from dataclasses import replace
from random import Random
import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from jsonschema.exceptions import ValidationError
from tests.integration.test_immediate_attack_counts_json import command
from tests.integration.test_oath_native import native_source, lady_context, LiteralD10
from tests.support.magic_weapon_battles import magic_battle
from tests.support.oath_sources import honour, lady, context, with_native_outcome_owner
from tests.support.pc_tactics_fixtures import automatic_source
from towr.adapters.pc_melee_json import encode_pc_melee_simulation_result
from towr.adapters.pc_melee_json_schema import validate_pc_melee_simulation_document
from towr.domain.pc_oath_models import PcLadyPrayerProof
from towr.domain.talent_catalog import TalentId
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_models import (
    PcMeleeSimulationRequest, PcMeleeSimulationResult, PcHelpActionCount,
    PcAllyRecoverActionCount, PcNpcExtraAttackCount, PcNpcHelpActionCount,
    PcNpcRecoverActionCount, validate_automatic_action_budget, validate_npc_action_budget,
)
from towr.simulation.pc_melee_simulation import run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
from towr.simulation.pc_oath_statistics import (
    PcOathCount, oath_count_actors, oath_observations, sum_oath_counts, validate_oath_counts,
    validate_oath_fate_budget,
)


class OathStatisticsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=native_source(pc_talents=(lady(free=True),),npc_talents=(lady(free=True),),
            pc_context=lady_context(),npc_context=lady_context())
        cls.result=run_pc_melee_scenario(cls.source,LiteralD10())
        cls.counts=oath_observations(cls.result)
        cls.request=PcMeleeSimulationRequest(cls.source,42,1)
        # Reuse the genuine replayed battle for extraction/transport, without
        # claiming additional independent Monte Carlo trials or dice rolls.
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',return_value=cls.result):
            cls.record=run_pc_melee_trial(cls.request,0)
        cls.batch=PcMeleeSimulationResult(cls.request,(cls.record,))
        cls.summary=summarize_pc_melee_simulation(cls.batch)

    def test_actual_paid_prayers_survive_record_summary_without_inventing_fate(self):
        self.assertEqual(self.counts,tuple(PcOathCount(actor,prayers=1)
            for actor in (*self.source.pc_activation_order,*self.source.enemy_activation_order)))
        self.assertEqual(self.result.executed_actions,2)
        self.assertEqual(self.record.oath_counts,self.counts)
        self.assertEqual(self.summary.oath_counts,self.counts)

    def test_source_order_requires_every_owner_even_when_zero(self):
        actors=oath_count_actors(self.source)
        zero=tuple(PcOathCount(actor) for actor in actors)
        validate_oath_counts(zero,self.source,trials=0,started_rounds=0,actions=0)
        for bad in (None,(),zero[:1],zero[::-1],(*zero,zero[0])):
            with self.subTest(bad=bad),self.assertRaises((TypeError,ValueError)):
                validate_oath_counts(bad,self.source,trials=1,started_rounds=1,actions=2)
        self.assertEqual(sum_oath_counts((),self.source),zero)
        self.assertEqual(sum_oath_counts((self.counts,zero,self.counts),self.source),
            tuple(PcOathCount(actor,prayers=2) for actor in actors))
        plain=automatic_source(pc_count=1,enemy_count=1,rounds=1)
        self.assertIsNone(sum_oath_counts((None,None),plain))
        self.assertIsNone(oath_observations(SimpleNamespace(source=plain)))
        with self.assertRaises(ValueError):
            validate_oath_counts((),plain,trials=1,started_rounds=1,actions=2)

    def test_exact_nonnegative_scalars_and_readmission(self):
        for name in ('prayers','wound_negations','glorious_activations','unmitigated_activations',
                'fate_spends','fate_session_cost'):
            for value in (True,1.0,'1',-1):
                with self.subTest(name=name,value=value),self.assertRaises((TypeError,ValueError)):
                    PcOathCount('pc',**{name:value})
        bad=PcOathCount(self.source.pc_activation_order[0])
        object.__setattr__(bad,'prayers',True)
        with self.assertRaises(TypeError):
            validate_oath_counts((bad,self.counts[1]),self.source,trials=1,started_rounds=1,actions=2)
        with self.assertRaises((TypeError,ValueError)):
            replace(self.record,oath_counts=None)
        with self.assertRaises(ValueError):
            replace(self.summary,oath_counts=(PcOathCount('foreign'),))

    def test_missing_talents_and_once_battle_limit_do_not_accept_fabricated_counts(self):
        actor=self.source.pc_activation_order[0]
        for bad in (PcOathCount(actor,prayers=2),PcOathCount(actor,wound_negations=2),
                PcOathCount(actor,glorious_activations=1),
                PcOathCount(actor,unmitigated_activations=1,fate_spends=1)):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                validate_oath_counts((bad,PcOathCount(self.source.enemy_activation_order[0])),
                    self.source,trials=1,started_rounds=1,actions=2)

    def test_honour_is_once_session_npc_has_no_fate_and_lucky_funding_is_actual(self):
        source=native_source(pc_talents=(honour(),),npc_talents=(honour(),),
            pc_context=context(),npc_context=context())
        pc,npc=source.pc_activation_order[0],source.enemy_activation_order[0]
        for rows in ((PcOathCount(pc,glorious_activations=1,unmitigated_activations=1,fate_spends=1),PcOathCount(npc)),
                (PcOathCount(pc),PcOathCount(npc,unmitigated_activations=1,fate_spends=1)),
                (PcOathCount(pc,unmitigated_activations=1),PcOathCount(npc)),
                (PcOathCount(pc,unmitigated_activations=1,fate_spends=1),PcOathCount(npc))):
            with self.subTest(rows=rows),self.assertRaises(ValueError):
                validate_oath_counts(rows,source,trials=1,started_rounds=1,actions=2)
        source=replace(source,party=(replace(source.party[0],
            oath_context=context(honour_bound_used_this_session=True)),))
        with self.assertRaises(ValueError):
            validate_oath_counts((PcOathCount(pc,glorious_activations=1),PcOathCount(npc)),
                source,trials=1,started_rounds=1,actions=2)
        for lucky in (False,True):
            actual=with_native_outcome_owner(magic_battle('staff',pc_strength=6,npc_toughness=3,rounds=1),
                fate=0 if lucky else 1,lucky=lucky)
            member=actual.party[0]
            actual=replace(actual,party=(replace(member,pc=replace(member.pc,weapon_skill=1,melee=1)),))
            result=run_pc_melee_scenario(actual,LiteralD10())
            self.assertEqual(oath_observations(result),(PcOathCount(actual.pc_activation_order[0],
                unmitigated_activations=1,fate_spends=1,fate_session_cost=0 if lucky else 1),))
            request=PcMeleeSimulationRequest(actual,42,1)
            with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',return_value=result):
                record=run_pc_melee_trial(request,0)
            summary=summarize_pc_melee_simulation(PcMeleeSimulationResult(request,(record,)))
            document=json.loads(encode_pc_melee_simulation_result(command(request),summary))
            validate_pc_melee_simulation_document(document,'result')
            self.assertEqual(document['summary']['oath_counts'][0]['fate_session_cost'],0 if lucky else 1)

    def test_honour_and_other_spends_share_session_pool_and_one_lucky_free_use(self):
        from towr.simulation.pc_melee_models import PcGloriousSpendCount
        for lucky in (False,True):
            source=with_native_outcome_owner(magic_battle('staff'),fate=0 if lucky else 1,lucky=lucky)
            actor=source.pc_activation_order[0]
            rows=(PcOathCount(actor,unmitigated_activations=1,fate_spends=1,
                fate_session_cost=0 if lucky else 1),)
            validate_oath_fate_budget(rows,source,(PcGloriousSpendCount(actor,0),),None,trials=1)
            with self.assertRaisesRegex(ValueError,'same actual session'):
                validate_oath_fate_budget(rows,source,(PcGloriousSpendCount(actor,1),),None,trials=1)

    def test_actual_glorious_activation_is_not_a_fate_spend(self):
        source=native_source(pc_talents=(honour(),),npc_talents=(honour(),),
            pc_context=context(),npc_context=context())
        member=source.party[0]
        source=replace(source,party=(replace(member,fate=replace(member.fate,rating=0,session_spend_limit=0)),))
        result=run_pc_melee_scenario(source,LiteralD10())
        self.assertEqual(oath_observations(result),tuple(PcOathCount(actor,glorious_activations=1)
            for actor in oath_count_actors(source)))

    def test_prebattle_prayer_is_not_counted_as_an_executed_action(self):
        source=native_source(pc_talents=(lady(free=True),),npc_talents=(lady(free=True),),
            pc_context=lady_context(prebattle=True),npc_context=lady_context(prebattle=True))
        result=run_pc_melee_scenario(source,LiteralD10())
        self.assertEqual(oath_observations(result),tuple(PcOathCount(actor) for actor in oath_count_actors(source)))
        with self.assertRaises(ValueError):
            validate_oath_counts(self.counts,source,trials=1,started_rounds=1,actions=2)

    def test_actual_pc_wound_negation_keeps_paid_prayer_distinct(self):
        from towr.domain.armour_models import ArmourLoadout
        from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon
        from tests.support.generated_weapon_sources import initial_generated_weapons
        initial=automatic_source(pc_count=1,enemy_count=2,rounds=1)
        actor=initial.pc_activation_order[0]
        member=replace(initial.party[0],talents=(lady(free=True),),oath_context=lady_context())
        weak=GeneratedNpc(3,1,3,3,4,4,initial_generated_weapons(GeneratedWeapon.DAGGER),
            ArmourLoadout(),defence=4)
        strong=replace(weak,strength=6)
        source=replace(initial,party=(member,),enemies=tuple(npc.participant(identifier)
            for npc,identifier in zip((weak,strong),initial.enemy_activation_order,strict=True)))
        result=run_pc_melee_scenario(source,LiteralD10(1))
        self.assertEqual(oath_observations(result),(PcOathCount(actor,prayers=1,wound_negations=1),))

    def test_actual_profile_wound_negation_counts_once_without_prebattle_action(self):
        original=magic_battle('scarab_knife',pc_strength=6,npc_toughness=3,
            pc_toughness=20,rounds=1,initial_charges=0)
        enemy=original.enemies[0]
        npc=replace(enemy.definition.generated_components,talents=(lady(free=True),),
            oath_context=lady_context(prebattle=True))
        source=replace(original,enemies=(npc.participant(enemy.state.actor_id),))
        result=run_pc_melee_scenario(source,LiteralD10(1))
        self.assertEqual(oath_observations(result),(PcOathCount(enemy.state.actor_id,wound_negations=1),))
        request=PcMeleeSimulationRequest(source,42,1)
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',return_value=result):
            record=run_pc_melee_trial(request,0)
        summary=summarize_pc_melee_simulation(PcMeleeSimulationResult(request,(record,)))
        document=json.loads(encode_pc_melee_simulation_result(command(request),summary))
        validate_pc_melee_simulation_document(document,'result')
        self.assertEqual(document['summary']['oath_counts'][0]['wound_negations'],1)

    def test_duplicate_actual_prayer_receipt_cannot_double_count(self):
        step=next(step for step in self.result.steps if type(step.proof) is PcLadyPrayerProof)
        result=SimpleNamespace(source=self.source,state=self.result.state,
            steps=(*self.result.steps,step),started_rounds=1,executed_actions=3)
        with self.assertRaisesRegex(ValueError,'duplicated'):
            oath_observations(result)

    def test_prayer_shares_pc_and_npc_action_ceilings(self):
        pc=self.source.pc_activation_order[0];npc=self.source.enemy_activation_order[0]
        with self.assertRaisesRegex(ValueError,'same actor'):
            validate_automatic_action_budget((PcHelpActionCount(pc,1),),(PcAllyRecoverActionCount(pc,0),),
                self.source,started_rounds=1,oath_counts=(PcOathCount(pc,prayers=1),))
        with self.assertRaisesRegex(ValueError,'same actor'):
            validate_npc_action_budget((PcNpcExtraAttackCount(npc,0),),(PcNpcHelpActionCount(npc,1),),
                (PcNpcRecoverActionCount(npc,0),),started_rounds=1,oath_counts=(PcOathCount(npc,prayers=1),))

    def test_dynamic_candidate_codec_retains_actual_rows_and_source_presence(self):
        from tests.integration.test_oath_source_json import request_document
        import towr.adapters.dynamic_encounter_json as codec
        from towr.application.dynamic_encounter import GeneratedCandidate
        raw=request_document()
        raw['max_rounds']=1
        raw['targets']['started_rounds']={'numerator':1,'denominator':1}
        parsed=codec.parse_dynamic_encounter_request(json.dumps(raw))
        npc=next(value for value in (parsed.request.space.sample(Random(seed)) for seed in range(20))
            if value.oath_context is not None)
        source=parsed.request.scenario((npc,),'actual:oath-observations')
        result=run_pc_melee_scenario(source,LiteralD10())
        request=PcMeleeSimulationRequest(source,42,1)
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',return_value=result):
            record=run_pc_melee_trial(request,0)
        summary=summarize_pc_melee_simulation(PcMeleeSimulationResult(request,(record,)))
        candidate=GeneratedCandidate((npc,),summary)
        document=json.loads(json.dumps(codec.candidate_document(parsed.request,candidate)))
        validator=codec._validator('result').evolve(schema={
            '$ref':'urn:towr:dynamic-encounter:common:1#/$defs/candidate'})
        validator.validate(document)
        self.assertEqual([row['actor_id'] for row in document['oath_counts']],
            list(oath_count_actors(source)))
        self.assertEqual(sum(row['prayers'] for row in document['oath_counts']),2)
        for change in ('missing','bool','unknown'):
            bad=deepcopy(document)
            if change=='missing':del bad['oath_counts']
            elif change=='bool':bad['oath_counts'][0]['fate_spends']=True
            else:bad['oath_counts'][0]['fake_fate']=1
            with self.subTest(change=change),self.assertRaises(ValidationError):
                validator.validate(bad)

    def test_current_json_has_source_conditional_strict_rows(self):
        document=json.loads(encode_pc_melee_simulation_result(command(self.request),self.summary))
        self.assertEqual(document['summary']['oath_counts'],[dict(actor_id=row.actor_id,prayers=1,
            wound_negations=0,glorious_activations=0,unmitigated_activations=0,fate_spends=0,fate_session_cost=0)
            for row in self.counts])
        validate_pc_melee_simulation_document(document,'result')
        for change in ('missing','empty','bool','foreign'):
            bad=deepcopy(document)
            if change=='missing':del bad['summary']['oath_counts']
            elif change=='empty':bad['summary']['oath_counts']=[]
            elif change=='bool':bad['summary']['oath_counts'][0]['prayers']=True
            else:bad['summary']['oath_counts'][0]['burns']=1
            with self.subTest(change=change),self.assertRaises(ValidationError):
                validate_pc_melee_simulation_document(bad,'result')
