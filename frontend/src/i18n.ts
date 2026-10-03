export type Lang = "hi" | "en";

const STRINGS = {
  hi: {
    appName: "स्वास्थ्य सहायक",
    online: "इंटरनेट चालू", offline: "इंटरनेट बंद",
    welcomeTitle: "अपनी तकलीफ बोलकर बताइए",
    welcomeLead: "यह टूल आपके लक्षण सुनकर बताता है कि आपको कितनी जल्दी डॉक्टर को दिखाना चाहिए।",
    does: "यह क्या करता है", does1: "आपकी बात हिंदी या हिंदी और अंग्रेजी मिलाकर सुनता है।", does2: "कुछ जरूरी सवाल पूछता है।", does3: "बताता है कि अभी क्या करना ठीक रहेगा।",
    doesNot: "यह क्या नहीं करता", not1: "यह बीमारी की पहचान (डायग्नोसिस) नहीं करता।", not2: "यह डॉक्टर की जगह नहीं ले सकता।", not3: "यह इलाज या दवा नहीं बताता।",
    emergencyTitle: "इन हालात में इंतजार न करें",
    emergencyLead: "अगर इनमें से कुछ भी हो तो इस टूल का इंतजार न करें, तुरंत नजदीकी अस्पताल जाएं या एम्बुलेंस बुलाएं:",
    emergencyContact: "आपातकालीन नंबर", emergencyContactMissing: "अपने क्षेत्र की आपातकालीन सेवा या नजदीकी स्वास्थ्य केंद्र से संपर्क करें।",
    start: "शुरू करें", language: "भाषा",
    micStart: "बोलने के लिए दबाएं", micStop: "रोकने के लिए दबाएं", recording: "रिकॉर्ड हो रहा है", processing: "आपकी बात सुन रहे हैं…",
    micUnsupported: "इस फोन या ब्राउज़र में रिकॉर्डिंग नहीं चल सकती। कृपया नीचे लिखकर बताएं।",
    micDenied: "माइक्रोफोन की अनुमति नहीं मिली। कृपया नीचे लिखकर बताएं, या ब्राउज़र की सेटिंग में अनुमति दें।",
    weHeard: "हमने यह सुना (गलत हो तो ठीक करें):", typeHere: "या यहां लिखकर बताएं", send: "भेजें", yourMessage: "आपकी बात",
    lowConfidence: "आवाज साफ नहीं सुनाई दी। कृपया ऊपर का लिखा हुआ ठीक करें या फिर से बोलें।", noSpeech: "कुछ सुनाई नहीं दिया। कृपया पास से, धीरे और साफ बोलें।",
    listen: "सुनें", stopListening: "बंद करें", listenUnavailable: "आवाज में सुनाना अभी उपलब्ध नहीं है।",
    helper: "सहायक", you: "आप", sending: "भेज रहे हैं…", retry: "फिर से कोशिश करें",
    resultTitle: "आपके लिए सुझाव", nextSteps: "अभी क्या करें", warningSigns: "ये दिखें तो तुरंत आपातकालीन मदद लें",
    levelEmergency: "तुरंत मदद", levelUrgent: "जल्दी दिखाएं", levelNonUrgent: "ध्यान रखें",
    startOver: "नई बातचीत", deleteData: "मेरी बातचीत मिटाएं", deleted: "आपकी बातचीत मिटा दी गई है।",
    errNetwork: "इंटरनेट नहीं मिल रहा। कनेक्शन जांचकर फिर कोशिश करें।", errTimeout: "जवाब आने में देर हो रही है। फिर कोशिश करें।",
    errRate: "बहुत जल्दी-जल्दी कोशिश हुई। थोड़ा रुककर फिर करें।", errSession: "यह बातचीत खत्म हो चुकी है। नई बातचीत शुरू करें।",
    errServer: "कुछ गड़बड़ हो गई। थोड़ी देर बाद फिर कोशिश करें।", errVoice: "आवाज की सुविधा अभी उपलब्ध नहीं है। कृपया लिखकर बताएं।",
    errAudio: "रिकॉर्डिंग ठीक नहीं थी। कृपया फिर से बोलें या लिखें।", errInput: "कृपया अपनी बात थोड़ी छोटी करके लिखें।",
    disclaimer: "यह टूल केवल शुरुआती स्वास्थ्य सलाह देता है। यह किसी बीमारी की पहचान नहीं करता और योग्य डॉक्टर की जगह नहीं ले सकता।",
    sec: "सेकंड",
  },
  en: {
    appName: "Health Helper",
    online: "Online", offline: "Offline",
    welcomeTitle: "Tell us your problem by speaking",
    welcomeLead: "This tool listens to your symptoms and tells you how soon you should see a doctor.",
    does: "What it does", does1: "Listens to Hindi, or Hindi mixed with English.", does2: "Asks a few important questions.", does3: "Tells you what is sensible to do next.",
    doesNot: "What it does not do", not1: "It does not diagnose any illness.", not2: "It does not replace a doctor.", not3: "It does not prescribe treatment or medicine.",
    emergencyTitle: "Do not wait in these situations",
    emergencyLead: "If any of these happen, do not wait for this tool. Go to the nearest hospital now or call an ambulance:",
    emergencyContact: "Emergency number", emergencyContactMissing: "Contact your local emergency service or the nearest health centre.",
    start: "Start", language: "Language",
    micStart: "Press to speak", micStop: "Press to stop", recording: "Recording", processing: "Listening to what you said…",
    micUnsupported: "Recording does not work on this phone or browser. Please type below.",
    micDenied: "Microphone permission was not given. Please type below, or allow the microphone in your browser settings.",
    weHeard: "We heard this (please correct it if wrong):", typeHere: "Or type here", send: "Send", yourMessage: "Your message",
    lowConfidence: "The audio was not clear. Please correct the text above or speak again.", noSpeech: "We could not hear anything. Please speak closer, slowly and clearly.",
    listen: "Listen", stopListening: "Stop", listenUnavailable: "Reading aloud is not available right now.",
    helper: "Helper", you: "You", sending: "Sending…", retry: "Try again",
    resultTitle: "Guidance for you", nextSteps: "What to do now", warningSigns: "If you see these, get emergency help at once",
    levelEmergency: "Get help now", levelUrgent: "See a doctor soon", levelNonUrgent: "Stay alert",
    startOver: "New conversation", deleteData: "Delete my conversation", deleted: "Your conversation has been deleted.",
    errNetwork: "Cannot reach the internet. Check your connection and try again.", errTimeout: "This is taking too long. Please try again.",
    errRate: "Too many attempts. Please wait a moment and try again.", errSession: "This conversation has ended. Please start a new one.",
    errServer: "Something went wrong. Please try again in a little while.", errVoice: "Voice is not available right now. Please type instead.",
    errAudio: "The recording was not usable. Please speak again or type.", errInput: "Please shorten your message and try again.",
    disclaimer: "This tool provides preliminary health triage guidance. It does not diagnose medical conditions and does not replace a qualified healthcare professional.",
    sec: "seconds",
  },
} as const;

export type Key = keyof (typeof STRINGS)["hi"];

let current: Lang = "hi";

export function setLang(lang: Lang): void {
  current = lang;
  document.documentElement.lang = lang;
}
export function getLang(): Lang {
  return current;
}
export function t(key: Key): string {
  return STRINGS[current][key];
}
export const ALL_STRINGS = STRINGS;
