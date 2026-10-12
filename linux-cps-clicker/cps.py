cd ~/linux-cps-clicker
cat > cps.py << 'EOF'
#!/usr/bin/env python3
"""Linux Click : auto-clicker CPS pour Linux (Wayland + X11) via evdev/uinput.

Raccourcis clavier (fonctionnent partout, même dans un jeu) :
  F4 : activer / désactiver le CLIC GAUCHE   (modifiable)
  F5 : activer / désactiver le CLIC DROIT    (modifiable)
  F6 : changer la touche du clic gauche (puis appuie sur la nouvelle touche, Échap = annuler)
  F7 : changer la touche du clic droit  (idem)
  F8 : quitter

Clic gauche et clic droit sont indépendants : tu peux activer les deux en même temps
et maintenir les deux boutons en même temps.

Dans le terminal, tu peux aussi taper des commandes (tape "help").

Usage : sudo python3 cps.py [--cps 13] [--left-key F4] [--right-key F5] [--link] [--debug]
Note : la souris est capturée et recopiée via une souris virtuelle.
       Les pavés tactiles ne sont pas pris en charge (souris uniquement).
"""
import argparse
import os
import selectors
import subprocess
import sys
import threading
import time

try:
    import readline
except ImportError:
    readline = None
try:
    import termios
except ImportError:
    termios = None

from evdev import InputDevice, UInput, ecodes as e, list_devices

REBIND_LEFT_KEY = e.KEY_F6
REBIND_RIGHT_KEY = e.KEY_F7
QUIT_KEY = e.KEY_F8
RESERVED = {REBIND_LEFT_KEY, REBIND_RIGHT_KEY, QUIT_KEY, e.KEY_ESC}

VERSION = "1.1"
PREFIX = "cps-virtual"
PROMPT = "linux-click> "
MAX_CPS = 200.0
LEFT, RIGHT = e.BTN_LEFT, e.BTN_RIGHT
BUTTONS = (LEFT, RIGHT)
LABEL = {LEFT: "clic gauche", RIGHT: "clic droit"}
SIDE = {"left": LEFT, "right": RIGHT}

BANNER = """
██╗     ██╗███╗   ██╗██╗   ██╗██╗  ██╗
██║     ██║████╗  ██║██║   ██║╚██╗██╔╝
██║     ██║██╔██╗ ██║██║   ██║ ╚███╔╝
██║     ██║██║╚██╗██║██║   ██║ ██╔██╗
███████╗██║██║ ╚████║╚██████╔╝██╔╝ ██╗
╚══════╝╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝  ╚═╝

 ██████╗██╗     ██╗ ██████╗██╗  ██╗
██╔════╝██║     ██║██╔════╝██║ ██╔╝
██║     ██║     ██║██║     █████╔╝
██║     ██║     ██║██║     ██╔═██╗
╚██████╗███████╗██║╚██████╗██║  ██╗
 ╚═════╝╚══════╝╚═╝ ╚═════╝╚═╝  ╚═╝
""".strip("\n").split("\n")

COMMANDS = [
    ("help", "", "Ouvre cette liste (help print : l'affiche dans le terminal)"),
    ("status", "", "Affiche l'état"),
    ("left", "[on/off]", "Clic gauche on/off (sans argument : bascule)"),
    ("right", "[on/off]", "Clic droit on/off (sans argument : bascule)"),
    ("on", "", "Active le gauche et le droit"),
    ("off", "", "Désactive le gauche et le droit"),
    ("link", "[on/off]", "Un bouton maintenu clique les deux"),
    ("cps", "[nombre]", "Change la vitesse (clics par seconde)"),
    ("key", "<left/right> <TOUCHE>", "Change la touche (ex : key left F9)"),
    ("keys", "", "Affiche les touches"),
    ("clear", "", "Efface l'écran"),
    ("quit", "", "Quitte le programme"),
]

keys = {LEFT: e.KEY_F4, RIGHT: e.KEY_F5}
enabled = {LEFT: False, RIGHT: False}
held = {LEFT: False, RIGHT: False}
link = False
target_cps = 10.0
measured = 0.0
rebinding = None
running = True
click_count = 0
active_ui = None
awaiting_input = False
print_lock = threading.Lock()
lock = threading.Lock()


