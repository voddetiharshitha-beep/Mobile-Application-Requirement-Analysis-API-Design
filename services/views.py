from uuid import uuid4

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .models import Booking, Payment, Service, UserProfile
from .pagination import ServicePagination
from .serializers import (
    BookingSerializer,
    BookingStatusSerializer,
    PaymentInitiateSerializer,
    PaymentProcessSerializer,
    PaymentWebhookSerializer,
    ProfileImageSerializer,
    RegisterSerializer,
    ServiceSerializer,
)
from .tasks import create_notification


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class ServiceListCreateView(generics.ListCreateAPIView):
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ServicePagination

    def get_queryset(self):
        queryset = Service.objects.select_related(
            "category",
            "provider",
        ).all()

        name = self.request.query_params.get("name")
        category = self.request.query_params.get("category")
        provider = self.request.query_params.get("provider")
        location = self.request.query_params.get("location")
        price = self.request.query_params.get("price")
        min_price = self.request.query_params.get("min_price")
        max_price = self.request.query_params.get("max_price")
        status_filter = self.request.query_params.get("status")

        if name:
            queryset = queryset.filter(name__icontains=name)

        if category:
            queryset = queryset.filter(
                category__name__icontains=category
            )

        if provider:
            queryset = queryset.filter(
                provider__name__icontains=provider
            )

        if location:
            queryset = queryset.filter(
                location__icontains=location
            )

        if price:
            queryset = queryset.filter(price=price)

        if min_price:
            queryset = queryset.filter(price__gte=min_price)

        if max_price:
            queryset = queryset.filter(price__lte=max_price)

        if status_filter:
            queryset = queryset.filter(
                status=status_filter.lower() == "true"
            )

        ordering = self.request.query_params.get("ordering")

        if ordering in [
            "price",
            "-price",
            "-created_at",
        ]:
            queryset = queryset.order_by(ordering)

        return queryset


class ServiceDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated]


