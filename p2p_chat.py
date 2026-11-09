#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        CYBERCHAT P2P - ÉDITION VERT/ROUGE                     ║
║                     Messagerie pair-à-pair via IP publique                    ║
║                                                                               ║
║  Auteur  : hackestchad                                                        ║
║  Version : 3.0.0                                                              ║
║  Licence : MIT                                                                ║
╚══════════════════════════════════════════════════════════════════════════════╝

Ce script permet à deux (ou plusieurs) personnes de discuter en direct via leurs
adresses IP publiques ou locales. Chaque utilisateur possède un profil complet
(photo, pseudo, statut, couleur) et peut héberger son propre serveur ou se
connecter à celui d'un ami, d'un frère ou d'un proche.

⚠️  IMPORTANT SECURITÉ  ⚠️
- N'exposez votre IP publique qu'à des personnes de confiance.
- Ouvrez le port choisi (par défaut 5050) sur votre routeur si vous utilisez
  votre IP publique.
- Activez le chiffrement optionnel via AES dans les paramètres.
"""

import os
import sys
import json
import base64
import socket
import threading
import datetime
import time
import random
import string
import hashlib
import ipaddress
import webbrowser
import logging
import tempfile
import shutil
import struct
import urllib.request
import urllib.error
from pathlib import Path
from io import BytesIO

# ───────────────────────────────────────────────────────────────────────────────
# GESTION DES DÉPENDANCES
# ───────────────────────────────────────────────────────────────────────────────
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog, scrolledtext, colorchooser
except ImportError as e:
    print("[ERREUR] Tkinter n'est pas installé sur ce système.")
    print("         Installez-le via votre gestionnaire de paquets.")
    sys.exit(1)

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFilter, ImageOps
except ImportError:
    print("[ERREUR] Pillow est requis : pip install pillow")
    sys.exit(1)

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("[AVERTISSEMENT] cryptography non installé : le chiffrement est désactivé.")

# ───────────────────────────────────────────────────────────────────────────────
# CONSTANTES GLOBALES
# ───────────────────────────────────────────────────────────────────────────────
APP_NAME = "CyberChat P2P"
APP_VERSION = "3.0.0"
APP_AUTHOR = "hackestchad"
DEFAULT_PORT = 5050
BUFFER_SIZE = 65536
SEPARATOR = "<|SEP|>"
ENCODING = "utf-8"
MAX_HISTORY = 500
PROFILE_VERSION = 2

# Thème cyber vert/rouge
THEME = {
    "bg_dark": "#0a0f0a",
    "bg_mid": "#0d1a0d",
    "bg_light": "#142614",
    "bg_input": "#1a2e1a",
    "green": "#00ff41",
    "green_dim": "#00cc33",
    "green_dark": "#008f11",
    "red": "#ff2a2a",
    "red_dim": "#cc2222",
    "red_dark": "#8f1111",
    "text": "#e8f5e8",
    "text_dim": "#8fb38f",
    "border": "#1f441f",
    "accent": "#00ff41",
    "online": "#00ff41",
    "offline": "#ff2a2a",
    "away": "#ffcc00",
    "font_mono": ("Consolas", 10),
    "font_ui": ("Segoe UI", 10),
    "font_title": ("Segoe UI", 14, "bold"),
    "font_small": ("Segoe UI", 8),
}

# ───────────────────────────────────────────────────────────────────────────────
# CONFIGURATION DES LOGS
# ───────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("CyberChat")

# ───────────────────────────────────────────────────────────────────────────────
# UTILITAIRES RÉSEAU
# ───────────────────────────────────────────────────────────────────────────────

def get_public_ip():
    """Récupère l'adresse IP publique de la connexion Internet."""
    services = [
        "https://api.ipify.org",
        "https://checkip.amazonaws.com",
        "https://icanhazip.com",
        "https://ident.me",
    ]
    for service in services:
        try:
            with urllib.request.urlopen(service, timeout=5) as response:
                ip = response.read().decode(ENCODING).strip()
                if ipaddress.ip_address(ip):
                    return ip
        except Exception as exc:
            logger.debug("Échec récupération IP via %s : %s", service, exc)
    return "Inconnue"


def get_local_ip():
    """Récupère l'IP locale de la machine."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.5)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def is_valid_ip(value):
    """Vérifie si une chaîne est une IPv4 ou IPv6 valide."""
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def is_valid_port(value):
    """Vérifie si un port est dans la plage autorisée."""
    try:
        port = int(value)
        return 1 <= port <= 65535
    except (ValueError, TypeError):
        return False


def generate_id():
    """Génère un identifiant unique alphanumérique."""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=16))


# ───────────────────────────────────────────────────────────────────────────────
# UTILITAIRES DE CHIFFREMENT (OPTIONNEL)
# ───────────────────────────────────────────────────────────────────────────────

def derive_key(password: str, salt: bytes = None):
    """Dérive une clé Fernet à partir d'un mot de passe."""
    if not CRYPTO_AVAILABLE:
        return None, None
    if salt is None:
        salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode(ENCODING)))
    return key, salt


def encrypt_message(password: str, message: str):
    """Chiffre un message avec le mot de passe partagé."""
    if not CRYPTO_AVAILABLE:
        return None
    key, salt = derive_key(password)
    fernet = Fernet(key)
    token = fernet.encrypt(message.encode(ENCODING))
    return base64.urlsafe_b64encode(salt + token).decode(ENCODING)


def decrypt_message(password: str, encrypted: str):
    """Déchiffre un message avec le mot de passe partagé."""
    if not CRYPTO_AVAILABLE:
        return None
    try:
        data = base64.urlsafe_b64decode(encrypted.encode(ENCODING))
        salt = data[:16]
        token = data[16:]
        key, _ = derive_key(password, salt)
        fernet = Fernet(key)
        return fernet.decrypt(token).decode(ENCODING)
    except Exception as exc:
        logger.error("Échec déchiffrement : %s", exc)
        return None


