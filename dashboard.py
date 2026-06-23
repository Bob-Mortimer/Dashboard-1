import streamlit as Streamlit
import pandas as pd
import requests
import os
from datetime import datetime, timedelta
import pytz

# --- GLOBAL INITIALIZATION ---
# These variables must be defined here so every section can access them
import pytz
from datetime import datetime, timedelta

local_tz = pytz.timezone("Australia/Melbourne")
now = datetime.now(local_tz)
date_str = now.strftime("%d %b %Y")
dtg = now.strftime("%d%H%M") + "K " + now.strftime("%b %y").upper()
seven_days_ago = now - timedelta(days=7)

# Initialize df as an empty DataFrame so the logic check at the end doesn't crash
df = pd.DataFrame()

# ---------------------------------------------------------
# 1. STREAMLIT PAGE CONFIGURATION
# ---------------------------------------------------------
Streamlit.set_page_config(
    page_title="Regional Intelligence Feed",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# 2. AUSTRALIAN ARMY COLOR PALETTE & LOCKDOWN CSS
# ---------------------------------------------------------
Streamlit.markdown("""
    <style>
    /* Force browser window to lock completely - No outer page scrolling */
    html, body, [data-testid="stAppViewContainer"] {
        overflow-y: hidden !important;
        height: 100vh !important;
    }

    /* Pull layout to the absolute edges of the screen */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0rem !important;
        padding-left: 1rem !important;   /* <--- Shrinks the left invisible margin */
        padding-right: 1rem !important;  /* <--- Shrinks the right invisible margin */
        max-width: 99% !important;       /* <--- Expands the total usable width */
    }

    /* Main Background */
    .stApp { background-color: #F9F8F6; } 
    
    /* Minimize margins on all main text headers to reclaim screen space */
    h1 { 
        margin-top: 15px !important; /* <--- Added a small breathing gap here */
        margin-bottom: 0px !important;
        padding-bottom: 0px !important;
        font-size: 2rem !important;
    }
    h3 {
        margin-top: -5px !important;
        margin-bottom: 0px !important;
        font-size: 1.1rem !important;
    }
    h2 {
        font-size: 1.2rem !important;
        margin-bottom: 5px !important;
    }
    
    /* Headers style */
    h1, h2, h3 { 
        color: #4B5320 !important; 
        font-family: 'Courier New', Courier, monospace !important; 
        text-transform: uppercase;
    }
    
    /* Intel Card Design */
    .intel-card { 
        border-left: 4px solid #4B5320; 
        background-color: #FFFFFF; 
        padding: 10px 12px;
        margin-bottom: 10px; 
        border-radius: 2px;
        box-shadow: 1px 1px 5px rgba(0,0,0,0.05);
    }
    .intel-title { color: #6B4423; font-weight: 800; font-family: 'Arial', sans-serif; font-size: 0.95em; margin-bottom: 3px;}
    .intel-loc { color: #C3B091; font-weight: bold; font-family: 'Courier New', Courier, monospace; font-size: 0.8em; margin-bottom: 5px;}
    .intel-desc { color: #000000; font-family: 'Arial', sans-serif; font-size: 0.85em; line-height: 1.3;}
    .intel-link { color: #6B4423; font-size: 0.75em; font-weight: bold; text-decoration: none;}
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 3. API KEY SECURITY
# ---------------------------------------------------------
news_api_key = "5f2b6766fa854e2489f0704311bc22d5"

# All sidebar and os.environ code has been deleted so it cannot overwrite your key!

# ---------------------------------------------------------
# 4. DATE LOGIC & CONSTANTS
# ---------------------------------------------------------
today = datetime.now()
seven_days_ago = today - timedelta(days=7)
date_str = f"{seven_days_ago.strftime('%d %b %Y').upper()} - {today.strftime('%d %b %Y').upper()}"
currents_start_date = seven_days_ago.strftime('%Y-%m-%dT00:00:00+00:00')

SEA_LOCATIONS = {
    "australia": {"loc": "Canberra, Australia", "lat": -35.2809, "lon": 149.1300},
    "philippines": {"loc": "Manila, Philippines", "lat": 14.5995, "lon": 120.9842},
    "indonesia": {"loc": "Jakarta, Indonesia", "lat": -6.2088, "lon": 106.8456},
    "malaysia": {"loc": "Kuala Lumpur, Malaysia", "lat": 3.1390, "lon": 101.6869},
    "vietnam": {"loc": "Hanoi, Vietnam", "lat": 21.0285, "lon": 105.8542},
    "thailand": {"loc": "Bangkok, Thailand", "lat": 13.7563, "lon": 100.5018},
    "singapore": {"loc": "Singapore", "lat": 1.3521, "lon": 103.8198},
    "taiwan": {"loc": "Taipei, Taiwan", "lat": 25.0330, "lon": 121.5654},
    "china": {"loc": "Beijing, China", "lat": 39.9042, "lon": 116.4074}
}

# ---------------------------------------------------------
# 5. INTELLIGENCE DATA PIPELINE (Theater vs. Global Split)
# ---------------------------------------------------------
def fetch_newsapi_data(query_string):
    url = "https://newsapi.org/v2/everything"
    trusted_domains = "reuters.com,apnews.com,bbc.co.uk,aljazeera.com,bloomberg.com,defensenews.com,scmp.com,channelnewsasia.com,theguardian.com,ft.com,wsj.com"
    newsapi_start_date = seven_days_ago.strftime('%Y-%m-%d')
    
    params = {
        "apiKey": news_api_key,
        "language": "en",
        "q": query_string,
        "searchIn": "title,description", 
        "domains": trusted_domains,
        "from": newsapi_start_date,
        "sortBy": "publishedAt",
        "pageSize": 50
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            return response.json().get("articles", [])
        else:
            Streamlit.error(f"API Error {response.status_code}: {response.json().get('message', 'Unknown Error')}")
            return []
    except Exception as e:
        Streamlit.error(f"Network Error: {e}")
        return []

def process_articles(raw_articles, category_name, required_keywords, exclude_keywords=None):
    items = []
    for art in raw_articles:
        title = str(art.get('title') or '')
        desc = str(art.get('description') or '')
        text_body = (title + " " + desc).lower()
        
        # MUTUAL EXCLUSION: Prevent theater-intersecting stories from hitting the global column
        if exclude_keywords and any(ex in text_body for ex in exclude_keywords):
            continue
            
        # SECONDARY VERIFICATION: Hard core security check
        if not any(keyword in text_body for keyword in required_keywords):
            continue 
            
        # Geolocation check for mapping infrastructure
        matched_loc = {"loc": "Global / External Flashpoint", "lat": 0.0, "lon": 0.0}
        is_mapped = False
        for key, coords in SEA_LOCATIONS.items():
            if key in text_body:
                matched_loc = coords
                is_mapped = True
                break
                
        # Word truncation
        words = desc.split()
        summary = " ".join(words[:25]) + ("..." if len(words) > 25 else "")
        if not summary.strip():
            summary = "No detailed intelligence summary provided by source."

        source_name = art.get('source', {}).get('name', 'Unknown Source')

        items.append({
            "Title": f"[{source_name.upper()}] {title}", 
            "Description": summary,
            "Location": matched_loc["loc"],
            "lat": matched_loc["lat"],
            "lon": matched_loc["lon"],
            "Category": category_name,
            "Mapped": is_mapped,
            "URL": art.get('url', '#')
        })
    return items

with Streamlit.spinner("Authenticating NewsAPI and pulling vetted source telemetry..."):
    # LEFT COLUMN: Theater Flashpoints
    sea_query = '(China OR Beijing OR PLA OR military OR defense OR navy OR geopolitics OR diplomacy) AND (Australia OR "Southeast Asia" OR Philippines OR Indonesia OR Malaysia OR Vietnam OR Thailand OR Singapore OR Taiwan OR "South China Sea")'
    sea_raw = fetch_newsapi_data(sea_query)
    
    # RIGHT COLUMN: Global Context
    global_query = '(military OR defense OR navy OR army OR security OR forces OR geopolitics OR diplomacy OR treaty OR summit OR government OR policy OR war OR conflict OR spending) AND (Ukraine OR Russia OR Iran OR Venezuela OR "European Union" OR EU OR Cuba OR "United States" OR US OR Washington)'
    global_raw = fetch_newsapi_data(global_query)

    # CENTER COLUMN (NEW): FIVE EYES Intelligence
    fvey_query = '("ASD" OR "GCHQ" OR "CSE" OR "GCSB" OR "NSA" OR "FBI" OR "CIA" OR "DIO" OR "ASIO" OR "ASIS" OR "AFP") AND (intelligence OR cyber OR espionage OR surveillance OR security OR counterterrorism)'
    fvey_raw = fetch_newsapi_data(fvey_query)

# Operational check keywords (Updated to include FVEY agencies to pass the strict filter)
strict_keywords = ['troops', 'missile', 'warship', 'exercises', 'deployment', 'combat', 'artillery', 'vessel', 'maritime', 'squadron', 'pentagon', 'pla', 'military', 'defense', 'navy', 'army', 'security', 'forces', 'treaty', 'summit', 'ambassador', 'diplomat', 'sanctions', 'bilateral', 'sovereignty', 'jurisdiction', 'government', 'policy', 'president', 'meeting', 'war', 'conflict', 'china', 'beijing', 'asd', 'gchq', 'cse', 'gcsb', 'nsa', 'fbi', 'cia', 'dio', 'asio', 'asis', 'afp', 'intelligence', 'cyber', 'espionage']

theater_exclusion_list = ['australia', 'southeast asia', 'philippines', 'indonesia', 'malaysia', 'vietnam', 'thailand', 'singapore', 'taiwan', 'manila', 'jakarta', 'taipei', 'south china sea']

# Process lists into separated data buckets
sea_events = process_articles(sea_raw, "SEA", strict_keywords)
global_events = process_articles(global_raw, "Global", strict_keywords, exclude_keywords=theater_exclusion_list)
fvey_events = process_articles(fvey_raw, "FVEY", strict_keywords)

# Master Dataframe now contains all three feeds
df = pd.DataFrame(sea_events + global_events + fvey_events)

# Operational check keywords
strict_keywords = ['troops', 'missile', 'warship', 'exercises', 'deployment', 'combat', 'artillery', 'vessel', 'maritime', 'squadron', 'pentagon', 'pla', 'military', 'defense', 'navy', 'army', 'security', 'forces', 'treaty', 'summit', 'ambassador', 'diplomat', 'sanctions', 'bilateral', 'sovereignty', 'jurisdiction', 'foreign minister', 'unclos', 'government', 'policy', 'president', 'prime minister', 'meeting', 'talks', 'war', 'conflict', 'spending', 'china', 'beijing']

# If an article mentions any of these theater flashpoints, it is banned from the right column to prevent duplication
theater_exclusion_list = ['australia', 'southeast asia', 'philippines', 'indonesia', 'malaysia', 'vietnam', 'thailand', 'singapore', 'taiwan', 'manila', 'jakarta', 'taipei', 'south china sea']

# Process lists into separated data buckets
sea_events = process_articles(sea_raw, "SEA", strict_keywords)
global_events = process_articles(global_raw, "Global", strict_keywords, exclude_keywords=theater_exclusion_list)

df = pd.DataFrame(sea_events + global_events)

# ---------------------------------------------------------
# 5.5 EXECUTIVE BRIEFING EXPORT TOOL (Collapsed for Space)
# ---------------------------------------------------------
Streamlit.sidebar.title("Executive Tools")

with Streamlit.sidebar.expander("📋 Generate Morning Brief"):
    # Generate the brief on-demand when the expander is opened
    from datetime import datetime
    import pytz
    
    local_tz = pytz.timezone("Australia/Melbourne")
    dtg = datetime.now(local_tz).strftime("%d%H%M") + "K " + datetime.now(local_tz).strftime("%b %y").upper()

    brief_text = f"UNOFFICIAL MORNING INTEL SUMMARY // DTG: {dtg}\n" + "="*40 + "\n\n"
    
    # SEA Section
    brief_text += "[1] SEA GEOPOLITICS\n"
    sea_brief = df[df['Category'] == 'SEA'].head(3) # Limited to 3 to save space
    for _, row in sea_brief.iterrows():
        brief_text += f"  • {row['Title']}\n\n"

    # FVEY Section
    brief_text += "[2] FVEY INTELLIGENCE\n"
    fvey_brief = df[df['Category'] == 'FVEY'].head(3)
    for _, row in fvey_brief.iterrows():
        brief_text += f"  • {row['Title']}\n\n"
        
    brief_text += "// END SUMMARY //"
    
    Streamlit.code(brief_text, language="text")

# ---------------------------------------------------------
# 6. DASHBOARD HEADER INTERFACE
# ---------------------------------------------------------
import streamlit.components.v1 as components

# Define the HTML content as a string
header_html = f"""
<div style='text-align: center; font-family: sans-serif;'>
    <div style='font-weight: 900; color: #CC0000; font-size: 1.2em; text-transform: uppercase; margin-bottom: 5px;'>
        UNOFFICIAL // FOR INTERNAL BRIEFING USE ONLY
    </div>
    <h2 style='margin: 0;'>INTELLIGENCE FEED</h2>
    <p style='font-size: 0.8em; margin-bottom: 5px;'>DATA SNAPSHOT: {date_str}</p>
    <p style='font-size: 0.85em; font-style: italic; color: #6B4423; margin-top: -5px; margin-bottom: 5px;'>
        All information sourced from a live environment at 
        <span style='color: #8B0000; font-weight: bold;'>{dtg}</span>.
    </p>
    <hr style='margin-top: 5px; margin-bottom: 15px; border: none; border-top: 2px solid #C3B091;'>
</div>
"""

# Force render the HTML component
# The height parameter (180) ensures it has enough space to render without cutting off
components.html(header_html, height=180)

# Logic check
if df.empty:
    Streamlit.warning("No tracking telemetry found for the past 7 days matching query limits.")
    Streamlit.stop()
    
# ---------------------------------------------------------
# 7. THE 3-COLUMN VIEWPORT-LOCKED LAYOUT
# ---------------------------------------------------------
Streamlit.sidebar.markdown("---")
Streamlit.sidebar.title("Live Tactical Filter")
search_term = Streamlit.sidebar.text_input("Isolate specific asset or event:", "").lower()

# If a keyword is typed, instantly filter the master dataframe before drawing the cards
if search_term:
    df = df[df.apply(lambda row: search_term in str(row['Title']).lower() or search_term in str(row['Description']).lower(), axis=1)]

col_left, col_center, col_right = Streamlit.columns([1, 1.4, 1], gap="small")

def render_html_cards(dataframe):
    """Helper function to draw the custom compact CSS news cards with Threat-Matrix Tagging"""
    # 1. Define our classification vocabularies
    tactical_keywords = ['missile', 'combat', 'clash', 'artillery', 'strike', 'live-fire', 'troops', 'warship', 'intercept', 'drill']
    strategic_keywords = ['treaty', 'talks', 'summit', 'ambassador', 'diplomat', 'sanctions', 'bilateral', 'policy', 'agreement']

    for _, row in dataframe.iterrows():
        text_to_check = (str(row['Title']) + " " + str(row['Description'])).lower()
        badge_html = ""
        
        if any(word in text_to_check for word in tactical_keywords):
            badge_html = "<span style='background-color: #8B0000; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.7em; font-weight: bold; margin-bottom: 5px; display: inline-block;'>[TACTICAL EVENT]</span><br>"
        elif any(word in text_to_check for word in strategic_keywords):
            badge_html = "<span style='background-color: #C3B091; color: #4B5320; padding: 2px 6px; border-radius: 3px; font-size: 0.7em; font-weight: bold; margin-bottom: 5px; display: inline-block;'>[STRATEGIC/POLICY]</span><br>"

        # Spacing tightened up to prevent Streamlit rendering errors
        card_html = f"""
        <div class="intel-card">
            {badge_html}<div class="intel-title">{row['Title'].upper()}</div>
            <div class="intel-loc">LOC: {row['Location'].upper()}</div>
            <div class="intel-desc">{row['Description']}</div>
            <div style="margin-top: 5px;"><a class="intel-link" href="{row['URL']}" target="_blank">[SOURCE DISPATCH]</a></div>
        </div>
        """
        Streamlit.markdown(card_html, unsafe_allow_html=True)

with col_left:
    Streamlit.subheader("SOUTHEAST ASIA")
    with Streamlit.container(height=420): 
        sea_df = df[df['Category'] == 'SEA'].sort_values(by='Mapped', ascending=False).head(15) 
        render_html_cards(sea_df)

with col_center:
    Streamlit.subheader("REGIONAL MAP")
    # Shrunk the map to half size (200px)
    with Streamlit.container(height=200):
        map_df = df[(df['Category'] == 'SEA') & (df['Mapped'] == True)]
        if not map_df.empty:
            Streamlit.map(map_df, latitude="lat", longitude="lon", zoom=2, color="#FF0000", use_container_width=True)
        else:
            Streamlit.info("No geospatial data locked for current timeline.")

    Streamlit.subheader("FIVE EYES (FVEY) AGENCIES")
    # Added the new FVEY feed in the remaining space
    with Streamlit.container(height=170):
        fvey_df = df[df['Category'] == 'FVEY'].copy()
        if not fvey_df.empty:
            import re
            # Exact user priority sequence
            agency_order = ['asd', 'gchq', 'cse', 'gcsb', 'nsa', 'fbi', 'cia', 'dio', 'asio', 'asis', 'afp']
            
            def get_fvey_priority(row):
                text = (str(row['Title']) + " " + str(row['Description'])).lower()
                # Use regex boundaries (\b) so "cse" doesn't trigger inside the word "case"
                for idx, agency in enumerate(agency_order):
                    if re.search(rf'\b{agency}\b', text):
                        return idx
                return 99 # Push unmatched to the bottom
            
            # Apply the strict sorting algorithm
            fvey_df['Priority'] = fvey_df.apply(get_fvey_priority, axis=1)
            fvey_df = fvey_df.sort_values('Priority').head(15)
            
            # Draw the FVEY cards
            render_html_cards(fvey_df)
        else:
            Streamlit.info("No FVEY intelligence updates detected in current cycle.")

with col_right:
    Streamlit.subheader("OTHER GEOPOLITICAL EVENTS")
    with Streamlit.container(height=420): 
        global_df = df[df['Category'] == 'Global'].head(15) 
        render_html_cards(global_df)