"""Close-range standard Recover with an explicit ally and ordinary damage."""
from dataclasses import replace

from tests.support.pc_glorious_scenarios import active_glorious_source
from towr.domain.attack_models import DamageProfile
from towr.domain.pc_melee_models import PcAllyRecoverPolicy,PcMeleePolicy


def active_ally_recover_source():
    source=active_glorious_source()
    actor,ally=source.party
    actor=replace(actor,policy=PcMeleePolicy.RECOVER_ALLY_OR_ATTACK_OR_RECOVER_SELF,
        ally_recover_policy=PcAllyRecoverPolicy(ally.actor_id))
    party=[]
    for member in (actor,ally):
        priority=tuple(reversed(member.target_priority))
        party.append(replace(member,target_priority=priority,
            defeat_decisions=tuple(member.defeat_decision(target) for target in priority)))
    enemies=tuple(replace(enemy,definition=replace(enemy.definition,
        attacks=(replace(enemy.definition.attacks[0],damage=DamageProfile(1)),))) for enemy in source.enemies)
    return replace(source,party=tuple(party),enemies=enemies,
        enemy_target_priority=(ally.actor_id,actor.actor_id))
