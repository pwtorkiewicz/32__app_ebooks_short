import streamlit as st
from openai import OpenAI
from dotenv import dotenv_values
import instructor
from pydantic import BaseModel, Field
from typing import List
import os
import requests # Do pobierania obrazów
from io import BytesIO # Do obsługi obrazów w pamięci
from fpdf import FPDF # Do generowania PDF
import io
from datetime import datetime # Do generowania unikalnej nazwy pliku

# Ładowanie klucza API z pliku .env
env = dotenv_values(".env")




# --- Modele Pydantic do strukturyzacji danych ---

class TitleAndSummary(BaseModel):
    """Model do przechowywania tytułu i zarysu fabuły."""
    title: str = Field(..., description="Kreatywny i chwytliwy tytuł opowiadania.")
    summary: str = Field(..., description="Zwięzły, jednoakapitowy opis fabuły opowiadania.")

class Scene(BaseModel):
    """Model pojedynczej sceny w opowiadaniu."""
    scene_title: str = Field(..., description="Tytuł sceny, np. 'Tajemnicze odkrycie'.")
    scene_description: str = Field(..., description="Szczegółowy opis tego, co dzieje się w scenie, kto bierze w niej udział i gdzie się rozgrywa.")

class StoryScenes(BaseModel):
    """Lista kluczowych scen w opowiadaniu."""
    scenes: List[Scene] = Field(..., description="Lista 5 do 7 kluczowych scen, które tworzą spójną historię.")

# --- Funkcje pomocnicze ---

def generate_title_and_summary(topic: str):
    """Generuje tytuł i podsumowanie na podstawie tematu."""
    try:
        response = instructor_openai_client.chat.completions.create(
            model="gpt-4o-mini",
            response_model=TitleAndSummary,
            messages=[
                {"role": "system", "content": f"{writer_desc}."},
                {"role": "user", "content": f"Wygeneruj tytuł i zarys fabuły dla opowiadania o tematyce: {topic}"}
            ]
        )
        return response.title, response.summary
    except Exception as e:
        st.error(f"Błąd podczas generowania tytułu i opisu: {e}")
        return None, None

def generate_scenes(title: str, summary: str):
    """Generuje listę scen na podstawie tytułu i podsumowania."""
    try:
        response = instructor_openai_client.chat.completions.create(
            model="gpt-4o-mini",
            response_model=StoryScenes,
            messages=[
                {"role": "system", "content": f"Jesteś scenarzystą. Twoim zadaniem jest podzielenie historii na kluczowe sceny. Zachowaj styl {style}"},
                {"role": "user", "content": f"Na podstawie poniższego tytułu i opisu, stwórz listę 5-7 kluczowych scen, które budują narrację.\n\nTytuł: {title}\n\nOpis: {summary}"}
            ]
        )
        return response.scenes
    except Exception as e:
        st.error(f"Błąd podczas generowania scen: {e}")
        return []

def generate_story(title: str, scenes: List[Scene]):
    """Generuje pełne opowiadanie na podstawie scen."""
    scenes_description = "\n".join([f"**Scena: {s.scene_title}**\n{s.scene_description}" for s in scenes])
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"{writer_desc}."},
                {"role": "user", "content": f"Napisz pełne opowiadanie bez tytułu na podstawie poniższych wytycznych.\n\nTytuł: {title}\n\nSceny:\n{scenes_description}"}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Błąd podczas generowania opowiadania: {e}")
        return ""

def generate_illustration(prompt: str):
    """Generuje ilustrację za pomocą DALL-E 3."""
    try:
        response = instructor_openai_client.images.generate(
            model="dall-e-3",
            prompt=f"Utwórz cyfrową ilustrację w stylu {Image_style}, oddającą atmosferę i nastrój: {atmospher_style}. Opis sceny: {prompt}",
            n=1,
            size="1024x1024", # Można zmienić na "1024x1792" lub "1792x1024" dla innych proporcji
            quality="standard" # lub "hd" dla lepszej jakości (droższe)
        )
        return response.data[0].url
    except Exception as e:
        st.error(f"Błąd podczas generowania ilustracji: {e}")
        return None

