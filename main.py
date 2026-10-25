if __name__ == "__main__":
    # First of all: errors from here on (even a missing PySide6) go to error.log and a message box
    import error_log
    error_log.install("Lorebook Organizer")

import copy
import json
import os
import sys
import tempfile
from pathlib import Path

import shiboken6
from PySide6.QtCore import Qt, Signal, QItemSelectionModel, QEvent, QTimer
from PySide6.QtGui import QDrag, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


VERSION = "1.0.7"
HISTORY_LIMIT = 100

THEME = """
QWidget { background: #1e1e1e; color: #ddd; }
QLineEdit, QListWidget {
    background: #2b2b2b; color: white; border: 1px solid #444;
}
QPushButton {
    background: #444; padding: 6px; border: 1px solid #666;
}
QPushButton:hover { background: #555; }
QListWidget { padding: 4px; }
QListWidget::item {
    border: 1px solid #555;
    margin: 3px;
    padding: 8px;
    border-radius: 4px;
    background: #323232;
}
QListWidget::item:selected {
    background: #6a5acd;
    color: white;
    border: 1px solid #8f7cff;
}
"""


def _reject_constant(name):
    # Python читает NaN/Infinity, но это не JSON: SillyTavern такой файл не откроет.
    raise ValueError(f"{name} is not a valid JSON value")


def load_json(path):
    # utf-8-sig: читает и обычные файлы, и файлы с BOM (Блокнот Windows и др.)
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f, parse_constant=_reject_constant)


def _default_file_mode():
    umask = os.umask(0)
    os.umask(umask)
    return 0o666 & ~umask


def save_json(path, data):
    path = os.fspath(path)
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        # mkstemp создаёт файл с правами 0600 — сохраняем права исходного файла
        try:
            mode = os.stat(path).st_mode & 0o777
        except OSError:
            mode = _default_file_mode()
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def find_entries_container(obj):
    if isinstance(obj, list):
        return obj, "root-list"
    if not isinstance(obj, dict):
        return {}, "none"

    nested = None
    data = obj.get("data")
    if isinstance(data, dict):
        book = data.get("character_book")
        if isinstance(book, dict):
            nested = book.get("entries")

    book = obj.get("character_book")
    book_entries = book.get("entries") if isinstance(book, dict) else None

    for where, value in (
        ("entries", obj.get("entries")),
        ("data.character_book.entries", nested),
        ("character_book.entries", book_entries),
    ):
        if isinstance(value, dict) and value:
            return value, where
        if isinstance(value, list) and value:
            return value, where

    if isinstance(obj.get("entries"), (dict, list)):
        return obj.get("entries"), "entries"
    return {}, "entries"


NESTED_WHERE = ("data.character_book.entries", "character_book.entries")


def get_book(obj, where):
    """Объект character_book для карточек персонажей, иначе None."""
    if isinstance(obj, dict):
        if where == "data.character_book.entries":
            return obj["data"]["character_book"]
        if where == "character_book.entries":
            return obj["character_book"]
    return None


def read_lorebook_name(obj, where):
    # В карточке персонажа корневое `name` — имя персонажа, а не лорбука.
    book = get_book(obj, where)
    source = book if book is not None else obj
    if isinstance(source, dict):
        return str(source.get("name") or "")
    return ""


def renumbered(entries):
    """Копии записей с uid/id по порядку; displayIndex / extensions.display_index (порядок в SillyTavern) — если они есть."""
    out = []
    for i, entry in enumerate(entries, start=1):
        e = copy.deepcopy(entry)
        e["uid"] = i
        e["id"] = i
        if "displayIndex" in e:
            e["displayIndex"] = i - 1
        # В карточках персонажей (embedded character_book) SillyTavern берёт порядок
        # из extensions.display_index.
        if isinstance(e.get("extensions"), dict) and "display_index" in e["extensions"]:
            e["extensions"]["display_index"] = i - 1
        out.append(e)
    return out


def build_payload(data, where, entries, name):
    """Собрать данные для сохранения, не меняя исходный объект. Возвращает (payload, where)."""
    items = renumbered(entries)
    if not isinstance(data, dict):
        return {"name": name, "entries": {str(i): e for i, e in enumerate(items, start=1)}}, "entries"
    payload = copy.deepcopy(data)
    if where in NESTED_WHERE:
        book = get_book(payload, where)
        book["entries"] = items
        book["name"] = name
        return payload, where
    payload["name"] = name
    payload["entries"] = {str(i): e for i, e in enumerate(items, start=1)}
    return payload, "entries"


