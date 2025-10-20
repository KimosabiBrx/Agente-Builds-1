import json
import os
import re
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from flask import Flask, render_template, request, jsonify

load_dotenv() 

from google import genai
from google.genai.errors import APIError

try:
    client = genai.Client()
except Exception as e:

    print(f"ERROR: No se pudo inicializar el cliente de Gemini. Detalle: {e}")
    client = None

GEMINI_MODEL = "gemini-2.5-flash" 

SOURCE_PRYDWEN = "Prydwen"
SOURCE_GAME8 = "Game8" 
SOURCE_HONKAILAB = "HonkaiLab" 
SOURCE_GENSHINLAB = "GenshinLab" 
SOURCE_GENSHINBUILD = "GenshinBuilds" 
SOURCE_GAMEWITH = "GameWithJP"

HSR_CONFIG = {
    "game": "HSR",
    "primary_base_url": "https://www.prydwen.gg/star-rail/characters",
    "primary_path_segment": "/star-rail/characters/",
    "secondary_base_url": "https://game8.co/games/Honkai-Star-Rail",
    "secondary_path_segment": "/Honkai-Star-Rail-", 
    "tertiary_base_url": "https://honkailab.com/honkai-star-rail-characters/",
    "tertiary_path_segment": "/honkai-star-rail-characters/",
    
    "file_path": 'hsr_builds.json',
    "team_size": 4, 
    "build_schema": {
        "character_name": "",
        "game": "HSR",
        "source": "", 
        "build_name": "Mejor Build General (Analizada por Gemini)",
        "weapon_recommendations": [],
        "artifact_set_recommendations": [], 
        "planetary_set_recommendations": [],
        "main_stats_recommendations": {
            "body": "Cuerpo", 
            "feet": "Pies", 
            "planar_sphere": "Esfera", 
            "link_rope": "Cuerda"
        },
        "final_stats_targets": {
            "HP": "", "DEF": "", "ATK": "", "CRIT Rate": "", "CRIT DMG": "", 
            "SPD": "", "Energy Regen Rate": "", "Effect RES": "", 
            "Effect HIT Rate": "", "Break Effect": ""
        },
        "team_recommendations": [] 
    }
}

ZZZ_CONFIG = {
    "game": "ZZZ",
    "primary_base_url": "https://www.prydwen.gg/zenless/characters",
    "primary_path_segment": "/zenless/agents/", 
    "secondary_base_url": "https://game8.co/games/Zenless-Zone-Zero", 
    "secondary_path_segment": "/Zenless-Zone-Zero-", 
    "tertiary_base_url": "https://genshinlab.com/zenless-zone-zerozzz-characters/",
    "tertiary_path_segment": "/zenless-zone-zerozzz-characters/",
    
    "file_path": 'zzz_builds.json',
    "team_size": 3, 
    "build_schema": {
        "character_name": "",
        "game": "ZZZ",
        "source": "",
        "build_name": "Mejor Build General (Analizada por Gemini)",
        "weapon_recommendations": [],
        "artifact_set_recommendations": [],
        "main_stats_recommendations": {
            "head_drive": "Head Drive", 
            "hand_drive": "Hand Drive", 
            "feet_drive": "Feet Drive", 
            "core_drive": "Core Drive"
        },
        "final_stats_targets": {
            "HP": "", "DEF": "", "ATK": "", "CRIT Rate": "", "CRIT DMG": "",
            "Energy_Charge": "", "Impact_Rating": "", "Attribute_DMG": "",
            "Anomaly_Proficiency": ""
        },
        "team_recommendations": [] 
    }
}

GI_CONFIG = {
    "game": "GI",
    "primary_base_url": "https://genshin-builds.com/es/characters",
    "primary_path_segment": "/es/characters/",
    "secondary_base_url": "https://gamewith.jp/genshin/article/show/230360",
    "secondary_path_segment": "https://gamewith.jp/genshin/article/show/",
    "gamewith_id_map": { 
        "furina": "407254",
        "navia": "426179", 
        "neuvillette": "399451"
    },
    
    "file_path": 'gi_builds.json',
    "team_size": 4, 
    "build_schema": {
        "character_name": "",
        "game": "GI",
        "source": "", 
        "build_name": "Mejor Build General (Analizada por Gemini)",
        "weapon_recommendations": [],
        "artifact_set_recommendations": [], 
        "main_stats_recommendations": {
            "sands": "Arena del Tiempo", 
            "goblet": "Cáliz de Eonotemo", 
            "circlet": "Tiara de Logos"
        },
        "final_stats_targets": {
            "Vida": "", "ATK": "", "DEF": "", 
            "Probabilidad Critica": "", "Daño Critico": "", 
            "Maestria Elemental": "", "Recarga de Energía": ""
        },
        "team_recommendations": []
    }
}

###CONFE PRIMERA PARTE FUNCIONA :3

def analyze_text_with_gemini(game, character_name, text_content, build_schema, team_size, target_language_code="es"):

