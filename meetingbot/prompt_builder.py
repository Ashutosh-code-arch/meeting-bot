from datetime import datetime
from .merge import Utterance, utterances_to_text


def build_user_message(
    utterances: list[Utterance],
    meeting_title: str = "Untitled",
    participants: list[str] = [],
    duration_min: float = 0,
    additional_context: str = "",
) -> str:
    transcript = utterances_to_text(utterances)
    speakers = sorted(set(u.speaker for u in utterances))
    metadata = f"""Meeting title:      {meeting_title}
Date:               {datetime.now().strftime('%Y-%m-%d')}
Duration:           {duration_min:.0f} minutes
Detected speakers:  {', '.join(speakers)}
Named participants: {', '.join(participants) if participants else 'Unknown'}
Total utterances:   {len(utterances)}
Context:            {additional_context or 'None'}"""
    return f"""{metadata}

=== MEETING TRANSCRIPT ===
{transcript}
=== END TRANSCRIPT ===

Generate the complete 10-section meeting output.
Mark missing owners, deadlines, or decisions as [MISSING]."""
