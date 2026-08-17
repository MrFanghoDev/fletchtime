"""Fenêtre graphique du serveur -- remplace le terminal comme point
d'entrée principal sur toutes les plateformes (PC et Pydroid), voir
``fletchtime.__main__.main`` qui bascule ici par défaut (et retombe sur le
mode terminal si ce module ne peut pas être importé, ex. `customtkinter`
absent).

Panneau latéral gauche avec un bouton par écran (Accueil, Affichage,
Réseau, Statut technique, Journal), qui bascule la zone de contenu --
même principe que ``fletchscore/gui/app.py::afficher_section`` (voir
issue #7, convergence de navigation entre les deux outils). Le journal
et le statut technique sont alimentés en continu par des threads
d'arrière-plan indépendamment de l'écran affiché (voir ``self.log_lines``/
``self.tech_status_data``) : passer d'un écran à l'autre ne perd jamais
ces données, seul le widget qui les affiche est détruit/reconstruit.

Le serveur (HTTP + WebSocket, voir ``fletchtime.runtime.ServerRuntime``)
démarre automatiquement à l'ouverture de la fenêtre, avec des boutons pour
l'arrêter/le relancer sans fermer l'application. Le journal affiché est une
redirection de stdout/stderr (voir ``_QueueWriter``) : capte aussi bien le
journal d'accès HTTP (``http.server`` écrit sur stderr) que n'importe quel
``print()`` du reste de l'appli, sans avoir à instrumenter chaque site
d'appel.

```{warning}
Le rendu du panneau latéral (customtkinter) a été vérifié visuellement via
Xvfb (voir CLAUDE.md global, section Environnement), redimensionnement
compris -- pas encore sur un vrai poste ni sur Pydroid. La logique de
démarrage/arrêt du serveur qu'elle pilote (``ServerRuntime``) est, elle,
testée sans affichage (voir tests/test_runtime.py).
```
"""

from __future__ import annotations

import json
import logging
import queue
import signal
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

import customtkinter as ctk
from PIL import Image

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

SECTIONS = ["accueil", "affichage", "reseau", "statut_technique", "journal", "aide"]

# Mêmes icônes que la vue web (theme.css, boutons .theme-btn) et que le
# sélecteur de thème de FletchScore (gui/app.py::ICONES_THEME, issue #49)
# -- reprises telles quelles ici (issue #15) pour remplacer le dropdown
# texte "Système"/"Clair"/"Sombre" d'avant, qui devait être retraduit à
# chaque changement de langue.
ICONES_THEME = {"system": "◐", "light": "☀", "dark": "☾"}
_THEME_PAR_ICONE = {icone: theme for theme, icone in ICONES_THEME.items()}

# Même fichier que celui utilisé comme icône de fletchtime.spec -- pas de
# nouvel asset à ajouter, seulement "*.ico" au package-data pip (voir
# pyproject.toml, absent jusqu'ici -- déjà embarqué par PyInstaller, qui
# prend tout web/ sans filtre, contrairement à pip). PIL charge un .ico
# directement (plusieurs résolutions internes, dont un 256x256 RGBA propre).
CHEMIN_LOGO = Path(__file__).resolve().parent / "web" / "logo.ico"