#Envia texto extraido a la API de Gemini para estructurar los datos y traducirlos al idioma especificado por el usuario
    
    if not client: return None

    if game == "HSR":
        game_terms = """
        **TÉRMINOS CLAVE HSR:**
        - Light Cone (Cono de Luz / Arma) - Relics (Reliquias / Set de 4 piezas)
        - Planar Ornaments (Ornamentos Planetarios / Set de 2 piezas)
        - Estadísticas Únicas: Effect RES, Effect HIT Rate, Break Effect, Energy Regen Rate.
        """
        team_type = "personajes"
    elif game == "ZZZ":
        game_terms = """
        **TÉRMINOS CLAVE ZZZ:**
        - W-Engine (Motor W / Arma) - Drives (Componentes de 4 piezas)
        - Sub/Core Drives (Componentes de 2 piezas)
        - Estadísticas Únicas: Impact Rating, Energy Charge, Anomaly Proficiency, Attribute DMG.
        """
        team_type = "agentes"
    else: 
        game_terms = """
        **TÉRMINOS CLAVE GI:**
        - Weapon (Arma) - Artifacts (Artefactos / Sets de 4 ó 2 piezas combinadas)
        - Artefactos con Main Stat variable: Sands (Arena del Tiempo), Goblet (Cáliz de Eonotemo), Circlet (Tiara de Logos).
        - Estadísticas Únicas: Maestria Elemental, Recarga de Energía.
        """
        team_type = "personajes"

    language_name = {
        "es": "ESPAÑOL", "en": "INGLÉS", "jp": "JAPONÉS", "cn": "CHINO", "fr": "FRANCÉS", 'cr': "COREANO"
    }.get(target_language_code.lower(), "ESPAÑOL")


    json_schema_content = json.dumps(build_schema, indent=4, ensure_ascii=False)
    
    #instrucciones de textito
    team_instruction = f"""Busca las 3 composiciones de equipo más relevantes y variadas que incluyan a '{character_name}'.
    Cada entrada en la lista 'team_recommendations' debe ser una única CADENA de texto, conteniendo los nombres de los **{team_size} {team_type}** separados por comas y TRADUCIDOS al {language_name}.
    Ejemplo para HSR/GI: ["Acheron, Sparkle, Pela, Lynx", "Blade, Bronya, Pela, Lynx"].
    Ejemplo para ZZZ: ["Billy, Nicole, Corin"].
    Si no encuentras 3 composiciones claras, usa la cadena "Equipo No Encontrado" para las entradas faltantes.

    **IMPORTANTE:** Si la fuente no proporciona estadísticas finales, rellena el diccionario 'final_stats_targets' con cadenas vacías ("").
    """
    
    #instrucciones de traduccion
    translation_instruction = f"""
    INSTRUCCIÓN DE LOCALIZACIÓN (CRÍTICA): Analiza el 'TEXTO A ANALIZAR'. Debes TRADUCIR y localizar todos los nombres de los ítems (sets, armas/conos/engines), estadísticas y nombres de personajes/agentes al IDIOMA **{language_name}** ({target_language_code}) en el JSON de salida.
    """
    
    prompt = f"""Eres un agente de recopilación de datos de videojuegos. Tu tarea es analizar el siguiente texto de una página de build del juego {game} del personaje/agente '{character_name}' y extraer las recomendaciones.

    {game_terms}
    {team_instruction}
    {translation_instruction}

    FORMATO DE SALIDA: Debes responder ÚNICAMENTE con un objeto JSON válido, sin ningún texto adicional, explicaciones o código.

    JSON SCHEMA (Solo proporciona los valores, no las claves estáticas):
    {json_schema_content}

    TEXTO A ANALIZAR:
    ---
    {text_content}
    ---
    """
    
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={"response_mime_type": "application/json"} 
        )
        llm_output_text = response.text.strip()

        if llm_output_text.startswith('```json'): 
            llm_output_text = llm_output_text[7:].strip().rstrip('`')
            
        return json.loads(llm_output_text)

    except APIError as e:
        print(f"Error de la API de Gemini: {e}")
        return None
    
    except json.JSONDecodeError:
        print(f"Error al parsear JSON de Gemini. Output inválido recibido.")
        return None
    except Exception as e:
        print(f"Error desconocido durante la llamada a Gemini: {e}")
        return None
    
##########

def clean_markdown_url(url):

    if not url:
        return url

    match = re.search(r'\(https?://[^\)]+\)', url)
    if match:
        return match.group(0).strip('()')

    url = url.replace('[', '').replace(']', '').replace('(', '').replace(')', '').replace('\"', '').strip()
    url = url.split(' ')[0]
    return url.strip()

###################

