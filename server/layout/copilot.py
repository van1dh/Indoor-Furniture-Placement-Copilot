"""Claude as the layout copilot: turn free-text notes and chat messages into presets and preferences, and explain
finished layouts in plain language.

Without Claude API credentials (or with COPILOT_OFFLINE set) the copilot still works, more simply: it picks a
preset from keywords in the notes and explains layouts from a template.
"""
import json
import os
import re
from dataclasses import dataclass, field

from . import preferences as prefs
from .catalog import FURNITURE_TYPES, PRESETS

MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"

INTERPRET_SYSTEM = f"""You are the copilot of a furniture layout planner. A layout engine places furniture in a \
rectangular room; you translate what the user wants into settings the engine understands.

Settings:
- preset: the overall goal, one of:
{chr(10).join(f'  - "{name}": {p["label"]} - {p["description"]}' for name, p in PRESETS.items())}
  Return null to keep the current preset. Only change it when the user's words clearly call for another goal
  (a toddler or baby means child_safe, a wheelchair or walker means accessible, several roommates or students
  sharing means shared).
- preferences: placement wishes for furniture types that are in the room. Each has
  kind "near", "away" or "against_wall"; piece (a furniture type); target ("window", "door", "center",
  "wall:bottom", "wall:right", "wall:top", "wall:left", or another furniture type; against_wall needs a wall);
  strength "low", "medium" or "high" (high only when the user insists); and a short reason.
  Furniture types: {", ".join(f"{k} ({v['label']})" for k, v in FURNITURE_TYPES.items())}.

Return the complete preference list that should apply from now on: keep earlier preferences the user has not
changed, replace or drop the ones they change, and add new ones. Do not invent wishes the user did not express.
The bottom wall is where y = 0; walls are named as seen on the floor plan (bottom, right, top, left).

reply: one or two sentences to the user, in the language they wrote in, saying what you set. If part of the
request cannot be expressed with these settings (for example adding furniture or resizing the room), say so
and point them to the form."""

EXPLAIN_SYSTEM = """You explain furniture layouts produced by a layout planner. Given the room, the furniture \
positions and the planner's metrics, write 3 to 5 plain sentences for the person who will live there: why the \
main pieces are where they are, how it serves their goal, which of their preferences were met or not, and \
anything to watch out for from the warnings. Refer to walls as the floor plan does (bottom, right, top, left) \
and to sizes in feet. Write in the language of the user's notes or messages (English if there are none). \
No headings, lists or markdown."""

INTERPRET_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["preset", "preferences", "reply"],
    "properties": {
        "preset": {"anyOf": [{"type": "string", "enum": list(PRESETS)}, {"type": "null"}]},
        "preferences": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "piece", "target", "strength", "reason"],
                "properties": {
                    "kind": {"type": "string", "enum": list(prefs.KINDS)},
                    "piece": {"type": "string", "enum": list(FURNITURE_TYPES)},
                    "target": {"type": "string", "enum": list(prefs.TARGETS)},
                    "strength": {"type": "string", "enum": list(prefs.STRENGTHS)},
                    "reason": {"type": "string"},
                },
            },
        },
        "reply": {"type": "string"},
    },
}

# Keyword fallback for choosing a preset when Claude is not available
PRESET_KEYWORDS = {
    "child_safe": r"child|kid|toddler|baby|infant|孩子|宝宝|婴儿|幼儿|儿童|小孩",
    "accessible": r"wheelchair|walker|mobility|accessib|disab|轮椅|行动不便|无障碍|残疾",
    "shared": r"roommate|room-mate|flatmate|shared|students|室友|合租|同学|共享",
}


class CopilotUnavailable(RuntimeError):
    pass


@dataclass
class Interpretation:
    preset: str | None
    preferences: list
    reply: str
    notices: list = field(default_factory=list)


def keyword_preset(text):
    for preset, pattern in PRESET_KEYWORDS.items():
        if re.search(pattern, text or "", re.IGNORECASE):
            return preset
    return None


