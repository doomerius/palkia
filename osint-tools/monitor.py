#!/usr/bin/env python3
"""
OSINT Monitor for DOOMERIUS
Tracks digital footprint, exposes, data breaches, domain activity
"""

import requests
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any

class OsintMonitor:
    """Monitor online exposure and threats"""
    
    def __init__(self, email_primary="wmd@palkia.io", domains=None):
        self.email = email_primary
        self.domains = domains or ["palkia.io", "doomerius.dk"]
        self.session = requests.Session()
        self.findings = []
        
    def check_breaches(self) -> List[Dict]:
        """Check if email appears in known data breaches (using haveibeenpwned API)"""
        breaches = []
        try:
            # Free API, no key needed, but needs proper user-agent
            headers = {"User-Agent": "PALKIA-Monitor/1.0"}
            resp = self.session.get(
                f"https://haveibeenpwned.com/api/v3/breachedaccount/{self.email}",
                headers=headers,
                timeout=10
            )
            
            if resp.status_code == 200:
                breaches = resp.json()
            elif resp.status_code == 404:
                breaches = []
            else:
                return [{"error": f"API error {resp.status_code}"}]
                
        except Exception as e:
            return [{"error": str(e)}]
            
        return breaches
    
    def check_domain_reputation(self) -> Dict[str, Any]:
        """Check domain reputation using free APIs"""
        results = {}
        
        for domain in self.domains:
            domain_info = {
                "domain": domain,
                "checks": {}
            }
            
            # Check if domain is in phishing/malware blacklists
            try:
                resp = requests.get(
                    f"https://api.abuseipdb.com/api/v2/check",
                    params={"domain": domain},
                    timeout=10
                )
                if resp.status_code == 200:
                    domain_info["checks"]["abuseipdb"] = resp.json()
            except:
                pass
            
            # Basic DNS check
            try:
                import socket
                ip = socket.gethostbyname(domain)
                domain_info["ip"] = ip
                domain_info["checks"]["dns_resolves"] = True
            except:
                domain_info["checks"]["dns_resolves"] = False
            
            results[domain] = domain_info
            
        return results
    
    def check_social_footprint(self, handles: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        Check for mentions across social platforms
        handles: {"twitter": ["handle1"], "github": ["handle1"], "mastodon": ["handle@instance"]}
        """
        results = {}
        
        # This would require platform-specific APIs
        # For now, return structure for future expansion
        results["twitter"] = {"requires_auth": True, "endpoints": ["search/tweets", "account/info"]}
        results["github"] = {"check": "public repos and profile"}
        results["mastodon"] = {"check": "public posts and interactions"}
        
        return results
    
    def monitor_dns_changes(self, domain: str, baseline: Dict = None) -> Dict[str, Any]:
        """Track DNS record changes for domain"""
        import socket
        import dns.resolver
        
        current = {}
        changes = []
        
        try:
            # A records
            for rdata in dns.resolver.resolve(domain, 'A'):
                current.setdefault('A', []).append(str(rdata))
            
            # MX records
            for rdata in dns.resolver.resolve(domain, 'MX'):
                current.setdefault('MX', []).append(str(rdata))
            
            # TXT records (includes SPF, DKIM, etc)
            try:
                for rdata in dns.resolver.resolve(domain, 'TXT'):
                    current.setdefault('TXT', []).append(str(rdata))
            except:
                pass
                
        except Exception as e:
            return {"error": str(e)}
        
        # Compare to baseline
        if baseline:
            for record_type, records in current.items():
                if record_type not in baseline or baseline[record_type] != records:
                    changes.append({
                        "type": record_type,
                        "before": baseline.get(record_type, []),
                        "after": records,
                        "changed_at": datetime.now().isoformat()
                    })
        
        return {"current": current, "changes": changes}
    
    def scan_exposed_credentials(self) -> List[Dict]:
        """Scan for exposed credentials in public GitHub, pastebin, etc"""
        results = []
        
        # This requires GitHub API + GitHub token to search
        # Or use specializes services like GitGuardian
        # For now, return structure
        
        return {
            "github_search": "requires_github_token",
            "gitguardian": "requires_api_key",
            "pastebin": "requires_scraping"
        }
    
    def generate_report(self) -> str:
        """Generate security report"""
        report = []
        report.append(f"=== OSINT MONITOR REPORT ===\n")
        report.append(f"Generated: {datetime.now().isoformat()}\n")
        report.append(f"Primary Email: {self.email}\n")
        report.append(f"Monitored Domains: {', '.join(self.domains)}\n\n")
        
        # Breaches
        report.append("--- DATA BREACHES ---\n")
        breaches = self.check_breaches()
        if breaches and "error" not in breaches[0]:
            for breach in breaches:
                report.append(f"⚠️  {breach.get('Name')} - {breach.get('BreachDate')}\n")
                report.append(f"   Affected: {breach.get('PwnCount')} accounts\n")
                report.append(f"   Data: {', '.join(breach.get('DataClasses', []))}\n")
        else:
            report.append("✓ No known breaches found\n")
        
        report.append("\n--- DOMAIN REPUTATION ---\n")
        domain_rep = self.check_domain_reputation()
        for domain, info in domain_rep.items():
            report.append(f"{domain}: {json.dumps(info, indent=2)}\n")
        
        return "".join(report)

if __name__ == "__main__":
    monitor = OsintMonitor()
    print(monitor.generate_report())
