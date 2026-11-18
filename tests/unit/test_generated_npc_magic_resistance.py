"""Actual target-scoped Magic Resistance in generated encounters (PG78).

Forecast snapshots below inspect decisions only. Native receipt assertions use
literal d10 runs and replay the complete real source-bound journal.
"""
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.armour_fixtures import light_loadout
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_magic_scenarios import magic_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon,GeneratedTalent
from towr.domain.magic_models import (
    SpellCastRequest,SpellCastExecutionRequest,IdentifiedSpellTarget,
)
from towr.domain.pc_magic_miscast_plan import PcMagicTaskKind
from towr.domain.pc_magic_models import (
    PcCastingProof,PcMagicEffectProof,PcMiscastRollProof,PcMagicCleanupProof,
    generated_spell_potency_modifiers,spell_choice,
)
from towr.domain.pc_magic_source_models import PcSpellId,pc_spell_definition
from towr.domain.pc_melee_result_models import (
    PcMeleeOutcome,PcMeleeStep,initial_pc_melee_state,
)
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step
from towr.rules.spell_cast_execution import resolve_spell_cast_targets
from towr.rules.stone_troll import MAGIC_RESISTANCE_RULE_ID


def npc(*,resistant=True,toughness=5,weapon_skill=1,shield=False):
    return GeneratedNpc(weapon_skill,1,toughness,1,2,2,initial_generated_weapons(GeneratedWeapon.STAFF),light_loadout(light=False, shield=shield),
        defence=6,
        talents=(GeneratedTalent.MAGIC_RESISTANCE,) if resistant else ())


def scenario(components, *,spell=PcSpellId.LIGHTNING_BLAST,reason=2,
        willpower=10,level=4,rounds=1):
    source=magic_scenario(reason=reason,willpower=willpower,level=level,
        rounds=rounds,enemies=len(components),spells=(spell,))
    return replace(source,enemies=tuple(value.participant(f'minion{i+1}')
        for i,value in enumerate(components)))


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def proofs(result,kind):
    return tuple(step.proof for step in result.steps if type(step.proof) is kind)


