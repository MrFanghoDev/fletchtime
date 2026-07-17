"""Fenêtre graphique du serveur -- remplace le terminal comme point
d'entrée principal sur toutes les plateformes (PC et Pydroid), voir
``fletchtime.__main__.main`` qui bascule ici par défaut (et retombe sur le
mode terminal si ce module ne peut pas être importé, ex. `customtkinter`
absent).

Le serveur (HTTP + WebSocket, voir ``fletchtime.runtime.ServerRuntime``)
démarre automatiquement à l'ouverture de la fenêtre, avec des boutons pour
l'arrêter/le relancer sans fermer l'application. Le journal affiché est une
redirection de stdout/stderr (voir ``_QueueWriter``) : capte aussi bien le
journal d'accès HTTP (``http.server`` écrit sur stderr) que n'importe quel
``print()`` du reste de l'appli, sans avoir à instrumenter chaque site
d'appel.

```{warning}
La fenêtre elle-même (rendu customtkinter) n'a pas pu être testée
visuellement lors de son écriture -- l'environnement de développement
utilisé n'a pas d'affichage graphique disponible. La logique de démarrage/
arrêt du serveur qu'elle pilote (``ServerRuntime``) est, elle, testée
(voir tests/test_runtime.py). Un premier lancement réel sur PC et sur
Pydroid reste nécessaire pour confirmer le rendu et l'ergonomie tactile.
```
"""

from __future__ import annotations

import queue
import sys
import webbrowser

import customtkinter as ctk

from fletchtime import __version__
from fletchtime.__main__ import (
    HTTP_PORT,
    WS_PORT,
    _app_web_dir,
    _data_root,
    ensure_directories,
    local_ip,
)
from fletchtime.runtime import ServerRuntime

_TRANSLATIONS = {
    "fr": {
        "title": "FletchTime -- Serveur",
        "start": "Démarrer",
        "stop": "Arrêter",
        "quit": "Quitter",
        "home": "Accueil",
        "control": "Contrôle",
        "display": "Affichage",
        "status_stopped": "Serveur arrêté",
        "status_running": "Serveur en cours -- {ip}",
        "log_title": "Journal",
        "club_data": "Données du club :",
    },
    "en": {
        "title": "FletchTime -- Server",
        "start": "Start",
        "stop": "Stop",
        "quit": "Quit",
        "home": "Home",
        "control": "Control",
        "display": "Display",
        "status_stopped": "Server stopped",
        "status_running": "Server running -- {ip}",
        "log_title": "Log",
        "club_data": "Club data:",
    },
}


class _QueueWriter:
    """Fichier-like minimal : réémet vers le flux d'origine (utile si un
    terminal existe malgré tout, ex. lancé depuis un IDE) et pousse chaque
    ligne dans une file thread-safe pour que la fenêtre l'affiche -- les
    serveurs tournent dans d'autres threads (voir ServerRuntime), donc tout
    ce qu'ils impriment (journal d'accès HTTP compris) arrive ici depuis un
    thread différent de celui de la fenêtre ; queue.Queue est thread-safe
    par construction, donc rien de plus à faire côté écriture."""

    def __init__(self, original, log_queue: queue.Queue) -> None:
        self._original = original
        self._queue = log_queue

    def write(self, text: str) -> None:
        if self._original is not None:
            try:
                self._original.write(text)
            except Exception:
                pass
        if text.strip():
            self._queue.put(text.rstrip("\n"))

    def flush(self) -> None:
        if self._original is not None:
            try:
                self._original.flush()
            except Exception:
                pass


