"""Patient facing text.

Internal results are structured codes. Only this module turns them into
sentences, so the clinical meaning cannot drift during localisation. Texts for
Hindi (Devanagari), romanised Hindi and English are fixed templates that a
reviewer can read in full. Other languages are served only through the
optional translation provider, with validation, or fall back to Hindi.

REVIEW REQUIRED: wording must be checked by native speakers and clinicians.
"""

from dataclasses import dataclass

from pydantic import BaseModel

from app.ai.base import ProviderError, TranslationProvider
from app.clinical.triage import TriageResult
from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.clinical import TriageLevel

log = get_logger("localization")

TEMPLATE_LANGUAGES = ("hi", "hi-Latn", "en")

DISCLAIMER = {
    "hi": "यह टूल केवल शुरुआती स्वास्थ्य सलाह देता है। यह किसी बीमारी की पहचान नहीं करता और योग्य डॉक्टर की जगह नहीं ले सकता।",
    "hi-Latn": "Yeh tool sirf shuruaati swasthya salah deta hai. Yeh kisi bimari ki pehchan nahi karta aur yogya doctor ki jagah nahi le sakta.",
    "en": "This tool provides preliminary health triage guidance. It does not diagnose medical conditions and does not replace a qualified healthcare professional.",
}

GREETING = {
    "hi": "नमस्ते। मैं स्वास्थ्य जानकारी में मदद करने वाला सहायक हूं, डॉक्टर नहीं। ",
    "hi-Latn": "Namaste. Main swasthya jaankari mein madad karne wala sahayak hoon, doctor nahi. ",
    "en": "Hello. I am a health guidance assistant, not a doctor. ",
}
REASK_PREFIX = {
    "hi": "माफ कीजिए, मुझे ठीक से समझ नहीं आया। ",
    "hi-Latn": "Maaf kijiye, mujhe theek se samajh nahi aaya. ",
    "en": "Sorry, I did not quite understand. ",
}

WARNING_SIGNS = {
    "hi": ["सांस लेने में बहुत दिक्कत", "सीने में दर्द", "बेहोशी या बहुत ज्यादा उलझन",
           "चेहरा टेढ़ा होना, एक तरफ कमजोरी या बोलने में दिक्कत", "दौरा या झटके", "बहुत ज्यादा खून बहना",
           "चेहरे, होंठ या गले में सूजन", "लगातार उल्टी या पानी न पी पाना"],
    "hi-Latn": ["Saans lene mein bahut dikkat", "Seene mein dard", "Behoshi ya bahut zyada uljhan",
                "Chehra tedha hona, ek taraf kamzori ya bolne mein dikkat", "Daura ya jhatke", "Bahut zyada khoon behna",
                "Chehre, honth ya gale mein sujan", "Lagataar ulti ya paani na pi paana"],
    "en": ["Severe difficulty breathing", "Chest pain", "Fainting or severe confusion",
           "Drooping face, weakness on one side or trouble speaking", "Seizure or convulsions", "Heavy bleeding",
           "Swelling of the face, lips or throat", "Constant vomiting or being unable to drink water"],
}

