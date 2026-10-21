"""Sentence patterns for what you ask Jarvis, in Sinhala, Singlish and English.

Edit freely: add a word to a list or a pattern to an intent, then run
    uv run python scripts/make_intent_data.py
Drafted with Claude on 21 Oct 2026 in everyday spoken Sinhala; Adhi checks
them. Sinhala grammar covered:

- verb forms: polite (කරන්න), casual (කරන්නකෝ), for me (කරලා දෙන්න),
  question (කරන්න පුළුවන්ද?), formal (විවෘත කරන්න), need (කරන්න ඕනේ)
- synonyms people really use: ඕපන් කරන්න / අරින්න / විවෘත කරන්න,
  ක්ලෝස් කරන්න / වහන්න, හොයන්න / සර්ච් කරන්න
- "එක" after English words (ක්‍රෝම් එක), cases (ලංකාවේ / ලංකාව), and මට
- word order: object first (usual), verb first as an afterthought
- wake words and fillers: ජාවිස්, ෆ්‍රයිඩේ, හරි, අනේ, පොඩ්ඩක්
- two-sentence requests: a reason, then the request
"""

from __future__ import annotations

from .generate import C, Choice, Pattern, V

# ============================================================================
# Sinhala (Sinhala script)
# ============================================================================

SI_W = [C(""), C("ජාවිස්, "), C("ෆ්‍රයිඩේ, "), C("හරි, "), C("අනේ "), C("පොඩ්ඩක් ")]

SI_OPEN = [V("ඕපන් කරන්න", "polite"), V("ඕපන් කරන්නකෝ", "casual"), V("ඕපන් කරලා දෙන්න", "for_me"),
           V("ඕපන් කරන්න පුළුවන්ද?", "question"), V("අරින්න", "polite"), V("අරින්නකෝ", "casual"),
           V("අරලා දෙන්න", "for_me"), V("විවෘත කරන්න", "formal")]
SI_OPEN_FIRST = [V("ඕපන් කරන්න", "polite"), V("ඕපන් කරන්නකෝ", "casual"), V("අරින්න", "polite"),
                 V("අරලා දෙන්න", "for_me")]
SI_CLOSE = [V("ක්ලෝස් කරන්න", "polite"), V("ක්ලෝස් කරන්නකෝ", "casual"), V("වහන්න", "polite"),
            V("වහන්නකෝ", "casual"), V("වහලා දාන්න", "for_me"), V("වහන්න පුළුවන්ද?", "question")]
SI_SEARCH = [V("හොයන්න", "polite"), V("හොයන්නකෝ", "casual"), V("හොයලා දෙන්න", "for_me"),
             V("සර්ච් කරන්න", "polite"), V("සර්ච් කරලා දෙන්න", "for_me"),
             V("හොයලා දෙන්න පුළුවන්ද?", "question")]
SI_PLAY = [V("දාන්න", "polite"), V("දාන්නකෝ", "casual"), V("දාලා දෙන්න", "for_me"),
           V("ප්ලේ කරන්න", "polite"), V("ප්ලේ කරන්නකෝ", "casual"), V("දාන්න පුළුවන්ද?", "question")]
SI_EXPLAIN = [V("පැහැදිලි කරන්න", "polite"), V("කියලා දෙන්න", "for_me"), V("කියලා දෙන්නකෝ", "casual"),
              V("තේරුම් කරලා දෙන්න", "for_me"), V("එක්ස්ප්ලේන් කරන්න", "polite"),
              V("පැහැදිලි කරන්න පුළුවන්ද?", "question"), V("කියලා දෙන්න පුළුවන්ද?", "question")]
SI_EXPLAIN_SHORT = [V("කියලා දෙන්න", "for_me"), V("පැහැදිලි කරන්න", "polite"), V("කියන්නකෝ", "casual")]
SI_REMIND = [V("මතක් කරන්න", "polite"), V("මතක් කරන්නකෝ", "casual"), V("මතක් කරලා දෙන්න", "for_me"),
             V("රිමයින්ඩ් කරන්න", "polite"), V("මතක් කරන්න පුළුවන්ද?", "question")]
SI_SOLVE = [V("විසඳන්න", "polite"), V("විසඳන්නකෝ", "casual"), V("විසඳලා දෙන්න", "for_me"),
            V("සොල්ව් කරන්න", "polite"), V("සොල්ව් කරලා දෙන්න", "for_me"), V("විසඳන්න පුළුවන්ද?", "question")]
