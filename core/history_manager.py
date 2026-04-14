class HistoryManager:
    def __init__(self, max_steps: int = 120):
        self.max_steps = max(10, int(max_steps))
        self._states: list[str] = []
        self._index: int = -1

    def clear(self):
        self._states.clear()
        self._index = -1

    def reset(self, state: str):
        self._states = [state]
        self._index = 0

    def current(self):
        if 0 <= self._index < len(self._states):
            return self._states[self._index]
        return None

    def can_undo(self) -> bool:
        return self._index > 0

    def can_redo(self) -> bool:
        return 0 <= self._index < (len(self._states) - 1)

    def push(self, state: str) -> bool:
        if not isinstance(state, str):
            return False

        cur = self.current()
        if cur == state:
            return False

        # 如果当前不在历史末尾，先截断“未来分支”
        if self._index < len(self._states) - 1:
            self._states = self._states[: self._index + 1]

        self._states.append(state)
        self._index = len(self._states) - 1

        # 控制长度
        if len(self._states) > self.max_steps:
            overflow = len(self._states) - self.max_steps
            self._states = self._states[overflow:]
            self._index = max(0, self._index - overflow)

        return True

    def undo(self):
        if not self.can_undo():
            return None
        self._index -= 1
        return self._states[self._index]

    def redo(self):
        if not self.can_redo():
            return None
        self._index += 1
        return self._states[self._index]