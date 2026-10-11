
from uuid import uuid4

from django.core.cache import caches
from django.test import SimpleTestCase


class RedisDistributedLockTests(SimpleTestCase):
    """
    Verify distributed-lock behavior against Redis.
    """

    def test_lock_excludes_second_client_until_release(self):
        cache = caches["default"]
        lock_name = f"test:redis-lock:{uuid4()}"

        first_lock = cache.lock(
            lock_name,
            timeout=30,
            blocking_timeout=0,
        )
        second_lock = cache.lock(
            lock_name,
            timeout=30,
            blocking_timeout=0,
        )

        first_acquired = False
        second_acquired_after_release = False

        try:
            first_acquired = first_lock.acquire(
                blocking=False
            )
            self.assertTrue(
                first_acquired,
                "The first client should acquire the lock.",
            )

            second_acquired = second_lock.acquire(
                blocking=False
            )
            self.assertFalse(
                second_acquired,
                "The second client must not acquire "
                "a lock that is already held.",
            )

            first_lock.release()
            first_acquired = False

            second_acquired_after_release = (
                second_lock.acquire(blocking=False)
            )
            self.assertTrue(
                second_acquired_after_release,
                "The second client should acquire the "
                "lock after the first client releases it.",
            )

        finally:
            if first_acquired:
                first_lock.release()

            if second_acquired_after_release:
                second_lock.release()
