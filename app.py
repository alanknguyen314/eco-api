# app.py
"""
Upcycle.green Environmental Engine API
- Best-effort Amazon scrape (if httpx + bs4 available), otherwise heuristic fallback
- Always returns 200 with a usable JSON payload; no 500s for normal scrape issues
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import hashlib
import re

# Optional imports (won't crash if missing)
try:
    import httpx  # type: ignore
except Exception:
    httpx = None  # type: ignore

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:
    BeautifulSoup = None  # type: ignore

app = FastAPI(
    title="Environmental Impact API",
    description="Calculate environmental metrics for products (scrape + fallback)",
    version="1.1.1",
)

# CORS: wide open for browser extensions
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------ Static DB / Heuristics ------------
MATERIAL_DATABASE: Dict[str, Dict[str, float]] = {
    "steel":     {"co2_per_kg": 2.0,  "water_per_kg": 50,    "recyclability": 90, "durability": 95},
    "aluminum":  {"co2_per_kg": 8.0,  "water_per_kg": 100,   "recyclability": 95, "durability": 90},
    "plastic":   {"co2_per_kg": 3.0,  "water_per_kg": 20,    "recyclability": 30, "durability": 60},
    "wood":      {"co2_per_kg": 0.5,  "water_per_kg": 10,    "recyclability": 70, "durability": 70},
    "cotton":    {"co2_per_kg": 5.0,  "water_per_kg": 10000, "recyclability": 60, "durability": 50},
    "polyester": {"co2_per_kg": 6.0,  "water_per_kg": 60,    "recyclability": 20, "durability": 70},
    "glass":     {"co2_per_kg": 1.0,  "water_per_kg": 15,    "recyclability": 100,"durability": 80},
    "ceramic":   {"co2_per_kg": 0.8,  "water_per_kg": 20,    "recyclability": 40, "durability": 85},
    "leather":   {"co2_per_kg": 17.0, "water_per_kg": 17000, "recyclability": 20, "durability": 90},
    "paper":     {"co2_per_kg": 1.2,  "water_per_kg": 30,    "recyclability": 80, "durability": 30},
    "rubber":    {"co2_per_kg": 3.0,  "water_per_kg": 40,    "recyclability": 50, "durability": 70},
}

TRANSPORT_DISTANCES = {
    "China": 10000, "India": 8000, "Vietnam": 10000, "USA": 1000,
    "Germany": 1000, "Mexico": 2000, "Unknown": 5000
}

# Simple in-memory cache
cache: Dict[str, Dict] = {}

# ------------ Models ------------
class ProductAnalysisRequest(BaseModel):
    url: str
    detailed: bool = False
    cache: bool = True

# ------------ Scrape helpers ------------
UA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/127.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

AMAZON_WEIGHT_RE = re.compile(
    r"(?:Item|Shipping)\s*Weight\s*[:\-]?\s*([\d\.,]+)\s*(pounds|pound|lbs|lb|ounces|oz|kilograms|kg|grams|g)",
    re.IGNORECASE,
)
AMAZON_COUNTRY_RE = re.compile(r"(?:Country of Origin)\s*[:\-]?\s*([A-Za-z ]+)", re.IGNORECASE)
AMAZON_MATERIAL_KEYS = [
    "Material", "Material Type", "Fabric Type", "Outer Material", "Material Composition"
]

def _to_kg(value_str: str, unit: str) -> float:
    v = float(value_str.replace(",", ""))
    unit = unit.lower()
    if unit in ("pounds", "pound", "lbs", "lb"):
        return v * 0.45359237
    if unit in ("ounces", "oz"):
        return v * 0.0283495231
    if unit in ("kilograms", "kg"):
        return v
    if unit in ("grams", "g"):
        return v / 1000.0
    return v  # assume kg if unknown

def _extract_first_text(soup, selector: str) -> Optional[str]:
    el = soup.select_one(selector)
    if el:
        txt = el.get_text(" ", strip=True)
        return txt if txt else None
    return None

def scrape_amazon(url: str, timeout_s: float = 8.0) -> Tuple[Dict, List[str]]:
    """
    Returns (partial, notes).
    partial = { 'title', 'materials':[], 'weight_kg': float|None, 'origin': str|None }
    notes = list of strings about what we found / missed
    """
    notes: List[str] = []
    result = {"title": None, "materials": [], "weight_kg": None, "origin": None}

    # If optional libs missing, skip scrape gracefully
    if httpx is None or BeautifulSoup is None:
        notes.append("Scrape libraries not installed (httpx/bs4); using heuristics.")
        return result, notes

    try:
        with httpx.Client(timeout=timeout_s, headers=UA_HEADERS, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code != 200 or not resp.text:
                notes.append(f"Amazon returned status {resp.status_code}")
                return result, notes

            # Use built-in parser to avoid extra deps
            soup = BeautifulSoup(resp.text, "html.parser")

            # Title
            title = _extract_first_text(soup, "#productTitle")
            if title:
                result["title"] = title

            # Feature bullets (can contain materials hints)
            bullet_box = soup.select_one("#feature-bullets")
            material_hits: List[str] = []
            if bullet_box:
                for li in bullet_box.select("li"):
                    txt = li.get_text(" ", strip=True).lower()
                    for k in MATERIAL_DATABASE.keys():
                        if k in txt and k not in material_hits:
                            material_hits.append(k)

            # Tech detail sections (several variants across locales)
            detail_blocks = soup.select("#detailBullets_feature_div li, #productDetails_techSpec_section_1 tr, #prodDetails tr")
            for row in detail_blocks:
                txt = row.get_text(" ", strip=True)

                # Materials by label
                for key in AMAZON_MATERIAL_KEYS:
                    if key.lower() in txt.lower():
                        parts = re.split(r":", txt, maxsplit=1)
                        if len(parts) == 2:
                            rhs = parts[1].strip().lower()
                            for k in MATERIAL_DATABASE.keys():
                                if k in rhs and k not in material_hits:
                                    material_hits.append(k)

                # Weight
                m_w = AMAZON_WEIGHT_RE.search(txt)
                if m_w and result["weight_kg"] is None:
                    result["weight_kg"] = round(_to_kg(m_w.group(1), m_w.group(2)), 3)

                # Country of origin
                m_c = AMAZON_COUNTRY_RE.search(txt)
                if m_c and not result["origin"]:
                    result["origin"] = m_c.group(1).strip()

            result["materials"] = material_hits

            # As a last resort, try bullets text for "weight"
            if result["weight_kg"] is None and bullet_box:
                txt = bullet_box.get_text(" ", strip=True)
                m_w2 = AMAZON_WEIGHT_RE.search(txt)
                if m_w2:
                    result["weight_kg"] = round(_to_kg(m_w2.group(1), m_w2.group(2)), 3)

            if not result["materials"]:
                notes.append("No materials found in page; will fall back to heuristics")
            if result["weight_kg"] is None:
                notes.append("No weight found in page; will fall back to heuristics")
            if not result["origin"]:
                notes.append("No country of origin found; defaulting to Unknown")

    except Exception as e:
        notes.append(f"Scrape error: {type(e).__name__}: {e}")

    return result, notes

# ------------ Heuristics ------------
def guess_materials(url: str) -> List[str]:
    u = url.lower()
    material_keywords = {
        "steel": ["steel", "stainless", "iron", "metal"],
        "aluminum": ["aluminum", "aluminium"],
        "plastic": ["plastic", "polypropylene", "pp", "polyethylene", "pe", "pet", "abs", "silicone", "rubber"],
        "wood": ["wood", "bamboo", "oak", "pine", "cedar"],
        "cotton": ["cotton"],
        "polyester": ["polyester", "synthetic"],
        "glass": ["glass"],
        "ceramic": ["ceramic", "porcelain"],
        "leather": ["leather"],
        "paper": ["paper", "cardboard"],
    }
    found: List[str] = []
    for m, keys in material_keywords.items():
        if any(k in u for k in keys):
            found.append(m)
    if found:
        return list(dict.fromkeys(found))  # de-dupe
    if any(x in u for x in ["kitchen", "cookware", "utensil", "pan", "pot"]):
        return ["steel", "plastic"]
    if any(x in u for x in ["furniture", "desk", "chair", "table", "sofa"]):
        return ["wood", "steel"]
    if any(x in u for x in ["clothing", "shirt", "pants", "dress"]):
        return ["cotton", "polyester"]
    if any(x in u for x in ["electronic", "computer", "laptop", "phone", "tablet"]):
        return ["plastic", "aluminum"]
    return ["plastic"]

def guess_weight_kg(url: str) -> float:
    u = url.lower()
    if any(x in u for x in ["phone", "smartphone", "mobile"]): return 0.2
    if any(x in u for x in ["laptop", "notebook", "computer"]): return 2.5
    if any(x in u for x in ["tablet", "ipad", "kindle"]): return 0.5
    if any(x in u for x in ["furniture", "desk", "chair", "sofa"]): return 15.0
    if any(x in u for x in ["clothing", "shirt", "pants", "dress"]): return 0.3
    if "book" in u: return 0.5
    if any(x in u for x in ["kitchen", "cookware", "pan", "pot"]): return 2.0
    if any(x in u for x in ["toy", "game"]): return 0.5
    return 1.0

def compute_metrics(materials: List[str], weight_kg: float, origin: str) -> Dict:
    co2_manu = 0.0
    water = 0.0
    rec_scores: List[float] = []
    dur_scores: List[float] = []

    w_each = weight_kg / len(materials) if materials else weight_kg
    for m in materials or ["plastic"]:
        if m in MATERIAL_DATABASE:
            d = MATERIAL_DATABASE[m]
            co2_manu += w_each * d["co2_per_kg"]
            water += w_each * d["water_per_kg"]
            rec_scores.append(d["recyclability"])
            dur_scores.append(d["durability"])
        else:
            co2_manu += w_each * 3.0
            water += w_each * 50
            rec_scores.append(50)
            dur_scores.append(50)

    co2_manu *= 1.2  # manufacturing overhead

    distance = TRANSPORT_DISTANCES.get(origin or "Unknown", 5000)
    co2_transport = weight_kg * distance * 0.00001 * 10  # simplified

    co2_total = co2_manu + co2_transport
    recyclability = sum(rec_scores) / len(rec_scores)
    durability = sum(dur_scores) / len(dur_scores)

    co2_score = max(0.0, 100.0 - (co2_total * 5.0))
    water_score = max(0.0, 100.0 - (water / 100.0))
    eco_score = (co2_score * 0.4 + water_score * 0.2 + recyclability * 0.2 + durability * 0.2)

    recs: List[str] = []
    if co2_total > 10: recs.append("High carbon footprint — consider locally made alternatives.")
    if recyclability < 50: recs.append("Low recyclability — look for products with sustainable materials.")
    if durability < 60: recs.append("May need frequent replacement — consider higher quality options.")
    if eco_score > 70:
        recs.append("Good environmental profile — relatively eco-friendly choice.")
    elif eco_score < 40:
        recs.append("Consider searching for more sustainable alternatives.")

    return {
        "co2_manufacturing": round(co2_manu, 2),
        "co2_transport": round(co2_transport, 2),
        "co2_total": round(co2_total, 2),
        "water_usage": round(water, 2),
        "recyclability": round(recyclability, 1),
        "durability": round(durability, 1),
        "eco_score": round(eco_score, 1),
        "recommendations": recs,
    }

def extract_product_name_from_url(url: str) -> str:
    if "/dp/" in url:
        parts = url.split("/")
        for i, part in enumerate(parts):
            if part == "dp" and i > 0:
                name_part = parts[i - 1].replace("-", " ").strip()
                if name_part:
                    return name_part[:60].title()
    return "Product"

# ------------ API ------------
@app.get("/")
def root():
    return {
        "status": "active",
        "service": "Environmental Impact Engine",
        "version": "1.1.1",
        "endpoints": ["/analyze (GET, POST)", "/materials", "/health", "/docs"],
        "message": "API is running",
    }

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/materials")
def get_materials():
    return {"materials": MATERIAL_DATABASE, "info": "CO2 in kg/kg; water in L/kg"}

class _AnalyzeParams(BaseModel):
    url: str
    detailed: bool = False
    cache: bool = True

@app.get("/analyze")
def analyze_get(url: str = Query(..., description="Product URL"), detailed: bool = False, use_cache: bool = True):
    req = _AnalyzeParams(url=url, detailed=detailed, cache=use_cache)
    return analyze_post(req)

@app.post("/analyze")
def analyze_post(request: _AnalyzeParams):
    cache_key = hashlib.md5(request.url.encode("utf-8")).hexdigest()
    if request.cache and cache_key in cache:
        cached = dict(cache[cache_key])
        cached["cached"] = True
        return cached

    url = request.url
    notes: List[str] = []
    scraped = {"title": None, "materials": [], "weight_kg": None, "origin": None}

    if "amazon." in url:
        s_partial, s_notes = scrape_amazon(url)
        scraped.update(s_partial)
        notes.extend(s_notes)

    materials = scraped["materials"] or guess_materials(url)
    weight_kg = scraped["weight_kg"] if scraped["weight_kg"] else guess_weight_kg(url)
    origin = scraped["origin"] or ("China" if "import" not in url.lower() else "USA")

    metrics = compute_metrics(materials, weight_kg, origin)

    confidence = 30
    if scraped["materials"]: confidence += 25
    if scraped["weight_kg"]: confidence += 25
    if scraped["origin"]: confidence += 20
    confidence = min(confidence, 95)

    product_name = scraped["title"] or extract_product_name_from_url(url)

    response = {
        "product_name": product_name,
        "environmental_score": {
            "co2_total_kg": metrics["co2_total"],
            "water_usage_liters": metrics["water_usage"],
            "recyclability_score": metrics["recyclability"],
            "durability_score": metrics["durability"],
            "overall_eco_score": metrics["eco_score"],
            "confidence_level": confidence,
        },
        "recommendations": metrics["recommendations"],
        "details": {
            "materials": materials,
            "estimated_weight_kg": weight_kg,
            "origin": origin,
            "co2_breakdown": {
                "manufacturing": metrics["co2_manufacturing"],
                "transport": metrics["co2_transport"],
            },
            "source": "scrape" if (scraped["materials"] or scraped["weight_kg"] or scraped["origin"]) else "fallback",
            "notes": notes,
        },
        "cached": False,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if request.cache:
        cache[cache_key] = response

    return response

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
