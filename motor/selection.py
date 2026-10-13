"""Picking a task from the task bank."""

import random


def pick_task(tasks, already_given_ids=(), group_counts=None, seed=None):
    """Pick one task.

    tasks: items with an `id` attribute
    already_given_ids: what this student has had before -> avoid these
    group_counts: {task_id: how many students in the group got it}

    Among the candidates the least used ones win, and one of those is drawn at
    random. This keeps the distribution even inside a group. If the student has
    already had every task, we fall back to the whole set rather than failing.
    """
    if not tasks:
        raise ValueError("Üres a feladatkészlet")

    counts = group_counts or {}
    candidates = [task for task in tasks if task.id not in already_given_ids] or list(tasks)

    fewest = min(counts.get(task.id, 0) for task in candidates)
    least_used = [task for task in candidates if counts.get(task.id, 0) == fewest]

    rng = random.Random(seed)
    return rng.choice(least_used)
