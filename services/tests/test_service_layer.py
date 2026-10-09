
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from services.service_service import (
    clear_service_list_cache,
    create_service,
    delete_service,
    update_service,
)


class ServiceLayerTests(SimpleTestCase):

    @patch("services.service_service.cache.delete_pattern")
    def test_clear_service_list_cache_deletes_service_list_keys(
        self, mock_delete_pattern
    ):
        clear_service_list_cache()

        mock_delete_pattern.assert_called_once_with(
            "service_list:*"
        )

    @patch(
        "services.service_service.cache.delete_pattern",
        side_effect=AttributeError,
    )
    def test_clear_service_list_cache_handles_unsupported_delete_pattern(
        self, mock_delete_pattern
    ):
        # The function should not raise AttributeError.
        clear_service_list_cache()

        mock_delete_pattern.assert_called_once_with(
            "service_list:*"
        )

    @patch("services.service_service.clear_service_list_cache")
    def test_create_service_saves_provider_and_clears_cache(
        self, mock_clear_cache
    ):
        serializer = MagicMock()
        provider = SimpleNamespace(id=10)
        expected_service = SimpleNamespace(id=20)
        serializer.save.return_value = expected_service

        result = create_service(
            serializer=serializer,
            provider=provider,
        )

        self.assertIs(result, expected_service)
        serializer.save.assert_called_once_with(
            provider=provider
        )
        mock_clear_cache.assert_called_once_with()

    @patch("services.service_service.clear_service_list_cache")
    @patch(
        "services.service_service."
        "notify_saved_customers_service_unavailable.delay"
    )
    def test_update_service_notifies_when_service_becomes_unavailable(
        self, mock_notify, mock_clear_cache
    ):
        existing_service = SimpleNamespace(
            id="service-123",
            status=True,
        )
        updated_service = SimpleNamespace(
            id="service-123",
            status=False,
        )

        serializer = MagicMock()
        serializer.instance = existing_service
        serializer.save.return_value = updated_service

        result = update_service(serializer=serializer)

        self.assertIs(result, updated_service)
        serializer.save.assert_called_once_with()
        mock_clear_cache.assert_called_once_with()
        mock_notify.assert_called_once_with("service-123")

    @patch("services.service_service.clear_service_list_cache")
    @patch(
        "services.service_service."
        "notify_saved_customers_service_unavailable.delay"
    )
    def test_update_service_does_not_notify_when_still_available(
        self, mock_notify, mock_clear_cache
    ):
        existing_service = SimpleNamespace(
            id="service-456",
            status=True,
        )
        updated_service = SimpleNamespace(
            id="service-456",
            status=True,
        )

        serializer = MagicMock()
        serializer.instance = existing_service
        serializer.save.return_value = updated_service

        result = update_service(serializer=serializer)

        self.assertIs(result, updated_service)
        mock_clear_cache.assert_called_once_with()
        mock_notify.assert_not_called()

    @patch("services.service_service.clear_service_list_cache")
    @patch(
        "services.service_service."
        "notify_saved_customers_service_unavailable.delay"
    )
    def test_update_service_does_not_notify_when_already_unavailable(
        self, mock_notify, mock_clear_cache
    ):
        existing_service = SimpleNamespace(
            id="service-789",
            status=False,
        )
        updated_service = SimpleNamespace(
            id="service-789",
            status=False,
        )

        serializer = MagicMock()
        serializer.instance = existing_service
        serializer.save.return_value = updated_service

        update_service(serializer=serializer)

        mock_clear_cache.assert_called_once_with()
        mock_notify.assert_not_called()

    @patch("services.service_service.clear_service_list_cache")
    def test_delete_service_deletes_service_and_clears_cache(
        self, mock_clear_cache
    ):
        service = MagicMock()

        delete_service(service=service)

        service.delete.assert_called_once_with()
        mock_clear_cache.assert_called_once_with()