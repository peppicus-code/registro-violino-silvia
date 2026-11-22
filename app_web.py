import streamlit as st
import json
import requests
from datetime import datetime
from fpdf import FPDF

st.set_page_config(page_title="Registro Lezioni di Violino - Silvia", page_icon="🎻", layout="wide")

# --- 1. CONNESSIONE AL DATABASE GITHUB GIST ---
GIST_ID = st.secrets["gist_id"]
GITHUB_TOKEN = st.secrets["github_token"]
FILENAME = "archivio_allievi_violino_silvia.json"

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def carica_dati():
    if "db" not in st.session_state:
        try:
            url = "https://api.github.com/gists/" + GIST_ID
            res = requests.get(url, headers=HEADERS, timeout=15)
            if res.status_code == 200:
                files = res.json().get("files", {})
                if FILENAME in files:
                    contenuto = files[FILENAME]["content"]
                elif files:
                    primo_file = next(iter(files.values()))
                    contenuto = primo_file["content"]
                else:
                    contenuto = "{}"
                dati_grezzi = json.loads(contenuto)
                if "_config" not in dati_grezzi:
                    dati_grezzi = {
                        "_config": {"password_docente": st.secrets["password_docente_iniziale"]},
                        "allievi": dati_grezzi if isinstance(dati_grezzi, dict) else {}
                    }
                if "allievi" not in dati_grezzi or not isinstance(dati_grezzi["allievi"], dict):
                    dati_grezzi["allievi"] = {}
                st.session_state["db"] = dati_grezzi
            else:
                st.session_state["db"] = {
                    "_config": {"password_docente": st.secrets["password_docente_iniziale"]},
                    "allievi": {}
                }
        except Exception as e:
            st.error(f"Errore di connessione al database: {e}")
            st.session_state["db"] = {
                "_config": {"password_docente": st.secrets["password_docente_iniziale"]},
                "allievi": {}
            }
    return st.session_state["db"]

def salva_dati_cloud(db_aggiornato):
    st.session_state["db"] = db_aggiornato
    url = "https://api.github.com/gists/" + GIST_ID
    payload = {
        "files": {
            FILENAME: {
                "content": json.dumps(db_aggiornato, ensure_ascii=False, indent=4)
            }
        }
    }
    try:
        res = requests.patch(url, headers=HEADERS, json=payload, timeout=15)
        if res.status_code != 200:
            st.error(f"⚠️ Errore durante il salvataggio online (codice {res.status_code})!")
    except Exception as e:
        st.error(f"⚠️ Errore di rete durante il salvataggio: {e}")

db = carica_dati()
allievi = db["allievi"]

# --- 2. SISTEMA DI LOGIN E RECUPERO PASSWORD ---
def controlla_accesso():
    if "ruolo" not in st.session_state:
        st.session_state["ruolo"] = None
        st.session_state["utente_loggato"] = None

    if st.session_state["ruolo"] is None:
        st.title("🎻 Registro Lezioni di Violino - Silvia")
        st.subheader("Accesso Riservato - Classe di Violino")

        with st.form("form_login"):
            pwd = st.text_input("Inserisci la tua password personale:", type="password")
            accedi = st.form_submit_button("Accedi", type="primary")

        if accedi:
            pwd_pulita = pwd.strip()
            pwd_docente_attuale = db["_config"].get(
                "password_docente",
                db["_config"].get("password_maestro", st.secrets["password_docente_iniziale"])
            )

            if pwd_pulita and pwd_pulita == pwd_docente_attuale:
                st.session_state["ruolo"] = "docente"
                st.session_state["utente_loggato"] = "Silvia"
                st.rerun()

            allievo_trovato = None
            for nome_allievo, info in allievi.items():
                pwd_allievo = info.get("password", "").strip()
                if pwd_pulita and pwd_allievo and pwd_pulita == pwd_allievo:
                    allievo_trovato = nome_allievo
                    break

            if allievo_trovato:
                st.session_state["ruolo"] = "studente"
                st.session_state["utente_loggato"] = allievo_trovato
                st.rerun()
            else:
                st.error("❌ Password non riconosciuta. Controlla di averla scritta correttamente.")

        st.markdown("---")
        with st.expander("❓ Hai dimenticato la password?"):
            st.info("🎓 **Sei un Allievo?** Chiedi alla Prof.ssa Silvia durante la lezione o via messaggio: può visualizzare o reimpostare la tua password in pochi secondi dalla sua area riservata.")

            st.markdown("🎻 **Sei Silvia (Docente)?** Inserisci il Codice di Emergenza (PIN) per impostare una nuova password:")
            with st.form("form_reset_docente"):
                pin_inserito = st.text_input("Codice di Emergenza (PIN):", type="password")
                nuova_pwd_docente = st.text_input("Nuova password Docente:", type="password")
                conferma_pwd_docente = st.text_input("Ripeti nuova password Docente:", type="password")
                reset_btn = st.form_submit_button("Reimposta Password Docente")

            if reset_btn:
                pin_corretto = st.secrets.get("pin_recupero_docente", "")
                if not pin_corretto or pin_inserito.strip() != pin_corretto:
                    st.error("❌ Codice di emergenza errato.")
                elif not nuova_pwd_docente.strip():
                    st.error("❌ Inserisci una nuova password valida.")
                elif nuova_pwd_docente.strip() != conferma_pwd_docente.strip():
                    st.error("❌ Le due password non coincidono.")
                else:
                    db["_config"]["password_docente"] = nuova_pwd_docente.strip()
                    salva_dati_cloud(db)
                    st.success("✅ Password Docente reimpostata con successo! Ora puoi accedere qui sopra.")
        st.stop()

