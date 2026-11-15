"""A csoportokhoz és az órákhoz tartozó műveletek, HTTP nélkül."""

import logging

from django.db.models import Q
from django.utils import timezone

from .models import Class

logger = logging.getLogger(__name__)


def sync_lesson_states():
    """A tárolt állapotot hozzáigazítja az időpontokhoz.

    A hozzáférést a Class.effective_state dönti el, ami akkor is helyes, ha ez
    a függvény nem futott le. Ez csak a tárolt mezőt igazítja - hogy az
    adminban és a szűrésekben a valóság látsszon.
    """
    now = timezone.now()

    # Előbb a zárás: ami lejárt, azt a következő lekérdezés ne nyissa ki.
    closed = (
        Class.objects.filter(closed_at__isnull=False, closed_at__lte=now)
        .exclude(state=Class.State.CLOSED)
        .update(state=Class.State.CLOSED)
    )

    opened = (
        Class.objects.filter(opened_at__isnull=False, opened_at__lte=now)
        .filter(Q(closed_at__isnull=True) | Q(closed_at__gt=now))
        .exclude(state=Class.State.OPEN)
        .update(state=Class.State.OPEN)
    )

    planned = (
        Class.objects.filter(opened_at__isnull=False, opened_at__gt=now)
        .exclude(state=Class.State.PLANNED)
        .update(state=Class.State.PLANNED)
    )

    if closed or opened or planned:
        logger.info("Lesson states synced: closed=%s opened=%s planned=%s", closed, opened, planned)

    return {"closed": closed, "opened": opened, "planned": planned}