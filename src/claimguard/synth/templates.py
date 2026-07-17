"""Clinical templates for the synthetic discharge-record engine.

Ground truth ICD-10 codes are embedded per template rather than assigned
per record: each template is a single clinically-reviewed (diagnosis, ICD
code) pair, and every generated record just instantiates one template with
randomized demographics/dates/amounts/scenario. This makes the golden set
answer-key-by-construction — clinical correctness is verified once per
template (12 checks) instead of once per record (hundreds of checks). The
trade-off, stated honestly: it cannot catch per-record coding errors,
because there are none to catch — the code is fixed at the template level.
It also means diversity comes from note-variant wording and scenario
injection, not from diagnosis variety within a template.
"""

REQUIRED_DOCS: dict[str, list[str]] = {
    "cashless": ["discharge_summary", "final_bill", "preauth_form", "id_proof"],
    "reimbursement": [
        "discharge_summary",
        "final_bill",
        "payment_receipts",
        "claim_form",
        "id_proof",
    ],
}

VAGUE_DX = [
    "Fever under evaluation, ?viral ?bacterial",
    "Abdominal pain, cause unclear, obs.",
    "Generalised weakness, w/u ongoing",
]

_DEFAULT_WEIGHTS = {"normal": 0.7, "missing_doc": 0.15, "vague_dx": 0.15}
_CLAIM_TYPES = ["cashless", "reimbursement"]

