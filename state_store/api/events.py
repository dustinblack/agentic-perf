from __future__ import annotations

from fastapi import APIRouter, Query, Request

router = APIRouter(prefix="/tickets", tags=["events"])


@router.get("/{ticket_id}/events")
def get_events(
    ticket_id: str,
    request: Request,
    since: int = Query(0, description="Return events with seq > this value"),
    limit: int = Query(200, description="Max events to return"),
):
    event_bus = getattr(request.app.state, "event_bus", None)
    if event_bus is None:
        return {"events": [], "latest_seq": 0}
    events = event_bus.get_events(ticket_id, since=since, limit=limit)
    latest_seq = events[-1]["seq"] if events else since
    return {"events": events, "latest_seq": latest_seq}


@router.get("/{ticket_id}/transcript")
def get_transcript(
    ticket_id: str,
    request: Request,
    agent: str = Query(None, description="Filter to a single agent name"),
):
    """Return all events for a ticket as a full transcript (no limit)."""
    event_bus = getattr(request.app.state, "event_bus", None)
    if event_bus is None:
        return {"ticket_id": ticket_id, "events": []}
    events = event_bus.get_events(ticket_id, since=0, limit=10000)
    if agent:
        events = [e for e in events if e.get("agent") == agent]

    store = request.app.state.store
    ticket = store.get(ticket_id)
    ticket_data = {}
    if ticket:
        ticket_data = {
            "summary": ticket.summary,
            "description": ticket.description,
            "status": ticket.status.value,
        }

    return {
        "ticket_id": ticket_id,
        "ticket": ticket_data,
        "events": events,
    }
