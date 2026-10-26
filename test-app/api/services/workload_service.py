import hashlib
import time


def cpu_work(duration_ms: int) -> float:
    started = time.perf_counter()
    deadline = started + duration_ms / 1000
    value = b"standalone-test-laboratory"
    while time.perf_counter() < deadline:
        value = hashlib.sha256(value).digest()
    return (time.perf_counter() - started) * 1000


def latency_work(delay_ms: int) -> float:
    started = time.perf_counter()
    time.sleep(delay_ms / 1000)
    return (time.perf_counter() - started) * 1000


def memory_work(megabytes: int, duration_ms: int) -> tuple[int, float]:
    started = time.perf_counter()
    allocation = bytearray(megabytes * 1024 * 1024)
    if allocation:
        allocation[0] = 1
        allocation[-1] = 1
    time.sleep(duration_ms / 1000)
    allocated_bytes = len(allocation)
    del allocation
    return allocated_bytes, (time.perf_counter() - started) * 1000
