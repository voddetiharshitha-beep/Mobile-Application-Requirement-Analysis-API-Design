from uuid import uuid4

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Booking,
    Notification,
    Payment,
    Provider,
    Service,
    ServiceImage,
    UserProfile,
)
from .pagination import ServicePagination
from .serializers import (
    BookingSerializer,
    BookingStatusSerializer,
    NotificationSerializer,
    PaymentInitiateSerializer,
    PaymentProcessSerializer,
    PaymentWebhookSerializer,
    ProfileImageSerializer,
    RegisterSerializer,
    ServiceImageSerializer,
    ServiceSerializer,
)
from .tasks import create_notification


def api_error(
    message,
    error_code,
    status_code,
    data=None,
):
    return Response(
        {
            "success": False,
            "message": message,
            "error_code": error_code,
            "data": data,
        },
        status=status_code,
    )


def clear_service_list_cache():
    """
    Clear all cached Service List API responses.
    """
    try:
        cache.delete_pattern("service_list:*")
    except AttributeError:
        pass


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class ServiceListCreateView(generics.ListCreateAPIView):
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ServicePagination

    def list(self, request, *args, **kwargs):
        """
        Return cached Service List API response when available.
        """
        cache_key = f"service_list:{request.get_full_path()}"

        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return Response(cached_data)

        response = super().list(
            request,
            *args,
            **kwargs,
        )

        cache.set(
            cache_key,
            response.data,
            60,
        )

        return response

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
            queryset = queryset.filter(
                name__icontains=name
            )

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
            queryset = queryset.filter(
                price=price
            )

        if min_price:
            queryset = queryset.filter(
                price__gte=min_price
            )

        if max_price:
            queryset = queryset.filter(
                price__lte=max_price
            )

        if status_filter:
            queryset = queryset.filter(
                status=status_filter.lower() == "true"
            )

        ordering = self.request.query_params.get(
            "ordering"
        )

        if ordering in [
            "price",
            "-price",
            "created_at",
            "-created_at",
        ]:
            queryset = queryset.order_by(ordering)

        return queryset

    def perform_create(self, serializer):
        try:
            provider = Provider.objects.get(
                user=self.request.user
            )
        except Provider.DoesNotExist:
            raise PermissionDenied(
                "Only registered providers can create services."
            )

        serializer.save(
            provider=provider
        )

        clear_service_list_cache()


class ServiceDetailView(
    generics.RetrieveUpdateDestroyAPIView
):
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Service.objects.select_related(
            "category",
            "provider",
        )

    def update(self, request, *args, **kwargs):
        service = self.get_object()

        if service.provider.user != request.user:
            return api_error(
                "You can only update your own services.",
                "PERMISSION_DENIED",
                status.HTTP_403_FORBIDDEN,
            )

        response = super().update(
            request,
            *args,
            **kwargs,
        )

        clear_service_list_cache()

        return response

    def destroy(self, request, *args, **kwargs):
        service = self.get_object()

        if service.provider.user != request.user:
            return api_error(
                "You can only delete your own services.",
                "PERMISSION_DENIED",
                status.HTTP_403_FORBIDDEN,
            )

        response = super().destroy(
            request,
            *args,
            **kwargs,
        )

        clear_service_list_cache()

        return response