# --- Funkcja do generowania PDF ---
class PDF(FPDF):
    def header(self):
        pass # Można dodać niestandardowy nagłówek

    def footer(self):
        self.set_y(-15)
        # Użycie czcionki dodanej w `create_story_pdf`
        # Sprawdzenie czy czcionka DejaVu została dodana
        font_name = "DejaVu" if "dejavu" in self.font_family.lower() else self.font_family
        self.set_font(font_name, "I", 8)
        self.cell(0, 10, f"Strona {self.page_no()}/{{nb}}", 0, 0, "C")

def create_story_pdf(title, story_text, scenes, illustration_urls):
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.alias_nb_pages()

    # Ścieżki do plików czcionek (umieść pliki .ttf w katalogu ze skryptem)
    font_regular_path = "DejaVuSans.ttf"
    font_bold_path = "DejaVuSans-Bold.ttf"
    font_italic_path = "DejaVuSans-Oblique.ttf"
    font_to_use = "Arial" # Domyślna, jeśli DejaVu nie jest dostępna

    try:
        if os.path.exists(font_regular_path) and os.path.exists(font_bold_path) and os.path.exists(font_italic_path):
            pdf.add_font("DejaVu", "", font_regular_path, uni=True)
            pdf.add_font("DejaVu", "B", font_bold_path, uni=True)
            pdf.add_font("DejaVu", "I", font_italic_path, uni=True)
            font_to_use = "DejaVu"
        else:
            st.warning(
                "Nie znaleziono plików czcionek DejaVu (np. DejaVuSans.ttf) w katalogu projektu. "
                "Polskie znaki w PDF mogą nie być wyświetlane poprawnie. "
                "Pobierz czcionki DejaVu i umieść je w głównym katalogu projektu."
            )
    except RuntimeError as e:
        st.warning(f"Błąd podczas ładowania czcionki DejaVu: {e}. Używam domyślnej czcionki (Arial).")

    pdf.add_page()

    # Tytuł opowiadania
    pdf.set_font(font_to_use, "B", 20)
    pdf.multi_cell(0, 10, title, 0, "C")
    pdf.ln(10)

    # Tekst opowiadania
    pdf.set_font(font_to_use, "", 12)
    pdf.multi_cell(0, 10, story_text)
    pdf.ln(10)
    if pdf.get_y() > (pdf.h - pdf.b_margin - 270 ): # Sprawdzenie miejsca przed nową sceną (wysokość orientacyjna)
             pdf.add_page()
    # Sceny i Ilustracje
    pdf.set_font(font_to_use, "B", 16)
    pdf.multi_cell(0, 10, "Rozdziały i Ilustracje", 0, "L")
    pdf.ln(5)

    for i, scene in enumerate(scenes):
        if pdf.get_y() > (pdf.h - pdf.b_margin - 70): # Sprawdzenie miejsca przed nową sceną (wysokość orientacyjna)
             pdf.add_page()

        # Tytuł sceny
        pdf.set_font(font_to_use, "B", 14)
        pdf.multi_cell(0, 10, f"{i+1}. {scene.scene_title}", 0, "L")
        pdf.ln(2)

        # Opis sceny
        pdf.set_font(font_to_use, "", 12)
        pdf.multi_cell(0, 8, scene.scene_description)
        pdf.ln(5)

        # Ilustracja
        if i < len(illustration_urls) and illustration_urls[i]:
            try:
                if pdf.get_y() > (pdf.h - pdf.b_margin - 80): # Sprawdzenie miejsca na obraz (orientacyjnie 80mm)
                    pdf.add_page()

                response = requests.get(illustration_urls[i], timeout=20) # Zwiększony timeout
                response.raise_for_status()
                img_bytes = BytesIO(response.content)
                
                img_max_width = pdf.w - pdf.l_margin - pdf.r_margin - 10 # Z marginesami
                
                # FPDF może mieć problem z niektórymi obrazami bez rozszerzenia, spróbujmy nadać mu nazwę
                # Dodajemy obraz bezpośrednio z BytesIO
                pdf.image(img_bytes, x=None, y=None, w=img_max_width, type='JPEG' if illustration_urls[i].lower().endswith(".jpg") or illustration_urls[i].lower().endswith(".jpeg") else 'PNG' if illustration_urls[i].lower().endswith(".png") else '')
                pdf.ln(5)
            except requests.exceptions.RequestException as e:
                pdf.set_font(font_to_use, "I", 10)
                pdf.multi_cell(0, 8, f"[Nie udało się załadować ilustracji: {e}]")
                pdf.ln(5)
            except Exception as e: # Inne błędy związane z obrazem
                pdf.set_font(font_to_use, "I", 10)
                pdf.multi_cell(0, 8, f"[Błąd podczas przetwarzania ilustracji: {e}]")
                pdf.ln(5)
        pdf.ln(5) # Dodatkowy odstęp po scenie

