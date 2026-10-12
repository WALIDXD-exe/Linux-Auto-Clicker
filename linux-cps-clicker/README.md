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
        CPS Clicker pour Linux

 
Un auto-clicker simple pour **Linux**, qui s'utilise dans le terminal.
Il marche sur **Wayland** et sur **X11** (testé sur Ubuntu).
 
> ⚠ Ce projet fonctionne uniquement sur **Linux**. Il ne marche pas sur Windows ni sur macOS.
 
## Comment ça marche
 
1. Tu lances le programme dans le terminal.
2. Tu appuies sur **F4** pour l'activer (`[ON]`).
3. Tu **maintiens le bouton de la souris** : le programme envoie des clics rapides à ta place.
4. Tu relâches : ça s'arrête.
5. **F4** à nouveau pour désactiver (`[OFF]`), **F8** pour quitter.
### Les touches
 
| Touche | Action |
|---|---|
| `F4` (modifiable) | Activer / désactiver |
| `F6` | Changer la touche d'activation : appuie sur `F6`, puis sur la nouvelle touche (`Échap` annule) |
| `F7` | Changer de mode |
| `F8` | Quitter |
 
### Les 4 modes
 
| Mode | Option | Ce que ça fait |
|---|---|---|
| Clic gauche | `--button left` | Maintenir le clic gauche répète le clic gauche |
| Clic droit | `--button right` | Maintenir le clic droit répète le clic droit |
| Gauche + droit | `--button both` | Chaque bouton répète son propre clic, et tu peux maintenir les deux en même temps |
| Les deux ensemble | `--button link` | Maintenir gauche **ou** droit envoie les deux clics en même temps |
 
## Installation
 
Il te faut Python 3 et la bibliothèque `evdev`.
 
```bash
sudo apt update
sudo apt install python3 python3-evdev
```
 
Ensuite, télécharge le projet :
 
```bash
git clone https://github.com/WALIDXD-exe/Linux-Auto-Clicker.git
cd Linux-Auto-Clicker/linux-cps-clicker
```
 
Sans Git, tu peux aussi cliquer sur le bouton vert **Code** puis **Download ZIP** sur la page GitHub, et décompresser le dossier.
 
## Utilisation
 
```bash
sudo python3 cps.py --cps 13
```
 
`sudo` est obligatoire, car le programme doit lire le clavier et la souris au niveau du système.
 
### Options
 
| Option | Description | Défaut |
|---|---|---|
| `--cps N` | Nombre de clics par seconde | `10` |
| `--button left\|right\|both\|link` | Mode de clic au démarrage | `left` |
| `--toggle TOUCHE` | Touche d'activation au démarrage (ex. `F9`, `CapsLock`) | `F4` |
| `--debug` | Affiche les touches reçues (utile en cas de problème) | désactivé |
 
Exemples :
 
```bash
sudo python3 cps.py --cps 15
sudo python3 cps.py --cps 13 --button right
sudo python3 cps.py --cps 13 --toggle F9 --button link
```
 
La touche choisie avec `F6` n'est pas mémorisée : au prochain lancement, utilise `--toggle` pour la remettre.
 
## Problèmes courants
 
### F4 ne fait rien
Sur beaucoup d'ordinateurs portables, les touches F servent d'abord au volume ou à la luminosité. Essaie **Fn + F4**, ou choisis une autre touche avec `F6`. Lance aussi avec `--debug` pour voir si la touche est bien reçue.
 
### `Permission refusée`
Tu as oublié `sudo` devant la commande.
 
### `ModuleNotFoundError: No module named 'evdev'`
Installe la dépendance : `sudo apt install python3-evdev`.
 
### Ma souris ne bouge plus
Appuie sur **F8** ou fais `Ctrl+C` dans le terminal : le programme relâche la souris en s'arrêtant.
 
### Le CPS affiché est un peu plus bas que celui demandé
C'est normal, chaque clic prend un peu de temps. Mets une valeur légèrement plus haute dans `--cps`.
 
## Limites
 
- Fonctionne avec une **souris** (le pavé tactile n'est pas pris en charge).
- Nécessite les droits administrateur (`sudo`).
- Testé sur Ubuntu. Devrait marcher sur les autres distributions Linux.
## Avertissement
 
Ce projet est fourni pour un usage personnel (tests, accessibilité, jeux solo).
De nombreux jeux et serveurs en ligne interdisent les auto-clickers : leur utilisation peut entraîner un bannissement. Tu es responsable de l'usage que tu en fais.
 
## Licence
 
Projet open source sous licence **MIT**. Voir le fichier [LICENSE](LICENSE).
