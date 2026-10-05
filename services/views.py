from django.contrib.auth.password_validation import validate_password
from django.conf import settings
from django.core.cache import cache

from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import (
    Booking,
    Notification,
    Payment,
    Provider,
    Service,
    ServiceImage,
    UserProfile,
    SavedService,
)

from .pagination import ServicePagination
from .permissions import IsCustomer

from .booking_service import (
    create_booking,
    cancel_booking,
    update_booking_status,
)

from .serializers import (
    BookingSerializer,
    BookingStatusSerializer,
    NotificationSerializer,
    PasswordChangeSerializer,
    PaymentInitiateSerializer,
    PaymentProcessSerializer,
    PaymentWebhookSerializer,
    ProfileImageSerializer,
    RegisterSerializer,
    ServiceImageSerializer,
    ServiceListSerializer,
    ServiceSerializer,
    SavedServiceSerializer,
)

from .payment_service import (
    initiate_payment,
    process_payment,
    process_payment_webhook,
)

from .stripe_service import StripeIntegrationError

from .service_service import (
    create_service,
    update_service,
    delete_service,
)

from .saved_service_service import (
    SavedServiceAlreadyExists,
    ServiceNotFound,
    delete_saved_service,
    list_saved_services,
    save_service,
)


def build_api_error_response(
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


class LoginView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "registration"


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password"

    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)

        request.user.set_password(
            serializer.validated_data["new_password"]
        )

        request.user.save(
            update_fields=["password"]
        )

        return Response(
            {
                "success": True,
                "message": "Password changed successfully.",
                "error_code": None,
                "data": None,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return build_api_error_response(
                message="Refresh token is required.",
                error_code="REFRESH_TOKEN_REQUIRED",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response(
                {
                    "success": True,
                    "message": "Logout successful.",
                    "error_code": None,
                    "data": None,
                },
                status=status.HTTP_200_OK,
            )

        except TokenError:
            return build_api_error_response(
                message="Invalid or already blacklisted refresh token.",
                error_code="INVALID_REFRESH_TOKEN",
                status_code=status.HTTP_400_BAD_REQUEST,
            )


class ServiceListCreateView(generics.ListCreateAPIView):
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ServicePagination

    def get_serializer_class(self):
        if self.request.method == "GET":
            return ServiceListSerializer

        return ServiceSerializer

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
            settings.SERVICE_LIST_CACHE_TIMEOUT,
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

        create_service(
            serializer=serializer,
            provider=provider,
        )


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

    def update(
        self,
        request,
        *args,
        **kwargs,
    ):
        service = self.get_object()

        if service.provider.user != request.user:
            return build_api_error_response(
                "You can only update your own services.",
                "PERMISSION_DENIED",
                status.HTTP_403_FORBIDDEN,
            )

        partial = kwargs.pop(
            "partial",
            False,
        )

        serializer = self.get_serializer(
            service,
            data=request.data,
            partial=partial,
        )

        serializer.is_valid(
            raise_exception=True
        )

        update_service(
            serializer=serializer,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def destroy(
        self,
        request,
        *args,
        **kwargs,
    ):
        service = self.get_object()

        if service.provider.user != request.user:
            return build_api_error_response(
                "You can only delete your own services.",
                "PERMISSION_DENIED",
                status.HTTP_403_FORBIDDEN,
            )

        delete_service(
            service=service,
        )

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )


class BookingListCreateView(
    generics.ListCreateAPIView
):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ServicePagination
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "booking"

    def create(
        self,
        request,
        *args,
        **kwargs,
    ):
        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        self.perform_create(serializer)

        if self.booking_created:
            response_status = status.HTTP_201_CREATED
            response_message = (
                "Booking created successfully."
            )
        else:
            response_status = status.HTTP_200_OK
            response_message = (
                "Booking request already processed."
            )

        return Response(
            {
                "success": True,
                "message": response_message,
                "data": serializer.data,
            },
            status=response_status,
        )

    def get_queryset(self):
        queryset = Booking.objects.select_related(
            "customer",
            "provider",
            "service",
        )

        try:
            provider = self.request.user.provider
        except Provider.DoesNotExist:
            provider = None

        if provider:
            return queryset.filter(
                provider=provider
            ).order_by("-created_at")

        return queryset.filter(
            customer=self.request.user
        ).order_by("-created_at")

    def perform_create(self, serializer):
        service = serializer.validated_data["service"]

        booking_date = serializer.validated_data[
            "booking_date"
        ]

        booking_time = serializer.validated_data[
            "booking_time"
        ]

        idempotency_key = self.request.headers.get(
            "Idempotency-Key"
        )

        booking, created = create_booking(
            customer=self.request.user,
            service=service,
            booking_date=booking_date,
            booking_time=booking_time,
            idempotency_key=idempotency_key,
        )

        serializer.instance = booking

        self.booking_created = created


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

    def update(
        self,
        request,
        *args,
        **kwargs,
    ):
        booking = self.get_object()

        if booking.status == "cancelled":
            return build_api_error_response(
                "Cancelled booking cannot be modified.",
                "BOOKING_ALREADY_CANCELLED",
                status.HTTP_400_BAD_REQUEST,
            )

        if booking.status == "completed":
            return build_api_error_response(
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
        return Booking.objects.select_related(
            "customer",
            "provider",
            "service",
        ).filter(
            customer=self.request.user
        )

    def post(self, request, *args, **kwargs):
        booking = self.get_object()

        try:
            booking = cancel_booking(
                booking=booking
            )

        except ValueError as exc:
            if booking.status == "cancelled":
                return build_api_error_response(
                    str(exc),
                    "BOOKING_ALREADY_CANCELLED",
                    status.HTTP_400_BAD_REQUEST,
                )

            if booking.status == "completed":
                return build_api_error_response(
                    str(exc),
                    "BOOKING_COMPLETED",
                    status.HTTP_400_BAD_REQUEST,
                )

            return build_api_error_response(
                str(exc),
                "BOOKING_CANCELLATION_FAILED",
                status.HTTP_400_BAD_REQUEST,
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

        booking = update_booking_status(
            booking=booking,
            new_status=new_status,
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
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "payment"

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

        payment = serializer.save()

        try:
            payment = initiate_payment(
                payment=payment
            )

        except StripeIntegrationError:
            return build_api_error_response(
                message=(
                    "The external payment service is "
                    "temporarily unavailable."
                ),
                error_code="PAYMENT_SERVICE_UNAVAILABLE",
                status_code=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "success": True,
                "message": "Payment initiated successfully.",
                "error_code": None,
                "data": {
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
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "payment"

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
            return build_api_error_response(
                "Payment does not exist.",
                "NOT_FOUND",
                status.HTTP_404_NOT_FOUND,
            )

        if payment.booking.customer != request.user:
            return build_api_error_response(
                "This payment does not belong to the current user.",
                "PERMISSION_DENIED",
                status.HTTP_403_FORBIDDEN,
            )

        if payment.payment_status != "PENDING":
            return build_api_error_response(
                "Only pending payments can be processed.",
                "PAYMENT_NOT_PENDING",
                status.HTTP_400_BAD_REQUEST,
            )

        result = serializer.validated_data[
            "result"
        ]

        payment = process_payment(
            payment=payment,
            payment_result=result,
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
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "payment"

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
            return build_api_error_response(
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

        payment = process_payment_webhook(
            payment=payment,
            payment_status=payment_status,
        )

        return Response(
            {
                "success": True,
                "message": (
                    "Payment webhook processed successfully."
                ),
                "data": {
                    "payment_id": str(
                        payment.id
                    ),
                    "payment_status": (
                        payment.payment_status
                    ),
                },
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
            return build_api_error_response(
                "Profile image is required.",
                "VALIDATION_ERROR",
                status.HTTP_400_BAD_REQUEST,
            )

        profile, _ = (
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
        service = (
            Service.objects.select_related(
                "provider__user"
            )
            .filter(id=service_id)
            .first()
        )

        if service is None:
            return build_api_error_response(
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
        service = (
            Service.objects.select_related(
                "provider__user"
            )
            .filter(id=service_id)
            .first()
        )

        if service is None:
            return build_api_error_response(
                "Service not found.",
                "NOT_FOUND",
                status.HTTP_404_NOT_FOUND,
            )

        if service.provider.user != request.user:
            return build_api_error_response(
                "You can only upload images for your own service.",
                "PERMISSION_DENIED",
                status.HTTP_403_FORBIDDEN,
            )

        if "image" not in request.FILES:
            return build_api_error_response(
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
        service = (
            Service.objects.select_related(
                "provider__user"
            )
            .filter(id=service_id)
            .first()
        )

        if service is None:
            return build_api_error_response(
                "Service not found.",
                "NOT_FOUND",
                status.HTTP_404_NOT_FOUND,
            )

        if service.provider.user != request.user:
            return build_api_error_response(
                "You can only delete images from your own service.",
                "PERMISSION_DENIED",
                status.HTTP_403_FORBIDDEN,
            )

        image = ServiceImage.objects.filter(
            id=image_id,
            service=service,
        ).first()

        if image is None:
            return build_api_error_response(
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
        return Notification.objects.select_related(
            "booking",
        ).filter(
            recipient=self.request.user
        ).order_by("-id")


class SavedServiceListCreateView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsCustomer,
    ]

    def get(self, request):
        saved_services = list_saved_services(
            customer=request.user,
        )

        serializer = SavedServiceSerializer(
            saved_services,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = SavedServiceSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        service = serializer.validated_data[
            "service"
        ]

        try:
            saved_service = save_service(
                customer=request.user,
                service=service,
            )

        except ServiceNotFound:
            return build_api_error_response(
                message="Service not found.",
                error_code="SERVICE_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        except SavedServiceAlreadyExists:
            return build_api_error_response(
                message="Service has already been saved.",
                error_code="ALREADY_SAVED",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        response_serializer = SavedServiceSerializer(
            saved_service,
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class SavedServiceDeleteView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def delete(
        self,
        request,
        pk,
    ):
        deleted = delete_saved_service(
            customer=request.user,
            saved_service_id=pk,
        )

        if not deleted:
            return build_api_error_response(
                message="Saved service not found.",
                error_code="NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )