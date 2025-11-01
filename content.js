// content.js - Main content script for the browser extension
// Injects environmental impact information into Amazon product pages

const API_BASE_URL = 'http://localhost:8000'; // Change to your deployed API URL

// Utility functions
function createEcoWidget(data) {
    const widget = document.createElement('div');
    widget.id = 'eco-impact-widget';
    widget.innerHTML = `
        <div class="eco-widget-container">
            <div class="eco-header">
                <h3>🌱 Environmental Impact</h3>
                <span class="eco-confidence">Confidence: ${data.confidence_level}%</span>
            </div>
            
            <div class="eco-metrics">
                <div class="eco-metric">
                    <div class="metric-icon">🏭</div>
                    <div class="metric-content">
                        <div class="metric-value">${data.co2_total_kg} kg</div>
                        <div class="metric-label">CO₂ Emissions</div>
                        <div class="metric-context">${data.co2_equivalent}</div>
                    </div>
                </div>
                
                <div class="eco-metric">
                    <div class="metric-icon">💧</div>
                    <div class="metric-content">
                        <div class="metric-value">${data.water_usage_liters} L</div>
                        <div class="metric-label">Water Usage</div>
                    </div>
                </div>
                
                <div class="eco-metric">
                    <div class="metric-icon">♻️</div>
                    <div class="metric-content">
                        <div class="metric-value">${data.recyclability_score}%</div>
                        <div class="metric-label">Recyclability</div>
                    </div>
                </div>
            </div>
            
            <div class="eco-score-container">
                <div class="eco-score-label">Eco Score</div>
                <div class="eco-score-bar">
                    <div class="eco-score-fill" style="width: ${data.overall_eco_score}%; background: ${getScoreColor(data.overall_eco_score)}">
                        ${data.overall_eco_score}/100
                    </div>
                </div>
            </div>
            
            <div class="eco-recommendations">
                <h4>💡 Recommendations</h4>
                <ul>
                    ${data.recommendations.map(r => `<li>${r}</li>`).join('')}
                </ul>
            </div>
            
            <div class="eco-alternatives">
                <button id="find-eco-alternatives" class="eco-button">
                    Find Greener Alternatives
                </button>
            </div>
            
            <div class="eco-footer">
                <a href="#" id="eco-details-link">View detailed report</a>
                <span class="eco-powered-by">Powered by Upcycle.green</span>
            </div>
        </div>
    `;
    
    // Add CSS styles
    const styles = `
        <style>
            #eco-impact-widget {
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 16px;
                margin: 16px 0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }
            
            .eco-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 16px;
                padding-bottom: 12px;
                border-bottom: 2px solid #4CAF50;
            }
            
            .eco-header h3 {
                margin: 0;
                color: #2e7d32;
                font-size: 18px;
            }
            
            .eco-confidence {
                background: #fff;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                color: #666;
            }
            
            .eco-metrics {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 16px;
                margin-bottom: 20px;
            }
            
            .eco-metric {
                display: flex;
                align-items: center;
                background: white;
                padding: 12px;
                border-radius: 6px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }
            
            .metric-icon {
                font-size: 24px;
                margin-right: 12px;
            }
            
            .metric-value {
                font-size: 18px;
                font-weight: bold;
                color: #333;
            }
            
            .metric-label {
                font-size: 12px;
                color: #666;
                margin-top: 2px;
            }
            
            .metric-context {
                font-size: 11px;
                color: #999;
                margin-top: 4px;
            }
            
            .eco-score-container {
                margin-bottom: 20px;
            }
            
            .eco-score-label {
                font-weight: bold;
                margin-bottom: 8px;
                color: #333;
            }
            
            .eco-score-bar {
                background: #e0e0e0;
                border-radius: 20px;
                height: 30px;
                overflow: hidden;
            }
            
            .eco-score-fill {
                height: 100%;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-weight: bold;
                transition: width 0.5s ease;
            }
            
            .eco-recommendations {
                background: #fff9c4;
                padding: 12px;
                border-radius: 6px;
                margin-bottom: 16px;
            }
            
            .eco-recommendations h4 {
                margin: 0 0 8px 0;
                font-size: 14px;
                color: #f57c00;
            }
            
            .eco-recommendations ul {
                margin: 0;
                padding-left: 20px;
                font-size: 13px;
            }
            
            .eco-recommendations li {
                margin-bottom: 4px;
            }
            
            .eco-button {
                width: 100%;
                background: #4CAF50;
                color: white;
                border: none;
                padding: 12px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                cursor: pointer;
                transition: background 0.3s;
            }
            
            .eco-button:hover {
                background: #45a049;
            }
            
            .eco-footer {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-top: 16px;
                padding-top: 12px;
                border-top: 1px solid #e0e0e0;
                font-size: 12px;
            }
            
            .eco-footer a {
                color: #2e7d32;
                text-decoration: none;
            }
            
            .eco-footer a:hover {
                text-decoration: underline;
            }
            
            .eco-powered-by {
                color: #999;
            }
            
            .eco-loading {
                text-align: center;
                padding: 20px;
                color: #666;
            }
            
            .eco-error {
                background: #ffebee;
                color: #c62828;
                padding: 12px;
                border-radius: 6px;
                margin-bottom: 16px;
            }
        </style>
    `;
    
    document.head.insertAdjacentHTML('beforeend', styles);
    return widget;
}