def get_character_url(base_url, character_name, path_segment, source_code):
    base_url = clean_markdown_url(base_url)
    target_name_normalized = character_name.strip().lower().replace(" ", "-").replace("_", "-").replace("'", "")
    target_name_simple = character_name.strip().lower()
    
    link_segment_check = ""
    
    if source_code == SOURCE_GAMEWITH:
        #Chequeo de Mapeo de IDs
        target_name_key = target_name_normalized.replace("-", "")
        # Acceder a la configuracion de GI para obtener el mapa de IDs
        gamewith_map = GI_CONFIG.get("gamewith_id_map", {})
        
        if target_name_key in gamewith_map:
              article_id = gamewith_map[target_name_key]
              full_url = f"https://gamewith.jp/genshin/article/show/{article_id}"
              print(f"Enlace de GameWith encontrado por ID (Bypass): {full_url}")
              return full_url

        link_segment_check = target_name_normalized 
        
    elif source_code == SOURCE_PRYDWEN:
        link_segment_check = f"{path_segment}{target_name_normalized}"
    elif source_code == SOURCE_HONKAILAB or source_code == SOURCE_GENSHINLAB: 
        link_segment_check = f"{target_name_normalized}-build"
    elif source_code == SOURCE_GENSHINBUILD: 
        link_segment_check = f"{path_segment}{target_name_normalized}"
    
    print(f"Buscando el enlace para el personaje: {character_name} en {base_url}")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
    
            page.goto(base_url, wait_until='domcontentloaded', timeout=90000) 
            
    #Ajuste de espera para contenido dinámico de Prydwen 
            if source_code == SOURCE_PRYDWEN:
    # Espera hasta 20 segundos para que aparezca cualquier enlace de pj
    # Esto es crucial para sitios como Prydwen que cargan la lista con JS
                selector_to_wait = 'a[href*="/agents/"], a[href*="/characters/"]'
                try:
                    page.wait_for_selector(selector_to_wait, timeout=20000)
                except Exception as e:
                    print(f"Advertencia: El selector de lista de Prydwen no apareció a tiempo. Fallback a 5s. Error: {e}")
                    page.wait_for_timeout(5000)
            else:
                page.wait_for_timeout(5000)

            html_content = page.content()
            browser.close()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            link = None
            
    # Si la URL base ya apunta a un artículo (como el caso de GameWith), devolvemos la URL base
            if source_code == SOURCE_GAMEWITH and base_url.count('/') > 4: 
                print(f"La URL base de GameWith ya parece ser la de un artículo: {base_url}")
                return base_url

    #ESTRATEGIA 1: Busqueda por slug en HREF
            if link_segment_check:
                link = soup.find('a', href=lambda href: href and link_segment_check in href)
    #ESTRATEGIA 2: Búsqueda por texto del enlace
            if not link:
                print(f"ℹFallback a búsqueda por texto para {source_code}.")
                
                selector_attrs = {'href': True}
                
                all_links = soup.find_all('a', **selector_attrs)
    # Normalizar el nombre buscado para coincidir con el texto del enlace
                search_text_normalized_tight = target_name_simple.replace(" ", "").replace("_", "").replace("'", "")
                
                for a in all_links:
                    link_text = a.get_text(strip=True).strip().lower()
                    link_text_normalized_tight = link_text.replace(" ", "").replace("_", "").replace("'", "")
                    
                    if link_text_normalized_tight == search_text_normalized_tight:
                        link = a
                        break
                    
                    if len(search_text_normalized_tight) > 3 and search_text_normalized_tight in link_text_normalized_tight:
                        if any(char.isalpha() for char in link_text): 
                            link = a
                            break

            if link:
                full_url = link['href']
                #Manejar URLs relativas
                if not full_url.startswith("http"):
                    if source_code == SOURCE_PRYDWEN:
                        full_url = "https://www.prydwen.gg" + full_url
                    elif source_code == SOURCE_HONKAILAB:
                        full_url = "https://honkailab.com" + full_url
                    elif source_code == SOURCE_GENSHINLAB:
                        full_url = "https://genshinlab.com" + full_url
                    elif source_code == SOURCE_GENSHINBUILD: 
                        full_url = "https://genshin-builds.com" + full_url
                    elif source_code == SOURCE_GAMEWITH: 
                        full_url = "https://gamewith.jp" + full_url 
                        
                full_url = clean_markdown_url(full_url)
                print(f"Enlace de build encontrado: {full_url}")
                return full_url
            else:
                print(f"No se encontró el enlace para '{character_name}'.")
                return None

    except Exception as e:
        print(f"Error en get_character_url para {source_code}: {e}")
        return None

