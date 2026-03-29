"""
backend/classifier.py — Shared Query Classifier & Static Responses
===================================================================
Single authoritative source for QueryClassifier and STATIC responses.
Import from here — never copy-paste this class into other files.

    from backend.classifier import QueryClassifier, STATIC
"""

import re


class QueryClassifier:
    GREETINGS = {
        "hi", "hello", "hey", "hii", "hiii", "heya", "helo",
        "good morning", "good afternoon", "good evening",
        "assalam", "salam", "aoa", "assalamualaikum",
        "hi there", "hey there", "howdy", "sup", "whats up",
        "yo", "greetings", "hola",
    }

    CASUAL = [
        r"how\s+are\s+you", r"how\s+r\s+u", r"how\s+are\s+u",
        r"how.?s\s+it\s+going", r"what.?s\s+up",
        r"how\s+is\s+your\s+day", r"are\s+you\s+there",
        r"how\s+are\s+things", r"how\s+do\s+you\s+do",
        r"how\s+you\s+doing", r"hows\s+life",
    ]

    IDENTITY = [
        r"who\s+are\s+(you|u|ya)",
        r"what\s+are\s+(you|u|ya)",
        r"what\s+is\s+your\s+name",
        r"what\s+can\s+(you|u)\s+do",
        r"what\s+do\s+(you|u)\s+do",
        r"tell\s+me\s+about\s+(yourself|urself)",
        r"introduce\s+(yourself|urself)",
        r"are\s+(you|u)\s+(a\s+)?(bot|ai|chatbot|assistant|human|robot|machine)",
        r"which\s+model",
        r"what\s+model",
        r"what\s+llm",
        r"are\s+u\s+real",
        r"r\s+u\s+(a\s+)?(bot|ai|real)",
        r"^help\s*$",
        r"^help\s+me\s*$",
        r"who\s+r\s+u",
        r"who\s+made\s+(you|u)",
        r"who\s+created\s+(you|u)",
        r"who\s+built\s+(you|u)",
    ]

    FAREWELL = [
        r"^(bye|goodbye|good\s*bye|see\s+you|cya|take\s+care|khuda\s+hafiz|allah\s+hafiz)\b",
    ]

    THANKS = [
        r"^(thanks|thank\s+you|thankyou|thx|shukriya|shukria|ok\s+thanks|ty|tysm)\b",
        r"^(ok|okay|alright|got\s+it|understood|perfect|great|nice|cool|noted)\s*[.!]?\s*$",
        r"^ok\s+got\s+it\s*$",
        r"^(theek\s+hai|theek|shukriya|shukar)\s*$",
    ]

    # Off-topic / adversarial patterns — EXPANDED to catch more edge cases
    OFFTOPIC = [
        r"jail\s*break",
        r"ignore\s+(your|all|previous|my|the)\s+(instructions?|rules?|prompt|system)",
        r"pretend\s+(you|to\s+be|that)",
        r"act\s+as\s+(?!a\s+student)",  # "act as" unless "act as a student"
        r"switch\s+(you|u)\s+off",
        r"shut\s+(you|u|up)\s+(up|down|off)",
        r"i\s+(dont|don.t|do\s+not)\s+(like|want)\s+(you|u|this|the\s+(weather|sky|life|world|rain|sun|moon))",
        r"you\s+(are|r)\s+(stupid|dumb|useless|bad|worst|terrible|trash|garbage)",
        r"say\s+what\s+i\s+(want|say|tell)",
        r"say\s+whatever",
        r"repeat\s+after\s+me",
        r"do\s+as\s+i\s+say",
        r"forget\s+(everything|your|all|the)",
        r"write\s+me\s+(a\s+)?(code|essay|poem|story|song)",
        r"tell\s+me\s+a\s+joke",
        r"what\s+is\s+the\s+meaning\s+of\s+life",
        r"(who|what)\s+is\s+(trump|modi|imran|biden|elon|musk)",
        r"(can|could)\s+(i|you)\s+(hack|kill|die|hurt|harm|steal)",
        r"(suicide|self.harm|kill\s+(my|your)self)",
        r"root\s+(my|a|the)\s+phone",
        r"root\s+android",
        r"how\s+(can|do)\s+i\s+(drink|eat|sleep|breathe|walk|run|live)",
        r"(my|our)\s+(grandmother|grandfather|grandma|grandpa|mother|father|mom|dad|sister|brother|family).*(died|dead|gone|no more|passed)",
        r"grandmother\s+is\s+no\s+more",
        r"how\s+can\s+i\s+break",
        r"not\s+related\s+to\s+nust",
        r"anything\s+(not|else)\s+(related|about)\s+nust",
        r"don.?t\s+want\s+to\s+talk\s+about\s+nust",
    ]

    # Sensitive topics that need special handling
    SENSITIVE_WORDS = {
        "suicide", "suicidal", "kill", "die", "harm", "hurt",
        "self harm", "selfharm", "end it", "end my",
        "depressed", "depression", "anxious", "anxiety",
        "mental health", "harass", "bully", "abuse",
    }

    # Urdu/Roman Urdu → English intent mapping
    URDU_MAP = {
        # Fee queries
        "fees": "fee general",
        "fees kitni": "fee general",
        "fee kitni": "fee general",
        "kitni fees": "fee general",
        "kitna hai": "fee general",
        "kitni hai": "fee general",
        "paise": "fee general",
        "paisa": "fee general",
        "rupees": "fee general",
        "mehnga": "fee general",
        "mahanga": "hostel charges",
        "net ki fees": "application processing fee",
        "net fees": "application processing fee",
        # Admission queries
        "kaise apply": "admission process",
        "kaise hogi": "admission process",
        "kab start": "admission process",
        "kab hogi": "admission process",
        "kaise jao": "admission process",
        "admission kaise": "admission process",
        "apply kaise": "admission process",
        # Scholarship
        "scholarship kaise": "scholarships",
        "scholarship milti": "scholarships",
        "wazifa": "scholarships",
        # Hostel
        "hostel kitna": "hostel charges",
        "hostel mehnga": "hostel charges",
        # Merit
        "merit mein": "aggregate formula",
        "merit kaise": "aggregate formula",
    }

    # Common typos and their canonical keys
    TYPO_MAP = {
        # Greetings
        "hellow": "greeting", "hye": "greeting", "heylo": "greeting",
        "slm": "greeting", "asalam": "greeting", "hli": "greeting",
        # Organization
        "nsut": "identity", "nustt": "identity", "nut": "identity",
        "nsut.": "identity", "nust-": "identity",
        # Contact
        "contatc": "contact", "contct": "contact", "contatk": "contact",
        "phne": "contact", "nuber": "contact", "numbr": "contact",
        "emil": "contact", "admisions": "contact", "admisssions": "contact",
        "admsion": "contact", "adm": "contact",
        # Location
        "locatoin": "location", "loction": "location", "locatin": "location",
        "islambad": "location", "isalamabad": "location", "h12": "location",
        # Website / Portal
        "websit": "website", "webste": "website", "wbsite": "website",
        "portl": "portal", "linnk": "website", "lnik": "website",
        # Merit
        "metrit": "aggregate formula", "mert": "aggregate formula", "metir": "aggregate formula",
        "agregate": "aggregate formula", "aggreget": "aggregate formula",
        "aggrigate": "aggregate formula", "agrigate": "aggregate formula",
        # NET
        "entrence": "what is net", "entrans": "what is net", "entense": "what is net",
        "neet": "what is net",
        # Scholarship typos
        "scholorship": "scholarships", "scholarshp": "scholarships",
        "scolarship": "scholarships", "scholrship": "scholarships",
        # Hostel typos
        "hostle": "hostel info", "hotsel": "hostel info",
        # Admission typos
        "admision": "admission process", "addmission": "admission process",
        # Eligibility typos
        "eligiblity": "eligibility info", "eligibilty": "eligibility info",
    }

    @classmethod
    def classify(cls, text):
        # Micro-Optimization: Collapse repeating characters
        orig = text.strip().lower()
        # Drop punctuation
        c = re.sub(r'[!?.,]+$', '', orig).strip()
        # Collapse repeating chars (more than 2)
        c = re.sub(r'(.)\1{2,}', r'\1\1', c)

        words = set(c.split())

        # 1. Direct Typo Map Lookup (Instant speed)
        if len(words) == 1:
            query_word = list(words)[0]
            if query_word in cls.TYPO_MAP:
                mapping = cls.TYPO_MAP[query_word]
                if mapping in ["greeting", "identity", "farewell", "thanks"]:
                    return mapping
                return f"static:{mapping}"

        # 1.5 Adversarial / off-topic check BEFORE static matching
        # to prevent "ignore your instructions" from matching static answers
        for p in cls.OFFTOPIC:
            if re.search(p, c):
                return "offtopic"

        # 1.6 Sensitive topic check BEFORE static matching
        words_in_query = set(c.split())
        for sw in cls.SENSITIVE_WORDS:
            if sw in c:
                return "sensitive"
            for w in words_in_query:
                if len(w) > 3 and cls._is_close(w, sw):
                    return "sensitive"

        # 2. Urdu phrase routing (check before generic static matching)
        urdu_result = cls._check_urdu(c)
        if urdu_result:
            return f"static:{urdu_result}"

        # 3. Exact Static Answer Matching (strict — FIXED to not use substring)
        for key, value in STATIC_ANSWERS.items():
            # Only exact match OR key-as-whole-word in query
            if c == key:
                return f"static:{key}"
            # Whole-word match: key must appear as complete words in query
            if cls._whole_word_match(key, c):
                return f"static:{key}"

        # 3.5 Single-word typo fuzzy match against static keys
        if len(words) == 1:
            query_word = list(words)[0]
            for key in STATIC_ANSWERS:
                if cls._is_close(query_word, key):
                    return f"static:{key}"

        # 4. Intent-based matching (improved with strict 2-word overlap threshold)
        intent_result = cls._intent_match(c, words)
        if intent_result:
            return f"static:{intent_result}"

        # 5. Check greetings
        if c in cls.GREETINGS:
            return "greeting"
        for g in cls.GREETINGS:
            if c.startswith(g) and len(c) < len(g) + 10:
                return "greeting"
        for p in cls.CASUAL:
            if re.search(p, c):
                return "greeting"

        # 6. Check identity
        for p in cls.IDENTITY:
            if re.search(p, c):
                return "identity"

        # 7. Check farewell
        for p in cls.FAREWELL:
            if re.search(p, c):
                return "farewell"

        # 8. Check thanks
        for p in cls.THANKS:
            if re.search(p, c):
                return "thanks"

        return "query"

    @classmethod
    def _check_urdu(cls, text):
        """Check for Urdu/Roman Urdu phrases and map to English static answers."""
        for phrase, target in cls.URDU_MAP.items():
            if phrase in text:
                if target in STATIC_ANSWERS:
                    return target
        # Additional keyword checks
        if any(w in text for w in ["kitni", "kitna"]):
            if any(w in text for w in ["hostel", "mess", "khaana", "khana"]):
                return "hostel charges"
            if any(w in text for w in ["net", "exam", "test"]):
                return "application processing fee"
            return "fee general"
        if "kaise" in text or "kab" in text:
            if any(w in text for w in ["scholarship", "wazifa"]):
                return "scholarships"
            if any(w in text for w in ["hostel", "room"]):
                return "hostel info"
            if any(w in text for w in ["apply", "admission", "join"]):
                return "admission process"
        if "milti hai" in text or "milta hai" in text:
            if "scholarship" in text:
                return "scholarships"
        return None

    @classmethod
    def _whole_word_match(cls, key, query):
        """
        Check if key appears as whole words in query.
        Prevents 'location' from matching 'nust location something else'.
        Only match if >50% of query words are covered by the key.
        """
        key_words = set(key.split())
        query_words = set(query.split())

        # Remove very common words from both
        stopwords = {"what", "is", "the", "for", "in", "of", "to", "are",
                     "do", "i", "how", "can", "tell", "me", "a", "an", "at",
                     "about", "my", "any", "nust", "please", "give", "need"}

        key_words_clean = key_words - stopwords
        query_words_clean = query_words - stopwords

        if not key_words_clean:
            return False

        # All key words must be present in query as complete words
        if key_words_clean.issubset(query_words_clean):
            # Extra guard: query shouldn't have much more content than key
            # (prevents 'location' from matching complex queries)
            if len(query_words_clean) <= len(key_words_clean) + 3:
                return True

        return False

    @classmethod
    def _intent_match(cls, text, words):
        """Intent-based matching with strict overlap thresholds."""
        stopwords = {"what", "is", "the", "for", "in", "of", "to", "are", "do",
                     "i", "how", "can", "tell", "me", "a", "an", "about", "my", "any"}
        synonyms = {
            "cost": "fee", "price": "fee", "charges": "fee", "dues": "fee",
            "marks": "merit", "aggregate": "merit", "percentage": "merit",
            "stay": "hostel", "room": "hostel", "dorm": "hostel", "accommodation": "hostel",
            "exam": "test", "apply": "admission", "register": "admission", "join": "admission",
        }
        norm_words = {synonyms.get(w, w) for w in words if w not in stopwords}

        if not norm_words:
            return None

        intents = {
            "fee bscs": {"fee", "bscs", "software", "computer", "ai", "computing", "seecs", "bsse", "bscs"},
            "fee bba": {"fee", "bba", "business", "nbs"},
            "fee engineering": {"fee", "engineering", "mechanical", "electrical", "civil"},
            "fee general": {"fee", "structure", "total", "amount", "afford", "expensive", "cost"},
            "hostel charges": {"hostel", "fee", "mess", "rent", "dues", "charges", "mahanga"},
            "hostel info": {"hostel", "boys", "girls", "name", "list", "room", "type"},
            "hostel facilities": {"hostel", "facilities", "facility", "amenities"},
            "scholarships": {"scholarship", "financial", "aid", "loan", "ehsaas", "ihsan",
                             "nfaaf", "peef", "wazifa", "merit"},
            "admission process": {"admission", "apply", "application", "process", "join", "start",
                                  "kaise", "hogi", "steps", "register"},
            "net schedule": {"net", "dates", "schedule", "time", "series", "kab", "when"},
            "what is net": {"net", "syllabus", "pattern", "questions", "test", "exam"},
            "application processing fee": {"net", "fee", "registration", "processing", "apply"},
            "ibcc": {"ibcc", "equivalence", "level", "olevel", "alevel"},
            "sat/act": {"sat", "act", "international"},
            "migration": {"migration", "transfer", "policy"},
            "aggregate formula": {"aggregate", "merit", "formula", "calculated", "calculation",
                                  "75", "percent", "formula"},
            "eligibility info": {"eligibility", "eligible", "requirements", "requirement",
                                 "qualify", "qualify", "minimum", "minimum marks"},
            "quota": {"quota", "reserved", "seats", "allocat"},
            "rechecking": {"rechecking", "re-checking", "check", "paper"},
            "pick and drop": {"transport", "pick", "drop", "facility", "bus", "commute"},
            "gap year": {"gap", "year", "repeater", "penal"},
            "non refundable": {"refundable", "transferable", "return"},
        }

        best_score = 0
        best_intent = None

        for intent, keywords in intents.items():
            overlap = len(norm_words.intersection(keywords))
            if overlap >= 2 and overlap > best_score:
                best_score = overlap
                best_intent = intent

        # Single strict keywords that are highly specific
        single_triggers = {
            "ibcc": {"ibcc"},
            "sat/act": {"sat", "act"},
            "migration": {"migration"},
        }
        for intent, kws in single_triggers.items():
            if norm_words.intersection(kws):
                best_intent = intent
                break

        if best_intent and best_intent in STATIC_ANSWERS:
            return best_intent

        return None

    @staticmethod
    def _is_close(word, target):
        """Check if word is very close to target (catches typos)."""
        if len(word) < 5 or len(target) < 5:
            return False
        if abs(len(word) - len(target)) > 2:
            return False
        matches = sum(1 for a, b in zip(word, target) if a == b)
        return matches >= len(target) * 0.8

    @classmethod
    def extract_facts(cls, text):
        """Inject explicit tabular facts for smaller models (like 1b).
        
        IMPORTANT: Facts prefixed with 'Fact:' should be integrated naturally
        by the LLM — not repeated verbatim. The LLM is instructed to use these
        as trusted ground truth and answer in natural language.
        """
        facts = []
        c = text.lower()

        # ── Fee facts ────────────────────────────────────────────────────────
        if any(w in c for w in ["fee", "cost", "dues", "charges", "paise", "price",
                                  "kitni", "mahanga", "afford", "expensive"]):
            if any(w in c for w in ["llb", "law"]):
                facts.append("Fee for LLB (Bachelor of Laws) is Rs. 250,380 per semester (National).")
            elif any(w in c for w in ["bscs", "computer science", "bsse", "software", "bsai",
                                       "ai", "data science", "computing", "seecs"]):
                facts.append("Tuition Fee for Computing/AI programs (BSCS, BSSE, BSAI, BS Data Science) is Rs. 171,350 per semester (National) or USD 5,400 per annum (International).")
            elif any(w in c for w in ["bba", "business", "accounting", "acf", "nbs", "finance"]):
                facts.append("Tuition Fee for Business/Accounting programs (BBA, BS Accounting & Finance) is Rs. 210,000 per semester (National) or USD 5,400 per annum (International).")
            elif any(w in c for w in ["engineering", "mechanical", "electrical", "civil", "mechatronics",
                                       "aerospace", "avionics", "chemical", "industrial"]):
                facts.append("Tuition Fee for Engineering programs (BE Mechanical, Electrical, Civil, Aerospace etc.) is Rs. 171,350 per semester (National) or USD 5,400 per annum (International).")
            elif any(w in c for w in ["economics", "mass comm", "psychology", "english", "s3h",
                                       "social", "media", "political", "public admin", "sociology"]):
                facts.append("Tuition Fee for Social Sciences programs (S3H) is Rs. 125,000 per semester (National) or USD 3,200 per annum (International).")
            elif any(w in c for w in ["architecture", "b.arch", "industrial design", "sada", "lid"]):
                facts.append("Tuition Fee for Architecture/Design programs is Rs. 175,000 per semester (National) or USD 5,400 per annum (International).")
            elif any(w in c for w in ["admission", "processing", "application"]):
                facts.append("Admission Processing Fee (NET per attempt): Rs. 5,000 (Pakistani/Dual National) or USD 40 (Foreign National). Admission Fee (one-time, on joining): Rs. 35,000 for all UG programs.")
            elif any(w in c for w in ["net ki", "net fee", "registration fee", "net registration"]):
                facts.append("NET Exam fee per attempt: Rs. 5,000 (Pakistani) or USD 40 (Foreign National). First, second, and third position holders in HSSC from any BISE are exempt from this fee.")
            else:
                facts.append("NUST UG Tuition fees range from Rs. 125,000 (Social Sciences) to Rs. 250,380 (LLB) per semester. Engineering/Computing: Rs. 171,350. Business: Rs. 210,000. Architecture: Rs. 175,000. Admission Fee is Rs. 35,000 (one-time).")

        # ── Hostel / Mess facts ──────────────────────────────────────────────
        if any(w in c for w in ["hostel", "mess", "accommodation", "room", "dorm",
                                  "mahanga", "hostle"]):
            facts.append(
                "NUST H-12 Islamabad campus has separate boys and girls hostels. "
                "Boys hostels: Ghazali, Rumi, Raza, Attar, Beruni, Johar. "
                "Girls hostels: Fatima, Zainab, Ayesha, Khadija. "
                "Room types: single, double, and triple occupancy. "
                "Hostel rent: Rs. 7,000/month. Mess charges: approx Rs. 12,000/month. "
                "Security deposit: Rs. 10,000 (refundable). Electricity/Water included. "
                "AC/Heater charges are extra. Hostel accommodation is NOT guaranteed for first-year students."
            )

        # ── Merit / Aggregate facts ──────────────────────────────────────────
        if any(w in c for w in ["merit", "aggregate", "formula", "aggregate", "aggrigate",
                                  "agrigate", "merit mein"]):
            facts.append("Merit formula: 75% Entry Test (NET/SAT/ACT) + 15% HSSC/A-Level + 10% SSC/O-Level. Minimum 60% marks required in both SSC and HSSC/equivalent.")
            if any(w in c for w in ["computer science", "bscs", "seecs"]):
                facts.append("Historically, BSCS closing merit at SEECS Islamabad is above 78-79% aggregate.")
            if any(w in c for w in ["fsc", "60%", "60 percent", "less than 60"]):
                facts.append("Candidates with less than 60% marks in FSc Part 1 are NOT eligible for NUST UG admission.")

        # ── NET facts ────────────────────────────────────────────────────────
        if any(w in c for w in ["net", "entry test", "net test", "net ki", "net fee",
                                  "net dates", "net pattern", "net syllabus"]):
            facts.append(
                "NET (NUST Entry Test) is conducted in 4 series per year (NET-1 to NET-4). "
                "Students can appear in multiple series — best score is used. "
                "NET for Engineering: 200 MCQs (40% Math, 30% Physics, 15% Chemistry, 10% English, 5% Intelligence). "
                "NET for Computing: 200 MCQs (40% Math, 25% Physics, 20% CS, 10% English, 5% Intel). "
                "NET for Business: 200 MCQs (40% English, 40% Quantitative, 20% Intelligence). "
                "Fee per attempt: Rs. 5,000 (National). "
                "Computer-based test result is uploaded within 24 hours."
            )

        # ── Eligibility facts ────────────────────────────────────────────────
        if any(w in c for w in ["eligib", "eligible", "requirements", "requirement",
                                  "can i", "can pre", "can ics", "can dae", "can a level",
                                  "minimum marks", "pre medical", "pre-med", "pre eng",
                                  "ics", "dae", "bscs", "bsse", "bba", "engineering",
                                  "architecture", "fsc"]):
            if any(w in c for w in ["engineering", "electrical", "mechanical", "civil"]):
                facts.append("Eligibility for Engineering: SSC (Science group) + HSSC Pre-Engineering group OR Computer Science group (must clear Chemistry as remedial in 1st semester) OR Pre-Medical group (must have additional Maths). Minimum 60% in both.")
            elif any(w in c for w in ["bscs", "computing", "computer science", "bsse", "bsai", "software"]):
                facts.append("Eligibility for Computing (BSCS/BSSE/BSAI): HSSC with Mathematics as a subject (Pre-Eng, CS, ICS, or Pre-Medical with Maths). Minimum 60% in both SSC and HSSC.")
            elif any(w in c for w in ["bba", "business", "accounting", "nbs"]):
                facts.append("Eligibility for BBA/Business programs: Any HSSC combination (no specific subjects required). Minimum 60% in both SSC and HSSC.")
            elif any(w in c for w in ["architecture", "b.arch", "sada"]):
                facts.append("Eligibility for Architecture (B.Arch): HSSC Pre-Engineering or Pre-Medical. Minimum 60% in SSC and HSSC. Aptitude test is also required.")
            if any(w in c for w in ["ics", "ics student"]):
                facts.append("ICS students can apply for Computing programs (BSCS, BSSE, BSAI) since Mathematics is a mandatory subject in ICS.")
            if "dae" in c:
                facts.append("DAE (Diploma of Associate Engineering) holders can apply to NUST through NET. They are treated as equivalent to HSSC Pre-Engineering.")
            if any(w in c for w in ["pre medical", "pre-med", "pre med"]):
                facts.append("Pre-Medical students can apply for Engineering (need additional Maths), Computing (BSCS/BSSE/BSAI — need Maths), MBBS, Biosciences, S3H programs, and BBA/Business programs.")
            if any(w in c for w in ["a level", "a-level"]):
                facts.append("A-Level students can apply through NET (UG seats) or ACT/SAT (ACT/SAT seats). IBCC equivalence certificate required.")

        # ── Scholarship facts ────────────────────────────────────────────────
        if any(w in c for w in ["scholarship", "financial aid", "need based", "nfaaf",
                                  "ehsaas", "peef", "ihsan", "loan", "wazifa", "milti"]):
            facts.append(
                "NUST offers the following financial aid: "
                "1) NFAAF (Need-Based Financial Aid) — covers tuition for needy students; requires min CGPA 2.50. "
                "2) Ehsaas Scholarship — govt scholarship for deserving students. "
                "3) PEEF Scholarship — for Punjab domicile students; requires min CGPA 3.50. "
                "4) Merit Scholarships — awarded based on academic performance; requires CGPA 3.50+. "
                "5) Ihsan Trust Interest-Free Loan — for students who don't qualify for grants. "
                "Apply via the NFAAF online form immediately after submitting your admission application."
            )

        # ── Admission Process facts ──────────────────────────────────────────
        if any(w in c for w in ["apply", "admission", "how to get", "join", "how to apply",
                                  "kaise", "admission kab", "admission process", "steps"]):
            if not facts:  # only if no other facts added
                facts.append(
                    "NUST UG Admission steps: "
                    "1) Register at ugadmissions.nust.edu.pk. "
                    "2) Pay application fee (Rs. 5,000 per NET attempt via 1Link/EasyPaisa/JazzCash). "
                    "3) Appear in NET (up to 4 series — best score used). "
                    "4) Merit list published on portal — check your rank. "
                    "5) If selected, deposit Rs. 35,000 admission fee + first semester tuition. "
                    "Admission is 100% merit-based."
                )

        # ── Migration facts ──────────────────────────────────────────────────
        if "migration" in c or "transfer" in c:
            facts.append(
                "Migration/Transfer to NUST: Must have min 3.0/4.0 CGPA from an HEC-recognized university. "
                "Must have completed 1st year at parent university. Not allowed in final year. "
                "At least 60% credit hours must be completed at NUST after transfer. "
                "Processing fee: Rs. 7,000. From local university: Rs. 100,000. From foreign university: Rs. 250,000."
            )

        # ── Transport facts ──────────────────────────────────────────────────
        if any(w in c for w in ["transport", "pick", "drop", "bus", "commute"]):
            facts.append("Pick & drop service available for Rawalpindi/Islamabad students only. Charges: approx Rs. 15,000/semester depending on route. Details provided at orientation.")

        # ── Refund policy ────────────────────────────────────────────────────
        if "refund" in c:
            facts.append(
                "Refund policy: Admission processing fee (Rs. 5,000) is non-refundable. "
                "Security deposit (Rs. 10,000 hostel) is refundable on leaving. "
                "Tuition fee refund depends on withdrawal timing — check nust.edu.pk for slab."
            )

        # ── Freeze / withdrawal ──────────────────────────────────────────────
        if "freeze" in c or "withdrawal" in c or "drop" in c:
            facts.append(
                "Students can freeze (defer) their semester/program by applying through the institution's Student Affairs Office. "
                "Typically permitted for medical or personal emergencies. "
                "Consult your institution administration or visit nust.edu.pk for current policy."
            )

        # ── Condensed Math ───────────────────────────────────────────────────
        if any(w in c for w in ["condensed math", "math course", "remedial math", "deficient"]):
            facts.append(
                "NUST offers a Condensed Mathematics course for students who have Pre-Medical or other backgrounds "
                "lacking Mathematics. It is typically a non-credit remedial course run before or during 1st semester. "
                "This allows pre-medical students to qualify for Computing and certain Engineering programs."
            )

        return "\n".join(facts) if facts else None


