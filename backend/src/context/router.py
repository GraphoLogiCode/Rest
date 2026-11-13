from src.visualization.client import owner_lock
from uuid import UUID

from fastapi import APIRouter

from src.auth import CurrentUser
from src.context.schemas import FeedbackIn, InsightOut, Period, SummaryOut
from src.context.summary import RULE_VERSION, input_version, insight_text, period_bounds, summarize
from src.errors import not_found
from src.storage import StoreDep
from src.timestamps import today_in

router = APIRouter(prefix="/v1", tags=["summary"])


@router.get("/summary", response_model=SummaryOut)
async def read_summary(user: CurrentUser, store: StoreDep, period: Period = "week") -> SummaryOut:
    async with owner_lock(user.id, store):
        profile = store.get_or_create_profile(user.id)
        today = today_in(profile.timezone)
        start, end = period_bounds(period, today)
        checkins = store.list_checkins(user.id, start, end)
        summary = summarize(checkins, start, end)
        # Saved so feedback has something to attach to. The same inputs and rule
        # version always return the same stored insight.
        insight = store.save_insight(
            user.id, start, end, input_version(checkins, start, end), RULE_VERSION, insight_text(summary)
        )
        return SummaryOut(
            period=period,
            period_start=start,
            period_end=end,
            timezone=profile.timezone,
            insight=InsightOut.model_validate(insight),
            **summary,
        )


@router.post("/insights/{insight_id}/feedback", response_model=InsightOut)
async def give_feedback(insight_id: UUID, body: FeedbackIn, user: CurrentUser, store: StoreDep) -> InsightOut:
    async with owner_lock(user.id, store):
        insight = store.set_insight_feedback(user.id, insight_id, body.feedback)
        if insight is None:
            raise not_found("Insight")
        return InsightOut.model_validate(insight)
