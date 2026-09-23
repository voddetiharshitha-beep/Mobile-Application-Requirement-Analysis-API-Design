
from datetime import datetime

from rest_framework import serializers

from .models import Booking, Payment, Service


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = [
            "id",
            "name",
            "description",
            "location",
            "price",
            "status",
            "category",
            "provider",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]


class BookingSerializer(serializers.ModelSerializer):
    customer = serializers.PrimaryKeyRelatedField(
        read_only=True,
    )

    class Meta:
        model = Booking
        fields = [
            "id",
            "customer",
            "provider",
            "service",
            "booking_date",
            "booking_time",
            "amount",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "customer",
            "amount",
            "status",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        service = attrs.get("service")
        provider = attrs.get("provider")
        booking_date = attrs.get("booking_date")
        booking_time = attrs.get("booking_time")

        if not Service.objects.filter(
            id=service.id
        ).exists():
            raise serializers.ValidationError(
                {
                    "service": "Service does not exist."
                }
            )

        if not provider.status:
            raise serializers.ValidationError(
                {
                    "provider": "Provider is not active."
                }
            )

        requested_datetime = datetime.combine(
            booking_date,
            booking_time,
        )

        if requested_datetime <= datetime.now():
            raise serializers.ValidationError(
                {
                    "booking_time": (
                        "Booking date and time must be in the future."
                    )
                }
            )

        conflicting_booking = Booking.objects.filter(
            provider=provider,
            booking_date=booking_date,
            booking_time=booking_time,
        ).exclude(
            status="cancelled"
        )

        if self.instance:
            conflicting_booking = conflicting_booking.exclude(
                id=self.instance.id
            )

        if conflicting_booking.exists():
            raise serializers.ValidationError(
                {
                    "booking_time": (
                        "Provider is already booked "
                        "for this time."
                    )
                }
            )

        return attrs

    def create(self, validated_data):
        service = validated_data["service"]

        validated_data["customer"] = self.context[
            "request"
        ].user

        validated_data["amount"] = service.price

        return Booking.objects.create(**validated_data)

    def update(self, instance, validated_data):
        if instance.status == "cancelled":
            raise serializers.ValidationError(
                {
                    "detail": "Cancelled booking cannot be modified."
                }
            )

        return super().update(instance, validated_data)


class PaymentInitiateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "booking",
            "amount",
        ]

    def validate(self, attrs):
        booking = attrs["booking"]
        amount = attrs["amount"]
        request = self.context["request"]

        # 1. Validate that the booking belongs
        #    to the authenticated user.
        if booking.customer != request.user:
            raise serializers.ValidationError(
                {
                    "booking": (
                        "This booking does not belong "
                        "to the current user."
                    )
                }
            )

        # 2. Validate that the booking is payable.
        if booking.status != "pending":
            raise serializers.ValidationError(
                {
                    "booking": (
                        "Only pending bookings can be paid."
                    )
                }
            )

        # 3. Validate that the amount matches
        #    the booking amount.
        if amount != booking.amount:
            raise serializers.ValidationError(
                {
                    "amount": (
                        "Payment amount must match "
                        "the booking amount."
                    )
                }
            )

        # 4. Prevent duplicate payment initiation.
        if Payment.objects.filter(
            booking=booking
        ).exists():
            raise serializers.ValidationError(
                {
                    "booking": (
                        "A payment already exists "
                        "for this booking."
                    )
                }
            )

        return attrs
class PaymentProcessSerializer(serializers.Serializer):
    result = serializers.ChoiceField(
        choices=["SUCCESS", "FAILED"]
    )
class PaymentWebhookSerializer(serializers.Serializer):
    payment_id = serializers.UUIDField()
    transaction_id = serializers.CharField(
        max_length=100,
    )
    payment_status = serializers.ChoiceField(
        choices=["SUCCESS", "FAILED"],
    )

    def validate(self, attrs):
        payment_id = attrs["payment_id"]
        transaction_id = attrs["transaction_id"]

        try:
            payment = Payment.objects.select_related(
                "booking"
            ).get(
                id=payment_id,
            )
        except Payment.DoesNotExist:
            raise serializers.ValidationError(
                {
                    "payment_id": (
                        "Payment does not exist."
                    )
                }
            )

        if payment.transaction_id != transaction_id:
            raise serializers.ValidationError(
                {
                    "transaction_id": (
                        "Transaction ID does not match "
                        "the payment."
                    )
                }
            )

        if payment.payment_status != "PENDING":
            raise serializers.ValidationError(
                {
                    "payment_id": (
                        "Only pending payments can "
                        "receive confirmation."
                    )
                }
            )

        attrs["payment"] = payment

        return attrs   
    
class BookingStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            "pending",
            "confirmed",
            "in_progress",
            "completed",
            "cancelled",
            "payment_failed",
        ]
    )

    def validate_status(self, value):
        booking = self.context["booking"]

        if not booking.can_transition_to(value):
            raise serializers.ValidationError(
                f"Invalid booking status transition: "
                f"{booking.status} → {value}."
            )

        return value 