# Zwraca bajty PDF
    try:
        output = pdf.output(dest="S")
        if isinstance(output, bytearray):
            pdf_output_bytes = bytes(output) # Konwersja bytearray na bytes
        elif isinstance(output, str): # Na wypadek, gdyby zwracał string (mało prawdopodobne z dest="S" w fpdf2)
            pdf_output_bytes = output.encode('latin1') # lub 'utf-8'
        elif isinstance(output, bytes):
             pdf_output_bytes = output # Już jest w poprawnym formacie
        else:
            st.error(f"Nieoczekiwany typ danych z pdf.output: {type(output)}")
            return None
    except Exception as e:
        st.error(f"Błąd podczas finalizowania PDF: {e}")
        return None
    return pdf_output_bytes


# --- Interfejs użytkownika Streamlit ---

st.set_page_config(page_title="Generator Opowiadań AI", layout="wide", initial_sidebar_state="expanded")

# OpenAI API key protection
if not st.session_state.get("openai_api_key"):
    if "OPENAI_API_KEY" in env:
        st.session_state["openai_api_key"] = env["OPENAI_API_KEY"]

    else:
        st.info("Dodaj swój klucz API OpenAI aby móc korzystać z tej aplikacji")
        st.session_state["openai_api_key"] = st.text_input("Klucz API", type="password")
        if st.session_state["openai_api_key"]:
            st.rerun()

if not st.session_state.get("openai_api_key"):
    st.stop()

# Inicjalizacja klienta OpenAI z biblioteką instructor
# Umożliwia to strukturyzowane odpowiedzi w formacie Pydantic

instructor_openai_client = instructor.from_openai(OpenAI(api_key=st.session_state["openai_api_key"]))
client = OpenAI(api_key=st.session_state["openai_api_key"])

st.title("🧙‍♂️ Generator Opowiadań z Ilustracjami")
st.markdown("Stwórz własne, unikalne opowiadanie z pomocą sztucznej inteligencji. Podaj temat, a my zajmiemy się resztą!")


# Inicjalizacja stanu sesji
if 'stage' not in st.session_state:
    st.session_state.stage = 0
if 'illustrations' not in st.session_state: # Inicjalizacja listy ilustracji
    st.session_state.illustrations = []


def set_stage(stage):
    st.session_state.stage = stage