_TRANSLATIONS = {
    "fr": {
        "title": "FletchTime -- Serveur",
        "start": "Démarrer",
        "stop": "Arrêter",
        "quit": "Quitter",
        "quitConfirmMessage": "Veux-tu vraiment quitter FletchTime ?",
        "quitConfirmServerNote": "Le serveur sera arrêté et tous les écrans connectés seront déconnectés.",
        "cancel": "Annuler",
        "homeWelcome": "Bienvenue sur FletchTime",
        "homeTagline": "Chronométrage open source pour compétitions d'archerie FFTL -- Indoor & Flint",
        "home": "Accueil",
        "control": "Contrôle",
        "display": "Affichage",
        "open": "Ouvrir",
        "network": "Réseau",
        "techStatusTitle": "Statut technique",
        "languageCaption": "Langue",
        "themeCaption": "Thème",
        "shortcutsTitle": "Accès rapide",
        "shortcutDisplayDesc": "Choisir la lane à ouvrir et couper le son avant de lancer l'écran",
        "shortcutNetworkDesc": "Modifier les ports HTTP/WebSocket du serveur",
        "shortcutTechDesc": "Voir les écrans connectés, le mode et la phase en cours",
        "shortcutLogDesc": "Consulter le journal de l'application",
        "shortcutHomeWeb": "Accueil ↗",
        "shortcutHomeWebDesc": "Ouvrir la page d'accueil web dans le navigateur",
        "shortcutControlWeb": "Contrôle ↗",
        "shortcutControlWebDesc": "Ouvrir le poste de contrôle dans le navigateur",
        "shortcutDisplayWeb": "Écran d'affichage ↗",
        "shortcutDisplayWebDesc": "Ouvrir l'écran d'affichage (lane 1) dans le navigateur",
        "help": "Aide",
        "helpIntro": "Ce résumé couvre l'essentiel. Pour le détail complet, consulte le manuel utilisateur :",
        "helpManualButton": "Ouvrir le manuel utilisateur",
        "helpHomeDesc": "Statut du serveur (démarré/arrêté), adresse à donner aux archers, et raccourcis vers les autres écrans et les pages web.",
        "helpDisplayDesc": "Choisis la lane à ouvrir et si le son doit être coupé, puis lance l'écran d'affichage dans le navigateur.",
        "helpNetworkDesc": "Modifie les ports HTTP/WebSocket du serveur -- utile pour faire tourner plusieurs salles de compétition sur le même PC.",
        "helpTechDesc": "Écrans connectés, mode actif, phase en cours, pack de sons, mot de passe configuré ou non.",
        "helpLogDesc": "Historique des commandes reçues, connexions/déconnexions et erreurs -- utile pour comprendre après coup ce qui s'est passé.",
        "status_stopped": "Serveur arrêté",
        "status_running": "Serveur en cours -- {ip}",
        "log_title": "Journal",
        "club_data": "Données du club :",
        "addressCaption": "Adresse :",
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
        "quitConfirmMessage": "Do you really want to quit FletchTime?",
        "quitConfirmServerNote": "The server will stop and all connected screens will be disconnected.",
        "cancel": "Cancel",
        "homeWelcome": "Welcome to FletchTime",
        "homeTagline": "Open source timing software for FFTL archery competitions -- Indoor & Flint",
        "home": "Home",
        "control": "Control",
        "display": "Display",
        "open": "Open",
        "network": "Network",
        "techStatusTitle": "Technical status",
        "languageCaption": "Language",
        "themeCaption": "Theme",
        "shortcutsTitle": "Quick access",
        "shortcutDisplayDesc": "Choose the lane to open and mute before launching the display",
        "shortcutNetworkDesc": "Change the server's HTTP/WebSocket ports",
        "shortcutTechDesc": "See connected screens, active mode and phase",
        "shortcutLogDesc": "View the application log",
        "shortcutHomeWeb": "Home ↗",
        "shortcutHomeWebDesc": "Open the web home page in your browser",
        "shortcutControlWeb": "Control ↗",
        "shortcutControlWebDesc": "Open the control station in your browser",
        "shortcutDisplayWeb": "Display screen ↗",
        "shortcutDisplayWebDesc": "Open the display screen (lane 1) in your browser",
        "help": "Help",
        "helpIntro": "This summary covers the essentials. For full detail, see the user manual:",
        "helpManualButton": "Open the user manual",
        "helpHomeDesc": "Server status (started/stopped), address to share with archers, and shortcuts to the other screens and web pages.",
        "helpDisplayDesc": "Choose which lane to open and whether to mute it, then launch the display screen in your browser.",
        "helpNetworkDesc": "Change the server's HTTP/WebSocket ports -- useful for running several competition rooms on the same PC.",
        "helpTechDesc": "Connected screens, active mode, current phase, sound pack, whether a password is configured.",
        "helpLogDesc": "History of received commands, connections/disconnections and errors -- useful to understand what happened afterwards.",
        "status_stopped": "Server stopped",
        "status_running": "Server running -- {ip}",
        "log_title": "Log",
        "club_data": "Club data:",
        "addressCaption": "Address:",
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
        # moins conforme à la charte graphique, jamais un plantage au
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

        self.language = gui_config["language"]
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.status_queue: queue.Queue = queue.Queue()
        # Sources de vérité pour le journal et le statut technique --
        # alimentées en continu (voir _poll_log_queue/_drain_status_queue)
        # indépendamment de l'écran affiché. Les widgets qui les montrent
        # (self.log_box, self.tech_status_label) sont détruits/recréés à
        # chaque changement d'écran (voir afficher_section) : None quand
        # leur écran n'est pas actif, auquel cas seules ces données-ci
        # sont mises à jour.
        self.log_lines: list[str] = []
        self.tech_status_data: dict | None = None
        self.section_active = "accueil"

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
        # Taille fixe raisonnable plutôt que calculée dynamiquement depuis
        # le contenu construit (ancienne approche, pensée pour un unique
        # panneau qui empilait tout) : avec un panneau latéral + écrans,
        # un seul écran est visible à la fois, donc la taille "naturelle"
        # du contenu construit au départ (Accueil) ne dit rien de la
        # taille dont les autres écrans (Réseau, Statut technique) auront
        # besoin. Mêmes valeurs que FletchScore, pour la cohérence.
        self.geometry("1100x700")
        self.minsize(900, 600)
        self.protocol("WM_DELETE_WINDOW", self._on_quit)

        self._build_ui()

        self._poll_log_queue()
        self._poll_technical_status()
        self._drain_status_queue()
        self._start_server()

    # -- traductions ---------------------------------------------------

    def _t(self, key: str, **kwargs) -> str:
        text = _TRANSLATIONS[self.language].get(key, key)
        return text.format(**kwargs) if kwargs else text

    def _libelle_section(self, cle: str) -> str:
        return {
            "accueil": self._t("home"),
            "affichage": self._t("display"),
            "reseau": self._t("network"),
            "statut_technique": self._t("techStatusTitle"),
            "journal": self._t("log_title"),
            "aide": self._t("help"),
        }[cle]

    # -- construction de l'interface -------------------------------------

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._construire_barre_laterale()
        self._construire_zone_contenu()
        self.afficher_section(self.section_active)

    def _construire_barre_laterale(self) -> None:
        self.barre_laterale = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.barre_laterale.grid(row=0, column=0, sticky="nsew")

        ligne = 0
        entete = ctk.CTkFrame(self.barre_laterale, fg_color="transparent")
        entete.grid(row=ligne, column=0, padx=20, pady=(20, 10))

        image_logo = ctk.CTkImage(
            light_image=Image.open(CHEMIN_LOGO), dark_image=Image.open(CHEMIN_LOGO), size=(28, 28)
        )
        ctk.CTkLabel(entete, image=image_logo, text="").pack(side="left", padx=(0, 8))
        ctk.CTkLabel(entete, text="FletchTime", font=ctk.CTkFont(size=20, weight="bold")).pack(
            side="left"
        )
        ligne += 1

        # Indicateur de statut serveur -- toujours présent dans le
        # panneau latéral (jamais détruit/reconstruit, contrairement aux
        # écrans), pour rester visible quel que soit l'écran affiché.
        # L'écran Accueil a en plus sa propre version complète avec les
        # boutons démarrer/arrêter (voir _construire_ecran_accueil).
        cadre_statut = ctk.CTkFrame(self.barre_laterale, fg_color="transparent")
        cadre_statut.grid(row=ligne, column=0, padx=20, pady=(0, 15), sticky="w")
        self.barre_status_dot = ctk.CTkLabel(
            cadre_statut, text="●", text_color="gray50", font=ctk.CTkFont(size=13)
        )
        self.barre_status_dot.pack(side="left")
        self.barre_status_label = ctk.CTkLabel(
            cadre_statut, text=self._t("status_stopped"), font=ctk.CTkFont(size=11)
        )
        self.barre_status_label.pack(side="left", padx=(5, 0))
        ligne += 1

        self.boutons_sections: dict[str, ctk.CTkButton] = {}
        for cle in SECTIONS:
            bouton = ctk.CTkButton(
                self.barre_laterale,
                text=self._libelle_section(cle),
                anchor="w",
                command=lambda c=cle: self.afficher_section(c),
            )
            bouton.grid(row=ligne, column=0, padx=20, pady=6, sticky="ew")
            self.boutons_sections[cle] = bouton
            ligne += 1

        # Ligne vide qui absorbe tout l'espace restant -- pousse langue/
        # thème/quitter/version en bas du panneau, même mécanisme que
        # FletchScore (gui/app.py::_construire_barre_laterale).
        self.barre_laterale.grid_rowconfigure(ligne, weight=1)
        ligne += 1

        self.langue_caption = ctk.CTkLabel(self.barre_laterale, text=self._t("languageCaption"))
        self.langue_caption.grid(row=ligne, column=0, padx=20, pady=(10, 0), sticky="w")
        ligne += 1
        self.segment_langue = ctk.CTkSegmentedButton(
            self.barre_laterale, values=["FR", "EN"], command=self._on_language_change
        )
        self.segment_langue.set(self.language.upper())
        self.segment_langue.grid(row=ligne, column=0, padx=20, pady=(5, 10), sticky="ew")
        ligne += 1

        self.theme_caption = ctk.CTkLabel(self.barre_laterale, text=self._t("themeCaption"))
        self.theme_caption.grid(row=ligne, column=0, padx=20, pady=(0, 0), sticky="w")
        ligne += 1
        self.segment_theme = ctk.CTkSegmentedButton(
            self.barre_laterale,
            values=list(ICONES_THEME.values()),
            command=self._on_theme_change,
        )
        self.segment_theme.set(ICONES_THEME[self.theme])
        self.segment_theme.grid(row=ligne, column=0, padx=20, pady=(5, 15), sticky="ew")
        ligne += 1

        self.quit_button = ctk.CTkButton(
            self.barre_laterale,
            text=self._t("quit"),
            command=self._on_quit,
            fg_color="#3a4354",
            hover_color="#4a5568",
        )
        self.quit_button.grid(row=ligne, column=0, padx=20, pady=(0, 15), sticky="ew")
        ligne += 1

        ctk.CTkLabel(
            self.barre_laterale,
            text=f"v{__version__}",
            font=ctk.CTkFont(size=11),
            text_color="gray60",
        ).grid(row=ligne, column=0, padx=20, pady=(0, 10), sticky="w")

    def _construire_zone_contenu(self) -> None:
        self.zone_contenu = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.zone_contenu.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.zone_contenu.grid_columnconfigure(0, weight=1)
        self.zone_contenu.grid_rowconfigure(1, weight=1)

        self.titre_section = ctk.CTkLabel(
            self.zone_contenu, text="", font=ctk.CTkFont(size=24, weight="bold")
        )
        self.titre_section.grid(row=0, column=0, sticky="w", pady=(0, 15))

        self.cadre_section = ctk.CTkFrame(self.zone_contenu, fg_color="transparent")
        self.cadre_section.grid(row=1, column=0, sticky="nsew")

    # -- navigation --------------------------------------------------------

    def afficher_section(self, cle: str) -> None:
        self.section_active = cle
        for widget in self.cadre_section.winfo_children():
            widget.destroy()

        # Ne valent que pour l'écran qui vient d'être détruit -- remis à
        # None avant de reconstruire, pour que les threads d'arrière-plan
        # (journal, statut technique, statut serveur) sachent qu'ils
        # doivent seulement mettre à jour leurs données, pas un widget
        # qui n'existe plus.
        self.log_box = None
        self.tech_status_label = None
        self.status_dot = None
        self.status_label = None
        self.address_entry = None
        self.network_status_label = None

        self.titre_section.configure(text=self._libelle_section(cle))

        if cle == "accueil":
            self._construire_ecran_accueil(self.cadre_section)
        elif cle == "affichage":
            self._construire_ecran_affichage(self.cadre_section)
        elif cle == "reseau":
            self._construire_ecran_reseau(self.cadre_section)
        elif cle == "statut_technique":
            self._construire_ecran_statut_technique(self.cadre_section)
        elif cle == "journal":
            self._construire_ecran_journal(self.cadre_section)
        elif cle == "aide":
            self._construire_ecran_aide(self.cadre_section)
        else:
            raise ValueError(f"Section inconnue : {cle}")

    # -- écran Accueil : statut, démarrer/arrêter, adresse, liens rapides --

    def _construire_ecran_accueil(self, parent: ctk.CTkBaseClass) -> None:
        # Même formule que fletchscore/gui/ecran_accueil.py::_construire_bienvenue
        # (titre + tagline courte) -- la tagline reprend mot pour mot celle
        # déjà utilisée sur la page web (web/i18n.js::homeTagline), pas de
        # nouveau texte inventé. Dupliquée plutôt que partagée (aucune
        # infrastructure commune entre i18n.js et _TRANSLATIONS ici) -- à
        # garder synchronisée si le texte change d'un côté.
        ctk.CTkLabel(
            parent, text=self._t("homeWelcome"), font=ctk.CTkFont(size=22, weight="bold")
        ).pack(anchor="w", pady=(0, 5))
        ctk.CTkLabel(parent, text=self._t("homeTagline"), text_color="gray60").pack(
            anchor="w", pady=(0, 15)
        )

        statut_frame = ctk.CTkFrame(parent)
        statut_frame.pack(fill="x", pady=(0, 8))

        self.status_dot = ctk.CTkLabel(statut_frame, text="●", font=ctk.CTkFont(size=18))
        self.status_dot.pack(side="left", padx=(12, 4), pady=10)

        self.status_label = ctk.CTkLabel(statut_frame, text=self._t("status_stopped"))
        self.status_label.pack(side="left", padx=(0, 12), pady=10)

        self.start_button = ctk.CTkButton(
            statut_frame, text=self._t("start"), width=100, command=self._start_server
        )
        self.start_button.pack(side="right", padx=(4, 12), pady=10)

        self.stop_button = ctk.CTkButton(
            statut_frame,
            text=self._t("stop"),
            width=100,
            command=self._stop_server,
            fg_color="#b3401f",
            hover_color="#8f3119",
        )
        self.stop_button.pack(side="right", padx=4, pady=10)

        # -- adresse du serveur -----------------------------------------
        # CTkEntry (désactivée après affichage) plutôt qu'un simple
        # libellé : l'intention est de permettre de sélectionner/copier
        # l'adresse (utile pour la retaper à la main sur un appareil sans
        # bouton de raccourci, ex. un téléphone d'archer) -- non vérifié
        # visuellement si "disabled" préserve la sélection de texte sur
        # toutes les plateformes ; à confirmer en conditions réelles.
        address_frame = ctk.CTkFrame(parent)
        address_frame.pack(fill="x", pady=(0, 8))

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

        self._construire_raccourcis(parent)

        self.footer_label = ctk.CTkLabel(
            parent,
            text=f"{self._t('club_data')} {self.data_root}",
            font=ctk.CTkFont(size=11),
            text_color="gray60",
            anchor="w",
        )
        self.footer_label.pack(fill="x", pady=(8, 0))

        self._refresh_status()

    def _construire_raccourcis(self, parent: ctk.CTkBaseClass) -> None:
        """Grille de raccourcis façon FletchScore (gui/ecran_accueil.py::
        _RACCOURCIS) -- une carte par destination, titre + description
        courte. Mélange volontairement deux natures de destination :
        écrans internes (reste dans l'appli) et pages web (ouvre le
        navigateur) -- distingués par une couleur différente et un
        suffixe "↗" sur les cartes web, pour ne jamais laisser croire
        qu'un clic va rester dans la fenêtre alors qu'il l'ouvre ailleurs
        (voir issue #9)."""
        ctk.CTkLabel(
            parent, text=self._t("shortcutsTitle"), font=ctk.CTkFont(size=14, weight="bold")
        ).pack(fill="x", pady=(8, 10), anchor="w")

        cadre = ctk.CTkFrame(parent, fg_color="transparent")
        cadre.pack(fill="x")
        cadre.grid_columnconfigure((0, 1), weight=1)

        raccourcis = [
            (
                self._libelle_section("affichage"),
                self._t("shortcutDisplayDesc"),
                lambda: self.afficher_section("affichage"),
                False,
            ),
            (
                self._libelle_section("reseau"),
                self._t("shortcutNetworkDesc"),
                lambda: self.afficher_section("reseau"),
                False,
            ),
            (
                self._libelle_section("statut_technique"),
                self._t("shortcutTechDesc"),
                lambda: self.afficher_section("statut_technique"),
                False,
            ),
            (
                self._libelle_section("journal"),
                self._t("shortcutLogDesc"),
                lambda: self.afficher_section("journal"),
                False,
            ),
            (
                self._t("shortcutHomeWeb"),
                self._t("shortcutHomeWebDesc"),
                lambda: self._open_link("/"),
                True,
            ),
            (
                self._t("shortcutControlWeb"),
                self._t("shortcutControlWebDesc"),
                lambda: self._open_link("/control.html"),
                True,
            ),
            (
                self._t("shortcutDisplayWeb"),
                self._t("shortcutDisplayWebDesc"),
                lambda: self._open_link("/display.html?lane=1"),
                True,
            ),
        ]

        for index, (titre, description, commande, web) in enumerate(raccourcis):
            kwargs = {}
            if web:
                # Même bleu que CTkOptionMenu (voir _apply_brand_colors) --
                # réutilise un langage de couleur déjà présent dans l'appli
                # ("bleu = interactif/sort de l'appli") plutôt que
                # d'inventer une nouvelle couleur.
                kwargs["fg_color"] = ("#3357bf", "#4c7bdb")
            bouton = ctk.CTkButton(
                cadre, text=f"{titre}\n{description}", height=60, command=commande, **kwargs
            )
            bouton.grid(
                row=index // 2,
                column=index % 2,
                sticky="ew",
                padx=(0, 10) if index % 2 == 0 else 0,
                pady=(0, 10),
            )

    # -- écran Affichage : lane à ouvrir, muet, bouton Ouvrir ---------------

    def _construire_ecran_affichage(self, parent: ctk.CTkBaseClass) -> None:
        cadre = ctk.CTkFrame(parent)
        cadre.pack(fill="x")

        ctk.CTkLabel(
            cadre,
            text=self._t("displayOptionsCaption"),
            font=ctk.CTkFont(size=11),
            text_color="gray60",
        ).pack(side="left", padx=(12, 8), pady=12)

        self.lane_entry = ctk.CTkEntry(cadre, width=90, justify="center")
        self.lane_entry.insert(0, "1")
        self.lane_entry.pack(side="left", padx=(0, 12), pady=12)

        self.mute_checkbox = ctk.CTkCheckBox(cadre, text=self._t("muteLabel"), width=20)
        self.mute_checkbox.pack(side="left", padx=(0, 12), pady=12)

        ctk.CTkButton(cadre, text=self._t("open"), command=self._open_display).pack(
            side="left", padx=(0, 12), pady=12
        )

    # -- écran Réseau : ports HTTP/WS ---------------------------------------

    def _construire_ecran_reseau(self, parent: ctk.CTkBaseClass) -> None:
        # Ports modifiables plutôt que figés : permet de faire tourner
        # plusieurs salles de compétition sur le même PC -- une copie de
        # dossier par salle, chacune avec des ports différents (voir
        # config/gui.toml, config_store). Changer un port ici redémarre
        # le serveur automatiquement s'il tournait déjà, pour que le
        # changement prenne effet immédiatement (voir _on_apply_network).
        cadre = ctk.CTkFrame(parent)
        cadre.pack(fill="x")

        self.network_caption = ctk.CTkLabel(
            cadre,
            text=self._t("networkCaption"),
            font=ctk.CTkFont(size=11),
            text_color="gray60",
        )
        self.network_caption.pack(side="left", padx=(12, 8), pady=12)

        self.http_port_entry = ctk.CTkEntry(cadre, width=70, justify="center")
        self.http_port_entry.insert(0, str(self.http_port))
        self.http_port_entry.pack(side="left", padx=(0, 4), pady=12)

        ctk.CTkLabel(cadre, text="/", text_color="gray60").pack(side="left", padx=2, pady=12)

        self.ws_port_entry = ctk.CTkEntry(cadre, width=70, justify="center")
        self.ws_port_entry.insert(0, str(self.ws_port))
        self.ws_port_entry.pack(side="left", padx=(4, 12), pady=12)

        self.network_apply_button = ctk.CTkButton(
            cadre, text=self._t("apply"), width=90, command=self._on_apply_network
        )
        self.network_apply_button.pack(side="left", padx=(0, 8), pady=12)

        self.network_status_label = ctk.CTkLabel(cadre, text="", text_color="gray60")
        self.network_status_label.pack(side="left", padx=(4, 12), pady=12, fill="x", expand=True)

    # -- écran Statut technique : mêmes données que /api/status -----------

    def _construire_ecran_statut_technique(self, parent: ctk.CTkBaseClass) -> None:
        self.tech_status_label = ctk.CTkLabel(
            parent, text=self._texte_statut_technique(), anchor="w", justify="left"
        )
        self.tech_status_label.pack(fill="x", padx=4, pady=8)

    def _texte_statut_technique(self) -> str:
        data = self.tech_status_data
        if not data or not data.get("available"):
            return self._t("techStatusUnavailable")
        lanes = ", ".join(data["connected_lanes"]) or self._t("techStatusNoLanes")
        mode = data["active_mode"] or self._t("techStatusNoMode")
        phase = data["match_phase"] or "--"
        return (
            f"{self._t('techStatusClients')} {data['connected_clients']}\n"
            f"{self._t('techStatusLanes')} {lanes}\n"
            f"{self._t('techStatusMode')} {mode}\n"
            f"{self._t('techStatusPhase')} {phase}\n"
            f"{self._t('techStatusSound')} {data['sound_pack']}\n"
            f"{self._t('techStatusAuth')} "
            f"{self._t('yes') if data['password_configured'] else self._t('no')}"
        )

    # -- écran Journal : sortie standard capturée --------------------------

    def _construire_ecran_journal(self, parent: ctk.CTkBaseClass) -> None:
        self.log_box = ctk.CTkTextbox(parent, font=ctk.CTkFont(family="monospace", size=11))
        self.log_box.pack(fill="both", expand=True)
        self.log_box.configure(state="normal")
        # Une ligne à la fois, chacune suivie d'un saut de ligne -- même
        # motif que _poll_log_queue (voir plus bas) pour la mise à jour en
        # direct, sinon la toute première ligne ajoutée en direct après
        # cette construction se retrouve collée à la dernière ligne
        # historique (pas de saut de ligne final sur un "\n".join(...)).
        for ligne in self.log_lines:
            self.log_box.insert("end", ligne + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # -- écran Aide : résumé rapide par écran + lien vers le manuel --------

    def _construire_ecran_aide(self, parent: ctk.CTkBaseClass) -> None:
        """Sur le modèle de fletchscore/gui/ecran_aide.py -- lien vers la
        doc complète en haut, puis un résumé (titre + description courte)
        par écran. Lien vers manual.html (déjà existant, niveau
        utilisateur) plutôt que la doc développeur publiée -- plus proche
        de ce que cherche un bénévole non-technique en pleine compétition
        (voir issue #11)."""
        cadre_lien = ctk.CTkFrame(parent)
        cadre_lien.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(cadre_lien, text=self._t("helpIntro"), wraplength=500, justify="left").pack(
            anchor="w", padx=15, pady=(15, 5)
        )

        ctk.CTkButton(
            cadre_lien,
            text=self._t("helpManualButton"),
            command=lambda: self._open_link("/manual.html"),
        ).pack(anchor="w", padx=15, pady=(0, 15))

        zone = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        zone.pack(fill="both", expand=True)

        sections_aide = [
            ("accueil", "helpHomeDesc"),
            ("affichage", "helpDisplayDesc"),
            ("reseau", "helpNetworkDesc"),
            ("statut_technique", "helpTechDesc"),
            ("journal", "helpLogDesc"),
        ]
        for index, (cle, cle_texte) in enumerate(sections_aide):
            ctk.CTkLabel(
                zone,
                text=self._libelle_section(cle),
                font=ctk.CTkFont(size=15, weight="bold"),
                anchor="w",
            ).pack(fill="x", pady=(10 if index else 0, 2))
            ctk.CTkLabel(
                zone, text=self._t(cle_texte), wraplength=500, justify="left", anchor="w"
            ).pack(fill="x")

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
        running = self.runtime.is_running
        couleur = "#2fb344" if running else "gray50"
        texte = self._t("status_running", ip=local_ip()) if running else self._t("status_stopped")

        self.barre_status_dot.configure(text_color=couleur)
        self.barre_status_label.configure(text=texte)

        if self.status_dot is not None:
            self.status_dot.configure(text_color=couleur)
        if self.status_label is not None:
            self.status_label.configure(text=texte)
        self._refresh_address()

    def _refresh_address(self) -> None:
        """L'adresse ne dépend pas de si le serveur tourne réellement --
        affichée dans tous les cas (utile même à l'arrêt, pour préparer
        la config réseau à l'avance sur un autre appareil). Seulement si
        l'écran Accueil est actif -- self.address_entry est None sinon."""
        if self.address_entry is None:
            return
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
        config_store.save_gui_config({"language": self.language})
        self.title(self._t("title"))
        for cle, bouton in self.boutons_sections.items():
            bouton.configure(text=self._libelle_section(cle))
        self.langue_caption.configure(text=self._t("languageCaption"))
        self.theme_caption.configure(text=self._t("themeCaption"))
        self.quit_button.configure(text=self._t("quit"))
        # Reconstruit l'écran actif pour retraduire tout son contenu --
        # plus simple et plus sûr que de retrouver et reconfigurer
        # individuellement chaque widget d'un écran qui pourrait ne même
        # pas être l'écran actuellement affiché.
        self.afficher_section(self.section_active)

    def _on_theme_change(self, icone: str) -> None:
        theme = _THEME_PAR_ICONE[icone]
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
        if not self._confirm_quit():
            return
        self.runtime.stop()
        self.destroy()

    def _confirm_quit(self) -> bool:
        """Popup de confirmation -- évite une fermeture accidentelle (clic
        malheureux sur « Quitter » ou sur la croix de la fenêtre) alors
        qu'un concours est en cours et des écrans connectés."""
        result = {"ok": False}

        dialog = ctk.CTkToplevel(self)
        dialog.title(self._t("quit"))
        dialog.geometry("340x160")
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

        message = self._t("quitConfirmMessage")
        if self.runtime.is_running:
            message += "\n\n" + self._t("quitConfirmServerNote")
        ctk.CTkLabel(dialog, text=message, wraplength=300, justify="left").pack(
            padx=20, pady=(20, 15)
        )

        def confirm() -> None:
            result["ok"] = True
            dialog.destroy()

        buttons_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons_frame.pack(pady=10)
        ctk.CTkButton(buttons_frame, text=self._t("quit"), fg_color="gray40", command=confirm).pack(
            side="left", padx=5
        )
        ctk.CTkButton(buttons_frame, text=self._t("cancel"), command=dialog.destroy).pack(
            side="left", padx=5
        )

        dialog.transient(self)
        dialog.after(50, dialog.grab_set)
        self.wait_window(dialog)
        return result["ok"]

    # -- journal (file thread-safe -> buffer, + widget si l'écran est actif) --

    def _poll_log_queue(self) -> None:
        try:
            while True:
                line = self.log_queue.get_nowait()
                self.log_lines.append(line)
                if self.log_box is not None:
                    self.log_box.configure(state="normal")
                    self.log_box.insert("end", line + "\n")
                    self.log_box.see("end")
                    self.log_box.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(200, self._poll_log_queue)

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
        self.tech_status_data = data
        if self.tech_status_label is not None:
            self.tech_status_label.configure(text=self._texte_statut_technique())


def run_gui() -> None:
    _hide_console_on_windows()
    app = None
    try:
        app = FletchTimeApp()

        # Ctrl+C/kill doivent fermer proprement même pendant une boucle Tk
        # imbriquée (wait_window() d'une popup modale, ex. confirmation de
        # fermeture) -- sans ce gestionnaire explicite, le KeyboardInterrupt
        # par défaut de Python n'est pas délivré de façon fiable tant
        # qu'une boucle modale est active, laissant le process pendu
        # jusqu'à un kill -9 (bug réel observé -- popup de confirmation
        # ajoutée sans ce filet). Même modèle que FletchScore (voir
        # gui/robustesse.py::construire_gestionnaire_arret côté ce
        # dépôt frère) : appelle destroy() directement, qui casse aussi
        # bien la boucle principale qu'une boucle modale imbriquée.
        def _gestionnaire_arret(signum: int, frame: object) -> None:
            print("\nFletchTime interrompu -- fermeture propre en cours...")
            app.destroy()

        for signal_gere in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(signal_gere, _gestionnaire_arret)
            except (ValueError, OSError, AttributeError):
                # ValueError : pas dans le thread principal.
                # OSError/AttributeError : signal non disponible sur cette
                # plateforme (ex. SIGTERM a un support limité sous Windows).
                # Ctrl+C reste rattrapé en dernier recours par le
                # KeyboardInterrupt par défaut de Python.
                pass

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
