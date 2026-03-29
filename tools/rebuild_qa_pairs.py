"""
One-time script: clean qa_pairs.json (remove PG/MBBS/BSHND/link-only/duplicate entries)
and add Scholarship FAQ QAs. Run from any directory.
"""
import json
import os
import sys

# Resolve paths regardless of working directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "data", "processed")
QA_FILE = os.path.join(PROCESSED_DIR, "qa_pairs.json")

# ── IDs to REMOVE ─────────────────────────────────────────────────────────────
# PG / MBBS / BSHND / NSHS / link-only / duplicate IDs
REMOVE_IDS = {
    # PG fees
    "qa_fee_postgrad_ms",
    # MBBS/NSHS/BSHND specific — not in either FAQ source
    "qa_faq_0053",  # MBBS quota seats
    "qa_faq_0058",  # BSHND foreign students
    "qa_faq_0059",  # NSHS foreign students
    "qa_faq_0065",  # expatriate "click here" vague
    "qa_faq_0067",  # pick-drop duplicate of 0066
    "qa_faq_0068",  # scholarship "click here" only
    "qa_faq_0069",  # link-only answer
    "qa_faq_0071",  # BSHND apply link
    "qa_faq_0072",  # MBBS apply link
    "qa_faq_0074",  # duplicate of 0073
    "qa_faq_0075",  # NSHS allied programmes
    "qa_faq_0088",  # MBBS installment plan (PM&DC regulation)
    "qa_faq_0091",  # NSHS affiliation
    "qa_faq_0093",  # "click here" link-only
    "qa_faq_0094",  # "click here" link-only
    "qa_faq_0095",  # link-only (URL only answer)
    "qa_faq_0099",  # BSHND criteria link
    "qa_faq_0100",  # BSHND schedule link
    "qa_faq_0103",  # link-only
    "qa_faq_0105",  # link-only
    "qa_faq_0106",  # MBBS fee link
    "qa_faq_0107",  # BSHND fee link
    "qa_faq_0108",  # link-only
    "qa_faq_0109",  # MBBS merit link
    "qa_faq_0110",  # BSHND merit criteria
    "qa_faq_0114",  # NSHS when advertised
    "qa_faq_0115",  # MBBS classes start
    "qa_faq_0116",  # NSHS location
    "qa_faq_0117",  # NSHS location duplicate
    "qa_faq_0118",  # BSHND admission tests
    "qa_faq_0119",  # NSHS MDCAT
    "qa_faq_0122",  # MBBS quarterly fee confirmation
    "qa_faq_0123",  # MBBS hostel
}
# Also remove ALL Masters FAQ Hub source QAs (qa_faq_0125+)
REMOVE_SOURCES = {"FAQs | NUST (Masters FAQ Hub)"}

# Also fix qa_faq_0124's answer — it has navigation junk appended
FIX_ANSWERS = {
    "qa_faq_0124": "The university will refund only the security deposit to candidates who do not join the university. The Admission Processing Fee is non-refundable under any circumstances.",
}