def _apply_brand_colors() -> None:
    """Surcharge uniquement les couleurs du thème `customtkinter` déjà
    chargé (voir FletchTimeApp.__init__) pour reprendre la palette de
    marque de l'appli -- mêmes couleurs que les pages web en thème sombre.
    Ne touche à aucune clé structurelle (rayons, épaisseurs de bordure...),
    qui reste celle du thème intégré ("dark-blue"), déjà complète et
    testée pour la version de `customtkinter` installée -- un thème
    entièrement personnalisé (JSON maison) risquait d'oublier une clé
    interne attendue par une version différente de la bibliothèque,
    faisant planter la construction de la fenêtre (déjà rencontré en
    pratique)."""
    try:
        theme = ctk.ThemeManager.theme

        def set_color(widget: str, key: str, light: str, dark: str) -> None:
            # Ne crée jamais une clé absente du thème chargé -- seulement
            # remplacer une valeur déjà attendue à cet endroit précis.
            if widget in theme and key in theme[widget]:
                theme[widget][key] = [light, dark]

        set_color("CTk", "fg_color", "#eef1f6", "#0f1216")
        set_color("CTkToplevel", "fg_color", "#eef1f6", "#0f1216")

        set_color("CTkFrame", "fg_color", "#ffffff", "#171b22")
        set_color("CTkFrame", "top_fg_color", "#f2f4f9", "#1d232c")
        set_color("CTkFrame", "border_color", "#d7dce6", "#2a3140")

        set_color("CTkButton", "fg_color", "#a8781f", "#d1a13d")
        set_color("CTkButton", "hover_color", "#8a6119", "#b38732")
        set_color("CTkButton", "text_color", "#ffffff", "#0f1216")

        set_color("CTkLabel", "text_color", "#1b2333", "#e8ebf1")

        set_color("CTkEntry", "fg_color", "#f2f4f9", "#1d232c")
        set_color("CTkEntry", "border_color", "#d7dce6", "#2a3140")
        set_color("CTkEntry", "text_color", "#1b2333", "#e8ebf1")

        set_color("CTkOptionMenu", "fg_color", "#3357bf", "#4c7bdb")

        set_color("CTkTextbox", "fg_color", "#f2f4f9", "#05070a")
        set_color("CTkTextbox", "border_color", "#d7dce6", "#2a3140")
        set_color("CTkTextbox", "text_color", "#1b2333", "#e8ebf1")
    except Exception:
        # Filet de sécurité : si l'API interne de ThemeManager diffère de
        # ce qui est attendu ici (ex. version de customtkinter différente),
        # l'appli continue avec le thème intégré "dark-blue" tel quel --
        # moins conforme à la charte graphique, mais jamais un plantage au
        # démarrage pour une simple histoire de couleurs.
        pass


