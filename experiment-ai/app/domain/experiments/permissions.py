from app.domain.experiments.access_context import ExperimentAccessContext, ExperimentMemberRoleEnum
from app.core.enums import UserRoleEnum


# Permission checks for experiment operations

def can_view_experiment(ctx: ExperimentAccessContext) -> bool:
    """
    Who can view:
    - owner
    - any member (viewer or editor)
    """
    if ctx.is_owner:
        return True

    if ctx.member_role is not None:
        return True

    return False

def can_edit_experiment(ctx: ExperimentAccessContext) -> bool:
    """
    Who can edit:
    - owner
    - members with EDITOR role
    """
    if ctx.is_owner:
        return True

    if ctx.member_role == ExperimentMemberRoleEnum.EDITOR:
        return True

    return False

def can_archive_experiment(ctx: ExperimentAccessContext) -> bool:
    """
    Who can archive:
    - owner only
    - admins (handled outside via global permission)
    """
    return ctx.is_owner

def can_create_experiment(user) -> bool:
    """
    Who can create experiments:
    - any authenticated user
    - except CONSUMER
    """
    if user.role == UserRoleEnum.CONSUMER:
        return False

    return True


# Permission checks for experiment members management

def can_manage_members(ctx: ExperimentAccessContext) -> bool:
    """
    Who can manage members:
    - owner
    - members with EDITOR role
    """
    if ctx.is_owner:
        return True

    if ctx.member_role == ExperimentMemberRoleEnum.EDITOR:
        return True

    return False