####Descarga el contenido HTML de la URL del build usando Playwright
def fetch_and_parse(url, source_code):

    url = clean_markdown_url(url)
    
    print(f"Iniciando Playwright para la URL de build ({source_code}): {url}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            page.goto(url, wait_until='domcontentloaded', timeout=90000) 
            page.wait_for_timeout(5000)
            
    #Intento de manejo de pop-ups/cookies 
            cookie_selectors = ['text="Accept"', 'text="Aceptar"', 'text="I accept"', 'text="Consent"'] 
            try:
                for selector in cookie_selectors:
                    page.click(selector, timeout=100) 
            except:
                pass
                
            page.wait_for_selector('h1, article, body', timeout=15000) 
            page.wait_for_timeout(2000) 

            html_content = page.content()
            
            browser.close()
            
            print("Playwright completado con éxito.")
            return BeautifulSoup(html_content, 'html.parser')

    except Exception as e:
        print(f"Error al usar Playwright en {source_code}: {e}")
        return None
    

####Extrae el nombre del personaje, el texto de la build y llama a Gemini con el idioma objetivo
def extract_build_info(soup, target_character, current_config, source, target_language):
    
    final_build = current_config["build_schema"].copy()
    final_build["game"] = current_config["build_schema"]["game"]
    final_build["source"] = source
    final_build["character_name"] = target_character
    
    #Extracción del Bloque de Texto (para el LLM)
    try:
        #Intenta seleccionar osea la fuente del contenido
        if source == SOURCE_PRYDWEN:
             build_section = soup.find('div', id='page-content') or soup.main
        elif source == SOURCE_GAME8:
             build_section = soup.find('article', class_=re.compile(r'a-article')) or soup.main
        elif source == SOURCE_HONKAILAB or source == SOURCE_GENSHINLAB: 
             build_section = soup.find('div', class_='entry-content') or soup.main
        elif source == SOURCE_GENSHINBUILD: 
             build_section = soup.find('div', class_='main-content') or soup.find('article') or soup.main
        elif source == SOURCE_GAMEWITH: 
             build_section = soup.find('div', class_='gdb_col_content') or soup.find('div', id='page_content') or soup.main


        if not build_section:
             build_section = soup.body
        
        if build_section:
            full_build_text = build_section.get_text(separator=' ', strip=True)
            
            #Si el texto es demasiado corto, puede ser una página de error o muy genérica.
            if len(full_build_text) < 500: 
                print(f"El texto extraído de {source} es demasiado corto o genérico. Saltando análisis.")
                return final_build ###Devuelve un plantilla vacia
                
            
            print(f"-> Analizando {len(full_build_text)} caracteres de {source} con Gemini...")
            
            #llamada a Gemini para analizar y estructurar la build
            llm_results = analyze_text_with_gemini(
                final_build["game"], 
                final_build["character_name"], 
                full_build_text, 
                final_build,
                current_config["team_size"],
                target_language #pasadon el idioma 
            )
            
            if llm_results:
                #Actualizar la build con los resultados del LLM
                for key, value in llm_results.items():
                    if key in final_build:
                        final_build[key] = value
            
    except Exception as e:
        print(f"Error general en la extracción o análisis de la build: {e}")

    return final_build

###############analiza la consulta del usuario para detectar juego, personaje y componentes solicitados
def parse_user_query(query):
    query = query.lower().strip()
    
    #la detección del juego
    game = None
    if any(keyword in query for keyword in ["honkai", "star rail", "hsr"]):
        game = "HSR"
    elif any(keyword in query for keyword in ["zenless", "zzz", "zone zero", "zenles"]):
        game = "ZZZ"
    elif any(keyword in query for keyword in ["genshin", "impact", "gi"]): 
        game = "GI" 
        
    if not game:
        print("No se pudo detectar el juego. Asumiendo HSR por defecto (Honkai: Star Rail).")
        game = "HSR"

    #Extracción del Nombre del pj
    target_character = None
    #Define todos los términos a eliminar para que quede solo el nombre del personaje
    game_and_key_terms = r'\b(del|de|para|honkai|star\s*rail|zenless|zone\s*zero|zzz|y|o|hsr|genshin|impact|gi|build|general|completa|todo|discos|reliquias|artefactos|armas|arma|engine|cono|light\s*cone|stats|estadística|objetivo|target|final|substats|equipo|team|composición|partner|muestrame|quiero|la|el|los|las|un|una|y|teams|dame|vida|ataque|defensa|probabilidad\s*critica|daño\s*critico|maestria\s*elemental|w-engines|recarga\s*de\s*energía)\b'
#limpiar la consulta de esos términos
    temp_query = re.sub(game_and_key_terms, ' ', query).strip()
#remplazar múltiples espacios por uno solo
    temp_query = re.sub(r'\s+', ' ', temp_query).strip()

   # Si quedan palabras, asumimos que son el nombre del personaje   
    if temp_query:
        target_character = temp_query
        # Limpieza final de caracteres no alfanuméricos execpto espacios y guiones
        target_character = re.sub(r'[^\w\s-]', '', target_character).strip()

#para evitar que quede vacio o erroneo, tomamos la última palabra si no se detectó nada
    if not target_character:
        last_word = query.split()[-1]
        if last_word not in ["hsr", "zzz", "build", "completa", "de", "la", "el", "gi", "impact"]:
             target_character = re.sub(r'[^\w\s-]', '', last_word).strip()

    #Detección de componentes solicitados
    requested_keys = ["character_name", "game", "build_name", "source", "Analisis_Gemini"]

    # Flags para detectar si se pide la build completa
    is_complete_build = any(keyword in query for keyword in ["build", "general", "completa", "todo"])
    
    # Detectar peticiones específicas de componentes o stats
    if any(keyword in query for keyword in ["arma", "engine", "w-engine", "cono", "light cone"]): requested_keys.append("weapon_recommendations")
    
    # Para HSR/ZZZ, esto incluye Relics/Drives y Planar/Core
    if game in ["HSR", "ZZZ"]:
        if any(keyword in query for keyword in ["reliquia", "artefacto", "disco", "drive", "set", "ornamental"]):
            requested_keys.extend(["artifact_set_recommendations", "planetary_set_recommendations", "main_stats_recommendations"])
    
    # Para GI, esto incluye Artefacto
    elif game == "GI":
        if any(keyword in query for keyword in ["reliquia", "artefacto", "set", "tiara", "caliz", "arena"]):
             requested_keys.extend(["artifact_set_recommendations", "main_stats_recommendations"])

    if any(keyword in query for keyword in ["stats", "estadística", "objetivo", "target", "final", "substats", "vida", "ataque", "defensa", "critica", "maestria", "recarga"]): requested_keys.append("final_stats_targets")
    if any(keyword in query for keyword in ["equipo", "team", "composición", "partner"]): requested_keys.append("team_recommendations")

#Si la consulta no fue lo suficientemente específica, asume la build completa.
    if len(requested_keys) <= 5 or is_complete_build:
        if game == "GI":
             requested_keys.extend(["weapon_recommendations", "artifact_set_recommendations", "main_stats_recommendations", "final_stats_targets", "team_recommendations"])
        else:
             requested_keys.extend(["weapon_recommendations", "artifact_set_recommendations", "planetary_set_recommendations", "main_stats_recommendations", "final_stats_targets", "team_recommendations"])
 #elimina duplicados
    requested_keys = list(dict.fromkeys(requested_keys))

    return game, target_character, requested_keys

#hace todo el proceso de build
def process_build(game, target_character, requested_keys, source_choice, target_language):
    if not client:
        return None, "El script no puede continuar. Revisa tu clave API"

    if not target_character:
        return None, "No se pudo identificar el nombre del PJ."

    #selecciona la configuración del juego osea HSR, ZZZ o GI
    if game == "HSR":
        CURRENT_CONFIG = HSR_CONFIG
        GAME_NAME = "Honkai: Star Rail"
    elif game == "ZZZ":
        CURRENT_CONFIG = ZZZ_CONFIG
        GAME_NAME = "Zenless Zone Zero"
    else: 
        CURRENT_CONFIG = GI_CONFIG
        GAME_NAME = "Genshin Impact"

    # Configuración de fuentes basada en el juego
    if game == "HSR":
        lab_name = SOURCE_HONKAILAB
        all_sources = [
            (SOURCE_PRYDWEN, CURRENT_CONFIG["primary_base_url"], CURRENT_CONFIG["primary_path_segment"]),
            (SOURCE_HONKAILAB, CURRENT_CONFIG["tertiary_base_url"], CURRENT_CONFIG["tertiary_path_segment"]),
        ]
        source_map = {'1': SOURCE_PRYDWEN, '2': lab_name}
        prompt_sources = f"1: Prydwen, 2: {lab_name}"
    elif game == "ZZZ":
        lab_name = SOURCE_GENSHINLAB
        all_sources = [
            (SOURCE_PRYDWEN, CURRENT_CONFIG["primary_base_url"], CURRENT_CONFIG["primary_path_segment"]),
            (SOURCE_GENSHINLAB, CURRENT_CONFIG["tertiary_base_url"], CURRENT_CONFIG["tertiary_path_segment"]),
        ]
        source_map = {'1': SOURCE_PRYDWEN, '2': lab_name}
        prompt_sources = f"1: Prydwen, 2: {lab_name}"
    else:
        lab_name_1 = SOURCE_GENSHINBUILD
        lab_name_2 = SOURCE_GAMEWITH
        all_sources = [
            (SOURCE_GENSHINBUILD, CURRENT_CONFIG["primary_base_url"], CURRENT_CONFIG["primary_path_segment"]),
            (SOURCE_GAMEWITH, CURRENT_CONFIG["secondary_base_url"], CURRENT_CONFIG["secondary_path_segment"]),
        ]
        source_map = {'1': lab_name_1, '2': lab_name_2}
        prompt_sources = f"1: {lab_name_1} (Español), 2: {lab_name_2} (Japonés con Mapeo de IDs)"

    #hace que la fuente elegida por el usuario tenga prioridad
    selected_source_code = source_map.get(source_choice)
    if selected_source_code:
        source_priority = [s for s in all_sources if s[0] == selected_source_code]
        source_priority.extend([s for s in all_sources if s[0] != selected_source_code])
    else:
        source_priority = all_sources

    #hace que el idioma por defecto sea español
    if not target_language:
        target_language = "es"

    #hace que recorra las fuentes en orden de prioridad
    final_build = None
    comparison_reason = ""

#en este for se hace todo el proceso de scraping y análisis
    for source_code, base_url, path_segment in source_priority:
        print(f"\n--- INICIANDO SCRAPING EN FUENTE PRIORITARIA: {source_code} ---")
        char_url = get_character_url(base_url, target_character, path_segment, source_code)
        if char_url:
            soup = fetch_and_parse(char_url, source_code)
            if soup:
                build_result = extract_build_info(soup, target_character, CURRENT_CONFIG, source_code, target_language)
                is_viable = any(v for k, v in build_result.items() if k not in ["character_name", "game", "source", "build_name", "main_stats_recommendations"])
                if is_viable:
                    final_build = build_result
                    if selected_source_code:
                        comparison_reason = f"Build seleccionada porque fue la fuente elegida por el usuario: {selected_source_code}."
                    else:
                        comparison_reason = f"Build seleccionada por ser la primera fuente viable (Prioridad: {source_code}) encontrada."
                    break
#por ultimo en el if guarda la build en el archivo JSON
    if final_build:
        final_build["Analisis_Gemini"] = comparison_reason
        filtered_build = {key: final_build.get(key) for key in requested_keys if key in final_build}
        file_path = CURRENT_CONFIG["file_path"]
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    all_builds = json.load(f)
                except json.JSONDecodeError:
                    all_builds = {}
        else:
            all_builds = {}
        build_key = f"{game.lower()}_{target_character.lower().replace(' ', '_')}"
        all_builds[build_key] = final_build
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(all_builds, f, indent=4, ensure_ascii=False)
        return filtered_build, None
    else:
        return None, "No se pudo encontrar información de build completa y viable."


##############imagenes con fe pipi A*

def buscar_imagenes_hoyolab(etiqueta: str, max_post=6):
    """
    Reemplazo instrumentado: misma firma.
    - Logs detallados en consola para ver candidatos, respuestas HTTP y razones.
    - Usa storage_state 'state.json' si existe para evitar 401 por recursos privados.
    - Umbral reducido a 0.5 para mayor recall.
    """
    import os, re, time, unicodedata
    from urllib.parse import urljoin, urlparse, quote_plus
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("[buscar_imagenes_hoyolab] Playwright no está disponible.")
        return []

    def _normalize_text(s: str) -> str:
        if not s:
            return ""
        s = unicodedata.normalize("NFKD", s)
        s = "".join(c for c in s if not unicodedata.combining(c))
        return re.sub(r'\s+', ' ', s).strip().lower()

    def _token_overlap_score(a: str, b: str) -> float:
        ta = [t for t in re.split(r'\W+', _normalize_text(a)) if t]
        tb = [t for t in re.split(r'\W+', _normalize_text(b)) if t]
        if not ta or not tb:
            return 0.0
        set_a, set_b = set(ta), set(tb)
        inter = set_a.intersection(set_b)
        denom = (len(set_a) + len(set_b)) / 2.0
        return (len(inter) / denom) if denom > 0 else 0.0

    def _is_placeholder_image(src: str) -> bool:
        if not src:
            return True
        s = src.lower()
        if s.startswith("data:"):
            return True
        if s.endswith(".svg") and ("rp/" in s or "sprite" in s or "icons" in s):
            return True
        if "/rp/" in s or "/th?id=" in s or "placeholder" in s or "blank" in s:
            return True
        if re.search(r'/\d+x\d+(\.|/)|thumb|thumbnail', s):
            return True
        return False

    def _image_match_score(etiqueta: str, src: str, alt: str, parent_text: str, filename: str, figcaption: str) -> float:
        etiqueta_n = _normalize_text(etiqueta or "")
        if not etiqueta_n:
            return 0.0
        score = 0.0
        if etiqueta_n in _normalize_text(alt or ""):
            score += 1.0
        if etiqueta_n in _normalize_text(filename or ""):
            score += 1.0
        if etiqueta_n in _normalize_text(figcaption or ""):
            score += 1.0
        score += 0.45 * _token_overlap_score(etiqueta, parent_text or "")
        score += 0.45 * _token_overlap_score(etiqueta, src or "")
        return min(1.0, score)

    if not etiqueta:
        return []

    seeds = [
        f"https://www.hoyolab.com/search?keyword={quote_plus(etiqueta)}",
        f"https://www.bing.com/images/search?q={quote_plus(etiqueta)}",
        f"https://www.pixiv.net/en/tags/{quote_plus(etiqueta)}/artworks",
    ]

    found = []
    seen = set()
    state_file = "state.json"  # si has generado storage_state con login, se usará

    # Threshold menos estricto para más recall; sube si obtienes falsos positivos
    SCORE_THRESHOLD = 0.5

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # usar storage_state si existe -> reduce 401
        if os.path.exists(state_file):
            context = browser.new_context(storage_state=state_file)
            print("[buscar_imagenes_hoyolab] Usando storage_state:", state_file)
        else:
            context = browser.new_context()
            print("[buscar_imagenes_hoyolab] No se encontró storage_state; continuando sin sesión.")

        page = context.new_page()

        for seed in seeds:
            if len(found) >= max_post:
                break
            try:
                print(f"[buscar_imagenes_hoyolab] Abriendo seed: {seed}")
                network_images = set()

                def on_response(resp):
                    try:
                        url = resp.url
                        ct = (resp.headers.get("content-type") or "").lower()
                        if resp.status == 200 and ct.startswith("image"):
                            cleanu = url.split("#")[0].split("?")[0]
                            network_images.add(cleanu)
                    except Exception:
                        pass

                page.on("response", on_response)
                page.goto(seed, wait_until='domcontentloaded', timeout=60000)
                # small wait then force data-src -> src
                page.wait_for_timeout(800)
                page.evaluate("""
                    () => {
                        document.querySelectorAll('img').forEach(img => {
                            try {
                                const ds = img.getAttribute('data-src') || img.getAttribute('data-original') || img.dataset.src || img.dataset.original;
                                if (ds) img.src = ds;
                                const dss = img.getAttribute('data-srcset') || img.dataset.srcset;
                                if (dss && !img.src) img.src = dss.split(',')[0].trim().split(' ')[0];
                            } catch(e){}
                        });
                    }
                """)
                # scroll progresivo y esperar para lazy load
                for _ in range(10):
                    page.mouse.wheel(0, 1500)
                    page.wait_for_timeout(500)
                page.wait_for_timeout(1000)

                # recoger imgs desde DOM
                imgs = page.locator("img")
                total = 0
                try:
                    total = imgs.count()
                except Exception:
                    total = 0
                print(f"[buscar_imagenes_hoyolab] imgs DOM detectadas: {total}, network captures: {len(network_images)}")

                candidates = []
                for i in range(total):
                    try:
                        src = imgs.nth(i).get_attribute("src") or imgs.nth(i).get_attribute("data-src") or imgs.nth(i).get_attribute("data-original") or ""
                        if not src:
                            ss = imgs.nth(i).get_attribute("srcset") or ""
                            if ss:
                                src = ss.split(",")[0].strip().split(" ")[0]
                        src_clean = re.sub(r'\?.*$', '', src)
                        alt = imgs.nth(i).get_attribute("alt") or imgs.nth(i).get_attribute("title") or ""
                        parent_text = ""
                        try:
                            parent_text = imgs.nth(i).locator("xpath=..").inner_text()
                        except Exception:
                            parent_text = ""
                        filename = urlparse(src_clean).path.split("/")[-1] if src_clean else ""
                        figcaption = ""
                        try:
                            el = imgs.nth(i).locator("xpath=ancestor::figure[1]//figcaption")
                            if el.count() > 0:
                                figcaption = el.nth(0).inner_text()
                        except Exception:
                            figcaption = ""
                        if src_clean:
                            abs_url = urljoin(page.url, src_clean)
                            candidates.append((abs_url, alt, parent_text, filename, figcaption))
                    except Exception:
                        continue

                # añadir las imágenes capturadas por la red (posible mejor URL real)
                for ni in network_images:
                    candidates.append((ni, "", "", ni.split("/")[-1], ""))

                # dedupe preserving order
                unique_candidates = []
                for c in candidates:
                    u = c[0]
                    if not u:
                        continue
                    u_clean = re.sub(r'\?.*$', '', u)
                    if u_clean in seen:
                        continue
                    seen.add(u_clean)
                    unique_candidates.append((u_clean, c[1], c[2], c[3], c[4]))

                print(f"[buscar_imagenes_hoyolab] candidatos únicos: {len(unique_candidates)}")

                # verificar candidatos: hacer request dentro del contexto para mantener cookies
                for urlc, alt, parent_text, filename, figcaption in unique_candidates:
                    if len(found) >= max_post:
                        break
                    if _is_placeholder_image(urlc):
                        continue

                    score = _image_match_score(etiqueta, urlc, alt, parent_text, filename, figcaption)

                    status = None
                    try:
                        resp = page.request.get(urlc, timeout=8000)
                        status = resp.status
                    except Exception:
                        status = None

                    # reintento con Referer si 401
                    if status == 401:
                        try:
                            headers = {"Referer": page.url}
                            resp2 = page.request.get(urlc, headers=headers, timeout=8000)
                            status = resp2.status
                        except Exception:
                            pass

                    print(f"[buscar_imagenes_hoyolab] candidato: {urlc} score={score:.2f} status={status} alt_len={len(alt)} filename='{filename}'")

                    # condición de aceptación
                    if (score >= SCORE_THRESHOLD and status == 200) or (score >= 0.8 and (status is None or status == 200)):
                        clean_url = re.sub(r'\?.*$', '', urlc)
                        if clean_url not in found:
                            found.append(clean_url)
                    else:
                        # si status==200 y score razonable, añadir como fallback
                        if status == 200 and score >= 0.45:
                            clean_url = re.sub(r'\?.*$', '', urlc)
                            if clean_url not in found:
                                found.append(clean_url)

                # small pause between seeds
                page.wait_for_timeout(400)
                page.remove_listener("response", on_response)
            except Exception as e:
                print(f"[buscar_imagenes_hoyolab] fallo seed {seed}: {e}")
                try:
                    page.remove_listener("response", on_response)
                except Exception:
                    pass
                continue

        # cerrar
        try:
            page.close()
            context.close()
            browser.close()
        except Exception:
            pass

    print(f"[buscar_imagenes_hoyolab] encontrados: {len(found)} (limit {max_post}) -> {found[:max_post]}")
    return found[:max_post]

# ---- helpers + scraper estricto ----
def _normalize_text(s: str) -> str:
    import unicodedata, re
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().strip()
    s = re.sub(r'\s+', ' ', s)
    return s


def _token_overlap_score(a: str, b: str) -> float:
    import re
    a_t = [t for t in re.split(r'\W+', _normalize_text(a)) if t]
    b_t = [t for t in re.split(r'\W+', _normalize_text(b)) if t]
    if not a_t or not b_t:
        return 0.0
    set_a, set_b = set(a_t), set(b_t)
    inter = set_a.intersection(set_b)
    denom = (len(set_a) + len(set_b)) / 2.0
    return (len(inter) / denom) if denom > 0 else 0.0


def _is_placeholder_image(src: str) -> bool:
    if not src:
        return True
    s = src.lower()
    if s.startswith("data:"):
        return True
    if s.endswith(".svg") and ("rp/" in s or "sprite" in s or "icons" in s):
        return True
    if "/rp/" in s or "/th?id=" in s or "placeholder" in s or "blank" in s:
        return True
    # tiny images
    if re := __import__('re'):
        if re.search(r'/\d+x\d+(\.|/)|thumb|thumbnail', s):
            return True
    return False


def _image_match_score(etiqueta: str, src: str, alt: str, parent_text: str, filename: str, figcaption: str) -> float:
    """
    Señales fuertes: alt, filename, figcaption (peso alto).
    Señales débiles: token overlap en parent_text y en src (peso medio).
    Normaliza a [0..1]. Threshold sugerido >= 0.6.
    """
    etiqueta_n = _normalize_text(etiqueta or "")
    if not etiqueta_n:
        return 0.0

    score = 0.0

    # strong phrase matches
    if etiqueta_n in _normalize_text(alt or ""):
        score += 1.0
    if etiqueta_n in _normalize_text(filename or ""):
        score += 1.0
    if etiqueta_n in _normalize_text(figcaption or ""):
        score += 1.0

    # weak signals (overlap)
    score += 0.45 * _token_overlap_score(etiqueta, parent_text or "")
    score += 0.45 * _token_overlap_score(etiqueta, src or "")

    return min(1.0, score)


def scrape_images_from_url_strict(url: str, etiqueta: str, max_images: int = 6,
                                  use_playwright: bool = False, timeout: int = 8):
    """
    Scrapea 'url' y devuelve lista de dicts {'src','score','reason'} solo si la imagen
    pasa el filtro estricto de relación con 'etiqueta'.
    """
    results = []
    etiqueta = etiqueta or ""
    try:
        # Requests + BS (ligero)
        import requests
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin, urlparse
        import re as _re

        headers = {"User-Agent": "Mozilla/5.0 (compatible; imagen-busqueda/1.0)"}
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # collect figcaptions (map src->figcaption)
        figcaptions = {}
        for fig in soup.find_all("figure"):
            img = fig.find("img")
            fc = fig.find("figcaption")
            if img and fc:
                src = img.get("src") or img.get("data-src") or ""
                if src:
                    figcaptions[_re.sub(r'\?.*$', '', src)] = fc.get_text(" ", strip=True)

        imgs = soup.find_all("img")
        for img in imgs:
            src = img.get("src") or img.get("data-src") or img.get("data-original") or ""
            if not src:
                continue
            src_clean = _re.sub(r'\?.*$', '', src)
            src_abs = urljoin(url, src_clean)
            if _is_placeholder_image(src_abs):
                continue

            alt = img.get("alt") or img.get("title") or ""
            parent = img.parent
            parent_text = parent.get_text(" ", strip=True) if parent else ""
            filename = urlparse(src_clean).path.split("/")[-1]
            figcaption = figcaptions.get(src_clean, "") or ""

            score = _image_match_score(etiqueta, src_abs, alt, parent_text, filename, figcaption)

            if score >= 0.6:
                reasons = []
                if _normalize_text(etiqueta) in _normalize_text(alt): reasons.append("alt")
                if _normalize_text(etiqueta) in _normalize_text(filename): reasons.append("filename")
                if figcaption: reasons.append("figcaption")
                if parent_text: reasons.append("surrounding")
                results.append({"src": src_abs, "score": round(score, 2), "reason": "|".join(reasons) if reasons else "token_overlap"})

            if len(results) >= max_images:
                break

        # OG fallback
        if len(results) < max_images:
            og = soup.find("meta", property="og:image")
            if og and og.get("content"):
                og_src = urljoin(url, _re.sub(r'\?.*$', '', og.get("content")))
                if not _is_placeholder_image(og_src):
                    sc = _image_match_score(etiqueta, og_src, "", "", _re.sub(r'.*/', '', og_src), "")
                    if sc >= 0.6:
                        results.append({"src": og_src, "score": round(sc, 2), "reason": "og:image"})

        return results

    except Exception:
        # fallback con Playwright (para sitios JS-heavy)
        if use_playwright:
            try:
                from playwright.sync_api import sync_playwright
                from urllib.parse import urljoin, urlparse
                import re as _re
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    page.goto(url, wait_until='domcontentloaded', timeout=timeout * 1000)
                    page.wait_for_timeout(1000)
                    imgs = page.locator("img")
                    count = imgs.count()
                    for i in range(count):
                        try:
                            src = imgs.nth(i).get_attribute("src") or imgs.nth(i).get_attribute("data-src")
                            if not src:
                                continue
                            src_clean = _re.sub(r'\?.*$', '', src)
                            src_abs = urljoin(url, src_clean)
                            if _is_placeholder_image(src_abs):
                                continue
                            alt = imgs.nth(i).get_attribute("alt") or imgs.nth(i).get_attribute("title") or ""
                            parent_text = ""
                            try:
                                parent_text = imgs.nth(i).locator("xpath=..").inner_text()
                            except Exception:
                                parent_text = ""
                            filename = urlparse(src_clean).path.split("/")[-1]
                            figcaption = ""  # no simple way via playwright here
                            score = _image_match_score(etiqueta, src_abs, alt, parent_text, filename, figcaption)
                            if score >= 0.6:
                                reasons = []
                                if _normalize_text(etiqueta) in _normalize_text(alt): reasons.append("alt")
                                if _normalize_text(etiqueta) in _normalize_text(filename): reasons.append("filename")
                                results.append({"src": src_abs, "score": round(score, 2), "reason": "|".join(reasons) if reasons else "token_overlap"})
                            if len(results) >= max_images:
                                break
                        except Exception:
                            continue
                    browser.close()
                    return results
            except Exception:
                return results
        return results


app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Maneja los mensajes del chat y el estado de la conversación."""
    data = request.json
    user_input = data.get('message', '').strip()
    state = data.get('state', {'step': 'initial'})
    json_response = {}

    if state['step'] == 'initial':
        game, target_character, requested_keys = parse_user_query(user_input)
        if not target_character:
            json_response = {'response': "No pude identificar el nombre del personaje. Por favor, sé más específico (ej: 'Build para Acheron HSR').", 'state': {'step': 'initial'}}
        else:
            state.update({'step': 'waiting_source', 'game': game, 'target_character': target_character, 'requested_keys': requested_keys})
            if game == "HSR": prompt_sources = "1: Prydwen, 2: HonkaiLab"
            elif game == "ZZZ": prompt_sources = "1: Prydwen, 2: GenshinLab"
            else: prompt_sources = "1: GenshinBuilds (ES), 2: GameWith (JP)"
            response_text = f"¡Entendido! Buscando a <strong>{target_character.title()}</strong>. ¿Fuente preferida?<br>({prompt_sources})"
            json_response = {'response': response_text, 'state': state}

    elif state['step'] == 'waiting_source':
        state['source_choice'] = user_input if user_input in ['1', '2'] else ''
        state['step'] = 'waiting_language'
        response_text = "Perfecto. ¿Que idioma desea los resultados? (ej: 'es', 'en', 'jp', 'cn', 'fr', 'cr'). Deja en blanco para 'es'."
        json_response = {'response': response_text, 'state': state}

    elif state['step'] == 'waiting_language':
        state['target_language'] = user_input if user_input else 'es'
#genera la build
        result, error = process_build(
            state['game'], state['target_character'], state['requested_keys'],
            state.get('source_choice', ''), state.get('target_language', 'es')
        )

        images_list = []
        try:
            game_names = {
                "HSR": "Honkai Star Rail",
                "ZZZ": "Zenless Zone Zero", 
                "GI": "Genshin Impact"
            }
            game_full = game_names.get(state['game'], state['game'])
            images_list = buscar_imagenes_hoyolab(f"{state['target_character']} {game_full} hoyoverse", max_post=6)
        except Exception as e:
            print(f"Error buscando imágenes: {e}")

#esta parte ahce el response final
        if result:
            response_text = f"¡Aquí tienes la build para <strong>{state['target_character'].title()}</strong>!<br>¿Necesitas otra build?"
            json_response = {
                'response': response_text,
                'data': result,
                'images': images_list,  
                'game': state.get('game'),
                'state': {'step': 'initial'}
            }
        else:
            response_text = f"Lo siento, hubo un error: {error}.<br>¿Quieres intentar con otro personaje?"
            json_response = {'response': response_text, 'data': None, 'game': state.get('game'), 'state': {'step': 'initial'}}

    else:
        json_response = {'response': "Ha ocurrido un error de estado. Reiniciando.", 'state': {'step': 'initial'}}

    return jsonify(json_response)

if __name__ == "__main__":
    app.run(debug=True)