# KROK 1: Podanie tematu
with st.sidebar:
    st.header("Panel Sterowania")
    topic = st.text_area("Wpisz tematykę opowiadania:", "Zaginiony artefakt w magicznym lesie, strzeżony przez starożytne stworzenia.", height=100)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Wybierz styl opowiadania")
        # Pole wyboru dla zmiennej 'style'
        style_options = ['Szekspira', 'Fantasy', 'Science-fiction', 'Norwida', 'Zbigniewa Herberta', 'Fiodor Dostojewski', 'INNE']
        style = st.selectbox("Wybierz styl:", style_options)
        # Jeśli wybrano "INNE", wyświetl pole tekstowe
        if style == "INNE":
            custom_style = st.text_input("Wprowadź własny styl:")
            if custom_style:  # Upewnij się, że pole nie jest puste
                style = custom_style
        st.write(f"Wybrany styl: {style}")

    with col2:
        st.subheader("Wybierz pisarza")
        # Pole wyboru pisarza
        writer_options = ["Innowacyjność i wszechstronność", "Głębia i unikalność", "Wizjonerstwo i dynamiczność", "Uniwersalność"]
        writer = st.selectbox("Wybierz pisarza:", writer_options)
        # Jeśli wybrano 
        if writer == "Innowacyjność i wszechstronność":
            writer_desc = f"Jesteś światowej klasy, wysoce kreatywnym pisarzem, zdolnym do generowania innowacyjnych treści w dowolnym stylu literackim. Twoje dzieła muszą być oryginalne, angażujące i inspirujące, przekraczając granice konwencji. Dąż do zaskoczenia i pobudzenia wyobraźni. Twórz w stylu {style}"
        elif writer == "Głębia i unikalność":
            writer_desc = f"Jesteś geniuszem literackim i niezrównanym pisarzem. Twoją misją jest tworzenie hipnotyzujących i intrygujących fabuł, które wyróżniają się głębią, oryginalnością i emocjonalnym rezonansem. Każde dzieło powinno zawierać ziarno nowej, nieodkrytej historii, gotowej do rozwinięcia. Twórz w stylu {style}"
        elif writer == "Wizjonerstwo i dynamiczność":
            writer_desc = f"Jesteś wizjonerskim i globalnie cenionym mistrzem pióra, który specjalizuje się w tworzeniu dynamicznych i porywających fabuł. Twoim zadaniem jest przekształcanie idei w iskrzące narracje, które natychmiastowo chwytają uwagę i pozostawiają niezatarte wrażenie. Skup się na innowacji i sile przekazu. Twórz w stylu {style}."
        else:
            writer_desc = f"Jesteś światowej sławy, niezmiernie kreatywnym pisarzem. Generujesz innowacyjne i porywające fabuły w stylu {style}, które inspirują i zaskakują swoją oryginalnością."

        st.write(f"Wybrany pisarz: {writer_desc}")



    if st.button("Rozpocznij przygodę!", on_click=set_stage, args=(1,)):
        # Resetowanie poprzednich danych jeśli zaczynamy od nowa z tym samym tematem
        keys_to_reset = ['title', 'summary', 'scenes', 'story', 'illustrations']
        for key in keys_to_reset:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.illustrations = [] # Ponowna inicjalizacja
        pass

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Wybierz styl Ilustracji")
        # Pole wyboru dla stylu ilustracji
        Image_options = ['fantasy', 'fcience-fiction', 'steampunk', 'cyberpunk', 'fotorealizm', 'akwarela', 'komiks', 'manga', 'anime', 'Van Gogha', 'Salvadora Dalego']
        Image_style = st.selectbox("Wybierz styl:", Image_options)
        st.write(f"Styl ilustracji: {Image_style}")

    with col2:
        st.subheader("Wybierz atmosferę ilustracji")
        # Pole wyboru atmosfery ilustracji
        atmospher_options = ["mroczny", "radosny", "tajemniczy", "epicki", "spokojny", "dynamiczny", "dramatyczny", "nostalgiczny"]
        atmospher_style = st.selectbox("Wybierz atmosferę ilustracji:", atmospher_options)
        st.write(f"Atmosfera i nastrój: {atmospher_style}")
# Tworzenie zakładek
tab1, tab2, tab3, tab4 = st.tabs(["Przygotowanie opowiadania", "Opowiadanie", "Tworzenie pdf", "Tworzenie audio"])

