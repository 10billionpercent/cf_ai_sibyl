INTERNSHIP_KEYWORDS = [
    "intern",
    "internship",
    "summer",
    "winter",
    "fall",
    "spring",
    "student",
    "graduate",
    "new grad",
    "entry level",
    "trainee",
    "apprentice",
    "campus",
    "university",
    "college"
]


EXCLUDE_KEYWORDS = [
    "senior",
    "staff",
    "principal",
    "lead",
    "manager",
    "director",
    "5+ years",
    "7+ years",
    "10+ years"
]


def is_internship(text):
    if not text:
        return False

    text = text.lower()

    # remove senior roles
    if any(word in text for word in EXCLUDE_KEYWORDS):
        return False

    # allow internship-ish roles
    return any(word in text for word in INTERNSHIP_KEYWORDS)