"""Schema-driven Caelestia shell settings.

Every option from ``shell.json`` is rendered from the bundled schema
(``src/data/shell_schema.json``):

* searchable categories with a section sidebar;
* global or per-monitor editing;
* staged changes applied in one pass (one backup and one shell restart);
* resets remove the override so the default/global value comes back;
* simple options use native rows, string lists have a small editor and
  list-of-object options have a validated JSON editor (actions, idle timeouts,
  bar entries, status icons, …).
"""

from __future__ import annotations

import json
import shlex

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src import backup, shell_config, shell_schema
from src.config import restart_caelestia
from src.lang import t
from src.preview import PreviewModel, build_preview_box, show_preview

_MISSING = object()


def _deep_get(data: dict, path: str, default=None):
    node = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def _deep_equal(a, b) -> bool:
    return a == b


def _preview(value, limit: int = 90) -> str:
    text = json.dumps(value, separators=(",", ":"))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _number_range(option: shell_schema.Option) -> tuple[float, float, float]:
    path = option.path.lower()
    default = option.default
    if "opacity" in path or "threshold" in path or path.endswith("clear"):
        return 0.0, 1.0, 0.05
    if "weight" in path:
        return 100, 900, 50
    if path.endswith("size") or ".size" in path:
        return 0, 512, 1
    if "timeout" in path or "interval" in path or "delay" in path or "threshold" in path:
        return 0, 600_000, 100
    if "scale" in path or "deform" in path:
        return 0, 20, 1
    if "level" in path or "tries" in path:
        return 0, 100, 1
    if "step" in path or "volume" in path or "increment" in path:
        return 0, 200, 1
    if isinstance(default, float):
        return 0.0, 10.0, 0.05
    return 0, 1000, 1


class ShellPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)

        self._staged: dict[str, dict[str, object]] = {}
        self._resets: dict[str, set[str]] = {}
        self._global_data: dict = {}
        self._monitor_data: dict = {}
        self._selected_section = shell_schema.sections()[0]
        self._rows: list[Gtk.Widget] = []
        self._last_apply: dict = {}

        self._build_toolbar()
        self._build_body()
        self._reload_data()
        self._rebuild_pages()
        self._select_section(self._selected_section)

    # ── Toolbar ───────────────────────────────────────────────────────────

    def _build_toolbar(self):
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.set_margin_top(10)
        bar.set_margin_bottom(6)
        bar.set_margin_start(12)
        bar.set_margin_end(12)

        self._search = Gtk.SearchEntry()
        self._search.set_hexpand(True)
        self._search.set_placeholder_text(t("Search Caelestia settings…"))
        self._search.connect("search-changed", lambda _e: self._rebuild_pages())
        bar.append(self._search)

        self._scope = Gtk.ComboBoxText()
        self._scope.set_valign(Gtk.Align.CENTER)
        self._scope.append("", t("All monitors (global)"))
        for name in self._monitor_names():
            self._scope.append(name, f"{t('Only')} {name}")
        self._scope.set_active(0)
        self._scope.connect("changed", self._on_scope_changed)
        bar.append(self._scope)

        self._reset_btn = Gtk.Button(label=t("Reset section"))
        self._reset_btn.set_tooltip_text(
            t("Remove this section's overrides so Caelestia defaults apply again")
        )
        self._reset_btn.connect("clicked", self._on_reset_section)
        bar.append(self._reset_btn)

        self._dirty_label = Gtk.Label()
        self._dirty_label.add_css_class("caption")
        self._dirty_label.add_css_class("dim-label")
        bar.append(self._dirty_label)

        self._preview_btn = Gtk.Button(label=t("Preview"))
        self._preview_btn.set_tooltip_text(t("Preview the staged appearance before applying"))
        self._preview_btn.connect("clicked", self._on_preview)
        bar.append(self._preview_btn)

        self._apply_btn = Gtk.Button(label=t("Review & apply"))
        self._apply_btn.add_css_class("suggested-action")
        self._apply_btn.set_sensitive(False)
        self._apply_btn.connect("clicked", self._on_apply)
        bar.append(self._apply_btn)

        self._undo_btn = Gtk.Button()
        self._undo_btn.set_icon_name("edit-undo-symbolic")
        self._undo_btn.set_tooltip_text(t("Undo the last applied change (this session)"))
        self._undo_btn.set_sensitive(False)
        self._undo_btn.connect("clicked", self._on_undo_last_apply)
        bar.append(self._undo_btn)

        self.append(bar)

        source = Gtk.Label()
        source.set_markup(
            f"<small>{t('Schema')}: caelestia-shell {shell_schema.source_tag()} · "
            f"{len(shell_schema.options())} {t('options')} · "
            f"{t('changes are written to')} <tt>~/.config/caelestia/shell.json</tt></small>"
        )
        source.set_halign(Gtk.Align.START)
        source.set_margin_start(12)
        source.set_margin_end(12)
        source.add_css_class("dim-label")
        self.append(source)

    def _monitor_names(self) -> list[str]:
        try:
            import subprocess

            result = subprocess.run(
                ["hyprctl", "monitors", "-j"], capture_output=True, text=True, timeout=3
            )
            return [monitor["name"] for monitor in json.loads(result.stdout)]
        except Exception:  # noqa: BLE001 - no compositor / invalid JSON
            return []

    def _scope_key(self) -> str:
        return self._scope.get_active_id() or ""

    # ── Body ──────────────────────────────────────────────────────────────

    def _build_body(self):
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        body.set_vexpand(True)
        self.append(body)

        nav_scroller = Gtk.ScrolledWindow()
        nav_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        nav_scroller.set_size_request(210, -1)
        self._nav = Gtk.ListBox()
        self._nav.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._nav.add_css_class("navigation-sidebar")
        self._nav.set_margin_top(6)
        self._nav.set_margin_bottom(6)
        self._nav.set_margin_start(6)
        self._nav.set_margin_end(6)
        self._nav.connect("row-selected", self._on_nav_selected)
        nav_scroller.set_child(self._nav)
        body.append(nav_scroller)

        body.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        self._stack = Gtk.Stack()
        self._stack.set_vexpand(True)
        self._stack.set_hexpand(True)
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        body.append(self._stack)

        self._nav_rows: dict[str, Gtk.ListBoxRow] = {}
        for section in shell_schema.sections():
            title, description, icon = shell_schema.section_meta(section)
            row = Gtk.ListBoxRow()
            row.set_tooltip_text(description)
            row._section = section  # type: ignore[attr-defined]
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            box.set_margin_top(8)
            box.set_margin_bottom(8)
            box.set_margin_start(8)
            box.set_margin_end(8)
            image = Gtk.Image.new_from_icon_name(icon)
            box.append(image)
            label = Gtk.Label(label=title)
            label.set_halign(Gtk.Align.START)
            label.set_hexpand(True)
            box.append(label)
            count = Gtk.Label(label=str(len(shell_schema.options_for_section(section))))
            count.add_css_class("caption")
            count.add_css_class("dim-label")
            box.append(count)
            row.set_child(box)
            self._nav.append(row)
            self._nav_rows[section] = row

    def _on_nav_selected(self, _nav, row):
        if row is None or not hasattr(row, "_section"):
            return
        if self._search.get_text().strip():
            return
        self._selected_section = row._section
        self._stack.set_visible_child_name(f"section:{row._section}")

    def _select_section(self, section: str):
        row = self._nav_rows.get(section)
        if row is not None:
            self._nav.select_row(row)
        self._stack.set_visible_child_name(f"section:{section}")

    # ── Data ──────────────────────────────────────────────────────────────

    def _reload_data(self):
        self._global_data = shell_config.read_global()
        monitor = self._scope_key()
        self._monitor_data = shell_config.read_monitor(monitor) if monitor else {}

    def _scope_file_data(self) -> dict:
        return self._monitor_data if self._scope_key() else self._global_data

    def _fallback_value(self, option: shell_schema.Option):
        if self._scope_key():
            value = _deep_get(self._global_data, option.path, _MISSING)
            if value is not _MISSING:
                return value
        return option.default

    def _value_for(self, option: shell_schema.Option):
        staged = self._staged.get(self._scope_key(), {})
        if option.path in staged:
            return staged[option.path]
        if option.path in self._resets.get(self._scope_key(), set()):
            return self._fallback_value(option)
        value = _deep_get(self._scope_file_data(), option.path, _MISSING)
        if value is not _MISSING:
            return value
        return self._fallback_value(option)

    # ── Staging ───────────────────────────────────────────────────────────

    def _dirty_count(self) -> int:
        return sum(len(values) for values in self._staged.values()) + sum(
            len(paths) for paths in self._resets.values()
        )

    def _update_dirty(self):
        count = self._dirty_count()
        self._dirty_label.set_text(
            t("No unsaved changes") if count == 0 else f"{count} {t('unsaved change(s)')}"
        )
        self._apply_btn.set_sensitive(count > 0)

    def _stage(self, option: shell_schema.Option, value):
        scope = self._scope_key()
        staged = self._staged.setdefault(scope, {})
        resets = self._resets.setdefault(scope, set())

        raw = _deep_get(self._scope_file_data(), option.path, _MISSING)
        fallback = self._fallback_value(option)

        if raw is not _MISSING and _deep_equal(value, raw):
            staged.pop(option.path, None)
            resets.discard(option.path)
        elif _deep_equal(value, fallback):
            staged.pop(option.path, None)
            resets.add(option.path)
        else:
            staged[option.path] = value
            resets.discard(option.path)

        self._update_dirty()

    def _reset(self, option: shell_schema.Option):
        scope = self._scope_key()
        self._staged.get(scope, {}).pop(option.path, None)
        self._resets.setdefault(scope, set()).add(option.path)
        self._update_dirty()
        self._rebuild_pages()

    def _on_reset_section(self, _button):
        scope = self._scope_key()
        for option in shell_schema.options_for_section(self._selected_section):
            self._staged.get(scope, {}).pop(option.path, None)
            self._resets.setdefault(scope, set()).add(option.path)
        self._update_dirty()
        self._rebuild_pages()

    def _on_scope_changed(self, _combo):
        self._reload_data()
        self._rebuild_pages()

    def _preview_model(self) -> PreviewModel:
        values = {
            option.path: self._value_for(option) for option in shell_schema.options()
        }
        return PreviewModel(values)

    def _on_preview(self, _button):
        show_preview(self.main_window, self._preview_model())

    def _build_plan(self) -> list[dict]:
        """Normalise staged changes into per-scope changes/resets plus diff lines."""

        options = shell_schema.option_map()
        global_raw = shell_config.read_global()
        plan: list[dict] = []

        for scope in set(self._staged) | set(self._resets):
            staged = dict(self._staged.get(scope, {}))
            resets = set(self._resets.get(scope, set()))
            monitor = scope or None
            raw_data = shell_config.read_monitor(scope) if monitor else global_raw

            changes: dict = {}
            lines: list[str] = []
            label = scope or t("Global")

            for path, value in staged.items():
                option = options[path]
                if monitor:
                    fallback = _deep_get(global_raw, path, _MISSING)
                    if fallback is _MISSING:
                        fallback = option.default
                else:
                    fallback = option.default

                raw = _deep_get(raw_data, path, _MISSING)
                if _deep_equal(value, fallback):
                    resets.add(path)
                    old = fallback if raw is _MISSING else raw
                    lines.append(f"{path}: {old!r} → {value!r} (override removed)")
                elif raw is not _MISSING and _deep_equal(value, raw):
                    continue
                else:
                    changes[path] = value
                    old = fallback if raw is _MISSING else raw
                    lines.append(f"{path}: {old!r} → {value!r}")

            for path in sorted(resets):
                if path in staged:
                    continue
                option = options[path]
                if monitor:
                    fallback = _deep_get(global_raw, path, _MISSING)
                    if fallback is _MISSING:
                        fallback = option.default
                else:
                    fallback = option.default
                raw = _deep_get(raw_data, path, _MISSING)
                if raw is _MISSING:
                    continue
                lines.append(f"{path}: removed override (now {fallback!r})")

            if changes or resets:
                plan.append(
                    {
                        "scope": scope,
                        "label": label,
                        "changes": changes,
                        "resets": resets,
                        "lines": lines,
                    }
                )
        return plan

    def _on_apply(self, _button):
        plan = self._build_plan()
        if not plan:
            self.main_window.add_toast(Adw.Toast.new(t("Nothing to apply.")))
            return

        total = sum(len(entry["changes"]) + len(entry["resets"]) for entry in plan)
        dialog = Adw.MessageDialog(
            transient_for=self.main_window,
            heading=t("Review changes"),
            body=f"{total} {t('change(s) will be saved.')}",
        )
        text_parts = []
        for entry in plan:
            text_parts.append(f"[{entry['label']}]")
            text_parts.extend(f"  {line}" for line in entry["lines"])
        text = "\n".join(text_parts) or t("No visible changes.")

        dialog.set_extra_child(build_preview_box(self._preview_model(), text))

        dialog.add_response("cancel", t("Cancel"))
        dialog.add_response("apply", t("Apply"))
        dialog.set_response_appearance("apply", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("apply")

        def on_response(dialog_obj, response):
            if response == "apply":
                self._apply_plan(plan)

        dialog.connect("response", on_response)
        dialog.present()

    def _apply_plan(self, plan: list[dict]):
        backups: dict = {}
        any_changed = False
        try:
            for entry in plan:
                changed, entry_backups = shell_config.apply_changes_tracked(
                    entry["changes"],
                    entry["resets"],
                    monitor=entry["scope"] or None,
                    restart=False,
                )
                if changed:
                    any_changed = True
                    backups.update(entry_backups)

            if any_changed:
                restart_caelestia()
            self._last_apply = backups
            self._update_undo()
            self._staged.clear()
            self._resets.clear()
            self._reload_data()
            self._update_dirty()
            self._rebuild_pages()
            self.main_window.add_toast(
                Adw.Toast.new(
                    t("Caelestia settings applied.")
                    if any_changed
                    else t("Nothing to apply.")
                )
            )
        except backup.BackupError as exc:
            self.main_window.add_toast(Adw.Toast.new(str(exc)))
        except Exception as exc:  # noqa: BLE001 - defensive UI path
            self.main_window.add_toast(
                Adw.Toast.new(f"{t('Could not save Caelestia settings')}: {exc}")
            )

    def _update_undo(self):
        self._undo_btn.set_sensitive(bool(self._last_apply))

    def _on_undo_last_apply(self, _button):
        if not self._last_apply:
            return
        try:
            for target, backup_path in self._last_apply.items():
                backup.restore_backup(backup_path, target)
            self._last_apply = {}
            self._update_undo()
            restart_caelestia()
            self._reload_data()
            self._rebuild_pages()
            self.main_window.add_toast(Adw.Toast.new(t("Last apply undone.")))
        except backup.BackupError as exc:
            self.main_window.add_toast(Adw.Toast.new(str(exc)))
        except Exception as exc:  # noqa: BLE001
            self.main_window.add_toast(
                Adw.Toast.new(f"{t('Could not undo the last apply')}: {exc}")
            )

    def set_search(self, text: str):
        self._search.set_text(text)
        self._rebuild_pages()

    # ── Rendering ─────────────────────────────────────────────────────────

    def _rebuild_pages(self):
        while child := self._stack.get_first_child():
            self._stack.remove(child)
        self._rows.clear()

        query = self._search.get_text().strip().lower()
        if query:
            self._nav.set_sensitive(False)
            self._stack.add_named(self._build_search_page(query), "search")
            self._stack.set_visible_child_name("search")
        else:
            self._nav.set_sensitive(True)
            for section in shell_schema.sections():
                self._stack.add_named(self._build_section_page(section), f"section:{section}")
            self._stack.set_visible_child_name(f"section:{self._selected_section}")
        self._update_dirty()

    def _build_section_page(self, section: str) -> Gtk.Widget:
        title, description, _icon = shell_schema.section_meta(section)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(14)
        content.set_margin_bottom(18)
        content.set_margin_start(16)
        content.set_margin_end(16)
        scroller.set_child(content)

        heading = Gtk.Label(label=title)
        heading.add_css_class("title-2")
        heading.set_halign(Gtk.Align.START)
        content.append(heading)

        subtitle = Gtk.Label(label=description)
        subtitle.add_css_class("dim-label")
        subtitle.set_halign(Gtk.Align.START)
        subtitle.set_wrap(True)
        content.append(subtitle)

        groups: dict[str | None, Adw.PreferencesGroup] = {}
        for option in shell_schema.options_for_section(section):
            key = option.subgroup
            if key not in groups:
                groups[key] = Adw.PreferencesGroup(
                    title=shell_schema.group_title(section, key)
                )
                content.append(groups[key])
            groups[key].add(self._make_row(option))
        return scroller

    def _build_search_page(self, query: str) -> Gtk.Widget:
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(14)
        content.set_margin_bottom(18)
        content.set_margin_start(16)
        content.set_margin_end(16)
        scroller.set_child(content)

        matches = [
            option
            for option in shell_schema.options()
            if query in option.label.lower()
            or query in option.path.lower()
            or query in shell_schema.section_meta(option.section)[0].lower()
            or query in shell_schema.group_title(option.section, option.subgroup).lower()
        ]

        heading = Gtk.Label(label=f"{t('Search results')} ({len(matches)})")
        heading.add_css_class("title-2")
        heading.set_halign(Gtk.Align.START)
        content.append(heading)

        if not matches:
            status = Adw.StatusPage()
            status.set_icon_name("system-search-symbolic")
            status.set_title(t("No matching settings"))
            status.set_description(t("Try a different search term."))
            content.append(status)
            return scroller

        group = Adw.PreferencesGroup()
        for option in matches:
            group.add(self._make_row(option, show_section=True))
        content.append(group)
        return scroller

    # ── Row factory ───────────────────────────────────────────────────────

    def _make_row(self, option: shell_schema.Option, show_section: bool = False) -> Gtk.Widget:
        value = self._value_for(option)
        subtitle = option.path
        if show_section:
            subtitle = f"{shell_schema.section_meta(option.section)[0]} · {option.path}"
        if option.global_only and self._scope_key():
            subtitle += f" · {t('global only')}"

        scope = self._scope_key()
        overridden = (
            option.path in self._staged.get(scope, {})
            or option.path in self._resets.get(scope, set())
            or _deep_get(self._scope_file_data(), option.path, _MISSING) is not _MISSING
        )

        reset_btn = Gtk.Button()
        reset_btn.set_icon_name("edit-undo-symbolic")
        reset_btn.add_css_class("flat")
        reset_btn.set_tooltip_text(t("Reset to default"))
        reset_btn.set_valign(Gtk.Align.CENTER)
        reset_btn.set_visible(overridden)
        reset_btn.connect("clicked", lambda _b: self._reset(option))

        if option.kind == "bool":
            row = Adw.SwitchRow(title=option.label, subtitle=subtitle)
            row.set_active(bool(value))
            row.connect("notify::active", lambda r, _p: self._stage(option, r.get_active()))
            row.add_suffix(reset_btn)
            widget: Gtk.Widget = row
        elif option.kind in ("int", "float"):
            minimum, maximum, step = _number_range(option)
            row = Adw.SpinRow.new_with_range(minimum, maximum, step)
            row.set_title(option.label)
            row.set_subtitle(subtitle)
            if option.kind == "float":
                row.set_digits(2)
            try:
                row.set_value(float(value))
            except (TypeError, ValueError):
                row.set_value(float(option.default or 0))
            row.connect("notify::value", lambda r, _p: self._stage(option, r.get_value()))
            row.add_suffix(reset_btn)
            widget = row
        elif option.kind == "enum":
            row = Adw.ActionRow(title=option.label, subtitle=subtitle)
            combo = Gtk.ComboBoxText()
            combo.set_valign(Gtk.Align.CENTER)
            values = shell_schema.enums().get(option.enum or "", [])
            for enum_value in values:
                combo.append(enum_value, enum_value)
            if not combo.set_active_id(str(value)):
                combo.append(str(value), str(value))
                combo.set_active_id(str(value))
            combo.connect("changed", lambda c: self._stage(option, c.get_active_id() or ""))
            row.add_suffix(combo)
            row.add_suffix(reset_btn)
            widget = row
        elif option.kind == "strlist":
            widget = self._make_string_list(option, value, subtitle, reset_btn)
        elif option.kind == "objlist":
            widget = self._make_object_list(option, value, subtitle, reset_btn)
        else:
            row = Adw.ActionRow(title=option.label, subtitle=subtitle)
            entry = Gtk.Entry()
            entry.set_text(str(value if value is not None else ""))
            entry.set_width_chars(32)
            entry.set_valign(Gtk.Align.CENTER)
            entry.connect("changed", lambda e: self._stage(option, e.get_text()))
            row.add_suffix(entry)
            row.add_suffix(reset_btn)
            widget = row

        if option.global_only and self._scope_key():
            widget.set_sensitive(False)
        return widget

    def _make_string_list(self, option, value, subtitle, reset_btn) -> Gtk.Widget:
        items = list(value) if isinstance(value, list) else []
        expander = Adw.ExpanderRow(title=option.label, subtitle=f"{subtitle} · {len(items)}")
        expander.add_suffix(reset_btn)

        item_rows: list[Gtk.Widget] = []

        def render():
            for row in item_rows:
                expander.remove(row)
            item_rows.clear()
            for index, item in enumerate(items):
                row = Adw.EntryRow(title=t("Item"))
                row.set_text(str(item))
                row.connect(
                    "changed",
                    lambda r, idx=index: self._update_string_item(items, idx, r.get_text(), option),
                )
                delete = Gtk.Button()
                delete.set_icon_name("user-trash-symbolic")
                delete.add_css_class("flat")
                delete.set_valign(Gtk.Align.CENTER)
                delete.connect("clicked", lambda _b, idx=index: self._delete_string_item(items, idx, option, render))
                row.add_suffix(delete)
                expander.add_row(row)
                item_rows.append(row)

            add = Adw.EntryRow(title=t("Add item"))
            add.set_show_apply_button(True)
            add.connect("apply", lambda r: self._add_string_item(items, r, option, render))
            expander.add_row(add)
            item_rows.append(add)

        render()
        return expander

    def _update_string_item(self, items, index, text, option):
        if 0 <= index < len(items):
            items[index] = text
            self._stage(option, list(items))

    def _add_string_item(self, items, row, option, render):
        text = row.get_text().strip()
        if not text:
            return
        items.append(text)
        self._stage(option, list(items))
        render()

    def _delete_string_item(self, items, index, option, render):
        if 0 <= index < len(items):
            items.pop(index)
            self._stage(option, list(items))
            render()

    TOGGLE_LISTS = {
        "bar.entries": [
            "logo", "workspaces", "spacer", "activeWindow", "tray", "clock",
            "statusIcons", "power",
        ],
        "bar.statusIcons": [
            "lockStatus", "audio", "microphone", "kbLayout", "network",
            "bluetooth", "battery",
        ],
        "utilities.quickToggles": [
            "wifi", "bluetooth", "mic", "settings", "gameMode", "dnd", "vpn",
        ],
    }

    def _make_object_list(self, option, value, subtitle, reset_btn) -> Gtk.Widget:
        if option.path in self.TOGGLE_LISTS:
            return self._make_toggle_list(option, value, subtitle, reset_btn)
        if option.path == "launcher.actions":
            return self._make_actions_editor(option, value, subtitle, reset_btn)
        return self._make_json_list(option, value, subtitle, reset_btn)

    def _make_toggle_list(self, option, value, subtitle, reset_btn) -> Gtk.Widget:
        canonical = self.TOGGLE_LISTS[option.path]
        items = [dict(item) for item in value] if isinstance(value, list) else []
        items = [item for item in items if isinstance(item, dict) and item.get("id")]
        existing = {item.get("id") for item in items}
        for item_id in canonical:
            if item_id not in existing:
                items.append({"id": item_id, "enabled": False})

        expander = Adw.ExpanderRow(
            title=option.label,
            subtitle=f"{subtitle} · {len(items)} {t('items')}",
        )
        expander.add_suffix(reset_btn)
        rows: list[Gtk.Widget] = []

        def render():
            for row in rows:
                expander.remove(row)
            rows.clear()
            for index, item in enumerate(items):
                item_id = str(item.get("id", ""))
                row = Adw.ActionRow(
                    title=shell_schema._humanize(item_id),
                    subtitle=item_id,
                )
                switch = Gtk.Switch()
                switch.set_active(bool(item.get("enabled", False)))
                switch.set_valign(Gtk.Align.CENTER)
                switch.connect(
                    "notify::active",
                    lambda s, idx=index: self._set_toggle_item(items, idx, "enabled", s.get_active(), option),
                )
                row.add_suffix(switch)

                if index > 0:
                    up = Gtk.Button()
                    up.set_icon_name("go-up-symbolic")
                    up.add_css_class("flat")
                    up.set_valign(Gtk.Align.CENTER)
                    up.connect("clicked", lambda _b, idx=index: self._move_toggle_item(items, idx, -1, option, render))
                    row.add_suffix(up)
                if index < len(items) - 1:
                    down = Gtk.Button()
                    down.set_icon_name("go-down-symbolic")
                    down.add_css_class("flat")
                    down.set_valign(Gtk.Align.CENTER)
                    down.connect("clicked", lambda _b, idx=index: self._move_toggle_item(items, idx, 1, option, render))
                    row.add_suffix(down)
                expander.add_row(row)
                rows.append(row)

        render()
        return expander

    def _set_toggle_item(self, items, index, key, value, option):
        if 0 <= index < len(items):
            items[index][key] = value
            self._stage(option, [dict(item) for item in items])

    def _move_toggle_item(self, items, index, delta, option, render):
        target = index + delta
        if 0 <= target < len(items):
            items[index], items[target] = items[target], items[index]
            self._stage(option, [dict(item) for item in items])
            render()

    def _make_actions_editor(self, option, value, subtitle, reset_btn) -> Gtk.Widget:
        items = [dict(action) for action in value] if isinstance(value, list) else []
        items = [action for action in items if isinstance(action, dict)]

        expander = Adw.ExpanderRow(
            title=option.label,
            subtitle=f"{subtitle} · {len(items)} {t('actions')}",
        )
        expander.add_suffix(reset_btn)
        rows: list[Gtk.Widget] = []

        def stage():
            self._stage(option, [dict(action) for action in items])

        def render():
            for row in rows:
                expander.remove(row)
            rows.clear()
            expander.set_subtitle(f"{subtitle} · {len(items)} {t('actions')}")
            for index, action in enumerate(items):
                name = str(action.get("name", t("Untitled action")))
                command = action.get("command", [])
                command_text = (
                    shlex.join([str(part) for part in command])
                    if isinstance(command, list)
                    else str(command)
                )
                row = Adw.ActionRow(
                    title=name,
                    subtitle=action.get("description") or command_text or t("No command"),
                )
                icon = Gtk.Image.new_from_icon_name(
                    str(action.get("icon") or "application-x-executable")
                )
                icon.set_valign(Gtk.Align.CENTER)
                row.add_prefix(icon)

                if index > 0:
                    up = Gtk.Button()
                    up.set_icon_name("go-up-symbolic")
                    up.add_css_class("flat")
                    up.set_valign(Gtk.Align.CENTER)
                    up.connect("clicked", lambda _b, i=index: self._move_action(items, i, -1, stage, render))
                    row.add_suffix(up)
                if index < len(items) - 1:
                    down = Gtk.Button()
                    down.set_icon_name("go-down-symbolic")
                    down.add_css_class("flat")
                    down.set_valign(Gtk.Align.CENTER)
                    down.connect("clicked", lambda _b, i=index: self._move_action(items, i, 1, stage, render))
                    row.add_suffix(down)

                edit = Gtk.Button()
                edit.set_icon_name("document-edit-symbolic")
                edit.add_css_class("flat")
                edit.set_valign(Gtk.Align.CENTER)
                edit.set_tooltip_text(t("Edit action"))
                edit.connect(
                    "clicked",
                    lambda _b, i=index: self._open_action_dialog(option, items, i, stage, render),
                )
                row.add_suffix(edit)

                delete = Gtk.Button()
                delete.set_icon_name("user-trash-symbolic")
                delete.add_css_class("flat")
                delete.set_valign(Gtk.Align.CENTER)
                delete.set_tooltip_text(t("Delete action"))
                delete.connect("clicked", lambda _b, i=index: self._delete_action(items, i, stage, render))
                row.add_suffix(delete)

                expander.add_row(row)
                rows.append(row)

            add = Adw.ActionRow(
                title=t("Add action"),
                subtitle=t("Create a new launcher action"),
            )
            add_btn = Gtk.Button()
            add_btn.set_icon_name("list-add-symbolic")
            add_btn.add_css_class("flat")
            add_btn.set_valign(Gtk.Align.CENTER)
            add_btn.connect(
                "clicked",
                lambda _b: self._open_action_dialog(option, items, None, stage, render),
            )
            add.add_suffix(add_btn)
            expander.add_row(add)
            rows.append(add)

        render()
        return expander

    def _move_action(self, items, index, delta, stage, render):
        target = index + delta
        if 0 <= target < len(items):
            items[index], items[target] = items[target], items[index]
            stage()
            render()

    def _delete_action(self, items, index, stage, render):
        if 0 <= index < len(items):
            items.pop(index)
            stage()
            render()

    def _open_action_dialog(self, option, items, index, stage, render):
        action = items[index] if index is not None and 0 <= index < len(items) else {}
        dialog = Adw.MessageDialog(
            transient_for=self.main_window,
            heading=t("Edit launcher action") if index is not None else t("New launcher action"),
        )

        grid = Gtk.Grid()
        grid.set_row_spacing(8)
        grid.set_column_spacing(12)
        grid.set_margin_top(8)
        grid.set_margin_bottom(8)
        grid.set_margin_start(8)
        grid.set_margin_end(8)

        def label(text, row):
            widget = Gtk.Label(label=text)
            widget.set_halign(Gtk.Align.END)
            widget.add_css_class("dim-label")
            grid.attach(widget, 0, row, 1, 1)

        def entry(value: str, row: int, placeholder: str = "") -> Gtk.Entry:
            widget = Gtk.Entry()
            widget.set_hexpand(True)
            widget.set_text(value)
            widget.set_placeholder_text(placeholder)
            grid.attach(widget, 1, row, 1, 1)
            return widget

        label(t("Name"), 0)
        name = entry(str(action.get("name", "")), 0, "Calculator")

        label(t("Icon"), 1)
        icon = entry(str(action.get("icon", "")), 1, "calculate")

        label(t("Description"), 2)
        description = entry(str(action.get("description", "")), 2, "Do simple math")

        command = action.get("command", [])
        command_text = (
            shlex.join([str(part) for part in command])
            if isinstance(command, list)
            else str(command)
        )
        label(t("Command"), 3)
        command_entry = entry(command_text, 3, "caelestia wallpaper -r")

        label(t("Enabled"), 4)
        enabled = Gtk.Switch()
        enabled.set_active(bool(action.get("enabled", True)))
        enabled.set_halign(Gtk.Align.START)
        grid.attach(enabled, 1, 4, 1, 1)

        label(t("Dangerous"), 5)
        dangerous = Gtk.Switch()
        dangerous.set_active(bool(action.get("dangerous", False)))
        dangerous.set_halign(Gtk.Align.START)
        grid.attach(dangerous, 1, 5, 1, 1)

        dialog.set_extra_child(grid)
        dialog.add_response("cancel", t("Cancel"))
        dialog.add_response("save", t("Save"))
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)

        def on_response(dialog_obj, response):
            if response != "save":
                return
            try:
                command_list = shlex.split(command_entry.get_text())
            except ValueError as exc:
                self.main_window.add_toast(
                    Adw.Toast.new(f"{t('Invalid command')}: {exc}")
                )
                return

            updated = dict(action)
            updated.update(
                {
                    "name": name.get_text().strip() or t("Untitled action"),
                    "icon": icon.get_text().strip() or "application-x-executable",
                    "description": description.get_text().strip(),
                    "command": command_list,
                    "enabled": enabled.get_active(),
                    "dangerous": dangerous.get_active(),
                }
            )
            if index is None:
                items.append(updated)
            else:
                items[index] = updated
            stage()
            render()

        dialog.connect("response", on_response)
        dialog.present()

    def _make_json_list(self, option, value, subtitle, reset_btn) -> Gtk.Widget:
        items = value if isinstance(value, list) else []
        expander = Adw.ExpanderRow(
            title=option.label,
            subtitle=f"{subtitle} · {len(items)} {t('items')}",
        )
        expander.add_suffix(reset_btn)

        row = Adw.ActionRow(title=t("Edit JSON"), subtitle=_preview(items))
        edit = Gtk.Button(label=t("Edit"))
        edit.set_valign(Gtk.Align.CENTER)
        edit.connect("clicked", lambda _b: self._open_json_editor(option, items, expander, row))
        row.add_suffix(edit)
        expander.add_row(row)
        return expander

    def _open_json_editor(self, option, value, expander, preview_row):
        dialog = Adw.MessageDialog(
            transient_for=self.main_window,
            heading=option.label,
            body=t("Edit the list as JSON. The value must be a JSON array."),
        )
        text = json.dumps(value, indent=4)
        buffer = Gtk.TextBuffer()
        buffer.set_text(text)
        view = Gtk.TextView(buffer=buffer)
        view.set_monospace(True)
        view.set_wrap_mode(Gtk.WrapMode.NONE)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_min_content_width(640)
        scroller.set_min_content_height(380)
        scroller.set_child(view)
        dialog.set_extra_child(scroller)
        dialog.add_response("cancel", t("Cancel"))
        dialog.add_response("apply", t("Apply"))
        dialog.set_response_appearance("apply", Adw.ResponseAppearance.SUGGESTED)

        def on_response(dialog_obj, response):
            if response != "apply":
                return
            start, end = buffer.get_bounds()
            raw = buffer.get_text(start, end, True)
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                self.main_window.add_toast(
                    Adw.Toast.new(f"{t('Invalid JSON')}: {exc}")
                )
                return
            if not isinstance(parsed, list):
                self.main_window.add_toast(Adw.Toast.new(t("The value must be a JSON array.")))
                return
            self._stage(option, parsed)
            preview_row.set_subtitle(_preview(parsed))
            expander.set_subtitle(f"{option.path} · {len(parsed)} {t('items')}")

        dialog.connect("response", on_response)
        dialog.present()
