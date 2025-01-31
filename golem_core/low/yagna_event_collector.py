from abc import ABC, abstractmethod
import asyncio
#   TODO: replace Any here
from typing import Any, Callable, Dict, List, Optional

from yapapi.rest.common import is_intermittent_error
from yapapi.rest.activity import _is_gsb_endpoint_not_found_error

def _is_gsb_endpoint_not_found_error_wrapper(e: Exception) -> bool:
    #   Q: why this?
    #   A: original `yapapi` function accepts only ya_activity.ApiException, we
    #      use this for all exceptions.
    #
    #   This is (ofc) an ugly fix, check TODO in _collect_yagna_events.
    try:
        return _is_gsb_endpoint_not_found_error(e)  # type: ignore
    except Exception:
        return False

class YagnaEventCollector(ABC):
    _event_collecting_task: Optional[asyncio.Task] = None

    def start_collecting_events(self) -> None:
        if self._event_collecting_task is None:
            task = asyncio.get_event_loop().create_task(self._collect_yagna_events())
            self._event_collecting_task = task

    def stop_collecting_events(self) -> None:
        if self._event_collecting_task is not None:
            self._event_collecting_task.cancel()
            self._event_collecting_task = None

    async def _collect_yagna_events(self) -> None:
        #   TODO: All of the logic related to "what if collecting fails" is now copied from
        #         yapapi pooling batch logic. Also, is quite ugly.
        #         https://github.com/golemfactory/golem-core-python/issues/50
        gsb_endpoint_not_found_cnt = 0
        MAX_GSB_ENDPOINT_NOT_FOUND_ERRORS = 3

        while True:
            args = self._collect_events_args()
            kwargs = self._collect_events_kwargs()
            try:
                events = await self._collect_events_func(*args, **kwargs)
            except Exception as e:
                if is_intermittent_error(e):
                    continue
                elif _is_gsb_endpoint_not_found_error_wrapper(e):
                    gsb_endpoint_not_found_cnt += 1
                    if gsb_endpoint_not_found_cnt <= MAX_GSB_ENDPOINT_NOT_FOUND_ERRORS:
                        await asyncio.sleep(3)
                        continue

                raise

            gsb_endpoint_not_found_cnt = 0
            if events:
                for event in events:
                    await self._process_event(event)

    @property
    @abstractmethod
    def _collect_events_func(self) -> Callable:
        raise NotImplementedError

    @abstractmethod
    async def _process_event(self, event: Any) -> None:
        raise NotImplementedError

    def _collect_events_args(self) -> List:
        return []

    def _collect_events_kwargs(self) -> Dict:
        return {}
