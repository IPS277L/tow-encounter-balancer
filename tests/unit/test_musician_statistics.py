"""Counters over an actual replayed music battle and exact source boundaries."""
from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from tests.integration.test_immediate_attack_counts_json import command
from tests.integration.test_musician_native import music_scenario,npc_music_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_tactics_fixtures import automatic_source
from towr.adapters.pc_melee_json import encode_pc_melee_simulation_result
from towr.adapters.pc_melee_json_schema import validate_pc_melee_simulation_document
from towr.domain import talent_actor_models
from towr.domain.pc_melee_result_models import PcAttackProof
from towr.domain.pc_musician_effect_models import PcMusicianActionProof,PcMusicianSignalProof
from towr.domain.talent_catalog import TalentId
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_models import (
    PcMeleeSimulationRequest,PcMeleeSimulationResult,PcHelpActionCount,PcAllyRecoverActionCount,
    PcNpcExtraAttackCount,PcNpcHelpActionCount,PcNpcRecoverActionCount,
    validate_automatic_action_budget,validate_npc_action_budget,
)
from towr.simulation.pc_melee_simulation import run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
from towr.simulation.pc_musician_statistics import (
    PcMusicianCount,musician_count_actors,musician_observations,sum_musician_counts,validate_musician_counts,
)


class MusicianStatisticsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        for name in ('PC_EXECUTABLE_TALENTS','NPC_EXECUTABLE_TALENTS'):
            values=getattr(talent_actor_models,name)
            if TalentId.BATTLEFIELD_MUSICIAN not in values:
                raise AssertionError('statistics acceptance requires the connected public Musician cap')
        cls.source=replace(music_scenario(),enemy_target_priority=('pc2','pc1','pc3'))
        rng=ScriptedD10([1,10,10,10,10]+[10]*10+[1,10,1,10,10]+[10]*10)
        cls.result=run_pc_melee_scenario(cls.source,rng)
        rng.assert_exhausted()
        cls.counts=musician_observations(cls.result)
        cls.request=PcMeleeSimulationRequest(cls.source,42,1)
        # Reuse that genuine native result for extraction/transport; these
        # fixtures do not claim independent Monte Carlo trials or new rolls.
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',return_value=cls.result):
            cls.record=run_pc_melee_trial(cls.request,0)
        cls.batch=PcMeleeSimulationResult(cls.request,(cls.record,))
        cls.summary=summarize_pc_melee_simulation(cls.batch)

    def test_real_action_signal_and_lost_positive_tie_are_counted_once(self):
        self.assertEqual(self.counts,(PcMusicianCount('pc1',actions=1,inspired_allies=1,
            signals=1,protected_ties=1),))
        self.assertEqual(sum(type(step.proof) is PcMusicianActionProof for step in self.result.steps),1)
        self.assertEqual(sum(type(step.proof) is PcMusicianSignalProof for step in self.result.steps),1)
        self.assertEqual(self.result.executed_actions,6)
        self.assertEqual(self.record.music_counts,self.counts)
        self.assertEqual(self.summary.music_counts,self.counts)
        validate_musician_counts(self.counts,self.source,trials=1,
            started_rounds=self.result.started_rounds,actions=self.result.executed_actions)

    def test_each_complete_source_row_is_required_in_exact_pc_then_npc_order(self):
        npc_source=npc_music_scenario()
        both=replace(self.source,enemies=npc_source.enemies)
        self.assertEqual(musician_count_actors(both),('pc1','minion1'))
        zeros=(PcMusicianCount('pc1'),PcMusicianCount('minion1'))
        validate_musician_counts(zeros,both,trials=0,started_rounds=0,actions=0)
        for changed in (None,(),zeros[::-1],zeros[:1],(*zeros,zeros[0])):
            with self.subTest(changed=changed),self.assertRaises((TypeError,ValueError)):
                validate_musician_counts(changed,both,trials=1,started_rounds=1,actions=6)
        self.assertEqual(sum_musician_counts((zeros,zeros),both),zeros)

    def test_absent_source_uses_none_and_aggregate_preserves_all_zero_rows(self):
        plain=automatic_source(pc_count=1,enemy_count=1,rounds=1)
        self.assertIsNone(sum_musician_counts((None,None),plain))
        self.assertIsNone(musician_observations(SimpleNamespace(source=plain,steps=())))
        with self.assertRaises(ValueError):
            validate_musician_counts((),plain,trials=1,started_rounds=1,actions=2)
        zero=(PcMusicianCount('pc1'),)
        self.assertEqual(sum_musician_counts((),self.source),zero)
        self.assertEqual(sum_musician_counts((self.counts,zero,self.counts),self.source),
            (PcMusicianCount('pc1',actions=2,inspired_allies=2,signals=2,protected_ties=2),))

    def test_literal_scalar_source_and_observation_bounds_reject_fabricated_totals(self):
        for name in ('actions','pickups','inspired_allies','signals','protected_ties'):
            for value in (True,1.0,'1',-1):
                with self.subTest(name=name,value=value),self.assertRaises((TypeError,ValueError)):
                    PcMusicianCount('pc1',**{name:value})
        for row in (PcMusicianCount('pc1',actions=3),PcMusicianCount('pc1',signals=2),
                PcMusicianCount('pc1',actions=1,inspired_allies=3),
                PcMusicianCount('pc1',protected_ties=1),
                PcMusicianCount('pc1',actions=1,inspired_allies=1,protected_ties=19)):
            with self.subTest(row=row),self.assertRaises(ValueError):
                validate_musician_counts((row,),self.source,trials=1,started_rounds=1,actions=6)
        with self.assertRaises((TypeError,ValueError)):
            replace(self.record,music_counts=None)
        with self.assertRaises(ValueError):
            replace(self.summary,music_counts=(PcMusicianCount('foreign'),))
        corrupt=PcMusicianCount('pc1')
        object.__setattr__(corrupt,'actions',True)
        with self.assertRaises(TypeError):
            validate_musician_counts((corrupt,),self.source,trials=1,started_rounds=1,actions=6)

    def test_receipt_extraction_rejects_double_observation_of_one_actual_action(self):
        step=next(step for step in self.result.steps if type(step.proof) is PcMusicianActionProof)
        duplicate=SimpleNamespace(source=self.source,steps=(*self.result.steps,step))
        with self.assertRaisesRegex(ValueError,'duplicated'):
            musician_observations(duplicate)

    def test_prepared_paid_tool_pickup_receipts_are_distinct_from_inspiration_actions(self):
        from tests.unit.test_musician_equipment import prepared,prepared_after
        from tests.unit.test_musician_tool_history import PreparationView
        from tests.support.talent_sources import free_talent
        from towr.domain.pc_battlefield_musician_models import PcMusicianRecoverProof
        from towr.domain.pc_musician_equipment_models import plan_musician_equipment
        from towr.domain.pc_tool_models import actor_tool_zone
        from towr.domain.tool_inventory_models import drop_tool
        from towr.domain.talent_models import TalentOwnerFacts,TalentLoreFact
        from towr.domain.magic_models import WizardMagicState
        from towr.domain.recover_models import (
            RecoverActionExecutionRequest,RecoverMode,RecoverObjectInteractionFollowUp,RecoverStandardChoice,
        )
        from towr.domain.turn_models import (
            ActionSlotGrant,CombatActionDeclaration,CombatActionKind,CombatActionSlotRequest,
        )
        from towr.rules.recover_resolution import execute_recover_action
        from towr.rules.turn_resolution import reserve_combat_action_slot
        # Explicit prepared owner views, not fabricated full native journals.
        for generated in (False,True):
            with self.subTest(generated=generated):
                state=prepared(hands=2,generated=generated)
                actor='minion1' if generated else 'pc'
                facts=TalentOwnerFacts(fellowship=4,lores=(TalentLoreFact('music',False),))
                talents=(free_talent(TalentId.BATTLEFIELD_MUSICIAN),)
                if generated:
                    enemy=state.enemy(actor)
                    npc=replace(enemy.definition.generated_components,fellowship=4,leadership=4,
                        talents=talents,talent_facts=facts)
                    source_enemy=npc.participant(actor)
                    source=replace(state.source,enemies=(source_enemy,))
                    current=replace(enemy,definition=source_enemy.definition)
                    state=PreparationView(state,source=source,enemies=(current,))
                    body=current.state
                else:
                    member=state.source.party[0]
                    member=replace(member,pc=replace(member.pc,fellowship=4,leadership=4),
                        talents=talents,talent_facts=facts)
                    source=replace(state.source,party=(member,))
                    state=PreparationView(state,source=source)
                    body=state.participant(actor)
                item=body.tool_inventory.items[0]
                state=prepared_after(state,plan_musician_equipment(state,actor,item.id))
                body=state.enemy(actor).state if generated else state.participant(actor)
                dropped=drop_tool(actor,body.tool_inventory,item.id,actor_zone_id=actor_tool_zone(state,actor)).after
                if generated:
                    state=PreparationView(state,enemies=(replace(state.enemy(actor),state=replace(body,tool_inventory=dropped)),))
                else:
                    state=PreparationView(state,party=(replace(body,tool_inventory=dropped),))
                clock=reserve_combat_action_slot(CombatActionSlotRequest('music:pickup:reserve',state.round_state,
                    actor,CombatActionDeclaration(CombatActionKind.RECOVER),ActionSlotGrant.STANDARD)).state
                state=PreparationView(state,round_state=clock)
                equipment=plan_musician_equipment(state,actor,item.id,pickup=True)
                choice=RecoverStandardChoice(WizardMagicState(),object_interaction=
                    RecoverObjectInteractionFollowUp('music:pickup:interaction',actor,item.id,True))
                request=RecoverActionExecutionRequest('music:pickup:execute',clock,actor,body.injury.conditions,
                    True,1,RecoverMode.STANDARD,choice)
                rng=ScriptedD10([])
                result=execute_recover_action(request,rng)
                rng.assert_exhausted()
                proof=PcMusicianRecoverProof(result,equipment)
                observed=musician_observations(SimpleNamespace(source=source,
                    steps=(SimpleNamespace(source=state,proof=proof),)))
                self.assertEqual(observed,(PcMusicianCount(actor,pickups=1),))
                validate_musician_counts(observed,source,trials=1,started_rounds=1,actions=1)

    def test_music_and_other_pc_support_cannot_borrow_one_anothers_turn(self):
        helped=tuple(PcHelpActionCount(member.actor_id,int(member.actor_id=='pc1')) for member in self.source.party)
        recovered=tuple(PcAllyRecoverActionCount(member.actor_id,0) for member in self.source.party)
        music=(PcMusicianCount('pc1',actions=1),)
        with self.assertRaisesRegex(ValueError,'same actor'):
            validate_automatic_action_budget(helped,recovered,self.source,started_rounds=1,music_counts=music)
        helped=tuple(PcHelpActionCount(member.actor_id,int(member.actor_id=='pc2')) for member in self.source.party)
        validate_automatic_action_budget(helped,recovered,self.source,started_rounds=1,music_counts=music)

    def test_npc_music_and_pickup_share_the_actual_npc_action_budget(self):
        source=npc_music_scenario()
        ids=source.enemy_activation_order
        extra=tuple(PcNpcExtraAttackCount(actor,0) for actor in ids)
        helped=tuple(PcNpcHelpActionCount(actor,int(actor==ids[0])) for actor in ids)
        recovered=tuple(PcNpcRecoverActionCount(actor,0) for actor in ids)
        with self.assertRaisesRegex(ValueError,'same actor'):
            validate_npc_action_budget(extra,helped,recovered,started_rounds=1,
                music_counts=(PcMusicianCount(ids[0],pickups=1),))
        helped=tuple(PcNpcHelpActionCount(actor,int(actor==ids[1])) for actor in ids)
        validate_npc_action_budget(extra,helped,recovered,started_rounds=1,
            music_counts=(PcMusicianCount(ids[0],actions=1),))

    def test_current_simulation_json_retains_mandatory_observations_and_strict_shape(self):
        document=json.loads(encode_pc_melee_simulation_result(command(self.request),self.summary))
        self.assertEqual(document['summary']['music_counts'],[dict(actor_id='pc1',actions=1,pickups=0,
            inspired_allies=1,signals=1,protected_ties=1)])
        validate_pc_melee_simulation_document(document,'result')
        for change in ('missing','empty','bool','foreign_field'):
            bad=deepcopy(document)
            if change=='missing':del bad['summary']['music_counts']
            elif change=='empty':bad['summary']['music_counts']=[]
            elif change=='bool':bad['summary']['music_counts'][0]['actions']=True
            else:bad['summary']['music_counts'][0]['fate']=1
            with self.subTest(change=change),self.assertRaises(ValidationError):
                validate_pc_melee_simulation_document(bad,'result')

    def test_dynamic_presence_fragment_requires_rows_only_for_actual_music_sources(self):
        from pathlib import Path
        schema=json.loads(Path('src/towr/adapters/schemas/dynamic-encounter-common.schema.json').read_text(encoding='utf-8'))
        validator=Draft202012Validator(schema['$defs']['musicCandidatePresence'])
        raw={'replay':{'scenario':{'party':[{'talents':[{'id':'battlefield_musician'}]}],'enemies':[]}},'music_counts':[]}
        validator.validate(raw)
        del raw['music_counts']
        with self.assertRaises(ValidationError):validator.validate(raw)
        raw['replay']['scenario']['party'][0]['talents']=[]
        validator.validate(raw)
        raw['music_counts']=[]
        with self.assertRaises(ValidationError):validator.validate(raw)
