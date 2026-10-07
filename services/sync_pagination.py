from rest_framework.pagination import CursorPagination


class SyncCursorPagination(CursorPagination):
    """
    Cursor pagination for mobile synchronization endpoints.

    Provides stable pagination for datasets that may change
    while the mobile client is downloading records.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    ordering = "-updated_at"