SI_SUMMARY = [V("සාරාංශයක් දෙන්න", "polite"), V("සාරාංශයක් හදලා දෙන්න", "for_me"),
              V("සමරි එකක් දෙන්න", "polite"), V("ප්‍රධාන කරුණු ටික කියන්න", "polite"),
              V("සාරාංශයක් දෙන්න පුළුවන්ද?", "question")]

SI_APP = [C("ක්‍රෝම් එක", "chrome"), C("ගූගල් ක්‍රෝම් එක", "chrome"), C("වීඑස් කෝඩ් එක", "vscode"),
          C("වර්ඩ් එක", "word"), C("එක්සෙල් එක", "excel"), C("පවර් බීඅයි එක", "powerbi"),
          C("යූටියුබ් එක", "youtube"), C("ස්පොටිෆයි එක", "spotify"), C("කැල්කියුලේටර් එක", "calculator"),
          C("නෝට්පෑඩ් එක", "notepad"), C("ෆයිල් එක්ස්ප්ලෝරර් එක", "explorer"), C("වට්ස්ඇප් එක", "whatsapp"),
          C("සූම් එක", "zoom"), C("ටෙලිග්‍රෑම් එක", "telegram")]
SI_APP_CLOSE = SI_APP + [C("බ්‍රවුසර් එක", "browser"), C("මේ වින්ඩෝ එක", "this_window")]
SI_FOLDER = [C("ඩවුන්ලෝඩ්ස් ෆෝල්ඩර් එක", "downloads"), C("ඩොකියුමන්ට්ස් ෆෝල්ඩර් එක", "documents"),
             C("ඩෙස්ක්ටොප් එක", "desktop"), C("ප්‍රොජෙක්ට් ෆෝල්ඩර් එක", "project"),
             C("ජාවිස් ෆෝල්ඩර් එක", "jarvis"), C("පික්චර්ස් ෆෝල්ඩර් එක", "pictures")]
SI_FILE = [C("මගේ ඇසයින්මන්ට් එක", "assignment"), C("ලැබ් රිපෝට් එක", "lab_report"),
           C("ෆිසික්ස් නෝට්ස්", "physics_notes"), C("කැල්කියුලස් ටියුටෝරියල් එක", "calculus_tutorial"),
           C("පාස්ට් පේපර්ස්", "past_papers"), C("ලෙක්චර් ස්ලයිඩ්ස්", "lecture_slides"),
           C("මගේ සීවී එක", "cv"), C("ප්‍රොජෙක්ට් ප්‍රොපෝසල් එක", "project_proposal"),
           C("ඊයේ හදපු එක්සෙල් ෂීට් එක", "excel_sheet")]
SI_MUSIC = [C("සින්දුවක්", "song"), C("බයිලා සින්දුවක්", "baila"), C("පරණ සිංහල සින්දු ටිකක්", "old_sinhala"),
            C("ක්ලැසිකල් සංගීතය", "classical"), C("ලෝෆයි මියුසික්", "lofi"), C("මගේ ප්ලේලිස්ට් එක", "my_playlist"),
            C("හෙමින් සින්දුවක්", "slow_song")]
SI_AMOUNT = [C(""), C("ටිකක් "), C("පොඩ්ඩක් "), C("තව ටිකක් ")]
SI_WHEN = [C("අද", "today"), C("හෙට", "tomorrow"), C("අද හවස", "this_evening"), C("මේ සතියේ", "this_week")]
SI_PLACE = [C("කොළඹ", "colombo"), C("මහනුවර", "kandy"), C("ගම්පහ", "gampaha"), C("කැලණියේ", "kelaniya"),
            C("ගාල්ලේ", "galle")]
SI_COUNTRY_LOC = [C("ලංකාවේ", "sri_lanka"), C("රුසියාවේ", "russia"), C("ඇමරිකාවේ", "usa"),
                  C("ඉන්දියාවේ", "india"), C("චීනයේ", "china"), C("ජපානයේ", "japan"), C("එංගලන්තයේ", "uk")]
SI_COUNTRY_NOM = [C("ලංකාව", "sri_lanka"), C("රුසියාව", "russia"), C("ඇමරිකාව", "usa"), C("ඉන්දියාව", "india"),
                  C("චීනය", "china"), C("ජපානය", "japan"), C("එංගලන්තය", "uk")]