_RESULT = {
    TriageLevel.EMERGENCY: {
        "hi": ("तुरंत इलाज की जरूरत हो सकती है",
               "आपने जो बताया उसके आधार पर आपको अभी तुरंत चिकित्सा सहायता की जरूरत हो सकती है। कृपया देर न करें।",
               ["नजदीकी अस्पताल या स्वास्थ्य केंद्र तुरंत पहुंचें, या एम्बुलेंस बुलाएं।", "{contact}",
                "मरीज को अकेला न छोड़ें।", "अगर संभव हो तो कोई और गाड़ी चलाए, मरीज खुद गाड़ी न चलाए।"]),
        "hi-Latn": ("Turant ilaaj ki zaroorat ho sakti hai",
                    "Aapne jo bataya uske aadhar par aapko abhi turant chikitsa sahayata ki zaroorat ho sakti hai. Kripya der na karein.",
                    ["Nazdeeki aspatal ya swasthya kendra turant pahunchein, ya ambulance bulayein.", "{contact}",
                     "Mareez ko akela na chhodein.", "Agar sambhav ho to koi aur gaadi chalaye, mareez khud gaadi na chalaye."]),
        "en": ("You may need urgent medical care",
               "Based on what you told me, you may need immediate medical attention. Please do not delay.",
               ["Go to the nearest hospital or health centre now, or call an ambulance.", "{contact}",
                "Do not leave the patient alone.", "If possible, let someone else drive. The patient should not drive."]),
    },
    TriageLevel.URGENT: {
        "hi": ("जल्दी डॉक्टर को दिखाना चाहिए",
               "आपके बताए लक्षणों के आधार पर आपको जल्द से जल्द, हो सके तो आज ही, किसी डॉक्टर या स्वास्थ्य केंद्र में जांच करानी चाहिए।",
               ["हो सके तो आज ही नजदीकी स्वास्थ्य केंद्र या डॉक्टर के पास जाएं।",
                "डॉक्टर को अपने सभी लक्षण और वे कितने दिन से हैं, यह बताएं।",
                "नीचे लिखे चेतावनी वाले लक्षण दिखें तो तुरंत आपातकालीन मदद लें।"]),
        "hi-Latn": ("Jaldi doctor ko dikhana chahiye",
                    "Aapke bataye lakshanon ke aadhar par aapko jald se jald, ho sake to aaj hi, kisi doctor ya swasthya kendra mein jaanch karani chahiye.",
                    ["Ho sake to aaj hi nazdeeki swasthya kendra ya doctor ke paas jaayein.",
                     "Doctor ko apne sabhi lakshan aur woh kitne din se hain, yeh bataayein.",
                     "Neeche likhe chetavani wale lakshan dikhein to turant aapatkaleen madad lein."]),
        "en": ("Please see a doctor soon",
               "Based on the symptoms you described, you should be checked by a doctor or health centre as soon as possible, ideally today.",
               ["If you can, go to the nearest health centre or doctor today.",
                "Tell the doctor all your symptoms and how many days you have had them.",
                "If any of the warning signs below appear, get emergency help immediately."]),
    },
    TriageLevel.NON_URGENT: {
        "hi": ("अभी आपातकाल जैसा नहीं लग रहा, फिर भी ध्यान रखें",
               "आपकी दी गई जानकारी के आधार पर अभी आपातकालीन स्थिति जैसा नहीं लगता, लेकिन यह डॉक्टर की जांच की जगह नहीं है। "
               "अगर तकलीफ बनी रहे या बढ़े, तो डॉक्टर या स्वास्थ्य केंद्र से जरूर मिलें।",
               ["अपने लक्षणों पर नजर रखें और नोट करें कि वे कब से हैं।",
                "तकलीफ बढ़े, कुछ दिनों में ठीक न हो, या नए लक्षण आएं तो डॉक्टर को दिखाएं।",
                "नीचे लिखे चेतावनी वाले लक्षण दिखें तो तुरंत आपातकालीन मदद लें।"]),
        "hi-Latn": ("Abhi aapatkaal jaisa nahi lag raha, phir bhi dhyan rakhein",
                    "Aapki di gayi jaankari ke aadhar par abhi aapatkaleen sthiti jaisa nahi lagta, lekin yeh doctor ki jaanch ki jagah nahi hai. "
                    "Agar takleef bani rahe ya badhe, to doctor ya swasthya kendra se zaroor milein.",
                    ["Apne lakshanon par nazar rakhein aur note karein ki woh kab se hain.",
                     "Takleef badhe, kuch dinon mein theek na ho, ya naye lakshan aayein to doctor ko dikhayein.",
                     "Neeche likhe chetavani wale lakshan dikhein to turant aapatkaleen madad lein."]),
        "en": ("This does not look like an emergency right now, but stay alert",
               "Based on the information you gave, this does not currently appear to need emergency escalation, but this is not a substitute "
               "for a doctor. If the problem continues or gets worse, please see a doctor or health centre.",
               ["Keep watching your symptoms and note how long you have had them.",
                "See a doctor if it gets worse, does not improve within a few days, or new symptoms appear.",
                "If any of the warning signs below appear, get emergency help immediately."]),
    },
}

_INSUFFICIENT = {
    "hi": "हमारे पास सुरक्षित सलाह देने के लिए पूरी जानकारी नहीं है, इसलिए सावधानी के तौर पर डॉक्टर से जांच कराना बेहतर होगा।",
    "hi-Latn": "Hamare paas surakshit salah dene ke liye poori jaankari nahi hai, isliye saavdhani ke taur par doctor se jaanch karana behtar hoga.",
    "en": "I do not have enough information to give safe advice, so as a precaution it is better to be checked by a doctor.",
}
_SELF_HARM = {
    "hi": ("आपकी बात हमारे लिए जरूरी है", "आपने जो साझा किया वह बहुत गंभीर है। कृपया अभी किसी भरोसेमंद व्यक्ति के पास जाएं या उन्हें अपने पास बुलाएं और तुरंत मदद लें।"),
    "hi-Latn": ("Aapki baat hamare liye zaroori hai", "Aapne jo saajha kiya woh bahut gambhir hai. Kripya abhi kisi bharosemand vyakti ke paas jaayein ya unhein apne paas bulayein aur turant madad lein."),
    "en": ("What you shared matters", "What you shared is very serious. Please go to a trusted person or ask them to come to you right now, and get help immediately."),
}
_CONTACT_LINE = {
    "hi": ("आपातकालीन नंबर: {label}{number}", "अपने क्षेत्र की आपातकालीन सेवा, नजदीकी स्वास्थ्य केंद्र या किसी भरोसेमंद व्यक्ति से तुरंत मदद लें।"),
    "hi-Latn": ("Aapatkaleen number: {label}{number}", "Apne kshetra ki aapatkaleen seva, nazdeeki swasthya kendra ya kisi bharosemand vyakti se turant madad lein."),
    "en": ("Emergency number: {label}{number}", "Contact your local emergency service, the nearest health centre, or a trusted person right away."),
}
_CRISIS_LINE = {"hi": "संकट सहायता नंबर: {n}", "hi-Latn": "Sankat sahayata number: {n}", "en": "Crisis helpline: {n}"}