def entries_to_list(raw):
    result = []
    if isinstance(raw, list):
        for e in raw:
            if isinstance(e, dict):
                result.append(copy.deepcopy(e))
        return result
    if not isinstance(raw, dict):
        return []
    items = []
    for key, entry in raw.items():
        if isinstance(entry, dict):
            items.append((str(key), copy.deepcopy(entry)))

    def sort_key(item):
        k, e = item
        if k.isascii() and k.isdecimal():  # isdigit() пропускает "²", на котором int() падает
            return (0, int(k))
        uid = e.get("uid", e.get("id"))
        try:
            return (1, int(uid))
        except (TypeError, ValueError):
            return (2, k)

    items.sort(key=sort_key)
    return [entry for _, entry in items]


def entry_title(entry, fallback):
    if not isinstance(entry, dict):
        return fallback
    return str(entry.get("name") or entry.get("comment") or fallback)


def keyword_count(entry):
    for name in ("key", "keys"):
        value = entry.get(name)
        if isinstance(value, list):
            count = len([x for x in value if str(x).strip()])
        elif isinstance(value, str):
            count = len([x for x in value.split(",") if x.strip()])
        else:
            count = 0
        if count:
            return count
    return 0


def char_count(text):
    """Символы, как их показывает поле текста: перевод строки (\\r\\n или \\r) — один символ,
    как в Lorebook Studio."""
    text = text if isinstance(text, str) else str(text or "")
    return len(text.replace("\r\n", "\n").replace("\r", "\n"))


def entry_row_text(position, entry, fallback):
    chars = char_count(entry.get("content"))
    return (
        f"{position}. {entry_title(entry, fallback)}\n"
        f"{chars} chars | {chars // 4} tokens | {keyword_count(entry)} keywords"
    )


def entry_haystack(entry):
    """Текст для фильтра: имя, ключевые слова (основные и вторичные) и содержимое."""
    parts = [str(entry.get("name") or ""), str(entry.get("comment") or ""), str(entry.get("content") or "")]
    for name in ("key", "keys", "keysecondary", "secondary_keys"):
        value = entry.get(name)
        if isinstance(value, list):
            parts.extend(str(x) for x in value)
        elif isinstance(value, str):
            parts.append(value)
    return "\n".join(parts).lower()


def place_at(entries, selected, position):
    """Поставить выбранные записи так, чтобы первая из них оказалась на позиции `position` (с 1)."""
    n = len(entries)
    selected = sorted({i for i in selected if 0 <= i < n})
    if not selected:
        return list(entries), []
    picked = [entries[i] for i in selected]
    chosen = set(selected)
    rest = [e for i, e in enumerate(entries) if i not in chosen]
    insert_at = max(0, min(position - 1, len(rest)))
    result = rest[:insert_at] + picked + rest[insert_at:]
    return result, list(range(insert_at, insert_at + len(picked)))


def shift_entries(entries, selected, direction):
    if not entries or not selected:
        return list(entries), list(selected)
    n = len(entries)
    selected = sorted({i for i in selected if 0 <= i < n})
    selected_set = set(selected)
    result = list(entries)

    if direction == "top":
        picked = [result[i] for i in selected]
        rest = [e for i, e in enumerate(result) if i not in selected_set]
        result = picked + rest
        return result, list(range(len(picked)))

    if direction == "bottom":
        picked = [result[i] for i in selected]
        rest = [e for i, e in enumerate(result) if i not in selected_set]
        result = rest + picked
        return result, list(range(len(rest), len(result)))

    if direction < 0:
        i = 1
        while i < n:
            if i in selected_set and (i - 1) not in selected_set:
                result[i - 1], result[i] = result[i], result[i - 1]
                selected_set.remove(i)
                selected_set.add(i - 1)
            i += 1
    else:
        i = n - 2
        while i >= 0:
            if i in selected_set and (i + 1) not in selected_set:
                result[i + 1], result[i] = result[i], result[i + 1]
                selected_set.remove(i)
                selected_set.add(i + 1)
            i -= 1
    return result, sorted(selected_set)


