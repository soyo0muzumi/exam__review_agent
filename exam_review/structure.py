"""Topological sort for learning order.

Uses Kahn's algorithm with chapter order as tiebreaker.
"""

from __future__ import annotations

from .models import Topic


def topological_sort(topics: list[Topic]) -> list[str]:
    """Topological sort respecting depends_on edges.

    Falls back to chapter order for disconnected topics.
    Returns ordered list of topic IDs.
    """
    # Build graph
    id_to_topic = {t.id: t for t in topics}
    graph: dict[str, list[str]] = {t.id: [] for t in topics}
    in_degree: dict[str, int] = {t.id: 0 for t in topics}

    for t in topics:
        for dep in t.depends_on:
            if dep in graph and t.id in graph:
                graph[dep].append(t.id)
                in_degree[t.id] += 1

    # Tiebreaker: chapter order
    topic_order = {t.id: i for i, t in enumerate(topics)}

    # Start with nodes that have no dependencies
    queue = sorted(
        [tid for tid, deg in in_degree.items() if deg == 0],
        key=lambda tid: topic_order.get(tid, 0),
    )

    result = []
    while queue:
        node = queue.pop(0)
        result.append(node)

        for neighbor in graph.get(node, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
                queue.sort(key=lambda tid: topic_order.get(tid, 0))

    # Append any remaining (cycle or disconnected)
    remaining = [t.id for t in topics if t.id not in result]
    result.extend(remaining)

    return result