def current_input():
    if readline:
        try:
            return readline.get_line_buffer()
        except Exception:
            return ""
    return ""


def out(text=""):
    """Affiche une ligne (utilisé par les commandes)."""
    with print_lock:
        sys.stdout.write(text + "\n")
        sys.stdout.flush()


def log(text):
    """Message asynchrone (touche pressée...) : sans casser la ligne en cours de saisie."""
    with print_lock:
        if awaiting_input:
            sys.stdout.write("\r\033[K" + text + "\n" + PROMPT + current_input())
        else:
            sys.stdout.write(text + "\n")
        sys.stdout.flush()


def key_name(code):
    name = e.KEY.get(code) or str(code)
    if isinstance(name, (list, tuple)):
        name = name[0]
    return name.replace("KEY_", "")


def parse_key(name):
    name = name.strip().upper()
    if not name.startswith("KEY_"):
        name = "KEY_" + name
    code = getattr(e, name, None)
    if not isinstance(code, int) or code not in e.KEY:
        raise ValueError(f"Touche inconnue : {name}")
    return code


def on_off(value):
    return "\033[92mON \033[0m" if value else "\033[91mOFF\033[0m"


def status_lines():
    return [
        f"  Clic gauche : {on_off(enabled[LEFT])}  (touche {key_name(keys[LEFT])})",
        f"  Clic droit  : {on_off(enabled[RIGHT])}  (touche {key_name(keys[RIGHT])})",
        f"  Mode lié    : {on_off(link)}",
        f"  CPS cible   : {target_cps:.1f}   (mesuré : {measured:.1f})",
        f"  Changer les touches : {key_name(REBIND_LEFT_KEY)} (gauche), "
        f"{key_name(REBIND_RIGHT_KEY)} (droit)   Quitter : {key_name(QUIT_KEY)}",
    ]


def print_banner():
    out()
    for line in BANNER:
        out("\033[96m  " + line + "\033[0m")
    out(f"\033[90m  CPS Clicker pour Linux  ·  v{VERSION}  ·  Wayland + X11\033[0m\n")

    rows = [
        (key_name(keys[LEFT]), "Clic gauche : activer / désactiver"),
        (key_name(keys[RIGHT]), "Clic droit : activer / désactiver"),
        (key_name(REBIND_LEFT_KEY), "Changer la touche du clic gauche"),
        (key_name(REBIND_RIGHT_KEY), "Changer la touche du clic droit"),
        (key_name(QUIT_KEY), "Quitter"),
    ]
    lines = [f" {k:<5} {d}" for k, d in rows]
    lines += ["", f" CPS cible : {target_cps:.1f}", " Commandes : tape help"]
    width = max(len(l) for l in lines) + 2
    out("  ┌" + "─" * width + "┐")
    for l in lines:
        out("  │" + l.ljust(width) + "│")
    out("  └" + "─" * width + "┘")


def set_toggle_key(side, code):
    b = SIDE[side]
    other = keys[RIGHT if b == LEFT else LEFT]
    if code in RESERVED:
        return False, (f"{key_name(code)} est réservée "
                       f"({key_name(REBIND_LEFT_KEY)}, {key_name(REBIND_RIGHT_KEY)}, "
                       f"{key_name(QUIT_KEY)}, Échap).")
    if code == other:
        return False, f"{key_name(code)} est déjà utilisée par l'autre bouton."
    keys[b] = code
    return True, f"Touche du {LABEL[b]} : {key_name(code)}"


def set_enabled(b, value=None):
    enabled[b] = (not enabled[b]) if value is None else value
    state = "\033[92m[ON] \033[0m" if enabled[b] else "\033[91m[OFF]\033[0m"
    return f"{state} {LABEL[b]}"


def buttons_to_click():
    """Boutons à cliquer maintenant (selon ceux maintenus et le mode lié)."""
    pressed = [b for b in BUTTONS if held[b] and enabled[b]]
    if link and pressed:
        return [b for b in BUTTONS if enabled[b]]
    return pressed


