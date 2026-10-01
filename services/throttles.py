from rest_framework.throttling import ScopedRateThrottle


class LoginThrottle(ScopedRateThrottle):
    scope = "login"


class RegistrationThrottle(ScopedRateThrottle):
    scope = "registration"


class PasswordThrottle(ScopedRateThrottle):
    scope = "password"


class BookingThrottle(ScopedRateThrottle):
    scope = "booking"


class PaymentThrottle(ScopedRateThrottle):
    scope = "payment"