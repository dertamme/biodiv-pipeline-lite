import os
import time
from dotenv import load_dotenv
import google.generativeai as genai
import json
import nltk
from functions.status import load_status, save_status

prompt_extraction = """
You are a highly intelligent text analysis assistant specializing in corporate sustainability reports.
Your task is to analyze the following numbered list of sentences and identify which ones describe a specific, tangible action or a measurable metric related to biodiversity undertaken **by the reporting company itself**.

**CRITICAL INSTRUCTIONS:**
1.  **Analyze the numbered list:** The user will provide a list of sentences, each with a number (index).
2.  **Identify relevant sentences:** Read through the sentences and find only those that describe a concrete company action (e.g., "we planted 1,000 trees") or a specific metric (e.g., "we monitor species X").
3.  **Ignore general statements:** Do NOT select sentences that are general statements, definitions, or descriptions of global frameworks (e.g., "Biodiversity is important," "The framework calls for...").
4.  **Return only the numbers:** Your response must be a JSON object with a single key "key_sentence_indices", which holds a list of the **NUMBERS (indices)** of the sentences you identified.

**EXAMPLE:**
Provided Text:
1. Biodiversity is crucial for our planet.
2. In line with our new policy, we have started reforesting 150 hectares near our main facility.
3. The Kunming-Montreal Global Biodiversity Framework sets ambitious goals.
4. We will monitor the return of native bird species as a key success metric.

**CORRECT JSON-OUTPUT:**
{{
  "key_sentence_indices": [2, 4]
}}
---
Analyze the following numbered sentences and provide the JSON output.

**Numbered Sentences:**
{numbered_sentences}
"""



# Stellt sicher, dass das NLTK-Paket für die Satzerkennung vorhanden ist.
def nltk_setup():
    """Prüft und lädt das notwendige NLTK-Datenpaket 'punkt' herunter."""
    try:
        nltk.data.find("tokenizers/punkt")
    except LookupError:
        print("NLTK 'punkt' Paket nicht gefunden. Lade herunter...")
        nltk.download("punkt", quiet=True)
        print("'punkt' Paket heruntergeladen.")

nltk_setup()

load_dotenv()
CURRENT_STAGE_KEY_GEMINI_VALIDATION = "relevant_text_passages_processing"



api_cache: dict[str, list[int]] = {}


def get_key_sentence_indices_from_api(gemini_model_version, passage_text: str) -> list[int]:
    try:
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        gemini_model = genai.GenerativeModel(gemini_model_version)
    except Exception as e:
        print(f"Fehler bei der Konfiguration der Gemini API: {e}")
        gemini_model = None

    # Liest JSONs, identifiziert Kern-Sätze per Index, baut Kontextfenster und schreibt die Ergebnisse in neue Output-JSONs.
    if gemini_model is None:
        print("Gemini-Modell nicht initialisiert.")
        return
    # Identifiziert relevante Sätze mittels KI und gibt deren Indizes zurück.
   
    # Zerlegt den Text in Sätze
    all_sentences = nltk.sent_tokenize(passage_text)
    if not all_sentences:
        return []

    # Erstellt einen nummerierten String für den Prompt
    numbered_sentences_str = "\n".join(f"{i+1}. {s}" for i, s in enumerate(all_sentences))
    
    # Cache-Schlüssel ist der nummerierte Text, um Eindeutigkeit zu gewährleisten
    cache_key = numbered_sentences_str
    if cache_key in api_cache:
        return api_cache[cache_key]

    prompt_text = prompt_extraction.format(numbered_sentences=numbered_sentences_str)
    generation_config = {"response_mime_type": "application/json"}
    
    max_versuche = 3
    # Schleife für die API-Aufrufe
    for versuch in range(max_versuche):
        try:
            response = gemini_model.generate_content(prompt_text, generation_config=generation_config)
            raw = response.text.strip()
            
            if raw:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and "key_sentence_indices" in parsed:
                    # Konvertiere Indizes (die 1-basiert vom Prompt kommen) in 0-basierte Indizes für Python
                    indices = [int(i) - 1 for i in parsed["key_sentence_indices"]]
                    api_cache[cache_key] = indices
                    return indices
        except Exception as e:
            print(f"  Warnung bei API-Aufruf (Versuch {versuch + 1}/{max_versuche}): {e}")
            if versuch < max_versuche - 1:
                time.sleep(5)
            continue
    
    print(f"  Fehler: Passage konnte nach {max_versuche} Versuchen nicht verarbeitet werden.")
    return []


def build_context_passages(all_sentences: list[str], key_indices: list[int], window_size: int = 2) -> list[str]:
    """
    Baut Kontextfenster um die gegebenen Kern-Satz-Indizes.
    """
    if not key_indices:
        return []

    final_passages = []
    processed_indices = set()

    # Sortiere die Indizes, um die Passagen in der richtigen Reihenfolge zu erstellen
    key_indices.sort()

    # Schleife über jeden von der KI identifizierten Index
    for key_index in key_indices:
        if key_index in processed_indices:
            continue

        start_index = max(0, key_index - window_size)
        end_index = min(len(all_sentences), key_index + window_size + 1)
        
        context_window_sentences = all_sentences[start_index:end_index]
        final_passages.append(" ".join(context_window_sentences))
        
        # Markiere alle Sätze in diesem Fenster als verarbeitet, um Überlappungen zu vermeiden
        for i in range(start_index, end_index):
            processed_indices.add(i)
            
    return final_passages


def text_validation_gemini(gemini_model_version, basis_ordner: str, relevanter_ordner_pfad: str) -> None:


    input_folder = os.path.join(basis_ordner, "biodiv_text_passages")
    output_folder = relevanter_ordner_pfad
    os.makedirs(output_folder, exist_ok=True)

    # Schleife über alle Dateien im Input-Ordner
    for fname in os.listdir(input_folder):
        if not (fname.lower().endswith(".json") and not load_status(fname, CURRENT_STAGE_KEY_GEMINI_VALIDATION)):
            continue

        print(f"\n--- Validiere Text aus Datei: {fname} ---")
        fpath = os.path.join(input_folder, fname)

        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print(f"  Ungültige JSON in '{fname}' – übersprungen.")
            continue

        all_context_passages_for_file = []
        # Schleife über jede Passage in der Eingabedatei
        for p in data.get("extracted_passages", []):
            original_passage_text = p.get("passage_text", "")
            if not original_passage_text:
                continue
            
            # Zerlege den Originaltext in Sätze
            all_sentences = nltk.sent_tokenize(original_passage_text)
            if not all_sentences:
                continue

            # Schritt 1: Kern-Satz-Indizes mit der KI identifizieren
            key_indices = get_key_sentence_indices_from_api(gemini_model_version, original_passage_text)
            
            # Schritt 2: Kontextfenster um die Indizes bauen
            context_passages = build_context_passages(all_sentences, key_indices, window_size=2)
            
            if context_passages:
                all_context_passages_for_file.append({
                    "page_range": p.get("page_range", "Unbekannt"),
                    "passage_text": context_passages,
                    "found_keywords": p.get("found_keywords", [])
                })

        if all_context_passages_for_file:
            out_data = {"biodiversity_passages": all_context_passages_for_file}
            out_path = os.path.join(output_folder, f"{os.path.splitext(fname)[0]}_relevant_passages.json")
            with open(out_path, "w", encoding="utf-8") as out_f:
                json.dump(out_data, out_f, ensure_ascii=False, indent=4)
            print(f"  Kontext-Passagen für '{fname}' extrahiert und gespeichert.")
        
        save_status(fname, CURRENT_STAGE_KEY_GEMINI_VALIDATION)