import sys
sys.path.insert(0, '.')

from backend.routers.assessments import run_spatial_assessment

localities = [
    ("Charminar", 17.3616, 78.4747, False),
    ("Dilsukhnagar", 17.3688, 78.5247, True),
    ("Kukatpally", 17.4947, 78.3996, False),
    ("Gachibowli", 17.4401, 78.3489, False),
    ("Madhapur", 17.4483, 78.3915, False),
    ("Secunderabad", 17.4399, 78.4983, False),
    ("LB Nagar", 17.3457, 78.5522, False),
    ("Mehdipatnam", 17.3916, 78.4385, False),
    ("Puppalguda", 17.4012, 78.3654, False),
    ("Banjara Hills", 17.4156, 78.4350, False),
]

print("=== LOCAL TESTING 10 TARGET LOCALITIES (HISTORICAL IUPS) ===")
for name, lat, lon, expected_scored in localities:
    res = run_spatial_assessment(lat, lon)
    cats = res.get("category_assessments", {})
    fl = cats.get("flood_risk", {})
    ht = cats.get("heat_risk", {})
    inf = cats.get("infrastructure_risk", {})
    iups = res.get("integrated_priority_assessment", {})
    
    score = fl.get("score_value")
    cls = fl.get("classification")
    is_scored = fl.get("is_scored")
    
    if expected_scored:
        assert is_scored is True, f"{name} expected scored"
        assert score == 46.2, f"{name} expected 46.2, got {score}"
        assert cls == "MEDIUM", f"{name} expected MEDIUM, got {cls}"
    else:
        assert is_scored is False, f"{name} expected unscored"
        assert score is None, f"{name} expected None, got {score}"
        assert cls == "NOT SCORED", f"{name} expected NOT SCORED, got {cls}"
        assert "Insufficient" in fl.get("reason", "")
        
    p_score = iups.get("priority_score")
    h_cls = ht.get("classification")
    i_cls = inf.get("classification")
    print(f"PASS: {name:15} | IUPS={p_score} | Flood={cls} ({score}) | Heat={h_cls} | Infra={i_cls}")

print(">>> ALL 10 LOCALITIES VERIFIED SUCCESSFULLY! <<<")
