"""Actual continuous Casting and Miscast journals on literal d10 sequences."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_magic_scenarios import magic_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.attack_models import ResilienceProfile
from towr.domain.condition_models import Condition
from towr.domain.magic_models import MiscastTableEntryId
from towr.domain.pc_magic_source_models import PcSpellId
from towr.domain.pc_magic_miscast_plan import PcMagicTaskKind
from towr.domain.pc_magic_models import (PcCastingProof, PcMiscastRollProof,
    PcMagicEffectProof, PcMagicCleanupProof, PcMagicUnsupported)
from towr.domain.pc_melee_result_models import (PcMeleeOutcome, PcAttackProof,
    PcHandDropProof, PcMeleeStep, initial_pc_melee_state)
from towr.domain.test_models import TestQuality
from towr.engine.pc_melee_runner import run_pc_melee_scenario, apply_pc_melee_step


_MISCAST_ROLLS = {
    2:(1,1), 3:(1,2), 4:(2,2), 5:(2,3), 6:(3,3), 7:(3,4), 8:(4,4),
    9:(4,5), 10:(5,5), 11:(5,6), 12:(6,6), 13:(6,7), 14:(7,7),
    15:(7,8), 16:(8,8), 17:(8,9), 18:(9,9), 19:(9,10), 20:(10,10),
    21:(5,5,5,6), 22:(5,5,6,6), 23:(5,6,6,6), 24:(6,6,6,6),
    25:(6,6,6,7), 26:(6,6,7,7), 27:(6,7,7,7), 28:(7,7,7,7),
    29:(7,7,7,8), 30:(7,7,8,8), 31:(7,8,8,8), 32:(8,8,8,8),
    33:(8,8,8,9), 34:(8,8,9,9), 35:(8,9,9,9), 36:(9,9,9,9),
    37:(9,9,9,10), 38:(9,9,10,10), 39:(9,10,10,10), 40:(10,10,10,10),
}


def execute(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def miscast_run(total, *, tail=(10,10,10,10), pc_count=1):
    roll = _MISCAST_ROLLS[total]
    source = magic_scenario(reason=len(roll),pc_count=pc_count)
    return execute(source,[9]*len(roll)+list(roll)+list(tail))


def resourced_enemies(source, profiles):
    enemies = []
    for enemy,resilience in zip(source.enemies,profiles,strict=True):
        definition = replace(enemy.definition,id=enemy.definition.id+':'+enemy.state.actor_id,
            resilience=resilience)
        enemies.append(replace(enemy,definition=definition,
            state=replace(enemy.state,definition_id=definition.id,current_resilience=resilience)))
    return replace(source,enemies=tuple(enemies))


def proofs(result, kind):
    return tuple(step.proof for step in result.steps if type(step.proof) is kind)


class PcMagicExecutionTests(unittest.TestCase):
    def test_rank_one_accumulates_cv_two_and_uses_only_last_roll_for_potency(self):
        source = magic_scenario(reason=1,willpower=5,rounds=2,enemies=1,
            spells=(PcSpellId.LIGHTNING_BLAST,))
        # First NPC hits for a first Staggered, leaving itself fresh; the second
        # Casting success releases the spell, then its next attack misses.
        result = execute(source,[1,1,10,1,10,10])
        casts = proofs(result,PcCastingProof)
        self.assertEqual(len(casts),2)
        self.assertIsNone(casts[0].spell_id)
        self.assertEqual(casts[0].execution.casting.state.casting_successes,1)
        self.assertIs(casts[1].spell_id,PcSpellId.LIGHTNING_BLAST)
        self.assertEqual(casts[1].execution.casting.state.casting_successes,2)
        self.assertEqual(casts[1].targets.targets[0].effect_request.potency,1)
        self.assertEqual(proofs(result,PcMagicEffectProof)[0].task.value,5)
        self.assertEqual(result.state.party[0].magic.casting_successes,0)
        self.assertEqual(result.state.party[0].magic.miscast_dice,0)
        self.assertEqual(result.executed_actions,4)
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)

    def test_lightning_uses_actual_target_armour_without_an_attack_or_protection_test(self):
        for armoured in (False,True):
            with self.subTest(armoured=armoured):
                source = magic_scenario(willpower=5,enemies=1,
                    spells=(PcSpellId.LIGHTNING_BLAST,))
                source = resourced_enemies(source,(ResilienceProfile(5,1) if armoured else ResilienceProfile(6),))
                result = execute(source,[1,1] + ([] if armoured else [10,10]))
                cast = proofs(result,PcCastingProof)[0]
                self.assertEqual(cast.targets.selected_target_id,'minion1')
                effect = proofs(result,PcMagicEffectProof)[0]
                self.assertEqual(effect.task.value,7 if armoured else 6)
                self.assertEqual(result.state.enemies[0].state.injury.defeated,armoured)
                self.assertFalse(any(p.request.actor_id=='pc1' for p in proofs(result,PcAttackProof)))
                self.assertEqual(result.executed_actions,1 if armoured else 2)

    def test_fire_breath_selects_distinct_foes_and_uses_each_targets_armour(self):
        source = magic_scenario(willpower=5,pc_count=2,spells=(PcSpellId.FIRE_BREATH,))
        source = resourced_enemies(source,(ResilienceProfile(3),ResilienceProfile(2,1)))
        # Allied PC misses, then the surviving armoured NPC misses.
        result = execute(source,[1,1]+[10,10,10,1,1]+[10,10])
        cast = proofs(result,PcCastingProof)[0]
        self.assertEqual(cast.targets.selected_target_id,source.facts.zone_id)
        effects = proofs(result,PcMagicEffectProof)
        self.assertEqual(tuple(p.task.target_id for p in effects),('minion1','minion2'))
        self.assertEqual(tuple(p.task.value for p in effects),(4,3))
        self.assertTrue(result.state.enemy('minion1').state.injury.defeated)
        self.assertTrue(result.state.enemy('minion2').state.injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(result.state.participant('pc2').injury.wounds)
        self.assertEqual(len(set(p.task.target_id for p in effects)),2)

    def test_nonnumeric_miscasts_keep_their_actual_entry_and_scene_subjects(self):
        for total in (2,3,4,7,8,9,10,15,16,25,26,29,30):
            with self.subTest(total=total):
                result = miscast_run(total)
                roll = proofs(result,PcMiscastRollProof)[0]
                self.assertEqual(roll.result.total,total)
                notes = result.state.magic_notes
                self.assertEqual(len(notes),1)
                self.assertIs(notes[0].note,roll.result.entry.id)
                self.assertIn('pc1',notes[0].affected_ids)
                self.assertIsNone(result.state.magic_pending)
                self.assertEqual(result.state.party[0].magic.miscast_dice,0)
                self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)

    def test_arcane_spill_adds_real_staggered_and_records_its_minor_manifestation(self):
        for total in (11,12):
            with self.subTest(total=total):
                result = miscast_run(total)
                self.assertTrue(result.state.party[0].injury.conditions.has(Condition.STAGGERED))
                self.assertEqual(tuple(p.task.kind for p in proofs(result,PcMagicEffectProof)),
                    (PcMagicTaskKind.STAGGER,PcMagicTaskKind.NOTE))
                self.assertIs(result.state.magic_notes[0].note,MiscastTableEntryId.ARCANE_SPILL)
                self.assertIsNone(result.state.magic_pending)

    def test_stench_penalty_applies_to_real_next_tests_and_leaves_fellowship_source(self):
        for total in (13,14):
            with self.subTest(total=total):
                result = miscast_run(total)
                attacks = proofs(result,PcAttackProof)
                first = attacks[0].request.kernel_request.attack
                self.assertTrue(any(m.amount==-1 for m in first.attacker_test.dice_modifiers))
                self.assertTrue(any(m.amount==-1 for m in first.defender_test.dice_modifiers))
                self.assertFalse(any(m.kind is PcMagicTaskKind.NEXT_TEST_PENALTY
                    for m in result.state.magic_modifiers))
                self.assertEqual(tuple(m.kind for m in result.state.magic_modifiers),
                    (PcMagicTaskKind.FELLOWSHIP_GRIM,))

    def test_daylight_blindness_is_actual_persistent_condition_with_grim_defence(self):
        for total in (19,20):
            with self.subTest(total=total):
                result = miscast_run(total)
                self.assertTrue(result.state.party[0].injury.conditions.has(Condition.BLINDED))
                defender = proofs(result,PcAttackProof)[0].request.kernel_request.attack.defender_test
                self.assertTrue(any(m.quality is TestQuality.GRIM for m in defender.quality_modifiers))
                self.assertTrue(any(m.kind is PcMagicTaskKind.BLINDED for m in result.state.magic_modifiers))

    def test_unnatural_wind_applies_prone_to_every_living_actor_before_any_attack(self):
        for total in (21,22):
            with self.subTest(total=total):
                result = miscast_run(total,tail=[10]*6)
                effects = proofs(result,PcMagicEffectProof)
                self.assertEqual(tuple(p.task.target_id for p in effects),('pc1','minion1','minion2'))
                self.assertTrue(all(p.task.kind is PcMagicTaskKind.PRONE for p in effects))
                self.assertTrue(result.state.party[0].injury.conditions.has(Condition.PRONE))
                self.assertTrue(all(e.state.injury.conditions.has(Condition.PRONE) for e in result.state.enemies))
                self.assertEqual(proofs(result,PcAttackProof)[0].request.kernel_request.attack.attacker_test.profile.base_dice,1)

    def test_arcane_sight_retains_its_awareness_context_without_general_glorious(self):
        for total in (27,28):
            with self.subTest(total=total):
                result = miscast_run(total)
                self.assertEqual(tuple(m.kind for m in result.state.magic_modifiers),
                    (PcMagicTaskKind.AWARENESS_GRIM,))
                self.assertIs(result.state.magic_notes[0].note,MiscastTableEntryId.ARCANE_SIGHT)
                attack = proofs(result,PcAttackProof)[0].request.kernel_request.attack
                self.assertFalse(any(m.quality is TestQuality.GLORIOUS for m in attack.defender_test.quality_modifiers))

    def test_internal_damage_completes_an_actual_wound_and_hand_drop_before_cleanup(self):
        for total in (31,32):
            with self.subTest(total=total):
                result = miscast_run(total,tail=[8,1]+[10]*8)
                wound = result.state.party[0].injury.wounds[0]
                self.assertEqual(wound.table_total,8)
                self.assertTrue(wound.effect_resolved)
                self.assertIsNone(result.state.party[0].weapon_hand)
                self.assertEqual(result.state.party[0].daily_wounds.wound_count,1)
                self.assertEqual(len(proofs(result,PcHandDropProof)),1)
                self.assertIsNone(result.state.pending_wound)
                self.assertFalse(result.state.pending)
                self.assertIsNone(result.state.magic_pending)

    def test_ear_damage_completes_fixed_wounds_for_all_party_and_defeats_minions(self):
        for total in (35,36):
            with self.subTest(total=total):
                # Caster Endurance10 and ally Endurance3 each gain one success.
                result = miscast_run(total,pc_count=2,tail=[1]+[10]*9+[1,10,10])
                self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
                for member in result.state.party:
                    self.assertEqual(member.injury.wounds[0].table_total,11)
                    self.assertTrue(member.injury.wounds[0].effect_resolved)
                    self.assertTrue(member.injury.conditions.has(Condition.DEAFENED))
                    self.assertEqual(member.daily_wounds.wound_count,1)
                self.assertTrue(all(e.state.injury.defeated for e in result.state.enemies))
                self.assertEqual(tuple(p.task.target_id for p in proofs(result,PcMagicEffectProof)),
                    ('pc1','pc2','minion1','minion2'))
                self.assertIsNone(result.state.magic_pending)
                self.assertEqual(result.state.party[0].magic.miscast_dice,0)
                self.assertEqual(result.executed_actions,1)

    def test_catastrophic_death_cleans_the_actual_pool_before_terminal_defeat(self):
        for total in (39,40):
            with self.subTest(total=total):
                result = miscast_run(total,tail=[])
                self.assertIs(result.outcome,PcMeleeOutcome.PARTY_DEFEATED)
                self.assertTrue(result.state.party[0].injury.dead)
                self.assertIsNone(result.state.magic_pending)
                self.assertEqual(result.state.party[0].magic.miscast_dice,0)
                self.assertEqual(len(proofs(result,PcMagicCleanupProof)),1)
                self.assertEqual(result.executed_actions,1)

    def test_gm_dependent_entries_keep_actual_roll_and_stop_before_effect_or_cleanup(self):
        for total in (5,6,17,18,23,24,33,34,37,38):
            with self.subTest(total=total):
                result = miscast_run(total,tail=[])
                self.assertIs(result.outcome,PcMeleeOutcome.UNSUPPORTED_PATH)
                self.assertIs(type(result.unsupported),PcMagicUnsupported)
                self.assertEqual(result.unsupported.total,total)
                roll = proofs(result,PcMiscastRollProof)[0]
                self.assertEqual(result.unsupported.entry_id,roll.result.entry.id.value)
                self.assertEqual(roll.result.roll_values,_MISCAST_ROLLS[total])
                self.assertFalse(proofs(result,PcMagicEffectProof))
                self.assertFalse(proofs(result,PcMagicCleanupProof))
                self.assertIsNotNone(result.state.magic_pending)
                self.assertEqual(result.state.party[0].magic.miscast_dice,len(_MISCAST_ROLLS[total]))

    def test_winning_spell_before_miscast_still_resolves_every_mandatory_phase(self):
        source = magic_scenario(reason=4,willpower=5,enemies=1,
            spells=(PcSpellId.LIGHTNING_BLAST,))
        source = resourced_enemies(source,(ResilienceProfile(3),))
        result = execute(source,[1,1,9,9,1,1,1])
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        cast = proofs(result,PcCastingProof)[0]
        self.assertIsNotNone(cast.preparation)
        self.assertIs(cast.spell_id,PcSpellId.LIGHTNING_BLAST)
        roll = proofs(result,PcMiscastRollProof)[0]
        self.assertEqual(len(roll.result.roll_values),3)  # 2 collected +1 for last-chance cast
        kinds = tuple(type(step.proof) for step in result.steps)
        self.assertLess(kinds.index(PcMagicEffectProof),kinds.index(PcMiscastRollProof))
        self.assertLess(kinds.index(PcMiscastRollProof),kinds.index(PcMagicCleanupProof))
        self.assertFalse(proofs(result,PcAttackProof))
        self.assertEqual(result.executed_actions,1)
        self.assertEqual(result.state.party[0].magic.miscast_dice,0)

    def test_complete_native_spell_journal_replays_and_rejects_forged_effects(self):
        source = magic_scenario(willpower=5,enemies=1,spells=(PcSpellId.LIGHTNING_BLAST,))
        result = execute(source,[1,1,10,10])
        current = initial_pc_melee_state(source)
        for step in result.steps:
            current = apply_pc_melee_step(current,step)
        self.assertEqual(current,result.state)
        step = next(step for step in result.steps if type(step.proof) is PcMagicEffectProof)
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(step.source,replace(step.proof,task=replace(step.proof.task,value=500)))
        with self.assertRaises((TypeError,ValueError)):
            apply_pc_melee_step(step.state,step)
        corrupted = deepcopy(step.proof)
        object.__setattr__(corrupted.task,'value',True)
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(step.source,corrupted)


if __name__ == '__main__':
    unittest.main()
