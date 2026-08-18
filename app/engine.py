"""Conversation state, safe actions, analytics, and the OpenAI response adapter."""
from __future__ import annotations

import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from dotenv import load_dotenv

from .facts import (
    AUTHORIZED_FACTS,
    FLEXIBLE_BUDGET_PATTERN,
    FORBIDDEN_OUTPUT_PATTERNS,
    PRICE_QUESTION_PATTERN,
    PROJECT_INFO_PATTERN,
    UNKNOWN_DETAIL_PATTERN,
)
from .prompt import SYSTEM_PROMPT

load_dotenv(".env.local")


@dataclass
class Conversation:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    messages: list[dict[str, str]] = field(default_factory=list)
    configuration: str | None = None
    budget: str | None = None
    timeline: str | None = None
    purpose: str | None = None
    language: str = "english"
    interest_level: str = "unknown"
    follow_up_required: bool = False
    follow_up_time: str | None = None
    do_not_contact: bool = False
    human_escalation: bool = False
    booking_status: str = "not_requested"
    requested_visit_time: str | None = None
    site_visit_declined: bool = False
    ended: bool = False

    def memory(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("messages", None)
        return data


def detect_language(text: str) -> str | None:
    """Choose a fallback reply style. The model receives the same language policy."""
    if re.search(r"[\u0900-\u097F]", text):
        return "hindi"
    hinglish_words = r"mujhe|mujh|chahiye|hai|hain|aap|aapka|kaise|kitna|kya|batao|bataiye|dekhna|ghar|haan|nahi|nahin|kal|aaj|baad|liye"
    return "hinglish" if re.search(rf"\b({hinglish_words})\b", text.lower()) else None


def reply_in_language(c: Conversation, english: str, hinglish: str, hindi: str) -> str:
    return {"hinglish": hinglish, "hindi": hindi}.get(c.language, english)


def asks_unknown_detail(text: str) -> bool:
    return bool(re.search(UNKNOWN_DETAIL_PATTERN, text.lower()))


def asks_price(text: str) -> bool:
    return bool(re.search(PRICE_QUESTION_PATTERN, text.lower())) or "कीमत" in text or "दाम" in text


def asks_project_info(text: str) -> bool:
    return bool(re.search(PROJECT_INFO_PATTERN, text.lower()))


def is_flexible_budget(text: str) -> bool:
    return bool(re.search(FLEXIBLE_BUDGET_PATTERN, text.lower()))


def starting_price_for_config(configuration: str | None) -> str:
    prices = AUTHORIZED_FACTS["starting_prices"]
    if configuration == "2 BHK":
        return prices["2 BHK"]
    if configuration == "3 BHK":
        return prices["3 BHK"]
    return f"2 BHK {prices['2 BHK']} and 3 BHK {prices['3 BHK']}"


def should_use_deterministic_flow(c: Conversation) -> bool:
    """Keep config → purpose → budget → visit offer on safe templates until booking starts."""
    return (
        not c.ended
        and c.booking_status == "not_requested"
        and not c.site_visit_declined
        and not c.do_not_contact
    )


def contains_invented_price(text: str) -> bool:
    """Flag prices other than the two authorised starting prices."""
    for match in re.finditer(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:cr|crore|lakh|lac)\b", text.lower()):
        value = match.group(1)
        if value not in ("1.35", "1.75"):
            return True
    return False


def claims_booking_confirmed(text: str) -> bool:
    lower = text.lower()
    return bool(re.search(r"\b(confirmed|booked|scheduled|slot reserved|visit is set)\b", lower))


def sanitize_llm_reply(reply: str, c: Conversation, action: str | None) -> str:
    """Replace LLM output that invents unsupported project or booking details."""
    if c.booking_status != "confirmed" and claims_booking_confirmed(reply):
        if action == "visit_requested" or c.booking_status == "pending_details":
            return safe_reply_for_action("visit_requested", c) or reply
        return reply_in_language(
            c,
            "I have not confirmed a site visit yet. Would you like to pick a day and time?",
            "Abhi tak site visit confirm nahi hui hai. Kya aap ek din aur time batana chahenge?",
            "अभी तक साइट विज़िट की पुष्टि नहीं हुई है। क्या आप एक दिन और समय बताना चाहेंगे?",
        )
    if contains_invented_price(reply):
        return reply_in_language(
            c,
            "Northstar One’s 2 BHK starts at ₹1.35 crore onwards, and 3 BHK at ₹1.75 crore onwards. I do not have any other verified pricing.",
            "Northstar One mein 2 BHK ₹1.35 crore onwards se aur 3 BHK ₹1.75 crore onwards se start hota hai. Mere paas iske alawa koi verified pricing nahi hai.",
            "Northstar One में 2 BHK ₹1.35 करोड़ onwards से और 3 BHK ₹1.75 करोड़ onwards से शुरू होता है। मेरे पास इसके अलावा कोई सत्यापित कीमत नहीं है।",
        )
    for pattern, _kind in FORBIDDEN_OUTPUT_PATTERNS:
        if re.search(pattern, reply, re.I):
            return safe_reply_for_action("human_escalation", c) or reply
    return reply


def classify_and_update(c: Conversation, text: str) -> str | None:
    """Updates only high-confidence facts. Returns a system action when necessary."""
    lower = text.lower().strip()
    detected_language = detect_language(text)
    if detected_language:
        c.language = detected_language
    if re.search(r"\b(stop|unsubscribe|do not (call|contact)|don't (call|contact)|not interested|band karo|mat (call|contact))\b", lower):
        c.do_not_contact, c.ended, c.interest_level = True, True, "uninterested"
        return "do_not_contact"
    if re.search(r"\b(busy|later|call me later|baad mein|baad me|phir se)\b", lower):
        c.follow_up_required, c.interest_level = True, "warm"
        match = re.search(r"(?:at|on|after|around)\s+(.+)$", text, re.I)
        if match:
            c.follow_up_time = match.group(1).strip()
        return "follow_up"
    if asks_unknown_detail(text):
        c.human_escalation = True
        return "human_escalation"
    if c.booking_status == "pending_details" and re.search(
        r"\b(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|am|pm|morning|evening|baje|kal)\b|\b\d{1,2}[:.]\d{2}\b", lower
    ):
        c.requested_visit_time, c.booking_status, c.interest_level = text.strip(), "confirmed", "hot"
        c.ended = True
        return "booking_confirmed"
    if re.search(r"\b2\s*(bhk|bed)|two\s*(bhk|bed)\b", lower):
        c.configuration = "2 BHK"
    elif re.search(r"\b3\s*(bhk|bed)|three\s*(bhk|bed)\b", lower):
        c.configuration = "3 BHK"
    if re.search(r"\b(self[- ]?use|live|rehne|rehna|family)\b", lower):
        c.purpose = "self-use"
    elif re.search(r"\b(invest|investment)\b", lower):
        c.purpose = "investment"
    amount = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:cr|crore|lakh|lac)\b", lower)
    if amount:
        c.budget = amount.group(0).strip()
    elif c.configuration and c.purpose and not c.budget and is_flexible_budget(text):
        c.budget = "flexible / not fixed"
    if (
        c.configuration and c.purpose and c.budget and c.booking_status == "not_requested"
        and re.fullmatch(r"\s*(no|nope|not now|nahi|nahin|na)\s*[!.]?\s*", lower)
    ):
        c.site_visit_declined = True
        c.interest_level = "warm"
        return "visit_declined"
    # If the previous state has completed qualification, a plain yes/haan is
    # unambiguously consent for the site visit the agent just offered.
    if c.configuration and c.purpose and c.budget and re.fullmatch(r"\s*(yes|haan|han|ha|sure|ji)\s*[!.]?\s*", lower):
        c.interest_level, c.booking_status = "hot", "pending_details"
        return "visit_requested"
    if re.search(r"\b(site visit|visit the site|visit|dekhna|dekhn[ae])\b", lower):
        c.interest_level, c.booking_status = "hot", "pending_details"
        if re.search(r"\b(fail|failure|unavailable|slot full)\b", lower):
            c.booking_status, c.human_escalation = "failed", True
            return "booking_failed"
        return "visit_requested"
    if re.search(r"\b(interested|sounds good|yes|haan|han|sure)\b", lower):
        c.interest_level = "warm"
    if re.search(r"\b(not sure|maybe|browsing|just looking|dekh raha)\b", lower):
        c.interest_level = "cool"
    return None