def move_entries_to(entries, selected, target):
    """Move selected indices to target index. Length never changes."""
    n = len(entries)
    selected = sorted({i for i in selected if 0 <= i < n})
    if not selected:
        return list(entries), []
    if target < 0:
        target = 0
    if target > n:
        target = n
    picked = [entries[i] for i in selected]
    chosen = set(selected)
    rest = [e for i, e in enumerate(entries) if i not in chosen]
    before = sum(1 for i in selected if i < target)
    insert_at = target - before
    if insert_at < 0:
        insert_at = 0
    if insert_at > len(rest):
        insert_at = len(rest)
    result = rest[:insert_at] + picked + rest[insert_at:]
    new_sel = list(range(insert_at, insert_at + len(picked)))
    return result, new_sel


ITEM_MIME = "application/x-qabstractitemmodeldatalist"


class EntryList(QListWidget):
    """Drag-and-drop группы записей. Порядок меняет Organizer, а не Qt."""
    drop_at = Signal(int)

    def __init__(self):
        super().__init__()
        self.drag_rows = []
        self._keep_group = False
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropMode(QAbstractItemView.DragDrop)

    def _event_pos(self, event):
        if hasattr(event, "position"):
            return event.position().toPoint()
        return event.pos()

    def mousePressEvent(self, event):
        # Нажатие на уже выделенную строку обрабатывает сам Qt: он не сбрасывает группу,
        # пока не ясно, начнётся ли перетаскивание. Здесь запоминаем, что группу надо сохранить
        # и при простом клике без перетаскивания.
        item = self.itemAt(self._event_pos(event))
        multi = bool(event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier))
        self._keep_group = bool(
            event.button() == Qt.LeftButton and item is not None and item.isSelected()
            and not multi and len(self.selectedItems()) > 1
        )
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        keep, self._keep_group = self._keep_group, False
        saved = [self.row(i) for i in self.selectedItems()] if keep else []
        super().mouseReleaseEvent(event)
        for row in saved:
            item = self.item(row)
            if item is not None and not item.isSelected():
                item.setSelected(True)

    def dropEvent(self, event):
        # Принимаем только собственное перетаскивание (не файлы и не текст из других программ).
        if not self.drag_rows or not event.mimeData().hasFormat(ITEM_MIME):
            event.ignore()
            return
        idx = self.indexAt(self._event_pos(event))
        if not idx.isValid():
            row = self.count()
        elif self.dropIndicatorPosition() == QAbstractItemView.DropIndicatorPosition.BelowItem:
            row = idx.row() + 1  # Qt рисует линию под строкой: ставим после неё
        else:
            row = idx.row()
        event.acceptProposedAction()
        self.drop_at.emit(row)

    def startDrag(self, supported_actions):
        items = self.selectedItems()
        rows = []
        for item in items:
            try:
                rows.append(int(item.data(Qt.UserRole)))
            except (TypeError, ValueError):
                continue
        if not rows:
            return
        self.drag_rows = sorted(set(rows))
        drag = QDrag(self)
        # Стандартный формат Qt: без него Qt не принимает drop в этот же список.
        drag.setMimeData(self.mimeData(items))
        try:
            drag.exec(Qt.MoveAction)
        finally:
            self.drag_rows = []


