"""Actual Wounds, handless Recover and mandatory turn ends (ADR-0130)."""
from dataclasses import replace
import unittest

from tests.support.pc_pistol_scenarios import make_pc_pistol_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.attack_models import DamageProfile,ResilienceProfile
from towr.domain.pc_combat_equipment_models import PcWeaponItem,PcItemLocation
from towr.domain.pc_heavy_wound_models import usable_hands
from towr.domain.pc_melee_models import PcMeleePolicy,PcMeleeWeapon,PcWeaponHand,PcBackupWeaponPolicy
from towr.domain.pc_melee_result_models import (
    PcRecoverProof,PcAttackProof,PcTurnEndProof,PcMeleeOutcome,initial_pc_melee_state,
)
from towr.domain.pc_weapon_inventory import PcWeaponSwapProof
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step


def scene(*,party=1,endurance=4,automatic=True):
    source=make_pc_pistol_scenario(pc_count=party,enemy_count=4,max_rounds=3)
    member=source.party[0]
    member=replace(member,pc=replace(member.pc,endurance=endurance,
        ranged=replace(member.pc.ranged,ballistic_skill=6,shooting=6)),
        policy=PcMeleePolicy.AUTOMATIC_COMBAT if automatic else PcMeleePolicy.ATTACK_OR_RECOVER_SELF,
        combat_equipment=(PcWeaponItem('gun:owned',PcMeleeWeapon.PISTOL,PcItemLocation.HELD,PcWeaponHand.LEFT),
            PcWeaponItem('sword:owned',PcMeleeWeapon.SWORD,PcItemLocation.CARRIED,None)) if automatic else None,
        backup_weapon_policy=PcBackupWeaponPolicy(PcMeleeWeapon.SWORD,PcWeaponHand.LEFT) if automatic else None)
    enemies=[]
    for enemy in source.enemies:
        resilience=ResilienceProfile(1,10)
        attack=replace(enemy.definition.attacks[0],damage=DamageProfile(30))
        enemies.append(replace(enemy,definition=replace(enemy.definition,
            resilience=resilience,attacks=(attack,)),state=replace(enemy.state,current_resilience=resilience)))
    return replace(source,party=(member,*source.party[1:]),enemies=tuple(enemies),
        facts=replace(source.facts,outnumbering_bonus_approved=False))


def prefix(*,party=1):
    # First PC misses (6d vs2). Four NPC hits (2d vs3) inflict literal
    # Wounds1,2,16(right),18(left clutch) before the next own turn.
    return ([10]*8+([10]*3+[1]*2 if party==2 else [])
        +[1,1]+[10]*3+[1]
        +[1,1]+[10]*3+[1,1]
        +[1,1]+[10]*3+[10,1,5,10]
        +[1,1]+[10]*3+[10,6,1,1])


def party_rng(seed):
    # Fixed independent streams test mechanics/parity, not Monte Carlo rates.
    return ScriptedD10(prefix(party=2)+[10]*40)