class FletchTimeApp(ctk.CTk):
    def __init__(self) -> None:
        # Doit être fait AVANT super().__init__() : customtkinter applique
        # le thème au moment de la construction de chaque widget, fenêtre
        # racine comprise -- appelé après, la fenêtre elle-même garderait
        # le thème par défaut. Mode sombre forcé (pas "system") : reprend
        # la même palette que les pages web en thème sombre, cohérent
        # avec display.html qui reste lui aussi toujours sombre par choix
        # délibéré (voir docs/architecture.md).
        #
        # Part d'un thème intégré à customtkinter ("dark-blue" -- garanti
        # complet pour la version installée) plutôt qu'un JSON entièrement
        # personnalisé : un thème maison risque d'oublier une clé interne
        # que customtkinter s'attend à trouver (ex. `corner_radius` sur une
        # section qu'on ne pensait pas à fournir), faisant planter la
        # construction de la fenêtre -- déjà rencontré en pratique. Seules
        # les couleurs sont ensuite surchargées (voir _apply_brand_colors),
        # tout le reste (rayons, épaisseurs de bordure...) reste celui,
        # déjà testé, du thème intégré.
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        _apply_brand_colors()

        super().__init__()

        self.language = "fr"
        self.log_queue: queue.Queue[str] = queue.Queue()

        self.data_root = _data_root()
        self.app_web_dir = _app_web_dir()
        ensure_directories(self.data_root, self.app_web_dir)
        self.assets_dir = self.data_root / "web" / "assets"
        self.runtime = ServerRuntime(
            str(self.app_web_dir), str(self.assets_dir), HTTP_PORT, WS_PORT
        )

        # Capte le journal d'accès HTTP (http.server écrit sur stderr) et
        # tout print() du reste de l'appli dans le widget de journal.
        sys.stdout = _QueueWriter(sys.stdout, self.log_queue)
        sys.stderr = _QueueWriter(sys.stderr, self.log_queue)

        self.title(self._t("title"))
        self.geometry("820x600")
        self.minsize(640, 480)
        self.protocol("WM_DELETE_WINDOW", self._on_quit)

        self._build_ui()
        self._poll_log_queue()
        self._start_server()

    # -- traductions ---------------------------------------------------

    def _t(self, key: str, **kwargs) -> str:
        text = _TRANSLATIONS[self.language].get(key, key)
        return text.format(**kwargs) if kwargs else text

    # -- construction de l'interface -------------------------------------

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, corner_radius=0)
        header.pack(fill="x")

        ctk.CTkLabel(header, text="FletchTime", font=ctk.CTkFont(size=22, weight="bold")).pack(
            side="left", padx=(16, 4), pady=12
        )

        ctk.CTkLabel(
            header,
            text=f"v{__version__}",
            font=ctk.CTkFont(size=13),
            text_color="gray60",
        ).pack(side="left", padx=(0, 16), pady=12)

        self.lang_menu = ctk.CTkOptionMenu(
            header, values=["FR", "EN"], width=70, command=self._on_language_change
        )
        self.lang_menu.set("FR")
        self.lang_menu.pack(side="right", padx=16, pady=12)

        # -- statut + démarrer/arrêter --------------------------------
        status_frame = ctk.CTkFrame(self)
        status_frame.pack(fill="x", padx=16, pady=(16, 8))

        self.status_dot = ctk.CTkLabel(
            status_frame, text="●", text_color="gray50", font=ctk.CTkFont(size=18)
        )
        self.status_dot.pack(side="left", padx=(12, 4), pady=10)

        self.status_label = ctk.CTkLabel(status_frame, text=self._t("status_stopped"))
        self.status_label.pack(side="left", padx=(0, 12), pady=10)

        self.start_button = ctk.CTkButton(
            status_frame, text=self._t("start"), width=100, command=self._start_server
        )
        self.start_button.pack(side="right", padx=(4, 12), pady=10)

        self.stop_button = ctk.CTkButton(
            status_frame,
            text=self._t("stop"),
            width=100,
            command=self._stop_server,
            fg_color="#b3401f",
            hover_color="#8f3119",
        )
        self.stop_button.pack(side="right", padx=4, pady=10)

        # -- liens rapides -------------------------------------------
        links_frame = ctk.CTkFrame(self)
        links_frame.pack(fill="x", padx=16, pady=8)

        self.home_button = ctk.CTkButton(
            links_frame, text=self._t("home"), command=lambda: self._open_link("/")
        )
        self.home_button.pack(side="left", padx=12, pady=10, expand=True, fill="x")

        self.control_button = ctk.CTkButton(
            links_frame,
            text=self._t("control"),
            command=lambda: self._open_link("/control.html"),
        )
        self.control_button.pack(side="left", padx=(0, 12), pady=10, expand=True, fill="x")

        self.display_button = ctk.CTkButton(
            links_frame,
            text=self._t("display"),
            command=lambda: self._open_link("/display.html?lane=1"),
        )
        self.display_button.pack(side="left", padx=(0, 12), pady=10, expand=True, fill="x")

        # -- journal ----------------------------------------------------
        self.log_label = ctk.CTkLabel(self, text=self._t("log_title"), anchor="w")
        self.log_label.pack(fill="x", padx=20, pady=(8, 0))

        self.log_box = ctk.CTkTextbox(self, font=ctk.CTkFont(family="monospace", size=11))
        self.log_box.pack(fill="both", expand=True, padx=16, pady=(4, 8))
        self.log_box.configure(state="disabled")

        # -- pied de page -------------------------------------------------
        self.footer_label = ctk.CTkLabel(
            self,
            text=f"{self._t('club_data')} {self.data_root}",
            font=ctk.CTkFont(size=11),
            text_color="gray60",
            anchor="w",
        )
        self.footer_label.pack(fill="x", padx=20, pady=(0, 10))

        self.quit_button = ctk.CTkButton(
            self,
            text=self._t("quit"),
            command=self._on_quit,
            fg_color="transparent",
            border_width=1,
        )
        self.quit_button.pack(padx=16, pady=(0, 12))

    # -- actions ---------------------------------------------------------

    def _open_link(self, path: str) -> None:
        webbrowser.open(f"http://127.0.0.1:{HTTP_PORT}{path}")

    def _start_server(self) -> None:
        if self.runtime.is_running:
            return
        self.runtime.start()
        self._refresh_status()

    def _stop_server(self) -> None:
        if not self.runtime.is_running:
            return
        self.runtime.stop()
        self._refresh_status()

    def _refresh_status(self) -> None:
        if self.runtime.is_running:
            self.status_dot.configure(text_color="#2fb344")
            self.status_label.configure(text=self._t("status_running", ip=local_ip()))
        else:
            self.status_dot.configure(text_color="gray50")
            self.status_label.configure(text=self._t("status_stopped"))

    def _on_language_change(self, value: str) -> None:
        self.language = value.lower()
        self.title(self._t("title"))
        self.start_button.configure(text=self._t("start"))
        self.stop_button.configure(text=self._t("stop"))
        self.home_button.configure(text=self._t("home"))
        self.control_button.configure(text=self._t("control"))
        self.display_button.configure(text=self._t("display"))
        self.log_label.configure(text=self._t("log_title"))
        self.quit_button.configure(text=self._t("quit"))
        self.footer_label.configure(text=f"{self._t('club_data')} {self.data_root}")
        self._refresh_status()

    def _on_quit(self) -> None:
        self.runtime.stop()
        self.destroy()

    # -- journal (file thread-safe -> widget) ------------------------------

    def _poll_log_queue(self) -> None:
        try:
            while True:
                line = self.log_queue.get_nowait()
                self.log_box.configure(state="normal")
                self.log_box.insert("end", line + "\n")
                self.log_box.see("end")
                self.log_box.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(200, self._poll_log_queue)