SI_TOPIC = [
    C("එන්ට්‍රොපිය", "entropy"), C("තාපගති විද්‍යාවේ පළමු නියමය", "first_law_thermodynamics"),
    C("ඕම් නියමය", "ohms_law"), C("කර්චොෆ් නියම", "kirchhoffs_laws"), C("අර්ධ ආයු කාලය", "half_life"),
    C("න්‍යෂ්ටික විඛණ්ඩනය", "nuclear_fission"), C("ප්‍රකාශ විද්‍යුත් ආචරණය", "photoelectric_effect"),
    C("අවිනිශ්චිතතා මූලධර්මය", "uncertainty_principle"), C("තරංග ශ්‍රිතය", "wave_function"),
    C("ගම්‍යතා සංස්ථිතිය", "momentum_conservation"), C("නිව්ටන්ගේ දෙවැනි නියමය", "newtons_second_law"),
    C("ව්‍යතිකරණය", "interference"), C("ධාරිත්‍රක", "capacitors"), C("ප්‍රත්‍යාවර්ත ධාරාව", "alternating_current"),
    C("හරිතාගාර ආචරණය", "greenhouse_effect"), C("අවකලනය", "differentiation"), C("අනුකලනය", "integration"),
    C("ආංශික අවකලනය", "partial_derivatives"), C("ටේලර් ශ්‍රේණිය", "taylor_series"),
    C("අභිසාරී ශ්‍රේණි", "convergent_series"), C("දෛශික ගුණිතය", "vector_product"),
    C("නිර්ණායකය", "determinant"), C("අයිගන් වැලියු", "eigenvalues"), C("ගණිත අභ්‍යුහනය", "induction"),
    C("ලඝුගණක", "logarithms"), C("සංකීර්ණ සංඛ්‍යා", "complex_numbers"), C("අවකල සමීකරණ", "differential_equations"),
    C("නිව්ටන් රැප්සන් ක්‍රමය", "newton_raphson"), C("සම්මත අපගමනය", "standard_deviation"),
    C("සම්භාවිතාව", "probability")]
SI_STUDY_CONTEXT = [C("හෙට මට එක්සෑම් එකක් තියෙනවා."), C("අද ලෙක්චර් එක හරිම අමාරු වුණා."),
                    C("මට මේක ගොඩක් වෙලා තිස්සේ තේරුණේ නෑ."), C("මම නෝට්ස් බැලුවා, ඒත් පැහැදිලි නෑ."),
                    C("ඇසයින්මන්ට් එකට මේක ඕනේ.")]
SI_PROBLEM = [C("මේ ප්‍රශ්නය", "problem"), C("මේ ගණන", "sum"), C("මේ සමීකරණය", "equation"),
              C("මේ පරිපථ ප්‍රශ්නය", "circuit_problem"), C("මේ අවකල සමීකරණය", "differential_equation"),
              C("මේ ඇසයින්මන්ට් ප්‍රශ්නය", "assignment_problem"), C("මේ අනුකලනය", "integral")]
SI_STUCK = [C("මට මේ ප්‍රශ්නේ හිර වුණා."), C("උත්තරේ එන්නේ නෑ."), C("මම කීප පාරක් ට්‍රයි කළා.")]
SI_DOC_GEN = [C("මේ පීඩීඑෆ් එකේ", "pdf"), C("මේ ලෙක්චර් නෝට්ස් වල", "lecture_notes"),
              C("මේ රිසර්ච් පේපර් එකේ", "paper"), C("මේ ඊමේල් එකේ", "email"), C("මේ චැප්ටර් එකේ", "chapter")]
SI_DOC_NOM = [C("මේ පීඩීඑෆ් එක", "pdf"), C("මේ ලෙක්චර් නෝට්ස්", "lecture_notes"),
              C("මේ රිසර්ච් පේපර් එක", "paper"), C("මේ ඊමේල් එක", "email"), C("මේ චැප්ටර් එක", "chapter")]
SI_TASK = [C("රිපෝට් එක සබ්මිට් කරන්න", "submit_report"), C("ලෙක්චර් එකට යන්න", "go_to_lecture"),
           C("වතුර බොන්න", "drink_water"), C("අම්මාට කෝල් කරන්න", "call_mother"), C("පාඩම් කරන්න", "study"),
           C("ඇසයින්මන්ට් එක ඉවර කරන්න", "finish_assignment"), C("බ්‍රේක් එකක් ගන්න", "take_break"),
           C("ලැබ් එකට යන්න", "go_to_lab")]
