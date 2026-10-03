"""Minimal in process metrics exposed in Prometheus text format.

Intentionally dependency free. In a multi worker deployment each worker keeps
its own counters, so scrape every worker or move to a shared registry.
"""

import threading
from collections import defaultdict

_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._hist: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0] * (len(_BUCKETS) + 2))

    def inc(self, name: str, **labels: str) -> None:
        with self._lock:
            self._counters[(name, tuple(sorted(labels.items())))] += 1

    def observe(self, route: str, seconds: float) -> None:
        with self._lock:
            row = self._hist[("http_request_duration_seconds", route)]
            for i, bound in enumerate(_BUCKETS):
                if seconds <= bound:
                    row[i] += 1
            row[len(_BUCKETS)] += 1  # +Inf bucket (count)
            row[len(_BUCKETS) + 1] += seconds  # sum

    def render(self) -> str:
        lines: list[str] = []
        with self._lock:
            for (name, labels), value in sorted(self._counters.items()):
                label_text = ",".join(f'{k}="{v}"' for k, v in labels)
                lines.append(f"{name}{{{label_text}}} {value:g}")
            for (name, route), row in sorted(self._hist.items()):
                for i, bound in enumerate(_BUCKETS):
                    lines.append(f'{name}_bucket{{route="{route}",le="{bound}"}} {row[i]:g}')
                lines.append(f'{name}_bucket{{route="{route}",le="+Inf"}} {row[len(_BUCKETS)]:g}')
                lines.append(f'{name}_count{{route="{route}"}} {row[len(_BUCKETS)]:g}')
                lines.append(f'{name}_sum{{route="{route}"}} {row[len(_BUCKETS) + 1]:.6f}')
        return "\n".join(lines) + "\n"


metrics = Metrics()
