"""
Environmental Engine API - Simplified for Render Deployment
Works with minimal dependencies and no compilation required
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import json
import hashlib
from datetime import datetime

app = FastAPI(
    title="Environmental Impact API",
    description="Calculate environmental metrics for products",
    version="1.0.0"
)

# Enable CORS for browser extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simplified material database
MATERIAL_DATABASE = {
    "steel": {"co2_per_kg": 2.0, "water_per_kg": 50, "recyclability": 90, "durability": 95},
    "aluminum": {"co2_per_kg": 8.0, "water_per_kg": 100, "recyclability": 95, "durability": 90},
    "plastic": {"co2_per_kg": 3.0, "water_per_kg": 20, "recyclability": 30, "durability": 60},
    "wood": {"co2_per_kg": 0.5, "water_per_kg": 10, "recyclability": 70, "durability": 70},
    "cotton": {"co2_per_kg": 5.0, "water_per_kg": 10000, "recyclability": 60, "durability": 50},
    "polyester": {"co2_per_kg": 6.0, "water_per_kg": 60, "recyclability": 20, "durability": 70},
    "glass": {"co2_per_kg": 1.0, "water_per_kg": 15, "recyclability": 100, "durability": 80},
    "ceramic": {"co2_per_kg": 0.8, "water_per_kg": 20, "recyclability": 40, "durability": 85},
    "leather": {"co2_per_kg": 17.0, "water_per_kg": 17000, "recyclability": 20, "durability": 90}
}

# Simple cache
cache = {}

# Request/Response Models (Pydantic v1 compatible)
class ProductAnalysisRequest(BaseModel):
    url: str
    detailed: Optional[bool] = False
    cache: Optional[bool] = True

class EnvironmentalScore(BaseModel):
    co2_total_kg: float
    water_usage_liters: float
    recyclability_score: float
    durability_score: float
    overall_eco_score: float
    confidence_level: float

class ProductAnalysisResponse(BaseModel):
    product_name: str
    environmental_score: EnvironmentalScore
    recommendations: List[str]
    cached: Optional[bool] = False
    timestamp: str

def extract_materials_from_url(url: str) -> List[str]:
    """Extract potential materials from product URL"""
    materials = []
    url_lower = url.lower()
    
    # Simple keyword matching
    material_keywords = {
        'steel': ['steel', 'metal', 'iron', 'stainless'],
        'aluminum': ['aluminum', 'aluminium'],
        'plastic': ['plastic', 'polypropylene', 'polyethylene'],
        'wood': ['wood', 'wooden', 'bamboo'],
        'cotton': ['cotton'],
        'polyester': ['polyester', 'synthetic'],
        'glass': ['glass'],
        'ceramic': ['ceramic', 'porcelain'],
        'leather': ['leather']
    }
    
    for material, keywords in material_keywords.items():
        if any(keyword in url_lower for keyword in keywords):
            materials.append(material)
    
    # Default based on categories
    if not materials:
        if 'kitchen' in url_lower or 'cookware' in url_lower:
            materials = ['steel', 'plastic']
        elif 'furniture' in url_lower:
            materials = ['wood']
        elif 'clothing' in url_lower:
            materials = ['cotton', 'polyester']
        elif 'electronic' in url_lower:
            materials = ['plastic', 'aluminum']
        else:
            materials = ['plastic']
    
    return materials

def estimate_weight(url: str) -> float:
    """Estimate product weight based on URL"""
    url_lower = url.lower()
    
    if 'phone' in url_lower:
        return 0.2
    elif 'laptop' in url_lower:
        return 2.5
    elif 'tablet' in url_lower:
        return 0.5
    elif 'furniture' in url_lower:
        return 15.0
    elif 'clothing' in url_lower:
        return 0.3
    elif 'book' in url_lower:
        return 0.5
    elif 'kitchen' in url_lower:
        return 2.0
    else:
        return 1.0

def calculate_metrics(url: str) -> Dict:
    """Calculate environmental metrics for a product"""
    
    materials = extract_materials_from_url(url)
    weight = estimate_weight(url)
    
    # Calculate emissions
    co2_manufacturing = 0
    water_usage = 0
    recyclability_scores = []
    durability_scores = []
    
    for material in materials:
        if material in MATERIAL_DATABASE:
            data = MATERIAL_DATABASE[material]
            material_weight = weight / len(materials)
            co2_manufacturing += material_weight * data["co2_per_kg"]
            water_usage += material_weight * data["water_per_kg"]
            recyclability_scores.append(data["recyclability"])
            durability_scores.append(data["durability"])
    
    # Transport emissions (simplified)
    co2_transport = weight * 0.5
    co2_total = co2_manufacturing + co2_transport
    
    # Calculate scores
    recyclability = sum(recyclability_scores) / len(recyclability_scores) if recyclability_scores else 50
    durability = sum(durability_scores) / len(durability_scores) if durability_scores else 50
    
    # Eco score
    eco_score = min(100, max(0, 100 - (co2_total * 5)))
    
    # Recommendations
    recommendations = []
    if co2_total > 10:
        recommendations.append("Consider locally-made alternatives")
    if recyclability < 50:
        recommendations.append("Look for products with sustainable materials")
    if eco_score > 70:
        recommendations.append("Good environmental profile!")
    
    # Extract product name
    product_name = "Product"
    if "/dp/" in url:
        parts = url.split("/")
        for i, part in enumerate(parts):
            if part == "dp" and i > 0:
                product_name = parts[i-1].replace("-", " ")[:50].title()
                break
    
    return {
        "product_name": product_name,
        "co2_total": round(co2_total, 2),
        "water_usage": round(water_usage, 2),
        "recyclability": round(recyclability, 1),
        "durability": round(durability, 1),
        "eco_score": round(eco_score, 1),
        "confidence": 70,
        "recommendations": recommendations
    }

@app.get("/")
async def root():
    """API health check"""
    return {
        "status": "active",
        "service": "Environmental Impact Engine",
        "version": "1.0.0",
        "message": "API is running! Use POST /analyze to analyze products"
    }

@app.post("/analyze")
async def analyze_product(request: ProductAnalysisRequest):
    """Analyze a product's environmental impact"""
    
    # Check cache
    cache_key = hashlib.md5(request.url.encode()).hexdigest()
    if request.cache and cache_key in cache:
        result = cache[cache_key]
        result["cached"] = True
        return result
    
    try:
        # Calculate metrics
        metrics = calculate_metrics(request.url)
        
        # Format response
        response = ProductAnalysisResponse(
            product_name=metrics["product_name"],
            environmental_score=EnvironmentalScore(
                co2_total_kg=metrics["co2_total"],
                water_usage_liters=metrics["water_usage"],
                recyclability_score=metrics["recyclability"],
                durability_score=metrics["durability"],
                overall_eco_score=metrics["eco_score"],
                confidence_level=metrics["confidence"]
            ),
            recommendations=metrics["recommendations"],
            cached=False,
            timestamp=datetime.utcnow().isoformat()
        )
        
        # Cache result
        response_dict = response.dict()
        if request.cache:
            cache[cache_key] = response_dict
        
        return response_dict
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)