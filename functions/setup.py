import nltk

def nltlk_setup():
    """Prüft und lädt die notwendigen NLTK-Datenpakete herunter."""
    required_packages = {
        "tokenizers/punkt": "punkt",
        "tokenizers/punkt_tab": "punkt_tab",
        "taggers/averaged_perceptron_tagger": "averaged_perceptron_tagger",
        "corpora/wordnet": "wordnet",
        "corpora/omw-1.4": "omw-1.4"
    }
    print("--- Überprüfe NLTK-Datenpakete ---")
    for path, package_id in required_packages.items():
        try:
            nltk.data.find(path)
        except LookupError:
            print(f"NLTK '{package_id}' Paket nicht gefunden. Lade herunter...")
            nltk.download(package_id)
            print(f"'{package_id}' Paket erfolgreich heruntergeladen.")
    print("--- NLTK-Setup abgeschlossen ---\n")