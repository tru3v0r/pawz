# pawz

Pilotage de Windows avec une manette : profils par appareil, raccourcis par application et par site web, interface Qt.

**Plateforme : Windows 10/11 · Python 3.12 · statut : prototype (0.1.0).**

## Lancer depuis les sources

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-windows.ps1
```

Les scripts utilisent un environnement Python propre à chaque machine, `%LOCALAPPDATA%\pawz\venv-py312`, hors du dossier synchronisé (personnalisable avec `PAWZ_VENV_DIR`).

## Construire l'exécutable

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1
```

Le script installe les dépendances dans ce même environnement, lance les tests puis produit `dist\pawz\pawz.exe`. Il s'arrête à la première erreur.

## Qualité

```powershell
$py = "$env:LOCALAPPDATA\pawz\venv-py312\Scripts\python.exe"
& $py -m pytest -q
& $py -m ruff check .
```

## Documentation

- [Guide utilisateur](docs/UTILISATEUR.md)
- [Guide des manettes](docs/MANETTES.md) : onglets Général, Profils et Manettes
- [Documentation développeur](docs/DEVELOPPEUR.md)
- [Architecture des contrôleurs](docs/CONTROLLER_ARCHITECTURE.md)
- [Provenance des illustrations](docs/ASSETS.md)

## Licence

GPL-3.0-or-later (voir `LICENSE`).