class NoHandRecoverIntegrationTests(unittest.TestCase):
    def execute(self,source,tail):
        rng=ScriptedD10(prefix(party=len(source.party))+[10]*tail)
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        replay=initial_pc_melee_state(source)
        for step in result.steps:
            replay=apply_pc_melee_step(replay,step)
        self.assertEqual(replay,result.state)
        self.assertIsNone(result.unsupported)
        return result

    def recover_steps(self,result):
        return tuple(step for step in result.steps if type(step.proof) is PcRecoverProof
            and step.source.round_state.active_turn.actor_id=='pc1')

    def assert_physical_state_kept(self,steps):
        self.assertTrue(steps)
        for step in steps:
            before=step.source.participant('pc1');after=step.state.participant('pc1')
            self.assertEqual(usable_hands(before),())
            self.assertEqual(after.body_facts,before.body_facts)
            self.assertEqual(after.injury.wounds,before.injury.wounds)
            self.assertEqual(after.weapon_inventory,before.weapon_inventory)
            self.assertEqual(after.ranged,before.ranged)
            self.assertIsNone(step.proof.result.source_request.choice.object_interaction)
            self.assertTrue(step.state.round_state.active_turn.action_slots[-1].executed)

    def test_standard_recover_still_owes_critical_end_phase_and_actual_death(self):
        result=self.execute(scene(),14)
        recover,=self.recover_steps(result)
        self.assert_physical_state_kept((recover,))
        self.assertIs(result.outcome,PcMeleeOutcome.PARTY_DEFEATED)
        self.assertEqual([w.table_total for w in result.state.party[0].injury.wounds],[1,2,16,18])
        self.assertTrue(result.state.party[0].injury.dead)
        end,=tuple(step for step in result.steps if type(step.proof) is PcTurnEndProof
            and step.proof.critical is not None)
        self.assertEqual(end.source.round_state.round_number,2)
        self.assertGreater(result.steps.index(end),result.steps.index(recover))
        self.assertFalse(any(type(step.proof) is PcWeaponSwapProof for step in result.steps))

    def test_surviving_solo_pc_reaches_round_limit_without_fake_attack_or_pickup(self):
        result=self.execute(scene(endurance=10),46)
        recovers=self.recover_steps(result)
        self.assertEqual([step.source.round_state.round_number for step in recovers],[2,3])
        self.assert_physical_state_kept(recovers)
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
        self.assertFalse(result.state.party[0].injury.dead)
        self.assertEqual(result.executed_actions,15)
        self.assertEqual(sum(type(step.proof) is PcTurnEndProof and step.proof.critical is not None
            for step in result.steps),2)
        self.assertFalse(any(type(step.proof) is PcAttackProof and step.proof.request.actor_id=='pc1'
            and step.source.round_state.round_number>1 for step in result.steps))

    def test_other_pc_and_npcs_continue_after_injured_pc_recovers_and_dies(self):
        result=self.execute(scene(party=2),40)
        recover,=self.recover_steps(result)
        self.assert_physical_state_kept((recover,))
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
        self.assertTrue(result.state.participant('pc1').injury.dead)
        self.assertFalse(result.state.participant('pc2').injury.dead)
        later=result.steps[result.steps.index(recover)+1:]
        from towr.domain.pc_ranged_models import PcRangedReloadProof
        self.assertTrue(any(type(step.proof) in (PcAttackProof,PcRecoverProof,PcRangedReloadProof)
            and step.source.round_state.active_turn.actor_id=='pc2' for step in later))
        attacks=[step.proof.request.actor_id for step in later if type(step.proof) is PcAttackProof]
        self.assertTrue(any(actor.startswith('minion') for actor in attacks))

    def test_explicit_attack_policy_keeps_its_original_grip_stop(self):
        rng=ScriptedD10(prefix())
        result=run_pc_melee_scenario(scene(automatic=False),rng)
        rng.assert_exhausted()
        self.assertIs(result.outcome,PcMeleeOutcome.UNSUPPORTED_PATH)
        self.assertEqual((result.unsupported.reason,result.unsupported.table_total),('ranged_grip_unavailable',18))
        self.assertFalse(self.recover_steps(result))

    def test_actual_party_recover_and_critical_death_match_spawn_records(self):
        from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
        from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
        from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
        from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
        source=PcMeleeSimulationRequest(scene(party=2),42,2)
        sequential=run_pc_melee_simulation(source,rng_factory=party_rng)
        process=run_pc_melee_simulation_parallel(source,workers=2,batch_size=1,rng_factory=party_rng)
        self.assertEqual(process,sequential)
        self.assertEqual(summarize_pc_melee_simulation(process),summarize_pc_melee_simulation(sequential))
        self.assertEqual(process.outcome_counts.unsupported_path,0)


if __name__=='__main__':unittest.main()
