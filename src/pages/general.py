import re
import subprocess
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
from src.config import HYPR_INPUT_LUA, HYPR_INPUT_CONF
from src.lang import t

# Gängige Tastaturlayouts: (xkb-Code, Anzeigename)
KEYBOARD_LAYOUTS = [
    ("ad",  "Andorranisch"),
    ("af",  "Afghanisch"),
    ("al",  "Albanisch"),
    ("am",  "Armenisch"),
    ("ara", "Arabisch"),
    ("at",  "Österreichisch (AT)"),
    ("au",  "Australisch"),
    ("az",  "Aserbaidschanisch"),
    ("ba",  "Bosnisch"),
    ("bd",  "Bengalisch"),
    ("be",  "Belgisch"),
    ("bg",  "Bulgarisch"),
    ("br",  "Brasilianisch"),
    ("brai","Braille"),
    ("bt",  "Bhutanisch"),
    ("bw",  "Botswanisch"),
    ("by",  "Weißrussisch"),
    ("ca",  "Kanadisch"),
    ("cd",  "Kongolesisch (DR)"),
    ("ch",  "Schweizer"),
    ("cm",  "Kamerunisch"),
    ("cn",  "Chinesisch"),
    ("cz",  "Tschechisch"),
    ("de",  "Deutsch (DE)"),
    ("dk",  "Dänisch"),
    ("ee",  "Estnisch"),
    ("epo", "Esperanto"),
    ("es",  "Spanisch"),
    ("et",  "Äthiopisch"),
    ("eu",  "Baskisch"),
    ("fi",  "Finnisch"),
    ("fo",  "Färöisch"),
    ("fr",  "Französisch"),
    ("gb",  "Englisch (UK)"),
    ("ge",  "Georgisch"),
    ("gh",  "Ghanaisch"),
    ("gn",  "Guineisch"),
    ("gr",  "Griechisch"),
    ("hr",  "Kroatisch"),
    ("hu",  "Ungarisch"),
    ("ie",  "Irisch"),
    ("il",  "Hebräisch"),
    ("in",  "Indisch"),
    ("iq",  "Irakisch"),
    ("ir",  "Persisch"),
    ("is",  "Isländisch"),
    ("it",  "Italienisch"),
    ("jp",  "Japanisch"),
    ("ke",  "Kenianisch"),
    ("kg",  "Kirgisisch"),
    ("kh",  "Khmerisch"),
    ("kr",  "Koreanisch"),
    ("kz",  "Kasachisch"),
    ("la",  "Laotisch"),
    ("latam","Lateinamerikanisch"),
    ("lk",  "Singhalesisch"),
    ("lt",  "Litauisch"),
    ("lv",  "Lettisch"),
    ("ma",  "Marokkanisch"),
    ("mao", "Maori"),
    ("md",  "Moldauisch"),
    ("me",  "Montenegrinisch"),
    ("mk",  "Mazedonisch"),
    ("ml",  "Malisch"),
    ("mm",  "Myanmarisch"),
    ("mn",  "Mongolisch"),
    ("mt",  "Maltesisch"),
    ("mv",  "Maledivisch"),
    ("my",  "Malaysisch"),
    ("ng",  "Nigerianisch"),
    ("nl",  "Niederländisch"),
    ("no",  "Norwegisch"),
    ("np",  "Nepalesisch"),
    ("ph",  "Philippinisch"),
    ("pk",  "Pakistanisch"),
    ("pl",  "Polnisch"),
    ("pt",  "Portugiesisch"),
    ("ro",  "Rumänisch"),
    ("rs",  "Serbisch"),
    ("ru",  "Russisch"),
    ("se",  "Schwedisch"),
    ("si",  "Slowenisch"),
    ("sk",  "Slowakisch"),
    ("sn",  "Senegalesisch"),
    ("sy",  "Syrisch"),
    ("tg",  "Togoisch"),
    ("th",  "Thaiisch"),
    ("tj",  "Tadschikisch"),
    ("tm",  "Turkmenisch"),
    ("tr",  "Türkisch"),
    ("tw",  "Taiwanisch"),
    ("tz",  "Tansanisch"),
    ("ua",  "Ukrainisch"),
    ("us",  "Englisch (US)"),
    ("uz",  "Usbekisch"),
    ("vn",  "Vietnamesisch"),
    ("za",  "Südafrikanisch"),
]