SI_TIME = [C("හෙට උදේ", "tomorrow_morning"), C("අද රෑ", "tonight"), C("ටිකකින්", "soon"),
           C("පැයකින්", "in_an_hour"), C("අද හවස", "this_evening"), C("හෙට දවල්", "tomorrow_noon")]
SI_LANG_INST = [C("සිංහලෙන්", "si"), C("ඉංග්‍රීසියෙන්", "en")]
SI_FEELING = [C("මට ගොඩක් මහන්සියි"), C("මට අද හරිම පාළුයි"), C("මට ස්ට්‍රෙස් වගේ"),
              C("මට පාඩම් කරන්න හිතෙන්නේ නෑ"), C("විභාගේ ගැන මට බයයි"), C("අද දවස හොඳ නෑ"),
              C("මට ඔළුව රිදෙනවා")]

SI_VOCAB: dict[str, list[Choice]] = {
    "w": SI_W, "open": SI_OPEN, "open_first": SI_OPEN_FIRST, "close": SI_CLOSE, "search": SI_SEARCH,
    "play": SI_PLAY, "explain": SI_EXPLAIN, "explain_short": SI_EXPLAIN_SHORT, "remind": SI_REMIND,
    "solve": SI_SOLVE, "summary": SI_SUMMARY, "app": SI_APP, "app__close": SI_APP_CLOSE, "folder": SI_FOLDER,
    "file": SI_FILE, "music": SI_MUSIC, "amt": SI_AMOUNT, "when": SI_WHEN, "place": SI_PLACE,
    "country__loc": SI_COUNTRY_LOC, "country__nom": SI_COUNTRY_NOM, "topic": SI_TOPIC,
    "ctx": SI_STUDY_CONTEXT, "problem": SI_PROBLEM, "stuck": SI_STUCK, "doc__gen": SI_DOC_GEN,
    "doc__nom": SI_DOC_NOM, "task": SI_TASK, "time": SI_TIME, "lang": SI_LANG_INST, "feeling": SI_FEELING,
}
SI_PATTERNS = [
    Pattern("open_app", "{w}{app} {open}"),
    Pattern("open_app", "{w}{open_first} {app}"),
    Pattern("open_app", "{w}මට {app} {open}"),
    Pattern("open_app", "{w}මට {app} ඕපන් කරන්න ඕනේ"),
    Pattern("close_app", "{w}{app__close} {close}"),
    Pattern("close_app", "{w}{app__close} දැන් {close}"),
    Pattern("close_app", "{w}ඒක {close}"),
    Pattern("open_folder", "{w}{folder} {open}"),
    Pattern("open_folder", "{w}මට {folder} {open}"),
    Pattern("search_files", "{w}{file} {search}"),
    Pattern("search_files", "{w}මගේ කොම්පියුටර් එකේ {file} {search}"),
    Pattern("search_files", "{w}{file} කොහෙද තියෙන්නේ?"),
    Pattern("play_music", "{w}{music} {play}"),
    Pattern("play_music", "{w}යූටියුබ් එකේ {music} {play}"),
    Pattern("volume_up", "{w}සද්දේ {amt}වැඩි කරන්න"),
    Pattern("volume_up", "{w}වොලියුම් එක {amt}අප් කරන්න"),
    Pattern("volume_up", "{w}ඇහෙන්නේ නෑ, සද්දේ {amt}වැඩි කරන්න"),
    Pattern("volume_up", "{w}සද්දේ මදි, {amt}වැඩි කරන්නකෝ"),
    Pattern("volume_down", "{w}සද්දේ {amt}අඩු කරන්න"),
    Pattern("volume_down", "{w}වොලියුම් එක {amt}ඩවුන් කරන්න"),
    Pattern("volume_down", "{w}සද්දේ වැඩියි, {amt}අඩු කරන්න"),
    Pattern("volume_down", "{w}සද්දේ {amt}අඩු කරන්නකෝ"),
    Pattern("ask_time", "{w}දැන් වෙලාව කීයද?"),
    Pattern("ask_time", "{w}වෙලාව කීයද?"),
    Pattern("ask_time", "{w}ටයිම් එක කීයද?"),
    Pattern("ask_time", "{w}දැන් කීයද?"),
    Pattern("ask_time", "{w}වෙලාව කියන්නකෝ"),
    Pattern("ask_time", "{w}දැන් වෙලාව කීයක් විතර ඇති?"),
    Pattern("ask_time", "{w}වෙලාව බලලා කියන්න"),
    Pattern("ask_weather", "{w}{when} කාලගුණය කොහොමද?"),
    Pattern("ask_weather", "{w}{place} {when} කාලගුණය කොහොමද?"),
    Pattern("ask_weather", "{w}{when} වහියිද?"),
    Pattern("ask_weather", "{w}{place} {when} වහියිද?"),
    Pattern("ask_weather", "{w}{when} වෙදර් එක කොහොමද?"),
    Pattern("news", "{w}{country__loc} අලුත් ප්‍රවෘත්ති මොනවද?"),
    Pattern("news", "{w}{country__nom} ගැන නිව්ස් පෙන්නන්න"),
    Pattern("news", "{w}{country__loc} මොකද වෙන්නේ?"),
    Pattern("news", "{w}අද ප්‍රවෘත්ති මොනවද?"),
    Pattern("news", "{w}අද මොකද වෙලා තියෙන්නේ?"),
    Pattern("explain_concept", "{w}{topic} ගැන {explain}"),
    Pattern("explain_concept", "{w}{topic} කියන්නේ මොකක්ද?"),
    Pattern("explain_concept", "{w}{topic} මට තේරෙන්නේ නෑ, {explain}"),
    Pattern("explain_concept", "{w}{topic} උදාහරණයක් එක්ක {explain}"),
    Pattern("explain_concept", "{w}මට {topic} ගැන පොඩි උදව්වක් ඕනේ"),
    Pattern("explain_concept", "{w}{topic} සරලව {explain_short}"),
    Pattern("explain_concept", "{ctx} {topic} ගැන {explain}"),
    Pattern("solve_problem", "{w}{problem} {solve}"),
    Pattern("solve_problem", "{w}{problem} පියවරෙන් පියවර {solve}"),
    Pattern("solve_problem", "{w}{problem} විසඳන්නේ කොහොමද?"),
    Pattern("solve_problem", "{stuck} {problem} {solve}"),
    Pattern("summarize_document", "{w}{doc__gen} {summary}"),
    Pattern("summarize_document", "{w}{doc__nom} කෙටියෙන් {explain_short}"),
    Pattern("summarize_document", "{w}{doc__gen} තියෙන්නේ මොනවද කියලා කෙටියෙන් කියන්න"),
    Pattern("set_reminder", "{w}{time} {task} {remind}"),
    Pattern("set_reminder", "{w}{task} කියලා {time} මට {remind}"),
    Pattern("set_reminder", "{w}{time} මට {task} තියෙනවා, {remind}"),
    Pattern("switch_language", "{w}{lang} කතා කරන්න"),
    Pattern("switch_language", "{w}{lang} කතා කරමු"),
    Pattern("switch_language", "{w}{lang} උත්තර දෙන්න"),
    Pattern("switch_language", "{w}ෆ්‍රයිඩේ එක්ක කතා කරන්න ඕනේ", {"language": "si"}),
    Pattern("switch_language", "{w}ජාවිස් එක්ක කතා කරන්න ඕනේ", {"language": "en"}),
    Pattern("stop", "{w}නවත්තන්න"),
    Pattern("stop", "{w}ඇති, නවත්තන්න"),
    Pattern("stop", "{w}කතා කරන එක නවත්තන්න"),
    Pattern("stop", "{w}ඒක අවලංගු කරන්න"),
    Pattern("stop", "{w}කමක් නෑ, එපා"),
    Pattern("stop", "{w}එපා එපා"),
    Pattern("stop", "{w}ස්ටොප් කරන්න"),
    Pattern("stop", "{w}දැන් ඇති"),
    Pattern("stop", "{w}ඔක්කොම නවත්තන්න"),
    Pattern("feeling_low", "{w}{feeling}"),
]

