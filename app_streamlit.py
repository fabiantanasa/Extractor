
import re, json, time, os, io
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from playwright.sync_api import sync_playwright
import streamlit as st

st.set_page_config(page_title="Last Updated Extractor (Custom)", page_icon="🗓️", layout="wide")

st.title("🗓️ Last Updated Extractor — Custom")
st.caption("Extrage data ultimei actualizări. Acum cu separare clară față de data publicării și cu expresii/zone personalizate pentru căutare.")

# -------------------------------
# Date parsing helpers (RO + EN)
# -------------------------------
EN_MONTHS = {
    "january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
    "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
    "jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"sept":9,"oct":10,"nov":11,"dec":12,
}
RO_MONTHS = {
    "ianuarie":1,"februarie":2,"martie":3,"aprilie":4,"mai":5,"iunie":6,
    "iulie":7,"august":8,"septembrie":9,"octombrie":10,"noiembrie":11,"decembrie":12
}

def try_parse_date(text):
    if not text:
        return None
    t = text.strip()
    # remove "Jan." -> "Jan"
    t = re.sub(r"\b([A-Za-z]{3})\.\b", r"\1", t)
    # US formats e.g. "March 5, 2023" or "Mar 5, 2023"
    for fmt in ["%B %d, %Y", "%b %d, %Y"]:
        try:
            return datetime.strptime(t, fmt).date().isoformat()
        except Exception:
            pass
    # "5 March 2023"
    m = re.match(r"^\s*(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})\s*$", t)
    if m:
        d, mon, y = m.groups()
        mm = EN_MONTHS.get(mon.lower().rstrip("."))
        if mm:
            try:
                return datetime(int(y), mm, int(d)).date().isoformat()
            except Exception:
                pass
    # "5 martie 2023"
    m = re.match(r"^\s*(\d{1,2})\s+([A-Za-zăâîșț]+)\s+(\d{4})\s*$", t, flags=re.IGNORECASE)
    if m:
        d, mon, y = m.groups()
        mm = RO_MONTHS.get(mon.lower())
        if mm:
            try:
                return datetime(int(y), mm, int(d)).date().isoformat()
            except Exception:
                pass
    # ISO-like "2024-06-01T.." or "2024-06-01"
    if re.match(r"^\d{4}-\d{2}-\d{2}", t):
        return t[:10]
    # Trim prefix if it's like "Updated March 5, 2023 at 10:00"
    m = re.match(r"^([A-Za-z]{3,9}\s+\d{1,2},\s*\d{4})", t)
    if m:
        return try_parse_date(m.group(1))
    return None

def extract_from_html(html):
    # <span class="last-updated"><span class="date"> ... </span></span>
    m = re.search(r'<span[^>]*class="[^"]*last-updated[^"]*"[^>]*>.*?<span[^>]*class="[^"]*date[^"]*"[^>]*>([^<]+)</span>', html, flags=re.IGNORECASE|re.DOTALL)
    if m:
        iso = try_parse_date(m.group(1))
        if iso:
            return ("html-last-updated-date", iso)
    # Last Updated on <span class="date">...</span>
    m = re.search(r'Last\s*Updated\s*on\s*<[^>]*class="[^"]*date[^"]*"[^>]*>([^<]+)</', html, flags=re.IGNORECASE)
    if m:
        iso = try_parse_date(m.group(1))
        if iso:
            return ("html-last-updated-inline", iso)
    # Last Updated: March 5, 2023 / 5 martie 2023
    m = re.search(r'Last\s*Updated\s*(?:on|:|-)?\s+([A-Za-z]{3,9}\.? \d{1,2}, \d{4}|\d{1,2}\s+[A-Za-zăâîșț]{3,20}\s+\d{4})', html, flags=re.IGNORECASE)
    if m:
        iso = try_parse_date(m.group(1))
        if iso:
            return ("html-text", iso)
    return (None, None)