with tab1:
    # KROK 2: Generowanie i edycja tytułu/opisu
    if st.session_state.stage >= 1:
        st.header("Krok 1: Tytuł i Zarys Fabuły")
        if 'title' not in st.session_state or st.session_state.stage == 1: # Generuj tylko raz lub gdy stage to wymusza
            with st.spinner("Czaruję tytuł i zarys fabuły... ✨"):
                title, summary = generate_title_and_summary(topic)
                if title and summary:
                    st.session_state.title = title
                    st.session_state.summary = summary
                    st.session_state.stage = 2 # Automatyczne przejście do następnego etapu
                else:
                    st.session_state.stage = 0 # Wróć jeśli błąd
        
        if 'title' in st.session_state and 'summary' in st.session_state:
            st.session_state.title = st.text_input("Tytuł:", st.session_state.title)
            st.session_state.summary = st.text_area("Opis:", st.session_state.summary, height=150)
            
            if st.button("Zatwierdź i generuj sceny ➡️", on_click=set_stage, args=(3,)):
                pass

    # KROK 3: Generowanie i edycja scen
    if st.session_state.stage >= 3:
        st.header("Krok 2: Kluczowe Sceny")
        if 'scenes' not in st.session_state or st.session_state.stage == 3:
            with st.spinner("Kreuję kluczowe sceny opowieści... 🎬"):
                scenes = generate_scenes(st.session_state.title, st.session_state.summary)
                if scenes:
                    st.session_state.scenes = scenes
                    st.session_state.stage = 4
                else:
                    st.session_state.stage = 2 # Wróć jeśli błąd
        
        if 'scenes' in st.session_state:
            for i, scene in enumerate(st.session_state.scenes):
                with st.expander(f"Rozdział {i+1}: {scene.scene_title}", expanded=True):
                    new_title = st.text_input(f"Rozdział {i+1}", scene.scene_title, key=f"title_{i}")
                    new_desc = st.text_area(f"Opis rozdziału {i+1}", scene.scene_description, key=f"desc_{i}", height=120)
                    # Aktualizacja w locie może być problematyczna bez odpowiedniego callbacka,
                    # lepiej aktualizować listę obiektów Scene
                    if new_title != scene.scene_title or new_desc != scene.scene_description:
                        st.session_state.scenes[i] = Scene(scene_title=new_title, scene_description=new_desc)
            
            if st.button("Zatwierdź i napisz opowiadanie ➡️", on_click=set_stage, args=(5,)):
                pass

    # KROK 4: Generowanie i edycja opowiadania
    if st.session_state.stage >= 5:
        st.header("Krok 3: Twoje Opowiadanie")
        if 'story' not in st.session_state or st.session_state.stage == 5:
            with st.spinner("Pióro samo pisze historię... 📜"):
                story = generate_story(st.session_state.title, st.session_state.scenes)
                if story:
                    st.session_state.story = story
                    st.session_state.stage = 6
                else:
                    st.session_state.stage = 4 # Wróć jeśli błąd
        
        if 'story' in st.session_state:
            st.session_state.story = st.text_area("Edytuj swoje opowiadanie:", st.session_state.story, height=400)
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Zatwierdź i generuj ilustracje ➡️", on_click=set_stage, args=(7,)):
                    pass
            with col2:
                # Przycisk do rozpoczęcia od nowa
                st.markdown("---")
                if st.button("✨ Stwórz nową historię od początku ✨"):
                    keys_to_clear = list(st.session_state.keys())
                    for key in keys_to_clear:
                        if key != 'stage': # Zachowaj 'stage' aby uniknąć pętli
                                del st.session_state[key]
                    st.session_state.illustrations = [] # Wyraźnie wyczyść listę
                    set_stage(0) # Zresetuj etap
                    st.rerun()  


    # KROK 5: Generowanie ilustracji
    if st.session_state.stage >= 7:
        st.header("Krok 4: Ilustracje")
        # Generuj ilustracje tylko jeśli jeszcze nie istnieją lub jeśli etap został jawnie ustawiony na 7
        if 'illustrations' not in st.session_state or not st.session_state.illustrations or st.session_state.stage == 7:
            if 'scenes' in st.session_state:
                with st.spinner("Artysta-mag maluje obrazy... 🎨 (To może chwilę potrwać)"):
                    illustrations_temp = []
                    prompts = [f"{s.scene_title}: {s.scene_description}" for s in st.session_state.scenes]
                    
                    progress_bar = st.progress(0)
                    total_scenes = len(prompts)

                    for i, prompt in enumerate(prompts):
                        st.info(f"Generowanie ilustracji do sceny {i+1}/{total_scenes}: {st.session_state.scenes[i].scene_title}...")
                        image_url = generate_illustration(prompt)
                        # Nawet jeśli image_url jest None, dodajemy placeholder, aby zachować kolejność
                        illustrations_temp.append(image_url if image_url else "error") # "error" lub None jako placeholder
                        progress_bar.progress((i + 1) / total_scenes)

                    st.session_state.illustrations = illustrations_temp
                    st.session_state.stage = 8 # Przejdź do następnego etapu po zakończeniu generowania
                    st.success("Wszystkie ilustracje zostały (lub próbowano je) wygenerować!")
                    st.balloons()
            else:
                st.error("Brak scen do wygenerowania ilustracji.")
                st.session_state.stage = 6 # Wróć, jeśli nie ma scen