# ============================================================================
# Singlish (Sinhala in English letters, as typed in chats)
# ============================================================================

SL_W = [C(""), C("jarvis "), C("friday "), C("hari "), C("ane "), C("podda ")]
SL_VOCAB: dict[str, list[Choice]] = {
    "w": SL_W,
    "open": [V("open karanna", "polite"), V("open karannako", "casual"), V("open karala denna", "for_me"),
             V("open karanna puluwanda", "question"), V("arinna", "polite"), V("arinnako", "casual")],
    "close": [V("close karanna", "polite"), V("close karannako", "casual"), V("wahanna", "polite"),
              V("wahala danna", "for_me"), V("close karanna puluwanda", "question")],
    "search": [V("hoyanna", "polite"), V("hoyala denna", "for_me"), V("search karanna", "polite"),
               V("search karala denna", "for_me"), V("hoyala denna puluwanda", "question")],
    "play": [V("danna", "polite"), V("dannako", "casual"), V("play karanna", "polite"),
             V("play karala denna", "for_me")],
    "explain": [V("explain karanna", "polite"), V("kiyala denna", "for_me"), V("kiyala dennako", "casual"),
                V("therum karala denna", "for_me"), V("explain karanna puluwanda", "question")],
    "remind": [V("mathak karanna", "polite"), V("mathak karala denna", "for_me"), V("remind karanna", "polite")],
    "solve": [V("solve karanna", "polite"), V("solve karala denna", "for_me"), V("wisadanna", "polite"),
              V("solve karanna puluwanda", "question")],
    "app": [C("chrome eka", "chrome"), C("google chrome eka", "chrome"), C("vs code eka", "vscode"),
            C("word eka", "word"), C("excel eka", "excel"), C("power bi eka", "powerbi"),
            C("youtube eka", "youtube"), C("spotify eka", "spotify"), C("calculator eka", "calculator"),
            C("notepad eka", "notepad"), C("whatsapp eka", "whatsapp"), C("zoom eka", "zoom")],
    "folder": [C("downloads folder eka", "downloads"), C("documents folder eka", "documents"),
               C("desktop eka", "desktop"), C("project folder eka", "project")],
    "file": [C("mage assignment eka", "assignment"), C("lab report eka", "lab_report"),
             C("physics notes", "physics_notes"), C("past papers", "past_papers"),
             C("lecture slides", "lecture_slides"), C("mage cv eka", "cv")],
    "music": [C("sindu ekak", "song"), C("baila sindu ekak", "baila"), C("lofi music", "lofi"),
              C("mage playlist eka", "my_playlist")],
    "amt": [C(""), C("tikak "), C("podda ")],
    "when": [C("ada", "today"), C("heta", "tomorrow")],
    "country": [C("lankawe", "sri_lanka"), C("russiawe", "russia"), C("americawe", "usa"),
                C("indiawe", "india"), C("chinawe", "china")],
    "topic": [C("entropy", "entropy"), C("derivative eka", "differentiation"), C("integration", "integration"),
              C("ohms law eka", "ohms_law"), C("half life eka", "half_life"), C("taylor series", "taylor_series"),
              C("eigen values", "eigenvalues"), C("standard deviation", "standard_deviation"),
              C("probability", "probability"), C("thermodynamics first law eka", "first_law_thermodynamics"),
              C("photoelectric effect eka", "photoelectric_effect"), C("newton raphson method eka", "newton_raphson"),
              C("uncertainty principle eka", "uncertainty_principle"),
              C("differential equations", "differential_equations")],
    "problem": [C("me prashnaya", "problem"), C("me ganana", "sum"), C("me equation eka", "equation"),
                C("me integral eka", "integral")],
    "doc": [C("me pdf eke", "pdf"), C("me lecture notes wala", "lecture_notes"), C("me paper eke", "paper")],
    "task": [C("report eka submit karanna", "submit_report"), C("lecture ekata yanna", "go_to_lecture"),
             C("wathura bonna", "drink_water"), C("ammata call karanna", "call_mother"),
             C("assignment eka iwara karanna", "finish_assignment")],
    "time": [C("heta ude", "tomorrow_morning"), C("ada ra", "tonight"), C("tikakin", "soon"),
             C("peyakin", "in_an_hour")],
    "lang": [C("sinhalen", "si"), C("englishen", "en"), C("ingreesiyen", "en")],
    "feeling": [C("mata godak mahansiyi"), C("mata stress wage"), C("mata padam karanna hithenne na"),
                C("ada dawasa hoda na")],
}
SL_PATTERNS = [
    Pattern("open_app", "{w}{app} {open}"),
    Pattern("open_app", "{w}mata {app} {open}"),
    Pattern("close_app", "{w}{app} {close}"),
    Pattern("open_folder", "{w}{folder} {open}"),
    Pattern("search_files", "{w}{file} {search}"),
    Pattern("search_files", "{w}{file} koheda thiyenne"),
    Pattern("play_music", "{w}{music} {play}"),
    Pattern("play_music", "{w}youtube eke {music} {play}"),
    Pattern("volume_up", "{w}sound eka {amt}wadi karanna"),
    Pattern("volume_up", "{w}volume eka {amt}up karanna"),
    Pattern("volume_down", "{w}sound eka {amt}adu karanna"),
    Pattern("volume_down", "{w}volume eka {amt}down karanna"),
    Pattern("ask_time", "{w}dan welawa keeyada"),
    Pattern("ask_time", "{w}time eka keeyada"),
    Pattern("ask_time", "{w}welawa kiyannako"),
    Pattern("ask_weather", "{w}{when} weather eka kohomada"),
    Pattern("ask_weather", "{w}{when} wahiyida"),
    Pattern("news", "{w}{country} news monawada"),
    Pattern("news", "{w}ada news monawada"),
    Pattern("explain_concept", "{w}{topic} gana {explain}"),
    Pattern("explain_concept", "{w}{topic} kiyanne mokakda"),
    Pattern("explain_concept", "{w}{topic} mata therenne na, {explain}"),
    Pattern("solve_problem", "{w}{problem} {solve}"),
    Pattern("solve_problem", "{w}{problem} step by step {solve}"),
    Pattern("summarize_document", "{w}{doc} summary ekak denna"),
    Pattern("summarize_document", "{w}{doc} main points tika kiyanna"),
    Pattern("set_reminder", "{w}{time} {task} {remind}"),
    Pattern("set_reminder", "{w}{task} kiyala {time} mata {remind}"),
    Pattern("switch_language", "{w}{lang} katha karanna"),
    Pattern("stop", "{w}nawaththanna"),
    Pattern("stop", "{w}athi nawaththanna"),
    Pattern("stop", "{w}epa epa"),
    Pattern("stop", "{w}eka cancel karanna"),
    Pattern("stop", "{w}stop karanna"),
    Pattern("feeling_low", "{w}{feeling}"),
]