def extract_from_dom_text(soup):
    for sel in [".meta .last-updated .date", ".last-updated .date"]:
        el = soup.select_one(sel)
        if el:
            iso = try_parse_date(el.get_text(" ", strip=True))
            if iso:
                return ("dom-last-updated-date", iso)
    wrap = soup.select_one(".last-updated")
    if wrap:
        cand = wrap.get_text(" ", strip=True)
        cand = re.sub(r"(?i)last\s*updated\s*(on|:|-)?", "", cand).strip(" -:")
        iso = try_parse_date(cand)
        if iso:
            return ("dom-last-updated", iso)
    for selector in [".entry-meta", ".byline", "article", "body"]:
        el = soup.select_one(selector)
        if not el:
            continue
        txt = el.get_text(" ", strip=True).replace("—","-").replace("–","-")
        m = re.search(r"(last\s*updated|updated)\s*(?:on|:|-)?\s+([A-Za-z]{3,9}\.? \d{1,2}, \d{4}|\d{1,2}\s+[A-Za-zăâîșț]{3,20}\s+\d{4}|\d{1,2}\s+[A-Za-z]{3,9}\.?\s+\d{4})", txt, flags=re.IGNORECASE)
        if m:
            iso = try_parse_date(m.group(2))
            if iso:
                return ("text", iso)
    return (None, None)

def from_meta_jsonld(soup, disallow_same_as_published=True):
    """Returnează (source, last_updated_iso, published_iso). last_updated_iso poate fi None.
    NU consideră datePublished/uploadDate ca 'Last Updated'.
    """
    published_iso = None
    # Meta tags – candidate de modificare
    for sel in [
        ('meta', {'property':'article:modified_time'}),
        ('meta', {'property':'og:updated_time'}),
        ('meta', {'name':'modified'}),
        ('meta', {'itemprop':'dateModified'}),
        ('meta', {'name':'last-modified'}),
        ('meta', {'http-equiv':'last-modified'}),
    ]:
        tag = soup.find(*sel)
        if tag and tag.get('content'):
            iso = try_parse_date(tag['content'])
            if iso:
                return ("meta", iso, published_iso)

    # time.updated / itemprop=dateModified
    t = soup.find('time', class_=lambda c: c and 'updated' in c) or soup.find('time', itemprop='dateModified')
    if t:
        cand = t.get('datetime') or t.get_text(" ", strip=True)
        iso = try_parse_date(cand)
        if iso:
            return ("time", iso, published_iso)

    # JSON-LD
    def walk(obj):
        if isinstance(obj, dict):
            yield obj
            for v in obj.values():
                yield from walk(v)
        elif isinstance(obj, list):
            for it in obj:
                yield from walk(it)

    last_upd_iso = None
    for s in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(s.string)
        except Exception:
            continue
        for node in walk(data):
            if isinstance(node, dict):
                # publicare (doar pentru comparație/raportare)
                if isinstance(node.get("datePublished"), str):
                    p = try_parse_date(node["datePublished"])
                    if p and not published_iso:
                        published_iso = p
                # modificare: DOAR aceste chei
                for key in ("dateModified","dateUpdated","lastModified"):
                    val = node.get(key)
                    if isinstance(val, str):
                        iso = try_parse_date(val)
                        if iso:
                            if not last_upd_iso or iso > last_upd_iso:
                                last_upd_iso = iso

    if last_upd_iso:
        if disallow_same_as_published and published_iso and last_upd_iso == published_iso:
            return (None, None, published_iso)
        return ("jsonld", last_upd_iso, published_iso)

    return (None, None, published_iso)

def extract_custom(soup, keywords, selectors=None):
    """
    Caută etichete personalizate urmate de o dată.
    keywords: list[str] – ex: ["Reviewed", "Actualizat", "Last Updated"]
    selectors: list[str] sau None – în ce zone să caute; dacă None, caută în body.
    Returnează (source, iso) sau (None, None).
    """
    if not keywords:
        return (None, None)

    kw_escaped = [re.escape(k.strip()) for k in keywords if k.strip()]
    if not kw_escaped:
        return (None, None)
    kw_group = "(?:" + "|".join(kw_escaped) + ")"

    # pattern dată (EN/RO)
    date_pat = r"([A-Za-z]{3,9}\.? \d{1,2}, \d{4}|\d{1,2}\s+[A-Za-zăâîșț]{3,20}\s+\d{4}|\d{4}-\d{2}-\d{2})"
    pattern = re.compile(kw_group + r"\s*(?:on|:|-)?\s+" + date_pat, flags=re.IGNORECASE)

    areas = []
    if selectors:
        for sel in selectors:
            for el in soup.select(sel.strip()):
                areas.append(el.get_text(" ", strip=True))
    else:
        body = soup.select_one("body") or soup
        areas = [body.get_text(" ", strip=True)]

    for text in areas:
        text = text.replace("—","-").replace("–","-")
        m = pattern.search(text)
        if m:
            iso = try_parse_date(m.group(1))
            if iso:
                return ("custom-text", iso)
    return (None, None)

