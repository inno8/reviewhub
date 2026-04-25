"""
Pagination classes for the grading app.

The DRF default `PageNumberPagination` ignores `?page_size=N` from the
client, so callers are stuck with the global PAGE_SIZE=20. The grading
inbox has very different sweet spots: a teacher skimming the day's
unread PRs wants 5-10 rows, a CSV export wants the lot. Both need
`page_size` to be tunable per-request.
"""
from __future__ import annotations

from rest_framework.pagination import PageNumberPagination


class GradingPagination(PageNumberPagination):
    """
    Standard PageNumberPagination + client-tunable page size.

    - `?page_size=5` works (default DRF doesn't honor this)
    - Capped at 100 to prevent accidental "give me everything" hits
      that would balloon DB load on a real cohort.
    - Default stays at 20 — same as the global setting, no behavior
      change for existing callers that don't pass page_size.
    """
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
