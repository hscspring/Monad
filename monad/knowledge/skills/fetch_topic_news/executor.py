def run(**kwargs):
    import requests
    from bs4 import BeautifulSoup
    import json
    from datetime import datetime
    
    topic = kwargs.get('topic', '')
    if not topic:
        return {"error": "Topic is required"}
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Search Bing for news about the topic
    search_url = f"https://www.bing.com/news/search?q={requests.utils.quote(topic)}&qft=+filterui:dateautn-1m"
    
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        news_items = []
        articles = soup.find_all('div', class_='news-card')[:10]
        
        for article in articles:
            try:
                title_elem = article.find('a', class_='title')
                source_elem = article.find('div', class_='source')
                
                if title_elem:
                    news_items.append({
                        "title": title_elem.get_text(strip=True),
                        "url": title_elem.get('href', ''),
                        "source": source_elem.get_text(strip=True) if source_elem else "Unknown"
                    })
            except Exception:
                continue
        
        return {
            "topic": topic,
            "count": len(news_items),
            "news": news_items,
            "timestamp": datetime.now().isoformat()
        }
        
    except requests.RequestException as e:
        return {"error": f"Failed to fetch news: {str(e)}"}