controlla_accesso()
is_docente = (st.session_state["ruolo"] == "docente")

# --- 3. GENERAZIONE PDF ---
def pulisci_testo_pdf(testo):
    for k, v in {"’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "..."}.items():
        testo = testo.replace(k, v)
    return testo.encode("latin-1", "replace").decode("latin-1")

def crea_pdf_bytes(nome_allievo, dati):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 11, pulisci_testo_pdf(f"VIOLINO (Prof.ssa Silvia) - {nome_allievo}"), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 11)
    info_riga = f"Livello: {dati.get('livello') or '---'}  |  Orario: {dati.get('orario') or '---'}  |  Data: {dati.get('data') or '---'}"
    pdf.cell(0, 7, pulisci_testo_pdf(info_riga), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf.set_fill_color(245, 247, 250)
    pdf.set_draw_color(180, 190, 200)
    pdf.set_font("Helvetica", "B", 10)
    riga_tecnica_pdf = (
        f"METRONOMO: {dati.get('bpm') or '---'}  |  "
        f"COLPI D'ARCO: {dati.get('colpi_arco') or '---'}  |  "
        f"INTONAZIONE / POSIZIONI: {dati.get('intonazione') or '---'}"
    )
    pdf.multi_cell(0, 8, pulisci_testo_pdf(riga_tecnica_pdf), border=1, new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.ln(6)

    for titolo, chiave in [("TECNICA, SCALE ED ESERCIZI", "tecnica"), ("BRANI IN STUDIO E OBIETTIVI", "brani")]:
        pdf.set_fill_color(230, 238, 248)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 9, pulisci_testo_pdf(f"  {titolo}"), new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 12)
        pdf.multi_cell(0, 7, pulisci_testo_pdf(dati.get(chiave) or "Nessuna nota inserita."))
        pdf.ln(5)

    pdf.set_fill_color(230, 238, 248)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 9, pulisci_testo_pdf("  COMPITI PER CASA (Spuntare al controllo)"), new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 12)

    if dati.get("compiti"):
        for riga in dati["compiti"].splitlines():
            riga_pulita = riga.strip()
            if riga_pulita:
                x_box = pdf.get_x() + 2
                y_box = pdf.get_y() + 1.5
                pdf.rect(x_box, y_box, 4, 4)
                pdf.set_x(x_box + 7)
                pdf.multi_cell(0, 7, pulisci_testo_pdf(riga_pulita))
                pdf.ln(1)
    else:
        pdf.multi_cell(0, 7, "Nessun compito assegnato.")

    return bytes(pdf.output())

