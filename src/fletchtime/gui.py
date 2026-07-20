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

import json
import logging
import queue
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

import customtkinter as ctk

from fletchtime import __version__
from fletchtime.__main__ import (
    _app_web_dir,
    _data_root,
    ensure_directories,
    local_ip,
)
from fletchtime.logging_setup import configure_logging
from fletchtime.runtime import ServerRuntime
from fletchtime.server import config_store

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
        "addressCaption": "Adresse :",
        "themeSystem": "Système",
        "themeLight": "Clair",
        "themeDark": "Sombre",
        "networkCaption": "Ports (HTTP/WS) :",
        "displayOptionsCaption": "Lane à ouvrir :",
        "muteLabel": "Muet",
        "apply": "Appliquer",
        "networkErrorNotANumber": "Les ports doivent être des nombres",
        "networkErrorRange": "Les ports doivent être entre 1 et 65535",
        "networkErrorSame": "Les deux ports doivent être différents",
        "networkApplied": "Appliqué",
        "techStatusUnavailable": "Statut technique : indisponible (serveur en cours de démarrage ?)",
        "techStatusClients": "Clients connectés :",
        "techStatusLanes": "Écrans :",
        "techStatusNoLanes": "aucun",
        "techStatusMode": "Mode :",
        "techStatusNoMode": "aucun",
        "techStatusPhase": "Phase :",
        "techStatusSound": "Sons :",
        "techStatusAuth": "Mot de passe :",
        "yes": "oui",
        "no": "non",
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
        "addressCaption": "Address:",
        "themeSystem": "System",
        "themeLight": "Light",
        "themeDark": "Dark",
        "networkCaption": "Ports (HTTP/WS):",
        "displayOptionsCaption": "Lane to open:",
        "muteLabel": "Muted",
        "apply": "Apply",
        "networkErrorNotANumber": "Ports must be numbers",
        "networkErrorRange": "Ports must be between 1 and 65535",
        "networkErrorSame": "Both ports must be different",
        "networkApplied": "Applied",
        "techStatusUnavailable": "Technical status: unavailable (server starting?)",
        "techStatusClients": "Connected clients:",
        "techStatusLanes": "Screens:",
        "techStatusNoLanes": "none",
        "techStatusMode": "Mode:",
        "techStatusNoMode": "none",
        "techStatusPhase": "Phase:",
        "techStatusSound": "Sounds:",
        "techStatusAuth": "Password:",
        "yes": "yes",
        "no": "no",
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
        # le thème par défaut.
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
        #
        # Thème choisi par la personne qui lance la fenêtre (voir
        # config/gui.toml, config_store.load_gui_config) -- "system" par
        # défaut, qui suit le thème du système d'exploitation (sauf sous
        # Linux, limitation connue de customtkinter -- retombe sur
        # "light"). Indépendant de display.html, qui reste lui, par choix
        # délibéré, toujours sombre (voir docs/architecture.md) : l'écran
        # vu par les archers et la fenêtre de contrôle du responsable du
        # chronométrage sont deux préoccupations distinctes.
        gui_config = config_store.load_gui_config()
        self.theme = gui_config["theme"]
        self.http_port = gui_config["http_port"]
        self.ws_port = gui_config["ws_port"]
        ctk.set_appearance_mode(self.theme)
        ctk.set_default_color_theme("dark-blue")
        _apply_brand_colors()

        super().__init__()

        self.language = "fr"
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.status_queue: queue.Queue = queue.Queue()

        self.data_root = _data_root()
        self.app_web_dir = _app_web_dir()
        ensure_directories(self.data_root, self.app_web_dir)
        self.assets_dir = self.data_root / "web" / "assets"
        self.runtime = ServerRuntime(
            str(self.app_web_dir), str(self.assets_dir), self.http_port, self.ws_port
        )

        # Capte le journal d'accès HTTP (http.server écrit sur stderr) et
        # tout print() du reste de l'appli dans le widget de journal.
        sys.stdout = _QueueWriter(sys.stdout, self.log_queue)
        sys.stderr = _QueueWriter(sys.stderr, self.log_queue)

        # Appelé APRÈS la redirection ci-dessus, volontairement : le
        # StreamHandler créé par configure_logging() se lie au sys.stderr
        # courant au moment de sa création -- fait après le remplacement,
        # les journaux applicatifs (commandes reçues, pertes de connexion,
        # transitions...) apparaissent donc aussi dans le widget de
        # journal de la fenêtre, pas seulement dans le fichier persistant.
        #
        # console_level=INFO explicite, pas le défaut (WARNING, pensé
        # pour un terminal silencieux par défaut -- voir
        # fletchtime.__main__, -v/--verbose) : sans ce paramètre, le
        # widget de journal de la fenêtre restait silencieux en usage
        # normal, puisque tous les journaux applicatifs sont à INFO --
        # exactement l'inverse de ce que ce widget est censé montrer.
        self.log_file = configure_logging(self.data_root / "logs", console_level=logging.INFO)

        self.title(self._t("title"))
        self.geometry("820x600")  # taille de départ -- corrigée juste après
        self.minsize(640, 480)
        self.protocol("WM_DELETE_WINDOW", self._on_quit)

        self._build_ui()

        # La taille de départ ci-dessus datait d'avant l'ajout de plusieurs
        # sections (ports, statut technique...) -- trop petite pour tout
        # montrer, le bouton Quitter se retrouvant hors de la fenêtre
        # visible (constaté en pratique). Plutôt que de deviner un nouveau
        # nombre fixe qui redeviendrait insuffisant à la prochaine section
        # ajoutée, calcule la taille réellement nécessaire à partir du
        # contenu construit juste au-dessus : update_idletasks() force
        # Tkinter à calculer la taille demandée par chaque widget avant
        # qu'on ne la lise, sans quoi winfo_reqheight/reqwidth
        # renverraient une valeur pas encore à jour.
        self.update_idletasks()
        required_width = max(820, self.winfo_reqwidth())
        required_height = max(600, self.winfo_reqheight())
        self.geometry(f"{required_width}x{required_height}")
        # Empêche aussi de redescendre en dessous de cette taille par un
        # redimensionnement manuel -- le bouton Quitter (et tout le reste)
        # doit rester accessible sans avoir à agrandir la fenêtre.
        self.minsize(required_width, required_height)

        self._poll_log_queue()
        self._poll_technical_status()
        self._drain_status_queue()
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

        self.theme_menu = ctk.CTkOptionMenu(
            header,
            values=[self._t("themeSystem"), self._t("themeLight"), self._t("themeDark")],
            width=110,
            command=self._on_theme_change,
        )
        self.theme_menu.set(self._theme_label(self.theme))
        self.theme_menu.pack(side="right", padx=(0, 8), pady=12)

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
            command=self._open_display,
        )
        self.display_button.pack(side="left", padx=(0, 12), pady=10, expand=True, fill="x")

        # -- options d'affichage (lane à ouvrir, muet ou non) --------------
        # Auparavant un simple raccourci vers lane=1 -- rendu configurable
        # pour pouvoir ouvrir n'importe quelle lane et couper le son sur cet
        # onglet précis (voir display.html, soundEnabled) directement
        # depuis la fenêtre, comme c'est déjà possible depuis la page
        # d'accueil.
        display_options_frame = ctk.CTkFrame(self)
        display_options_frame.pack(fill="x", padx=16, pady=(0, 8))

        self.display_options_caption = ctk.CTkLabel(
            display_options_frame,
            text=self._t("displayOptionsCaption"),
            font=ctk.CTkFont(size=11),
            text_color="gray60",
        )
        self.display_options_caption.pack(side="left", padx=(12, 8), pady=8)

        self.lane_entry = ctk.CTkEntry(display_options_frame, width=90, justify="center")
        self.lane_entry.insert(0, "1")
        self.lane_entry.pack(side="left", padx=(0, 12), pady=8)

        self.mute_checkbox = ctk.CTkCheckBox(
            display_options_frame, text=self._t("muteLabel"), width=20
        )
        self.mute_checkbox.pack(side="left", padx=(0, 12), pady=8)

        # -- adresse du serveur -----------------------------------------
        # CTkEntry (désactivée après affichage) plutôt qu'un simple
        # libellé : l'intention est de permettre de sélectionner/copier
        # l'adresse (utile pour la retaper à la main sur un appareil sans
        # bouton de raccourci, ex. un téléphone d'archer) -- non vérifié
        # visuellement si "disabled" préserve la sélection de texte sur
        # toutes les plateformes ; à confirmer en conditions réelles.
        address_frame = ctk.CTkFrame(self)
        address_frame.pack(fill="x", padx=16, pady=(0, 8))

        self.address_caption = ctk.CTkLabel(
            address_frame,
            text=self._t("addressCaption"),
            font=ctk.CTkFont(size=11),
            text_color="gray60",
        )
        self.address_caption.pack(side="left", padx=(12, 8), pady=8)

        self.address_entry = ctk.CTkEntry(
            address_frame, font=ctk.CTkFont(family="monospace", size=12)
        )
        self.address_entry.pack(side="left", padx=(0, 12), pady=8, expand=True, fill="x")

        # -- réseau (ports) -----------------------------------------------
        # Ports modifiables plutôt que figés : permet de faire tourner
        # plusieurs salles de compétition sur le même PC -- une copie de
        # dossier par salle, chacune avec des ports différents (voir
        # config/gui.toml, config_store). Changer un port ici redémarre le
        # serveur automatiquement s'il tournait déjà, pour que le
        # changement prenne effet immédiatement (voir _on_apply_network).
        network_frame = ctk.CTkFrame(self)
        network_frame.pack(fill="x", padx=16, pady=(0, 8))

        self.network_caption = ctk.CTkLabel(
            network_frame,
            text=self._t("networkCaption"),
            font=ctk.CTkFont(size=11),
            text_color="gray60",
        )
        self.network_caption.pack(side="left", padx=(12, 8), pady=8)

        self.http_port_entry = ctk.CTkEntry(network_frame, width=70, justify="center")
        self.http_port_entry.insert(0, str(self.http_port))
        self.http_port_entry.pack(side="left", padx=(0, 4), pady=8)

        self.network_separator = ctk.CTkLabel(network_frame, text="/", text_color="gray60")
        self.network_separator.pack(side="left", padx=2, pady=8)

        self.ws_port_entry = ctk.CTkEntry(network_frame, width=70, justify="center")
        self.ws_port_entry.insert(0, str(self.ws_port))
        self.ws_port_entry.pack(side="left", padx=(4, 12), pady=8)

        self.network_apply_button = ctk.CTkButton(
            network_frame, text=self._t("apply"), width=90, command=self._on_apply_network
        )
        self.network_apply_button.pack(side="left", padx=(0, 8), pady=8)

        self.network_status_label = ctk.CTkLabel(network_frame, text="", text_color="gray60")
        self.network_status_label.pack(side="left", padx=(4, 12), pady=8, fill="x", expand=True)

        # -- statut technique ---------------------------------------------
        # Les mêmes données techniques que celles déjà affichées dans la
        # page de contrôle (écrans connectés, mode actif...), lues via
        # /api/status -- voir _poll_technical_status ci-dessous, et
        # fletchtime.server.http_static._DualRootHandler._build_status_body
        # côté serveur.
        tech_frame = ctk.CTkFrame(self)
        tech_frame.pack(fill="x", padx=16, pady=(0, 8))

        self.tech_status_label = ctk.CTkLabel(
            tech_frame, text=self._t("techStatusUnavailable"), anchor="w", justify="left"
        )
        self.tech_status_label.pack(fill="x", padx=12, pady=8)

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
            fg_color="#3a4354",
            hover_color="#4a5568",
        )
        self.quit_button.pack(padx=16, pady=(0, 12))

    # -- actions ---------------------------------------------------------

    def _open_link(self, path: str) -> None:
        webbrowser.open(f"http://127.0.0.1:{self.http_port}{path}")

    def _open_display(self) -> None:
        lane = self.lane_entry.get().strip() or "1"
        path = f"/display.html?lane={urllib.parse.quote(lane)}"
        if self.mute_checkbox.get():
            path += "&mute=1"
        self._open_link(path)

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
        self._refresh_address()

    def _refresh_address(self) -> None:
        """L'adresse ne dépend pas de si le serveur tourne réellement --
        affichée dans tous les cas (utile même à l'arrêt, pour préparer
        la config réseau à l'avance sur un autre appareil)."""
        address = f"http://{local_ip()}:{self.http_port}/"
        # CTkEntry ne supporte que "normal"/"disabled" (contrairement à
        # ttk.Entry, qui a un vrai état "readonly") -- il faut donc la
        # débloquer temporairement pour la mettre à jour, puis la
        # reverrouiller aussitôt après.
        self.address_entry.configure(state="normal")
        self.address_entry.delete(0, "end")
        self.address_entry.insert(0, address)
        self.address_entry.configure(state="disabled")

    def _on_language_change(self, value: str) -> None:
        self.language = value.lower()
        self.title(self._t("title"))
        self.start_button.configure(text=self._t("start"))
        self.stop_button.configure(text=self._t("stop"))
        self.home_button.configure(text=self._t("home"))
        self.control_button.configure(text=self._t("control"))
        self.display_button.configure(text=self._t("display"))
        self.display_options_caption.configure(text=self._t("displayOptionsCaption"))
        self.mute_checkbox.configure(text=self._t("muteLabel"))
        self.address_caption.configure(text=self._t("addressCaption"))
        self.log_label.configure(text=self._t("log_title"))
        self.quit_button.configure(text=self._t("quit"))
        self.footer_label.configure(text=f"{self._t('club_data')} {self.data_root}")
        # Les valeurs du menu de thème sont des libellés traduits (pas des
        # codes internes comme "FR"/"EN") -- il faut donc reconstruire la
        # liste ET repositionner la sélection sur le thème actuel, pas
        # juste changer le texte d'un widget existant.
        self.theme_menu.configure(
            values=[self._t("themeSystem"), self._t("themeLight"), self._t("themeDark")]
        )
        self.theme_menu.set(self._theme_label(self.theme))
        self.network_caption.configure(text=self._t("networkCaption"))
        self.network_apply_button.configure(text=self._t("apply"))
        self._refresh_status()

    def _theme_label(self, theme: str) -> str:
        return {
            "system": self._t("themeSystem"),
            "light": self._t("themeLight"),
            "dark": self._t("themeDark"),
        }.get(theme, self._t("themeSystem"))

    def _on_theme_change(self, label: str) -> None:
        reverse = {
            self._t("themeSystem"): "system",
            self._t("themeLight"): "light",
            self._t("themeDark"): "dark",
        }
        theme = reverse.get(label, "system")
        self.theme = theme
        ctk.set_appearance_mode(theme)
        config_store.save_gui_config({"theme": theme})

    def _on_apply_network(self) -> None:
        """Change les ports HTTP/WebSocket -- reconstruit ServerRuntime
        avec les nouvelles valeurs (les ports sont figés à la
        construction, voir fletchtime.runtime.ServerRuntime) et
        redémarre automatiquement si le serveur tournait déjà, pour que
        le changement prenne effet tout de suite plutôt que de laisser
        la fenêtre dans un état incohérent (ports affichés différents de
        ceux réellement utilisés par le serveur en cours)."""
        try:
            http_port = int(self.http_port_entry.get())
            ws_port = int(self.ws_port_entry.get())
        except ValueError:
            self.network_status_label.configure(
                text=self._t("networkErrorNotANumber"), text_color="#d6534a"
            )
            return

        if not (1 <= http_port <= 65535) or not (1 <= ws_port <= 65535):
            self.network_status_label.configure(
                text=self._t("networkErrorRange"), text_color="#d6534a"
            )
            return
        if http_port == ws_port:
            self.network_status_label.configure(
                text=self._t("networkErrorSame"), text_color="#d6534a"
            )
            return

        try:
            config_store.save_gui_config({"http_port": http_port, "ws_port": ws_port})
        except ValueError:
            # Filet de sécurité seulement -- les cas attendus sont déjà
            # couverts par les vérifications ci-dessus, donc ce chemin ne
            # devrait normalement jamais s'exécuter.
            self.network_status_label.configure(
                text=self._t("networkErrorRange"), text_color="#d6534a"
            )
            return

        was_running = self.runtime.is_running
        if was_running:
            self.runtime.stop()

        self.http_port = http_port
        self.ws_port = ws_port
        self.runtime = ServerRuntime(
            str(self.app_web_dir), str(self.assets_dir), self.http_port, self.ws_port
        )
        if was_running:
            self.runtime.start()

        self.network_status_label.configure(text=self._t("networkApplied"), text_color="#2fb344")
        self._refresh_status()

    def _on_quit(self) -> None:
        self.runtime.stop()
        self.destroy()

    # -- journal (file thread-safe -> widget) ------------------------------

    # -- statut technique (thread séparé pour la requête HTTP -> file) -----

    def _poll_technical_status(self) -> None:
        # Une requête HTTP, même locale, peut mettre du temps à répondre
        # (serveur qui démarre, port qui change...) -- jamais faite
        # directement depuis le thread principal (gèlerait la fenêtre le
        # temps de la requête). Un thread par sondage, plutôt qu'un seul
        # thread persistant : plus simple, et chaque requête se termine en
        # quelques millisecondes en pratique (même machine).
        threading.Thread(target=self._fetch_technical_status, daemon=True).start()
        self.after(2000, self._poll_technical_status)

    def _fetch_technical_status(self) -> None:
        # Tourne dans un thread séparé -- ne touche JAMAIS un widget
        # Tkinter directement ici (pas thread-safe) ; pousse seulement le
        # résultat dans une file, lue depuis le thread principal via
        # _drain_status_queue, exactement comme le journal (self.log_queue).
        try:
            url = f"http://127.0.0.1:{self.http_port}/api/status"
            with urllib.request.urlopen(url, timeout=2) as res:
                data = json.loads(res.read())
        except (urllib.error.URLError, OSError, ValueError):
            # Serveur pas encore démarré, port en cours de changement,
            # réponse invalide... -- affiche juste "indisponible", jamais
            # une exception qui remonterait jusqu'au thread principal.
            data = None
        self.status_queue.put(data)

    def _drain_status_queue(self) -> None:
        try:
            while True:
                data = self.status_queue.get_nowait()
                self._render_technical_status(data)
        except queue.Empty:
            pass
        self.after(200, self._drain_status_queue)

    def _render_technical_status(self, data: dict | None) -> None:
        if not data or not data.get("available"):
            self.tech_status_label.configure(text=self._t("techStatusUnavailable"))
            return
        lanes = ", ".join(data["connected_lanes"]) or self._t("techStatusNoLanes")
        mode = data["active_mode"] or self._t("techStatusNoMode")
        phase = data["match_phase"] or "--"
        text = (
            f"{self._t('techStatusClients')} {data['connected_clients']}  |  "
            f"{self._t('techStatusLanes')} {lanes}  |  "
            f"{self._t('techStatusMode')} {mode}  |  "
            f"{self._t('techStatusPhase')} {phase}  |  "
            f"{self._t('techStatusSound')} {data['sound_pack']}  |  "
            f"{self._t('techStatusAuth')} "
            f"{self._t('yes') if data['password_configured'] else self._t('no')}"
        )
        self.tech_status_label.configure(text=text)

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
