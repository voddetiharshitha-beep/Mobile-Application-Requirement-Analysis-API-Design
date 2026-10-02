from datetime import datetime, timedelta
from uuid import uuid4

from locust import HttpUser, between, task


class BackendArchitectureUser(HttpUser):
    """
    Simulates a customer using the backend APIs
    for a controlled load test.
    """

    wait_time = between(5, 10)

    def on_start(self):
        """
        Login once when each simulated user starts.
        """

        self.username = "loadtestuser"
        self.password = "LoadTest@2026!"

        response = self.client.post(
            "/api/v1/token/",
            json={
                "username": self.username,
                "password": self.password,
            },
            name="Login",
        )

        if response.status_code != 200:
            response.failure(
                f"Login failed: HTTP {response.status_code}"
            )
            return

        data = response.json()

        access_token = data.get("access")

        if not access_token:
            response.failure(
                "Login succeeded but access token was missing."
            )
            return

        self.client.headers.update(
            {
                "Authorization": f"Bearer {access_token}",
            }
        )

    @task(5)
    def service_search(self):
        """
        Test Service Search API.
        """

        self.client.get(
            "/api/v1/services/?search=cleaning",
            name="Service Search",
        )

    @task(3)
    def booking_history(self):
        """
        Test Booking History API.
        """

        self.client.get(
            "/api/v1/bookings/",
            name="Booking History",
        )

    @task(2)
    def notifications(self):
        """
        Test Notifications API.
        """

        self.client.get(
            "/api/v1/services/notifications/",
            name="Notifications",
        )

    @task(1)
    def create_booking(self):
        """
        Test Booking Creation API.

        A unique future booking time is generated
        to reduce booking conflicts.
        """

        service_id = (
            "dc6eae95-cfee-4cb0-ba6d-ac70a47e1ebe"
        )

        booking_datetime = (
            datetime.now()
            + timedelta(
                days=3,
                minutes=uuid4().int % 10000,
            )
        )

        booking_date = booking_datetime.strftime(
            "%Y-%m-%d"
        )

        booking_time = booking_datetime.strftime(
            "%H:%M:%S"
        )

        self.client.post(
            "/api/v1/bookings/",
            json={
                "service": service_id,
                "booking_date": booking_date,
                "booking_time": booking_time,
            },
            headers={
                "Idempotency-Key": str(uuid4()),
            },
            name="Create Booking",
        )