class EmergencyContact(BaseModel):
    number: str
    label: str = ""


class PatientResult(BaseModel):
    level: TriageLevel
    language: str
    headline: str
    message: str
    next_steps: list[str]
    warning_signs: list[str]
    disclaimer: str
    emergency_contact: EmergencyContact | None = None


def resolve_language(detected: str | None, preferred: str | None = None, settings: Settings | None = None) -> str:
    """Pick the language for patient facing text from detection and the UI choice."""
    extra = settings.translation_language_list if settings else []
    if preferred in TEMPLATE_LANGUAGES or preferred in extra:
        return preferred  # type: ignore[return-value]
    return {"hi": "hi", "mwr": "hi", "hi-Latn": "hi-Latn", "en": "en"}.get(detected or "", "hi")


def _tpl(table: dict, lang: str):  # type: ignore[no-untyped-def]
    return table.get(lang) or table["hi"]


def emergency_contact(settings: Settings) -> EmergencyContact | None:
    if settings.emergency_contact_number.strip():
        return EmergencyContact(number=settings.emergency_contact_number.strip(), label=settings.emergency_contact_label.strip())
    return None


@dataclass
class Localizer:
    settings: Settings
    translator: TranslationProvider | None = None

    def disclaimer(self, lang: str) -> str:
        return _tpl(DISCLAIMER, lang if lang in TEMPLATE_LANGUAGES else "hi")

    def greeting(self, lang: str) -> str:
        return _tpl(GREETING, lang if lang in TEMPLATE_LANGUAGES else "hi")

    def reask_prefix(self, lang: str) -> str:
        return _tpl(REASK_PREFIX, lang if lang in TEMPLATE_LANGUAGES else "hi")

    def _contact_text(self, lang: str, level_self_harm: bool) -> str:
        with_number, without = _tpl(_CONTACT_LINE, lang)
        contact = emergency_contact(self.settings)
        lines = [with_number.format(label=(contact.label + " ") if contact and contact.label else "", number=contact.number)
                 if contact else without]
        if level_self_harm and self.settings.crisis_helpline_number.strip():
            lines.append(_tpl(_CRISIS_LINE, lang).format(n=self.settings.crisis_helpline_number.strip()))
        return " ".join(lines)

    def render_result(self, result: TriageResult, lang: str) -> PatientResult:
        template_lang = lang if lang in TEMPLATE_LANGUAGES else "hi"
        headline, message, steps = _tpl(_RESULT[result.triage_level], template_lang)
        self_harm = "mental_health_crisis" in result.reason_codes
        if self_harm:
            headline, message = _tpl(_SELF_HARM, template_lang)
        if "insufficient_information" in result.reason_codes:
            message = f"{message} {_tpl(_INSUFFICIENT, template_lang)}"
        contact = self._contact_text(template_lang, self_harm)
        steps = [s.format(contact=contact) if "{contact}" in s else s for s in steps]
        if result.triage_level == TriageLevel.EMERGENCY and not any(contact in s for s in steps):
            steps.append(contact)
        out = PatientResult(
            level=result.triage_level, language=template_lang, headline=headline, message=message, next_steps=steps,
            warning_signs=_tpl(WARNING_SIGNS, template_lang), disclaimer=self.disclaimer(template_lang),
            emergency_contact=emergency_contact(self.settings),
        )
        if lang not in TEMPLATE_LANGUAGES:
            out = self._translate(out, lang)
        return out

    def _translate(self, result: PatientResult, lang: str) -> PatientResult:
        """Translate reviewed English text for an extra language. Falls back to Hindi on any problem."""
        if self.translator is None or lang not in self.settings.translation_language_list:
            return result
        try:
            english = self._render_english_source(result)
            return result.model_copy(update={
                "language": lang,
                "headline": self.translator.translate(english["headline"], lang),
                "message": self.translator.translate(english["message"], lang),
                "next_steps": [self.translator.translate(s, lang) for s in english["next_steps"]],
                "warning_signs": [self.translator.translate(s, lang) for s in WARNING_SIGNS["en"]],
                "disclaimer": self.translator.translate(DISCLAIMER["en"], lang),
            })
        except ProviderError as exc:
            log.warning("translation failed, using Hindi", extra={"target": lang, "reason": exc.reason})
            return result

    def _render_english_source(self, result: PatientResult) -> dict:
        headline, message, steps = _tpl(_RESULT[result.level], "en")
        contact = self._contact_text("en", False)
        return {"headline": headline, "message": message, "next_steps": [s.format(contact=contact) for s in steps]}