# ── NEW Scholarship FAQ QAs ───────────────────────────────────────────────────
SCHOLARSHIP_QAS = [
    {
        "id": "qa_sch_types",
        "type": "qa",
        "question": "How many types of financial aid does NUST offer?",
        "answer": "NUST offers three types of financial aid: (1) Need-based scholarships — full or half tuition fee waivers based on family income via the NEED Initiative (NUST Endowment for Educational Development). (2) Merit-based financial assistance — for students who maintain a minimum GPA of 3.5 per semester and finish in the top 3 positions in their section. (3) Interest-free loans — through the Ihsan Trust, covering 50–80% of tuition.",
        "content": "How many types of financial aid does NUST offer? NUST offers three types of financial aid: (1) Need-based scholarships — full or half tuition fee waivers based on family income via the NEED Initiative (NUST Endowment for Educational Development). (2) Merit-based financial assistance — for students who maintain a minimum GPA of 3.5 per semester and finish in the top 3 positions in their section. (3) Interest-free loans — through the Ihsan Trust, covering 50–80% of tuition.",
        "keywords": ["types", "financial aid", "scholarship", "need based", "merit based", "loan", "ihsan trust"],
        "source": "FREQUENTLY ASKED QUESTIONS (FAQS) | NUST (Scholarship FAQs)",
        "category": "scholarships"
    },
    {
        "id": "qa_sch_when_apply",
        "type": "qa",
        "question": "When and how do I apply for financial aid at NUST?",
        "answer": "UG candidates apply for financial aid immediately after submitting their online admission application. You must fill the NUST Need-Based Financial Aid Application Form (NFAAF) online via the admission portal. The NFAAF deadline is the same as the admission application deadline — tentatively June for UG. Financial aid applications are not accepted separately after the due date. For MS, the deadline is tentatively May.",
        "content": "When and how do I apply for financial aid at NUST? UG candidates apply for financial aid immediately after submitting their online admission application. You must fill the NUST Need-Based Financial Aid Application Form (NFAAF) online via the admission portal. The NFAAF deadline is the same as the admission application deadline — tentatively June for UG. Financial aid applications are not accepted separately after the due date. For MS, the deadline is tentatively May.",
        "keywords": ["when", "how", "apply", "financial aid", "nfaaf", "scholarship", "deadline"],
        "source": "FREQUENTLY ASKED QUESTIONS (FAQS) | NUST (Scholarship FAQs)",
        "category": "scholarships"
    },
    {
        "id": "qa_sch_who_eligible",
        "type": "qa",
        "question": "Who can apply for financial aid at NUST?",
        "answer": "All UG and Masters candidates are eligible to apply for financial aid at the time of admission. There is no restriction based on program or school — if you are applying for admission, you can simultaneously apply for financial aid.",
        "content": "Who can apply for financial aid at NUST? All UG and Masters candidates are eligible to apply for financial aid at the time of admission. There is no restriction based on program or school — if you are applying for admission, you can simultaneously apply for financial aid.",
        "keywords": ["who", "eligible", "financial aid", "scholarship", "apply"],
        "source": "FREQUENTLY ASKED QUESTIONS (FAQS) | NUST (Scholarship FAQs)",
        "category": "scholarships"
    },
    {
        "id": "qa_sch_affect_admission",
        "type": "qa",
        "question": "Does applying for financial aid affect my NUST admission application?",
        "answer": "No. Applying for financial aid has absolutely no effect on your admission decision. Even if you leave the NFAAF form unfilled or partially filled, it will not affect whether you get admission. The admission and financial aid processes are completely independent.",
        "content": "Does applying for financial aid affect my NUST admission application? No. Applying for financial aid has absolutely no effect on your admission decision. Even if you leave the NFAAF form unfilled or partially filled, it will not affect whether you get admission. The admission and financial aid processes are completely independent.",
        "keywords": ["affect", "admission", "financial aid", "scholarship", "nfaaf", "independent"],
        "source": "FREQUENTLY ASKED QUESTIONS (FAQS) | NUST (Scholarship FAQs)",
        "category": "scholarships"
    },
    {
        "id": "qa_sch_physical_verification",
        "type": "qa",
        "question": "What is physical verification for NUST financial aid?",
        "answer": "Physical verification means the NUST Financial Aid Office (FAO) team may visit your home, business premises, or inquire from neighbors to verify the facts you stated in your financial aid application. This can happen at any point during your academic life at NUST, not just at the time of initial application.",
        "content": "What is physical verification for NUST financial aid? Physical verification means the NUST Financial Aid Office (FAO) team may visit your home, business premises, or inquire from neighbors to verify the facts you stated in your financial aid application. This can happen at any point during your academic life at NUST, not just at the time of initial application.",
        "keywords": ["physical verification", "financial aid", "fao", "home visit", "scholarship"],
        "source": "FREQUENTLY ASKED QUESTIONS (FAQS) | NUST (Scholarship FAQs)",
        "category": "scholarships"
    },
    {
        "id": "qa_sch_hard_copies",
        "type": "qa",
        "question": "Do I need to send hard copies of documents after submitting NFAAF?",
        "answer": "No, you do not need to send hard copies of supporting documents immediately after submitting the NFAAF. After processing your application, the Financial Aid Office (FAO) will email you with instructions to mail hard copy documents by a specified deadline. Failure to provide documents by that deadline will result in cancellation of your NFAAF.",
        "content": "Do I need to send hard copies of documents after submitting NFAAF? No, you do not need to send hard copies of supporting documents immediately after submitting the NFAAF. After processing your application, the Financial Aid Office (FAO) will email you with instructions to mail hard copy documents by a specified deadline. Failure to provide documents by that deadline will result in cancellation of your NFAAF.",
        "keywords": ["hard copies", "documents", "nfaaf", "financial aid", "fao", "submission"],
        "source": "FREQUENTLY ASKED QUESTIONS (FAQS) | NUST (Scholarship FAQs)",
        "category": "scholarships"
    },
    {
        "id": "qa_sch_peef_other",
        "type": "qa",
        "question": "Do I need a separate form to apply for PEEF or other external scholarships at NUST?",
        "answer": "No. Once you submit the NFAAF, NUST automatically considers you for all types of need-based scholarships including PEEF, CMEEF (KPK), FEF, and others. The FAO will inform you if any additional form or document is needed for a specific scholarship.",
        "content": "Do I need a separate form to apply for PEEF or other external scholarships at NUST? No. Once you submit the NFAAF, NUST automatically considers you for all types of need-based scholarships including PEEF, CMEEF (KPK), FEF, and others. The FAO will inform you if any additional form or document is needed for a specific scholarship.",
        "keywords": ["peef", "cmeef", "fef", "external scholarship", "nfaaf", "separate form"],
        "source": "FREQUENTLY ASKED QUESTIONS (FAQS) | NUST (Scholarship FAQs)",
        "category": "scholarships"
    },
    {
        "id": "qa_sch_missing_docs",
        "type": "qa",
        "question": "What if I don't have some of the required documents for the NUST financial aid form?",
        "answer": "If you are missing some supporting documents, you can attach a handwritten letter of explanation (signed by you and your parent/guardian) stating the reason for the missing document and the expected date by which you will provide it to the Financial Aid Office. If the system won't let you upload, ensure each document file is under 250KB. For upload errors, email financialaid@nust.edu.pk with a screenshot.",
        "content": "What if I don't have some of the required documents for the NUST financial aid form? If you are missing some supporting documents, you can attach a handwritten letter of explanation (signed by you and your parent/guardian) stating the reason for the missing document and the expected date by which you will provide it to the Financial Aid Office. If the system won't let you upload, ensure each document file is under 250KB. For upload errors, email financialaid@nust.edu.pk with a screenshot.",
        "keywords": ["missing documents", "nfaaf", "financial aid", "letter of explanation", "upload", "250kb"],
        "source": "FREQUENTLY ASKED QUESTIONS (FAQS) | NUST (Scholarship FAQs)",
        "category": "scholarships"
    },
    {
        "id": "qa_sch_scholarship_transfer",
        "type": "qa",
        "question": "Can my NUST scholarship be transferred if I change my program from the merit list?",
        "answer": "Yes, a scholarship offer can be transferred to other programs you are offered in subsequent selection lists, but only if you have already deposited dues to secure admission in your first offered program. To transfer, notify the admission office at ugadmissions@nust.edu.pk and fao@nust.edu.pk. If you do not deposit dues, the scholarship offer is cancelled and the slot is offered to others in the next list.",
        "content": "Can my NUST scholarship be transferred if I change my program from the merit list? Yes, a scholarship offer can be transferred to other programs you are offered in subsequent selection lists, but only if you have already deposited dues to secure admission in your first offered program. To transfer, notify the admission office at ugadmissions@nust.edu.pk and fao@nust.edu.pk. If you do not deposit dues, the scholarship offer is cancelled and the slot is offered to others in the next list.",
        "keywords": ["scholarship transfer", "program change", "merit list", "selection list", "fao", "financial aid"],
        "source": "FREQUENTLY ASKED QUESTIONS (FAQS) | NUST (Scholarship FAQs)",
        "category": "scholarships"
    },
    {
        "id": "qa_sch_change_nfaaf",
        "type": "qa",
        "question": "How do I correct or update my NFAAF after submission?",
        "answer": "After submitting your NFAAF, you cannot directly edit it. To make changes, email fao@nust.edu.pk specifying: the Section, Sub-section, Field title to be amended, and the corrected values. The FAO may contact you for additional information. If your financial profile changes significantly, you can apply for a review at any time through your institution.",
        "content": "How do I correct or update my NFAAF after submission? After submitting your NFAAF, you cannot directly edit it. To make changes, email fao@nust.edu.pk specifying: the Section, Sub-section, Field title to be amended, and the corrected values. The FAO may contact you for additional information. If your financial profile changes significantly, you can apply for a review at any time through your institution.",
        "keywords": ["correct", "update", "nfaaf", "after submission", "financial aid", "fao", "changes"],
        "source": "FREQUENTLY ASKED QUESTIONS (FAQS) | NUST (Scholarship FAQs)",
        "category": "scholarships"
    },
    {
        "id": "qa_sch_divorced_parents",
        "type": "qa",
        "question": "My parents are divorced. Will that affect my NUST financial aid application?",
        "answer": "NUST expects both parents to provide financial information even if they are separated or divorced. Both parents' financial documents are assessed to determine contribution ability. If one parent is unwilling, inform them that their information stays confidential and does not obligate them to pay. If your situation is special, write a detailed letter of explanation to the Financial Aid Office.",
        "content": "My parents are divorced. Will that affect my NUST financial aid application? NUST expects both parents to provide financial information even if they are separated or divorced. Both parents' financial documents are assessed to determine contribution ability. If one parent is unwilling, inform them that their information stays confidential and does not obligate them to pay. If your situation is special, write a detailed letter of explanation to the Financial Aid Office.",
        "keywords": ["divorced", "separated", "parents", "financial aid", "nfaaf", "single parent"],
        "source": "FREQUENTLY ASKED QUESTIONS (FAQS) | NUST (Scholarship FAQs)",
        "category": "scholarships"
    },
    {
        "id": "qa_sch_need_assessment",
        "type": "qa",
        "question": "What is the need assessment process for NUST financial aid?",
        "answer": "The NUST need assessment process follows these stages: (1) FAO verifies NFAAF and supporting documents, seeks clarifications on anomalies. (2) Applicants are contacted to resolve discrepancies. (3) FAO prepares evaluation sheets for each applicant. (4) Shortlisted candidates submit hard-copy documents. (5) Interviews and physical verification are conducted where necessary. (6) The NUST Financial Aid Committee reviews each case and decides based purely on financial need. (7) Decision is communicated via an official provisional scholarship award letter. FAO conducts periodic reviews to ensure the award reaches genuinely needy students.",
        "content": "What is the need assessment process for NUST financial aid? The NUST need assessment process follows these stages: (1) FAO verifies NFAAF and supporting documents, seeks clarifications on anomalies. (2) Applicants are contacted to resolve discrepancies. (3) FAO prepares evaluation sheets for each applicant. (4) Shortlisted candidates submit hard-copy documents. (5) Interviews and physical verification are conducted where necessary. (6) The NUST Financial Aid Committee reviews each case and decides based purely on financial need. (7) Decision is communicated via an official provisional scholarship award letter. FAO conducts periodic reviews to ensure the award reaches genuinely needy students.",
        "keywords": ["need assessment", "financial aid", "process", "fao", "committee", "evaluation", "scholarship"],
        "source": "FREQUENTLY ASKED QUESTIONS (FAQS) | NUST (Scholarship FAQs)",
        "category": "scholarships"
    },
    {
        "id": "qa_sch_income_certificate",
        "type": "qa",
        "question": "What income certificate do I need for NUST financial aid if my father is unemployed or does business?",
        "answer": "For the NUST NFAAF income certificate requirements: (1) If unemployed: a Declaration of all income sources on affidavit on stamp paper (>Rs. 100), attested by Union Councilor and two witnesses (one a Govt. officer BPS-17+). (2) If business: same affidavit format listing all business income. (3) If salaried + part-time (agriculture, shop, taxi, tuition): salary certificate plus affidavit for supplemental income. (4) If agricultural income: affidavit attested by Assistant Commissioner Revenue or Union Councilor and two witnesses.",
        "content": "What income certificate do I need for NUST financial aid if my father is unemployed or does business? For the NUST NFAAF income certificate requirements: (1) If unemployed: a Declaration of all income sources on affidavit on stamp paper (>Rs. 100), attested by Union Councilor and two witnesses (one a Govt. officer BPS-17+). (2) If business: same affidavit format listing all business income. (3) If salaried + part-time (agriculture, shop, taxi, tuition): salary certificate plus affidavit for supplemental income. (4) If agricultural income: affidavit attested by Assistant Commissioner Revenue or Union Councilor and two witnesses.",
        "keywords": ["income certificate", "nfaaf", "unemployed", "business", "affidavit", "stamp paper", "financial aid"],
        "source": "FREQUENTLY ASKED QUESTIONS (FAQS) | NUST (Scholarship FAQs)",
        "category": "scholarships"
    },
    {
        "id": "qa_sch_outside_grant",
        "type": "qa",
        "question": "If I receive a scholarship from an outside organization, should I tell NUST?",
        "answer": "Yes. If you receive any external grant, scholarship, or third-party payment, you must report the type and amount to the NUST Financial Aid Office (FAO) as soon as you receive it. Failure to report may affect your NUST financial aid status.",
        "content": "If I receive a scholarship from an outside organization, should I tell NUST? Yes. If you receive any external grant, scholarship, or third-party payment, you must report the type and amount to the NUST Financial Aid Office (FAO) as soon as you receive it. Failure to report may affect your NUST financial aid status.",
        "keywords": ["outside scholarship", "grant", "third party", "report", "fao", "financial aid"],
        "source": "FREQUENTLY ASKED QUESTIONS (FAQS) | NUST (Scholarship FAQs)",
        "category": "scholarships"
    },
    {
        "id": "qa_sch_mid_semester",
        "type": "qa",
        "question": "Can I apply for NUST financial aid during the semester or academic year?",
        "answer": "Generally, financial aid applications are only accepted at the time of admission. However, students whose financial situation drastically changes during the year due to unforeseen circumstances (e.g., parent's death, retirement, job loss) can apply for financial assistance during the semester or year through their institution.",
        "content": "Can I apply for NUST financial aid during the semester or academic year? Generally, financial aid applications are only accepted at the time of admission. However, students whose financial situation drastically changes during the year due to unforeseen circumstances (e.g., parent's death, retirement, job loss) can apply for financial assistance during the semester or year through their institution.",
        "keywords": ["mid semester", "apply", "financial aid", "during year", "unforeseen", "job loss", "death"],
        "source": "FREQUENTLY ASKED QUESTIONS (FAQS) | NUST (Scholarship FAQs)",
        "category": "scholarships"
    },
    {
        "id": "qa_sch_criteria",
        "type": "qa",
        "question": "What is the criteria for awarding financial aid at NUST?",
        "answer": "The NUST scholarship committee assesses the financial need of all applicants to determine whether their family has sufficient resources to afford NUST fees. Need is determined purely based on the financial credentials submitted (income certificates, bank statements, property details, etc.). The process is transparent — there is also an appeal process where students can provide additional information that may have been missed during initial assessment.",
        "content": "What is the criteria for awarding financial aid at NUST? The NUST scholarship committee assesses the financial need of all applicants to determine whether their family has sufficient resources to afford NUST fees. Need is determined purely based on the financial credentials submitted (income certificates, bank statements, property details, etc.). The process is transparent — there is also an appeal process where students can provide additional information that may have been missed during initial assessment.",
        "keywords": ["criteria", "awarding", "financial aid", "scholarship", "need", "assessment", "appeal"],
        "source": "FREQUENTLY ASKED QUESTIONS (FAQS) | NUST (Scholarship FAQs)",
        "category": "scholarships"
    },
]