TEMPLATES: list[dict] = [
    {
        "specialty": "general_surgery",
        "diagnosis_text": "Acute appendicitis",
        "icd_codes": ["K35.9"],
        "procedures": ["Laparoscopic appendectomy"],
        "medications": [
            "Inj Ceftriaxone 1g IV BD",
            "Inj Metronidazole 500mg IV TID",
            "Tab Paracetamol 650mg SOS",
        ],
        "claim_band": (40000, 90000),
        "claim_types": _CLAIM_TYPES,
        "scenario_weights": dict(_DEFAULT_WEIGHTS),
        "notes": [
            "Patient presented with a 2-day history of periumbilical pain migrating to the "
            "right iliac fossa, associated with low-grade fever and vomiting. On examination, "
            "tenderness and guarding at McBurney's point with positive Rovsing's sign. USG "
            "abdomen showed a non-compressible, dilated appendix (9mm) with peri-appendiceal "
            "fat stranding, confirming acute appendicitis. Patient was taken up for emergency "
            "laparoscopic appendectomy under general anaesthesia. Intraoperatively, an "
            "inflamed, non-perforated appendix was noted; appendectomy performed uneventfully "
            "with no intraoperative complications. Post-op recovery was uneventful, patient "
            "tolerated oral feeds by day 2, ambulated independently, and was discharged in "
            "stable condition with advice for wound care and follow-up.",
            "H/o pain abdomen x 2 days, shifted to RIF, fever+, vomiting+. USG s/o acute "
            "appendicitis. Emergency lap appendectomy done under GA. Intra-op: appendix "
            "inflamed, no perforation/rupture. Post-op course uneventful, started orally on "
            "POD1, drain removed POD2. Afebrile at discharge, wound healthy, sutures to be "
            "removed on Day 7 at follow up.",
            "Patient ko pichhle 2 din se pet mein dard tha jo right side shift ho gaya, bukhar "
            "aur ulti bhi thi. USG mein appendix inflamed dikha. Emergency laparoscopic "
            "appendectomy ki gayi GA ke under. Operation ke baad recovery achhi rahi, patient "
            "ne oral diet second din se le li, koi complication nahi hua. Discharge ke time "
            "patient stable tha, wound clean and dry, follow-up ke liye bola gaya hai.",
        ],
    },
    {
        "specialty": "internal_medicine",
        "diagnosis_text": "Dengue fever with warning signs",
        "icd_codes": ["A90"],
        "procedures": ["Serial hematocrit and platelet monitoring"],
        "medications": [
            "IV Fluids (Ringer Lactate)",
            "Tab Paracetamol 650mg SOS",
            "Inj Pantoprazole 40mg IV OD",
        ],
        "claim_band": (25000, 70000),
        "claim_types": _CLAIM_TYPES,
        "scenario_weights": dict(_DEFAULT_WEIGHTS),
        "notes": [
            "Patient presented with high-grade fever for 4 days associated with severe "
            "myalgia, retro-orbital pain and rash. Warning signs noted: persistent vomiting, "
            "abdominal pain, and postural dizziness. NS1 antigen positive on Day 2 of illness; "
            "platelet count on admission was 68,000/cumm, trending down to 32,000/cumm by Day "
            "3, with rising hematocrit suggestive of plasma leakage. Managed with aggressive "
            "IV fluid resuscitation per WHO dengue protocol, strict input-output monitoring, "
            "and serial CBC every 6 hours. Patient remained hemodynamically stable throughout, "
            "no bleeding manifestations. Platelet counts began recovering from Day 5, and "
            "patient was afebrile for 24 hours prior to discharge. Discharged in stable "
            "condition with advice for adequate hydration and follow-up CBC after 3 days.",
            "Patient ko admission ke time tez bukhar tha, platelets gir rahe the, IV fluids "
            "diye gaye. NS1 positive tha aur warning signs jaise pet dard aur baar baar ulti "
            "bhi thi. Platelet count 30,000 tak neeche gaya, isliye close monitoring ki gayi "
            "CBC har 6 ghante mein. Koi bleeding nahi hua, patient stable raha. 5th din se "
            "platelets improve hone lage aur bukhar bhi utar gaya. Discharge ke time patient "
            "stable tha, hydration maintain karne ki salah di gayi.",
            "4-day h/o high fever, myalgia, retro-orbital pain. NS1 Ag +ve. Platelet nadir "
            "32k/cumm D3, HCT rising - warning signs present. Managed as per WHO dengue "
            "protocol with IV fluids, strict I/O charting, serial platelet/HCT monitoring "
            "q6h. No bleed, no shock. Platelets recovered >100k by D6, afebrile 24h, "
            "discharged stable.",
        ],
    },
    {
        "specialty": "internal_medicine",
        "diagnosis_text": "Enteric (typhoid) fever",
        "icd_codes": ["A01.0"],
        "procedures": ["Blood culture sampling"],
        "medications": [
            "Inj Ceftriaxone 2g IV OD",
            "Tab Paracetamol 650mg SOS",
            "ORS and IV fluids",
        ],
        "claim_band": (20000, 60000),
        "claim_types": _CLAIM_TYPES,
        "scenario_weights": dict(_DEFAULT_WEIGHTS),
        "notes": [
            "Patient presented with insidious onset, step-ladder pattern fever for 8 days, "
            "associated with relative bradycardia, coated tongue, and diffuse abdominal "
            "discomfort. Blood culture sent on admission grew Salmonella Typhi, sensitive to "
            "ceftriaxone. Widal test also reactive at significant titres. Started on IV "
            "Ceftriaxone 2g OD; fever showed gradual defervescence by Day 4 of antibiotics. "
            "Patient monitored for complications including GI bleed and perforation, none "
            "noted. Tolerated soft diet well, ambulated without difficulty. Discharged "
            "afebrile with oral antibiotics to complete a 14-day course and advice on food "
            "hygiene.",
            "Patient ko 8 din se dheere dheere bukhar chadh raha tha, pet mein bhi halka dard "
            "tha. Blood culture mein Salmonella Typhi positive aaya. Ceftriaxone injection "
            "start kiya gaya IV route se. 4 din mein bukhar kam hona shuru hua. Koi "
            "complication jaise bleeding ya perforation nahi hua. Patient ne diet bhi acchi "
            "tarah li. Discharge ke time bukhar nahi tha, oral antibiotic course complete "
            "karne ki salah di gayi.",
            "C/o low-grade to high-grade fever x 8 days, step-ladder pattern, relative "
            "bradycardia noted. Blood C/S: Salmonella Typhi isolated, sensitive to "
            "ceftriaxone. Widal reactive. Rx: Inj Ceftriaxone 2g IV OD x 10 days. "
            "Defervescence by D4. No GI bleed/perforation. Discharged afebrile, advised to "
            "complete oral antibiotic course and maintain food/water hygiene.",
        ],
    },
    {
        "specialty": "cardiology",
        "diagnosis_text": "Acute myocardial infarction",
        "icd_codes": ["I21.9"],
        "procedures": ["Coronary angiography", "Primary PTCA with drug-eluting stent to LAD"],
        "medications": [
            "Tab Aspirin 150mg OD",
            "Tab Clopidogrel 75mg OD",
            "Tab Atorvastatin 80mg OD",
            "Inj Heparin as per protocol",
        ],
        "claim_band": (200000, 450000),
        "claim_types": _CLAIM_TYPES,
        "scenario_weights": dict(_DEFAULT_WEIGHTS),
        "notes": [
            "Patient presented to emergency with severe, crushing central chest pain radiating "
            "to the left arm and jaw, associated with sweating and breathlessness, of 2 hours "
            "duration. ECG showed ST-elevation in leads V1-V4 consistent with anterior wall "
            "STEMI. Troponin I was markedly elevated. Patient was taken up for emergent "
            "coronary angiography which revealed 95% thrombotic occlusion of the proximal "
            "LAD. Primary PTCA was performed with successful deployment of a drug-eluting "
            "stent, achieving TIMI III flow. Post-procedure course was uneventful, no "
            "arrhythmias or heart failure noted. Echo showed mild LV dysfunction (EF 45%). "
            "Patient started on dual antiplatelet therapy, statin, and beta-blocker, mobilized "
            "gradually, and discharged in stable condition with cardiac rehabilitation advice.",
            "Presented with acute onset central chest pain, diaphoresis, 2 hrs duration. ECG: "
            "STEMI anterior wall. Trop I markedly elevated. Emergency CAG done - 95% proximal "
            "LAD occlusion. Primary PTCA + DES to LAD, TIMI III flow achieved post-procedure. "
            "Post-PCI course uneventful, no arrhythmia. 2D-Echo: EF 45%, mild hypokinesia "
            "anterior wall. DAPT + statin + beta-blocker started. Ambulated D2, discharged "
            "stable D4 with cardiac rehab and lifestyle advice.",
        ],
    },
    {
        "specialty": "endocrinology",
        "diagnosis_text": "Type 2 diabetes mellitus with diabetic ketoacidosis",
        "icd_codes": ["E11.1"],
        "procedures": ["IV insulin infusion titration", "Arterial blood gas monitoring"],
        "medications": [
            "IV Insulin infusion (regular insulin)",
            "IV Normal Saline",
            "Inj Potassium chloride correction",
        ],
        "claim_band": (40000, 120000),
        "claim_types": _CLAIM_TYPES,
        "scenario_weights": dict(_DEFAULT_WEIGHTS),
        "notes": [
            "Known case of Type 2 diabetes mellitus presented with a 2-day history of "
            "vomiting, abdominal pain, and altered sensorium. On evaluation, blood glucose "
            "was 485 mg/dL with metabolic acidosis (pH 7.18, bicarbonate 9 mEq/L) and "
            "ketonuria 3+, confirming diabetic ketoacidosis. Managed in ICU with IV insulin "
            "infusion as per protocol, aggressive fluid resuscitation, and potassium "
            "correction with hourly monitoring of blood glucose and electrolytes. "
            "Precipitating cause identified as poor drug compliance with an intercurrent UTI. "
            "Acidosis corrected by 36 hours, patient transitioned to subcutaneous insulin, "
            "sensorium improved fully. Discharged in stable condition on a basal-bolus "
            "insulin regimen with diabetes education and follow-up advice.",
            "Patient ko pehle se sugar (diabetes) tha, 2 din se ulti aur pet dard ho raha tha "
            "aur hosh bhi thoda kam tha. Blood sugar bahut zyada tha (485) aur DKA confirm "
            "hua blood test se. ICU mein IV insulin drip start ki gayi, saath mein fluids aur "
            "potassium bhi diya gaya. Dhire dhire sugar aur acidosis control hua, 36 ghante "
            "mein patient normal hone laga. Discharge ke time patient poori tarah hosh mein "
            "tha, insulin injection lene ki salah di gayi ghar par.",
            "T2DM x 6 yrs, presented c/o vomiting, abdominal pain, altered sensorium x 2 "
            "days. RBS 485 mg/dL, ABG: pH 7.18, HCO3 9, ketonuria 3+ - DKA. Precipitant: UTI "
            "+ non-compliance. ICU care: IV insulin infusion, fluid resuscitation, K+ "
            "correction, hourly glucose monitoring. Acidosis resolved by 36h, switched to SC "
            "basal-bolus insulin. Sensorium normalized. Discharged stable, diabetes education "
            "given, follow-up in endocrinology OPD advised.",
        ],
    },
    {
        "specialty": "ophthalmology",
        "diagnosis_text": "Senile cataract",
        "icd_codes": ["H25.9"],
        "procedures": ["Phacoemulsification with IOL implantation"],
        "medications": [
            "Eye drops - Moxifloxacin 0.5%",
            "Eye drops - Prednisolone acetate 1%",
            "Eye drops - Ketorolac 0.5%",
        ],
        "claim_band": (20000, 45000),
        "claim_types": _CLAIM_TYPES,
        "scenario_weights": dict(_DEFAULT_WEIGHTS),
        "notes": [
            "Patient presented with progressive, painless diminution of vision in the right "
            "eye over 6 months, more pronounced for near work and in bright light, consistent "
            "with senile cataract. Best corrected visual acuity was 6/36 in the right eye. "
            "Slit-lamp examination confirmed nuclear sclerosis grade III cataract. Patient "
            "underwent uneventful phacoemulsification with foldable IOL implantation under "
            "topical anaesthesia. Intraoperative course was uncomplicated with good capsular "
            "bag stability. Post-operatively, vision improved to 6/9 on Day 1. Patient "
            "discharged the same day with topical antibiotic-steroid combination eye drops "
            "and advised to avoid water contact and strenuous activity for 2 weeks, with "
            "follow-up on Day 7.",
            "C/o gradual painless diminution of vision, right eye, x 6 months. BCVA 6/36 RE. "
            "Slit lamp: NS grade III cataract. Underwent phacoemulsification with foldable "
            "IOL implantation under topical anaesthesia, day-care procedure. Intra-op "
            "uneventful. POD1 vision 6/9, cornea clear, IOL well centered. Discharged same "
            "day on topical antibiotic-steroid-NSAID combination, F/U on Day 7 and Day 30.",
        ],
    },
    {
        "specialty": "general_surgery",
        "diagnosis_text": "Inguinal hernia",
        "icd_codes": ["K40.9"],
        "procedures": ["Open inguinal hernioplasty with mesh (Lichtenstein repair)"],
        "medications": [
            "Inj Ceftriaxone 1g IV OD",
            "Tab Diclofenac 50mg BD",
            "Tab Paracetamol 650mg SOS",
        ],
        "claim_band": (35000, 80000),
        "claim_types": _CLAIM_TYPES,
        "scenario_weights": dict(_DEFAULT_WEIGHTS),
        "notes": [
            "Patient presented with a gradually increasing right groin swelling of 8 months "
            "duration, reducible on lying down, associated with occasional dragging "
            "discomfort, more pronounced on straining and coughing. Clinical examination "
            "confirmed a reducible right inguinal hernia with a positive cough impulse. "
            "Patient underwent elective open inguinal hernioplasty with mesh placement "
            "(Lichtenstein technique) under spinal anaesthesia. Intraoperative findings "
            "showed an indirect inguinal hernia with intact bowel loops, no signs of "
            "strangulation. Mesh was placed without tension, and the procedure was completed "
            "uneventfully. Post-operative recovery was smooth, patient ambulated the same "
            "evening, pain well controlled with oral analgesics, and was discharged the "
            "following day with wound care and activity restriction advice.",
            "8-month h/o reducible right groin swelling, worse on straining, cough impulse "
            "+ve. Dx: right indirect inguinal hernia. Elective open hernioplasty with mesh "
            "(Lichtenstein) under SA. Intra-op: indirect sac, bowel viable, no "
            "strangulation. Mesh placed tension-free. Post-op pain controlled with oral "
            "analgesics, ambulated same evening, wound clean. Discharged POD1, advised to "
            "avoid heavy lifting for 6 weeks, suture removal Day 10.",
        ],
    },
    {
        "specialty": "pulmonology",
        "diagnosis_text": "Community-acquired pneumonia",
        "icd_codes": ["J18.9"],
        "procedures": ["Oxygen supplementation via nasal cannula", "Chest physiotherapy"],
        "medications": [
            "Inj Ceftriaxone 1g IV BD",
            "Inj Azithromycin 500mg IV OD",
            "Nebulization with Salbutamol/Ipratropium",
            "Tab Paracetamol 650mg SOS",
        ],
        "claim_band": (30000, 90000),
        "claim_types": _CLAIM_TYPES,
        "scenario_weights": dict(_DEFAULT_WEIGHTS),
        "notes": [
            "Patient presented with a 5-day history of fever, productive cough with yellowish "
            "sputum, and progressive breathlessness. On examination, SpO2 was 90% on room "
            "air, with coarse crepitations over the right lower lung zone. Chest X-ray showed "
            "right lower lobe consolidation, confirming community-acquired pneumonia. "
            "CURB-65 score of 2 warranted inpatient management. Patient started on IV "
            "antibiotics (ceftriaxone and azithromycin) as per hospital protocol, "
            "supplemental oxygen via nasal cannula, and nebulization. SpO2 improved to 96% "
            "on room air by Day 3, fever settled, and cough reduced significantly. Repeat "
            "chest examination showed resolving crepitations. Patient was weaned off oxygen "
            "and discharged in stable condition on oral antibiotics to complete a 7-day "
            "course.",
            "5-day h/o fever, productive cough, breathlessness. SpO2 90% RA, coarse crepts "
            "RLL. CXR: RLL consolidation. CURB-65 = 2, admitted. IV Ceftriaxone + "
            "Azithromycin, O2 via NC, nebulization started. D3: SpO2 96% RA, afebrile, cough "
            "improving. Weaned off O2 by D4. Discharged stable on oral antibiotics, advised "
            "follow-up CXR after 2 weeks.",
        ],
    },
    {
        "specialty": "neurology",
        "diagnosis_text": "Cerebral infarction (acute ischemic stroke)",
        "icd_codes": ["I63.9"],
        "procedures": ["CT brain plain", "IV thrombolysis with alteplase"],
        "medications": [
            "Inj Alteplase (rtPA)",
            "Tab Aspirin 150mg OD",
            "Tab Atorvastatin 40mg OD",
            "Tab Clopidogrel 75mg OD",
        ],
        "claim_band": (150000, 350000),
        "claim_types": _CLAIM_TYPES,
        "scenario_weights": dict(_DEFAULT_WEIGHTS),
        "notes": [
            "Patient was brought to emergency within 2 hours of sudden onset left-sided "
            "weakness and slurring of speech. NIHSS score on admission was 12. Non-contrast "
            "CT brain ruled out haemorrhage; clinical picture consistent with acute ischemic "
            "stroke in the right MCA territory. Patient was within the thrombolysis window "
            "and, after ruling out contraindications, was administered IV alteplase. "
            "Post-thrombolysis, patient showed partial improvement in power of the left upper "
            "and lower limb. Monitored in the stroke unit for 24 hours with no hemorrhagic "
            "transformation on repeat CT. Started on dual antiplatelet therapy and statin "
            "after 24 hours, underwent physiotherapy, and was discharged with residual mild "
            "left-sided weakness, advised for continued physiotherapy and follow-up.",
            "Patient ko achanak se left side mein kamzori aa gayi thi aur baat karne mein bhi "
            "dikkat ho rahi thi, isliye 2 ghante ke andar hospital laya gaya. CT scan mein "
            "bleeding nahi tha, stroke confirm hua right side ke brain mein. Time window ke "
            "andar hone ki wajah se clot dissolve karne ki dawa (alteplase) di gayi. Uske "
            "baad thodi improvement dikhi left haath aur pair mein. 24 ghante stroke unit "
            "mein observation mein rakha gaya, koi bleeding nahi hua dobara scan mein. "
            "Physiotherapy shuru ki gayi, discharge ke time halki kamzori baaki thi left "
            "side mein, ghar par physiotherapy jari rakhne ki salah di gayi.",
            "Acute onset L-sided weakness + slurred speech, onset-to-door 2h. NIHSS 12 on "
            "admission. NCCT brain: no bleed. Dx: acute ischemic stroke, R MCA territory. "
            "Within thrombolysis window, no contraindications - IV alteplase given. Partial "
            "improvement in L limb power post-lysis. Stroke unit monitoring 24h, repeat CT: "
            "no hemorrhagic transformation. DAPT + statin started at 24h. PT initiated. "
            "Discharged with residual mild L hemiparesis, OPD f/u and continued "
            "physiotherapy advised.",
        ],
    },
    {
        "specialty": "orthopedics",
        "diagnosis_text": "Fracture neck of femur",
        "icd_codes": ["S72.0"],
        "procedures": ["Bipolar hemiarthroplasty"],
        "medications": [
            "Inj Cefuroxime 1.5g IV BD",
            "Inj Enoxaparin 40mg SC OD",
            "Tab Paracetamol 650mg TID",
        ],
        "claim_band": (180000, 350000),
        "claim_types": _CLAIM_TYPES,
        "scenario_weights": dict(_DEFAULT_WEIGHTS),
        "notes": [
            "Elderly patient sustained a fall at home resulting in inability to bear weight "
            "on the right lower limb, with the limb held in a shortened and externally "
            "rotated position. X-ray pelvis with both hips confirmed a displaced fracture "
            "neck of right femur. Given the patient's age and fracture pattern, bipolar "
            "hemiarthroplasty was planned and performed under spinal anaesthesia. "
            "Intraoperative course was uneventful with good prosthesis fixation. "
            "Post-operative course included DVT prophylaxis with low-molecular-weight "
            "heparin, early mobilization with walker support from Day 2, and physiotherapy. "
            "Wound healed well with no signs of infection. Patient was discharged ambulant "
            "with walker assistance, advised on hip precautions and continued physiotherapy.",
            "Patient ghar par gir gaye the, uske baad se right leg par weight nahi daal pa "
            "rahe the aur leg thodi chhoti aur bahar ki taraf mudi hui lag rahi thi. X-ray "
            "mein hip ki fracture confirm hui. Operation kiya gaya (hemiarthroplasty) spinal "
            "anesthesia ke under. Operation acche se hua, koi dikkat nahi hui. Blood clot na "
            "bane isliye injection diya gaya roz. Doosre din se walker ki madad se chalna "
            "shuru karaya gaya. Discharge ke time patient walker se chal pa rahe the, ghar "
            "par precautions batayi gayi hain.",
            "H/o fall at home, unable to bear weight on R lower limb, limb shortened + "
            "externally rotated. X-ray pelvis/hip: displaced # neck of femur (R). Planned "
            "bipolar hemiarthroplasty under SA - uneventful, good prosthesis seating. "
            "Post-op: LMWH DVT prophylaxis, early mobilization with walker from D2, "
            "physiotherapy. Wound healthy, afebrile. Discharged ambulant with walker, hip "
            "precautions and OPD physiotherapy advised.",
        ],
    },
    {
        "specialty": "general_surgery",
        "diagnosis_text": "Cholelithiasis (gallstones) with chronic cholecystitis",
        "icd_codes": ["K80.2"],
        "procedures": ["Laparoscopic cholecystectomy"],
        "medications": [
            "Inj Ceftriaxone 1g IV OD",
            "Inj Pantoprazole 40mg IV OD",
            "Tab Paracetamol 650mg SOS",
        ],
        "claim_band": (45000, 95000),
        "claim_types": _CLAIM_TYPES,
        "scenario_weights": dict(_DEFAULT_WEIGHTS),
        "notes": [
            "Patient presented with recurrent episodes of right upper quadrant pain over the "
            "past 3 months, colicky in nature, associated with fatty food intolerance and "
            "occasional nausea. Ultrasound abdomen revealed multiple gallstones with a "
            "thickened gallbladder wall, consistent with chronic calculous cholecystitis. "
            "Liver function tests were within normal limits. Patient underwent elective "
            "laparoscopic cholecystectomy under general anaesthesia. Intraoperative findings "
            "showed a chronically inflamed gallbladder with multiple stones, dissected "
            "without difficulty, Calot's triangle clearly delineated, no bile duct injury. "
            "Post-operative recovery was smooth, patient started on oral fluids within 6 "
            "hours, ambulated the same evening. Discharged Day 1 post-surgery in stable "
            "condition with dietary advice and follow-up.",
            "3-month h/o recurrent colicky RUQ pain, fatty food intolerance. USG abdomen: "
            "multiple gallstones, GB wall thickened - chronic calculous cholecystitis. LFTs "
            "WNL. Elective lap cholecystectomy under GA. Intra-op: chronically inflamed GB, "
            "Calot's triangle well delineated, CBD not injured, specimen retrieved intact. "
            "Smooth post-op course, oral fluids started 6h post-op, ambulated same evening. "
            "Discharged POD1, low-fat diet and wound care advice given.",
        ],
    },
    {
        "specialty": "obstetrics",
        "diagnosis_text": "Delivery by emergency lower segment caesarean section",
        "icd_codes": ["O82"],
        "procedures": ["Emergency lower segment caesarean section"],
        "medications": [
            "Inj Ceftriaxone 1g IV OD",
            "Inj Oxytocin as per protocol",
            "Tab Paracetamol 650mg TID",
        ],
        "claim_band": (45000, 110000),
        "claim_types": _CLAIM_TYPES,
        "scenario_weights": dict(_DEFAULT_WEIGHTS),
        "notes": [
            "Primigravida at 39 weeks of gestation was admitted in early labour. Labour was "
            "augmented, however cardiotocography showed recurrent late decelerations with "
            "fetal heart rate in the range of 100-110 bpm, suggestive of fetal distress. In "
            "view of non-reassuring fetal status and failure to progress, decision for "
            "emergency lower segment caesarean section was taken. A live female baby was "
            "delivered with good Apgar scores, no immediate resuscitation required. "
            "Intraoperative blood loss was within normal limits, uterus well contracted. "
            "Post-operative course was uneventful, patient ambulated on Day 1, breastfeeding "
            "established, and was discharged on Day 3 in stable condition along with the "
            "neonate, with advice on wound care and postnatal follow-up.",
            "Pehli baar pregnant patient 39 weeks mein labour ke liye admit hui thi. Labour "
            "ke dauran baby ki heart rate girne lagi thi (fetal distress ke signs the), "
            "isliye emergency operation (LSCS) karne ka decision liya gaya. Ek healthy baby "
            "girl delivery hui, achhi condition mein thi turant. Operation ke dauran zyada "
            "bleeding nahi hui, uterus theek se contract hua. Maa aur baby dono ki recovery "
            "achhi rahi, breastfeeding bhi shuru ho gayi. Discharge teesre din kiya gaya "
            "dono stable condition mein, wound care aur follow up ki salah di gayi.",
            "Primi, 39 wks POG, admitted in early labour. Labour augmented; CTG showed "
            "recurrent late decelerations, FHR 100-110 bpm - fetal distress. Non-reassuring "
            "NST + failure to progress -> emergency LSCS. Live female baby delivered, good "
            "Apgar, no resuscitation needed. EBL within normal limits, uterus well contracted "
            "post-delivery. Uneventful post-op course, ambulated D1, breastfeeding "
            "established. Mother-baby dyad discharged D3, stable, postnatal f/u and wound "
            "care advised.",
        ],
    },
]
