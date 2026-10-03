"""Symptom lexicon for Hindi, Hindi English code switching and Marwari influenced speech.

IMPORTANT: this is a starter vocabulary written for engineering purposes. It
must be reviewed by native Marwari and Hindi speakers and by clinicians before
any real world use. Entries prefixed with "ctx:" describe medical context
instead of symptoms. Ambiguity is declared on the concept, not here.

Roman spellings are folded (see text.fold_token), so spelling variants such as
"bukhar" and "bukhaar" do not need separate entries.
"""

from collections import defaultdict
from dataclasses import dataclass

from .text import fold_phrase

LEXICON: dict[str, list[str]] = {
    "fever": [
        "bukhar", "bukhaar", "taav", "taap", "jwar", "jvar", "badan garam", "sharir garam", "badan tap",
        "bukhar jaisa", "fever", "temperature", "high temperature",
        "बुखार", "ताव", "ताप", "ज्वर", "बदन गरम", "शरीर गरम", "तापमान",
    ],
    "headache": [
        "sar dard", "sir dard", "sar mein dard", "sir mein dard", "sar me dard", "sir me dard", "sar dukh",
        "sir dukh", "matha dard", "maatha dard", "matho dukhe", "maatho dukhe", "matho dukhai", "matha dukh",
        "sar phat", "sar fat raha", "headache", "head ache", "head pain",
        "सिरदर्द", "सर दर्द", "सिर दर्द", "सर में दर्द", "सिर में दर्द", "माथा दर्द", "माथो दुखै", "माथो दुखे",
        "माथा दुख", "सर दुख", "सिर दुख", "सर फट",
    ],
    "head_heaviness": [
        "sar bhari", "sir bhari", "sar bhaari", "matha bhari", "matho bhari",
        "सर भारी", "सिर भारी", "माथा भारी", "माथो भारी",
    ],
    "cough": ["khansi", "khaansi", "khasi", "khaans", "cough", "coughing", "खांसी", "खाँसी", "खांस", "खासी"],
    "sore_throat": [
        "gala dard", "gale mein dard", "gale me dard", "gala kharab", "gale mein kharash", "gala dukh",
        "throat pain", "sore throat", "गला दर्द", "गले में दर्द", "गले में खराश", "गला खराब", "गला दुख",
    ],
    "cold_symptoms": [
        "zukam", "jukam", "nazla", "naak beh", "naak bah", "naak band", "sardi", "runny nose", "cold",
        "जुकाम", "नजला", "नाक बह", "नाक बंद", "सर्दी",
    ],
    "chills": ["thand lag", "thandi lag", "kaanp", "kapkapi", "chills", "ठंड लग", "कंपकंपी", "कांप"],
    "body_pain": [
        "badan dard", "badan mein dard", "badan me dard", "badan dukh", "sharir dard", "body pain", "body ache",
        "haath pair dard", "jodon mein dard", "jod dard", "joint pain", "badan tut", "badan toot",
        "बदन दर्द", "बदन में दर्द", "शरीर दर्द", "शरीर में दर्द", "हाथ पैर दर्द", "जोड़ों में दर्द", "जोड़ दर्द",
        "बदन टूट", "शरीर टूट",
    ],
    "weakness": [
        "kamzori", "kamjori", "thakan", "thakaan", "kamzor", "bahut kamzor", "weakness", "fatigue", "tired",
        "कमजोरी", "थकान", "कमजोर", "थकावट",
    ],
    "dizziness": [
        "chakkar", "chakkar aa", "sar ghoom", "sir ghoom", "ghumri", "dizzy", "dizziness", "lightheaded",
        "चक्कर", "सर घूम", "सिर घूम", "घूमरी",
    ],
    "palpitations": [
        "dil tez dhadak", "dhadkan tez", "dhadkan badh", "dil ghabra", "ghabrahat", "palpitation",
        "heart racing", "धड़कन तेज", "धड़कन बढ़", "घबराहट", "दिल घबरा", "दिल की धड़कन",
    ],
    "vomiting": [
        "ulti", "ultiyan", "ultiya", "ulti ho", "vomit", "vomiting", "vomited", "उल्टी", "उलटी", "ऊलटी",
    ],
    "nausea": ["ji machal", "jee michal", "ji michal", "ji kachcha", "nausea", "जी मचल", "जी मिचल", "जी घबरा"],
    "diarrhea": [
        "dast", "dast lag", "patle dast", "loose motion", "loose motions", "lose motion", "potty patli",
        "patli potty", "diarrhea", "diarrhoea", "दस्त", "पतले दस्त", "लूज मोशन", "पतली पॉटी",
    ],
    "stomach_upset": ["pet kharab", "पेट खराब", "pet ki gadbad", "पेट की गड़बड़"],
    "abdominal_pain": [
        "pet dard", "pet mein dard", "pet me dard", "pet dukh", "pet mein marod", "marod", "pet ka dard",
        "pet dukhe", "stomach pain", "stomach ache", "abdominal pain", "belly pain",
        "पेट दर्द", "पेट में दर्द", "पेट दुख", "पेट में मरोड़", "मरोड़", "पेट दुखै",
    ],
    "rash": [
        "daane", "dane", "chakatte", "chakte", "rash", "khujli", "khujali", "itching",
        "दाने", "चकत्ते", "खुजली", "लाल निशान",
    ],
    "dysuria": [
        "peshab mein jalan", "peshab me jalan", "peshab mein dard", "burning urination", "burning while urinating",
        "पेशाब में जलन", "पेशाब में दर्द",
    ],
    "blood_in_urine": ["peshab mein khoon", "peshab me khoon", "blood in urine", "पेशाब में खून"],
    "blood_in_stool": [
        "potty mein khoon", "mal mein khoon", "dast mein khoon", "blood in stool", "पॉटी में खून", "मल में खून",
        "दस्त में खून",
    ],
    "jaundice": [
        "peelia", "peeliya", "aankhen peeli", "aankhein peeli", "pili aankhen", "jaundice",
        "पीलिया", "आंखें पीली", "आँखें पीली", "पीली आंखें",
    ],
    "vision_change": [
        "dikhai nahi", "dhundhla", "dhundhli nazar", "nazar dhundhli", "aankhon ke samne andhera",
        "blurred vision", "double vision", "दिखाई नहीं", "धुंधला", "धुंधली नजर", "आंखों के सामने अंधेरा",
    ],
    "bleeding": [
        "khoon aa raha", "khoon aa rahi", "khoon nikal", "thoda khoon", "naak se khoon", "bleeding",
        "खून आ रहा", "खून आ रही", "खून निकल", "थोड़ा खून", "नाक से खून",
    ],
    "injury": [
        "chot", "chot lagi", "gir gaya", "gir gayi", "girne se", "accident", "haddi tut", "haddi toot",
        "fracture", "kat gaya", "kat gayi", "injury", "चोट", "चोट लगी", "गिर गया", "गिर गई", "गिरने से",
        "हड्डी टूट", "एक्सीडेंट", "कट गया", "कट गई",
    ],
    "burn": ["jal gaya", "jal gayi", "jalne se", "aag se jal", "burn", "burnt", "जल गया", "जल गई", "आग से जल"],
    "head_injury": [
        "sar par chot", "sir par chot", "sar mein chot", "sir mein chot", "head injury",
        "सर पर चोट", "सिर पर चोट", "सर में चोट", "सिर में चोट",
    ],
    "neck_stiffness": [
        "gardan akad", "gardan mein akadan", "gardan sakht", "gardan jakad", "gardan nahi mud", "stiff neck",
        "neck stiff", "गर्दन अकड़", "गर्दन जकड़", "गर्दन सख्त", "गर्दन में अकड़न",
    ],
    "dehydration_signs": [
        "peshab nahi", "peshab band", "peshab bahut kam", "aankhen dhans", "aankhein dhans", "munh sukh",
        "hoth sukh", "jibh sukh", "no urine", "dry mouth", "sunken eyes",
        "पेशाब नहीं", "पेशाब बंद", "पेशाब बहुत कम", "आंखें धंस", "आँखें धंस", "मुंह सूख", "मुँह सूख", "होंठ सूख",
    ],
    # Red flag concepts
    "breathlessness": [
        "saans lene mein", "saans lene me", "sans lene mein", "saans lene mein dikkat", "saans lene mein takleef",
        "saans phool", "sans phul", "dam phool", "dam phul", "dam ghut", "saans nahi aa", "saans nahi a pa",
        "saans chadh", "saans chade", "saans ukhad", "hafni", "hanfni", "saans ki takleef", "saans ki dikkat",
        "saans ki problem", "saans tez", "breathless", "shortness of breath", "difficulty breathing",
        "cant breathe", "can't breathe", "unable to breathe", "trouble breathing",
        "सांस लेने में", "साँस लेने में", "सांस फूल", "सांस नहीं आ", "सांस नहीं ले", "सांस चढ़", "सांस चढै",
        "दम फूल", "दम घुट", "हांफ", "सांस की तकलीफ", "सांस की दिक्कत", "सांस तेज", "सांस की परेशानी",
    ],
    "chest_pain": [
        "seene mein dard", "sine mein dard", "seene me dard", "chhati mein dard", "chaati mein dard",
        "chhati dukh", "seene mein jakdan", "seene par bojh", "seene mein dabav", "dil mein dard", "chest pain",
        "chest tightness", "pain in chest", "chest pressure",
        "सीने में दर्द", "छाती में दर्द", "छाती दुख", "सीने में जकड़न", "सीने पर बोझ", "सीने में दबाव",
        "दिल में दर्द", "सीने में भारीपन", "छाती दुखै",
    ],
    "loss_of_consciousness": [
        "behosh", "behoshi", "hosh nahi", "hosh kho", "chakkar khakar gir", "chakkar aakar gir", "unconscious",
        "fainted", "faint", "passed out", "blacked out", "murchha", "moorchha",
        "बेहोश", "बेहोशी", "होश नहीं", "होश खो", "चक्कर खाकर गिर", "चक्कर आकर गिर", "मूर्छा",
    ],
    "confusion": [
        "behki behki", "behki baat", "ulta seedha bol", "pehchan nahi", "pehchan nahi pa", "confused",
        "confusion", "bhram", "behka hua", "बहकी बहकी", "उल्टा सीधा बोल", "पहचान नहीं", "भ्रम", "बहका हुआ",
    ],
    "stroke_signs": [
        "chehra tedha", "munh tedha", "munh ek taraf", "chehra ek taraf", "munh latak", "ek taraf kamzori",
        "ek taraf ka haath", "ek taraf ka hath", "lakwa", "lakva", "paralysis", "paralyzed", "face drooping",
        "face droop", "slurred speech", "zubaan ladkhada", "zuban ladkhada", "jeebh ladkhada",
        "bolne mein dikkat", "bolne mein takleef", "bol nahi pa", "speech problem", "arm weakness",
        "चेहरा टेढ़ा", "मुंह टेढ़ा", "मुँह टेढ़ा", "एक तरफ कमजोरी", "एक तरफ का हाथ", "लकवा", "पैरालिसिस",
        "जुबान लड़खड़ा", "ज़ुबान लड़खड़ा", "बोलने में दिक्कत", "बोलने में तकलीफ", "बोल नहीं पा",
    ],
    "severe_bleeding": [
        "bahut khoon", "khoon band nahi", "khoon nahi ruk", "khoon beh raha", "khoon bah raha", "zyada khoon",
        "jyada khoon", "heavy bleeding", "severe bleeding", "bleeding wont stop", "bleeding won't stop",
        "खून बंद नहीं", "खून नहीं रुक", "बहुत खून", "ज्यादा खून", "खून बह रहा", "खून बह रही",
    ],
    "gi_bleeding_severe": [
        "khoon ki ulti", "ulti mein khoon", "ulti me khoon", "kala mal", "kaale rang ka mal", "kali potty",
        "black stool", "tarry stool", "vomiting blood", "blood in vomit", "vomit blood",
        "खून की उल्टी", "उल्टी में खून", "काला मल", "काली पॉटी", "काले रंग का मल",
    ],
    "allergic_severe": [
        "chehre par sujan", "hothon par sujan", "hont sujan", "gale mein sujan", "jeebh sujan", "jibh sujan",
        "zubaan sujan", "gala band", "swelling of face", "face swelling", "lip swelling", "throat swelling",
        "tongue swelling", "throat closing", "anaphylaxis",
        "मुंह पर सूजन", "चेहरे पर सूजन", "होंठ सूजन", "होंठों पर सूजन", "गले में सूजन", "जीभ सूजन", "गला बंद",
    ],
    "seizure": [
        "daura pad", "dora pad", "daura", "mirgi", "jhatke aa", "jhatke", "hath pair akad", "akad gaya",
        "akadan", "fits", "fit aa", "seizure", "convulsion", "convulsions",
        "दौरा", "मिर्गी", "झटके", "अकड़न", "हाथ पैर अकड़",
    ],
    "snakebite": [
        "saanp ne kata", "saap ne kata", "saanp kata", "saanp ka kaata", "sanp ne kata", "snake bite", "snakebite",
        "bitten by snake", "साँप ने काटा", "सांप ने काटा", "सांप काटा", "साँप काटा", "सांप के काटने",
    ],
    "poisoning": [
        "zehar", "jahar", "zahar kha", "jahar kha", "vish", "keetnashak", "kitnashak", "keede marne ki dawa",
        "poison", "poisoned", "overdose", "pesticide", "insecticide",
        "जहर", "जहर खा", "विष", "कीटनाशक", "कीड़े मारने की दवा", "ज्यादा गोलियां खा",
    ],
    "worst_headache": [
        "sabse tez sar dard", "sabse bura sar dard", "sabse jyada sar dard", "worst headache",
        "सबसे तेज सर दर्द", "सबसे तेज सिर दर्द", "सबसे बुरा सर दर्द",
    ],
    "self_harm": [
        "khudkushi", "suicide", "jaan dena", "marna chahta", "marna chahti", "jeena nahi chahta",
        "jeena nahi chahti", "mar jana chahta", "end my life", "kill myself",
        "आत्महत्या", "खुदकुशी", "मरना चाहता", "मरना चाहती", "जान देना", "जीना नहीं चाहता", "जीना नहीं चाहती",
        "जीने का मन नहीं",
    ],
    # Context entries
    "ctx:pregnant": [
        "garbhvati", "garbh se", "pregnant", "pregnancy", "hamila", "pet se hu", "pet se hoon", "pet se hai",
        "गर्भवती", "गर्भ से", "प्रेग्नेंट", "पेट से हूँ", "पेट से हूं", "पेट से है", "गर्भावस्था",
    ],
    "ctx:diabetes": [
        "sugar ki bimari", "sugar ka mareez", "sugar ke mareez", "diabetes", "diabetic", "madhumeh",
        "शुगर की बीमारी", "शुगर का मरीज", "मधुमेह", "डायबिटीज",
    ],
    "ctx:hypertension": [
        "bp ki dawa", "bp high", "bp ki bimari", "blood pressure", "hypertension", "बीपी की दवा",
        "बीपी हाई", "ब्लड प्रेशर", "बीपी की बीमारी",
    ],
    "ctx:heart_disease": [
        "dil ki bimari", "dil ka mareez", "heart patient", "heart ki bimari", "stent", "bypass",
        "दिल की बीमारी", "दिल का मरीज", "हार्ट पेशेंट", "स्टेंट",
    ],
    "ctx:asthma": ["dama", "asthma", "दमा", "अस्थमा"],
    "ctx:kidney_disease": [
        "kidney ki bimari", "gurde ki bimari", "dialysis", "किडनी की बीमारी", "गुर्दे की बीमारी", "डायलिसिस",
    ],
    "ctx:cancer": ["cancer", "कैंसर"],
    "ctx:tuberculosis": ["tb", "tuberculosis", "टीबी", "क्षय रोग"],
}

# Base confidence for a lexicon hit. Ambiguous concepts get less because several clinical
# readings are possible and the patient should be asked to clarify.
DEFAULT_CONFIDENCE = 0.92
AMBIGUOUS_CONFIDENCE = 0.82


@dataclass(frozen=True)
class CompiledPhrase:
    tokens: tuple[str, ...]
    concept: str
    original: str


def _compile() -> dict[str, list[CompiledPhrase]]:
    index: dict[str, list[CompiledPhrase]] = defaultdict(list)
    for concept, phrases in LEXICON.items():
        for phrase in phrases:
            tokens = fold_phrase(phrase)
            if tokens:
                index[tokens[0]].append(CompiledPhrase(tokens, concept, phrase))
    for entries in index.values():
        entries.sort(key=lambda p: len(p.tokens), reverse=True)  # longest match wins
    return dict(index)


PHRASE_INDEX = _compile()

# Single token Latin phrases eligible for typo tolerant matching.
FUZZY_CANDIDATES: dict[str, str] = {
    p.tokens[0]: p.concept
    for entries in PHRASE_INDEX.values()
    for p in entries
    if len(p.tokens) == 1 and len(p.tokens[0]) >= 6 and p.tokens[0].isascii()
}
