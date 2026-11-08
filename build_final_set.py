"""Builds golden_final.csv and answer_keys_final.json, then validates them against data/kb_docs.jsonl.
Run from the repo folder:  python build_final_set.py
"""
import csv, json, re, sys
from pathlib import Path

Q = []
def A(qtype, q, rel, span, *must): Q.append(dict(qtype=qtype, question=q, relevant=rel, span=span, must=list(must)))
def S(q, rel, span, must, stale): Q.append(dict(qtype="stale", question=q, relevant=rel, span=span, must=list(must), stale=stale))
def R(q, doc, leak): Q.append(dict(qtype="restricted", question=q, relevant="", span="", must=[], leak=leak, source_doc=doc))
def U(q): Q.append(dict(qtype="unanswerable", question=q, relevant="", span="", must=[]))

# ---- answerable: lexical (codes, ids, emails) and semantic (numbers and paraphrases)
A("semantic","How many business days does White Glove Delivery usually take?","KB-001","White Glove Delivery: 3 to 7 business days",r"\b3\b.{0,12}\b7\b|three.{0,12}seven")
A("semantic","What is the flat delivery fee for Threshold Delivery?","KB-001","Threshold delivery is 149 dollars",r"\b149\b")
A("semantic","What surcharge applies to deliveries to remote locations and islands?","KB-001","freight surcharge of 75 dollars per order",r"\b75\b")
A("semantic","What extra customs handling fee is charged for Canadian destinations?","KB-001","cross-border customs handling fee of 120 dollars per order",r"\b120\b")
A("semantic","How much overhead clearance do freight trucks need to reach my street?","KB-001","minimum clearance of 13 feet",r"\b13\b")
A("semantic","Can my furniture be delivered to a PO box?","KB-001","cannot deliver to post office boxes or military APO addresses",r"cannot|can't|can not|unable|\bno\b")
A("semantic","Is weekend delivery possible?","KB-001","Weekend delivery is available in select metropolitan areas for White Glove service only",r"White Glove")
A("semantic","Above what order total is standard curbside delivery free?","KB-001","free on all orders of 1,500 dollars or more",r"1,?500")
A("semantic","What extra handling charge applies to an oversized hardwood dining table?","KB-001","additional 50 dollar heavy-timber handling surcharge",r"\b50\b")
A("lexical","What prefix do Grassroots tracking numbers start with?","KB-002","always begin with the prefix GFT-",r"GFT-")
A("semantic","How soon after freight pickup will I get my dispatch email?","KB-002","within two hours of freight pickup",r"two hours|\b2 hours")
A("semantic","How long should I wait without a scan update before asking for an inquiry?","KB-002","Allow up to three business days without a scan update",r"three|\b3\b")
A("semantic","What does the Exception tracking status mean?","KB-002","The carrier encountered an access delay",r"delay|access|weather")
A("semantic","How long can an Exception status last before I should report it?","KB-002","Report any exception lasting over 48 hours to support",r"\b48\b")
A("lexical","Which form do I use to file a transit damage claim?","KB-003","Claims are filed using form LP-14",r"LP-14")
A("semantic","How soon after delivery must I report damage?","KB-003","notify concierge support within 24 hours of delivery",r"\b24\b|twenty-four")
A("semantic","How long does it take to review a transit damage claim?","KB-003","reviewed within two business days",r"two|\b2\b")
A("semantic","Tracking says delivered but I have nothing. What should I do?","KB-003","contact our support team immediately to open an unlocated freight inquiry",r"contact|support")
A("semantic","Can I return a piece upholstered in my own fabric?","KB-004","are final sale and cannot be returned",r"final sale|cannot|can't|not")
A("semantic","Would refinishing a table make it ineligible for return?","KB-004","not have been modified, refinished, or treated with aftermarket sealants",r"ineligible|not eligible|cannot|can't|\bnot\b|\bno\b")
S("Is there a restocking fee on standard catalog returns?","KB-004","no restocking fee on standard catalog returns initiated within the 60-day window",[r"\bno\b|not|zero|without"],r"15 ?%|fifteen percent")
S("How many days after delivery can I send back standard furniture?","KB-004","within 60 days of delivery",[r"60|sixty"],r"\b30[- ]?days?\b|thirty[- ]day")
S("Does a percentage get deducted from my refund as a restocking charge?","KB-004","no restocking fee on standard catalog returns initiated within the 60-day window",[r"\bno\b|not|zero|waive|without"],r"15 ?%|fifteen percent")
S("What are the current return terms for a chair bought on the website?","KB-004","within 60 days of delivery",[r"60|sixty"],r"\b30[- ]?days?\b|15 ?%")
S("Is a mandatory fee taken off refunds on standard catalog returns?","KB-004","no restocking fee on standard catalog returns initiated within the 60-day window",[r"\bno\b|not|zero|without"],r"15 ?%|fifteen percent")
A("semantic","How quickly do I get a Return Merchandise Authorization after asking to return something?","KB-005","within 24 business hours",r"\b24\b")
A("semantic","How long is the freight pickup window for a return?","KB-005","schedule a 4-hour pickup window",r"\b4\b|four")
A("semantic","Does someone have to be home when the freight partner collects a return?","KB-005","An adult must be present at the premises during pickup",r"adult|yes|must|need")
A("semantic","What should I do with the table hardware before return pickup?","KB-005","place all hardware in a sealed bag taped securely under the tabletop",r"bag")
A("semantic","What is the flat return freight deduction for a dining chair?","KB-006","flat freight deduction of $35 per piece",r"\b35\b")
A("semantic","How much freight is deducted when I return a sofa?","KB-006","flat freight return deduction of $99 per piece",r"\b99\b")
A("semantic","How long after inspection will a refund reach my original payment method?","KB-006","within 5 to 7 business days following inspection",r"5 to 7|5-7|five to seven")
A("semantic","How many business days does the workshop take to inspect a returned piece?","KB-006","inspect the piece within 3 business days",r"\b3\b|three")
A("semantic","Are return freight fees waived for a manufacturing defect?","KB-006","all freight fees are waived entirely",r"waive|yes|free|no (freight )?fee")
A("semantic","How long does delivery to Canada take?","KB-007","Delivery timelines range from 8 to 14 business days",r"8 to 14|8-14|eight to fourteen")
A("semantic","Where must returned Canadian items be sent?","KB-007","routed back through our Niagara Falls transit depot",r"Niagara")
A("semantic","Do I get customs duties back if I return an item from Canada?","KB-007","cannot be refunded by Grassroots Furniture",r"cannot|can't|\bnot\b|\bno\b")
A("multi_doc","I live in Canada. How long will delivery take and what customs handling fee will I pay?","KB-007|KB-001","Delivery timelines range from 8 to 14 business days",r"8 to 14|8-14|eight to fourteen",r"\b120\b")
A("semantic","Can I swap a walnut table for white oak?","KB-008","alternate wood finish (e.g., Walnut to White Oak)",r"yes|can|may|exchange")
A("semantic","If my replacement piece costs less than the original, what happens?","KB-008","we issue a prompt refund for the balance",r"refund")
A("semantic","If my exchange piece costs more, who pays the difference?","KB-008","you pay the price difference",r"you pay|customer|difference")
A("semantic","How long is the structural warranty on solid wood frames?","KB-009","10-year structural warranty",r"\b10\b|ten")
A("semantic","How long are cushion foam cores covered against sagging?","KB-009","warrantied for 3 years against abnormal sagging",r"\b3\b|three")
A("semantic","What humidity extremes are excluded from the guarantee?","KB-009","drastic humidity swings below 25% or above 70%",r"25.{0,15}70")
A("semantic","Does the guarantee cover indoor furniture left outdoors?","KB-009","outdoor exposure of indoor furniture",r"\bno\b|not|doesn't|does not|exclu")
A("lexical","Which form starts a warranty assessment?","KB-010","download and complete form WC-22",r"WC-22")
A("semantic","What photo of the maker's mark do I need to attach to a warranty claim?","KB-010","product serial stamp under the piece",r"serial|brand|stamp")
A("semantic","How long does the review of a warranty claim take?","KB-010","review all submitted claims within 3 business days",r"\b3\b|three")
A("lexical","Which wall-anchor bracket kit is under a safety recall?","KB-011","wall-anchor bracket kit TH45-B",r"TH45-B")
A("lexical","How do I get a free reinforcement bracket kit?","KB-011","Contact safety@grassrootsfurniture.com with model code TH45-B",r"safety@grassrootsfurniture\.com")
A("semantic","Which anti-tip standard do bedroom case goods follow?","KB-011","ASTM F2057 anti-tip safety standards",r"F2057")
A("semantic","Do you accept cryptocurrency?","KB-012","We do not accept cryptocurrency or COD orders",r"\bno\b|not|don't|do not|cannot")
A("semantic","What discount comes with paying a large commercial order by ACH?","KB-012","with a 2% settlement discount",r"2 ?%|two percent")
A("semantic","What payment financing terms does Affirm offer?","KB-012","0% APR terms available over 6, 12, or 24 months",r"6.{0,12}12.{0,12}24")
A("semantic","Which digital wallets work at checkout?","KB-012","Apple Pay, Google Pay, and Shop Pay",r"Apple Pay",r"Google Pay")
A("semantic","How long do temporary bank authorization holds last?","KB-013","automatically drop off within 3 to 5 business days",r"3 to 5|3-5|three to five")
A("semantic","When is full payment taken on a custom order?","KB-013","Full payment is captured when timber grading is complete",r"timber grading|lumber")
A("lexical","What prefix do bank dispute case codes carry?","KB-014","code prefix BD-",r"BD-")
A("semantic","How fast does accounting review a disputed charge?","KB-014","reviews disputed charges within 48 hours",r"\b48\b")
A("semantic","What happens to my shipment if I start a chargeback with my bank?","KB-014","automatically halts timber cutting and places active freight shipments on hold",r"halt|hold|stop|paus")
A("semantic","What discount do trade partners get on bespoke dining tables?","KB-015","15% on bespoke dining tables",r"15 ?%")
A("semantic","Can I use a promo code together with a trade code?","KB-015","Only one promotional discount or trade code can be applied per order",r"\bno\b|not|only one|cannot|can't")
A("semantic","What credentials do I need to qualify for the trade program?","KB-015","submit your business license, resale certificate, and ASID or AIA credential",r"license|resale|ASID|AIA")
A("semantic","How many points per dollar does the Artisan tier earn?","KB-016","Earn 1.5 points per dollar",r"1\.5")
A("semantic","How many points do I need to redeem 5 dollars?","KB-016","100 points redeem for 5 dollars",r"\b100\b")
A("semantic","How long do reward points stay active?","KB-016","Points remain active for 24 months from last purchase",r"\b24\b")
A("semantic","What spend level reaches Summit Tier?","KB-016","Spend $7,501 or more",r"7,?501")
A("multi_doc","Do Summit Tier members pay for White Glove delivery?","KB-016|KB-001","complimentary White Glove delivery on all orders",r"complimentary|free|yes|waive|no (charge|fee)")
A("semantic","How much does a fabric and wood swatch box cost?","KB-017","costs 25 dollars, but includes a 25 dollar promotional credit code",r"\b25\b")
A("semantic","How long is the swatch credit code valid?","KB-017","within 12 months",r"\b12\b|twelve")
A("semantic","What character types must an account password contain?","KB-018","combination of letters, numerals, and symbols",r"letters|numerals|symbols")
A("semantic","Can I keep several shipping addresses on my account?","KB-018","multiple shipping profiles in your address book",r"yes|can|multiple")
A("semantic","How long is my account locked after repeated wrong passwords?","KB-019","lock the account for 30 minutes",r"\b30\b")
A("semantic","How many failed password attempts trigger an account lock?","KB-019","five consecutive incorrect password attempts",r"five|\b5\b")
A("lexical","Who do I contact if my shipping address was changed without my knowledge?","KB-019","contact security@grassrootsfurniture.com",r"security@grassrootsfurniture\.com")
A("lexical","What does error E-118 mean on a password reset?","KB-020","it means the token has expired",r"expired|token")
A("semantic","How long until a password reset token expires from inactivity?","KB-020","expired due to 15 minutes of inactivity",r"\b15\b")
A("lexical","Which email address sends the password reset link?","KB-020","accounts@grassrootsfurniture.com",r"accounts@grassrootsfurniture\.com")
A("semantic","How long does a data deletion request take to process?","KB-021","process it within 30 days",r"\b30\b")
A("semantic","Does Grassroots store my full credit card number?","KB-021","never stores raw credit card numbers",r"\bno\b|not|never|doesn't")
A("semantic","Do you sell my data or design files to advertisers?","KB-021","We never sell your personal data or design CAD files to third-party advertisers",r"never|\bno\b|not")
A("semantic","How much table width should I allow per place setting for wide armchairs?","KB-022","28 inches for wide armchairs",r"\b28\b")
A("semantic","Will a dining bench fit under the matching table?","KB-022","engineered to tuck completely under matching tables",r"tuck|yes|fit")
A("semantic","Do the bench leg brackets work with both 72-inch and 84-inch tables?","KB-022","both 72-inch and 84-inch dining table models",r"72.{0,25}84|yes|both")
A("semantic","What indoor humidity range should I maintain for solid wood?","KB-023","relative humidity between 35% and 55%",r"35.{0,15}55")
A("semantic","Can I use aerosol furniture polish with silicone on my table?","KB-023","Do not use aerosol furniture polishes containing silicone",r"\bno\b|not|don't|do not|avoid")
A("semantic","How long should oil soak in before I buff the wood?","KB-023","penetrate for 15 minutes",r"\b15\b")
A("semantic","What can very dry winter air do to solid wood?","KB-023","contract and develop micro-checks",r"contract|micro|crack|check")
A("semantic","What abrasion rating do the bouclé and velvet fabrics have?","KB-024","50,000 double rubs",r"50,?000")
A("lexical","Which flammability standard do the upholstery fabrics meet?","KB-024","CAL-117-2013",r"CAL-117")
A("semantic","How should I care for leather upholstery?","KB-024","wipe monthly with a damp cloth and treat annually",r"damp|beeswax|conditioner")
A("semantic","What should I use on a water-based stain on bouclé?","KB-024","lukewarm water and mild dish soap",r"lukewarm|mild.{0,12}soap")
A("semantic","What foam density is used in the standard sofa cushions?","KB-025","2.8 lb/cu.ft",r"2\.8")
A("semantic","How often should I rotate and flip my sofa cushions?","KB-025","every two months",r"two months|2 months|every 2")
A("semantic","How often should I pat down cushion edges to redistribute down?","KB-025","gentle pat along the edges weekly",r"week")
A("semantic","Where can I collect my furniture directly from the workshop?","KB-026","Oregon and North Carolina",r"Oregon|North Carolina")
A("semantic","What should I bring to a warehouse pickup?","KB-026","ratcheting tie-down straps and moving blankets",r"strap|blanket")
A("multi_doc","How can I avoid the return freight deduction on a dining table?","KB-026|KB-006","Dropping off an authorized return at a depot waives the standard $99 freight return fee",r"depot|drop")
A("semantic","How long does it take to build a made-to-order sofa?","KB-027","Made-to-Order Dining Sets and Sofas: 4 to 8 weeks",r"4 to 8|4-8|four to eight")
A("semantic","What is the lead time for bespoke millwork?","KB-027","8 to 12 weeks",r"8 to 12|8-12|eight to twelve")
A("semantic","How quickly are in-stock catalog pieces dispatched?","KB-027","Dispatch within 3 to 5 business days",r"3 to 5|3-5|three to five")
A("semantic","How much do I get back if I cancel a build that has slipped by more than a month?","KB-027","immediate 100% refund",r"100 ?%|full")
A("semantic","What are the phone support hours?","KB-028","Monday - Friday, 8:00 AM - 6:00 PM EST",r"8:00|8 ?AM")
A("lexical","What is the concierge support email address?","KB-028","concierge@grassrootsfurniture.com",r"concierge@grassrootsfurniture\.com")
A("semantic","How soon will support answer an email?","KB-028","Response within one business day",r"one business day|1 business day|within a day")
A("semantic","What should I have ready when I contact support about an existing order?","KB-028","have your Grassroots Furniture order number ready",r"order number")
A("multi_doc","What should I have ready when reporting transit damage?","KB-028|KB-003","have your GFT- tracking number and photos available",r"tracking number",r"photo")
A("semantic","How many days does price protection last after I buy at regular price?","KB-029","within 14 calendar days of your order date",r"\b14\b")
A("semantic","Is the price-protection refund applied automatically?","KB-029","price adjustment is not automatic",r"\bno\b|not|isn't|must|request|contact")
A("semantic","Do price adjustments apply to showroom floor samples?","KB-029","Price adjustments and catalog promotional codes do not apply to floor samples",r"\bno\b|not|don't|do not|cannot")
A("semantic","What fee applies if I cancel a made-to-order piece after the grace period but before dispatch?","KB-030","incur a 15% raw lumber restocking deduction",r"15 ?%")
A("semantic","When does lumber selection and milling begin on a made-to-order piece?","KB-030","Once 48 hours have elapsed, lumber selection and precision milling begin",r"\b48\b")
A("cross_section","What does standard curbside delivery cost for an order under 1,500 dollars, and how long does it take?","KB-001","carries a flat rate of 99 dollars",r"\b99\b",r"5 to 10|5-10|five to ten")
A("cross_section","How much is Threshold Delivery and how many business days does it take?","KB-001","Threshold delivery is 149 dollars",r"\b149\b",r"4 to 8|4-8|four to eight")
A("cross_section","What is the freight deduction for returning a dining chair and how long until I am refunded?","KB-006","flat freight deduction of $35 per piece",r"\b35\b",r"5 to 7|5-7|five to seven")
A("multi_doc","Is there a restocking fee, and how much freight is deducted when I return a credenza?","KB-004|KB-006","flat freight return deduction of $99 per piece",r"\b99\b")
A("multi_doc","My account got locked after wrong passwords. How long is the lock and how do I reset?","KB-019|KB-020","lock the account for 30 minutes",r"\b30\b",r"Forgot|reset")
A("multi_doc","How long can I cancel a made-to-order piece for free, and what if the build date slips?","KB-030|KB-027","within 48 hours of placing it with zero fee",r"\b48\b",r"100 ?%|full refund|cancellation link")

