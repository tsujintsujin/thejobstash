# -*- coding: utf-8 -*-
"""python test_harvard.py - harvard.py's guards, with no network and no Gemini."""
import copy
import harvard as H

SRC = """JANE DOE
Cebu City, Philippines | jane@example.com | 0917 555 0142
EXPERIENCE
Bookkeeper - Reyes Trading   2019 to 2024
Recorded 40 daily transactions in QuickBooks.
SKILLS
QuickBooks, Microsoft Excel, data entry, calendar management
"""

GOOD = {
    "name": "Jane Doe", "location": "Cebu City, Philippines", "phone": "0917 555 0142",
    "email": "jane@example.com", "links": [],
    "education": [],
    "experience": [{"org": "Reyes Trading", "location": "", "title": "Bookkeeper",
                    "dates": "2019 to 2024",
                    "bullets": ["Recorded 40 daily transactions in QuickBooks."]}],
    "projects": [], "activities": [],
    "additional": [{"label": "Technical Skills",
                    "items": ["QuickBooks", "Microsoft Excel", "Data Entry"]}],
}


def main():
    assert H.check_facts(GOOD, SRC) == [], H.check_facts(GOOD, SRC)

    bad = copy.deepcopy(GOOD)
    bad["experience"][0]["bullets"].append("Cut month-end close by 30%.")
    bad["experience"][0]["org"] = "Globe Telecom"
    bad["additional"][0]["items"].append("SAP")
    bad["links"] = ["linkedin.com/in/janedoe"]
    found = {(w, v) for w, v, _ in H.check_facts(bad, SRC)}
    assert ("experience.bullets", "Cut month-end close by 30%.") in found, found
    assert ("experience.org", "Globe Telecom") in found, found
    assert ("additional.Technical Skills", "SAP") in found, found
    assert ("links", "linkedin.com/in/janedoe") in found, found

    fixed = H.strip_facts(copy.deepcopy(bad), H.check_facts(bad, SRC))
    assert "SAP" not in fixed["additional"][0]["items"]
    assert fixed["experience"][0]["bullets"] == GOOD["experience"][0]["bullets"]
    assert fixed["links"] == []

    # calendar management is in the source but not in GOOD: it gets put back.
    assert H.lost_skills(GOOD, SRC) == ["calendar management"], H.lost_skills(GOOD, SRC)
    back = H.add_back(copy.deepcopy(GOOD), SRC, ["calendar management"])
    assert "Calendar management" in back["additional"][0]["items"]
    assert H.lost_skills(back, SRC) == []

    # Grouped under Tools only -> a Skills group is created, not Tools padded.
    tools = copy.deepcopy(GOOD)
    tools["additional"] = [{"label": "Tools", "items": ["QuickBooks"]}]
    back = H.add_back(tools, SRC, ["data entry"])
    assert back["additional"][0] == {"label": "Skills", "items": ["Data entry"]}

    page = H.to_html(dict(GOOD, name="<script>x</script>"))
    assert "<script>x" not in page and "&lt;script&gt;" in page
    assert "REYES TRADING" not in page and "Reyes Trading" in page   # CSS uppercases

    assert H.warnings_for(GOOD) == ["No education section found."]
    assert H.ID_RE.match("h1789627467084_y5v0ffmf")
    assert not H.ID_RE.match("x & del *")

    tense = copy.deepcopy(GOOD)
    tense["experience"][0]["bullets"] = ["Build and maintain dashboards.",
                                         "Validate source data.", "Responsible for filing."]
    H.fix_tense(tense)
    assert tense["experience"][0]["bullets"] == [
        "Built and maintained dashboards.", "Validated source data.",
        "Responsible for filing."], tense["experience"][0]["bullets"]
    tense["experience"][0]["dates"] = "2019 to Present"
    tense["experience"][0]["bullets"] = ["Build dashboards."]
    H.fix_tense(tense)
    assert tense["experience"][0]["bullets"] == ["Build dashboards."]
    print("test_harvard: all pass")


if __name__ == "__main__":
    main()