def click_loop():
    """Envoie de vrais clics séparés pour chaque bouton concerné."""
    global click_count
    next_time = time.perf_counter()
    while running:
        ui = active_ui
        buttons = buttons_to_click()
        if not (buttons and ui):
            time.sleep(0.005)
            next_time = time.perf_counter()
            continue

        with lock:
            for b in buttons:
                ui.write(e.EV_KEY, b, 1)
            ui.syn()
        time.sleep(0.008)
        with lock:
            for b in buttons:
                ui.write(e.EV_KEY, b, 0)
            ui.syn()
            click_count += len(buttons)

        next_time += 1.0 / target_cps
        delay = next_time - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        else:
            next_time = time.perf_counter()


def find_devices():
    keyboards, mice = [], []
    for path in list_devices():
        dev = InputDevice(path)
        if dev.name.startswith(PREFIX):
            dev.close()
            continue
        caps = dev.capabilities()
        ev_keys = caps.get(e.EV_KEY, [])
        rel = caps.get(e.EV_REL, [])
        absolute = caps.get(e.EV_ABS, [])
        if e.KEY_A in ev_keys and QUIT_KEY in ev_keys:
            keyboards.append(dev)
        elif LEFT in ev_keys and e.REL_X in rel and not absolute:
            mice.append(dev)
        else:
            dev.close()
    return keyboards, mice


def handle_key(code, debug, dev_name):
    """Gère une touche du clavier (appui)."""
    global rebinding, running

    if debug:
        log(f"[debug] touche {key_name(code)} ({dev_name})")

    if rebinding:
        side = rebinding
        if code == e.KEY_ESC:
            rebinding = None
            log("Changement annulé")
            return
        ok, msg = set_toggle_key(side, code)
        log(msg)
        if ok:
            rebinding = None
        return

    for b in BUTTONS:
        if code == keys[b]:
            log(set_enabled(b))
            return
    if code == QUIT_KEY:
        running = False
    elif code == REBIND_LEFT_KEY:
        rebinding = "left"
        log("\033[93m>>> Appuie sur la nouvelle touche du CLIC GAUCHE (Échap = annuler)\033[0m")
    elif code == REBIND_RIGHT_KEY:
        rebinding = "right"
        log("\033[93m>>> Appuie sur la nouvelle touche du CLIC DROIT (Échap = annuler)\033[0m")


def commands_text():
    lines = ["", "  Raccourcis clavier :",
             f"    {key_name(keys[LEFT]):<6} clic gauche : activer / désactiver",
             f"    {key_name(keys[RIGHT]):<6} clic droit : activer / désactiver",
             f"    {key_name(REBIND_LEFT_KEY):<6} changer la touche du clic gauche",
             f"    {key_name(REBIND_RIGHT_KEY):<6} changer la touche du clic droit",
             f"    {key_name(QUIT_KEY):<6} quitter", "", "  Commandes :"]
    for name, arg, desc in COMMANDS:
        lines.append(f"    {(name + ' ' + arg).strip():<26} {desc}")
    lines.append("")
    return lines


def commands_file_text():
    """Contenu de COMMANDS.md : du texte simple, lisible dans n'importe quel éditeur."""
    width = max(len((n + " " + a).strip()) for n, a, _ in COMMANDS) + 3
    lines = ["LINUX CLICK - COMMANDES", ""]
    for name, arg, desc in COMMANDS:
        lines.append(f"{(name + ' ' + arg).strip():<{width}}{desc}")
    lines.append("")
    return "\n".join(lines)


def write_commands_file():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "COMMANDS.md")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(commands_file_text())
        uid, gid = os.environ.get("SUDO_UID"), os.environ.get("SUDO_GID")
        if uid and gid:
            os.chown(path, int(uid), int(gid))
    except OSError:
        return None
    return path


def open_file_as_user(path):
    """Ouvre un fichier avec l'appli par défaut de l'utilisateur (même sous sudo)."""
    user, uid = os.environ.get("SUDO_USER"), os.environ.get("SUDO_UID")
    if user and uid:
        runtime = f"/run/user/{uid}"
        env = [f"XDG_RUNTIME_DIR={runtime}",
               f"DBUS_SESSION_BUS_ADDRESS=unix:path={runtime}/bus",
               f"DISPLAY={os.environ.get('DISPLAY', ':0')}"]
        wayland = os.environ.get("WAYLAND_DISPLAY") or (
            "wayland-0" if os.path.exists(f"{runtime}/wayland-0") else None)
        if wayland:
            env.append(f"WAYLAND_DISPLAY={wayland}")
        if os.environ.get("XAUTHORITY"):
            env.append(f"XAUTHORITY={os.environ['XAUTHORITY']}")
        cmd = ["sudo", "-u", user, "env", *env, "xdg-open", path]
    else:
        cmd = ["xdg-open", path]
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return False
    try:
        return proc.wait(timeout=3) == 0
    except subprocess.TimeoutExpired:
        return True