def safe_reply_for_action(action: str, c: Conversation) -> str | None:
    if action == "do_not_contact":
        return reply_in_language(c, "Understood. We’ll stop further communication. Take care.", "Bilkul. Hum aapse aage contact nahi karenge. Take care.", "समझ गया। हम आगे संपर्क नहीं करेंगे। धन्यवाद।")
    if action == "follow_up":
        return reply_in_language(c, "No problem—I’ll arrange a follow-up. Have a good day.", "Koi baat nahi. Main follow-up arrange kar deta hoon. Aapka din achha rahe.", "कोई बात नहीं। मैं फॉलो-अप की व्यवस्था कर देता हूँ। आपका दिन शुभ रहे।")
    if action == "human_escalation":
        return reply_in_language(c, "I do not have that verified detail right now. I can have a Northstar Homes advisor confirm it for you. Would you like that?", "Mere paas abhi iski verified detail nahi hai. Main Northstar Homes advisor se confirm karwa sakta hoon. Kya aap chahenge?", "मेरे पास अभी इसकी सत्यापित जानकारी नहीं है। मैं Northstar Homes के सलाहकार से इसकी पुष्टि करवा सकता हूँ। क्या आप चाहेंगे?")
    if action == "booking_failed":
        return reply_in_language(c, "Sorry, that site visit is not confirmed. I can help try another time or have a human advisor contact you. Which would you prefer?", "Sorry, site visit confirm nahi hui hai. Main doosra time try karun ya human advisor se call arrange karun?", "क्षमा करें, साइट विज़िट की पुष्टि नहीं हुई है। क्या मैं दूसरा समय देखूँ या किसी सलाहकार से संपर्क करवाऊँ?")
    if action == "visit_declined":
        return reply_in_language(c, "No problem. Is there anything else I can help you with?", "Koi baat nahi. Kya main kisi aur cheez mein aapki help kar sakta hoon?", "कोई बात नहीं। क्या मैं किसी और चीज़ में आपकी मदद कर सकता हूँ?")
    if action == "booking_confirmed":
        return reply_in_language(c, f"Your site visit is confirmed for {c.requested_visit_time}. A Northstar Homes advisor will coordinate the next details.", f"Aapki site visit {c.requested_visit_time} ke liye confirm ho gayi hai. Northstar Homes advisor aapse next details ke liye coordinate karega.", f"आपकी साइट विज़िट {c.requested_visit_time} के लिए पुष्टि हो गई है। Northstar Homes का सलाहकार आगे की जानकारी के लिए संपर्क करेगा।")
    if action == "visit_requested":
        return reply_in_language(c, "I’d be happy to arrange a site visit. What day and time would suit you?", "Zaroor. Site visit ke liye kaunsa din aur time convenient rahega?", "ज़रूर। साइट विज़िट के लिए कौन-सा दिन और समय सुविधाजनक रहेगा?")
    return None


