# Demonstration test cases

The automated assertions live in `tests/test_engine.py`. These examples make the expected agent behavior and actual deterministic output easy to review without an API call.

| Scenario / input | Expected behavior | Actual output |
| --- | --- | --- |
| `I need a 2 BHK. What is the price?` | Capture 2 BHK and state only the supplied starting price. | `Northstar One’s 2 BHK starts at ₹1.35 crore onwards, and 3 BHK at ₹1.75 crore onwards. Which configuration are you considering?` |
| `Please stop calling me` | Mark do-not-contact, end immediately, no further qualification. | `Understood. We’ll stop further communication. Take care.` |
| `I want a site visit` then `Saturday at 11 AM` | Ask for a time first; only then simulate confirmation. | `Your site visit is confirmed for Saturday at 11 AM. A Northstar Homes advisor will coordinate the next details.` |
| `I want a site visit but the slot is unavailable` | Explicitly mark failure and offer an alternative/human; never claim confirmation. | `Sorry, that site visit is not confirmed. I can help try another time or have a human advisor contact you. Which would you prefer?` |
| `I need a 3 BHK for self-use with 2 crore budget` | Capture configuration, intent and budget for analytics. | Memory includes `3 BHK`, `self-use`, and `2 crore`; analytics reports these fields. |
| `Does it have a swimming pool?` | Escalate; do not invent amenities. | `I do not have that verified detail right now. I can have a Northstar Homes advisor confirm it for you.` |
| `Tell me about the project` | State only authorised facts (location, configs, starting prices). | Reply mentions Sector 79, 2/3 BHK, ₹1.35/₹1.75 crore onwards, and defers other details to an advisor. |
| After config + purpose, user says `not fixed` | Accept flexible budget; cite only the starting price; offer a site visit. | `No problem—a flexible budget works. For reference, 2 BHK starts at ₹1.35 crore onwards. Would you like to arrange a site visit?` |