def cmd_help(args):
    if args and args[0].lower() in ("print", "text", "texte"):
        for line in commands_text():
            out(line)
        return
    path = write_commands_file()
    if path:
        out(f"  Ouverture de {path} ...")
        if open_file_as_user(path):
            return
        out("  Impossible de l'ouvrir automatiquement. Voici les commandes :")
    for line in commands_text():
        out(line)


def parse_switch(args):
    """Retourne True / False / None (bascule) selon l'argument on/off."""
    if not args:
        return None
    word = args[0].lower()
    if word in ("on", "1", "oui", "true"):
        return True
    if word in ("off", "0", "non", "false"):
        return False
    raise ValueError("Utilise on ou off.")


def run_command(line):
    global running, link, target_cps
    parts = line.strip().split()
    if not parts:
        return
    cmd, args = parts[0].lower(), parts[1:]

    try:
        if cmd == "help":
            cmd_help(args)
        elif cmd == "status":
            for l in status_lines():
                out(l)
        elif cmd in ("left", "right"):
            out("  " + set_enabled(SIDE[cmd], parse_switch(args)))
        elif cmd == "on":
            out("  " + set_enabled(LEFT, True))
            out("  " + set_enabled(RIGHT, True))
        elif cmd == "off":
            out("  " + set_enabled(LEFT, False))
            out("  " + set_enabled(RIGHT, False))
        elif cmd == "link":
            value = parse_switch(args)
            link = (not link) if value is None else value
            out(f"  Mode lié : {on_off(link)}")
        elif cmd == "cps":
            if not args:
                out(f"  CPS cible : {target_cps:.1f}   (mesuré : {measured:.1f})")
            else:
                try:
                    value = float(args[0].replace(",", "."))
                except ValueError:
                    raise ValueError("Donne un nombre, ex : cps 13")
                if not 0 < value <= MAX_CPS:
                    raise ValueError(f"Choisis une valeur entre 0 et {MAX_CPS:.0f}.")
                target_cps = value
                out(f"  CPS cible : {target_cps:.1f}")
        elif cmd == "key":
            if len(args) != 2 or args[0].lower() not in SIDE:
                raise ValueError("Usage : key <left/right> <TOUCHE>   ex : key left F9")
            ok, msg = set_toggle_key(args[0].lower(), parse_key(args[1]))
            out(("  " if ok else "  ✗ ") + msg)
        elif cmd == "keys":
            out(f"  Clic gauche : {key_name(keys[LEFT])}   Clic droit : {key_name(keys[RIGHT])}")
            out(f"  Changer : {key_name(REBIND_LEFT_KEY)} / {key_name(REBIND_RIGHT_KEY)}"
                f"   Quitter : {key_name(QUIT_KEY)}")
        elif cmd == "clear":
            with print_lock:
                sys.stdout.write("\033[2J\033[H")
                sys.stdout.flush()
        elif cmd in ("quit", "exit"):
            running = False
        else:
            out(f"  Commande inconnue : {cmd}   (tape help)")
    except ValueError as err:
        out(f"  ✗ {err}")


def command_loop():
    """Thread qui lit les commandes tapées dans le terminal."""
    global awaiting_input
    while running:
        try:
            awaiting_input = True
            line = input(PROMPT)
        except (EOFError, KeyboardInterrupt, OSError):
            awaiting_input = False
            return
        awaiting_input = False
        try:
            run_command(line)
        except Exception as err:
            out(f"  ✗ Erreur : {err}")