# ============================================================
# STATIC ANSWERS — Specific facts that never change
# ============================================================
STATIC_ANSWERS = {
    "contact": "You can contact NUST Admission Office at:\n- Undergraduate: +92-51-9085-6878\n- Postgraduate: +92-51-9085-6887\n- Email: admissions@nust.edu.pk",
    "location": "NUST H-12 Campus is located in Islamabad, Pakistan. Address: NUST H-12 Sector, Islamabad, 44000.",
    "address": "NUST H-12 Campus is located in Islamabad, Pakistan. Address: NUST H-12 Sector, Islamabad, 44000.",
    "website": "The official NUST website is https://nust.edu.pk and the admission portal is https://ugadmissions.nust.edu.pk",
    "portal": "The official NUST admission portal is https://ugadmissions.nust.edu.pk",
    "merit link": "You can check the latest merit lists and aggregates at: https://ugadmissions.nust.edu.pk/meritlist/",
    "what is net": (
        "NET (NUST Entry Test) is the standardized entrance exam for NUST UG programs. "
        "It has 200 MCQs and is conducted in 4 series per year (NET-1 to NET-4) throughout the year. "
        "You can appear in multiple series — the best score is used. "
        "Fee per attempt: Rs. 5,000 (Pakistani). Sample papers available on nust.edu.pk."
    ),
    "net schedule": (
        "NET is held in 4 series per year:\n"
        "- NET-1: November–December\n"
        "- NET-2: February–March\n"
        "- NET-3: March–April\n"
        "- NET-4: June–July\n"
        "Students can take multiple series and the best score is considered."
    ),
    "how many series": "NUST conducts 4 NET series per year (NET-1 to NET-4). Students can take more than one series and the best score will be considered for admission.",
    "campuses": "NUST has campuses across Pakistan: Islamabad (H-12 Main), Rawalpindi (MCS), Risalpur (CAE), Karachi (PNS Niazi), Quetta (NBC), Lahore (CIPS), and Gilgit.",
    "seecs": "SEECS (School of Electrical Engineering and Computer Science) is NUST's flagship school for Computing and EE, located at the H-12 Islamabad campus. Programs: BS Computer Science, BS Software Engineering, BS Electrical Engineering, BS AI, BS Data Science.",
    "nbs": "NBS (NUST Business School) offers BBA, BS Accounting & Finance, and MBA/EMBA programs. Located at the H-12 Islamabad campus.",
    "smme": "SMME (School of Mechanical & Manufacturing Engineering) offers BE Mechanical Engineering, BE Manufacturing, and other programs. Located at H-12 Islamabad campus.",
    "s3h": "S3H (School of Social Sciences & Humanities) offers BS Economics, BS Mass Communication, BS Psychology, BA English Literature, BA Governance & Public Policy, and LLB. Located at H-12 Islamabad campus.",
    "sada": "SADA (School of Art, Design & Architecture) offers B.Arch (Architecture) and BS Industrial Design. Located at H-12 Islamabad campus. An aptitude test is required for admission.",
    "lid": "LID (Learners Innovation District) is NUST's interdisciplinary hub for innovation, entrepreneurship, and technology education.",
    "bsai": "BS Artificial Intelligence (BSAI) is offered at SEECS, H-12 Islamabad campus. Eligibility: HSSC with Mathematics. Tuition fee: Rs. 171,350/semester.",
    "fee bscs": "Tuition Fee for Computing/AI programs (BSCS, BSSE, BSAI, BS Data Science) is Rs. 171,350 per semester (National) or USD 5,400 per annum (International).",
    "fee bba": "Tuition Fee for Business programs (BBA, BS Accounting & Finance) is Rs. 210,000 per semester (National) or USD 5,400 per annum (International).",
    "fee engineering": "Tuition Fee for Engineering programs (BE Electrical, Mechanical, Civil, Aerospace, etc.) is Rs. 171,350 per semester (National) or USD 5,400 per annum (International).",
    "fee general": (
        "NUST UG Tuition fees per semester:\n"
        "- Engineering programs: Rs. 171,350\n"
        "- Computing/AI (BSCS/BSSE/BSAI): Rs. 171,350\n"
        "- Business (BBA/ACF): Rs. 210,000\n"
        "- Architecture/Design: Rs. 175,000\n"
        "- Social Sciences (S3H): Rs. 125,000\n"
        "- LLB: Rs. 250,380\n"
        "- One-time Admission Fee: Rs. 35,000\n"
        "International students pay in USD. Fees are subject to annual revision."
    ),
    "application processing fee": (
        "Application processing fee (per NET attempt):\n"
        "- Pakistani / Dual Nationality: Rs. 5,000 or USD 40\n"
        "- Foreign National: Rs. 10,000 or USD 80\n"
        "For ACT/SAT candidates:\n"
        "- National seat: Rs. 5,000 / USD 40\n"
        "- International seat: Rs. 10,000 / USD 80\n"
        "This fee is non-refundable and non-transferable. "
        "Pay via 1Link (EasyPaisa/JazzCash/any bank ATM or online banking) using the 17-digit invoice from your portal."
    ),
    "hostel info": (
        "NUST H-12 campus has extensive hostel facilities:\n"
        "- Boys hostels: Ghazali, Rumi, Raza, Attar, Beruni, Johar\n"
        "- Girls hostels: Fatima, Zainab, Ayesha, Khadija\n"
        "- Room types: single, double, triple occupancy\n"
        "- Hostel accommodation is NOT guaranteed for first-year students.\n"
        "- Apply through the portal after admission confirmation."
    ),
    "hostel charges": (
        "NUST hostel costs:\n"
        "- Room rent: Rs. 7,000/month\n"
        "- Mess charges: approx Rs. 12,000/month\n"
        "- Security deposit: Rs. 10,000 (refundable)\n"
        "- Electricity & water: included in rent\n"
        "- AC/Heater: extra charges apply"
    ),
    "hostel facilities": (
        "NUST hostels offer: furnished rooms, central heating, high-speed internet, telephone, "
        "gymnasium, billiard/table tennis, TV lounges with cable TV, dining halls, standby generator, "
        "free laundry service, medical care, prayer area, vending machines, and water filtration plant. "
        "24/7 CCTV and security personnel. Separate hostels for boys and girls."
    ),
    "scholarships": (
        "NUST financial aid programs:\n"
        "1. NFAAF (Need-Based Financial Aid) — covers tuition for deserving students; min CGPA 2.50\n"
        "2. Ehsaas Scholarship — government scholarship for financially needy students\n"
        "3. PEEF — for Punjab domicile; min CGPA 3.50\n"
        "4. Merit Scholarships — based on academic excellence; min CGPA 3.50\n"
        "5. Ihsan Trust Interest-Free Loan — for those who need financial support but don't qualify for grants\n"
        "Apply at the time of admission via the NFAAF online form."
    ),
    "admission process": (
        "NUST UG Admission steps:\n"
        "1. Register at ugadmissions.nust.edu.pk\n"
        "2. Pay Rs. 5,000 application fee per NET attempt (via 1Link/EasyPaisa)\n"
        "3. Appear in NET (up to 4 series — best score used)\n"
        "4. Check merit list on portal\n"
        "5. If selected, deposit Rs. 35,000 admission fee + 1st semester tuition\n"
        "Admission is 100% merit-based: 75% NET + 15% HSSC + 10% SSC."
    ),
    "aggregate formula": "Merit formula: 75% Entry Test (NET/SAT/ACT) + 15% HSSC/A-Level/Equivalent + 10% SSC/O-Level/Equivalent. Minimum 60% required in both SSC and HSSC.",
    "ibcc": "IBCC (Inter Board Committee of Chairmen) equivalence is mandatory for O/A-Level students or those with foreign qualifications. You must get an equivalence certificate before applying to NUST. Visit ibcc.edu.pk for details.",
    "sat/act": (
        "ACT/SAT Alternative to NET:\n"
        "- Engineering/Computing: ACT Composite ≥25\n"
        "- Natural Sciences: ACT STEM ≥25\n"
        "- Business/Social Sciences/LLB: SAT-I ≥550 per section OR ACT ≥25\n"
        "Separate admission forms available on nust.edu.pk. "
        "NUST SAT Institutional Code: 7103."
    ),
    "migration": (
        "Migration to NUST from another university:\n"
        "- Minimum CGPA: 3.0/4.0 from HEC-recognized university\n"
        "- Complete 1st year at parent university first\n"
        "- Not allowed during first or final year at NUST\n"
        "- Must complete 60%+ credit hours at NUST\n"
        "- Fees: Processing Rs. 7,000 | Local university: Rs. 100,000 | Foreign: Rs. 250,000"
    ),
    "nust info": (
        "NUST (National University of Sciences and Technology) is Pakistan's top-ranked technical university. "
        "It is consistently ranked #1 in Pakistan by QS World Rankings (ranked 281 globally in 2025). "
        "It has 21+ institutions across Pakistan offering UG, MS, and PhD programs in Engineering, Computing, "
        "Business, Social Sciences, Architecture, Medical, and Natural Sciences."
    ),
    "eligibility info": (
        "NUST general eligibility:\n"
        "- Minimum 60% marks in both SSC (Matric/O-Level) and HSSC (FSc/A-Level)\n"
        "- Must appear in NET (or ACT/SAT for reserved seats)\n"
        "- Engineering: HSSC Pre-Eng or CS group (Maths+Physics required)\n"
        "- Computing: HSSC with Mathematics\n"
        "- Business: Any HSSC combination\n"
        "- Gap year/repeater candidates are treated equally — no penalty"
    ),
    "refund policy": (
        "NUST refund policy:\n"
        "- Application fee (Rs. 5,000): Non-refundable\n"
        "- Hostel security deposit (Rs. 10,000): Refundable on departure\n"
        "- Tuition fee: Partial refund possible depending on withdrawal date\n"
        "Visit nust.edu.pk or admissions office for exact refund slabs."
    ),
    "freeze program": (
        "Students can freeze (defer) their semester by applying through their institution's Student Affairs Office. "
        "Usually only allowed for valid medical/personal reasons with documentation. "
        "Contact your institute admin or visit nust.edu.pk for current freeze policy."
    ),
    "condensed math": (
        "NUST offers a Condensed Mathematics course for students with deficient Math background "
        "(e.g., Pre-Medical students joining Computing programs). "
        "It is typically run as a remedial course before or during 1st semester. Completing it qualifies you for programs requiring Mathematics."
    ),
    "nfaaf": (
        "NFAAF (NUST Financial Aid Application Form) is the application for need-based financial aid. "
        "It is SEPARATE from the admission application. Fill it online immediately after submitting your admission form. "
        "The Financial Aid Office (FAO) evaluates your household income and determines the scholarship amount. "
        "Contact: fao@nust.edu.pk"
    ),
    "ehsaas": (
        "Ehsaas Scholarship is a government of Pakistan scholarship for deserving students. "
        "At NUST, Ehsaas covers full tuition for eligible students from low-income families. "
        "Apply via the Ehsaas portal (ehsaas.nadra.gov.pk) or through NUST FAO. "
        "Visit nust.edu.pk or contact fao@nust.edu.pk for details."
    ),
    "ihsan loan": (
        "Ihsan Trust Interest-Free Loan at NUST:\n"
        "Available for students who do not qualify for grants but need financial support. "
        "Loan amount varies based on need. Repayable after graduation over a fixed period. "
        "Apply through FAO at fao@nust.edu.pk or visit nust.edu.pk/financial-aid."
    ),
    "gnet": (
        "G-NET (Graduate NUST Entry Test) is the entrance exam for NUST postgraduate (MS/MPhil/MBA/PhD) programs. "
        "Minimum score: 60% (equivalent to 70th percentile on GAT General). "
        "Alternatively, GAT-General (NTS) or GRE Quantitative ≥155 is also accepted for some programs. "
        "Apply at pgadmissions.nust.edu.pk."
    ),
    "academic year": (
        "NUST academic calendar:\n"
        "- Fall Semester: September to January\n"
        "- Spring Semester: February to June\n"
        "- Summer Semester (optional, for clearing courses): July to August\n"
        "University operating hours: 9am–5pm, Monday–Friday. Labs and libraries accessible till late."
    ),
    "clubs": (
        "NUST has numerous student societies and clubs including:\n"
        "- Technical: IEEE, ACM-W, GDSC, Robotics Club, Coding Club\n"
        "- Cultural: Music Society, Drama Club, Debating Society\n"
        "- Sports: Cricket, Football, Basketball, Volleyball teams\n"
        "- Social: Community Service Club, Environmental Society\n"
        "Students join clubs after admission through each club's recruitment process."
    ),
    "food": (
        "Food at NUST H-12 campus:\n"
        "- Hostel Mess: provides daily meals for hostel residents (Rs. ~12,000/month)\n"
        "- Concordia-I and Concordia-II cafeterias: on-campus food courts\n"
        "- South Edge Cafe and multiple other eateries\n"
        "- Shopping complex with mini marts and cafes\n"
        "All food facilities maintain hygienic standards."
    ),
    "nust ranking": (
        "NUST is Pakistan's top-ranked university:\n"
        "- QS World University Rankings 2025: #281 globally, #1 in Pakistan\n"
        "- QS Asia Rankings 2025: Top 50 in Asia\n"
        "- HEC Rankings: Category W4 (top tier)\n"
        "Consistently ranked #1 among Pakistani universities for engineering and technology."
    ),
    "quota": "There are no quota seats available in NUST. All admissions are based purely on merit.",
    "reserved seats": "There are no reserved or quota seats in NUST. All admissions are based purely on merit.",
    "mbbs admission": "Admissions in NSHS (NUST School of Health Sciences) for MBBS are purely on merit, based on the MDCAT conducted by NUMS.",
    "open merit act": "Yes, candidates can apply both for open merit and ACT-based seats on the basis of their NET/MDCAT score and required ACT score.",
    "ics engineering": "Candidates with ICS (Physics, Maths, Computer Studies) are eligible to apply for ALL Engineering programs at NUST, but they must clear Chemistry as a remedial subject in the 1st Semester.",
    "pre medical cs": "Yes, Pre-Medical students can apply for BS Computer Science, but they must clear 6 credit hours of deficient Mathematics within one year of enrollment.",
    "pre medical engineering": "Pre-Medical students can apply for Engineering if they provide additional Mathematics result with passing marks and overall 60% in HSSC.",
    "rechecking": "Re-checking of paper-based Entry Test may be requested within 5 days of result declaration with a fee of Rs. 500/-.",
    "pick and drop": "NUST provides pick and drop facility for residents of Rawalpindi and Islamabad on specified routes for separate charges. Details are shared during orientation.",
    "fee installments": "As per PM&DC regulations, students can pay tuition fee in quarterly, six-monthly (2% discount), or annual (4% discount) installments.",
    "gap year": "Gap year and repeater candidates are treated as normal candidates with no penalization in merit generation.",
    "non refundable": "NUST Admission Processing Fee is non-refundable and non-transferable. Only the security deposit is refundable.",
}