class GeneratedNpcMagicResistanceTests(unittest.TestCase):
    def test_target_execution_records_one_to_zero_and_two_to_one_without_fake_effects(self):
        enemy=npc().participant('resistant')
        definition=pc_spell_definition(PcSpellId.LIGHTNING_BLAST)
        for potency in (1,2):
            source=SpellCastRequest('scope:cast','caster',definition.rule_id,
                definition.lore_id,definition.casting_value,potency,'RULE-MAGIC-004:cast-or-wait')
            request=SpellCastExecutionRequest('scope:targets',source,enemy.state.actor_id,
                (IdentifiedSpellTarget(enemy.state.actor_id,generated_spell_potency_modifiers(enemy)),))
            result=resolve_spell_cast_targets(request)
            with self.subTest(potency=potency):
                target=result.targets[0]
                self.assertEqual((target.potency.base_potency,target.potency.potency_delta,
                    target.potency.effective_potency),(potency,-1,potency-1))
                self.assertEqual(target.potency.applied_rule_ids,(MAGIC_RESISTANCE_RULE_ID,))
                self.assertEqual(len(result.follow_ups),int(potency==2))
                self.assertEqual(target.effect_request is None,potency==1)

    def test_native_lightning_damage_changes_wound_to_real_stagger(self):
        for resistant in (False,True):
            source=scenario((npc(resistant=resistant),))
            result=execute(source,[1,1]+([10,10] if resistant else []))
            with self.subTest(resistant=resistant):
                cast=proofs(result,PcCastingProof)[0]
                target=cast.targets.targets[0]
                self.assertEqual(target.potency.effective_potency,2-int(resistant))
                self.assertEqual(target.potency.potency_delta,-int(resistant))
                effects=proofs(result,PcMagicEffectProof)
                self.assertEqual([p.task.value for p in effects],[6-int(resistant)])
                injury=result.state.enemy('minion1').state.injury
                self.assertEqual(injury.defeated,not resistant)
                self.assertEqual(injury.conditions.has(Condition.STAGGERED),resistant)

    def test_native_fire_keeps_original_target_count_and_each_positive_targets_fixed_damage(self):
        source=scenario((npc(toughness=3),npc(resistant=False,toughness=3),npc(toughness=3)),
            spell=PcSpellId.FIRE_BREATH)
        result=execute(source,[1,1,10,10])
        cast=proofs(result,PcCastingProof)[0]
        self.assertEqual(tuple(target.target_id for target in cast.targets.targets),('minion1','minion2'))
        self.assertEqual(tuple(target.potency.effective_potency for target in cast.targets.targets),(1,2))
        effects=proofs(result,PcMagicEffectProof)
        self.assertEqual([(p.task.target_id,p.task.value) for p in effects],[('minion1',4),('minion2',4)])
        self.assertTrue(result.state.enemy('minion1').state.injury.defeated)
        self.assertTrue(result.state.enemy('minion2').state.injury.defeated)
        self.assertFalse(result.state.enemy('minion3').state.injury.defeated)

    def test_advice_does_not_value_immune_staggered_target_and_drained_does_not_disable_resistance(self):
        source=scenario((npc(),))
        state=initial_pc_melee_state(source)
        enemy=state.enemies[0]
        for conditions in ((Condition.STAGGERED,), (Condition.STAGGERED,Condition.DRAINED)):
            current=replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
                conditions=ConditionState(frozenset(conditions)))))
            snapshot=replace(state,enemies=(current,))
            with self.subTest(conditions=conditions):
                self.assertEqual(spell_choice(snapshot,'pc1',1),(None,(),0.0))
                self.assertEqual(generated_spell_potency_modifiers(current)[0].amount,-1)
                self.assertEqual(spell_choice(snapshot,'pc1',2)[1:], (('minion1',),1.0))

    def test_native_last_roll_one_fire_chooses_nonresistant_foe_without_false_hit_on_resistant(self):
        source=scenario((npc(toughness=3),npc(resistant=False,toughness=3)),
            spell=PcSpellId.FIRE_BREATH,rounds=2,willpower=5)
        result=execute(source,[1,10]+[10]*4+[1,10]+[10]*2)
        casts=proofs(result,PcCastingProof)
        self.assertIsNone(casts[0].spell_id)
        self.assertEqual(tuple(t.target_id for t in casts[1].targets.targets),('minion2',))
        self.assertFalse(result.state.enemy('minion1').state.injury.defeated)
        self.assertTrue(result.state.enemy('minion2').state.injury.defeated)

    def test_optional_pre_miscast_spell_uses_resistance_then_finishes_real_miscast(self):
        source=scenario((npc(toughness=4),),reason=4,willpower=5,level=1)
        result=execute(source,[1,1,9,9,1,1,1])
        cast=proofs(result,PcCastingProof)[0]
        self.assertIsNotNone(cast.preparation)
        self.assertEqual(cast.targets.targets[0].potency.effective_potency,1)
        self.assertEqual(proofs(result,PcMagicEffectProof)[0].task.value,5)
        self.assertEqual(len(proofs(result,PcMiscastRollProof)[0].result.roll_values),3)
        self.assertEqual(len(proofs(result,PcMagicCleanupProof)),1)
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_miscast_wind_is_not_a_spell_and_still_affects_resistant_npcs(self):
        source=scenario((npc(toughness=100,weapon_skill=6),npc(toughness=100,weapon_skill=6)),
            reason=4,willpower=1,level=1)
        result=execute(source,[9]*4+[5,5,6,6]+[10]*16)
        self.assertEqual(proofs(result,PcMiscastRollProof)[0].result.total,22)
        tasks=[p.task for p in proofs(result,PcMagicEffectProof)]
        self.assertEqual(tuple(task.target_id for task in tasks),('pc1','minion1','minion2'))
        self.assertTrue(all(task.kind is PcMagicTaskKind.PRONE for task in tasks))
        self.assertTrue(all(e.state.injury.conditions.has(Condition.PRONE) for e in result.state.enemies))

    def test_full_replay_rejects_forged_target_potency_and_duplicate_cast(self):
        source=scenario((npc(),))
        result=execute(source,[1,1,10,10])
        state=initial_pc_melee_state(source)
        for step in result.steps:
            if type(step.proof) is PcCastingProof:
                proof=deepcopy(step.proof)
                target=proof.targets.targets[0]
                altered=replace(target,potency=replace(target.potency,
                    potency_delta=0,effective_potency=2,applied_rule_ids=()))
                proof=replace(proof,targets=replace(proof.targets,targets=(altered,)))
                with self.assertRaises(ValueError):
                    PcMeleeStep(state,proof)
            state=apply_pc_melee_step(state,step)
            if type(step.proof) is PcCastingProof:
                with self.assertRaises(ValueError):
                    apply_pc_melee_step(state,step)
        self.assertEqual(state,result.state)


if __name__=='__main__':
    unittest.main()
