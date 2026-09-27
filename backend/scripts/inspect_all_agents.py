#!/usr/bin/env python3
"""
inspect_all_agents.py - BeeSafe.AI Agent Inspection Utility

Runs each agent in isolation and in an end-to-end simulated turn using Google Gemini,
printing color-coded outputs, schemas, and live evaluation details.
"""

import sys
import json
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.services.llm_client import get_default_provider
from app.services.persona_agent import get_honeypot_reply
from app.services.scammer_bot import (
    get_simulated_scammer_reply,
    SEEDED_FAKE_WALLET,
    SEEDED_FAKE_PAYMENT_HANDLE,
    SEEDED_FAKE_URL,
    SEEDED_FAKE_PHONE,
)
from app.services.risk_agent import run_risk_agent, explain_for_demo
from app.services.extraction import extract_indicators
from app.schemas import RiskAssessmentResult

# ANSI Colors for clean terminal presentation
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"


def header(title: str):
    print(f"\n{BOLD}{CYAN}{'=' * 70}{RESET}")
    print(f"{BOLD}{CYAN}{title.center(70)}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 70}{RESET}\n")


def subheader(title: str):
    print(f"\n{BOLD}{YELLOW}--- {title} ---{RESET}")


def run_inspection():
    header("BEESAFE.AI - MULTI-AGENT INSPECTION SUITE")
    print(f"{BOLD}Active Provider:{RESET} {GREEN}{get_default_provider().upper()}{RESET}")
    print(f"{BOLD}Model:{RESET}           {GREEN}{settings.GEMINI_MODEL}{RESET}")
    print(f"{BOLD}API Key Configured:{RESET} {'Yes' if settings.GEMINI_API_KEY else 'No'}")

    # ------------------------------------------------------------------------
    # 1. SCAMMER BOT
    # ------------------------------------------------------------------------
    header("1. SCAMMER BOT (Pig-Butchering Simulation Agent)")
    print("Simulates a scammer progressing across conversational stages:")
    
    stages = [
        (1, "Stage 1: Wrong Number / Innocent Hook"),
        (3, "Stage 2: Rapport & Platform Shift"),
        (5, "Stage 3: Urgency & Wire / Crypto Demand"),
    ]
    
    scammer_history = []
    for turn_no, stage_desc in stages:
        subheader(stage_desc)
        reply = get_simulated_scammer_reply(scammer_history, turn_number=turn_no)
        print(f"{BOLD}{MAGENTA}[Turn {turn_no} Scammer]:{RESET} {reply}")
        scammer_history.append({"role": "scammer", "text": reply})
        scammer_history.append({"role": "persona", "text": "I see, could you explain more?"})

    # ------------------------------------------------------------------------
    # 2. THREAT INDICATOR EXTRACTION
    # ------------------------------------------------------------------------
    header("2. THREAT INDICATOR EXTRACTOR")
    sample_text = (
        f"Contact our manager at {SEEDED_FAKE_PHONE} or send the crypto fee directly to USDT wallet {SEEDED_FAKE_WALLET} "
        f"or via handle {SEEDED_FAKE_PAYMENT_HANDLE}. Verify our registration at {SEEDED_FAKE_URL}"
    )
    print(f"{BOLD}Sample Inbound Text:{RESET}\n{sample_text}\n")
    indicators = extract_indicators(sample_text)
    for idx, ind in enumerate(indicators, 1):
        i_type = ind.get("indicator_type", "IOC") if isinstance(ind, dict) else ind.indicator_type
        i_val = ind.get("value", "") if isinstance(ind, dict) else ind.value
        print(f"  {idx}. {BOLD}{i_type.upper()}:{RESET} {GREEN}{i_val}{RESET}")

    # ------------------------------------------------------------------------
    # 3. PERSONA AGENT (Honeypot Defender)
    # ------------------------------------------------------------------------
    header("3. PERSONA AGENT (Autonomous Honeypot Defense)")
    persona = {
        "name": "Margaret Chen",
        "age": 72,
        "background": "Retired elementary teacher, loves gardening, cautious with tech",
        "delay_strategy": "Acts slightly confused, asks polite clarifying questions, delays compliance",
    }
    print(f"{BOLD}Persona Assigned:{RESET} {persona['name']} ({persona['age']}, {persona['background']})")
    print(f"{BOLD}Delay Strategy:{RESET}   {persona['delay_strategy']}")

    inbound_scam = "Kindly send $250 via wire transfer immediately to prevent account suspension."
    history = [{"role": "scammer", "text": inbound_scam}]
    
    subheader("Input Turn from Scammer")
    print(f"{BOLD}Scammer message:{RESET} \"{inbound_scam}\"")

    honeypot_res = get_honeypot_reply(history, persona)
    
    subheader("Persona Agent Live Output")
    print(f"{BOLD}{GREEN}Generated Reply:{RESET}  \"{honeypot_res.reply}\"")
    print(f"{BOLD}{YELLOW}Flagged Action:{RESET}   {honeypot_res.flagged_action} {'(Triggered Review Queue)' if honeypot_res.flagged_action else '(Safe to send)'}")

    # ------------------------------------------------------------------------
    # 4. RISK AGENT (Threat Assessment Engine)
    # ------------------------------------------------------------------------
    header("4. RISK AGENT (Multi-Turn Fraud Evaluation)")
    demo_transcript = f"""
Scammer: Hello! Your bank account was accessed from an unrecognized device in Dallas, TX.
Persona: Oh goodness me! Which bank is this? I only use my local branch down on Elm Street.
Scammer: This is the fraud division. To safeguard your savings, please wire $1,200 to crypto address {SEEDED_FAKE_WALLET}.
Persona: I need to find my reading glasses, dear. Where do I send the check?
Scammer: No checks! You must do an immediate transfer to {SEEDED_FAKE_WALLET} right now.
"""
    print(f"{BOLD}Evaluating Demo Conversation Transcript:{RESET}")
    print(demo_transcript.strip())

    risk_res = run_risk_agent(demo_transcript)
    
    subheader("Risk Agent Live Output")
    print(f"{BOLD}Risk Score:{RESET}       {GREEN if risk_res.risk_score < 40 else YELLOW if risk_res.risk_score < 70 else MAGENTA}{risk_res.risk_score}/100{RESET}")
    print(f"{BOLD}Classification:{RESET}   {risk_res.classification}")
    print(f"{BOLD}Risk Factors / Reasons:{RESET}")
    for r in risk_res.reasons:
        print(f"  • {r}")

    # ------------------------------------------------------------------------
    # 5. DEMO EXPLANATION AGENT
    # ------------------------------------------------------------------------
    header("5. DEMO EXPLANATION AGENT (Executive Brief)")
    explanation = explain_for_demo(risk_res)
    print(f"{BOLD}Executive Narrative for Analysts/Executives:{RESET}\n")
    print(f"{BLUE}{explanation}{RESET}")

    header("ALL AGENTS EVALUATED SUCCESSFULLY")


if __name__ == "__main__":
    run_inspection()
