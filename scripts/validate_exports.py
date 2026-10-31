import json
from pathlib import Path

root = Path(__file__).parents[1] / "exports"
for name in ("schedule.json", "schedule_after.json"):
    data = json.loads((root / name).read_text())
    assert data["metadata"]["validated"] is True
    assert data["metadata"]["hardConstraintViolations"] == 0
    seen = set()
    for session in data["sessions"]:
        key = (session["day"], session["startPeriod"], session["room"])
        assert key not in seen, f"{name}: room collision {key}"
        seen.add(key)
    print(f"{name}: valid ({len(data['sessions'])} sessions, 0 hard violations)")
