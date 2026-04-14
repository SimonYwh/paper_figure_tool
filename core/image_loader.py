from __future__ import annotations

from functools import partial

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from core.image_utils import load_image_thumb_qimage


class _TaskSignals(QObject):
    loaded = Signal(int, str, object, int, int)  # batch_id, path, QImage, orig_w, orig_h
    failed = Signal(int, str, str)  # batch_id, path, error
    finished = Signal(int)  # batch_id


class _ImageLoadTask(QRunnable):
    def __init__(self, path: str, batch_id: int, max_thumb: int = 2200):
        super().__init__()
        self.path = path
        self.batch_id = int(batch_id)
        self.max_thumb = max_thumb
        self.signals = _TaskSignals()

    def run(self):
        try:
            qimg, orig_w, orig_h = load_image_thumb_qimage(self.path, max_thumb=self.max_thumb)
            self.signals.loaded.emit(self.batch_id, self.path, qimg, int(orig_w), int(orig_h))
        except Exception as e:
            self.signals.failed.emit(self.batch_id, self.path, str(e))
        finally:
            self.signals.finished.emit(self.batch_id)


class ImageLoader(QObject):
    image_loaded = Signal(int, str, object, int, int)
    image_failed = Signal(int, str, str)
    progress = Signal(int, int, int)  # batch_id, done, total（当前批次）
    finished = Signal(int)  # batch_id（单个批次完成）

    def __init__(self, max_thumb: int = 2200, parent=None):
        super().__init__(parent)
        self.max_thumb = max_thumb
        self.pool = QThreadPool.globalInstance()
        self._next_batch_id = 1
        self._batch_state: dict[int, dict[str, int]] = {}
        self._running_tasks: dict[int, list[_ImageLoadTask]] = {}

    def load_files(self, paths: list[str]) -> int | None:
        if not paths:
            return None

        batch_id = self._next_batch_id
        self._next_batch_id += 1

        total = len(paths)
        self._batch_state[batch_id] = {"done": 0, "total": total}
        self._running_tasks[batch_id] = []

        for p in paths:
            task = _ImageLoadTask(p, batch_id=batch_id, max_thumb=self.max_thumb)
            task.signals.loaded.connect(self.image_loaded.emit)
            task.signals.failed.connect(self.image_failed.emit)
            task.signals.finished.connect(partial(self._on_one_finished, task))
            self._running_tasks[batch_id].append(task)
            self.pool.start(task)

        return batch_id

    def _on_one_finished(self, task: _ImageLoadTask, batch_id: int):
        state = self._batch_state.get(int(batch_id))
        if state is None:
            return

        batch_id = int(batch_id)

        tasks = self._running_tasks.get(batch_id)
        if isinstance(tasks, list):
            try:
                tasks.remove(task)
            except ValueError:
                pass

        done = int(state.get("done", 0)) + 1
        total = int(state.get("total", 0))
        state["done"] = done

        self.progress.emit(batch_id, done, total)

        if done >= total:
            self._batch_state.pop(batch_id, None)
            self._running_tasks.pop(batch_id, None)
            self.finished.emit(batch_id)