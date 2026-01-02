"""Reusable thread-pool helpers for background tasks.

This module exposes a singleton ThreadPoolExecutor and convenience helpers to submit
background work from different parts of the app without repeating executor setup logic.

Configuration:
- SAMPLING_WORKER_THREADS environment variable controls the default max_workers when the
  executor is first created (defaults to 8).

API:
- get_executor(max_workers=None) -> ThreadPoolExecutor
- submit_task(fn, *args, **kwargs) -> concurrent.futures.Future
- shutdown_executor(wait=False)
"""
from concurrent.futures import ThreadPoolExecutor
import os
from atexit import register as _atexit_register
import threading
import logging

_executor = None
_executor_lock = threading.Lock()


def _create_executor(max_workers=None):
    if max_workers is None:
        try:
            max_workers = int(os.environ.get('SAMPLING_WORKER_THREADS', '8'))
        except Exception:
            max_workers = 8
    return ThreadPoolExecutor(max_workers=max_workers)


def get_executor(max_workers=None):
    """Return a singleton ThreadPoolExecutor (create lazily)."""
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:
                _executor = _create_executor(max_workers=max_workers)
                # register shutdown on interpreter exit
                try:
                    _atexit_register(lambda: shutdown_executor(wait=False))
                except Exception:
                    logging.exception('Failed to register executor shutdown')
    return _executor


def submit_task(fn, *args, **kwargs):
    """Submit a callable to the shared executor and return a Future.

    The callable will run in background. Exceptions are available on the returned Future;
    callers can ignore the Future for fire-and-forget semantics.
    """
    try:
        execu = get_executor()
        return execu.submit(fn, *args, **kwargs)
    except Exception:
        logging.exception('Failed to submit background task')
        raise


def shutdown_executor(wait=False):
    """Shutdown the shared executor if created."""
    global _executor
    try:
        exec_local = _executor
        if exec_local is not None:
            exec_local.shutdown(wait=wait)
    except Exception:
        logging.exception('Error while shutting down executor')
    finally:
        _executor = None

