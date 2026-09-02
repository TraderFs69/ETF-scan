# Scanner Swing ETF — Trading en Action

Scanner quotidien d'ETF canadiens et américains utilisant les données ajustées de Yahoo Finance.

Le programme recherche une reprise après un repli contrôlé dans une tendance haussière :

- clôture au-dessus de l'EMA50 et EMA50 au-dessus de l'EMA200;
- EMA50 en hausse;
- force relative supérieure au benchmark du marché;
- ETF parmi les 30 % les plus forts sur 63 séances;
- repli récent sur EMA20 ou EMA50;
- RSI refroidi puis en redressement;
- retournement Heikin-Ashi rouge vers vert;
- clôture réelle au-dessus du sommet précédent;
- distance maximale d'une fois l'ATR au-dessus de l'EMA20;
- stop et objectifs calculés avec l'ATR;
- maximum de deux ETF par catégorie dans le rapport principal.

## Installation locale

Python 3.11 ou plus récent est recommandé.

```bash
python -m venv .venv
```

Windows :

```bash
.venv\Scripts\activate
pip install -r requirements.txt
python -m scanner.main
```

macOS ou Linux :

```bash
source .venv/bin/activate
pip install -r requirements.txt
python -m scanner.main
```

## GitHub Actions

Le fichier `.github/workflows/scan.yml` lance automatiquement le scanner du lundi au vendredi à 22 h 30 UTC, après la clôture nord-américaine.

Dans GitHub :

1. téléverser tout le contenu du projet en conservant les dossiers;
2. ouvrir `Settings`;
3. choisir `Secrets and variables`, puis `Actions`;
4. créer le secret `DISCORD_WEBHOOK_URL`;
5. ouvrir l'onglet `Actions`;
6. choisir `Scanner Swing ETF quotidien`;
7. cliquer sur `Run workflow` pour le premier test.

Ne jamais inscrire l'adresse du webhook directement dans le code.

## Configuration

Les réglages sont dans `config.yml`.

Pour analyser seulement le Canada :

```yaml
markets:
  CA: true
  US: false
```

Pour analyser seulement les États-Unis :

```yaml
markets:
  CA: false
  US: true
```

Principaux paramètres :

- `minimum_score`: score minimal sur 100;
- `minimum_price`: prix minimal d'un ETF;
- `minimum_average_dollar_volume`: volume financier moyen minimal par marché;
- `minimum_rs_percentile`: 70 conserve les 30 % les plus forts;
- `maximum_extension_atr`: empêche d'acheter un signal déjà trop étendu;
- `maximum_per_category`: limite les expositions très semblables dans le Top 15.

L'univers se trouve dans `data/etfs.csv`. Une ligne peut être désactivée en remplaçant `true` par `false`. Il est possible d'ajouter un ETF avec son symbole Yahoo Finance, son nom, son marché et sa catégorie.

## Résultats

Chaque exécution crée le dossier `output/` avec :

- `tous_les_signaux_etf.csv`;
- `top_etf_diversifie.csv`;
- `rapport_etf.md`;
- `univers_etf_utilise.csv`;
- `diagnostics.json`.

Ces fichiers sont conservés pendant 30 jours dans les artifacts GitHub Actions.

## Avertissement

Le scanner est un outil d'aide à l'analyse. Les signaux techniques ne constituent ni des recommandations personnalisées ni une garantie de rendement. Yahoo Finance est une source pratique, mais non un flux officiel destiné à l'exécution automatique d'ordres.