# ============================================================================
# English
# ============================================================================

EN_W = [C(""), C("Jarvis, "), C("please "), C("hey Jarvis, ")]
EN_VOCAB: dict[str, list[Choice]] = {
    "w": EN_W,
    "app": [C("Chrome", "chrome"), C("Google Chrome", "chrome"), C("VS Code", "vscode"), C("Word", "word"),
            C("Excel", "excel"), C("Power BI", "powerbi"), C("YouTube", "youtube"), C("Spotify", "spotify"),
            C("the calculator", "calculator"), C("Notepad", "notepad"), C("WhatsApp", "whatsapp"),
            C("Zoom", "zoom")],
    "app__close": [C("Chrome", "chrome"), C("Word", "word"), C("Excel", "excel"), C("YouTube", "youtube"),
                  C("Spotify", "spotify"), C("the browser", "browser"), C("this window", "this_window")],
    "folder": [C("the downloads folder", "downloads"), C("my documents", "documents"), C("the desktop", "desktop"),
               C("the project folder", "project")],
    "file": [C("my assignment", "assignment"), C("the lab report", "lab_report"),
             C("my physics notes", "physics_notes"), C("the past papers", "past_papers"),
             C("the lecture slides", "lecture_slides"), C("my CV", "cv")],
    "music": [C("some music", "song"), C("a baila song", "baila"), C("some lofi music", "lofi"),
              C("my playlist", "my_playlist"), C("old Sinhala songs", "old_sinhala")],
    "when": [C("today", "today"), C("tomorrow", "tomorrow"), C("this evening", "this_evening")],
    "place": [C("Colombo", "colombo"), C("Kandy", "kandy"), C("Kelaniya", "kelaniya")],
    "country": [C("Sri Lanka", "sri_lanka"), C("Russia", "russia"), C("the US", "usa"), C("India", "india"),
                C("China", "china"), C("Japan", "japan")],
    "topic": [C("entropy", "entropy"), C("the first law of thermodynamics", "first_law_thermodynamics"),
              C("Ohm's law", "ohms_law"), C("half-life", "half_life"),
              C("the photoelectric effect", "photoelectric_effect"),
              C("the uncertainty principle", "uncertainty_principle"), C("derivatives", "differentiation"),
              C("integration", "integration"), C("Taylor series", "taylor_series"),
              C("eigenvalues", "eigenvalues"), C("standard deviation", "standard_deviation"),
              C("the Newton-Raphson method", "newton_raphson")],
    "problem": [C("this problem", "problem"), C("this equation", "equation"), C("this integral", "integral"),
                C("this circuit problem", "circuit_problem"), C("this differential equation", "differential_equation")],
    "doc": [C("this PDF", "pdf"), C("these lecture notes", "lecture_notes"), C("this paper", "paper"),
            C("this email", "email")],
    "task": [C("submit the report", "submit_report"), C("go to the lecture", "go_to_lecture"),
             C("drink water", "drink_water"), C("call my mother", "call_mother"),
             C("finish the assignment", "finish_assignment"), C("take a break", "take_break")],
    "time": [C("tomorrow morning", "tomorrow_morning"), C("tonight", "tonight"), C("in an hour", "in_an_hour"),
             C("this evening", "this_evening")],
    "lang": [C("Sinhala", "si"), C("English", "en")],
    "feeling": [C("I'm really tired"), C("I'm feeling stressed"), C("I don't feel like studying"),
                C("I'm scared about the exam"), C("today was a bad day"), C("I have a headache")],
}
EN_PATTERNS = [
    Pattern("open_app", "{w}open {app}"), Pattern("open_app", "{w}can you open {app}"),
    Pattern("open_app", "{w}launch {app}"), Pattern("open_app", "{w}start {app}"),
    Pattern("close_app", "{w}close {app__close}"), Pattern("close_app", "{w}can you close {app__close}"),
    Pattern("open_folder", "{w}open {folder}"), Pattern("open_folder", "{w}show me {folder}"),
    Pattern("search_files", "{w}find {file}"), Pattern("search_files", "{w}search for {file}"),
    Pattern("search_files", "{w}where is {file}"),
    Pattern("play_music", "{w}play {music}"), Pattern("play_music", "{w}put on {music}"),
    Pattern("play_music", "{w}play {music} on YouTube"),
    Pattern("volume_up", "{w}turn the volume up"), Pattern("volume_up", "{w}make it louder"),
    Pattern("volume_up", "{w}turn it up a bit"), Pattern("volume_up", "{w}I can't hear, turn it up"),
    Pattern("volume_down", "{w}turn the volume down"), Pattern("volume_down", "{w}make it quieter"),
    Pattern("volume_down", "{w}turn it down a little"), Pattern("volume_down", "{w}it's too loud"),
    Pattern("ask_time", "{w}what time is it"), Pattern("ask_time", "{w}what's the time"),
    Pattern("ask_time", "{w}tell me the time"),
    Pattern("ask_weather", "{w}what's the weather like {when}"), Pattern("ask_weather", "{w}will it rain {when}"),
    Pattern("ask_weather", "{w}what's the weather in {place} {when}"),
    Pattern("news", "{w}what's the news today"), Pattern("news", "{w}show me news about {country}"),
    Pattern("news", "{w}what's happening in {country}"),
    Pattern("explain_concept", "{w}explain {topic}"), Pattern("explain_concept", "{w}what is {topic}"),
    Pattern("explain_concept", "{w}can you explain {topic} simply"),
    Pattern("explain_concept", "{w}I don't understand {topic}, can you explain it"),
    Pattern("explain_concept", "{w}explain {topic} with an example"),
    Pattern("solve_problem", "{w}solve {problem}"), Pattern("solve_problem", "{w}solve {problem} step by step"),
    Pattern("solve_problem", "{w}how do I solve {problem}"), Pattern("solve_problem", "{w}help me with {problem}"),
    Pattern("summarize_document", "{w}summarize {doc}"),
    Pattern("summarize_document", "{w}give me a summary of {doc}"),
    Pattern("summarize_document", "{w}what are the main points of {doc}"),
    Pattern("set_reminder", "{w}remind me to {task} {time}"),
    Pattern("set_reminder", "{w}{time}, remind me to {task}"),
    Pattern("switch_language", "{w}speak {lang}"), Pattern("switch_language", "{w}switch to {lang}"),
    Pattern("switch_language", "{w}can we talk in {lang}"), Pattern("switch_language", "{w}reply in {lang}"),
    Pattern("switch_language", "{w}talk to Friday", {"language": "si"}),
    Pattern("stop", "{w}stop"), Pattern("stop", "{w}stop talking"), Pattern("stop", "{w}cancel that"),
    Pattern("stop", "{w}never mind"), Pattern("stop", "{w}that's enough"), Pattern("stop", "{w}stop everything"),
    Pattern("feeling_low", "{w}{feeling}"),
]

LANGUAGES = {"si": (SI_VOCAB, SI_PATTERNS), "si-Latn": (SL_VOCAB, SL_PATTERNS), "en": (EN_VOCAB, EN_PATTERNS)}
# How many examples per intent, per language (the most for Sinhala, the research focus).
PER_INTENT = {"si": 220, "si-Latn": 90, "en": 70}
