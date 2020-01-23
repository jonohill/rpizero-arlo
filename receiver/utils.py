import asyncio
import logging

log = logging.getLogger(__name__)

async def as_completed_and_iterated(*awaitables_and_iterables):
    '''Generator. Given a set of awaitables:
        - Run all concurrently.
        - For iterators - yield the values as they iterate
        - for other awaitables - yield the values as they complete
    Can be sent new awaitables/iterators after each returned result.
    Yielded value is a tuple of (input_awaitable, result), or None after a new awaitable/iterable has been sent.
    Note: may yield a result of (None, None) at any time as a result of checking for new awaitables. Always check there is a task.
    '''

    tasks = {}
    pending = set()

    def is_iterable(candidate):
        return hasattr(candidate, '__anext__')

    def next_iterable_task(it):
        return asyncio.create_task(type(it).__anext__(it))

    def add_task(aw_or_it):
        nonlocal pending
        if is_iterable(aw_or_it):
            t = next_iterable_task(aw_or_it)
        else:
            t = asyncio.create_task(aw_or_it)
        tasks[t] = aw_or_it
        pending |= {t}

    for aw_or_it in awaitables_and_iterables:
        add_task(aw_or_it)

    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for t in done:
            try:
                result = await t
                aw_or_it = tasks[t]
                del tasks[t]
                new_aw = yield aw_or_it, result
                if new_aw:
                    add_task(new_aw)
                if is_iterable(aw_or_it):
                    add_task(aw_or_it)
            except StopAsyncIteration:
                del tasks[t]

        receiving = True
        while receiving:
            aw_or_it = yield None, None
            if aw_or_it:
                add_task(aw_or_it)
            else:
                receiving = False

class StreamReaderSaver():
    '''Wrapper for a StreamReader with the same interface.
       Permits saving the data from the stream as it is read.'''
    
    def __init__(self, original_streamreader: asyncio.StreamReader, target_file):
        self._sr = original_streamreader
        self._f = target_file

    async def read(self, n=-1):
        data = await self._sr.read(n)
        if data:
            self._f.write(data)
        return data

    
