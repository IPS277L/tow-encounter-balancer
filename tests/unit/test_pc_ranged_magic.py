"""Actual Reload/Casting distinction for one automatic ranged Wizard."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.support.pc_magic_scenarios import magic_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_pc_ranged_advice import ranged_source
from towr.domain.attack_models import ResilienceProfile
from towr.domain.pc_magic_models import PcCastingProof,magic_hand
from towr.domain.pc_magic_source_models import PcSpellId
from towr.domain.pc_melee_models import PcFatePolicy,PcGloriousPolicy
from towr.domain.pc_melee_result_models import PcAttackProof,initial_pc_melee_state
from towr.domain.pc_ranged_models import PcRangedReloadProof
from towr.domain.pc_tactical_models import PcTacticalChoice
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatActionKind,ImproviseKind
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step


class PcRangedMagicTests(unittest.TestCase):
    def test_actual_casting_keeps_partial_reload_and_uses_its_own_slot_fate_and_hand(self):
        source=ranged_source(rounds=3)
        actor=source.party[0]
        wizard=magic_scenario(reason=2,willpower=5,spells=(PcSpellId.LIGHTNING_BLAST,)).party[0].wizard
        actor=replace(actor,wizard=wizard,fate_policy=PcFatePolicy.CONFIGURED,
            fate=replace(actor.fate,rating=1,session_spend_limit=1),
            glorious_policy=PcGloriousPolicy((Skill.WILLPOWER,),2,0))
        enemy=source.enemies[0]
        resilience=ResilienceProfile(100)
        enemy=replace(enemy,definition=replace(enemy.definition,resilience=resilience),
            state=replace(enemy.state,current_resilience=resilience))
        source=replace(source,party=(actor,),enemies=(enemy,),
            facts=replace(source.facts,daylight_confirmed=True,can_leave_zone=False))

        def advice(state,actor_id=None):
            actor_id=actor_id or state.round_state.active_turn.actor_id
            round_number=state.round_state.round_number
            return PcTacticalChoice(actor_id,
                CombatActionKind.ATTACK if round_number==1 else CombatActionKind.IMPROVISE,
                'minion1' if round_number==1 else None,None,1.0,'scripted:ranged-and-magic',
                weapon_item_id='gun',ranged_reload=round_number==2)

        # The spell gives the already-Staggered Minion its second Staggered,
        # ending the encounter before its third turn.
        rng=ScriptedD10([10]*9+[1,10,10]+[10]*3+[1,10,1])
        with patch('towr.domain.pc_tactical_models.select_pc_tactic',side_effect=advice):
            result=run_pc_melee_scenario(source,rng)
            rng.assert_exhausted()
            replay=initial_pc_melee_state(source)
            for step in result.steps:
                replay=apply_pc_melee_step(replay,step)
            self.assertEqual(replay,result.state)
        reload,=tuple(step for step in result.steps if type(step.proof) is PcRangedReloadProof)
        cast,=tuple(step for step in result.steps if type(step.proof) is PcCastingProof)
        shots=tuple(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.ranged_shot is not None)
        self.assertEqual(len(shots),1)
        self.assertEqual((shots[0].source.round_state.round_number,
            reload.source.round_state.round_number,cast.source.round_state.round_number),(1,2,3))
        partial=reload.state.party[0].ranged
        self.assertFalse(partial.loaded)
        self.assertEqual(partial.exacting.accumulated_successes,1)
        self.assertEqual(cast.source.party[0].ranged,partial)
        self.assertEqual(cast.state.party[0].ranged,partial)
        self.assertEqual(result.state.party[0].ranged,partial)
        self.assertEqual(magic_hand(cast.source,actor.actor_id),cast.source.party[0].weapon_hand)
        self.assertEqual(cast.source.party[0].weapon_inventory,cast.state.party[0].weapon_inventory)
        self.assertIsNotNone(cast.proof.glorious)
        self.assertEqual(cast.proof.execution.casting.test.trace.final_values,(1,1))
        self.assertEqual(cast.state.party[0].fate.remaining_spends,0)
        self.assertIs(cast.proof.spell_id,PcSpellId.LIGHTNING_BLAST)
        self.assertIs(reload.proof.request.round_state.active_turn.action_slots[0].declaration.improvise_kind,
            ImproviseKind.SKILL)
        self.assertEqual(result.executed_actions,5)


if __name__=='__main__':
    unittest.main()