with tab2:
    # KROK 6: Wyświetlanie finalnego rezultatu
    if st.session_state.stage >= 8:
        st.header("🎉 Twoja Ukończona Historia! 🎉")
        st.divider()

        # Wyświetl Tytuł
        if 'title' in st.session_state:
            st.subheader(st.session_state.title)
        # Wyświetl Pełne Opowiadanie
        if 'story' in st.session_state:
            st.markdown(st.session_state.story)
            st.markdown("---")
        else:
            st.warning("Brak wygenerowanego opowiadania.")

        # Wyświetl Sceny i Ilustracje
        st.subheader("Sceny i Ilustracje")
        if 'scenes' in st.session_state:
            for i, scene in enumerate(st.session_state.scenes):
                st.markdown(f"### Scena {i+1}: {scene.scene_title}")
                st.write(scene.scene_description)
                
                # Sprawdzenie, czy ilustracje istnieją i czy jest ilustracja dla tej sceny
                if 'illustrations' in st.session_state and i < len(st.session_state.illustrations):
                    img_url = st.session_state.illustrations[i]
                    if img_url and img_url != "error":
                        try:
                            st.image(img_url, caption=f"Ilustracja do sceny: {scene.scene_title}", use_column_width=True)
                        except Exception as e:
                            st.warning(f"Nie udało się wyświetlić ilustracji dla sceny '{scene.scene_title}'. URL: {img_url}. Błąd: {e}")
                    elif img_url == "error":
                        st.warning(f"Wystąpił błąd podczas generowania ilustracji dla sceny: {scene.scene_title}")
                    else: # img_url is None
                        st.info(f"Brak ilustracji dla sceny: {scene.scene_title} (nie wygenerowano).")
                else:
                    st.info(f"Brak informacji o ilustracji dla sceny: {scene.scene_title}")
                st.markdown("---") # Separator po każdej scenie
        else:
            st.warning("Brak scen do wyświetlenia.")
