import csv
import io
import os
import re
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ============================================================
# CONFIGURATION GLOBALE
# ============================================================
st.set_page_config(
    page_title="Diagnostic profil investisseur",
    page_icon="📊",
    layout="centered",
)

LEADS_FILE = "leads_profil_investisseur_premium.csv"
SCORE_MAP = {"a": 1, "b": 2, "c": 3, "d": 4}
DIMENSIONS = [
    "Horizon",
    "Tolérance au risque",
    "Capacité financière",
    "Connaissances",
    "Objectifs",
]


# ============================================================
# QUESTIONS PREMIUM - VERSION MIF2 LIGHT
# - chaque question a une dimension et un poids
# - la logique reste simple pour un lead magnet, mais plus robuste
# ============================================================
QUESTIONS: List[Dict[str, Any]] = [
    # 1) Situation financière et capacité de perte
    {
        "id": 1,
        "section": "Situation financière",
        "dimension": "Capacité financière",
        "weight": 2.0,
        "question": "Quelle part de votre patrimoine financier pouvez-vous immobiliser sur le long terme ?",
        "options": {
            "a": "Moins de 10%",
            "b": "Entre 10% et 30%",
            "c": "Entre 30% et 60%",
            "d": "Plus de 60%",
        },
    },
    {
        "id": 2,
        "section": "Situation financière",
        "dimension": "Capacité financière",
        "weight": 2.0,
        "question": "Comment qualifieriez-vous la stabilité de vos revenus ?",
        "options": {
            "a": "Très instables ou irréguliers",
            "b": "Assez variables",
            "c": "Plutôt stables",
            "d": "Très stables et prévisibles",
        },
    },
    {
        "id": 3,
        "section": "Situation financière",
        "dimension": "Capacité financière",
        "weight": 2.0,
        "question": "De combien de mois de dépenses courantes disposez-vous en épargne de précaution ?",
        "options": {
            "a": "Moins de 3 mois",
            "b": "Entre 3 et 6 mois",
            "c": "Entre 6 et 12 mois",
            "d": "Plus de 12 mois",
        },
    },
    {
        "id": 4,
        "section": "Situation financière",
        "dimension": "Capacité financière",
        "weight": 2.0,
        "question": "Quel est votre niveau d'endettement par rapport à vos revenus ?",
        "options": {
            "a": "Élevé",
            "b": "Modéré",
            "c": "Faible",
            "d": "Très faible ou nul",
        },
    },
    {
        "id": 5,
        "section": "Situation financière",
        "dimension": "Capacité financière",
        "weight": 3.0,
        "question": "Si votre portefeuille baissait de 20%, quel serait l'impact sur votre situation personnelle ?",
        "options": {
            "a": "Impact sérieux, je devrais revoir mes projets",
            "b": "Impact sensible mais gérable",
            "c": "Impact limité",
            "d": "Impact faible ou nul",
        },
    },
    # 2) Horizon d'investissement
    {
        "id": 6,
        "section": "Horizon d'investissement",
        "dimension": "Horizon",
        "weight": 2.0,
        "question": "Dans combien de temps pensez-vous avoir besoin de la majeure partie de ce capital ?",
        "options": {
            "a": "Moins de 3 ans",
            "b": "Entre 3 et 5 ans",
            "c": "Entre 5 et 10 ans",
            "d": "Plus de 10 ans",
        },
    },
    {
        "id": 7,
        "section": "Horizon d'investissement",
        "dimension": "Horizon",
        "weight": 2.0,
        "question": "Quel est votre horizon idéal pour construire votre patrimoine financier ?",
        "options": {
            "a": "Court terme",
            "b": "Moyen terme",
            "c": "Long terme",
            "d": "Très long terme",
        },
    },
    {
        "id": 8,
        "section": "Horizon d'investissement",
        "dimension": "Objectifs",
        "weight": 1.5,
        "question": "Quel est votre objectif principal aujourd'hui ?",
        "options": {
            "a": "Préserver mon capital",
            "b": "Compléter mes revenus",
            "c": "Préparer un projet long terme ou la retraite",
            "d": "Accélérer fortement la croissance de mon patrimoine",
        },
    },
    # 3) Réaction aux baisses et tolérance émotionnelle
    {
        "id": 9,
        "section": "Tolérance au risque",
        "dimension": "Tolérance au risque",
        "weight": 2.0,
        "question": "Si votre portefeuille baissait de 10%, quelle serait votre réaction ?",
        "options": {
            "a": "Je vendrais rapidement",
            "b": "Je serais très inquiet",
            "c": "Je conserverais mes positions",
            "d": "J'en profiterais pour renforcer",
        },
    },
    {
        "id": 10,
        "section": "Tolérance au risque",
        "dimension": "Tolérance au risque",
        "weight": 3.0,
        "question": "Quelle perte temporaire maximale pensez-vous pouvoir accepter sans changer de stratégie ?",
        "options": {
            "a": "5% maximum",
            "b": "10% environ",
            "c": "20% environ",
            "d": "30% ou plus",
        },
    },
    {
        "id": 11,
        "section": "Tolérance au risque",
        "dimension": "Tolérance au risque",
        "weight": 2.0,
        "question": "Lors d'un krach boursier majeur, vous auriez tendance à :",
        "options": {
            "a": "Sortir du marché",
            "b": "Réduire le risque",
            "c": "Attendre avec discipline",
            "d": "Acheter progressivement",
        },
    },
    {
        "id": 12,
        "section": "Tolérance au risque",
        "dimension": "Tolérance au risque",
        "weight": 2.0,
        "question": "Quel niveau de volatilité vous semble acceptable ?",
        "options": {
            "a": "Faible, je privilégie la stabilité",
            "b": "Modéré",
            "c": "Élevé si le potentiel de rendement est supérieur",
            "d": "Très élevé, je comprends les cycles longs",
        },
    },
    {
        "id": 13,
        "section": "Tolérance au risque",
        "dimension": "Tolérance au risque",
        "weight": 2.0,
        "question": "Face à des pertes temporaires, vous vous décririez comme :",
        "options": {
            "a": "Très sensible émotionnellement",
            "b": "Prudent et inconfortable",
            "c": "Patient et rationnel",
            "d": "Opportuniste et détaché",
        },
    },
    # 4) Connaissances et expérience
    {
        "id": 14,
        "section": "Connaissances",
        "dimension": "Connaissances",
        "weight": 1.0,
        "question": "Quel est votre niveau d'expérience en investissement ?",
        "options": {
            "a": "Débutant complet",
            "b": "Quelques notions",
            "c": "Intermédiaire",
            "d": "Avancé",
        },
    },
    {
        "id": 15,
        "section": "Connaissances",
        "dimension": "Connaissances",
        "weight": 1.0,
        "question": "Votre connaissance des ETF est :",
        "options": {
            "a": "Nulle",
            "b": "Basique",
            "c": "Correcte",
            "d": "Bonne ou opérationnelle",
        },
    },
    {
        "id": 16,
        "section": "Connaissances",
        "dimension": "Connaissances",
        "weight": 1.0,
        "question": "À quelle fréquence suivez-vous vos placements ou les marchés ?",
        "options": {
            "a": "Rarement",
            "b": "Occasionnellement",
            "c": "Régulièrement",
            "d": "Très souvent",
        },
    },
    {
        "id": 17,
        "section": "Connaissances",
        "dimension": "Connaissances",
        "weight": 1.0,
        "question": "Quels supports avez-vous déjà utilisés ?",
        "options": {
            "a": "Livrets ou fonds euros uniquement",
            "b": "Assurance-vie diversifiée",
            "c": "ETF, OPCVM ou actions",
            "d": "Portefeuille actions/ETF structuré et suivi",
        },
    },
    # 5) Construction de portefeuille et préférences
    {
        "id": 18,
        "section": "Allocation souhaitée",
        "dimension": "Objectifs",
        "weight": 1.5,
        "question": "Quel portefeuille vous semble le plus adapté à votre personnalité ?",
        "options": {
            "a": "80% sécuritaire / 20% actions",
            "b": "60% diversifié / 40% défensif",
            "c": "70% actions / 30% stabilisateurs",
            "d": "90% à 100% actions",
        },
    },
    {
        "id": 19,
        "section": "Allocation souhaitée",
        "dimension": "Objectifs",
        "weight": 1.5,
        "question": "Votre priorité d'investissement est :",
        "options": {
            "a": "Sécuriser le capital",
            "b": "Stabiliser la performance",
            "c": "Faire croître le capital",
            "d": "Maximiser la performance potentielle",
        },
    },
    {
        "id": 20,
        "section": "Allocation souhaitée",
        "dimension": "Objectifs",
        "weight": 1.0,
        "question": "L'idée d'investir chaque mois vous semble :",
        "options": {
            "a": "Stressante",
            "b": "Peu naturelle",
            "c": "Rassurante",
            "d": "Très motivante",
        },
    },
    # 6) Objectifs patrimoniaux
    {
        "id": 21,
        "section": "Objectifs patrimoniaux",
        "dimension": "Objectifs",
        "weight": 1.5,
        "question": "Quel résultat attendez-vous principalement de votre stratégie d'investissement ?",
        "options": {
            "a": "Préserver mon niveau de sécurité financière",
            "b": "Créer un complément de revenu",
            "c": "Préparer ma retraite sereinement",
            "d": "Construire un patrimoine élevé à long terme",
        },
    },
    {
        "id": 22,
        "section": "Objectifs patrimoniaux",
        "dimension": "Objectifs",
        "weight": 1.5,
        "question": "Votre vision de l'investissement est la plus proche de :",
        "options": {
            "a": "La sécurité avant tout",
            "b": "L'équilibre entre risque et rendement",
            "c": "La croissance régulière du patrimoine",
            "d": "La maximisation du rendement long terme",
        },
    },
    # 7) Contrôles de cohérence - MIF2 light
    {
        "id": 23,
        "section": "Cohérence du profil",
        "dimension": "Horizon",
        "weight": 2.0,
        "question": "Si un projet important dépend de ce capital dans moins de 3 ans, vous accepteriez quand même une forte exposition actions.",
        "options": {
            "a": "Pas du tout",
            "b": "Plutôt non",
            "c": "Pourquoi pas en partie",
            "d": "Oui, sans problème",
        },
    },
    {
        "id": 24,
        "section": "Cohérence du profil",
        "dimension": "Tolérance au risque",
        "weight": 2.0,
        "question": "Si votre portefeuille chutait fortement pendant 12 mois, votre discipline d'investissement resterait :",
        "options": {
            "a": "Très difficile à maintenir",
            "b": "Fragile",
            "c": "Plutôt stable",
            "d": "Très stable",
        },
    },
    {
        "id": 25,
        "section": "Cohérence du profil",
        "dimension": "Capacité financière",
        "weight": 2.5,
        "question": "Avant d'investir, votre niveau de sécurité financière personnelle est :",
        "options": {
            "a": "Insuffisant à ce stade",
            "b": "Encore limité",
            "c": "Globalement correct",
            "d": "Solide",
        },
    },
]