def read_input_lua() -> dict:
    """Liest input.lua und gibt ein Dict mit kb_layout und numlock_by_default zurück."""
    result = {}
    target = HYPR_INPUT_LUA if HYPR_INPUT_LUA.exists() else HYPR_INPUT_CONF
    if not target.exists():
        return result
    try:
        content = target.read_text()
        m_layout = re.search(r'kb_layout\s*=\s*["\']([^"\']+)["\']', content)
        if m_layout:
            result["kb_layout"] = m_layout.group(1).split(",")[0].strip()
        m_numlock = re.search(r'numlock_by_default\s*=\s*(true|false)', content, re.IGNORECASE)
        if m_numlock:
            result["numlock_by_default"] = m_numlock.group(1).lower()
    except Exception as e:
        print(f"input.lua lesen fehler: {e}")
    return result

read_input_conf = read_input_lua


def _write_input_lua_key(key: str, value: str):
    """Ersetzt einen Schlüssel in input.lua als valides Lua."""
    target = HYPR_INPUT_LUA if HYPR_INPUT_LUA.exists() else HYPR_INPUT_CONF
    if not target.exists():
        return
    try:
        content = target.read_text()
        if key == "numlock_by_default":
            formatted_val = "true" if str(value).lower() == "true" else "false"
        else:
            formatted_val = f'"{value}"'

        pattern = rf"^(\s*{re.escape(key)}\s*=\s*)[^,\n]+(,?)"
        new_line = rf"\g<1>{formatted_val}\g<2>"
        new_content, n = re.subn(pattern, new_line, content, flags=re.MULTILINE)
        if n == 0:
            if "input = {" in content:
                new_content = re.sub(
                    r"(input\s*=\s*\{)",
                    rf"\1\n        {key} = {formatted_val},",
                    content,
                    count=1
                )
            else:
                new_content = content + f"\n{key} = {formatted_val}\n"
        target.write_text(new_content)
    except Exception as e:
        print(f"input.lua schreiben fehler: {e}")

_write_input_conf_key = _write_input_lua_key


class GeneralPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(12)
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(12)
        self.set_margin_end(12)

        self.is_loading = False

        # ── EINGABE ──────────────────────────────────────────────────────
        input_group = Adw.PreferencesGroup(title=t("Input"))
        self.append(input_group)

        # Tastaturlayout-Dropdown
        layout_row = Adw.ActionRow(title=t("Keyboard Layout"))
        layout_row.set_subtitle(t("Live change in Hyprland"))

        self.layout_combo = Gtk.ComboBoxText()
        self.layout_combo.set_valign(Gtk.Align.CENTER)

        # Suchfunktion via Gtk.ComboBox hat keinen eingebauten Filter —
        # wir nutzen ein Entry-Completion-ähnliches Dropdown
        for code, label in KEYBOARD_LAYOUTS:
            self.layout_combo.append(code, f"{label}  ({code})")

        layout_row.add_suffix(self.layout_combo)
        input_group.add(layout_row)

        # NumLock
        self.numlock_row = Adw.SwitchRow(
            title="NumLock beim Start aktivieren",
            subtitle="numlock_by_default in input.lua"
        )
        input_group.add(self.numlock_row)

        # ── REGION & SPRACHE ─────────────────────────────────────────────
        system_group = Adw.PreferencesGroup(title=t("Region and Language"))
        self.append(system_group)

        lang_row = Adw.ActionRow(title=t("System Language"))
        lang_row.set_subtitle(t("Requires password"))
        self.lang_combo = Gtk.ComboBoxText()
        self.lang_combo.append("de_DE.UTF-8", "Deutsch (Deutschland)")
        self.lang_combo.append("en_US.UTF-8", "English (US)")
        self.lang_combo.append("en_GB.UTF-8", "English (UK)")
        lang_row.add_suffix(self.lang_combo)
        system_group.add(lang_row)

        time_row = Adw.ActionRow(title=t("Timezone"))
        self.time_combo = Gtk.ComboBoxText()
        self.time_combo.append("Europe/Berlin",   "Berlin (CET/CEST)")
        self.time_combo.append("Europe/London",   "London (GMT/BST)")
        self.time_combo.append("America/New_York","New York (EST/EDT)")
        self.time_combo.append("UTC",             "UTC")
        time_row.add_suffix(self.time_combo)
        system_group.add(time_row)

        # Laden & Signale
        self._load_all()
        self.layout_combo.connect("changed",        self._on_layout_changed)
        self.numlock_row.connect("notify::active",  self._on_numlock_changed)
        self.lang_combo.connect("changed",          self._on_language_changed)
        self.time_combo.connect("changed",          self._on_timezone_changed)

    # ── Laden ─────────────────────────────────────────────────────────────

    def _load_all(self):
        self.is_loading = True

        conf = read_input_conf()

        # Tastaturlayout
        layout = conf.get("kb_layout", "us").lower()
        if not self.layout_combo.set_active_id(layout):
            # Unbekanntes Layout ans Ende anhängen
            self.layout_combo.append(layout, f"Unbekannt  ({layout})")
            self.layout_combo.set_active_id(layout)

        # NumLock
        numlock_val = conf.get("numlock_by_default", "false").lower()
        self.numlock_row.set_active(numlock_val == "true")

        # Systemsprache
        try:
            res = subprocess.run(["localectl", "status"], capture_output=True, text=True)
            for line in res.stdout.splitlines():
                if "LANG=" in line:
                    lang = line.split("LANG=")[1].strip()
                    if not self.lang_combo.set_active_id(lang):
                        self.lang_combo.append(lang, f"{t('Current')}: {lang}")
                        self.lang_combo.set_active_id(lang)
        except Exception as e:
            print(f"Err Lang: {e}")

        # Zeitzone
        try:
            res = subprocess.run(
                ["timedatectl", "show", "-p", "Timezone", "--value"],
                capture_output=True, text=True
            )
            tz = res.stdout.strip()
            if not self.time_combo.set_active_id(tz):
                self.time_combo.append(tz, f"{t('Current')}: {tz}")
                self.time_combo.set_active_id(tz)
        except Exception as e:
            print(f"Err Time: {e}")

        self.is_loading = False

    # ── Callbacks ─────────────────────────────────────────────────────────

    def show_toast(self, message):
        toast = Adw.Toast.new(message)
        if hasattr(self.main_window, "add_toast"):
            self.main_window.add_toast(toast)

    def _on_layout_changed(self, combo):
        if self.is_loading: return
        lang = combo.get_active_id()
        if not lang: return
        try:
            subprocess.run(["hyprctl", "keyword", "input:kb_layout", lang], check=True)
            _write_input_conf_key("kb_layout", lang)
            self.show_toast(f"Tastaturlayout: {lang.upper()}")
        except Exception as e:
            self.show_toast(f"Fehler: {e}")

    def _on_numlock_changed(self, row, _):
        if self.is_loading: return
        val = "true" if row.get_active() else "false"
        try:
            subprocess.run(["hyprctl", "keyword", "input:numlock_by_default", val], check=True)
            _write_input_conf_key("numlock_by_default", val)
            self.show_toast(f"NumLock: {val}")
        except Exception as e:
            self.show_toast(f"Fehler: {e}")

    def _on_language_changed(self, combo):
        if self.is_loading: return
        lang = combo.get_active_id()
        if not lang: return
        try:
            subprocess.run(["pkexec", "localectl", "set-locale", f"LANG={lang}"], check=True)
            self.show_toast(t("Language set successfully (reboot needed)."))
        except subprocess.CalledProcessError:
            self.show_toast(t("Language change cancelled."))
            self._load_all()
        except Exception as e:
            self.show_toast(f"Fehler: {e}")
            self._load_all()

    def _on_timezone_changed(self, combo):
        if self.is_loading: return
        tz = combo.get_active_id()
        if not tz: return
        try:
            subprocess.run(["pkexec", "timedatectl", "set-timezone", tz], check=True)
            self.show_toast(t("Timezone set successfully."))
        except subprocess.CalledProcessError:
            self.show_toast(t("Timezone change cancelled."))
            self._load_all()
        except Exception as e:
            self.show_toast(f"Fehler: {e}")
            self._load_all()