class BookingListCreateView(generics.ListCreateAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.select_related(
            "customer",
            "provider",
            "service",
        ).filter(
            customer=self.request.user
        ).order_by("-created_at")

    def perform_create(self, serializer):
        booking = serializer.save()

        transaction.on_commit(
            lambda: create_notification.delay(
                booking.customer_id,
                str(booking.id),
                "BOOKING_CREATED",
                "Your booking has been created successfully.",
            )
        )


class BookingDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.select_related(
            "customer",
            "provider",
            "service",
        ).filter(
            customer=self.request.user
        )

    def update(self, request, *args, **kwargs):
        booking = self.get_object()

        if booking.status == "cancelled":
            return Response(
                {
                    "detail": (
                        "Cancelled booking cannot be modified."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if booking.status == "completed":
            return Response(
                {
                    "detail": (
                        "Completed booking cannot be modified."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().update(
            request,
            *args,
            **kwargs,
        )


class BookingCancelView(generics.GenericAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.filter(
            customer=self.request.user
        )

    def post(self, request, *args, **kwargs):
        booking = self.get_object()

        if booking.status == "cancelled":
            return Response(
                {
                    "detail": "Booking is already cancelled."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if booking.status == "completed":
            return Response(
                {
                    "detail": (
                        "Completed booking cannot be cancelled."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking.status = "cancelled"
        booking.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        create_notification.delay(
            booking.customer_id,
            str(booking.id),
            "BOOKING_CANCELLED",
            "Your booking has been cancelled.",
        )

        return Response(
            BookingSerializer(
                booking,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )


class BookingStatusUpdateView(generics.GenericAPIView):
    serializer_class = BookingStatusSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.filter(
            customer=self.request.user
        )

    def post(self, request, *args, **kwargs):
        booking = self.get_object()

        serializer = self.get_serializer(
            data=request.data,
            context={"booking": booking},
        )
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data["status"]

        booking.status = new_status
        booking.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        channel_layer = get_channel_layer()

        async_to_sync(channel_layer.group_send)(
            f"booking_{booking.id}",
            {
                "type": "booking_status_update",
                "booking_id": str(booking.id),
                "status": booking.status,
                "message": (
                    f"Booking status changed to "
                    f"{booking.status}."
                ),
            },
        )

        if new_status == "in_progress":
            create_notification.delay(
                booking.customer_id,
                str(booking.id),
                "PROVIDER_STARTED",
                "The provider has started your service.",
            )

        elif new_status == "completed":
            create_notification.delay(
                booking.customer_id,
                str(booking.id),
                "BOOKING_COMPLETED",
                "Your booking has been completed.",
            )

        return Response(
            {
                "message": (
                    "Booking status updated successfully."
                ),
                "booking_id": str(booking.id),
                "status": booking.status,
            },
            status=status.HTTP_200_OK,
        )


class PaymentInitiateView(generics.CreateAPIView):
    serializer_class = PaymentInitiateSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)

        payment = serializer.save(
            transaction_id=(
                f"MOCK-{uuid4().hex[:12].upper()}"
            ),
            payment_status="PENDING",
            payment_method="MOCK",
        )

        return Response(
            {
                "message": (
                    "Payment initiated successfully."
                ),
                "payment": {
                    "id": str(payment.id),
                    "booking": str(payment.booking.id),
                    "amount": str(payment.amount),
                    "transaction_id": payment.transaction_id,
                    "payment_status": payment.payment_status,
                    "payment_method": payment.payment_method,
                    "created_at": payment.created_at,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class PaymentProcessView(generics.GenericAPIView):
    serializer_class = PaymentProcessSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payment = Payment.objects.select_related(
                "booking"
            ).get(id=pk)
        except Payment.DoesNotExist:
            return Response(
                {
                    "detail": "Payment does not exist."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if payment.booking.customer != request.user:
            return Response(
                {
                    "detail": (
                        "This payment does not belong "
                        "to the current user."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if payment.payment_status != "PENDING":
            return Response(
                {
                    "detail": (
                        "Only pending payments can be processed."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = serializer.validated_data["result"]

        payment.payment_status = result
        payment.save(
            update_fields=["payment_status"]
        )

        return Response(
            {
                "message": "Payment processed successfully.",
                "payment": {
                    "id": str(payment.id),
                    "booking": str(payment.booking.id),
                    "amount": str(payment.amount),
                    "transaction_id": payment.transaction_id,
                    "payment_status": payment.payment_status,
                    "payment_method": payment.payment_method,
                    "created_at": payment.created_at,
                },
            },
            status=status.HTTP_200_OK,
        )


class PaymentWebhookView(generics.GenericAPIView):
    serializer_class = PaymentWebhookSerializer
    permission_classes = []

    def post(self, request, *args, **kwargs):
        webhook_secret = request.headers.get(
            "X-Webhook-Secret"
        )

        if webhook_secret != settings.PAYMENT_WEBHOOK_SECRET:
            return Response(
                {
                    "detail": "Invalid webhook secret."
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = self.get_serializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        payment = serializer.validated_data["payment"]
        payment_status = serializer.validated_data[
            "payment_status"
        ]

        payment.payment_status = payment_status
        payment.save(
            update_fields=["payment_status"]
        )

        if payment_status == "SUCCESS":
            payment.booking.status = "confirmed"
            payment.booking.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            transaction.on_commit(
                lambda: create_notification.delay(
                    payment.booking.customer_id,
                    str(payment.booking.id),
                    "PAYMENT_SUCCESSFUL",
                    "Your payment was successful.",
                )
            )

            transaction.on_commit(
                lambda: create_notification.delay(
                    payment.booking.customer_id,
                    str(payment.booking.id),
                    "BOOKING_CONFIRMED",
                    "Your booking has been confirmed.",
                )
            )

        return Response(
            {
                "message": (
                    "Payment confirmation received "
                    "successfully."
                ),
                "payment_id": str(payment.id),
                "payment_status": payment.payment_status,
            },
            status=status.HTTP_200_OK,
        )
        

class ProfileImageUploadView(generics.GenericAPIView):
    serializer_class = ProfileImageSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        if "image" not in request.FILES:
            return Response(
                {
                    "success": False,
                    "message": "Profile image is required.",
                    "data": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile, created = UserProfile.objects.get_or_create(
            user=request.user
        )

        serializer = self.get_serializer(
            profile,
            data=request.data,
            partial=True,
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "success": True,
                "message": "Profile image uploaded successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
           