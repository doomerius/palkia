#!/usr/bin/env python3
"""
Personal Brand Monitor
Tracks mentions across web, monitors reputation, manages digital identity
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Any
from urllib.parse import quote

class PersonalBrandMonitor:
    """Monitor and protect personal brand online"""
    
    def __init__(self, name="DOOMERIUS", aliases=None):
        self.name = name
        self.aliases = aliases or ["doomerius", "Palkia"]
        self.mentions = []
    
    def search_mentions(self) -> Dict[str, List[Dict]]:
        """Search for mentions across web"""
        
        results = {
            "reddit": self._search_reddit(),
            "twitter": self._search_twitter(),
            "hackernews": self._search_hackernews(),
            "github": self._search_github(),
            "pastebin": self._search_pastebin()
        }
        
        return results
    
    def _search_reddit(self) -> List[Dict]:
        """Search Reddit mentions"""
        mentions = []
        
        for alias in self.aliases:
            try:
                resp = requests.get(
                    "https://www.reddit.com/search.json",
                    params={"q": alias, "sort": "new", "t": "week"},
                    headers={"User-Agent": "PALKIA-Monitor/1.0"},
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for post in data.get('data', {}).get('children', [])[:5]:
                        mentions.append({
                            "platform": "reddit",
                            "alias": alias,
                            "title": post['data'].get('title', ''),
                            "url": post['data'].get('url', ''),
                            "score": post['data'].get('score', 0),
                            "author": post['data'].get('author', ''),
                            "timestamp": post['data'].get('created_utc', '')
                        })
            except Exception as e:
                print(f"Reddit search failed: {e}")
        
        return mentions
    
    def _search_twitter(self) -> List[Dict]:
        """Search Twitter mentions (requires Twitter API)"""
        
        # Would use Twitter v2 API with proper auth
        return [{"note": "Requires Twitter API key"}]
    
    def _search_hackernews(self) -> List[Dict]:
        """Search HackerNews mentions"""
        mentions = []
        
        for alias in self.aliases:
            try:
                resp = requests.get(
                    f"https://hn.algolia.com/api/v1/search",
                    params={"query": alias, "type": "all"},
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get('hits', [])[:5]:
                        mentions.append({
                            "platform": "hackernews",
                            "alias": alias,
                            "title": item.get('title', item.get('comment_text', '')[:100]),
                            "url": item.get('url', f"https://news.ycombinator.com/item?id={item.get('objectID')}"),
                            "author": item.get('author', ''),
                            "timestamp": item.get('created_at', ''),
                            "type": item.get('type', '')
                        })
            except Exception as e:
                print(f"HN search failed: {e}")
        
        return mentions
    
    def _search_github(self) -> List[Dict]:
        """Search GitHub mentions and contributions"""
        mentions = []
        
        for alias in self.aliases:
            try:
                resp = requests.get(
                    "https://api.github.com/search/users",
                    params={"q": alias},
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for user in data.get('items', [])[:3]:
                        mentions.append({
                            "platform": "github",
                            "alias": alias,
                            "username": user.get('login', ''),
                            "profile": user.get('html_url', ''),
                            "repos": user.get('public_repos', 0),
                            "followers": user.get('followers', 0)
                        })
            except Exception as e:
                print(f"GitHub search failed: {e}")
        
        return mentions
    
    def _search_pastebin(self) -> List[Dict]:
        """Check Pastebin for pastes (requires Pastebin API)"""
        
        # This requires Pastebin API access
        # Would check for exposed credentials, config files, etc.
        
        return [{"note": "Requires Pastebin scraper or API"}]
    
    def check_reputation(self) -> Dict[str, Any]:
        """Assess overall reputation score"""
        
        reputation = {
            "overall_score": 0,  # 0-100, higher is better
            "sources": {},
            "recommendations": []
        }
        
        # Positive signals
        github_score = 0
        mentions = self.search_mentions()
        
        if mentions.get('github'):
            github_score += 30  # Has public GitHub presence
            reputation['sources']['github'] = "positive"
        
        # Check for negative signals (would integrate with abuse databases)
        reputation['overall_score'] = min(100, github_score + 50)  # Baseline 50
        
        # Generate recommendations
        if reputation['overall_score'] < 70:
            reputation['recommendations'].append("Increase public contributions")
        
        if not mentions.get('twitter'):
            reputation['recommendations'].append("Consider Twitter presence for visibility")
        
        return reputation
    
    def monitor_impersonation(self) -> Dict[str, Any]:
        """Check for account impersonation"""
        
        findings = {
            "accounts_found": [],
            "suspicious_accounts": [],
            "impersonations": []
        }
        
        # Check GitHub, Twitter, etc. for similar usernames
        # Flag accounts that might be impersonating
        
        return findings
    
    def generate_brand_report(self) -> str:
        """Generate personal brand health report"""
        
        report = []
        report.append("=== PERSONAL BRAND REPORT ===\n")
        report.append(f"Generated: {datetime.now().isoformat()}\n")
        report.append(f"Name: {self.name}\n")
        report.append(f"Aliases: {', '.join(self.aliases)}\n\n")
        
        # Reputation
        rep = self.check_reputation()
        report.append(f"Reputation Score: {rep['overall_score']}/100\n\n")
        
        # Mentions
        report.append("=== RECENT MENTIONS ===\n")
        mentions = self.search_mentions()
        
        for platform, items in mentions.items():
            if items and "note" not in str(items[0]):
                report.append(f"\n{platform.upper()}:\n")
                for mention in items[:3]:
                    report.append(f"  - {mention.get('title', mention.get('username', ''))[:80]}\n")
        
        # Impersonation
        report.append("\n=== IMPERSONATION CHECK ===\n")
        impersonation = self.monitor_impersonation()
        if impersonation['impersonations']:
            report.append("⚠️  Potential impersonations detected\n")
        else:
            report.append("✓ No impersonations detected\n")
        
        return "".join(report)

if __name__ == "__main__":
    monitor = PersonalBrandMonitor("DOOMERIUS", ["doomerius", "Palkia"])
    print(monitor.generate_brand_report())
