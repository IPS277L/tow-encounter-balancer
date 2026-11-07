"""Caller-confirmed Close facts and NPC dispositions for Skin Wolf end phases."""
from dataclasses import dataclass, replace

from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.pc_npc_blood_rage_policy_models import SKIN_WOLF_DEFINITION_ID
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition


WARPED_FORM_RULE_ID = 'RULE-PROFILE-MONSTER-011:warped-form'


@dataclass(frozen=True, slots=True)
class PcWarpedFormPolicy:
    actor_id: str
    close_actor_ids: tuple[str, ...]
    npc_defeat_decisions: tuple[MinionDefeatDecision, ...]

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('Warped Form requires an exact caster ID')
        if type(self.close_actor_ids) is not tuple:
            raise TypeError('Warped Form Close actors require an exact ordered tuple')
        for actor in self.close_actor_ids:
            if type(actor) is not str or not actor.strip():
                raise TypeError('Warped Form Close actor IDs must be exact nonempty strings')
            if actor == self.actor_id:
                raise ValueError('Warped Form wave excludes its caster')
        if len(set(self.close_actor_ids)) != len(self.close_actor_ids):
            raise ValueError('Warped Form Close actors must be unique')
        if type(self.npc_defeat_decisions) is not tuple:
            raise TypeError('Warped Form NPC decisions require an exact ordered tuple')
        for decision in self.npc_defeat_decisions:
            if type(decision) is not MinionDefeatDecision:
                raise TypeError('Warped Form NPC decisions require their exact type')
            replace(decision)
            if (type(decision.attacker_id) is not str or type(decision.target_id) is not str
                    or type(decision.disposition) is not NpcDefeatDisposition
                    or type(decision.gm_approved) is not bool):
                raise TypeError('Warped Form NPC decisions must retain exact nested types')
            if decision.attacker_id != self.actor_id:
                raise ValueError('Warped Form NPC decision must belong to its caster')
            if not decision.gm_approved:
                raise ValueError('Warped Form NPC disposition requires GM approval')


def validate_pc_warped_form_policies(policies, party, enemies) -> None:
    """PC↔NPC Close is known; same-side NPC Close is explicit and symmetric."""
    if type(policies) is not tuple:
        raise TypeError('Warped Form policies require an exact ordered tuple')
    pc_ids = {member.actor_id for member in party}
    enemy_by_id = {enemy.state.actor_id: enemy for enemy in enemies}
    known = pc_ids | set(enemy_by_id)
    by_actor = {}
    for policy in policies:
        if type(policy) is not PcWarpedFormPolicy:
            raise TypeError('Warped Form policy must retain its exact type')
        replace(policy)
        if policy.actor_id not in enemy_by_id:
            raise ValueError('Warped Form caster must belong to the source opposition')
        definition = enemy_by_id[policy.actor_id].definition
        validate_pc_book_npc_definition(definition)
        if definition.id != SKIN_WOLF_DEFINITION_ID:
            raise ValueError('Warped Form requires the canonical Skin Wolf')
        if policy.actor_id in by_actor:
            raise ValueError('each Skin Wolf must have at most one Warped Form policy')
        by_actor[policy.actor_id] = policy
        if not pc_ids <= set(policy.close_actor_ids):
            raise ValueError('Warped Form Close list must include every source PC exactly once')
        if not set(policy.close_actor_ids) <= known:
            raise ValueError('Warped Form Close actors must belong to the complete source')
        npc_targets = tuple(actor for actor in policy.close_actor_ids if actor in enemy_by_id)
        if tuple(decision.target_id for decision in policy.npc_defeat_decisions) != npc_targets:
            raise ValueError('Warped Form NPC decisions must cover Close NPCs in relative order')
    for actor, policy in by_actor.items():
        for other, other_policy in by_actor.items():
            if (other in policy.close_actor_ids) != (actor in other_policy.close_actor_ids):
                raise ValueError('configured Skin Wolves must have symmetric Close facts')
