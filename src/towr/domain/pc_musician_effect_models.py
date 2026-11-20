"""Native Battlefield Musician sources and their actual next-turn lifetime.

PG1.4 III73; hearing at grant and disappearance are ADR-0141 C17 choices.
The journal is the source bank: no round-end timer or death heuristic can
silently replace the musician's next actual TurnStart.
"""
from dataclasses import dataclass, replace

from towr.rules.attack_resolution import ATTACK_TIE_RULE_ID
from towr.domain.talent_tie_models import compose_talent_tie_break
from towr.domain.test_models import OpposedSide, TieBreak
from towr.domain.turn_models import CombatTurnStartResult


@dataclass(frozen=True, slots=True)
class PcMusicianActionProof:
    result: object
    decline: object | None = None
    glorious: object | None = None

    def __post_init__(self):
        from towr.domain.talent_battlefield_musician_models import BattlefieldMusicianActionResult
        if type(self.result) is not BattlefieldMusicianActionResult:
            raise TypeError('music requires its exact completed Leadership action')
        replace(self.result)


@dataclass(frozen=True, slots=True)
class PcMusicianSignalProof:
    result: object

    def __post_init__(self):
        from towr.domain.talent_battlefield_musician_models import BattlefieldMusicianSignalResult
        if type(self.result) is not BattlefieldMusicianSignalResult:
            raise TypeError('music signal requires its exact own-turn receipt')
        replace(self.result)


def active_music_sources(state):
    """Return accepted paid actions not followed by their owner's actual turn.

    A recipient's subsequent movement/Deafened and a musician's death/exit do
    not end an already granted effect. Zero-success actions grant no source.
    """
    sources = []
    for proof in state.history:
        if type(proof) is CombatTurnStartResult:
            actor = proof.turn.actor_id
            sources = [source for source in sources if source.source_request.source.actor_id != actor]
        elif type(proof) is PcMusicianActionProof and proof.result.beneficiary_ids:
            sources.append(proof.result)
    return tuple(sources)


def musician_defends_ties(state, target_id: str) -> bool:
    return any(target_id in source.beneficiary_ids for source in active_music_sources(state))


def pc_attack_tie_break(state, attacker_id: str, target_id: str) -> TieBreak | None:
    sources = tuple(source for source in active_music_sources(state) if target_id in source.beneficiary_ids)
    if not sources:
        return None
    ordinary = TieBreak(ATTACK_TIE_RULE_ID, OpposedSide.INITIATOR)
    preferences = tuple(TieBreak('RULE-TALENT-002:battlefield-musician:'
        + str(len(source.source_request.id)) + ':' + source.source_request.id,
        OpposedSide.OPPONENT) for source in sources)
    return compose_talent_tie_break(ordinary, preferences)


def pc_attack_success_wins(state, attacker_id: str, target_id: str,
        successes: int, opposed: int) -> bool:
    if not successes:
        return False
    source = pc_attack_tie_break(state, attacker_id, target_id)
    return successes > opposed or (successes == opposed
        and (source is None or source.winner is OpposedSide.INITIATOR))
