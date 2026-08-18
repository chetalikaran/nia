from app.engine import (
    Conversation,
    analytics,
    classify_and_update,
    generate_reply,
    sanitize_llm_reply,
)


def run_message(c, message):
    action = classify_and_update(c, message)
    c.messages.append({"role": "user", "content": message})
    return generate_reply(c, message, action)


def test_prices_and_configuration_are_captured():
    c = Conversation()
    actual = run_message(c, "I need a 2 BHK. What is the price?")
    assert c.configuration == "2 BHK"
    assert "₹1.35 crore onwards" in actual


def test_stop_ends_conversation_and_sets_dnc():
    c = Conversation()
    actual = run_message(c, "Please stop calling me")
    assert c.do_not_contact is True and c.ended is True
    assert "stop further communication" in actual.lower()


def test_booking_failure_is_never_presented_as_confirmed():
    c = Conversation()
    actual = run_message(c, "I want a site visit but the slot is unavailable")
    assert c.booking_status == "failed" and c.human_escalation is True
    assert "not confirmed" in actual.lower()


def test_site_visit_is_confirmed_only_after_a_slot_is_given():
    c = Conversation()
    first = run_message(c, "I want a site visit")
    assert c.booking_status == "pending_details"
    assert "what day and time" in first.lower()
    actual = run_message(c, "Saturday at 11 AM")
    assert c.booking_status == "confirmed"
    assert c.ended is True
    assert "confirmed for saturday at 11 am" in actual.lower()


def test_analytics_contains_required_lead_fields():
    c = Conversation()
    run_message(c, "I need a 3 BHK for self-use with 2 crore budget")
    result = analytics(c)
    assert result["configuration"] == "3 BHK"
    assert result["purpose"] == "self-use"
    assert result["budget"]


def test_fallback_does_not_repeat_the_purpose_question_after_answer():
    c = Conversation()
    run_message(c, "I need a 2 BHK")
    actual = run_message(c, "self-use")
    assert c.purpose == "self-use"
    assert "budget" in actual.lower()


def test_hinglish_fallback_reply_matches_customer_language():
    c = Conversation()
    actual = run_message(c, "Mujhe 2 BHK chahiye")
    assert c.language == "hinglish"
    assert "self-use ke liye" in actual

    follow_up = run_message(c, "self-use")
    assert "comfortable budget" in follow_up.lower()
    assert "samajh gaya" in follow_up.lower()


def test_hindi_fallback_reply_matches_customer_language():
    c = Conversation()
    actual = run_message(c, "मुझे 3 BHK चाहिए")
    assert c.language == "hindi"
    assert "स्वयं रहने" in actual


def test_hindi_price_question_gets_a_hindi_reply():
    c = Conversation()
    actual = run_message(c, "2 BHK की कीमत क्या है?")
    assert c.language == "hindi"
    assert "शुरू होता है" in actual


def test_yes_after_qualification_moves_to_site_visit_time():
    c = Conversation()
    run_message(c, "Mujhe 2 BHK chahiye")
    run_message(c, "self-use")
    run_message(c, "2 crore")
    actual = run_message(c, "haan")
    assert c.booking_status == "pending_details"
    assert "kaunsa din aur time" in actual.lower()


def test_unknown_project_detail_escalates_without_inventing_an_answer():
    c = Conversation()
    actual = run_message(c, "What is the possession date?")
    assert c.human_escalation is True
    assert "do not have that verified detail" in actual.lower()


def test_no_to_site_visit_does_not_repeat_the_offer():
    c = Conversation(configuration="2 BHK", purpose="self-use", budget="3cr")
    actual = run_message(c, "no")
    assert c.site_visit_declined is True
    assert "anything else i can help" in actual.lower()
    follow_up = run_message(c, "no")
    assert "anything else i can help" in follow_up.lower()


def test_amenity_question_escalates_without_inventing():
    c = Conversation()
    actual = run_message(c, "Does it have a swimming pool?")
    assert c.human_escalation is True
    assert "do not have that verified detail" in actual.lower()
    assert "pool" not in actual.lower() or "verified" in actual.lower()


def test_project_overview_uses_only_authorised_facts():
    c = Conversation()
    actual = run_message(c, "Tell me about the project")
    assert "Sector 79" in actual
    assert "₹1.35 crore onwards" in actual
    assert "₹1.75 crore onwards" in actual
    assert "pool" not in actual.lower()
    assert "possession" not in actual.lower() or "mere paas nahi" in actual.lower() or "do not have" in actual.lower()


def test_sanitize_strips_invented_prices():
    c = Conversation()
    cleaned = sanitize_llm_reply("Great choice! The 2 BHK is priced at ₹1.25 crore all inclusive.", c, None)
    assert "1.35 crore onwards" in cleaned
    assert "1.25" not in cleaned


def test_sanitize_strips_invented_amenities():
    c = Conversation()
    cleaned = sanitize_llm_reply("Yes, we have a swimming pool and clubhouse.", c, None)
    assert "verified detail" in cleaned.lower()


def test_flexible_budget_does_not_hallucinate():
    c = Conversation()
    run_message(c, "Mujhe 2 BHK chahiye")
    run_message(c, "self-use")
    actual = run_message(c, "not fixed")
    assert c.budget == "flexible / not fixed"
    assert "₹1.35 crore onwards" in actual
    assert "site visit" in actual.lower()
    assert "payment" not in actual.lower()
    assert "discount" not in actual.lower()


def test_flexible_budget_hinglish_variant():
    c = Conversation()
    run_message(c, "3 BHK")
    run_message(c, "investment")
    actual = run_message(c, "abhi fix nahi hai")
    assert c.budget == "flexible / not fixed"
    assert "₹1.75 crore onwards" in actual
    assert "site visit" in actual.lower()


def test_sanitize_blocks_false_booking_confirmation():
    c = Conversation(booking_status="pending_details")
    cleaned = sanitize_llm_reply("Your visit is confirmed for tomorrow at 10 AM.", c, None)
    assert "confirm" not in cleaned.lower() or "not confirmed" in cleaned.lower() or "pick a day" in cleaned.lower()