class Organizer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Lorebook Organizer {VERSION}")
        self.resize(720, 860)

        self.data = {"name": "Lorebook", "entries": {}}
        self.entries = []
        self.entries_where = "entries"
        self.current_file = None
        self.dirty = False
        self.history = []        # состояния для отмены: (список записей, выделение)
        self.future = []         # состояния для повтора
        self.saved_entries = []  # что записано на диске (для определения «изменён ли файл»)
        self.saved_name = ""

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        self.lorebook_name = QLineEdit()
        self.lorebook_name.setPlaceholderText("Lorebook name")
        self.lorebook_name.textChanged.connect(self.on_name_changed)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter by name, keywords, content...")
        self.search.textChanged.connect(lambda _t: self.refresh())

        self.list = EntryList()
        self.list.drop_at.connect(self.on_drop_at)
        self.list.itemSelectionChanged.connect(self.update_status)

        btn_open = QPushButton("Open")
        btn_save = QPushButton("Save")
        btn_up = QPushButton("Up")
        btn_down = QPushButton("Down")
        btn_top = QPushButton("Top")
        btn_bottom = QPushButton("Bottom")
        btn_delete = QPushButton("Delete")
        btn_clear_filter = QPushButton("Clear filter")
        btn_undo = QPushButton("Undo")
        btn_redo = QPushButton("Redo")
        btn_move_to = QPushButton("Move to #")
        self.pos_spin = QSpinBox()
        self.pos_spin.setRange(1, 1)
        self.pos_spin.setToolTip("Position in the whole list (Ctrl+G to focus, Enter to move)")
        for button, tip in (
            (btn_open, "Open (Ctrl+O)"), (btn_save, "Save (Ctrl+S)"),
            (btn_undo, "Undo (Ctrl+Z)"), (btn_redo, "Redo (Ctrl+Y)"),
            (btn_up, "Move up (Alt+Up)"), (btn_down, "Move down (Alt+Down)"),
            (btn_top, "Move to the start (Alt+Home)"), (btn_bottom, "Move to the end (Alt+End)"),
            (btn_delete, "Delete selected (Delete)"),
            (btn_move_to, "Put the selected entries at the chosen position"),
        ):
            button.setToolTip(tip)

        btn_open.clicked.connect(lambda: self.open_file())
        btn_save.clicked.connect(self.save_file)
        btn_up.clicked.connect(lambda: self.move_selection(-1))
        btn_down.clicked.connect(lambda: self.move_selection(1))
        btn_top.clicked.connect(lambda: self.move_selection("top"))
        btn_bottom.clicked.connect(lambda: self.move_selection("bottom"))
        btn_delete.clicked.connect(self.delete_selected)
        btn_clear_filter.clicked.connect(self.clear_filter)
        btn_undo.clicked.connect(self.undo)
        btn_redo.clicked.connect(self.redo)
        btn_move_to.clicked.connect(self.move_to_position)
        self.pos_spin.lineEdit().returnPressed.connect(self.move_to_position)

        files = QHBoxLayout()
        files.addWidget(btn_open)
        files.addWidget(btn_save)
        files.addWidget(btn_undo)
        files.addWidget(btn_redo)

        filt = QHBoxLayout()
        filt.addWidget(self.search)
        filt.addWidget(btn_clear_filter)

        moves = QHBoxLayout()
        moves.addWidget(btn_up)
        moves.addWidget(btn_down)
        moves.addWidget(btn_top)
        moves.addWidget(btn_bottom)
        moves.addWidget(btn_delete)

        goto = QHBoxLayout()
        goto.addWidget(btn_move_to)
        goto.addWidget(self.pos_spin)
        goto.addStretch()

        self.status = QLabel("No file")

        layout.addLayout(files)
        layout.addWidget(self.lorebook_name)
        layout.addLayout(filt)
        layout.addWidget(self.list, 1)
        layout.addLayout(moves)
        layout.addLayout(goto)
        layout.addWidget(self.status)
        self._setup_shortcuts()
        self.refresh()

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def _setup_shortcuts(self):
        def add(sequence, slot, widget=None):
            shortcut = QShortcut(QKeySequence(sequence), widget or self, slot)
            if widget is not None:
                shortcut.setContext(Qt.WidgetShortcut)  # только когда фокус в этом виджете
            return shortcut

        add("Ctrl+O", lambda: self.open_file())
        add("Ctrl+S", self.save_file)
        add("Ctrl+F", lambda: (self.search.setFocus(), self.search.selectAll()))
        add("Ctrl+G", lambda: (self.pos_spin.setFocus(), self.pos_spin.selectAll()))
        add("Ctrl+Z", self.undo)
        add("Ctrl+Y", self.redo)
        add("Ctrl+Shift+Z", self.redo)
        add("Alt+Up", lambda: self.move_selection(-1))
        add("Alt+Down", lambda: self.move_selection(1))
        add("Alt+Home", lambda: self.move_selection("top"))
        add("Alt+End", lambda: self.move_selection("bottom"))
        add("Delete", self.delete_selected, self.list)  # в поле фильтра Delete стирает символы

    def on_name_changed(self, text):
        # Имя применяется при сохранении (build_payload): в карточке персонажа корневое `name`
        # принадлежит персонажу и не должно перезаписываться здесь.
        self.recompute_dirty()

    def recompute_dirty(self):
        """Файл считается изменённым, если порядок/состав записей или имя отличаются от сохранённых."""
        same = len(self.entries) == len(self.saved_entries) and all(
            a is b for a, b in zip(self.entries, self.saved_entries)
        )
        self.dirty = (not same) or self.lorebook_name.text() != self.saved_name
        self.update_title()

    def mark_saved(self):
        self.saved_entries = list(self.entries)
        self.saved_name = self.lorebook_name.text()
        self.dirty = False
        self.update_title()

    def snapshot(self):
        return list(self.entries), self.selected_indexes()

    def push_history(self):
        self.history.append(self.snapshot())
        del self.history[:-HISTORY_LIMIT]
        self.future.clear()

    def restore(self, state):
        entries, selection = state
        self.entries = list(entries)
        self.recompute_dirty()
        self.refresh(restore=selection)

    def undo(self):
        if self.history:
            self.future.append(self.snapshot())
            self.restore(self.history.pop())

    def redo(self):
        if self.future:
            self.history.append(self.snapshot())
            self.restore(self.future.pop())

    def update_title(self):
        name = self.lorebook_name.text().strip() or "Lorebook Organizer"
        mark = " *" if self.dirty else ""
        self.setWindowTitle(f"Lorebook Organizer {VERSION} - {name}{mark}")

    def clear_filter(self):
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.refresh()

    def selected_indexes(self):
        chosen = []
        for item in self.list.selectedItems():
            if item.isHidden():
                continue
            try:
                idx = int(item.data(Qt.UserRole))
            except (TypeError, ValueError):
                continue
            if 0 <= idx < len(self.entries):
                chosen.append(idx)
        return sorted(set(chosen))

    def visible_indexes(self):
        return [i for i in range(self.list.count()) if not self.list.item(i).isHidden()]

    def update_status(self):
        query = self.search.text().strip()
        extra = f" | filter: {len(self.visible_indexes())} shown" if query else ""
        self.status.setText(
            f"Entries: {len(self.entries)} | selected: {len(self.selected_indexes())}{extra}"
        )

    def refresh(self, restore=None):
        query = self.search.text().strip().lower()
        wanted = set(self.selected_indexes() if restore is None else restore)

        self.list.blockSignals(True)
        self.list.clear()
        first_item = None
        for i, entry in enumerate(self.entries):
            item = QListWidgetItem(entry_row_text(i + 1, entry, f"Entry {i + 1}"))
            item.setData(Qt.UserRole, i)
            self.list.addItem(item)  # setHidden() работает только для элемента, уже добавленного в список
            hidden = bool(query) and query not in entry_haystack(entry)
            item.setHidden(hidden)
            if i in wanted and not hidden:
                item.setSelected(True)
                if first_item is None:
                    first_item = item
        if first_item is not None:
            self.list.setCurrentItem(first_item, QItemSelectionModel.NoUpdate)
        self.list.blockSignals(False)
        self.pos_spin.setRange(1, max(1, len(self.entries)))
        if first_item is not None:
            self.list.scrollToItem(first_item)
        self.update_status()

    def apply_order(self, new_items, new_sel):
        if len(new_items) != len(self.entries):
            QMessageBox.critical(self, "Error", "Move aborted: entry count would change.")
            return
        self.push_history()
        self.entries = new_items
        self.recompute_dirty()
        self.refresh(restore=new_sel)

    def move_to_position(self):
        selected = self.selected_indexes()
        if not selected:
            return
        new_items, new_sel = place_at(self.entries, selected, self.pos_spin.value())
        if all(a is b for a, b in zip(new_items, self.entries)):
            return
        self.apply_order(new_items, new_sel)

    def move_selection(self, direction):
        selected = self.selected_indexes()
        if not selected:
            return
        if direction in ("top", "bottom"):
            new_items, new_sel = shift_entries(self.entries, selected, direction)
        else:
            # Up/Down двигают относительно видимых записей: при активном фильтре запись
            # не должна «меняться местами» со скрытой соседкой.
            visible = self.visible_indexes()
            slot = {entry_idx: pos for pos, entry_idx in enumerate(visible)}
            part = [self.entries[i] for i in visible]
            part_new, part_sel = shift_entries(part, [slot[i] for i in selected if i in slot], direction)
            new_items = list(self.entries)
            for entry_idx, entry in zip(visible, part_new):
                new_items[entry_idx] = entry
            new_sel = [visible[j] for j in part_sel]
        if len(new_items) == len(self.entries) and all(a is b for a, b in zip(new_items, self.entries)):
            return
        self.apply_order(new_items, new_sel)

    def on_drop_at(self, target_row):
        selected = list(self.list.drag_rows)
        if not selected:
            return
        new_items, new_sel = move_entries_to(self.entries, selected, target_row)
        self.apply_order(new_items, new_sel)

    def delete_selected(self):
        selected = self.selected_indexes()
        if not selected:
            return
        r = QMessageBox.question(
            self,
            "Delete",
            f"Delete {len(selected)} selected entries? (Ctrl+Z undoes it.)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if r != QMessageBox.Yes:
            return
        skip = set(selected)
        self.push_history()
        self.entries = [e for i, e in enumerate(self.entries) if i not in skip]
        self.recompute_dirty()
        self.refresh(restore=[])

    def eventFilter(self, obj, event):
        kind = event.type()
        # Файл, брошенный в любое место окна, открывается как через Open. Перетаскивание
        # записей внутри списка файлов не несёт и проходит дальше как обычно.
        if kind in (QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop) \
                and isinstance(obj, QWidget) and obj.window() is self:
            mime = event.mimeData()
            paths = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()] if mime and mime.hasUrls() else []
            if paths:
                if kind == QEvent.Type.Drop:
                    # Первый .json (если его нет — первый файл, и открытие покажет ошибку).
                    path = next((x for x in paths if x.lower().endswith(".json")), paths[0])
                    # Открываем после завершения drop: окно с вопросом внутри обработчика
                    # заблокировало бы Проводник, из которого тащат файл.
                    QTimer.singleShot(0, lambda: self.open_file(path))
                # Всегда «скопировано»: с Shift система предлагает «переместить», и Проводник Windows
                # после такого ответа может удалить исходный файл. Программа файл только читает.
                event.setDropAction(Qt.DropAction.CopyAction)
                event.accept()
                return True
        return super().eventFilter(obj, event)

    def confirm_unsaved(self, action):
        """Вопрос о несохранённых правках перед открытием другого файла или закрытием.
        False — отмена (Cancel или окно сохранения закрыто без сохранения)."""
        if self.dirty:
            r = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"Save changes before {action}?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes,
            )
            if r == QMessageBox.Cancel:
                return False
            if r == QMessageBox.Yes:
                self.save_file()
                if self.dirty:
                    return False
        return True

    def open_file(self, path=None):
        """Open (path=None — выбрать файл в окне) или файл, брошенный в окно."""
        if not self.confirm_unsaved("opening another file"):
            return

        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Open", "", "JSON (*.json)")
        if not path:
            return
        try:
            loaded = load_json(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open JSON:\n{e}")
            return

        raw, where = find_entries_container(loaded)
        entries = entries_to_list(raw)
        if not entries:
            # Не подменяем текущий лорбук: иначе сохранение «пустого» файла затёрло бы
            # данные в формате, который программа не распознала.
            QMessageBox.warning(
                self, "No entries",
                "No lorebook entries were found in this file. The current lorebook was left unchanged."
            )
            return

        self.data = loaded
        self.entries_where = where
        self.entries = entries
        self.current_file = path

        self.lorebook_name.blockSignals(True)
        self.lorebook_name.setText(read_lorebook_name(loaded, where))
        self.lorebook_name.blockSignals(False)
        self.history.clear()
        self.future.clear()
        self.mark_saved()
        # Номера выделенных строк старого файла к новому не относятся: refresh() не должен их выделить.
        self.list.clearSelection()
        self.clear_filter()

    def save_file(self):
        name = self.lorebook_name.text()
        payload, where = build_payload(self.data, self.entries_where, self.entries, name)

        safe = "".join(c for c in name if c not in '\\/:*?"<>|' and ord(c) >= 32).strip().rstrip(".")
        if safe:
            suggested = f"{safe}.json"
        elif self.current_file:
            suggested = Path(self.current_file).name
        else:
            suggested = "lorebook.json"
        if self.current_file:
            suggested = str(Path(self.current_file).parent / suggested)

        path, _ = QFileDialog.getSaveFileName(self, "Save", suggested, "JSON (*.json)")
        if not path:
            return
        if Path(path).suffix.lower() != ".json":  # "my.book" -> "my.book.json"
            path += ".json"
        try:
            save_json(path, payload)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save JSON:\n{e}")
            return
        self.data = payload
        self.entries_where = where
        self.current_file = path
        self.mark_saved()

    def closeEvent(self, event):
        if self.confirm_unsaved("closing"):
            event.accept()
        else:
            event.ignore()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(THEME)
    win = Organizer()
    win.show()
    code = app.exec()
    # Сигналы держат окно через лямбды, поэтому само оно не удаляется. Удаляем его явно,
    # пока QApplication ещё жив, иначе при выходе бывает Segmentation fault.
    shiboken6.delete(win)
    sys.exit(code)