# ───────────────────────────────────────────────────────────────────────────────
# GESTIONNAIRE DE PROFILS
# ───────────────────────────────────────────────────────────────────────────────
class ProfileManager:
    """Gère la création, la sauvegarde et le chargement du profil utilisateur."""

    def __init__(self, directory=None):
        if directory is None:
            directory = Path.home() / ".cyberchat"
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.profile_file = self.directory / "profile.json"
        self.avatar_file = self.directory / "avatar.png"
        self.default_data = {
            "version": PROFILE_VERSION,
            "id": generate_id(),
            "nickname": "Anonyme",
            "status": "En ligne",
            "status_message": "Disponible pour discuter",
            "theme_color": "#00ff41",
            "font_scale": 1.0,
            "avatar": None,
            "language": "fr",
            "sound_enabled": True,
            "notifications": True,
            "encryption_enabled": False,
            "encryption_password": "",
            "history_enabled": True,
            "auto_accept_files": False,
            "public_ip_history": [],
            "friends": [],
        }
        self.data = self.load()

    def load(self):
        """Charge le profil depuis le disque ou crée un profil par défaut."""
        if self.profile_file.exists():
            try:
                with open(self.profile_file, "r", encoding=ENCODING) as f:
                    data = json.load(f)
                # Migration de version si nécessaire
                if data.get("version", 1) < PROFILE_VERSION:
                    data = self._migrate(data)
                return data
            except Exception as exc:
                logger.error("Impossible de charger le profil : %s", exc)
        return self.default_data.copy()

    def _migrate(self, data):
        """Migre un ancien profil vers le format actuel."""
        logger.info("Migration du profil version %s → %s", data.get("version", 1), PROFILE_VERSION)
        data.update({k: v for k, v in self.default_data.items() if k not in data})
        data["version"] = PROFILE_VERSION
        return data

    def save(self):
        """Sauvegarde le profil sur le disque."""
        try:
            with open(self.profile_file, "w", encoding=ENCODING) as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as exc:
            logger.error("Impossible de sauvegarder le profil : %s", exc)
            return False

    def set_avatar(self, image_path):
        """Copie et redimensionne une image de profil."""
        try:
            img = Image.open(image_path)
            img = img.convert("RGB")
            size = (256, 256)
            img.thumbnail(size, Image.Resampling.LANCZOS)
            # Créer un canvas carré avec fond
            canvas = Image.new("RGB", size, (10, 30, 10))
            offset = ((size[0] - img.width) // 2, (size[1] - img.height) // 2)
            canvas.paste(img, offset)
            canvas.save(self.avatar_file, "PNG")
            with open(self.avatar_file, "rb") as f:
                self.data["avatar"] = base64.b64encode(f.read()).decode(ENCODING)
            self.save()
            return True
        except Exception as exc:
            logger.error("Erreur lors de la mise à jour de l'avatar : %s", exc)
            return False

    def get_avatar_image(self, size=(64, 64)):
        """Retourne une PhotoImage Tkinter de l'avatar redimensionnée."""
        try:
            if self.data.get("avatar"):
                raw = base64.b64decode(self.data["avatar"])
                img = Image.open(BytesIO(raw))
            elif self.avatar_file.exists():
                img = Image.open(self.avatar_file)
            else:
                img = self._generate_default_avatar()
            img = img.convert("RGB")
            img = img.resize(size, Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception as exc:
            logger.error("Erreur chargement avatar : %s", exc)
            img = self._generate_default_avatar().resize(size, Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)

    def _generate_default_avatar(self):
        """Génère un avatar par défaut stylisé."""
        size = (256, 256)
        img = Image.new("RGB", size, THEME["bg_mid"])
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, size[0], size[1]], fill=THEME["bg_mid"], outline=THEME["green_dark"], width=4)
        draw.ellipse([48, 48, 208, 208], outline=THEME["green"], width=6)
        draw.text((128, 128), self.data.get("nickname", "?")[:1].upper(), fill=THEME["green"], anchor="mm")
        return img

    def add_friend(self, name, ip, port=DEFAULT_PORT, note=""):
        """Ajoute un ami à la liste des contacts."""
        friend = {
            "id": generate_id(),
            "name": name,
            "ip": ip,
            "port": int(port),
            "note": note,
            "added_at": datetime.datetime.now().isoformat(),
        }
        self.data["friends"].append(friend)
        self.save()
        return friend

    def remove_friend(self, friend_id):
        """Supprime un ami de la liste."""
        self.data["friends"] = [f for f in self.data["friends"] if f["id"] != friend_id]
        self.save()

    def update_profile(self, **kwargs):
        """Met à jour les champs du profil."""
        self.data.update(kwargs)
        self.save()

    def get_friend_by_id(self, friend_id):
        """Retourne un ami par son identifiant."""
        for friend in self.data.get("friends", []):
            if friend["id"] == friend_id:
                return friend
        return None


# ───────────────────────────────────────────────────────────────────────────────
# PROTOCOLE DE MESSAGES
# ───────────────────────────────────────────────────────────────────────────────
class MessageProtocol:
    """Définit les types de messages échangés sur le réseau."""

    HELLO = "HELLO"
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    FILE = "FILE"
    FILE_CHUNK = "FILE_CHUNK"
    FILE_END = "FILE_END"
    TYPING = "TYPING"
    STATUS = "STATUS"
    PING = "PING"
    PONG = "PONG"
    DISCONNECT = "DISCONNECT"
    ERROR = "ERROR"

    @staticmethod
    def encode(msg_type, payload, sender_id="", sender_name="", timestamp=None):
        """Encode un message au format JSON sur une seule ligne."""
        if timestamp is None:
            timestamp = datetime.datetime.now().isoformat()
        packet = {
            "type": msg_type,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "timestamp": timestamp,
            "payload": payload,
        }
        return json.dumps(packet, ensure_ascii=False).encode(ENCODING)

    @staticmethod
    def decode(data):
        """Décode un message JSON reçu."""
        try:
            return json.loads(data.decode(ENCODING))
        except Exception as exc:
            logger.error("Message malformé reçu : %s", exc)
            return None


# ───────────────────────────────────────────────────────────────────────────────
# TRANSFERT DE FICHIERS
# ───────────────────────────────────────────────────────────────────────────────
class FileTransfer:
    """Utilitaires de lecture/écriture de fichiers encodés en base64."""

    @staticmethod
    def read_file_b64(path):
        """Lit un fichier et retourne (nom, base64)."""
        try:
            with open(path, "rb") as f:
                data = f.read()
            filename = os.path.basename(path)
            return filename, base64.b64encode(data).decode(ENCODING)
        except Exception as exc:
            logger.error("Erreur lecture fichier %s : %s", path, exc)
            return None, None

    @staticmethod
    def save_file_b64(directory, filename, data_b64):
        """Sauvegarde un fichier encodé en base64 dans un répertoire."""
        try:
            directory = Path(directory)
            directory.mkdir(parents=True, exist_ok=True)
            safe_name = os.path.basename(filename)
            target = directory / safe_name
            counter = 1
            while target.exists():
                stem = Path(safe_name).stem
                suffix = Path(safe_name).suffix
                target = directory / f"{stem}_{counter}{suffix}"
                counter += 1
            with open(target, "wb") as f:
                f.write(base64.b64decode(data_b64.encode(ENCODING)))
            return target
        except Exception as exc:
            logger.error("Erreur sauvegarde fichier %s : %s", filename, exc)
            return None


