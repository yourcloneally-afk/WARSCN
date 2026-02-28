"""Lightweight i18n: ~50 key phrases in EN, HE, FA, AR."""

TRANSLATIONS = {
    "app_name": {
        "en": "EvacScan",
        "he": "EvacScan",
        "fa": "EvacScan",
        "ar": "EvacScan",
    },
    "tagline": {
        "en": "Real-Time Conflict Monitor & Evacuation Tool",
        "he": "כלי ניטור עימותים ופינוי בזמן אמת",
        "fa": "ابزار نظارت بر درگیری و تخلیه در لحظه",
        "ar": "أداة مراقبة النزاعات والإخلاء في الوقت الفعلي",
    },
    # --- Threat levels ---
    "threat_critical": {
        "en": "CRITICAL THREAT",
        "he": "איום קריטי",
        "fa": "تهدید بحرانی",
        "ar": "تهديد حرج",
    },
    "threat_high": {
        "en": "HIGH THREAT",
        "he": "איום גבוה",
        "fa": "تهدید بالا",
        "ar": "تهديد مرتفع",
    },
    "threat_moderate": {
        "en": "MODERATE THREAT",
        "he": "איום בינוני",
        "fa": "تهدید متوسط",
        "ar": "تهديد معتدل",
    },
    "threat_low": {
        "en": "LOW THREAT",
        "he": "איום נמוך",
        "fa": "تهدید پایین",
        "ar": "تهديد منخفض",
    },
    "threat_unknown": {
        "en": "STATUS UNKNOWN",
        "he": "מצב לא ידוע",
        "fa": "وضعیت نامشخص",
        "ar": "الحالة غير معروفة",
    },
    # --- Action suggestions ---
    "action_critical": {
        "en": "Seek shelter immediately. Do not travel unless evacuating.",
        "he": "חפשו מחסה מיד. אל תנסעו אלא אם כן מפנים.",
        "fa": "فوراً به پناهگاه بروید. سفر نکنید مگر برای تخلیه.",
        "ar": "ابحث عن مأوى فوراً. لا تسافر إلا للإخلاء.",
    },
    "action_high": {
        "en": "Review evacuation routes. Stay alert for updates.",
        "he": "בדקו מסלולי פינוי. הישארו עירניים לעדכונים.",
        "fa": "مسیرهای تخلیه را بررسی کنید. هوشیار باشید.",
        "ar": "راجع طرق الإخلاء. ابقَ متيقظاً للتحديثات.",
    },
    "action_moderate": {
        "en": "Monitor updates. Prepare emergency supplies.",
        "he": "עקבו אחר עדכונים. הכינו ציוד חירום.",
        "fa": "به‌روزرسانی‌ها را دنبال کنید. لوازم اضطراری آماده کنید.",
        "ar": "تابع التحديثات. جهّز مستلزمات الطوارئ.",
    },
    "action_low": {
        "en": "No immediate action needed. Stay informed.",
        "he": "אין צורך בפעולה מיידית. הישארו מעודכנים.",
        "fa": "نیازی به اقدام فوری نیست. مطلع باشید.",
        "ar": "لا حاجة لإجراء فوري. ابقَ على اطلاع.",
    },
    "action_unknown": {
        "en": "Unable to assess threat. Check official sources.",
        "he": "לא ניתן להעריך איום. בדקו מקורות רשמיים.",
        "fa": "ارزیابی تهدید ممکن نیست. منابع رسمی را بررسی کنید.",
        "ar": "تعذّر تقييم التهديد. راجع المصادر الرسمية.",
    },
    # --- Navigation ---
    "nav_map": {"en": "Map", "he": "מפה", "fa": "نقشه", "ar": "خريطة"},
    "nav_feed": {"en": "Feed", "he": "פיד", "fa": "فید", "ar": "آخر الأخبار"},
    "nav_evacuate": {"en": "Evacuate", "he": "פינוי", "fa": "تخلیه", "ar": "إخلاء"},
    "nav_resources": {"en": "Resources", "he": "משאבים", "fa": "منابع", "ar": "موارد"},
    "nav_about": {"en": "About", "he": "אודות", "fa": "درباره", "ar": "حول"},
    # --- Buttons ---
    "btn_my_location": {
        "en": "Use My Location",
        "he": "השתמש במיקום שלי",
        "fa": "از موقعیت من استفاده کن",
        "ar": "استخدم موقعي",
    },
    "btn_calculate_route": {
        "en": "Calculate Safe Route",
        "he": "חשב מסלול בטוח",
        "fa": "محاسبه مسیر امن",
        "ar": "احسب المسار الآمن",
    },
    "btn_download_pdf": {
        "en": "Download Evacuation Plan (PDF)",
        "he": "הורד תוכנית פינוי (PDF)",
        "fa": "دانلود طرح تخلیه (PDF)",
        "ar": "تحميل خطة الإخلاء (PDF)",
    },
    "btn_im_safe": {
        "en": "I'm Safe",
        "he": "אני בטוח",
        "fa": "من در امانم",
        "ar": "أنا بأمان",
    },
    "btn_share": {"en": "Share", "he": "שתף", "fa": "اشتراک‌گذاری", "ar": "مشاركة"},
    "btn_battery_saver": {
        "en": "Battery Saver",
        "he": "חיסכון בסוללה",
        "fa": "صرفه‌جویی باتری",
        "ar": "توفير البطارية",
    },
    # --- Event categories ---
    "cat_confirmed": {"en": "Confirmed", "he": "מאושר", "fa": "تأیید شده", "ar": "مؤكد"},
    "cat_developing": {"en": "Developing", "he": "מתפתח", "fa": "در حال توسعه", "ar": "قيد التطور"},
    "cat_rumored": {"en": "Rumored", "he": "שמועה", "fa": "شایعه", "ar": "شائعة"},
    # --- Alert messages ---
    "alert_nearby": {
        "en": "ALERT: {title} reported {distance}km from your location",
        "he": "התראה: {title} דווח {distance} ק\"מ ממיקומך",
        "fa": "هشدار: {title} در {distance} کیلومتری شما گزارش شده",
        "ar": "تنبيه: {title} تم الإبلاغ عنه على بعد {distance} كم من موقعك",
    },
    "alert_severity": {
        "en": "Severity: {level}. {sources} sources.",
        "he": "חומרה: {level}. {sources} מקורות.",
        "fa": "شدت: {level}. {sources} منبع.",
        "ar": "الخطورة: {level}. {sources} مصادر.",
    },
    # --- Misc ---
    "last_updated": {
        "en": "Last updated",
        "he": "עודכן לאחרונה",
        "fa": "آخرین به‌روزرسانی",
        "ar": "آخر تحديث",
    },
    "data_stale": {
        "en": "Data may be stale. Check official sources.",
        "he": "הנתונים עשויים להיות לא עדכניים. בדקו מקורות רשמיים.",
        "fa": "داده‌ها ممکن است قدیمی باشند. منابع رسمی را بررسی کنید.",
        "ar": "قد تكون البيانات قديمة. راجع المصادر الرسمية.",
    },
    "disclaimer": {
        "en": "EvacScan aggregates publicly available data. Always verify with official emergency services. This is not a substitute for professional guidance.",
        "he": "EvacScan מאגד נתונים ציבוריים. תמיד אמתו עם שירותי החירום הרשמיים. כלי זה אינו תחליף להנחיות מקצועיות.",
        "fa": "EvacScan داده‌های عمومی را جمع‌آوری می‌کند. همیشه با خدمات اضطراری رسمی تأیید کنید. این جایگزین راهنمایی حرفه‌ای نیست.",
        "ar": "EvacScan يجمع البيانات المتاحة للعامة. تحقق دائماً من خدمات الطوارئ الرسمية. هذه الأداة ليست بديلاً عن الإرشاد المهني.",
    },
    "no_events": {
        "en": "No events found for the current filters.",
        "he": "לא נמצאו אירועים עבור הסינון הנוכחי.",
        "fa": "هیچ رویدادی برای فیلترهای فعلی یافت نشد.",
        "ar": "لم يتم العثور على أحداث للفلاتر الحالية.",
    },
    "offline_mode": {
        "en": "You are offline. Showing cached data.",
        "he": "אתם במצב לא מקוון. מוצגים נתונים מהמטמון.",
        "fa": "شما آفلاین هستید. داده‌های ذخیره‌شده نمایش داده می‌شود.",
        "ar": "أنت غير متصل. يتم عرض البيانات المخزنة مؤقتاً.",
    },
    "emergency_title": {
        "en": "Emergency Resources",
        "he": "משאבי חירום",
        "fa": "منابع اضطراری",
        "ar": "موارد الطوارئ",
    },
}

RTL_LANGUAGES = {"he", "fa", "ar"}


def t(key, lang="en", **kwargs):
    entry = TRANSLATIONS.get(key, {})
    text = entry.get(lang, entry.get("en", key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def is_rtl(lang):
    return lang in RTL_LANGUAGES