def fetch(context, url, debug=False, published_fallback=False, custom_keywords_list=None, custom_selectors_list=None, disallow_same_as_published=True):
    page = context.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
    published_iso_for_row = None
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        for sel in ["#onetrust-accept-btn-handler", "button[aria-label='Accept all']", "text=Accept All", "text=Accept"]:
            try:
                page.locator(sel).click(timeout=1000)
            except Exception:
                pass
        try:
            page.wait_for_selector(".meta", timeout=8000)
        except Exception:
            pass
        header_html = ""
        try:
            header_html = page.eval_on_selector(".meta", "el => el.outerHTML")
        except Exception:
            pass
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        if header_html:
            src, date = extract_from_html(header_html)
            if date:
                return {"url": url, "last_updated": date, "source": src, "error": None, "published": published_iso_for_row}

        src, date = extract_from_html(html)
        if date:
            return {"url": url, "last_updated": date, "source": src, "error": None, "published": published_iso_for_row}

        # META/JSON-LD – strict pe "modified", nu pe "published"
        src, date, published_iso = from_meta_jsonld(soup, disallow_same_as_published=disallow_same_as_published)
        if published_iso:
            published_iso_for_row = published_iso
        if date:
            return {"url": url, "last_updated": date, "source": src, "error": None, "published": published_iso_for_row}

        src, date = extract_from_dom_text(soup)
        if date:
            return {"url": url, "last_updated": date, "source": src, "error": None, "published": published_iso_for_row}

        # Căutare custom (dacă user a dat keywords)
        if custom_keywords_list:
            src, date = extract_custom(soup, custom_keywords_list, selectors=custom_selectors_list)
            if date:
                return {"url": url, "last_updated": date, "source": src, "error": None, "published": published_iso_for_row}

        if published_fallback:
            for sel in [".meta .date", "time[datetime]", "time[class*='published']", "time[itemprop='datePublished']"]:
                el = soup.select_one(sel)
                if el:
                    cand = el.get("datetime") or el.get_text(" ", strip=True)
                    iso = try_parse_date(cand)
                    if iso:
                        return {"url": url, "last_updated": iso, "source": "fallback-published", "error": None, "published": published_iso_for_row}

        err = "No last-updated date found"
        if debug:
            try:
                snippet = soup.get_text(" ", strip=True)[:600]
                err += f". Snippet: {snippet}"
            except Exception:
                pass
        return {"url": url, "last_updated": None, "source": None, "error": err, "published": published_iso_for_row}
    except Exception as e:
        return {"url": url, "last_updated": None, "source": None, "error": str(e), "published": published_iso_for_row}
    finally:
        page.close()

def run_extraction(df, url_col, limit, offset, published_fallback=False, debug=False, sleep_between=0.15,
                   custom_keywords="", custom_selectors="", disallow_same_as_published=True):
    urls_all = df[url_col].dropna().astype(str).tolist()
    urls = urls_all[offset: offset + limit] if (limit and limit > 0) else urls_all[offset:]
    df_out = df.copy()
    for col in ("last_updated", "source", "error", "published"):
        if col not in df_out.columns:
            df_out[col] = None

    # Parse custom inputs
    ck_list = [x.strip() for x in re.split(r"[,\n]+", custom_keywords or "") if x.strip()]
    cs_list = [x.strip() for x in (custom_selectors.split(",") if custom_selectors else []) if x.strip()]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York",
            viewport={"width": 1366, "height": 768},
            device_scale_factor=1.0
        )
        progress = st.progress(0.0, text="Se procesează URL-urile...")
        for i, url in enumerate(urls, start=1):
            res = fetch(context, url, debug=debug, published_fallback=published_fallback,
                        custom_keywords_list=ck_list, custom_selectors_list=cs_list,
                        disallow_same_as_published=disallow_same_as_published)
            row_index = offset + (i - 1)
            df_out.at[row_index, "last_updated"] = res["last_updated"]
            df_out.at[row_index, "source"] = res["source"]
            df_out.at[row_index, "error"] = res["error"]
            df_out.at[row_index, "published"] = res.get("published")
            progress.progress(i / max(1, len(urls)), text=f"[{i}/{len(urls)}] {url}")
            time.sleep(sleep_between)
        context.close()
        browser.close()

    progress.empty()
    return df_out