# ───────────────────────────────────────────────────────────────────────────────
# SERVEUR P2P
# ───────────────────────────────────────────────────────────────────────────────
class P2PServer(threading.Thread):
    """Serveur TCP acceptant les connexions entrantes."""

    def __init__(self, app, port=DEFAULT_PORT):
        super().__init__(daemon=True)
        self.app = app
        self.port = port
        self.running = False
        self.socket = None
        self.clients = []
        self.lock = threading.Lock()

    def run(self):
        """Boucle principale du serveur."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(("0.0.0.0", self.port))
            self.socket.listen(10)
            self.running = True
            self.app.on_server_started(self.port)
            logger.info("Serveur démarré sur le port %s", self.port)

            while self.running:
                try:
                    self.socket.settimeout(1.0)
                    client_sock, client_addr = self.socket.accept()
                    handler = ClientHandler(self.app, client_sock, client_addr)
                    handler.start()
                    with self.lock:
                        self.clients.append(handler)
                    self.app.on_client_connected(handler)
                except socket.timeout:
                    continue
                except OSError:
                    break
        except Exception as exc:
            logger.error("Erreur serveur : %s", exc)
            self.app.on_server_error(str(exc))
        finally:
            self.running = False
            self.app.on_server_stopped()

    def stop(self):
        """Arrête le serveur proprement."""
        self.running = False
        with self.lock:
            for client in self.clients:
                client.stop()
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass


# ───────────────────────────────────────────────────────────────────────────────
# GESTIONNAIRE DE CLIENT CONNECTÉ
# ───────────────────────────────────────────────────────────────────────────────
class ClientHandler(threading.Thread):
    """Gère une connexion cliente entrante."""

    def __init__(self, app, sock, address):
        super().__init__(daemon=True)
        self.app = app
        self.sock = sock
        self.address = address
        self.remote_ip = address[0]
        self.remote_port = address[1]
        self.running = False
        self.peer_name = f"{self.remote_ip}:{self.remote_port}"
        self.authenticated = False
        self.buffer = b""

    def run(self):
        """Boucle de réception pour un client."""
        self.running = True
        try:
            self.sock.settimeout(None)
            while self.running:
                data = self.sock.recv(BUFFER_SIZE)
                if not data:
                    break
                self.buffer += data
                while b"\n" in self.buffer:
                    line, self.buffer = self.buffer.split(b"\n", 1)
                    self._process_line(line)
        except ConnectionResetError:
            logger.info("Connexion réinitialisée par %s", self.peer_name)
        except Exception as exc:
            logger.error("Erreur client handler %s : %s", self.peer_name, exc)
        finally:
            self.running = False
            self.app.on_client_disconnected(self)
            self._close_socket()

    def _process_line(self, line):
        """Traite une ligne de message reçue."""
        msg = MessageProtocol.decode(line)
        if not msg:
            return
        msg["_handler"] = self
        msg["direction"] = "incoming"
        self.app.handle_message(msg)

    def send(self, msg_type, payload, sender_id="", sender_name=""):
        """Envoie un message au client."""
        try:
            data = MessageProtocol.encode(msg_type, payload, sender_id, sender_name) + b"\n"
            self.sock.sendall(data)
            return True
        except Exception as exc:
            logger.error("Échec envoi vers %s : %s", self.peer_name, exc)
            return False

    def stop(self):
        """Arrête la connexion cliente."""
        self.running = False
        self._close_socket()

    def _close_socket(self):
        """Ferme le socket en toute sécurité."""
        try:
            self.sock.close()
        except Exception:
            pass


# ───────────────────────────────────────────────────────────────────────────────
# CLIENT P2P
# ───────────────────────────────────────────────────────────────────────────────
class P2PClient(threading.Thread):
    """Client TCP sortant vers un pair."""

    def __init__(self, app, ip, port):
        super().__init__(daemon=True)
        self.app = app
        self.ip = ip
        self.port = port
        self.sock = None
        self.running = False
        self.buffer = b""

    def run(self):
        """Tente de se connecter au pair puis écoute les messages."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((self.ip, self.port))
            self.sock.settimeout(None)
            self.running = True
            self.app.on_connection_success(self.ip, self.port)

            # Envoi du hello
            self.send(
                MessageProtocol.HELLO,
                {
                    "nickname": self.app.profile.data.get("nickname", "Anonyme"),
                    "status": self.app.profile.data.get("status", "En ligne"),
                    "status_message": self.app.profile.data.get("status_message", ""),
                    "id": self.app.profile.data.get("id", ""),
                },
                self.app.profile.data.get("id", ""),
                self.app.profile.data.get("nickname", "Anonyme"),
            )

            while self.running:
                data = self.sock.recv(BUFFER_SIZE)
                if not data:
                    break
                self.buffer += data
                while b"\n" in self.buffer:
                    line, self.buffer = self.buffer.split(b"\n", 1)
                    self._process_line(line)
        except Exception as exc:
            logger.error("Erreur connexion à %s:%s : %s", self.ip, self.port, exc)
            self.app.on_connection_error(self.ip, self.port, str(exc))
        finally:
            self.running = False
            self.app.on_disconnected(self.ip, self.port)
            self._close_socket()

    def _process_line(self, line):
        """Traite une ligne reçue du serveur pair."""
        msg = MessageProtocol.decode(line)
        if not msg:
            return
        msg["direction"] = "incoming"
        self.app.handle_message(msg)

    def send(self, msg_type, payload, sender_id="", sender_name=""):
        """Envoie un message au pair."""
        if not self.sock or not self.running:
            return False
        try:
            data = MessageProtocol.encode(msg_type, payload, sender_id, sender_name) + b"\n"
            self.sock.sendall(data)
            return True
        except Exception as exc:
            logger.error("Échec envoi vers %s:%s : %s", self.ip, self.port, exc)
            return False

    def stop(self):
        """Arrête le client."""
        self.running = False
        self._close_socket()

    def _close_socket(self):
        """Ferme le socket."""
        try:
            self.sock.close()
        except Exception:
            pass


# ───────────────────────────────────────────────────────────────────────────────
# NOTIFICATEUR SYSTÈME
# ───────────────────────────────────────────────────────────────────────────────
class Notifier:
    """Gère les notifications et effets sonores simples."""

    def __init__(self, profile):
        self.profile = profile
        self.last_notification = 0

    def notify(self, title, message):
        """Affiche une notification visuelle si activée."""
        if not self.profile.data.get("notifications", True):
            return
        now = time.time()
        if now - self.last_notification < 2:
            return
        self.last_notification = now
        try:
            # Notification simple via Tkinter si possible, sinon print
            pass
        except Exception:
            pass

    def play_sound(self):
        """Joue un bip système si activé."""
        if not self.profile.data.get("sound_enabled", True):
            return
        try:
            if sys.platform == "win32":
                import winsound
                winsound.MessageBeep()
            else:
                print("\a", end="")
        except Exception:
            pass


