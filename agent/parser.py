import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup

class LeadWebParser:
    """Web content parser to deeply extract representative products and prices."""
    
    PRICE_REGEX = re.compile(r'(?:£|GBP\s*)(\d+(?:\.\d{2})?)', re.IGNORECASE)

    def extract_products(self, html_content: str) -> List[Dict[str, Any]]:
        """Extract representative products and their prices from HTML content."""
        soup = BeautifulSoup(html_content, 'html.parser')
        products = []

        # Extract through common product card selectors
        product_cards = soup.find_all(class_=re.compile(r'product|item|card', re.I))
        for card in product_cards:
            text = card.get_text()
            price_match = self.PRICE_REGEX.search(text)
            if price_match:
                title_elem = card.find(['h2', 'h3', 'h4', 'a', 'span'], class_=re.compile(r'title|name', re.I))
                name = title_elem.get_text(strip=True) if title_elem else "Retail Product"
                price = float(price_match.group(1))
                if price > 0:
                    products.append({"name": name[:50], "price": price, "currency": "GBP"})
            if len(products) >= 5:
                break

        # Fallback: regex search across the raw body text
        if not products:
            matches = self.PRICE_REGEX.finditer(html_content)
            for m in matches:
                price = float(m.group(1))
                if 5.0 <= price <= 500.0:
                    products.append({"name": "Discovered Item", "price": price, "currency": "GBP"})
                if len(products) >= 3:
                    break

        return products

    def parse_page(self, html_content: str) -> Dict[str, Any]:
        """Main entry point for parsing page content."""
        products = self.extract_products(html_content)
        return {
            "representative_products": products,
            "has_products": len(products) > 0
        }
