
# Last Updated Extractor — Desktop (double-click)

Acest pachet creează un **executabil** care, la dublu-click, pornește UI-ul (Streamlit) în browser.

## Cerințe pentru build
- Python 3.11+
- `pip install -r requirements.txt`
- `pip install pyinstaller`

## Build (Windows sau macOS)
```bash
pyinstaller --noconsole --onefile launcher.py
# sau, alternativ:
# pyinstaller launcher.spec
```

După build, vei avea un executabil `dist/LastUpdatedExtractor` (pe Windows: `LastUpdatedExtractor.exe`).

Pune în același folder cu exe-ul:
- `app_streamlit.py` (din acest pachet)

La **primul rulaj**, programul va descărca Chromium pentru Playwright (poate dura puțin).

## Rulare (End-user)
- Dublu click pe `LastUpdatedExtractor.exe`
- Se deschide automat UI-ul în browser: `http://localhost:8501`
- Încarci Excel / lipești linkuri, setezi `limit/offset`, rulezi, descarci Excel.

## Notă
Dacă folosești antivirus/EDR strict, semnează codul sau creează o regulă de allowlist pentru exe.