function getScoreColor(score) {
    if (score >= 70) return '#4CAF50';
    if (score >= 40) return '#FFC107';
    return '#f44336';
}

function createLoadingWidget() {
    const widget = document.createElement('div');
    widget.id = 'eco-impact-widget';
    widget.innerHTML = `
        <div class="eco-widget-container">
            <div class="eco-loading">
                <h3>🌱 Calculating Environmental Impact...</h3>
                <p>Analyzing materials, manufacturing, and transport emissions</p>
            </div>
        </div>
    `;
    return widget;
}

function createErrorWidget(error) {
    const widget = document.createElement('div');
    widget.id = 'eco-impact-widget';
    widget.innerHTML = `
        <div class="eco-widget-container">
            <div class="eco-error">
                <h3>Unable to calculate environmental impact</h3>
                <p>${error}</p>
            </div>
        </div>
    `;
    return widget;
}

// Main function to analyze current product
async function analyzeCurrentProduct() {
    const currentUrl = window.location.href;
    
    // Check if we're on a product page
    if (!currentUrl.includes('/dp/') && !currentUrl.includes('/gp/product/')) {
        return;
    }
    
    // Find insertion point (near the buy box)
    const insertionPoint = document.getElementById('apex_desktop') || 
                          document.getElementById('centerCol') ||
                          document.querySelector('.a-fixed-left-grid-col.a-col-right');
    
    if (!insertionPoint) {
        console.log('Could not find insertion point for eco widget');
        return;
    }
    
    // Remove existing widget if present
    const existingWidget = document.getElementById('eco-impact-widget');
    if (existingWidget) {
        existingWidget.remove();
    }
    
    // Insert loading widget
    insertionPoint.appendChild(createLoadingWidget());
    
    try {
        // Call API to analyze product
        const response = await fetch(`${API_BASE_URL}/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                url: currentUrl,
                detailed: true,
                cache: true
            })
        });
        
        if (!response.ok) {
            throw new Error('API request failed');
        }
        
        const data = await response.json();
        
        // Format data for display
        const displayData = {
            co2_total_kg: data.environmental_score.co2_total_kg.toFixed(1),
            co2_equivalent: `≈ ${(data.environmental_score.co2_total_kg / 2.3).toFixed(1)} miles driven`,
            water_usage_liters: Math.round(data.environmental_score.water_usage_liters),
            recyclability_score: Math.round(data.environmental_score.recyclability_score),
            overall_eco_score: Math.round(data.environmental_score.overall_eco_score),
            confidence_level: Math.round(data.environmental_score.confidence_level),
            recommendations: data.recommendations
        };
        
        // Replace loading widget with data widget
        document.getElementById('eco-impact-widget').remove();
        insertionPoint.appendChild(createEcoWidget(displayData));
        
        // Add event listeners
        setupEventListeners(data);
        
        // Store data for comparison features
        chrome.storage.local.set({
            [currentUrl]: data
        });
        
    } catch (error) {
        console.error('Error analyzing product:', error);
        document.getElementById('eco-impact-widget').remove();
        insertionPoint.appendChild(createErrorWidget('Service temporarily unavailable'));
    }
}

// Setup event listeners for widget interactions
function setupEventListeners(data) {
    // Find alternatives button
    const altButton = document.getElementById('find-eco-alternatives');
    if (altButton) {
        altButton.addEventListener('click', () => {
            findEcoAlternatives(data);
        });
    }
    
    // Details link
    const detailsLink = document.getElementById('eco-details-link');
    if (detailsLink) {
        detailsLink.addEventListener('click', (e) => {
            e.preventDefault();
            showDetailedReport(data);
        });
    }
}

// Find eco-friendly alternatives
async function findEcoAlternatives(currentProduct) {
    // Get product category
    const breadcrumbs = document.querySelector('#wayfinding-breadcrumbs_feature_div');
    const category = breadcrumbs ? breadcrumbs.innerText : 'all';
    
    // Search for alternatives
    const searchQuery = `eco friendly sustainable ${category}`;
    window.location.href = `/s?k=${encodeURIComponent(searchQuery)}`;
}

// Show detailed report in modal
function showDetailedReport(data) {
    // Create modal with full report
    const modal = document.createElement('div');
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0,0,0,0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
    `;
    
    modal.innerHTML = `
        <div style="background: white; padding: 30px; border-radius: 10px; max-width: 600px; max-height: 80vh; overflow-y: auto;">
            <h2>Detailed Environmental Impact Report</h2>
            <pre>${JSON.stringify(data, null, 2)}</pre>
            <button onclick="this.parentElement.parentElement.remove()">Close</button>
        </div>
    `;
    
    document.body.appendChild(modal);
}

// Add comparison feature for search results
function addComparisonToSearchResults() {
    if (!window.location.href.includes('/s?') && !window.location.href.includes('/s/')) {
        return;
    }
    
    const products = document.querySelectorAll('[data-component-type="s-search-result"]');
    
    products.forEach(async (product) => {
        const link = product.querySelector('h2 a');
        if (!link) return;
        
        const productUrl = 'https://www.amazon.com' + link.getAttribute('href');
        
        // Add eco indicator
        const indicator = document.createElement('div');
        indicator.style.cssText = `
            background: #4CAF50;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            margin-top: 8px;
            display: inline-block;
        `;
        indicator.textContent = '🌱 Checking eco impact...';
        
        product.appendChild(indicator);
        
        // Fetch eco score (cached or new)
        try {
            const cached = await chrome.storage.local.get(productUrl);
            if (cached[productUrl]) {
                indicator.textContent = `🌱 Eco Score: ${Math.round(cached[productUrl].environmental_score.overall_eco_score)}/100`;
            } else {
                // Optionally fetch in background
                indicator.textContent = '🌱 Click to view eco impact';
            }
        } catch (error) {
            indicator.style.display = 'none';
        }
    });
}

// Initialize extension
function init() {
    // Check if we're on a product page or search results
    if (window.location.hostname.includes('amazon.com')) {
        analyzeCurrentProduct();
        addComparisonToSearchResults();
        
        // Listen for page changes (Amazon uses AJAX)
        let lastUrl = location.href;
        new MutationObserver(() => {
            const url = location.href;
            if (url !== lastUrl) {
                lastUrl = url;
                setTimeout(() => {
                    analyzeCurrentProduct();
                    addComparisonToSearchResults();
                }, 1000);
            }
        }).observe(document, {subtree: true, childList: true});
    }
}

// Run when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'getProductData') {
        const data = document.getElementById('eco-impact-widget');
        sendResponse({hasData: !!data});
    }
});