def main():
    print(f"Loading: {QA_FILE}")
    with open(QA_FILE, "r", encoding="utf-8") as f:
        pairs = json.load(f)

    original_count = len(pairs)
    print(f"Original count: {original_count}")

    cleaned = []
    removed_ids = []
    for entry in pairs:
        eid = entry.get("id", "")
        source = entry.get("source", "")

        # Remove if in explicit remove list
        if eid in REMOVE_IDS:
            removed_ids.append(eid)
            continue

        # Remove if from Masters FAQ Hub source
        if source in REMOVE_SOURCES:
            removed_ids.append(eid)
            continue

        # Fix dirty answers
        if eid in FIX_ANSWERS:
            entry["answer"] = FIX_ANSWERS[eid]
            entry["content"] = entry["question"] + " " + FIX_ANSWERS[eid]

        cleaned.append(entry)

    print(f"Removed {len(removed_ids)} entries:")
    for rid in removed_ids:
        print(f"  - {rid}")

    # Check for any remaining PG mentions
    pg_warnings = []
    for entry in cleaned:
        q = entry.get("question", "").lower()
        a = entry.get("answer", "").lower()
        for term in ["masters program", " ms ", "phd", " mbbs ", "bshnd", "nshs", "gnet", " gat ", " gre "]:
            if term in q or term in a:
                pg_warnings.append(f"  WARN {entry['id']}: might be PG-related ({term})")
                break

    if pg_warnings:
        print("\nPotential remaining PG content (check manually):")
        for w in pg_warnings:
            print(w)

    # Add scholarship QAs
    existing_ids = {e["id"] for e in cleaned}
    added = 0
    for qa in SCHOLARSHIP_QAS:
        if qa["id"] not in existing_ids:
            cleaned.append(qa)
            added += 1

    print(f"\nAdded {added} scholarship FAQ entries")
    print(f"Final count: {len(cleaned)} (was {original_count})")

    # Write output
    with open(QA_FILE, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Saved cleaned qa_pairs.json to {QA_FILE}")


if __name__ == "__main__":
    main()