# ───────────────────────────────────────────────────────────────────────────────
# INTERFACE GRAPHIQUE PRINCIPALE
# ───────────────────────────────────────────────────────────────────────────────
class CyberChatApp:
    """Application principale CyberChat P2P."""

    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION} - par {APP_AUTHOR}")
        self.root.geometry("1100x750")
        self.root.configure(bg=THEME["bg_dark"])
        self.root.minsize(900, 600)

        # Données
        self.profile = ProfileManager()
        self.local_ip = get_local_ip()
        self.public_ip = get_public_ip()
        self.server = None
        self.connected_peers = {}
        self.outgoing_connections = {}
        self.message_history = []
        self.typing_timers = {}
        self.notifier = Notifier(self.profile)

        # Style global
        self._configure_styles()

        # UI
        self._build_menu()
        self._build_header()
        self._build_main_layout()
        self._build_footer()

        # Chargement
        self._load_profile_ui()
        self._refresh_friends_list()
        self._start_status_updater()
        self._add_system_message("Bienvenue dans CyberChat P2P. Démarrez votre serveur ou connectez-vous à un ami.", tag="success")

    def _configure_styles(self):
        """Configure les styles ttk."""
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TScrollbar", troughcolor=THEME["bg_dark"], background=THEME["green_dark"],
                        bordercolor=THEME["bg_dark"], arrowcolor=THEME["green"])

    # ── Menu ──────────────────────────────────────────────────────────────────
    def _build_menu(self):
        """Construit la barre de menu."""
        menubar = tk.Menu(self.root, bg=THEME["bg_mid"], fg=THEME["green"],
                          activebackground=THEME["green_dark"], activeforeground="white")
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0, bg=THEME["bg_mid"], fg=THEME["text"],
                            activebackground=THEME["green_dark"])
        file_menu.add_command(label="Nouvelle connexion", command=self._connect_to_peer)
        file_menu.add_command(label="Éditer le profil", command=self._open_profile_editor)
        file_menu.add_separator()
        file_menu.add_command(label="Quitter", command=self._on_close)
        menubar.add_cascade(label="Fichier", menu=file_menu)

        tools_menu = tk.Menu(menubar, tearoff=0, bg=THEME["bg_mid"], fg=THEME["text"],
                             activebackground=THEME["green_dark"])
        tools_menu.add_command(label="Paramètres avancés", command=self._open_settings)
        tools_menu.add_command(label="Tester un port", command=self._test_port_dialog)
        tools_menu.add_command(label="Afficher mon IP", command=self._show_ips)
        menubar.add_cascade(label="Outils", menu=tools_menu)

        help_menu = tk.Menu(menubar, tearoff=0, bg=THEME["bg_mid"], fg=THEME["text"],
                            activebackground=THEME["green_dark"])
        help_menu.add_command(label="Commandes slash", command=self._show_help)
        help_menu.add_command(label="À propos", command=self._show_about)
        menubar.add_cascade(label="Aide", menu=help_menu)

    # ── En-tête ───────────────────────────────────────────────────────────────
    def _build_header(self):
        """Construit l'en-tête avec les infos réseau et profil."""
        self.header = tk.Frame(self.root, bg=THEME["bg_mid"], height=90)
        self.header.pack(fill=tk.X, padx=5, pady=5)
        self.header.pack_propagate(False)

        # Avatar
        self.avatar_img = self.profile.get_avatar_image((70, 70))
        self.avatar_label = tk.Label(self.header, image=self.avatar_img, bg=THEME["bg_mid"],
                                     highlightbackground=THEME["green"], highlightthickness=2)
        self.avatar_label.pack(side=tk.LEFT, padx=10, pady=10)
        self.avatar_label.bind("<Button-1>", lambda e: self._upload_avatar())

        # Infos profil
        profile_frame = tk.Frame(self.header, bg=THEME["bg_mid"])
        profile_frame.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.Y)

        self.nickname_label = tk.Label(profile_frame, text=self.profile.data.get("nickname", "Anonyme"),
                                       bg=THEME["bg_mid"], fg=THEME["green"], font=("Segoe UI", 14, "bold"))
        self.nickname_label.pack(anchor=tk.W)

        self.status_msg_label = tk.Label(profile_frame, text=self.profile.data.get("status_message", ""),
                                         bg=THEME["bg_mid"], fg=THEME["text_dim"], font=THEME["font_small"])
        self.status_msg_label.pack(anchor=tk.W)

        self.status_label = tk.Label(profile_frame, text="● Hors ligne", bg=THEME["bg_mid"],
                                     fg=THEME["red"], font=("Segoe UI", 9, "bold"))
        self.status_label.pack(anchor=tk.W)

        # Bouton éditer profil
        tk.Button(self.header, text="✎ Profil", bg=THEME["green_dark"], fg="white",
                  command=self._open_profile_editor).pack(side=tk.RIGHT, padx=10, pady=10)

        # Informations IP
        ip_frame = tk.Frame(self.header, bg=THEME["bg_mid"])
        ip_frame.pack(side=tk.RIGHT, padx=20, pady=10)

        self.local_ip_label = tk.Label(ip_frame, text=f"IP Locale : {self.local_ip}",
                                       bg=THEME["bg_mid"], fg=THEME["text"], font=THEME["font_small"])
        self.local_ip_label.pack(anchor=tk.E)

        self.public_ip_label = tk.Label(ip_frame, text=f"IP Publique : {self.public_ip}",
                                        bg=THEME["bg_mid"], fg=THEME["green"], font=THEME["font_small"])
        self.public_ip_label.pack(anchor=tk.E)

    # ── Layout principal ──────────────────────────────────────────────────────
    def _build_main_layout(self):
        """Construit le panneau principal (amis + chat)."""
        main_frame = tk.Frame(self.root, bg=THEME["bg_dark"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Panneau gauche : amis et connexion
        left_frame = tk.Frame(main_frame, bg=THEME["bg_mid"], width=300)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left_frame.pack_propagate(False)

        # Section connexion rapide
        conn_frame = tk.LabelFrame(left_frame, text=" Connexion ", bg=THEME["bg_mid"],
                                   fg=THEME["green"], font=THEME["font_ui"])
        conn_frame.pack(fill=tk.X, padx=8, pady=8)

        tk.Label(conn_frame, text="IP du pair :", bg=THEME["bg_mid"], fg=THEME["text"],
                 font=THEME["font_small"]).pack(anchor=tk.W, padx=5, pady=(5, 0))
        self.target_ip_entry = tk.Entry(conn_frame, bg=THEME["bg_input"], fg=THEME["text"],
                                        insertbackground=THEME["green"])
        self.target_ip_entry.pack(fill=tk.X, padx=5, pady=2)

        tk.Label(conn_frame, text="Port :", bg=THEME["bg_mid"], fg=THEME["text"],
                 font=THEME["font_small"]).pack(anchor=tk.W, padx=5)
        self.target_port_entry = tk.Entry(conn_frame, bg=THEME["bg_input"], fg=THEME["text"],
                                          insertbackground=THEME["green"])
        self.target_port_entry.insert(0, str(DEFAULT_PORT))
        self.target_port_entry.pack(fill=tk.X, padx=5, pady=2)

        tk.Button(conn_frame, text="➤ Se connecter", bg=THEME["green_dark"], fg="white",
                  command=self._connect_to_peer).pack(fill=tk.X, padx=5, pady=5)

        # Section serveur
        server_frame = tk.LabelFrame(left_frame, text=" Mon serveur ", bg=THEME["bg_mid"],
                                     fg=THEME["green"], font=THEME["font_ui"])
        server_frame.pack(fill=tk.X, padx=8, pady=8)

        tk.Label(server_frame, text="Port d'écoute :", bg=THEME["bg_mid"], fg=THEME["text"],
                 font=THEME["font_small"]).pack(anchor=tk.W, padx=5, pady=(5, 0))
        self.port_entry = tk.Entry(server_frame, bg=THEME["bg_input"], fg=THEME["text"],
                                   insertbackground=THEME["green"])
        self.port_entry.insert(0, str(DEFAULT_PORT))
        self.port_entry.pack(fill=tk.X, padx=5, pady=2)

        self.server_btn = tk.Button(server_frame, text="▶ Démarrer mon serveur", bg=THEME["green_dark"],
                                    fg="white", command=self._toggle_server)
        self.server_btn.pack(fill=tk.X, padx=5, pady=5)

        # Liste d'amis
        friends_frame = tk.LabelFrame(left_frame, text=" Amis / Frères ", bg=THEME["bg_mid"],
                                      fg=THEME["green"], font=THEME["font_ui"])
        friends_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.friends_listbox = tk.Listbox(friends_frame, bg=THEME["bg_dark"], fg=THEME["text"],
                                          selectbackground=THEME["green_dark"], selectforeground="white",
                                          font=THEME["font_ui"], relief=tk.FLAT, highlightthickness=1,
                                          highlightbackground=THEME["green_dark"])
        self.friends_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.friends_listbox.bind("<Double-Button-1>", lambda e: self._connect_to_selected_friend())

        btn_frame = tk.Frame(friends_frame, bg=THEME["bg_mid"])
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Button(btn_frame, text="+ Ajouter", bg=THEME["green_dark"], fg="white",
                  command=self._add_friend_dialog).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        tk.Button(btn_frame, text="- Supprimer", bg=THEME["red_dark"], fg="white",
                  command=self._remove_selected_friend).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # Panneau droit : chat
        right_frame = tk.Frame(main_frame, bg=THEME["bg_dark"])
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Zone de chat
        chat_frame = tk.Frame(right_frame, bg=THEME["bg_dark"])
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.chat_text = tk.Text(chat_frame, bg=THEME["bg_dark"], fg=THEME["text"], wrap=tk.WORD,
                                 state=tk.DISABLED, font=THEME["font_mono"], relief=tk.FLAT,
                                 highlightthickness=1, highlightbackground=THEME["green_dark"],
                                 padx=10, pady=10)
        self.chat_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(chat_frame, command=self.chat_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_text.config(yscrollcommand=scrollbar.set)

        # Tags de couleur
        self.chat_text.tag_configure("timestamp", foreground=THEME["text_dim"], font=("Consolas", 9))
        self.chat_text.tag_configure("message", foreground=THEME["text"], font=THEME["font_mono"])
        self.chat_text.tag_configure("system", foreground=THEME["text_dim"], font=("Segoe UI", 9, "italic"))
        self.chat_text.tag_configure("success", foreground=THEME["green"], font=("Segoe UI", 9, "bold"))
        self.chat_text.tag_configure("error", foreground=THEME["red"], font=("Segoe UI", 9, "bold"))

        # Indicateur d'écriture
        self.typing_label = tk.Label(right_frame, text="", bg=THEME["bg_dark"],
                                     fg=THEME["green_dim"], font=THEME["font_small"])
        self.typing_label.pack(fill=tk.X, padx=5)

        # Zone de saisie
        input_frame = tk.Frame(right_frame, bg=THEME["bg_dark"])
        input_frame.pack(fill=tk.X, padx=5, pady=5)

        self.msg_entry = tk.Entry(input_frame, bg=THEME["bg_input"], fg=THEME["text"],
                                  insertbackground=THEME["green"], font=THEME["font_ui"],
                                  relief=tk.FLAT, highlightthickness=1,
                                  highlightbackground=THEME["green_dark"])
        self.msg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=6)
        self.msg_entry.bind("<Return>", lambda e: self._send_text_message())
        self.msg_entry.bind("<KeyRelease>", lambda e: self._on_typing())

        tk.Button(input_frame, text="Envoyer", bg=THEME["green_dark"], fg="white",
                  command=self._send_text_message).pack(side=tk.LEFT, padx=2)
        tk.Button(input_frame, text="📎 Fichier", bg=THEME["bg_light"], fg=THEME["green"],
                  command=self._send_file).pack(side=tk.LEFT, padx=2)
        tk.Button(input_frame, text="📷 Image", bg=THEME["bg_light"], fg=THEME["green"],
                  command=self._send_image).pack(side=tk.LEFT, padx=2)

    # ── Pied de page ──────────────────────────────────────────────────────────
    def _build_footer(self):
        """Construit la barre d'état inférieure."""
        footer = tk.Frame(self.root, bg=THEME["bg_mid"], height=25)
        footer.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=(0, 5))
        footer.pack_propagate(False)

        self.info_label = tk.Label(footer, text="Prêt", bg=THEME["bg_mid"], fg=THEME["text_dim"],
                                   font=THEME["font_small"], anchor=tk.W)
        self.info_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        self.author_label = tk.Label(footer, text=f"Auteur : {APP_AUTHOR} | v{APP_VERSION}",
                                     bg=THEME["bg_mid"], fg=THEME["green_dark"], font=THEME["font_small"])
        self.author_label.pack(side=tk.RIGHT, padx=10)

    # ── Chargement du profil ──────────────────────────────────────────────────
    def _load_profile_ui(self):
        """Met à jour l'interface avec les données du profil."""
        self.avatar_img = self.profile.get_avatar_image((70, 70))
        self.avatar_label.config(image=self.avatar_img)
        self.nickname_label.config(text=self.profile.data.get("nickname", "Anonyme"))
        self.status_msg_label.config(text=self.profile.data.get("status_message", ""))

    def _refresh_ips(self):
        """Rafraîchit les IPs affichées."""
        self.public_ip = get_public_ip()
        self.local_ip_label.config(text=f"IP Locale : {self.local_ip}")
        self.public_ip_label.config(text=f"IP Publique : {self.public_ip}")

    # ── Serveur ───────────────────────────────────────────────────────────────
    def _toggle_server(self):
        """Démarre ou arrête le serveur d'écoute."""
        if self.server and self.server.running:
            self.server.stop()
            self.server = None
            self.server_btn.config(text="▶ Démarrer mon serveur", bg=THEME["green_dark"])
            self._set_info("Serveur arrêté.")
        else:
            port_text = self.port_entry.get().strip()
            if not is_valid_port(port_text):
                messagebox.showerror("Port invalide", "Veuillez entrer un port entre 1 et 65535.")
                return
            port = int(port_text)
            self.server = P2PServer(self, port)
            self.server.start()
            self.server_btn.config(text="⏹ Arrêter mon serveur", bg=THEME["red_dark"])
            self._set_info(f"Démarrage du serveur sur le port {port}...")

    # ── Connexion à un pair ───────────────────────────────────────────────────
    def _connect_to_peer(self):
        """Se connecte à un pair via IP et port."""
        ip = self.target_ip_entry.get().strip()
        port_text = self.target_port_entry.get().strip()

        if not is_valid_ip(ip):
            messagebox.showerror("IP invalide", "Veuillez entrer une adresse IP valide.")
            return
        if not is_valid_port(port_text):
            messagebox.showerror("Port invalide", "Veuillez entrer un port valide.")
            return

        port = int(port_text)
        key = f"{ip}:{port}"
        if key in self.outgoing_connections and self.outgoing_connections[key].running:
            self._set_info("Vous êtes déjà connecté à ce pair.")
            return

        client = P2PClient(self, ip, port)
        self.outgoing_connections[key] = client
        client.start()
        self._set_info(f"Connexion à {ip}:{port} en cours...")

    def _connect_to_selected_friend(self):
        """Se connecte à l'ami sélectionné dans la liste."""
        selection = self.friends_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        friends = self.profile.data.get("friends", [])
        if index >= len(friends):
            return
        friend = friends[index]
        self.target_ip_entry.delete(0, tk.END)
        self.target_ip_entry.insert(0, friend["ip"])
        self.target_port_entry.delete(0, tk.END)
        self.target_port_entry.insert(0, str(friend["port"]))
        self._connect_to_peer()

    # ── Gestion des amis ──────────────────────────────────────────────────────
    def _refresh_friends_list(self):
        """Rafraîchit la liste des amis."""
        self.friends_listbox.delete(0, tk.END)
        for friend in self.profile.data.get("friends", []):
            display = f"{friend['name']} ({friend['ip']}:{friend['port']})"
            self.friends_listbox.insert(tk.END, display)

    def _add_friend_dialog(self):
        """Ouvre une boîte de dialogue pour ajouter un ami."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Ajouter un ami")
        dialog.configure(bg=THEME["bg_mid"])
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Nom :", bg=THEME["bg_mid"], fg=THEME["text"]).grid(row=0, column=0, padx=5, pady=5)
        name_entry = tk.Entry(dialog, bg=THEME["bg_input"], fg=THEME["text"], insertbackground=THEME["green"])
        name_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(dialog, text="IP :", bg=THEME["bg_mid"], fg=THEME["text"]).grid(row=1, column=0, padx=5, pady=5)
        ip_entry = tk.Entry(dialog, bg=THEME["bg_input"], fg=THEME["text"], insertbackground=THEME["green"])
        ip_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(dialog, text="Port :", bg=THEME["bg_mid"], fg=THEME["text"]).grid(row=2, column=0, padx=5, pady=5)
        port_entry = tk.Entry(dialog, bg=THEME["bg_input"], fg=THEME["text"], insertbackground=THEME["green"])
        port_entry.insert(0, str(DEFAULT_PORT))
        port_entry.grid(row=2, column=1, padx=5, pady=5)

        tk.Label(dialog, text="Note :", bg=THEME["bg_mid"], fg=THEME["text"]).grid(row=3, column=0, padx=5, pady=5)
        note_entry = tk.Entry(dialog, bg=THEME["bg_input"], fg=THEME["text"], insertbackground=THEME["green"])
        note_entry.grid(row=3, column=1, padx=5, pady=5)

        def save_friend():
            name = name_entry.get().strip()
            ip = ip_entry.get().strip()
            port = port_entry.get().strip()
            note = note_entry.get().strip()
            if not name or not is_valid_ip(ip) or not is_valid_port(port):
                messagebox.showerror("Champs invalides", "Vérifiez le nom, l'IP et le port.")
                return
            self.profile.add_friend(name, ip, int(port), note)
            self._refresh_friends_list()
            dialog.destroy()

        tk.Button(dialog, text="Ajouter", bg=THEME["green_dark"], fg="white",
                  command=save_friend).grid(row=4, column=0, columnspan=2, pady=10)

    def _remove_selected_friend(self):
        """Supprime l'ami sélectionné."""
        selection = self.friends_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        friends = self.profile.data.get("friends", [])
        if index < len(friends):
            if messagebox.askyesno("Confirmer", f"Supprimer {friends[index]['name']} ?"):
                self.profile.remove_friend(friends[index]["id"])
                self._refresh_friends_list()

    # ── Envoi de messages ─────────────────────────────────────────────────────
    def _send_text_message(self):
        """Envoie un message texte aux pairs connectés."""
        text = self.msg_entry.get().strip()
        if not text:
            return
        self.msg_entry.delete(0, tk.END)

        if text.startswith("/"):
            self._handle_command(text)
            return

        encrypted = None
        if self.profile.data.get("encryption_enabled") and self.profile.data.get("encryption_password"):
            encrypted = encrypt_message(self.profile.data["encryption_password"], text)

        payload = {
            "text": text,
            "encrypted": encrypted,
            "color": self.profile.data.get("theme_color", THEME["green"]),
        }
        self._broadcast(MessageProtocol.TEXT, payload)
        self._add_message_to_chat(
            self.profile.data.get("nickname", "Moi"),
            text,
            "self",
            datetime.datetime.now(),
        )

    def _handle_command(self, text):
        """Gère les commandes spéciales commençant par /."""
        parts = text.split()
        command = parts[0].lower()
        if command == "/aide":
            self._add_system_message("Commandes : /aide /statut /nom /ip /clear /quit /image")
        elif command == "/clear":
            self.chat_text.config(state=tk.NORMAL)
            self.chat_text.delete("1.0", tk.END)
            self.chat_text.config(state=tk.DISABLED)
        elif command == "/ip":
            self._add_system_message(f"Locale : {self.local_ip} | Publique : {self.public_ip}")
        elif command == "/quit":
            self._on_close()
        elif command == "/statut" and len(parts) > 1:
            new_status = " ".join(parts[1:])
            self.profile.update_profile(status_message=new_status)
            self.status_msg_label.config(text=new_status)
            self._broadcast(MessageProtocol.STATUS, {"status": "En ligne", "status_message": new_status})
            self._add_system_message(f"Statut mis à jour : {new_status}")
        elif command == "/nom" and len(parts) > 1:
            new_name = " ".join(parts[1:])
            self.profile.update_profile(nickname=new_name)
            self.nickname_label.config(text=new_name)
            self._add_system_message(f"Pseudo changé en : {new_name}")
        elif command == "/image":
            self._send_image()
        else:
            self._add_system_message(f"Commande inconnue : {command}")

    def _send_file(self):
        """Envoie un fichier aux pairs connectés."""
        path = filedialog.askopenfilename(title="Choisir un fichier à envoyer")
        if not path:
            return
        filename, data_b64 = FileTransfer.read_file_b64(path)
        if data_b64 is None:
            messagebox.showerror("Erreur", "Impossible de lire le fichier.")
            return
        # Limite à 5 Mo pour éviter les blocages
        size_mb = len(data_b64) * 3 / 4 / (1024 * 1024)
        if size_mb > 5:
            messagebox.showwarning("Fichier trop lourd", "La limite est de 5 Mo dans cette version.")
            return
        payload = {"filename": filename, "data": data_b64, "size": len(data_b64)}
        self._broadcast(MessageProtocol.FILE, payload)
        self._add_system_message(f"Vous avez envoyé le fichier : {filename} ({size_mb:.2f} Mo)")

    def _send_image(self):
        """Envoie une image aux pairs connectés."""
        path = filedialog.askopenfilename(
            title="Choisir une image à envoyer",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp"), ("Tous", "*.*")],
        )
        if not path:
            return
        filename, data_b64 = FileTransfer.read_file_b64(path)
        if data_b64 is None:
            messagebox.showerror("Erreur", "Impossible de lire l'image.")
            return
        size_mb = len(data_b64) * 3 / 4 / (1024 * 1024)
        if size_mb > 5:
            messagebox.showwarning("Image trop lourde", "La limite est de 5 Mo dans cette version.")
            return
        payload = {"filename": filename, "data": data_b64, "size": len(data_b64)}
        self._broadcast(MessageProtocol.IMAGE, payload)
        self._add_system_message(f"Vous avez envoyé l'image : {filename} ({size_mb:.2f} Mo)")

    def _broadcast(self, msg_type, payload):
        """Diffuse un message à tous les pairs connectés."""
        sender_id = self.profile.data.get("id", "")
        sender_name = self.profile.data.get("nickname", "Anonyme")
        sent = False
        for handler in list(self.connected_peers.values()):
            if handler.send(msg_type, payload, sender_id, sender_name):
                sent = True
        for client in list(self.outgoing_connections.values()):
            if client.running and client.send(msg_type, payload, sender_id, sender_name):
                sent = True
        if not sent and msg_type != MessageProtocol.PING:
            self._add_system_message("Aucun pair connecté. Message non envoyé.")

    def _on_typing(self):
        """Envoie un indicateur d'écriture."""
        self._broadcast(MessageProtocol.TYPING, {"state": True})
        self.root.after(2000, lambda: self._broadcast(MessageProtocol.TYPING, {"state": False}))

    # ── Réception et affichage des messages ───────────────────────────────────
    def handle_message(self, msg):
        """Point d'entrée central pour traiter les messages reçus."""
        msg_type = msg.get("type")
        payload = msg.get("payload", {})
        sender_name = msg.get("sender_name", "Inconnu")
        timestamp = msg.get("timestamp", datetime.datetime.now().isoformat())

        try:
            dt = datetime.datetime.fromisoformat(timestamp)
        except Exception:
            dt = datetime.datetime.now()

        if msg_type == MessageProtocol.HELLO:
            self._handle_hello(msg)
        elif msg_type == MessageProtocol.TEXT:
            text = payload.get("text", "")
            encrypted = payload.get("encrypted")
            if encrypted and self.profile.data.get("encryption_enabled"):
                decrypted = decrypt_message(self.profile.data.get("encryption_password", ""), encrypted)
                if decrypted:
                    text = decrypted
            self._add_message_to_chat(sender_name, text, "other", dt)
            self.notifier.play_sound()
        elif msg_type == MessageProtocol.IMAGE:
            self._handle_received_image(payload, sender_name, dt)
            self.notifier.play_sound()
        elif msg_type == MessageProtocol.FILE:
            self._handle_received_file(payload, sender_name, dt)
            self.notifier.play_sound()
        elif msg_type == MessageProtocol.TYPING:
            self._handle_typing(sender_name, payload.get("state", False))
        elif msg_type == MessageProtocol.STATUS:
            self._add_system_message(f"{sender_name} est maintenant : {payload.get('status_message', '')}")
        elif msg_type == MessageProtocol.PING:
            handler = msg.get("_handler")
            if handler:
                handler.send(MessageProtocol.PONG, {"time": time.time()})
        elif msg_type == MessageProtocol.PONG:
            pass
        elif msg_type == MessageProtocol.DISCONNECT:
            self._add_system_message(f"{sender_name} s'est déconnecté.")
        elif msg_type == MessageProtocol.ERROR:
            self._add_system_message(f"Erreur de {sender_name} : {payload.get('message', '')}", tag="error")

    def _handle_hello(self, msg):
        """Traite le message d'introduction d'un pair."""
        payload = msg.get("payload", {})
        sender_name = payload.get("nickname", "Inconnu")
        handler = msg.get("_handler")
        if handler:
            self.connected_peers[handler.address] = handler
        self._add_system_message(f"{sender_name} a rejoint le salon.", tag="success")
        self.status_label.config(text="● En ligne", fg=THEME["green"])

    def _handle_typing(self, sender_name, state):
        """Met à jour l'indicateur 'est en train d'écrire'."""
        if state:
            self.typing_label.config(text=f"{sender_name} écrit...")
            if sender_name in self.typing_timers:
                self.root.after_cancel(self.typing_timers[sender_name])
            self.typing_timers[sender_name] = self.root.after(3000, lambda: self.typing_label.config(text=""))
        else:
            self.typing_label.config(text="")

    def _handle_received_image(self, payload, sender_name, dt):
        """Traite une image reçue."""
        self._add_message_to_chat(sender_name, "[Image reçue]", "other", dt)
        if self.profile.data.get("auto_accept_files") or messagebox.yesno(
            "Image reçue", f"{sender_name} vous envoie {payload.get('filename', 'image.png')}. Accepter ?"
        ):
            target = FileTransfer.save_file_b64(self.profile.directory / "received",
                                                payload.get("filename", "image.png"), payload.get("data"))
            if target:
                self._add_system_message(f"Image sauvegardée : {target}", tag="success")

    def _handle_received_file(self, payload, sender_name, dt):
        """Traite un fichier reçu."""
        filename = payload.get("filename", "fichier")
        self._add_message_to_chat(sender_name, f"[Fichier : {filename}]", "other", dt)
        if self.profile.data.get("auto_accept_files") or messagebox.yesno(
            "Fichier reçu", f"{sender_name} vous envoie {filename}. Accepter ?"
        ):
            target = FileTransfer.save_file_b64(self.profile.directory / "received", filename, payload.get("data"))
            if target:
                self._add_system_message(f"Fichier sauvegardé : {target}", tag="success")

    def _add_message_to_chat(self, nickname, text, direction, dt):
        """Ajoute un message formaté dans la zone de chat."""
        self.chat_text.config(state=tk.NORMAL)
        time_str = dt.strftime("%H:%M:%S")
        self.chat_text.insert(tk.END, f"[{time_str}] ", "timestamp")
        tag = "nickname_self" if direction == "self" else "nickname_other"
        color = THEME["green"] if direction == "self" else THEME["red"]
        self.chat_text.tag_configure(tag, foreground=color, font=("Segoe UI", 9, "bold"))
        self.chat_text.insert(tk.END, f"{nickname}: ", tag)
        self.chat_text.insert(tk.END, f"{text}\n", "message")
        self.chat_text.see(tk.END)
        self.chat_text.config(state=tk.DISABLED)
        self.message_history.append({"nick": nickname, "text": text, "time": time_str, "dir": direction})
        if len(self.message_history) > MAX_HISTORY:
            self.message_history.pop(0)

    def _add_system_message(self, text, tag="system"):
        """Ajoute un message système dans la zone de chat."""
        self.chat_text.config(state=tk.NORMAL)
        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        self.chat_text.insert(tk.END, f"[{time_str}] ", "timestamp")
        self.chat_text.insert(tk.END, f"{text}\n", tag)
        self.chat_text.see(tk.END)
        self.chat_text.config(state=tk.DISABLED)

    # ── Éditeur de profil ─────────────────────────────────────────────────────
    def _open_profile_editor(self):
        """Ouvre la fenêtre d'édition du profil."""
        editor = tk.Toplevel(self.root)
        editor.title("Éditer le profil")
        editor.configure(bg=THEME["bg_mid"])
        editor.transient(self.root)
        editor.grab_set()
        editor.geometry("400x450")

        fields = [
            ("Pseudo", "nickname", "entry"),
            ("Message de statut", "status_message", "entry"),
            ("Statut", "status", "combo", ["En ligne", "Absent", "Occupé", "Invisible"]),
        ]
        entries = {}
        for idx, field in enumerate(fields):
            label_text, key, kind = field[:3]
            tk.Label(editor, text=label_text + " :", bg=THEME["bg_mid"], fg=THEME["text"]).grid(
                row=idx, column=0, padx=10, pady=8, sticky=tk.W
            )
            if kind == "entry":
                widget = tk.Entry(editor, bg=THEME["bg_input"], fg=THEME["text"],
                                  insertbackground=THEME["green"], width=30)
                widget.insert(0, self.profile.data.get(key, ""))
                widget.grid(row=idx, column=1, padx=10, pady=8)
                entries[key] = widget
            elif kind == "combo":
                widget = ttk.Combobox(editor, values=field[3], state="readonly", width=28)
                widget.set(self.profile.data.get(key, field[3][0]))
                widget.grid(row=idx, column=1, padx=10, pady=8)
                entries[key] = widget

        color_idx = len(fields)
        tk.Label(editor, text="Couleur thème :", bg=THEME["bg_mid"], fg=THEME["text"]).grid(
            row=color_idx, column=0, padx=10, pady=8, sticky=tk.W
        )
        color_var = tk.StringVar(value=self.profile.data.get("theme_color", THEME["green"]))
        color_preview = tk.Label(editor, bg=color_var.get(), width=10, relief=tk.RIDGE)
        color_preview.grid(row=color_idx, column=1, padx=10, pady=8, sticky=tk.W)

        def choose_color():
            color = colorchooser.askcolor(color=color_var.get(), title="Choisir une couleur")[1]
            if color:
                color_var.set(color)
                color_preview.config(bg=color)

        tk.Button(editor, text="Choisir", bg=THEME["bg_light"], fg=THEME["green"],
                  command=choose_color).grid(row=color_idx, column=1, padx=10, pady=8, sticky=tk.E)

        # Avatar
        avatar_idx = color_idx + 1
        tk.Label(editor, text="Avatar :", bg=THEME["bg_mid"], fg=THEME["text"]).grid(
            row=avatar_idx, column=0, padx=10, pady=8, sticky=tk.W
        )
        self.editor_avatar = tk.Label(editor, image=self.avatar_img, bg=THEME["bg_mid"])
        self.editor_avatar.grid(row=avatar_idx, column=1, padx=10, pady=8)
        tk.Button(editor, text="Uploader une photo", bg=THEME["bg_light"], fg=THEME["green"],
                  command=lambda: self._upload_avatar_for_editor()).grid(
            row=avatar_idx + 1, column=1, padx=10, pady=5
        )

        def save_profile():
            updates = {key: widget.get() for key, widget in entries.items()}
            updates["theme_color"] = color_var.get()
            self.profile.update_profile(**updates)
            self._load_profile_ui()
            editor.destroy()

        tk.Button(editor, text="Sauvegarder", bg=THEME["green_dark"], fg="white",
                  font=("Segoe UI", 10, "bold"), command=save_profile).grid(
            row=avatar_idx + 2, column=0, columnspan=2, pady=20
        )

    def _upload_avatar(self):
        """Permet d'uploader un avatar depuis la section profil."""
        path = filedialog.askopenfilename(
            title="Choisir une photo de profil",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp"), ("Tous", "*.*")],
        )
        if path and self.profile.set_avatar(path):
            self._load_profile_ui()

    def _upload_avatar_for_editor(self):
        """Uploade un avatar depuis l'éditeur."""
        path = filedialog.askopenfilename(
            title="Choisir une photo de profil",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp"), ("Tous", "*.*")],
        )
        if path and self.profile.set_avatar(path):
            self.avatar_img = self.profile.get_avatar_image((80, 80))
            self.editor_avatar.config(image=self.avatar_img)

    # ── Paramètres avancés ────────────────────────────────────────────────────
    def _open_settings(self):
        """Ouvre les paramètres avancés."""
        settings = tk.Toplevel(self.root)
        settings.title("Paramètres avancés")
        settings.configure(bg=THEME["bg_mid"])
        settings.transient(self.root)
        settings.grab_set()
        settings.geometry("400x350")

        vars_map = {
            "sound_enabled": tk.BooleanVar(value=self.profile.data.get("sound_enabled", True)),
            "notifications": tk.BooleanVar(value=self.profile.data.get("notifications", True)),
            "history_enabled": tk.BooleanVar(value=self.profile.data.get("history_enabled", True)),
            "auto_accept_files": tk.BooleanVar(value=self.profile.data.get("auto_accept_files", False)),
        }

        row = 0
        for key, var in vars_map.items():
            text = key.replace("_", " ").title()
            tk.Checkbutton(settings, text=text, variable=var, bg=THEME["bg_mid"],
                           fg=THEME["text"], selectcolor=THEME["bg_input"],
                           activebackground=THEME["bg_mid"], activeforeground=THEME["green"]).grid(
                row=row, column=0, sticky=tk.W, padx=20, pady=5
            )
            row += 1

        tk.Label(settings, text="Mot de passe de chiffrement (AES) :", bg=THEME["bg_mid"],
                 fg=THEME["text"]).grid(row=row, column=0, sticky=tk.W, padx=20, pady=(15, 0))
        row += 1
        enc_var = tk.BooleanVar(value=self.profile.data.get("encryption_enabled", False))
        enc_check = tk.Checkbutton(settings, text="Activer le chiffrement", variable=enc_var,
                                   bg=THEME["bg_mid"], fg=THEME["text"], selectcolor=THEME["bg_input"])
        enc_check.grid(row=row, column=0, sticky=tk.W, padx=20, pady=5)
        row += 1
        pwd_entry = tk.Entry(settings, show="•", bg=THEME["bg_input"], fg=THEME["text"],
                             insertbackground=THEME["green"], width=30)
        pwd_entry.insert(0, self.profile.data.get("encryption_password", ""))
        pwd_entry.grid(row=row, column=0, padx=20, pady=5)
        row += 1

        if not CRYPTO_AVAILABLE:
            tk.Label(settings, text="⚠ Installez 'cryptography' pour activer le chiffrement.",
                     bg=THEME["bg_mid"], fg=THEME["red"], font=THEME["font_small"]).grid(
                row=row, column=0, padx=20, pady=5
            )
            row += 1

        def save_settings():
            updates = {key: var.get() for key, var in vars_map.items()}
            updates["encryption_enabled"] = enc_var.get()
            updates["encryption_password"] = pwd_entry.get()
            self.profile.update_profile(**updates)
            settings.destroy()
            self._set_info("Paramètres sauvegardés.")

        tk.Button(settings, text="Sauvegarder", bg=THEME["green_dark"], fg="white",
                  command=save_settings).grid(row=row, column=0, pady=20)

    def _test_port_dialog(self):
        """Vérifie si un port est ouvert localement."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Test de port")
        dialog.configure(bg=THEME["bg_mid"])
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Port :", bg=THEME["bg_mid"], fg=THEME["text"]).pack(padx=10, pady=5)
        port_entry = tk.Entry(dialog, bg=THEME["bg_input"], fg=THEME["text"], insertbackground=THEME["green"])
        port_entry.insert(0, str(DEFAULT_PORT))
        port_entry.pack(padx=10, pady=5)

        result_label = tk.Label(dialog, text="", bg=THEME["bg_mid"], fg=THEME["text_dim"])
        result_label.pack(padx=10, pady=5)

        def test():
            port = port_entry.get().strip()
            if not is_valid_port(port):
                result_label.config(text="Port invalide", fg=THEME["red"])
                return
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2)
                    s.bind(("0.0.0.0", int(port)))
                    result_label.config(text=f"Le port {port} est libre localement.", fg=THEME["green"])
            except OSError:
                result_label.config(text=f"Le port {port} est occupé ou fermé.", fg=THEME["red"])

        tk.Button(dialog, text="Tester", bg=THEME["green_dark"], fg="white", command=test).pack(pady=10)

    def _show_ips(self):
        """Affiche les IPs de la machine."""
        messagebox.showinfo("Mes adresses IP", f"IP Locale : {self.local_ip}\nIP Publique : {self.public_ip}")

    def _show_help(self):
        """Affiche l'aide des commandes."""
        messagebox.showinfo(
            "Commandes slash",
            "/aide  → Afficher cette aide\n"
            "/clear → Vider le chat\n"
            "/ip    → Afficher vos IP\n"
            "/nom   → Changer de pseudo\n"
            "/statut→ Changer de statut\n"
            "/image → Envoyer une image\n"
            "/quit  → Quitter"
        )

    def _show_about(self):
        """Affiche la fenêtre À propos."""
        messagebox.showinfo(
            "À propos",
            f"{APP_NAME}\nVersion {APP_VERSION}\nAuteur : {APP_AUTHOR}\n\n"
            "Messagerie pair-à-pair sécurisée et stylisée."
        )

    # ── Callbacks réseau ──────────────────────────────────────────────────────
    def on_server_started(self, port):
        """Appelé quand le serveur démarre."""
        self.status_label.config(text=f"● Serveur actif :{port}", fg=THEME["green"])
        self._add_system_message(f"Votre serveur est actif sur le port {port}.", tag="success")
        self._set_info("Serveur actif. Partagez votre IP publique avec vos amis.")

    def on_server_error(self, error):
        """Appelé en cas d'erreur serveur."""
        self._add_system_message(f"Erreur serveur : {error}", tag="error")
        self._set_info(f"Erreur serveur : {error}")

    def on_server_stopped(self):
        """Appelé quand le serveur s'arrête."""
        self.status_label.config(text="● Hors ligne", fg=THEME["red"])
        self._add_system_message("Serveur arrêté.")

    def on_client_connected(self, handler):
        """Appelé quand un client se connecte."""
        self.connected_peers[handler.address] = handler
        self.status_label.config(text="● En ligne", fg=THEME["green"])
        # Envoi du profil
        handler.send(
            MessageProtocol.HELLO,
            {
                "nickname": self.profile.data.get("nickname", "Anonyme"),
                "status": self.profile.data.get("status", "En ligne"),
                "status_message": self.profile.data.get("status_message", ""),
                "id": self.profile.data.get("id", ""),
            },
            self.profile.data.get("id", ""),
            self.profile.data.get("nickname", "Anonyme"),
        )

    def on_client_disconnected(self, handler):
        """Appelé quand un client se déconnecte."""
        if handler.address in self.connected_peers:
            del self.connected_peers[handler.address]
        if not self.connected_peers and not any(c.running for c in self.outgoing_connections.values()):
            self.status_label.config(text="● Hors ligne", fg=THEME["red"])

    def on_connection_success(self, ip, port):
        """Appelé quand une connexion sortante réussit."""
        self._add_system_message(f"Connecté à {ip}:{port}.", tag="success")
        self.status_label.config(text=f"● Connecté {ip}:{port}", fg=THEME["green"])
        self._set_info(f"Connecté à {ip}:{port}")

    def on_connection_error(self, ip, port, error):
        """Appelé en cas d'échec de connexion."""
        self._add_system_message(f"Échec connexion à {ip}:{port} : {error}", tag="error")
        self._set_info(f"Échec connexion : {error}")

    def on_disconnected(self, ip, port):
        """Appelé quand une connexion sortante se termine."""
        key = f"{ip}:{port}"
        if key in self.outgoing_connections:
            del self.outgoing_connections[key]
        self._add_system_message(f"Déconnecté de {ip}:{port}.")
        if not self.connected_peers and not self.outgoing_connections:
            self.status_label.config(text="● Hors ligne", fg=THEME["red"])

    # ── Mise à jour périodique ────────────────────────────────────────────────
    def _start_status_updater(self):
        """Lance les tâches périodiques."""
        self._send_ping_loop()
        self._refresh_ips_loop()

    def _send_ping_loop(self):
        """Envoie un ping toutes les 30 secondes pour garder les connexions actives."""
        if self.connected_peers or self.outgoing_connections:
            self._broadcast(MessageProtocol.PING, {"time": time.time()})
        self.root.after(30000, self._send_ping_loop)

    def _refresh_ips_loop(self):
        """Rafraîchit l'IP publique toutes les 5 minutes."""
        self._refresh_ips()
        self.root.after(300000, self._refresh_ips_loop)

    def _set_info(self, text):
        """Met à jour la barre d'information."""
        self.info_label.config(text=text)

    # ── Fermeture ─────────────────────────────────────────────────────────────
    def _on_close(self):
        """Ferme proprement l'application."""
        if messagebox.askyesno("Quitter", "Voulez-vous vraiment quitter CyberChat ?"):
            self._broadcast(MessageProtocol.DISCONNECT, {"message": "Fermeture de l'application"})
            if self.server:
                self.server.stop()
            for client in list(self.outgoing_connections.values()):
                client.stop()
            self.root.destroy()


# ───────────────────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE
# ───────────────────────────────────────────────────────────────────────────────
def main():
    """Lance l'application CyberChat P2P."""
    root = tk.Tk()
    app = CyberChatApp(root)
    root.protocol("WM_DELETE_WINDOW", app._on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