def run_gui() -> None:
    _hide_console_on_windows()
    app = None
    try:
        app = FletchTimeApp()
        app.mainloop()
    except Exception:
        # Si la construction de la fenêtre échoue après que le serveur ait
        # déjà démarré (voir FletchTimeApp.__init__, qui appelle
        # _start_server() en toute fin de construction), l'arrêter ici
        # évite qu'un appelant qui retombe sur le mode terminal (voir
        # fletchtime.__main__.main) ne se heurte à un port déjà occupé.
        if app is not None:
            try:
                app.runtime.stop()
            except Exception:
                pass
        raise


def _hide_console_on_windows() -> None:
    """Meilleur effort, sans conséquence si ça échoue : masque la fenêtre
    console une fois la fenêtre graphique prête à s'afficher.

    On la garde volontairement visible (voir ``fletchtime.spec``,
    ``console=True``) plutôt que de la supprimer complètement à la
    construction : si ce module échoue à s'importer (ex. `customtkinter`
    cassé), ``fletchtime.__main__.main`` retombe sur le mode terminal --
    sans console du tout, ce repli serait invisible et le DOS n'aurait
    aucun moyen de savoir si le serveur tourne réellement. Cacher la
    console seulement APRÈS un lancement réussi de la fenêtre donne le
    meilleur des deux : rendu soigné quand tout va bien, filet de sécurité
    visible sinon."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:
        pass
