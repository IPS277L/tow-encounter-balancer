"""Effect-bank folding over real K1 music and combat-clock receipts."""
from types import SimpleNamespace
from unittest import TestCase

from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_battlefield_musician_resolution import action_request
from towr.domain.pc_musician_effect_models import (
    PcMusicianActionProof,active_music_sources,musician_defends_ties,pc_attack_success_wins,
)
from towr.domain.turn_models import (CombatTurnEndRequest,CombatTurnStartRequest,CombatRoundAdvanceRequest,
    CombatActionSlotRequest,CombatActionDeclaration,CombatActionKind,ActionSlotGrant)
from towr.domain.condition_models import ConditionState
from towr.domain.magic_models import WizardMagicState
from towr.domain.recover_models import RecoverActionExecutionRequest,RecoverMode,RecoverStandardChoice
from towr.rules.recover_resolution import execute_recover_action
from towr.rules.battlefield_musician_resolution import execute_battlefield_musician_action
from towr.rules.turn_resolution import end_combat_turn,start_combat_turn,advance_combat_round,reserve_combat_action_slot


def effect():
    request=action_request()
    rng=ScriptedD10([1,10])
    result=execute_battlefield_musician_action(request,rng)
    rng.assert_exhausted()
    return PcMusicianActionProof(result)


def next_round(proof,*,remove_musician=False):
    clock=proof.result.round_state
    history=[proof]
    actor=clock.active_turn.actor_id
    clock=end_combat_turn(CombatTurnEndRequest('music:end',clock,actor)).state
    while not clock.round_complete:
        participant=next(participant for participant in clock.participants
            if participant.entity_id not in clock.completed_turn_entity_ids and participant.side is clock.next_side)
        started=start_combat_turn(CombatTurnStartRequest('ally:start:'+participant.entity_id,clock,participant.entity_id))
        history.append(started)
        reserved=reserve_combat_action_slot(CombatActionSlotRequest('ally:reserve:'+participant.entity_id,
            started.state,participant.entity_id,CombatActionDeclaration(CombatActionKind.RECOVER),ActionSlotGrant.STANDARD))
        request=RecoverActionExecutionRequest('ally:recover:'+participant.entity_id,reserved.state,
            participant.entity_id,ConditionState(),False,1,RecoverMode.STANDARD,RecoverStandardChoice(WizardMagicState()))
        rng=ScriptedD10([])
        recovered=execute_recover_action(request,rng)
        rng.assert_exhausted()
        clock=end_combat_turn(CombatTurnEndRequest('ally:end:'+participant.entity_id,
            recovered.round_state,participant.entity_id)).state
    roster=tuple(member for member in clock.participants if not remove_musician or member.entity_id!=actor)
    advanced=advance_combat_round(CombatRoundAdvanceRequest('music:advance',clock,roster))
    history.append(advanced)
    return history,advanced.state


class MusicianEffectLifetimeTests(TestCase):
    def test_grant_changes_only_positive_ties_for_the_actual_distinct_ally(self):
        proof=effect()
        state=SimpleNamespace(history=(proof,))
        self.assertTrue(musician_defends_ties(state,'ally1'))
        self.assertFalse(musician_defends_ties(state,'ally2'))
        self.assertFalse(pc_attack_success_wins(state,'opponent','ally1',0,0))
        self.assertFalse(pc_attack_success_wins(state,'opponent','ally1',1,1))
        self.assertTrue(pc_attack_success_wins(state,'opponent','ally1',2,1))
        self.assertTrue(pc_attack_success_wins(state,'opponent','ally1',1,0))
        self.assertTrue(pc_attack_success_wins(state,'opponent','ally2',1,1))

    def test_other_turns_and_round_advance_do_not_expire_the_effect(self):
        proof=effect()
        history,clock=next_round(proof)
        for count in range(1,len(history)+1):
            self.assertTrue(musician_defends_ties(SimpleNamespace(history=tuple(history[:count])),'ally1'))
        started=start_combat_turn(CombatTurnStartRequest('music:next-turn',clock,'musician'))
        self.assertEqual(active_music_sources(SimpleNamespace(history=(*history,started))),())

    def test_no_phantom_turn_when_musician_leaves_the_actual_next_roster(self):
        proof=effect()
        history,clock=next_round(proof,remove_musician=True)
        started=start_combat_turn(CombatTurnStartRequest('survivor:turn',clock,'ally1'))
        state=SimpleNamespace(history=(*history,started))
        self.assertTrue(musician_defends_ties(state,'ally1'))
        self.assertEqual(active_music_sources(state),(proof.result,))

    def test_receiving_snapshot_stays_frozen_after_later_hearing_or_range_changes(self):
        proof=effect()
        frozen=proof.result.selected_listeners
        # This pure fold intentionally has no current hearing/position owner.
        state=SimpleNamespace(history=(proof,),music_audible=False,recipient_deafened=True,recipient_range='far')
        self.assertTrue(musician_defends_ties(state,'ally1'))
        self.assertEqual(proof.result.selected_listeners,frozen)
