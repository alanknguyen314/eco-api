"""
Environmental Engine API - Production Ready Version
Simplified for immediate deployment on Render/Railway/Replit
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict
import json
import hashlib
import re

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

# Simplified material database (no external dependencies)
MATERIAL_DATABASE = {
    "steel": {"co2_per_kg": 2.0, "water_per_kg": 50, "recyclability": 90, "durability": 95},
    "aluminum": {"co2_per_kg": 8.0, "water_per_kg": 100, "recyclability": 95, "durability": 90},
    "plastic": {"co2_per_kg": 3.0, "water_per_kg": 20, "recyclability": 30, "durability": 60},
    "wood": {"co2_per_kg": 0.5, "water_per_kg": 10, "recyclability": 70, "durability": 70},
    "cotton": {"co2_per_kg": 5.0, "water_per_kg": 10000, "recyclability": 60, "durability": 50},
    "polyester": {"co2_per_kg": 6.0, "water_per_kg": 60, "recyclability": 20, "durability": 70},
    "glass": {"co2_per_kg": 1.0, "water_per_kg": 15, "recyclability": 100, "durability": 80},
    "ceramic": {"co2_per_kg": 0.8, "water_per_kg": 20, "recyclability": 40, "durability": 85},
    "leather": {"co2_per_kg": 17.0, "water_per_kg": 17000, "recyclability": 20, "durability": 90},
    "paper": {"co2_per_kg": 1.2, "water_per_kg": 30, "recyclability": 80, "durability": 30},
    "rubber": {"co2_per_kg": 3.0, "water_per_kg": 40, "recyclability": 50, "durability": 70}
}

TRANSPORT_DISTANCES = {
    "China": 10000,
    "India": 8000,
    "Vietnam": 10000,
    "USA": 1000,
    "Germany": 1000,
    "Mexico": 2000,
    "Unknown": 5000
}

# Simple in-memory cache
cache = {}

# Request/Response Models
class ProductAnalysisRequest(BaseModel):
    url: str
    detailed: bool = False
    cache: bool = True

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
    cached: bool = False
    timestamp: str

def extract_materials_from_url(url: str) -> List[str]:
    """Extract potential materials from product URL and title"""
    materials = []
    url_lower = url.lower()
    
    # Simple keyword matching
    material_keywords = {
        'steel': ['steel', 'metal', 'iron', 'stainless'],
        'aluminum': ['aluminum', 'aluminium'],
        'plastic': ['plastic', 'polypropylene', 'pp', 'polyethylene', 'pe', 'pet', 'abs'],
        'wood': ['wood', 'wooden', 'bamboo', 'oak', 'pine', 'cedar'],
        'cotton': ['cotton'],
        'polyester': ['polyester', 'synthetic'],
        'glass': ['glass'],
        'ceramic': ['ceramic', 'porcelain'],
        'leather': ['leather'],
        'paper': ['paper', 'cardboard'],
        'rubber': ['rubber', 'silicone']
    }
    
    for material, keywords in material_keywords.items():
        if any(keyword in url_lower for keyword in keywords):
            materials.append(material)
    
    # Default materials based on common Amazon categories
    if not materials:
        if any(x in url_lower for x in ['kitchen', 'cookware', 'utensil']):
            materials = ['steel', 'plastic']
        elif any(x in url_lower for x in ['furniture', 'desk', 'chair', 'table']):
            materials = ['wood', 'steel']
        elif any(x in url_lower for x in ['clothing', 'shirt', 'pants', 'dress']):
            materials = ['cotton', 'polyester']
        elif any(x in url_lower for x in ['electronic', 'computer', 'phone', 'tablet']):
            materials = ['plastic', 'aluminum']
        else:
            materials = ['plastic']  # Default assumption
    
    return materials

def estimate_weight_from_category(url: str) -> float:
    """Estimate product weight based on URL/category"""
    url_lower = url.lower()
    
    # Category-based weight estimates (in kg)
    if any(x in url_lower for x in ['phone', 'smartphone', 'mobile']):
        return 0.2
    elif any(x in url_lower for x in ['laptop', 'notebook', 'computer']):
        return 2.5
    elif any(x in url_lower for x in ['tablet', 'ipad', 'kindle']):
        return 0.5
    elif any(x in url_lower for x in ['furniture', 'desk', 'chair', 'sofa']):
        return 15.0
    elif any(x in url_lower for x in ['clothing', 'shirt', 'pants', 'dress']):
        return 0.3
    elif any(x in url_lower for x in ['book']):
        return 0.5
    elif any(x in url_lower for x in ['kitchen', 'cookware', 'pan', 'pot']):
        return 2.0
    elif any(x in url_lower for x in ['toy', 'game']):
        return 0.5
    else:
        return 1.0  # Default weight

def calculate_environmental_metrics(url: str) -> Dict:
    """Calculate environmental metrics for a product"""
    
    # Extract product info from URL
    materials = extract_materials_from_url(url)
    weight = estimate_weight_from_category(url)
    
    # Determine origin (simplified - in production, would scrape actual data)
    origin = "China" if "import" not in url.lower() else "USA"
    
    # Calculate manufacturing emissions
    co2_manufacturing = 0
    water_usage = 0
    recyclability_scores = []
    durability_scores = []
    
    weight_per_material = weight / len(materials) if materials else weight
    
    for material in materials:
        if material in MATERIAL_DATABASE:
            mat_data = MATERIAL_DATABASE[material]
            co2_manufacturing += weight_per_material * mat_data["co2_per_kg"]
            water_usage += weight_per_material * mat_data["water_per_kg"]
            recyclability_scores.append(mat_data["recyclability"])
            durability_scores.append(mat_data["durability"])
        else:
            # Default values for unknown materials
            co2_manufacturing += weight_per_material * 3.0
            water_usage += weight_per_material * 50
            recyclability_scores.append(50)
            durability_scores.append(50)
    
    # Add manufacturing overhead
    co2_manufacturing *= 1.2
    
    # Calculate transport emissions
    distance = TRANSPORT_DISTANCES.get(origin, 5000)
    co2_transport = weight * distance * 0.00001 * 10  # Simplified calculation
    
    # Calculate scores
    co2_total = co2_manufacturing + co2_transport
    recyclability = sum(recyclability_scores) / len(recyclability_scores) if recyclability_scores else 50
    durability = sum(durability_scores) / len(durability_scores) if durability_scores else 50
    
    # Overall eco score (0-100, higher is better)
    co2_score = max(0, 100 - (co2_total * 5))
    water_score = max(0, 100 - (water_usage / 100))
    eco_score = (co2_score * 0.4 + water_score * 0.2 + recyclability * 0.2 + durability * 0.2)
    
    # Confidence level (based on how much we could extract)
    confidence = 60 if materials else 30
    if weight != 1.0:  # Not default weight
        confidence += 20
    if origin != "Unknown":
        confidence += 20
    
    # Generate recommendations
    recommendations = []
    if co2_total > 10:
        recommendations.append("High carbon footprint - consider locally-made alternatives")
    if recyclability < 50:
        recommendations.append("Low recyclability - look for products with sustainable materials")
    if durability < 60:
        recommendations.append("May need frequent replacement - consider higher quality options")
    if eco_score > 70:
        recommendations.append("Good environmental profile! This is a relatively eco-friendly choice")
    elif eco_score < 40:
        recommendations.append("Consider searching for more sustainable alternatives")
    
    # Extract product name from URL
    product_name = "Product"
    if "/dp/" in url:
        # Try to extract from Amazon URL pattern
        parts = url.split("/")
        for i, part in enumerate(parts):
            if part == "dp" and i > 0:
                name_part = parts[i-1].replace("-", " ")
                product_name = name_part[:50].title() if name_part else "Product"
                break
    
    return {
        "product_name": product_name,
        "materials": materials,
        "weight": weight,
        "origin": origin,
        "co2_manufacturing": round(co2_manufacturing, 2),
        "co2_transport": round(co2_transport, 2),
        "co2_total": round(co2_total, 2),
        "water_usage": round(water_usage, 2),
        "recyclability": round(recyclability, 1),
        "durability": round(durability, 1),
        "eco_score": round(eco_score, 1),
        "confidence": confidence,
        "recommendations": recommendations
    }

# API Endpoints
@app.get("/")
async def root():
    """API health check and info"""
    return {
        "status": "active",
        "service": "Environmental Impact Engine",
        "version": "1.0.0",
        "endpoints": [
            "/analyze",
            "/materials",
            "/docs"
        ],
        "message": "API is running! Use /docs for interactive documentation"
    }

@app.post("/analyze")
async def analyze_product(request: ProductAnalysisRequest):
    """Analyze a single product's environmental impact"""
    
    # Check cache
    cache_key = hashlib.md5(request.url.encode()).hexdigest()
    if request.cache and cache_key in cache:
        cached_result = cache[cache_key].copy()
        cached_result["cached"] = True
        return cached_result
    
    try:
        # Calculate metrics
        metrics = calculate_environmental_metrics(request.url)
        
        # Format response
        from datetime import datetime
        response = {
            "product_name": metrics["product_name"],
            "environmental_score": {
                "co2_total_kg": metrics["co2_total"],
                "water_usage_liters": metrics["water_usage"],
                "recyclability_score": metrics["recyclability"],
                "durability_score": metrics["durability"],
                "overall_eco_score": metrics["eco_score"],
                "confidence_level": metrics["confidence"]
            },
            "recommendations": metrics["recommendations"],
            "cached": False,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add detailed info if requested
        if request.detailed:
            response["details"] = {
                "materials": metrics["materials"],
                "estimated_weight_kg": metrics["weight"],
                "origin": metrics["origin"],
                "co2_breakdown": {
                    "manufacturing": metrics["co2_manufacturing"],
                    "transport": metrics["co2_transport"]
                }
            }
        
        # Cache result
        if request.cache:
            cache[cache_key] = response
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/materials")
async def get_materials_database():
    """Get the materials database for reference"""
    return {
        "materials": MATERIAL_DATABASE,
        "info": "CO2 in kg per kg of material, water in liters per kg"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy"}

# For running locally
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