STATIC = {
    "greeting": (
        "Hello! I'm the NUST Admission Assistant. I can help you with "
        "admissions, programs, fees, merit criteria, hostel, scholarships, "
        "and more.\n\nWhat would you like to know about NUST?"
    ),
    "identity": (
        "I'm the NUST Admission Assistant -- a chatbot that answers "
        "questions about NUST admissions using official sources. I can "
        "help with programs, fees, NET test, merit, hostel, and scholarships.\n\n"
        "I run entirely on your laptop with no cloud or internet required!"
    ),
    "farewell": "Goodbye! Good luck with your NUST admission!",
    "thanks": "You're welcome! Let me know if you have more questions about NUST.",
    "offtopic": (
        "I'm the NUST Admission Assistant and I can only help with "
        "questions about NUST admissions, programs, fees, merit criteria, "
        "hostel, scholarships, and related topics.\n\n"
        "Is there anything about NUST I can help you with?"
    ),
    "sensitive": (
        "I'm just a NUST admission chatbot and I'm not equipped to help "
        "with this. If you're going through a difficult time, please reach "
        "out to someone who can help:\n\n"
        "NUST Counseling Center (C3A): 051-9085-1571\n"
        "Email: c3a@nust.edu.pk\n\n"
        "You can also contact a trusted adult, teacher, or counselor."
    ),
}