PROFILE_BANDS: List[Dict[str, Any]] = [
    {
        "name": "Très prudent",
        "min_score": 0,
        "max_score": 34,
        "risk_level": "Très faible",
        "subtitle": "Votre priorité est la sécurité du capital et la réduction maximale des fluctuations.",
        "allocation": [
            ("Monétaire / fonds euros / obligataire court terme", 70),
            ("Obligations diversifiées", 20),
            ("Actions diversifiées", 10),
        ],
        "volatility": "Faible. Une baisse de -5% à -10% peut déjà être inconfortable.",
        "horizon": "0 à 5 ans",
        "pitch": "Une stratégie défensive, très lisible, avec forte poche de sécurité.",
    },
    {
        "name": "Prudent",
        "min_score": 35,
        "max_score": 49,
        "risk_level": "Faible à modéré",
        "subtitle": "Vous acceptez une part mesurée de risque si elle reste strictement encadrée.",
        "allocation": [
            ("Supports sécuritaires / obligataires", 55),
            ("Actions monde de qualité", 30),
            ("Actifs réels / diversification", 15),
        ],
        "volatility": "Modérée. Une baisse de -10% à -15% reste sensible.",
        "horizon": "3 à 7 ans",
        "pitch": "Une allocation de transition entre sécurité, revenus et croissance progressive.",
    },
    {
        "name": "Équilibré",
        "min_score": 50,
        "max_score": 64,
        "risk_level": "Modéré",
        "subtitle": "Vous recherchez un bon compromis entre croissance du capital et maîtrise du risque.",
        "allocation": [
            ("Actions diversifiées", 55),
            ("Obligations / supports stabilisateurs", 30),
            ("Diversification complémentaire", 15),
        ],
        "volatility": "Intermédiaire. Une baisse de -15% à -20% reste possible sur un cycle de marché.",
        "horizon": "5 à 10 ans",
        "pitch": "Une allocation robuste, diversifiée et cohérente pour une progression régulière.",
    },
    {
        "name": "Dynamique",
        "min_score": 65,
        "max_score": 79,
        "risk_level": "Élevé",
        "subtitle": "Vous êtes orienté croissance et acceptez les cycles de marché pour viser plus de performance.",
        "allocation": [
            ("Actions monde / thématiques", 75),
            ("Obligations / défensif", 10),
            ("Diversification", 15),
        ],
        "volatility": "Élevée. Des baisses de -20% à -30% doivent être anticipées.",
        "horizon": "8 à 12 ans",
        "pitch": "Une stratégie de croissance long terme, exigeante mais structurée.",
    },
    {
        "name": "Offensif",
        "min_score": 80,
        "max_score": 100,
        "risk_level": "Très élevé",
        "subtitle": "Vous privilégiez la performance long terme et acceptez une forte volatilité.",
        "allocation": [
            ("Actions diversifiées", 85),
            ("Satellite opportuniste", 10),
            ("Poche de stabilisation", 5),
        ],
        "volatility": "Très élevée. Les drawdowns peuvent être profonds et prolongés.",
        "horizon": "10 ans et plus",
        "pitch": "Une allocation offensive réservée à des profils préparés, stables et disciplinés.",
    },
]