with tab3:   
    # Przycisk pobierania PDF
    if 'title' in st.session_state and 'story' in st.session_state and 'scenes' in st.session_state and 'illustrations' in st.session_state:
        if st.button("Pobierz opowiadanie jako PDF 📄"):
            with st.spinner("Przygotowuję PDF... Może to chwilę potrwać, zwłaszcza z obrazami. ⏳"):
                pdf_file_name = f"{st.session_state.title.replace(' ', '_').replace('.', '').lower()}_opowiadanie.pdf"
                
                # Filtrujemy ilustracje, które nie są 'error' lub None
                valid_illustrations = [url for url in st.session_state.illustrations if url and url != "error"]
                
                # Jeśli sceny i ilustracje mają różne długości (np. błędy w generowaniu),
                # musimy przekazać do PDF tylko te ilustracje, które faktycznie istnieją
                # Dla uproszczenia, create_story_pdf obsłuży brakujące URL-e
                
                pdf_bytes = create_story_pdf(
                    st.session_state.title,
                    st.session_state.story,
                    st.session_state.scenes, # Przekazujemy wszystkie sceny
                    st.session_state.illustrations # Przekazujemy wszystkie URL-e (funkcja PDF obsłuży błędy)
                )
                if pdf_bytes:
                    st.download_button(
                        label="Pobierz PDF gotowy!",
                        data=pdf_bytes,
                        file_name=pdf_file_name,
                        mime="application/pdf"
                    )
                else:
                    st.error("Nie udało się wygenerować pliku PDF.")

with tab4:
    # KROK 7: Audio

    # Opcje głosu
    voice_options = {
        "Alloy": "alloy",
        "Echo": "echo",
        "Fable": "fable",
        "Onyx": "onyx",
        "Nova": "nova",
        "Shimmer": "shimmer",
        "Coral": "coral"
    }


    # Przycisk do generowania audio
    if st.session_state.get('story'):
        selected_voice = st.selectbox("Wybierz głos:", list(voice_options.keys()))
        if st.button("Generuj Audio"):
            with st.spinner("Generowanie audio... proszę czekać."):
                try:
                    # Generowanie audio za pomocą OpenAI TTS
                    # Domyślny model to 'tts-1', ale możesz użyć 'tts-1-hd' dla wyższej jakości
                    response = client.audio.speech.create(
                        model="tts-1",
                        voice=voice_options[selected_voice],
                        input=st.session_state.story,
                    )

                    # Zapisanie audio do zmiennej w pamięci (obiekt BytesIO)
                    # Zamiast zapisywać do pliku, co jest bardziej efektywne w Streamlit
                    audio_bytes_io = io.BytesIO()
                    for chunk in response.iter_bytes(chunk_size=4096):
                        audio_bytes_io.write(chunk)
                    audio_bytes_io.seek(0) # Przewiń na początek pliku

                    # Zapisz audio w session_state
                    st.session_state['audio_data'] = audio_bytes_io
                    st.session_state['audio_generated'] = True
                    st.success("Audio wygenerowane pomyślnie!")

                except Exception as e:
                    st.error(f"Wystąpił błąd podczas generowania audio: {e}")
                    st.session_state['audio_generated'] = False

    # Wyświetlanie odtwarzacza audio, jeśli audio zostało wygenerowane
    if 'audio_generated' in st.session_state and st.session_state['audio_generated']:
        if 'audio_data' in st.session_state:
            st.subheader("Odtwarzacz Opowiadania")
            st.audio(st.session_state['audio_data'], format="audio/mpeg")
            st.write("Możesz teraz odtworzyć wygenerowane audio.")

            # --- Przycisk do pobierania pliku ---
            # Użyj kopii danych, aby nie zakłócać odtwarzania, jeśli BytesIO jest używane do pobierania
            audio_data_for_download = st.session_state['audio_data'].getvalue()

            # Generuj unikalną nazwę pliku
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            download_filename = f"opowiadanie_tts_{current_time}.mp3"

            st.download_button(
                label="Pobierz plik audio",
                data=audio_data_for_download,
                file_name=download_filename,
                mime="audio/mpeg"
            )
            # --- Koniec przycisku do pobierania ---

        else:
            st.error("Błąd: Dane audio nie zostały znalezione w sesji.")

    st.markdown("---")