class BookingListCreateView(
    generics.ListCreateAPIView
):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ServicePagination

    def get_queryset(self):
        queryset = Booking.objects.select_related(
            "customer",
            "provider",
            "service",
        )

        provider = Provider.objects.filter(
            user=self.request.user
        ).first()

        if provider:
            return queryset.filter(
                provider=provider
            ).order_by("-created_at")

        return queryset.filter(
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


class BookingDetailView(
    generics.RetrieveUpdateAPIView
):
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
            return api_error(
                "Cancelled booking cannot be modified.",
                "BOOKING_ALREADY_CANCELLED",
                status.HTTP_400_BAD_REQUEST,
            )

        if booking.status == "completed":
            return api_error(
                "Completed booking cannot be modified.",
                "BOOKING_COMPLETED",
                status.HTTP_400_BAD_REQUEST,
            )

        return super().update(
            request,
            *args,
            **kwargs,
        )


class BookingCancelView(
    generics.GenericAPIView
):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.filter(
            customer=self.request.user
        )

    def post(self, request, *args, **kwargs):
        booking = self.get_object()

        if booking.status == "cancelled":
            return api_error(
                "Booking is already cancelled.",
                "BOOKING_ALREADY_CANCELLED",
                status.HTTP_400_BAD_REQUEST,
            )

        if booking.status == "completed":
            return api_error(
                "Completed booking cannot be cancelled.",
                "BOOKING_COMPLETED",
                status.HTTP_400_BAD_REQUEST,
            )

        booking.status = "cancelled"

        booking.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        channel_layer = get_channel_layer()

        async_to_sync(
            channel_layer.group_send
        )(
            f"booking_{booking.id}",
            {
                "type": "booking_status_update",
                "booking_id": str(booking.id),
                "status": booking.status,
                "message": (
                    "Booking status changed to cancelled."
                ),
            },
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


class BookingStatusUpdateView(
    generics.GenericAPIView
):
    serializer_class = BookingStatusSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.filter(
            provider__user=self.request.user
        )

    def post(self, request, *args, **kwargs):
        booking = self.get_object()

        serializer = self.get_serializer(
            data=request.data,
            context={
                "booking": booking,
            },
        )

        serializer.is_valid(
            raise_exception=True
        )

        new_status = serializer.validated_data[
            "status"
        ]

        booking.status = new_status

        booking.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        channel_layer = get_channel_layer()

        async_to_sync(
            channel_layer.group_send
        )(
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


class PaymentInitiateView(
    generics.CreateAPIView
):
    serializer_class = PaymentInitiateSerializer
    permission_classes = [IsAuthenticated]

    def create(
        self,
        request,
        *args,
        **kwargs,
    ):
        serializer = self.get_serializer(
            data=request.data,
            context={
                "request": request,
            },
        )

        serializer.is_valid(
            raise_exception=True
        )

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
                    "booking": str(
                        payment.booking.id
                    ),
                    "amount": str(
                        payment.amount
                    ),
                    "transaction_id": (
                        payment.transaction_id
                    ),
                    "payment_status": (
                        payment.payment_status
                    ),
                    "payment_method": (
                        payment.payment_method
                    ),
                    "created_at": (
                        payment.created_at
                    ),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class PaymentProcessView(
    generics.GenericAPIView
):
    serializer_class = PaymentProcessSerializer
    permission_classes = [IsAuthenticated]

    def post(
        self,
        request,
        pk,
        *args,
        **kwargs,
    ):
        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        try:
            payment = Payment.objects.select_related(
                "booking"
            ).get(
                id=pk
            )
        except Payment.DoesNotExist:
            return api_error(
                "Payment does not exist.",
                "NOT_FOUND",
                status.HTTP_404_NOT_FOUND,
            )

        if payment.booking.customer != request.user:
            return api_error(
                "This payment does not belong to the current user.",
                "PERMISSION_DENIED",
                status.HTTP_403_FORBIDDEN,
            )

        if payment.payment_status != "PENDING":
            return api_error(
                "Only pending payments can be processed.",
                "PAYMENT_NOT_PENDING",
                status.HTTP_400_BAD_REQUEST,
            )

        result = serializer.validated_data[
            "result"
        ]

        payment.payment_status = result

        payment.save(
            update_fields=[
                "payment_status",
            ]
        )

        return Response(
            {
                "message": (
                    "Payment processed successfully."
                ),
                "payment": {
                    "id": str(payment.id),
                    "booking": str(
                        payment.booking.id
                    ),
                    "amount": str(
                        payment.amount
                    ),
                    "transaction_id": (
                        payment.transaction_id
                    ),
                    "payment_status": (
                        payment.payment_status
                    ),
                    "payment_method": (
                        payment.payment_method
                    ),
                    "created_at": (
                        payment.created_at
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )


class PaymentWebhookView(
    generics.GenericAPIView
):
    serializer_class = PaymentWebhookSerializer
    permission_classes = []

    def post(
        self,
        request,
        *args,
        **kwargs,
    ):
        webhook_secret = request.headers.get(
            "X-Webhook-Secret"
        )

        if (
            webhook_secret
            != settings.PAYMENT_WEBHOOK_SECRET
        ):
            return api_error(
                "Invalid webhook secret.",
                "INVALID_WEBHOOK_SECRET",
                status.HTTP_401_UNAUTHORIZED,
            )

        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        payment = serializer.validated_data[
            "payment"
        ]

        payment_status = serializer.validated_data[
            "payment_status"
        ]

        payment.payment_status = payment_status

        payment.save(
            update_fields=[
                "payment_status",
            ]
        )

        if payment_status == "SUCCESS":
            payment.booking.status = "confirmed"

            payment.booking.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            channel_layer = get_channel_layer()

            async_to_sync(
                channel_layer.group_send
            )(
                f"booking_{payment.booking.id}",
                {
                    "type": "booking_status_update",
                    "booking_id": str(
                        payment.booking.id
                    ),
                    "status": "confirmed",
                    "message": (
                        "Booking status changed to confirmed."
                    ),
                },
            )

            transaction.on_commit(
                lambda: create_notification.delay(
                    payment.booking.customer_id,
                    str(
                        payment.booking.id
                    ),
                    "PAYMENT_SUCCESSFUL",
                    "Your payment was successful.",
                )
            )

            transaction.on_commit(
                lambda: create_notification.delay(
                    payment.booking.customer_id,
                    str(
                        payment.booking.id
                    ),
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
                "payment_id": str(
                    payment.id
                ),
                "payment_status": (
                    payment.payment_status
                ),
            },
            status=status.HTTP_200_OK,
        )


class ProfileImageUploadView(
    generics.GenericAPIView
):
    serializer_class = ProfileImageSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [
        MultiPartParser,
        FormParser,
    ]

    def post(
        self,
        request,
        *args,
        **kwargs,
    ):
        if "image" not in request.FILES:
            return api_error(
                "Profile image is required.",
                "VALIDATION_ERROR",
                status.HTTP_400_BAD_REQUEST,
            )

        profile, created = (
            UserProfile.objects.get_or_create(
                user=request.user
            )
        )

        serializer = self.get_serializer(
            profile,
            data=request.data,
            partial=True,
        )

        serializer.is_valid(
            raise_exception=True
        )

        serializer.save()

        return Response(
            {
                "success": True,
                "message": (
                    "Profile image uploaded successfully."
                ),
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class ServiceImageListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [
        MultiPartParser,
        FormParser,
    ]

    def get(
        self,
        request,
        service_id,
    ):
        service = Service.objects.filter(
            id=service_id
        ).first()

        if service is None:
            return api_error(
                "Service not found.",
                "NOT_FOUND",
                status.HTTP_404_NOT_FOUND,
            )

        images = ServiceImage.objects.filter(
            service=service
        ).order_by("-uploaded_at")

        paginator = ServicePagination()

        page = paginator.paginate_queryset(
            images,
            request,
            view=self,
        )

        serializer = ServiceImageSerializer(
            page,
            many=True,
            context={
                "request": request,
            },
        )

        return paginator.get_paginated_response(
            serializer.data
        )

    def post(
        self,
        request,
        service_id,
    ):
        service = Service.objects.filter(
            id=service_id
        ).first()

        if service is None:
            return api_error(
                "Service not found.",
                "NOT_FOUND",
                status.HTTP_404_NOT_FOUND,
            )

        if (
            service.provider.user
            != request.user
        ):
            return api_error(
                "You can only upload images for your own service.",
                "PERMISSION_DENIED",
                status.HTTP_403_FORBIDDEN,
            )

        if "image" not in request.FILES:
            return api_error(
                "Image file is required.",
                "VALIDATION_ERROR",
                status.HTTP_400_BAD_REQUEST,
            )

        serializer = ServiceImageSerializer(
            data=request.data,
            context={
                "request": request,
            },
        )

        serializer.is_valid(
            raise_exception=True
        )

        serializer.save(
            service=service
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )


class ServiceImageDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(
        self,
        request,
        service_id,
        image_id,
    ):
        service = Service.objects.filter(
            id=service_id
        ).first()

        if service is None:
            return api_error(
                "Service not found.",
                "NOT_FOUND",
                status.HTTP_404_NOT_FOUND,
            )

        if (
            service.provider.user
            != request.user
        ):
            return api_error(
                "You can only delete images from your own service.",
                "PERMISSION_DENIED",
                status.HTTP_403_FORBIDDEN,
            )

        image = ServiceImage.objects.filter(
            id=image_id,
            service=service,
        ).first()

        if image is None:
            return api_error(
                "Image not found.",
                "NOT_FOUND",
                status.HTTP_404_NOT_FOUND,
            )

        image.delete()

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )


class NotificationListView(
    generics.ListAPIView
):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(
            recipient=self.request.user
        ).order_by("-id")