# ============================================================
# FONCTIONS MÉTIER
# ============================================================
def is_valid_email(email: str) -> bool:
    """Validation simple mais plus propre qu'un simple test de présence du @."""
    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    return bool(re.match(pattern, email.strip()))


def get_question_by_id(question_id: int) -> Dict[str, Any]:
    return next(q for q in QUESTIONS if q["id"] == question_id)


def calculate_weighted_score(answers: Dict[int, str]) -> Tuple[float, float, float]:
    """Retourne:
    - raw_weighted_score: score pondéré constaté
    - normalized_score: score global ramené sur 100
    - max_weighted_score: score pondéré maximum
    """
    raw_weighted_score = 0.0
    max_weighted_score = 0.0

    for q in QUESTIONS:
        answer = answers.get(q["id"], "")
        raw_weighted_score += SCORE_MAP.get(answer, 0) * q["weight"]
        max_weighted_score += 4 * q["weight"]

    min_weighted_score = sum(1 * q["weight"] for q in QUESTIONS)
    normalized_score = ((raw_weighted_score - min_weighted_score) / (max_weighted_score - min_weighted_score)) * 100
    return raw_weighted_score, round(normalized_score, 1), max_weighted_score


def calculate_dimension_scores(answers: Dict[int, str]) -> Dict[str, float]:
    dimension_totals: Dict[str, float] = {dimension: 0.0 for dimension in DIMENSIONS}
    dimension_weights: Dict[str, float] = {dimension: 0.0 for dimension in DIMENSIONS}

    for q in QUESTIONS:
        dimension = q["dimension"]
        weight = q["weight"]
        answer_score = SCORE_MAP.get(answers.get(q["id"], ""), 0)
        dimension_totals[dimension] += answer_score * weight
        dimension_weights[dimension] += weight

    scores: Dict[str, float] = {}
    for dimension in DIMENSIONS:
        min_score = 1 * dimension_weights[dimension]
        max_score = 4 * dimension_weights[dimension]
        normalized = ((dimension_totals[dimension] - min_score) / (max_score - min_score)) * 100 if max_score > min_score else 0
        scores[dimension] = round(normalized, 1)
    return scores


def get_profile(normalized_score: float) -> Dict[str, Any]:
    for band in PROFILE_BANDS:
        if band["min_score"] <= normalized_score <= band["max_score"]:
            return band
    return PROFILE_BANDS[-1]


def build_consistency_flags(answers: Dict[int, str], dimension_scores: Dict[str, float]) -> List[str]:
    """Version MIF2 light : génère des alertes de cohérence sans prétendre remplacer un questionnaire réglementaire."""
    flags: List[str] = []

    horizon_short = answers.get(6) in {"a", "b"}
    wants_aggressive = answers.get(18) == "d" or answers.get(19) == "d" or dimension_scores["Tolérance au risque"] >= 75
    low_fin_capacity = dimension_scores["Capacité financière"] < 45
    low_knowledge = dimension_scores["Connaissances"] < 35
    low_discipline = answers.get(24) in {"a", "b"}

    if horizon_short and wants_aggressive:
        flags.append("Horizon plutôt court mais appétence élevée pour les actifs risqués : arbitrage à sécuriser.")
    if low_fin_capacity and wants_aggressive:
        flags.append("Tolérance déclarée au risque supérieure à la capacité financière réelle : prudence recommandée.")
    if low_knowledge and dimension_scores["Tolérance au risque"] >= 65:
        flags.append("Niveau de connaissance encore limité pour le niveau de risque visé : accompagnement conseillé.")
    if low_discipline and dimension_scores["Tolérance au risque"] >= 65:
        flags.append("Appétence au risque correcte, mais discipline déclarée fragile en cas de baisse prolongée.")
    if answers.get(25) in {"a", "b"}:
        flags.append("Niveau de sécurité financière personnelle encore limité avant mise en risque élevée du capital.")

    return flags


