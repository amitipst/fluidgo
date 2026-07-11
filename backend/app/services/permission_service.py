"""Data-scope resolver — v3.1 with region-based org structure.

Org hierarchy for fluidPro:
  business_head (Amit) → sees ALL regions within fluidPro globally
  bu_head → sees own BU/region only (e.g. a regional head hired per-BU)
  manager → sees own team (direct reports via manager_id)
  rep / pre_sales → own data only

DUAL ROLE: any of the above can ALSO be personally assigned as someone's
manager_id — independent of region/bu/business — e.g. a bu_head of West who
additionally line-manages one rep in North, or a business_head who directly
manages a small team rather than delegating to a separate manager account.
resolve_visible_user_ids() unions those personal direct reports into every
role's normal scope, so this works everywhere (DSR approval, targets, FGA,
meetings, pipeline, opportunities...) not just a single dedicated screen.
Set it via the Team page → edit a user → "Reports to (Manager)".

Region values (canonical):
  India - North | India - South | India - West | India - East | India - Central
  Global - fluidPro (for business_head / global roles)
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User, ROLE_HIERARCHY, role_level


INDIA_REGIONS = [
    "India - North",
    "India - South",
    "India - West",
    "India - East",
    "India - Central",
]


async def resolve_visible_user_ids(
    db: AsyncSession,
    current_user: User,
    region_filter: Optional[str] = None    # optional region drill-down for business_head
) -> Optional[list]:
    """Returns list of user UUIDs visible to current_user.
    Returns None = sees everyone (CEO/super_admin).

    region_filter: when business_head passes a region name, scope narrows to that region.

    DUAL-ROLE SUPPORT: any role (manager, bu_head, business_head, ...) can
    ALSO be personally assigned as someone's manager_id, independent of
    region/bu/business — e.g. a BU Head of West who is additionally the
    direct manager of one rep in North. Whatever the role's normal scope
    query returns is UNIONED with those personal direct reports, so a dual
    role works consistently across every router that calls this function
    (DSR approval, targets, FGA, meetings, pipeline, opportunities, etc.) —
    not just the one screen that happens to call resolve_direct_report_ids
    directly. Skipped when region_filter is set: an explicit single-region
    drill-down should show only that region, not leak in an out-of-region
    direct report.
    """
    scope = ROLE_HIERARCHY.get(current_user.role, {}).get("scope", "own")

    async def _with_dual_role(base_ids: Optional[list]) -> Optional[list]:
        if base_ids is None or region_filter:
            return base_ids
        extra = await resolve_direct_report_ids(db, current_user)
        if not extra:
            return base_ids
        return list(set(base_ids) | set(extra))

    # CEO / super_admin — see everything
    if scope == "all":
        if region_filter:
            result = await db.execute(
                select(User.id).where(User.region == region_filter, User.is_active == True)
            )
            return [row[0] for row in result.all()]
        return None

    # HR — all users (FGA audit only)
    if scope == "hr":
        result = await db.execute(select(User.id).where(User.is_active == True))
        return [row[0] for row in result.all()]

    # Finance — all users (approved FGA export)
    if scope == "finance":
        result = await db.execute(select(User.id).where(User.is_active == True))
        return [row[0] for row in result.all()]

    # Business Head (Amit) — all users in this business across ALL regions
    if scope == "business":
        q = select(User.id).where(
            User.business == current_user.business,
            User.is_active == True
        )
        if region_filter:
            q = q.where(User.region == region_filter)
        result = await db.execute(q)
        return await _with_dual_role([row[0] for row in result.all()])

    # BU Head (legacy) — users in same bu + business
    if scope == "bu":
        q = select(User.id).where(
            User.bu == current_user.bu,
            User.business == current_user.business,
            User.is_active == True
        )
        if region_filter:
            q = q.where(User.region == region_filter)
        result = await db.execute(q)
        return await _with_dual_role([row[0] for row in result.all()])

    # Manager — direct reports only
    if scope == "team":
        result = await db.execute(
            select(User.id).where(
                User.manager_id == current_user.id,
                User.is_active == True
            )
        )
        direct_reports = [row[0] for row in result.all()]
        if not direct_reports:
            # Fallback: same region + business
            result = await db.execute(
                select(User.id).where(
                    User.region == current_user.region,
                    User.business == current_user.business,
                    User.is_active == True
                )
            )
            return [row[0] for row in result.all()]
        return direct_reports

    # Default: own only, plus any personal direct reports (dual-role field
    # roles are rare but not disallowed — e.g. a senior rep temporarily
    # mentoring one junior hire before a formal manager is hired).
    return await _with_dual_role([current_user.id])


async def resolve_direct_report_ids(db: AsyncSession, current_user: User) -> list:
    """Returns user IDs that report directly to current_user via manager_id —
    independent of role. This is what lets someone with a dual hat (e.g. a
    business_head who also personally line-manages a small sales/pre-sales
    team, rather than delegating that to a separate 'manager' role account)
    get a focused "My Team" view on top of whatever their primary role
    already grants via resolve_visible_user_ids.

    Deliberately has NO role gate and NO fallback-to-region behaviour (unlike
    the "team" scope branch above) — if you have zero direct reports, you get
    an empty list, full stop. The caller decides what to do with that (e.g.
    hide the "My Team" toggle in the UI when this is empty)."""
    result = await db.execute(
        select(User.id).where(
            User.manager_id == current_user.id,
            User.is_active == True
        )
    )
    return [row[0] for row in result.all()]


async def get_region_summary(
    db: AsyncSession,
    current_user: User,
    period: str,
) -> list[dict]:
    """Returns performance summary sliced by region.
    Only available to business_head and above.
    Used for the Regional Performance Dashboard."""
    from app.models import DSRDaily
    from app.services.rigor_service import calculate_avg_rigor
    from sqlalchemy import func
    from datetime import date
    from calendar import monthrange

    if role_level(current_user.role) < 40:
        return []   # Only business_head and above

    yr, mo = int(period[:4]), int(period[5:7])
    start = date(yr, mo, 1)
    end   = date(yr, mo, monthrange(yr, mo)[1])

    # Get all regions with users in this business
    regions_result = await db.execute(
        select(User.region, func.count(User.id).label("team_size"))
        .where(User.business == current_user.business, User.is_active == True,
               User.region != None, User.region != 'Global - fluidPro')
        .group_by(User.region)
        .order_by(User.region)
    )
    region_rows = regions_result.all()

    summary = []
    for region, team_size in region_rows:
        # Get user IDs for this region
        region_users = (await db.execute(
            select(User.id).where(
                User.business == current_user.business,
                User.region == region,
                User.is_active == True,
                User.role.in_(["rep", "inside_sales", "pre_sales", "manager"])
            )
        )).scalars().all()

        if not region_users:
            continue

        # DSR data for this region in the period
        dsrs = (await db.execute(
            select(DSRDaily).where(
                DSRDaily.user_id.in_(region_users),
                DSRDaily.date >= start,
                DSRDaily.date <= end
            )
        )).scalars().all()

        working = [d for d in dsrs if d.status == "working"]
        compliance_pct = round(
            len({d.user_id for d in dsrs}) / max(len(region_users), 1) * 100, 1
        )

        summary.append({
            "region":          region,
            "team_size":       team_size,
            "dsr_days":        len(dsrs),
            "working_days":    len(working),
            "total_calls":     sum(d.calls for d in dsrs),
            "total_visits":    sum(d.visits for d in dsrs),
            "total_followups": sum(d.followups for d in dsrs),
            "total_leads":     sum(d.new_leads for d in dsrs),
            "total_proposals": sum(d.proposals for d in dsrs),
            "avg_rigor":       calculate_avg_rigor(dsrs),
            "dsr_compliance_pct": compliance_pct,
        })

    # Sort by avg_rigor descending (best region first)
    summary.sort(key=lambda x: x["avg_rigor"], reverse=True)
    for i, row in enumerate(summary):
        row["rank"] = i + 1
    return summary


async def can_user_edit_target(
    db: AsyncSession, actor: User, target_user_id: str
) -> bool:
    if role_level(actor.role) >= 40:   # business_head and above
        return True
    visible = await resolve_visible_user_ids(db, actor)
    if visible is None:
        return True
    import uuid
    return uuid.UUID(target_user_id) in visible