def main():
    global target_cps, link, running, click_count, active_ui, measured, awaiting_input

    parser = argparse.ArgumentParser(description="Linux Click : auto-clicker CPS pour Linux")
    parser.add_argument("--cps", type=float, default=10.0,
                        help="clics par seconde (défaut : 10)")
    parser.add_argument("--left-key", default="F4",
                        help="touche du clic gauche au démarrage (défaut : F4)")
    parser.add_argument("--right-key", default="F5",
                        help="touche du clic droit au démarrage (défaut : F5)")
    parser.add_argument("--link", action="store_true",
                        help="mode lié : maintenir un bouton envoie les clics des deux")
    parser.add_argument("--debug", action="store_true",
                        help="affiche chaque touche reçue")
    args = parser.parse_args()

    if not 0 < args.cps <= MAX_CPS:
        sys.exit(f"--cps doit être entre 0 et {MAX_CPS:.0f}")
    try:
        left_code, right_code = parse_key(args.left_key), parse_key(args.right_key)
    except ValueError as err:
        sys.exit(str(err))
    if left_code in RESERVED or right_code in RESERVED:
        sys.exit("F6, F7, F8 et Échap sont réservées. Choisis d'autres touches.")
    if left_code == right_code:
        sys.exit("Le clic gauche et le clic droit ne peuvent pas avoir la même touche.")
    keys[LEFT], keys[RIGHT] = left_code, right_code
    target_cps = args.cps
    link = args.link

    try:
        keyboards, mice = find_devices()
    except PermissionError:
        sys.exit("Permission refusée : lance avec  sudo python3 cps.py")

    if not keyboards:
        sys.exit("Aucun clavier détecté (essaie avec sudo).")
    if not mice:
        sys.exit("Aucune souris détectée (essaie avec sudo).")

    mice_by_path = {m.path: m for m in mice}
    mouse_ui = {}
    swallowed = {}
    try:
        for m in mice:
            mouse_ui[m.path] = UInput.from_device(m, name=f"{PREFIX}-{m.name}")
            swallowed[m.path] = set()
            m.grab()
    except OSError as err:
        sys.exit(f"Impossible de capturer la souris : {err}")

    saved_tty = None
    if termios and sys.stdin.isatty():
        try:
            saved_tty = termios.tcgetattr(sys.stdin.fileno())
        except termios.error:
            saved_tty = None

    print_banner()
    out("\n  Claviers écoutés :")
    for k in keyboards:
        out(f"    - {k.name}  ({k.path})")
    out("  Souris capturées :")
    for m in mice:
        out(f"    - {m.name}  ({m.path})")
    out()

    sel = selectors.DefaultSelector()
    for dev in keyboards + mice:
        sel.register(dev, selectors.EVENT_READ, data=dev.path)

    time.sleep(0.5)
    threading.Thread(target=click_loop, daemon=True).start()
    if sys.stdin.isatty():
        threading.Thread(target=command_loop, daemon=True).start()

    last_t = time.perf_counter()
    try:
        while running:
            for key, _ in sel.select(timeout=0.2):
                dev = key.fileobj
                path = key.data
                try:
                    for ev in dev.read():
                        if path in mouse_ui:
                            ui = mouse_ui[path]
                            if ev.type == e.EV_KEY and ev.code in BUTTONS:
                                b = ev.code
                                if ev.value == 1:
                                    if enabled[b]:
                                        swallowed[path].add(b)
                                        held[b] = True
                                        active_ui = ui
                                        continue
                                elif b in swallowed[path]:
                                    if ev.value == 0:
                                        swallowed[path].discard(b)
                                        held[b] = False
                                    continue
                            with lock:
                                ui.write_event(ev)
                        elif ev.type == e.EV_KEY and ev.value == 1:
                            handle_key(ev.code, args.debug, dev.name)
                except BlockingIOError:
                    pass
                except OSError:
                    sel.unregister(dev)
                    log(f"[!] Périphérique perdu : {dev.name}")

            now = time.perf_counter()
            if now - last_t >= 0.5:
                with lock:
                    count, click_count = click_count, 0
                measured = count / (now - last_t)
                last_t = now
    except KeyboardInterrupt:
        pass
    finally:
        running = False
        for path, ui in mouse_ui.items():
            try:
                mice_by_path[path].ungrab()
            except OSError:
                pass
            ui.close()
        if saved_tty is not None:
            try:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, saved_tty)
            except termios.error:
                pass
        awaiting_input = False
        out("\nBye.")
    os._exit(0)


if __name__ == "__main__":
    main()
EOF
head -3 cps.py
grep -c "#" cps.py