# --- 4. BARRA LATERALE ---
with st.sidebar:
    if is_docente:
        st.title("🎻 Area Docente - Silvia")

        with st.form("form_aggiungi_allievo", clear_on_submit=True):
            nuovo_nome = st.text_input("Nome e Cognome Allievo...")
            nuova_pwd_allievo = st.text_input("Password iniziale per l'allievo...")
            aggiungi_btn = st.form_submit_button("➕ Aggiungi Allievo", type="primary", use_container_width=True)

        if aggiungi_btn:
            nome_pulito = nuovo_nome.strip()
            pwd_all_pulita = nuova_pwd_allievo.strip()
            if not nome_pulito:
                st.warning("Inserisci il nome dell'allievo.")
            elif nome_pulito in allievi:
                st.warning("Allievo già presente!")
            else:
                db["allievi"][nome_pulito] = {
                    "password": pwd_all_pulita,
                    "livello": "", "orario": "", "telefono": "",
                    "data": datetime.now().strftime("%d/%m/%Y"),
                    "bpm": "", "colpi_arco": "", "intonazione": "",
                    "tecnica": "", "brani": "", "compiti": "",
                    "storico": []
                }
                salva_dati_cloud(db)
                st.session_state["allievo_attivo"] = nome_pulito
                st.rerun()

        st.divider()
        st.subheader("I tuoi allievi")
        lista_nomi = sorted(allievi.keys())
        if not lista_nomi:
            st.info("Nessun allievo in lista.")
            allievo_selezionato = None
        else:
            indice_default = 0
            if "allievo_attivo" in st.session_state and st.session_state["allievo_attivo"] in lista_nomi:
                indice_default = lista_nomi.index(st.session_state["allievo_attivo"])
            allievo_selezionato = st.radio(
                "Seleziona allievo:",
                lista_nomi,
                index=indice_default,
                label_visibility="collapsed"
            )
            st.session_state["allievo_attivo"] = allievo_selezionato
    else:
        allievo_selezionato = st.session_state["utente_loggato"]
        st.title("🎻 Area Allievo")
        st.success(f"Benvenuto/a, **{allievo_selezionato}**")
        st.caption("Stai visualizzando esclusivamente il tuo piano di studio di Violino con la Prof.ssa Silvia.")

    st.divider()
    with st.expander("🔑 Cambia la mia Password"):
        with st.form("form_cambia_pwd", clear_on_submit=True):
            nuova_pass = st.text_input("Nuova password:", type="password")
            conferma_pass = st.text_input("Ripeti nuova password:", type="password")
            aggiorna_pwd_btn = st.form_submit_button("Aggiorna Password", use_container_width=True)

        if aggiorna_pwd_btn:
            np = nuova_pass.strip()
            if not np:
                st.error("La password non può essere vuota.")
            elif np != conferma_pass.strip():
                st.error("Le due password non coincidono.")
            else:
                gia_usata = (np == db["_config"].get("password_docente")) or any(
                    info.get("password") == np for k, info in allievi.items() if k != allievo_selezionato
                )
                if gia_usata:
                    st.error("Questa password non è disponibile, scegline un'altra.")
                else:
                    if is_docente:
                        db["_config"]["password_docente"] = np
                    else:
                        db["allievi"][allievo_selezionato]["password"] = np
                    salva_dati_cloud(db)
                    st.success("✅ Password aggiornata con successo!")

    if is_docente:
        with st.expander("💾 Backup Manuale (.json)"):
            json_str = json.dumps(db, ensure_ascii=False, indent=4)
            st.download_button(
                "⬇️ Scarica Archivio",
                data=json_str,
                file_name="archivio_violino_silvia.json",
                mime="application/json",
                use_container_width=True
            )

            file_caricato = st.file_uploader("⬆️ Ripristina da JSON", type=["json"])
            if file_caricato is not None:
                if st.button("Conferma Ripristino", use_container_width=True):
                    dati_importati = json.load(file_caricato)
                    if "_config" not in dati_importati:
                        dati_importati = {
                            "_config": {"password_docente": db["_config"]["password_docente"]},
                            "allievi": dati_importati
                        }
                    salva_dati_cloud(dati_importati)
                    st.success("Archivio ripristinato!")
                    st.rerun()

    if st.button("🚪 Esci (Logout)", use_container_width=True):
        st.session_state["ruolo"] = None
        st.session_state["utente_loggato"] = None
        st.rerun()

# --- 5. AREA PRINCIPALE ---
if not allievo_selezionato:
    st.title("🎻 Registro Lezioni di Violino - Silvia")
    st.info("👈 Crea o seleziona un allievo dalla barra a sinistra.")