# -------------------------------
# Sidebar controls
# -------------------------------
with st.sidebar:
    st.header("Setări")
    limit = st.number_input("Limită (câte linkuri să procesez)", min_value=0, value=50, step=1, help="0 înseamnă fără limită")
    offset = st.number_input("Offset (de unde să încep)", min_value=0, value=0, step=1)
    published_fallback = st.checkbox("Folosește data publicării dacă 'Last Updated' lipsește (fallback explicit)", value=False)
    disallow_same = st.checkbox("Ignoră 'Last Updated' dacă e identică cu data publicării", value=True)
    debug = st.checkbox("Debug (include fragmente de text în erori)", value=False)
    sleep_between = st.slider("Pauză între URL-uri (secunde)", 0.0, 2.0, 0.15, 0.05)

    st.divider()
    st.subheader("Căutare personalizată")
    custom_keywords = st.text_area(
        "Cuvinte/expresii pentru detecția 'Last Updated' (separate prin virgulă sau linie nouă)",
        value="Last Updated, Updated, Reviewed, Actualizat, Revizuit",
        help="Se caută aceste etichete urmate de o dată. Acceptă și regex-uri simple (vor fi escape-uite literal)."
    )
    custom_selectors = st.text_input(
        "Selectori CSS (opțional, separați prin virgulă)",
        value="",
        help="Ex: .meta, .entry-meta, header.article-header. Dacă e gol, caută în tot documentul."
    )

# -------------------------------
# Input area (Excel sau listă manuală)
# -------------------------------
tab1, tab2 = st.tabs(["📁 Încarcă Excel", "📝 Lipește linkuri"])

df_input = None
url_column_name = None

with tab1:
    uploaded = st.file_uploader("Încarcă un fișier Excel", type=["xlsx", "xls"])
    if uploaded is not None:
        try:
            df_input = pd.read_excel(uploaded)
            st.success(f"Am citit {len(df_input)} rânduri.")
            url_cols = [c for c in df_input.columns if "url" in c.lower()] or list(df_input.columns)
            url_column_name = st.selectbox("Coloana cu URL-uri", url_cols)
            st.dataframe(df_input.head(20))
        except Exception as e:
            st.error(f"Nu am putut citi Excelul: {e}")

with tab2:
    pasted = st.text_area("Lipește o listă de linkuri (unul pe linie)", height=180, placeholder="https://exemplu.ro/articol-1\nhttps://exemplu.ro/articol-2")
    if pasted.strip():
        links = [ln.strip() for ln in pasted.splitlines() if ln.strip()]
        df_input = pd.DataFrame({"url": links})
        url_column_name = "url"
        st.success(f"Am preluat {len(df_input)} linkuri.")
        st.dataframe(df_input.head(20))

# -------------------------------
# Run extraction
# -------------------------------
if df_input is not None and url_column_name:
    st.divider()
    if st.button("Rulează extragerea", type="primary"):
        with st.spinner("Rulez Playwright și extrag datele..."):
            out_df = run_extraction(
                df_input, url_column_name, limit, offset,
                published_fallback, debug, sleep_between,
                custom_keywords=custom_keywords, custom_selectors=custom_selectors,
                disallow_same_as_published=disallow_same
            )
        st.success("Gata! Vezi rezultatele mai jos.")
        st.dataframe(out_df)
        # Download as Excel
        buf = io.BytesIO()
        try:
            out_df.to_excel(buf, index=False, engine="openpyxl")
        except Exception:
            out_df.to_excel(buf, index=False)
        buf.seek(0)
        st.download_button("Descarcă Excel cu rezultate", data=buf, file_name="last_updated_results.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.info("Sugestie: pe Linux/CI, rulează: `playwright install chromium` și (opțional) `playwright install-deps` înainte de a porni aplicația.")