class Copilot:
    def __init__(self, client=None):
        self._client = client
        self.offline_reason = None
        if client is None and os.environ.get("COPILOT_OFFLINE"):
            self.offline_reason = "turned off with COPILOT_OFFLINE"

    @property
    def online(self):
        return self.offline_reason is None

    # --- Claude calls -------------------------------------------------------------------------------------

    def _create(self, **kwargs):
        import anthropic

        if self._client is None:
            client = anthropic.Anthropic(timeout=60.0, max_retries=1)
            # The SDK only notices missing credentials when it builds the request (and raises TypeError then)
            if client.api_key is None and client.auth_token is None and client.credentials is None:
                self.offline_reason = "no Claude API credentials are configured"
                raise CopilotUnavailable(self.offline_reason)
            self._client = client
        try:
            response = self._client.beta.messages.create(
                model=MODEL,
                betas=[FALLBACK_BETA],
                fallbacks="default",
                **kwargs,
            )
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
            self.offline_reason = "the Claude API credentials are missing or invalid"
        except anthropic.RateLimitError:
            self.offline_reason = "the Claude API is rate limiting requests"
        except anthropic.APIConnectionError:
            self.offline_reason = "the Claude API could not be reached"
        except anthropic.APIStatusError as e:
            self.offline_reason = f"the Claude API returned an error ({e.status_code})"
        except anthropic.AnthropicError:
            self.offline_reason = "no Claude API credentials are configured"
        else:
            if response.stop_reason == "refusal":
                raise CopilotUnavailable("Claude declined this request")
            text = "".join(b.text for b in response.content if b.type == "text").strip()
            if not text:
                raise CopilotUnavailable("Claude returned an empty answer")
            return text
        raise CopilotUnavailable(self.offline_reason)

    def _interpret_online(self, text, context, history):
        messages = []
        for turn in history:
            messages.append({"role": turn["role"], "content": turn["text"]})
        messages.append({
            "role": "user",
            "content": f"Current room and settings:\n{json.dumps(context, indent=1)}\n\nUser:\n{text}",
        })
        answer = self._create(
            max_tokens=8000,
            system=INTERPRET_SYSTEM,
            messages=messages,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": INTERPRET_SCHEMA}},
        )
        try:
            data = json.loads(answer)
        except json.JSONDecodeError:
            raise CopilotUnavailable("Claude returned an answer that is not valid JSON")
        return data

    # --- public API ---------------------------------------------------------------------------------------

    def interpret(self, text, room, pieces, preset, current_preferences, history=(), layout=None):
        """Turn notes or a chat message into (preset or None to keep, full preference list, reply)."""
        context = {
            "room": room.to_dict(),
            "furniture": sorted({p.type for p in pieces}),
            "preset": preset,
            "preferences": [{k: v for k, v in p.items() if k != "met"} for p in current_preferences],
        }
        if layout:
            context["current_layout"] = layout
        notices = []
        if self.online:
            try:
                data = self._interpret_online(text, context, history)
            except CopilotUnavailable as e:
                if self.online:  # a one-off failure such as a refusal; going offline is reported separately
                    notices.append(f"The copilot could not help this time ({e}), so only simple keywords were used.")
            else:
                valid = []
                for item in data.get("preferences") or []:
                    try:
                        kept, dropped = prefs.normalize([item], pieces)
                    except prefs.PreferenceError:
                        continue
                    valid.extend(kept)
                    notices.extend(dropped)
                preset_choice = data.get("preset") if data.get("preset") in PRESETS else None
                return Interpretation(preset_choice, valid[:prefs.MAX_PREFERENCES], data.get("reply") or "", notices)

        preset_choice = keyword_preset(text)
        if preset_choice and preset_choice != preset:
            reply = f"Switched to the {PRESETS[preset_choice]['label']} preset based on your notes."
        else:
            reply = "I could not apply this without the copilot; use the form to change the layout."
        return Interpretation(preset_choice, list(current_preferences), reply, notices)

    def explain(self, summary):
        """Plain-language explanation of a finished layout (``summary`` is a JSON-ready dict)."""
        if self.online:
            try:
                return self._create(
                    max_tokens=4000,
                    system=EXPLAIN_SYSTEM,
                    messages=[{"role": "user", "content": json.dumps(summary, indent=1)}],
                    output_config={"effort": "low"},
                )
            except CopilotUnavailable:
                pass
        return template_explanation(summary)


def template_explanation(summary):
    """Explanation built from the metrics, used when Claude is not available."""
    pieces_by_wall = {}
    for piece in summary["furniture"]:
        if piece["wall"]:
            pieces_by_wall.setdefault(piece["wall"], []).append(piece["label"])
    sentences = [f"This is a {summary['preset']} layout for a {summary['room']}."]
    if pieces_by_wall:
        parts = [f"{', '.join(labels)} against the {wall} wall" for wall, labels in pieces_by_wall.items()]
        sentences.append(f"It puts the {'; the '.join(parts)}.")
    metrics = summary["metrics"]
    sentences.append(
        f"The largest open area is {metrics['openAreaFeet']} ft across, walkways are at least "
        f"{metrics['walkwayInches']} in wide, and a typical day takes about {metrics['dailyWalkFeet']} ft of walking.")
    met = [p for p in summary["preferences"] if p["met"]]
    if summary["preferences"]:
        sentences.append(f"{len(met)} of {len(summary['preferences'])} of your preferences are met.")
    if summary["warnings"]:
        sentences.append(f"Watch out: {summary['warnings'][0]}")
    return " ".join(sentences)

