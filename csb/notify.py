"""Desktop notifications (GNotification) for sessions entering Needs you or Finished.

DESIGN.md §8: notify only on a transition into needs/done, never for states that
already existed at start-up, never when notifications are off, never twice for
the same transition.
"""
from gi.repository import Gio, GLib

from . import model

ACTION_FOCUS = "app.focus"
NOTIFY_STATES = (model.NEEDS, model.DONE)


def entering(prev, sessions):
    """Sessions whose state just became needs/done. `prev` maps session_id -> last state."""
    return [
        s for s in sessions
        if s.state in NOTIFY_STATES and prev.get(s.session_id) != s.state
    ]


def snapshot_states(sessions):
    return {s.session_id: s.state for s in sessions}


def text_for(session):
    """(title, body, priority) for a notification."""
    if session.state == model.NEEDS:
        body = session.message or "Claude needs your input"
        return f"{session.project} needs you", body, Gio.NotificationPriority.URGENT
    body = "Done. Waiting for your next prompt."
    return f"{session.project} is finished", body, Gio.NotificationPriority.NORMAL


def build(session, icon_png):
    """Build the Gio.Notification for one session."""
    title, body, priority = text_for(session)
    notif = Gio.Notification.new(title)
    notif.set_body(body)
    notif.set_priority(priority)
    if icon_png:
        notif.set_icon(Gio.BytesIcon.new(GLib.Bytes.new(icon_png)))
    notif.add_button_with_target("Open terminal", ACTION_FOCUS, GLib.Variant("s", session.session_id))
    notif.set_default_action_and_target(ACTION_FOCUS, GLib.Variant("s", session.session_id))
    return notif


def notification_id(session):
    return f"csb-{session.session_id}-{session.state}"