else:
    dati_allievo = allievi[allievo_selezionato]

    col_titolo, col_storico = st.columns([2, 1])
    with col_titolo:
        st.title(f"Piano di Studio: {allievo_selezionato}")
    with col_storico:
        storico = dati_allievo.get("storico", [])
        opzioni_storico = ["📌 Scheda Attuale (In corso)"] + [
            f"{i+1}. {item.get('data_salvataggio', 'Senza data')}" for i, item in enumerate(storico)
        ]
        scelta_storico = st.selectbox("Storico lezioni:", opzioni_storico)

    if scelta_storico == "📌 Scheda Attuale (In corso)":
        dati_mostrati = dati_allievo
        in_storico = False
    else:
        indice_st = int(scelta_storico.split(".")[0]) - 1
        dati_mostrati = storico[indice_st]
        in_storico = True
        st.warning(f"Stai visualizzando una lezione archiviata ({scelta_storico}).")

    disabilitato = (not is_docente) or in_storico

    if is_docente:
        with st.expander("🔐 Gestione Password di questo Allievo"):
            pwd_corrente_allievo = st.text_input(
                "Password attuale dell'allievo (puoi vederla o reimpostarla qui se la dimentica):",
                value=dati_allievo.get("password", ""),
                disabled=in_storico
            )
    else:
        pwd_corrente_allievo = dati_allievo.get("password", "")

    c1, c2, c3, c4 = st.columns(4)
    livello = c1.text_input("Livello / Corso:", value=dati_mostrati.get("livello", ""), placeholder="Es. Base, Intermedio, Conservatorio...", disabled=disabilitato)
    orario = c2.text_input("Giorno e Ora Fissa:", value=dati_mostrati.get("orario", ""), placeholder="Es. Giovedì 16:30", disabled=disabilitato)
    telefono = c3.text_input("Telefono / Contatto:", value=dati_mostrati.get("telefono", ""), placeholder="Es. 333 1234567", disabled=disabilitato)
    data_lez = c4.text_input("Data Lezione:", value=dati_mostrati.get("data", ""), placeholder="Es. 22/11/2026", disabled=disabilitato)

    st.markdown("---")
    t1, t2, t3 = st.columns(3)
    bpm = t1.text_input("Metronomo (BPM):", value=dati_mostrati.get("bpm", ""), placeholder="Es. 72 -> 84 BPM", disabled=disabilitato)
    colpi_arco = t2.text_input("Colpi d'Arco:", value=dati_mostrati.get("colpi_arco", ""), placeholder="Es. Détaché, Legato, Martellato, Spiccato...", disabled=disabilitato)
    intonazione = t3.text_input("Intonazione / Posizioni:", value=dati_mostrati.get("intonazione", ""), placeholder="Es. 1ª-3ª posizione, cambi di posizione...", disabled=disabilitato)

    tecnica = st.text_area("Tecnica, Scale ed Esercizi:", value=dati_mostrati.get("tecnica", ""), height=100, disabled=disabilitato)
    brani = st.text_area("Brani in Studio e Obiettivi della Lezione:", value=dati_mostrati.get("brani", ""), height=130, disabled=disabilitato)
    compiti = st.text_area("Compiti per Casa (ogni riga diventa una casella da spuntare sul PDF):", value=dati_mostrati.get("compiti", ""), height=130, disabled=disabilitato)

    st.markdown("---")

    b1, b2, b3, b4 = st.columns([1.2, 1.4, 1.4, 1])

    pdf_pronto = crea_pdf_bytes(allievo_selezionato, {
        "livello": livello, "orario": orario, "data": data_lez,
        "bpm": bpm, "colpi_arco": colpi_arco, "intonazione": intonazione,
        "tecnica": tecnica, "brani": brani, "compiti": compiti
    })
    nome_file_pdf = f"Lezione_Violino_{allievo_selezionato.replace(' ', '_')}.pdf"
    b3.download_button("📄 Scarica PDF Lezione", data=pdf_pronto, file_name=nome_file_pdf, mime="application/pdf", use_container_width=True)

    if is_docente and not in_storico:
        if b1.button("💾 Salva Scheda", type="primary", use_container_width=True):
            db["allievi"][allievo_selezionato] = {
                "password": pwd_corrente_allievo.strip(),
                "livello": livello, "orario": orario, "telefono": telefono,
                "data": data_lez, "bpm": bpm, "colpi_arco": colpi_arco, "intonazione": intonazione,
                "tecnica": tecnica, "brani": brani, "compiti": compiti,
                "storico": dati_allievo.get("storico", [])
            }
            salva_dati_cloud(db)
            st.success(f"Scheda di {allievo_selezionato} salvata!")

        if b2.button("📚 Archivia nello Storico", use_container_width=True):
            etichetta_data = data_lez.strip() if data_lez.strip() else datetime.now().strftime("%d/%m/%Y %H:%M")
            copia_lezione = {
                "livello": livello, "orario": orario, "telefono": telefono,
                "data": data_lez, "bpm": bpm, "colpi_arco": colpi_arco, "intonazione": intonazione,
                "tecnica": tecnica, "brani": brani, "compiti": compiti,
                "data_salvataggio": etichetta_data
            }
            storico_att = dati_allievo.get("storico", [])
            storico_att.append(copia_lezione)
            db["allievi"][allievo_selezionato] = {
                **copia_lezione,
                "password": pwd_corrente_allievo.strip(),
                "storico": storico_att
            }
            salva_dati_cloud(db)
            st.success(f"Lezione del {etichetta_data} archiviata nello storico!")
            st.rerun()

        if b4.button("🗑️ Elimina Allievo", use_container_width=True):
            del db["allievi"][allievo_selezionato]
            salva_dati_cloud(db)
            st.session_state["allievo_attivo"] = None
            st.rerun()