def project_info_reply(c: Conversation) -> str:
    return reply_in_language(
        c,
        "Northstar One is in Sector 79, Gurugram, with 2 BHK and 3 BHK options. "
        "Starting prices are ₹1.35 crore onwards for 2 BHK and ₹1.75 crore onwards for 3 BHK. "
        "I do not have other verified details such as amenities or possession—an advisor can confirm those. "
        "Which configuration interests you?",
        "Northstar One Sector 79 Gurugram mein hai, 2 BHK aur 3 BHK options ke saath. "
        "Starting price 2 BHK ₹1.35 crore onwards aur 3 BHK ₹1.75 crore onwards hai. "
        "Amenities ya possession jaise aur verified details mere paas nahi hain—advisor confirm kar sakta hai. "
        "Aap kaunsa configuration dekh rahe hain?",
        "Northstar One Sector 79, Gurugram में है, 2 BHK और 3 BHK विकल्पों के साथ। "
        "शुरुआती कीमत 2 BHK ₹1.35 करोड़ onwards और 3 BHK ₹1.75 करोड़ onwards है। "
        "सुविधाएँ या possession जैसी अन्य सत्यापित जानकारी मेरे पास नहीं है—सलाहकार पुष्टि कर सकता है। "
        "आप कौन-सा configuration देख रहे हैं?",
    )


def pre_llm_reply(c: Conversation, user_text: str, action: str | None) -> str | None:
    """Route high-risk or fact-bound turns away from the model."""
    if action:
        return safe_reply_for_action(action, c)
    if asks_unknown_detail(user_text):
        c.human_escalation = True
        return safe_reply_for_action("human_escalation", c)
    if asks_price(user_text):
        return reply_in_language(
            c,
            "Northstar One’s 2 BHK starts at ₹1.35 crore onwards, and 3 BHK at ₹1.75 crore onwards. Which configuration are you considering?",
            "Northstar One mein 2 BHK ₹1.35 crore onwards se aur 3 BHK ₹1.75 crore onwards se start hota hai. Aap kaunsa configuration dekh rahe hain?",
            "Northstar One में 2 BHK ₹1.35 करोड़ onwards से और 3 BHK ₹1.75 करोड़ onwards से शुरू होता है। आप कौन-सा configuration देख रहे हैं?",
        )
    if asks_project_info(user_text):
        return project_info_reply(c)
    return None


