import re

MAXIMUM = re.compile(r"\b(highest|maximum|max|high)\s+(?:daily\s+)?temperature\b|\btemperature\b.{0,65}\b(?:exceed|above|reach|over|at least)\b", re.I)
WEATHER = re.compile(r"\b(temperature|rain|rainfall|snow|snowfall|hurricane|wind|weather)\b", re.I)


def classify(question: str, description: str | None = None) -> str | None:
    text = f"{question} {description or ''}"
    if MAXIMUM.search(question):
        return "daily_max_temperature"
    if WEATHER.search(text):
        return "unsupported"
    return None
