"""Tests for async task manager."""

from omnirag.api.tasks import TaskManager, TaskStatus


def test_create_task():
    tm = TaskManager()
    task = tm.create("my_pipeline", "what is RAG?")
    assert task.status == TaskStatus.PENDING
    assert task.pipeline_name == "my_pipeline"
    assert task.query == "what is RAG?"


def test_update_task():
    tm = TaskManager()
    task = tm.create("p1", "query")
    tm.update(task.task_id, TaskStatus.RUNNING)
    assert tm.get(task.task_id).status == TaskStatus.RUNNING

    tm.update(
        task.task_id,
        TaskStatus.COMPLETED,
        result={"answer": "done"},
    )
    updated = tm.get(task.task_id)
    assert updated.status == TaskStatus.COMPLETED
    assert updated.result == {"answer": "done"}
    assert updated.completed_at is not None


def test_update_failed():
    tm = TaskManager()
    task = tm.create("p1", "query")
    tm.update(task.task_id, TaskStatus.FAILED, error="boom")
    assert tm.get(task.task_id).error == "boom"


def test_list_tasks():
    tm = TaskManager()
    tm.create("a", "q1")
    tm.create("b", "q2")
    tm.create("c", "q3")
    tasks = tm.list_tasks(limit=2)
    assert len(tasks) == 2


def test_get_nonexistent():
    tm = TaskManager()
    assert tm.get("fake-id") is None