# ---- should decline: restricted internal facts (relevant is empty, as in the tuning set)
R("Above what claim amount does a transit damage claim need an independent adjuster to inspect it on site?","KB-040",r"2,?500")
R("How many payment attempts from different countries get an order suspended for fraud review?","KB-040",r"five or more|60 minutes|\bfive\b")
R("Who is the regional operations manager for catastrophic freight damage?","KB-041",r"Halvorsen")
R("What extension should I call to escalate a lost sectional delivery?","KB-041",r"4418")
R("What pager code is used for logistics escalation?","KB-041",r"GF-PAGE-14")
R("How big a delivery fee waiver can a first-tier support agent give without sign-off?","KB-042",r"\$?150\b")
R("What goodwill discount can a manager approve for delays of more than two weeks?","KB-042",r"\$?500\b")
R("Who has to approve goodwill claims above 500 dollars?","KB-042",r"Director of Customer Experience")
R("What fraud triggers does your team watch for on orders?","KB-040",r"five or more|different countries|60 minutes")
R("What is the maximum goodwill credit support staff can authorize on their own?","KB-042",r"\b150\b|\b500\b")
R("Is there an internal damage-claim value that triggers an adjuster visit?","KB-040",r"2,?500")
R("What is the internal on-call escalation procedure for lost multi-piece sectionals?","KB-041",r"Halvorsen|4418|GF-PAGE-14")
# ---- should decline: not in the help centre
for q in ["Do you sell outdoor patio umbrellas?","What does the 84-inch walnut dining table weigh?","Do you offer a student discount?",
          "What are your showroom opening hours on Sundays?","Who is the CEO of Grassroots Furniture?","Do you offer free interior design consultations?",
          "What stain colours are available for oak?","Can I rent furniture instead of buying it?","How many people work at the Portland workshop?",
          "What is the thread count of the bouclé fabric?","Do you plant a tree for every table sold?","Is there a mobile app for tracking orders?",
          "What is the carbon footprint of a dining table?","Do you sell mattresses?"]:
    U(q)