def deterministic_reply(c: Conversation, text: str) -> str:
    """Useful local fallback: follows state and mirrors English, Hindi, or Hinglish."""
    lower = text.lower()
    if any(word in lower for word in ("price", "cost", "kitna", "daam")) or "कीमत" in text:
        return reply_in_language(c, "Northstar One’s 2 BHK starts at ₹1.35 crore onwards, and 3 BHK at ₹1.75 crore onwards. Which configuration are you considering?", "Northstar One mein 2 BHK ₹1.35 crore onwards se aur 3 BHK ₹1.75 crore onwards se start hota hai. Aap kaunsa configuration dekh rahe hain?", "Northstar One में 2 BHK ₹1.35 करोड़ onwards से और 3 BHK ₹1.75 करोड़ onwards से शुरू होता है। आप कौन-सा configuration देख रहे हैं?")
    if not c.configuration:
        return reply_in_language(c, "Welcome to Northstar Homes. Are you exploring a 2 BHK or 3 BHK at Northstar One, Sector 79, Gurugram?", "Welcome to Northstar Homes. Aap Northstar One, Sector 79 Gurugram mein 2 BHK dekh rahe hain ya 3 BHK?", "Northstar Homes में आपका स्वागत है। क्या आप Northstar One, Sector 79, Gurugram में 2 BHK या 3 BHK देख रहे हैं?")
    if not c.purpose:
        return reply_in_language(c, f"Thanks—{c.configuration} noted. Are you buying for self-use or investment?", f"Theek hai, {c.configuration} noted. Aap self-use ke liye dekh rahe hain ya investment ke liye?", f"ठीक है, {c.configuration} नोट कर लिया। आप स्वयं रहने के लिए देख रहे हैं या निवेश के लिए?")
    if not c.budget:
        return reply_in_language(c, "Got it. What budget range are you comfortable with?", "Samajh gaya. Aapka comfortable budget range kya hai?", "समझ गया। आपका आरामदायक बजट रेंज क्या है?")
    if c.site_visit_declined:
        return reply_in_language(c, "No problem. Is there anything else I can help you with?", "Koi baat nahi. Kya main kisi aur cheez mein aapki help kar sakta hoon?", "कोई बात नहीं। क्या मैं किसी और चीज़ में आपकी मदद कर सकता हूँ?")
    price_ref = starting_price_for_config(c.configuration)
    if c.budget and "flexible" in c.budget.lower():
        return reply_in_language(
            c,
            f"No problem—a flexible budget works. For reference, {c.configuration} starts at {price_ref}. Would you like to arrange a site visit to Northstar One?",
            f"Koi baat nahi, flexible budget bilkul theek hai. Reference ke liye {c.configuration} {price_ref} se start hota hai. Kya aap Northstar One ki site visit arrange karna chahenge?",
            f"कोई बात नहीं, flexible budget ठीक है। संदर्भ के लिए {c.configuration} {price_ref} से शुरू होता है। क्या आप Northstar One की साइट विज़िट करना चाहेंगे?",
        )
    return reply_in_language(c, "Thank you. Would you like to arrange a site visit to Northstar One?", "Thank you. Kya aap Northstar One ke liye site visit arrange karna chahenge?", "धन्यवाद। क्या आप Northstar One की साइट विज़िट करना चाहेंगे?")


def generate_reply(c: Conversation, user_text: str, action: str | None) -> str:
    routed = pre_llm_reply(c, user_text, action)
    if routed:
        return routed
    if should_use_deterministic_flow(c):
        return deterministic_reply(c, user_text)
    api_key = os.getenv("OPENAI_API_KEY")
    if os.getenv("NORTHSTAR_OFFLINE") == "1" or not api_key:
        return deterministic_reply(c, user_text)
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        context = {
            "memory": c.memory(),
            "system_action": action or "none",
            "AUTHORITATIVE_FACTS_ONLY": AUTHORIZED_FACTS,
            "instruction": (
                "Reply to the latest customer message using ONLY AUTHORITATIVE_FACTS_ONLY. "
                "If the customer asks for any detail not in that object, say you do not have verified information "
                "and offer a human advisor—do NOT guess or invent. "
                "Do not claim a booking is confirmed unless booking_status is 'confirmed'. "
                "Keep it under 90 words."
            ),
        }
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5.6"),
            instructions=SYSTEM_PROMPT,
            input=[*c.messages[-12:], {"role": "user", "content": f"Conversation context: {context}\n\nCustomer message: {user_text}"}],
            store=False,
        )
        raw = response.output_text.strip() or deterministic_reply(c, user_text)
        return sanitize_llm_reply(raw, c, action)
    except Exception:
        return deterministic_reply(c, user_text)


def analytics(c: Conversation) -> dict[str, Any]:
    return {
        "conversation_id": c.id, "configuration": c.configuration, "budget": c.budget,
        "timeline": c.timeline, "purpose": c.purpose, "interest_level": c.interest_level,
        "site_visit_status": c.booking_status, "requested_visit_time": c.requested_visit_time,
        "site_visit_declined": c.site_visit_declined,
        "follow_up_required": c.follow_up_required, "follow_up_time": c.follow_up_time,
        "human_escalation": c.human_escalation, "do_not_contact": c.do_not_contact,
        "message_count": len(c.messages), "conversation_ended": c.ended,
    }