def get_marketing_summary(profile: Dict[str, Any], dimension_scores: Dict[str, float], flags: List[str]) -> str:
    main_strength = max(dimension_scores, key=dimension_scores.get)
    weakest_area = min(dimension_scores, key=dimension_scores.get)

    summary = (
        f"Votre profil ressort comme {profile['name'].lower()}, avec un point fort sur « {main_strength.lower()} » "
        f"et une vigilance particulière sur « {weakest_area.lower()} ». "
        f"La stratégie pertinente consiste à aligner horizon, capacité financière et niveau de volatilité réellement supportable."
    )
    if flags:
        summary += " Une ou plusieurs zones de cohérence méritent d'être clarifiées avant toute allocation plus offensive."
    return summary


def save_lead(
    name: str,
    email: str,
    normalized_score: float,
    profile_name: str,
    dimension_scores: Dict[str, float],
    answers: Dict[int, str],
) -> None:
    file_exists = os.path.exists(LEADS_FILE)

    fieldnames = [
        "timestamp",
        "name",
        "email",
        "score_100",
        "profile",
        "horizon_score",
        "risk_score",
        "financial_score",
        "knowledge_score",
        "objectives_score",
    ] + [f"Q{i}" for i in range(1, len(QUESTIONS) + 1)]

    row = {
        "timestamp": datetime.utcnow().isoformat(),
        "name": name.strip(),
        "email": email.strip().lower(),
        "score_100": normalized_score,
        "profile": profile_name,
        "horizon_score": dimension_scores["Horizon"],
        "risk_score": dimension_scores["Tolérance au risque"],
        "financial_score": dimension_scores["Capacité financière"],
        "knowledge_score": dimension_scores["Connaissances"],
        "objectives_score": dimension_scores["Objectifs"],
    }
    for q in QUESTIONS:
        row[f"Q{q['id']}"] = answers.get(q["id"], "")

    with open(LEADS_FILE, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def create_radar_chart(dimension_scores: Dict[str, float]) -> bytes:
    labels = list(dimension_scores.keys())
    values = list(dimension_scores.values())

    # Radar chart: le premier point est répété pour fermer la forme
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    values += values[:1]
    angles += angles[:1]

    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(111, polar=True)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 100)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"])
    ax.plot(angles, values, linewidth=2)
    ax.fill(angles, values, alpha=0.20)
    ax.set_title("Profil dimensionnel", pad=20)

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def generate_pdf_report(
    profile: Dict[str, Any],
    normalized_score: float,
    dimension_scores: Dict[str, float],
    flags: List[str],
    chart_bytes: bytes,
    marketing_summary: str,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.7 * cm,
        rightMargin=1.7 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="SmallBody",
            parent=styles["BodyText"],
            fontSize=9,
            leading=13,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#1F2937"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="CardTitle",
            parent=styles["Heading2"],
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=8,
        )
    )

    story: List[Any] = []
    story.append(Paragraph("Diagnostic profil investisseur - version premium", styles["Title"]))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(f"Client : <b>{name}</b> - Email : <b>{email}</b>", styles["BodyText"]))
    story.append(Paragraph(f"Date : <b>{datetime.now().strftime('%d/%m/%Y %H:%M')}</b>", styles["BodyText"]))
    story.append(Spacer(1, 0.35 * cm))

    header_table = Table(
        [
            ["Profil", profile["name"], "Score global", f"{normalized_score} / 100"],
            ["Niveau de risque", profile["risk_level"], "Horizon cohérent", profile["horizon"]],
        ],
        colWidths=[3.0 * cm, 5.2 * cm, 3.3 * cm, 5.0 * cm],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 0.35 * cm))

    story.append(Paragraph("Synthèse exécutive", styles["CardTitle"]))
    story.append(Paragraph(profile["subtitle"], styles["BodyText"]))
    story.append(Paragraph(marketing_summary, styles["BodyText"]))
    story.append(Paragraph(profile["pitch"], styles["BodyText"]))
    story.append(Spacer(1, 0.3 * cm))

    dim_rows = [["Dimension", "Score / 100"]] + [[k, f"{v}"] for k, v in dimension_scores.items()]
    dim_table = Table(dim_rows, colWidths=[8.8 * cm, 3.2 * cm])
    dim_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
                ("ALIGN", (1, 1), (1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(Paragraph("Lecture dimensionnelle", styles["CardTitle"]))
    story.append(dim_table)
    story.append(Spacer(1, 0.3 * cm))

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_chart:
        tmp_chart.write(chart_bytes)
        tmp_chart_path = tmp_chart.name

    story.append(Paragraph("Graphique profil", styles["CardTitle"]))
    story.append(Image(tmp_chart_path, width=11.5 * cm, height=11.5 * cm))
    story.append(Spacer(1, 0.25 * cm))

    alloc_rows = [["Poche", "Poids indicatif"]] + [[label, f"{weight}%"] for label, weight in profile["allocation"]]
    alloc_table = Table(alloc_rows, colWidths=[10.0 * cm, 2.0 * cm])
    alloc_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
                ("ALIGN", (1, 1), (1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(Paragraph("Allocation indicative", styles["CardTitle"]))
    story.append(Paragraph(f"Volatilité attendue : {profile['volatility']}", styles["BodyText"]))
    story.append(alloc_table)
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("Points de vigilance - MIF2 light", styles["CardTitle"]))
    if flags:
        for flag in flags:
            story.append(Paragraph(f"- {flag}", styles["BodyText"]))
    else:
        story.append(Paragraph("Aucune incohérence majeure détectée entre horizon, capacité financière, objectifs et appétence au risque déclarée.", styles["BodyText"]))
    story.append(Spacer(1, 0.25 * cm))

    story.append(Paragraph("Important", styles["CardTitle"]))
    story.append(
        Paragraph(
            "Ce document constitue un outil pédagogique et d'orientation commerciale. Il s'inspire des dimensions classiques d'un recueil de profil investisseur, mais ne remplace pas un questionnaire réglementaire complet de connaissance client, d'adéquation et de suitability.",
            styles["SmallBody"],
        )
    )

    doc.build(story)

    if os.path.exists(tmp_chart_path):
        os.remove(tmp_chart_path)

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# ============================================================
# INTERFACE STREAMLIT
# ============================================================
st.title("Diagnostic profil investisseur")
st.markdown(
    """
Répondez à **25 questions structurées** pour estimer votre **profil de risque**, votre **capacité financière à supporter la volatilité**
ainsi que la cohérence globale de votre stratégie.  
Vous obtenez ensuite :
- un **score pondéré sur 100**,
- un **profil investisseur détaillé**,
- un **graphique radar**,
- un **rapport PDF téléchargeable**.
"""
)

with st.expander("Méthodologie du diagnostic", expanded=False):
    st.write(
        "Le scoring combine cinq dimensions : horizon, tolérance au risque, capacité financière, connaissances et objectifs. "
        "Les questions les plus sensibles, notamment sur la capacité de perte et la réaction aux baisses, sont davantage pondérées."
    )
    st.info(
        "Version MIF2 light : cette grille renforce la cohérence du profil, mais ne remplace pas un questionnaire réglementaire complet."
    )

st.markdown("---")

st.markdown("## Questionnaire premium")

answers: Dict[int, str] = {}
current_section = None
for index, q in enumerate(QUESTIONS, start=1):
    progress = index / len(QUESTIONS)
    if q["section"] != current_section:
        current_section = q["section"]
        st.markdown(f"### {current_section}")

    st.caption(f"Question {index}/{len(QUESTIONS)} - Poids {q['weight']}")
    st.markdown(f"**Q{q['id']}. {q['question']}**")

    labels = [f"{key}) {value}" for key, value in q["options"].items()]
    selected_label = st.radio(
        label="Choisissez une réponse",
        options=labels,
        key=f"question_{q['id']}",
        index=None,
        label_visibility="collapsed",
    )
    if selected_label:
        answers[q["id"]] = selected_label[0].lower()

    st.progress(progress)

st.markdown("---")
submit = st.button("Obtenir mon diagnostic investisseur")

if submit:

    missing_questions = [q["id"] for q in QUESTIONS if q["id"] not in answers]

    if missing_questions:
        st.error("Merci de répondre à toutes les questions.")
    
    else:
        raw_weighted_score, normalized_score, max_weighted_score = calculate_weighted_score(answers)
        dimension_scores = calculate_dimension_scores(answers)
        profile = get_profile(normalized_score)
        flags = build_consistency_flags(answers, dimension_scores)
        marketing_summary = get_marketing_summary(profile, dimension_scores, flags)
        chart_bytes = create_radar_chart(dimension_scores)

        pdf_bytes = generate_pdf_report(
            profile=profile,
            normalized_score=normalized_score,
            dimension_scores=dimension_scores,
            flags=flags,
            chart_bytes=chart_bytes,
            marketing_summary=marketing_summary,
        )

        st.success("Votre diagnostic a été généré avec succès.")
        st.markdown("## Votre résultat")

        col1, col2, col3 = st.columns(3)
        col1.metric("Score pondéré", f"{normalized_score} / 100")
        col2.metric("Profil", profile["name"])
        col3.metric("Niveau de risque", profile["risk_level"])

        st.markdown(f"**Lecture du profil :** {profile['subtitle']}")
        st.markdown(f"**Horizon cohérent :** {profile['horizon']}")
        st.markdown(f"**Volatilité à anticiper :** {profile['volatility']}")
        st.markdown(f"**Synthèse :** {marketing_summary}")

        st.markdown("### Scores par dimension")
        score_cols = st.columns(len(DIMENSIONS))
        for idx, dimension in enumerate(DIMENSIONS):
            score_cols[idx].metric(dimension, f"{dimension_scores[dimension]} / 100")

        st.markdown("### Graphique profil")
        st.image(chart_bytes, use_container_width=False)

        st.markdown("### Télécharger votre rapport")
        st.download_button(
            label="Télécharger le rapport PDF",
            data=pdf_bytes,
            file_name="diagnostic_profil_investisseur.pdf",
            mime="application/pdf",
        )

        st.markdown("### Allocation indicative")
        allocation_table = {
            "Poche": [label for label, _ in profile["allocation"]],
            "Poids indicatif": [f"{weight}%" for _, weight in profile["allocation"]],
        }
        st.table(allocation_table)

        st.markdown("### Points de vigilance")
        if flags:
            for flag in flags:
                st.warning(flag)
        else:
            st.info("Aucune incohérence majeure détectée entre le risque visé, l'horizon et la capacité financière déclarée.")

        st.markdown("### Prochaine étape")
        st.write(
            "Utilisez ce diagnostic comme base d'échange pour transformer un niveau de risque théorique en allocation concrète, enveloppes adaptées, horizon cohérent et plan d'action patrimonial."
        )

        st.link_button(
            "Recevoir mon diagnostic personnalisé par email",
            "https://docs.google.com/forms/d/e/1FAIpQLSdFU9rg4dM1uCtg_31kcMBRUFsmihTqlMEFOtSIwXqYiucqjg/viewform?usp=publish-editor"
        )

        with st.expander("Détails techniques du scoring", expanded=False):
            st.write(f"Score pondéré brut : {round(raw_weighted_score, 2)} / {round(max_weighted_score, 2)}")
            st.write("Questions fortement pondérées : capacité de perte, horizon réel, discipline en phase de baisse, sécurité financière.")
            
            