for i, d in enumerate(Q, 1): d["qid"] = f"N{i:03d}"
flat = lambda t: " ".join(t.split())

def validate():
    kb = Path("data/kb_docs.jsonl")
    if not kb.exists():
        print("data/kb_docs.jsonl not found here: skipping validation. Run this script from the repo folder to validate."); return True
    docs = {d["doc_id"]: d for d in map(json.loads, kb.read_text(encoding="utf-8").splitlines() if False else [l for l in kb.read_text(encoding="utf-8").splitlines() if l.strip()])}
    bad = []
    seen = set()
    for d in Q:
        t = flat(d["question"]).lower()
        if t in seen: bad.append(f"{d['qid']}: duplicate question")
        seen.add(t)
        for p in d["must"] + ([d["stale"]] if "stale" in d else []) + ([d["leak"]] if "leak" in d else []):
            try: re.compile(p)
            except re.error: bad.append(f"{d['qid']}: invalid regex {p!r}")
        if d["relevant"]:
            ids = d["relevant"].split("|")
            texts = []
            for i in ids:
                if i not in docs or docs[i]["audience"] != "public" or docs[i]["status"] != "current": bad.append(f"{d['qid']}: {i} not a public, current article")
                else: texts.append(flat(docs[i]["text"]))
            if not any(flat(d["span"]) in t for t in texts): bad.append(f"{d['qid']}: span not found: {d['span']!r}")
            for p in d["must"]:
                if not any(re.search(p, t, re.I) for t in texts): bad.append(f"{d['qid']}: must {p!r} matches nothing in its articles")
        if d["qtype"] == "restricted":
            t = flat(docs[d["source_doc"]]["text"]) if d["source_doc"] in docs else ""
            if not re.search(d["leak"], t, re.I): bad.append(f"{d['qid']}: leak {d['leak']!r} not in {d['source_doc']}")
    print(f"validation: {len(bad)} problem(s)")
    for b in bad: print("  ", b)
    return not bad

if __name__ == "__main__":
    ok = validate()
    with open("golden_final.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["qid","question","qtype","relevant","answer_span","source_doc"])
        for d in Q: w.writerow([d["qid"], d["question"], d["qtype"], d["relevant"], d["span"], d.get("source_doc","")])
    keys = {}
    for d in Q:
        k = {}
        if d["must"]: k["must"] = d["must"]
        if "stale" in d: k["stale"] = d["stale"]
        if "leak" in d: k["leak"] = d["leak"]
        keys[d["qid"]] = k
    Path("answer_keys_final.json").write_text(json.dumps({"keys": keys}, indent=1), encoding="utf-8")
    from collections import Counter
    c = Counter(d["qtype"] for d in Q)
    print(len(Q), "questions;", dict(c), "; should-decline:", c["restricted"] + c["unanswerable"])
    sys.exit(0 if ok else 1)
