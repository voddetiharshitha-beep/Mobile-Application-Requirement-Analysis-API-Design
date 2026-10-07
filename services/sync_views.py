
from datetime import datetime

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Booking
from .serializers import BookingSerializer
from .sync_pagination import SyncCursorPagination


class BookingSyncView(APIView):
    """
    Incremental synchronization endpoint for mobile clients.

    The mobile client provides the timestamp from its
    previous successful synchronization.

    Only bookings changed after that timestamp are returned.

    Cursor pagination is used so the client can safely
    continue when many records have changed.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        synced_at = timezone.now()

        updated_after = request.query_params.get(
            "updated_after"
        )

        queryset = (
            Booking.objects
            .select_related(
                "customer",
                "provider",
                "service",
            )
            .filter(
                customer=request.user,
            )
            .order_by(
                "-updated_at",
            )
        )

        if updated_after:
            try:
                updated_after_datetime = (
                    timezone.datetime.fromisoformat(
                        updated_after.replace(
                            "Z",
                            "+00:00",
                        )
                    )
                )
            except ValueError:
                return Response(
                    {
                        "success": False,
                        "message": (
                            "updated_after must be a "
                            "valid ISO 8601 datetime."
                        ),
                        "error_code": (
                            "INVALID_SYNC_TIMESTAMP"
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            queryset = queryset.filter(
                updated_at__gt=updated_after_datetime,
                updated_at__lte=synced_at,
            )

        paginator = SyncCursorPagination()

        page = paginator.paginate_queryset(
            queryset,
            request,
            view=self,
        )

        serializer = BookingSerializer(
            page,
            many=True,
            context={
                "request": request,
            },
        )

        next_link = paginator.get_next_link()

        response_data = {
            "success": True,
            "data": serializer.data,
            "sync": {
                "updated_after": updated_after,
                "synced_at": synced_at,
                "has_more": next_link is not None,
                "next_cursor": next_link,
            },
        }

        return Response(
            response_data,
            status=status.HTTP_200_OK,
        )
