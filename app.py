# Was muss ich einstellen?
# - input/ = Berichte ablegen
# - matching/ = "sample_summary.xlsx" ablegen (bereits vorhanden). Muss die Metadaten (Unternehmensnamen, Branche, Land etc) ethalten. 
# - .env = GOOGLE_API_KEY="ABCDEFGHIJKLMNOPXYZ" muss gesetzt sein. Mit einem korrekten Key.
# - functions/suchbegriffe.json = Enthält die Suchbegriffe. Kann erweitert werden.  
# - config.py = Einstellen der Gemini Model Version


# Wo sind die Ergebnisse?
# - text_passages/analyse/AI/JSON_Reports = Anteile pro Unternehmen an Kategrien, sowie Metadaten des Unternehmens
# - text_passages/analyse/AI/Screenshots = Markierte Textstellen in den Berichten als PNG
# - text_passages/analyse/AI/Top_Down_Analyse/top_down_klassifizierungs_reort = Alle Aussagen mit Kategorie, Status (planned/done) etc.
 

import os
from dotenv import load_dotenv
from functions.setup import nltlk_setup
from config import input_ordner, text_passages_ordner, relevant_text_passages_ordner, analyse_ordner, gemini_model_version
from functions.analyze_measures import analyze_measures_and_smartness
from functions.AI_clustering import fuehre_top_down_klassifizierung_durch
from functions.deduplicate_statements import deduplicate_globally_per_file
from functions.find_actions_and_metrics import extract_details_from_passages
from functions.remove_empty_passages import bereinige_leere_passagen
from functions.robust_matching import behebe_zuordnungsfehler
from functions.screenshots import generate_screenshots
from functions.statistics import generate_company_jsons
from functions.status import status_setup
from functions.summary_stats import generate_global_summary
from functions.text_validation_gemini import text_validation_gemini
from functions.text_extraction import text_extraction
from functions.check_pdfs import clean_report_folder   
    
def main():
    if not os.path.isdir(input_ordner):
        os.makedirs(input_ordner, exist_ok=True)
        
    if not os.path.isdir(text_passages_ordner):
        os.makedirs(text_passages_ordner, exist_ok=True)
        
    if not os.path.isdir(relevant_text_passages_ordner):
        os.makedirs(relevant_text_passages_ordner, exist_ok=True)
          
    if not os.path.isdir(analyse_ordner):
        os.makedirs(analyse_ordner, exist_ok=True)
    
 
            

# ========= >> Setup << =========
# > Lädt alle benötigten NLTK Pakete.    
    nltlk_setup()
# > Erstelle die Status-Datei, um doppelte Bearbeitungen bei späterem Ausführen zu vermeiden.
    status_setup()
# > Entfernt Firmen aus dem Input-Ordner, welche nicht im STOXX 600 Katalog (2025) sind
    clean_report_folder(input_ordner, "matching/sample_summary.xlsx")
# ======= >> Setup Ende << =======    


    
# ========= >> Actions Identifikation << =========
# > Beginne mit Identifikation relevanter Stellen (+/- 5 Sätze) anhand von Keywords
    print(">>>> Starte mit text_extraction <<<<< ")
    text_extraction (input_ordner, text_passages_ordner)
# > Prüfe, ob innerhalb der Stellen, wo die Keywords stehen, auch Maßnahmen oder Metriken bzgl BioDiv genannt werden, oder ob nur das Keyword genannt wird. Wenn ja, gib die Action/Metric +/- 2 Sätze zurück (5 Sätze insg.).
    print(">>>> Starte mit text_validation_gemini <<<<< ")
    text_validation_gemini(gemini_model_version, text_passages_ordner,relevant_text_passages_ordner)
# > Entfernt alle nicht mehr relevanten Textpassagen.
    print(">>>> Starte mit bereinige_leere_passagen <<<<< ")
    bereinige_leere_passagen(relevant_text_passages_ordner)
# > Sucht nach Actions / Metrics innerhalb jeder Passage. Rückgabe nur ein Satz.
    print(">>>> Starte mit extract_details_from_passages <<<<< ")
    extract_details_from_passages(gemini_model_version, relevant_text_passages_ordner)
# > Entfernt doppelte Einträge
    print(">>>> Starte mit deduplicate_globally_per_file <<<<< ")
    deduplicate_globally_per_file(relevant_text_passages_ordner)
# ======= >> Ende Actions Identifikation << =======
 


# ========= >>Clustering mit AI << =========
    print(">>>> Starte mit fuehre_top_down_klassifizierung_durch <<<<< ")
    fuehre_top_down_klassifizierung_durch(gemini_model_version, relevant_text_passages_ordner, "matching/sample_summary.xlsx", "text_passages/analyse/AI")
    final_report_path = "text_passages/analyse/AI/Top_Down_Analyse/top_down_klassifizierungs_report.xlsx"
    behebe_zuordnungsfehler(report_path=final_report_path, summary_path="matching/sample_summary.xlsx")
# ========= >> ENDE AI Clustering << ========



# ========= >> VISUALS & Statistics << =========
    final_report_path = "text_passages/analyse/AI/Top_Down_Analyse/top_down_klassifizierungs_report.xlsx"
    global_summary_output_path = "text_passages/analyse/AI/globaler_summary_report.xlsx"
    generate_global_summary(data_path=final_report_path,output_path=global_summary_output_path)


    json_output_folder = "text_passages/analyse/AI/JSON_Reports"
    print(">>>> Starte mit generate_company_jsons <<<<< ")
    generate_company_jsons(data_path=final_report_path,output_folder=json_output_folder)

    screenshots_output_folder = "text_passages/analyse/AI/Screenshots"
    pdf_reports_folder = "input"
    print(">>>> Starte mit generate_screenshots <<<<< ")
    generate_screenshots(report_path=final_report_path,pdf_folder=pdf_reports_folder,output_folder=screenshots_output_folder)
# ====== >> Ende VISUALS << =======



# ========= >> Berechne Anteile neue / alte Aussagen & SMART Ziele << =========
    daten_ordner = "matching/aussagen"
    ergebnisse_ordner = daten_ordner
    analyze_measures_and_smartness(gemini_model_version, daten_ordner, ergebnisse_ordner)
# ====== >> Ende Berechne Anteile neue / alte Aussagen & SMART Ziele << =======





if __name__ == "__main__":
    main()