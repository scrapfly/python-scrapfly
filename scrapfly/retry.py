import random
import time
from functools import partial
from typing import Tuple, Union, Iterable
from loguru import logger
from decorator import decorator


class RetryBudgetExceeded(Exception):

    def __init__(self, tries:int, delay:int, retried_error:Exception):
        super().__init__('Retry Budget Exceeded')

        self.tries = tries
        self.delay = delay
        self.retried_error = retried_error

    def __str__(self):
        return 'Error %s has been retried %s times. %s' % (type(self.retried_error), self.tries, str(self.delay), str(self.retried_error))


def __retry_internal(f, exceptions=Tuple[Exception, ...], tries=0, delay=0, max_delay=None, backoff=1, jitter=0):
    _tries, _delay = tries, delay
    _tries_from_exception_set = None

    while _tries:
        try:
            return f()
        except exceptions as e:
            if e.is_retryable is True:
                if _tries_from_exception_set is None:
                    _tries_from_exception_set = True
            else:
                raise

            _tries -= 1

            if not _tries:
                raise RetryBudgetExceeded(tries=tries, delay=delay, retried_error=e) from e

            logger.warning('[%s/%s] %s, retrying in %s seconds...' % (tries - _tries, tries, e, _delay))

            time.sleep(_delay)
            _delay *= backoff

            if isinstance(jitter, tuple):
                _delay += random.uniform(*jitter)
            else:
                _delay += jitter

            if max_delay is not None:
                _delay = min(_delay, max_delay)


def retry(exceptions:Union[Tuple[Exception, ...], Exception], tries=0, delay=0, max_delay=None, backoff=1, jitter=0):
    if not isinstance(exceptions, tuple):
        if not isinstance(exceptions, Iterable):
            exceptions = [exceptions]

        exceptions = tuple(exceptions)

    @decorator
    def retry_decorator(f, *fargs, **fkwargs):
        args = fargs if fargs else list()
        kwargs = fkwargs if fkwargs else dict()

        return __retry_internal(partial(f, *args, **kwargs), exceptions, tries, delay, max_delay, backoff, jitter)

    return retry_decorator
