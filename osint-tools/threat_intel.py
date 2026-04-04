#!/usr/bin/env python3
"""
Threat Intelligence Aggregator
Pulls from open-source threat feeds, correlates, alerts on threats
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
import hashlib

class ThreatIntel:
    """Aggregate threat intelligence from public sources"""
    
    def __init__(self):
        self.sources = {
            "abuse_ipdb": "https://api.abuseipdb.com/api/v2",
            "urlhaus": "https://urlhaus-api.abuse.ch/v1",
            "otx": "https://otx.alienvault.com/api/v1",
            "threatmaps": "https://www.abuseipdb.com/threatmaps"
        }
        self.alerts = []
    
    def check_ip_reputation(self, ip: str, min_abuse_score=50) -> Dict[str, Any]:
        """Check IP reputation across multiple sources"""
        
        result = {
            "ip": ip,
            "sources": {},
            "risk_level": "unknown"
        }
        
        # Check AbuseIPDB (requires free API key or quota)
        try:
            resp = requests.get(
                f"{self.sources['abuse_ipdb']}/check",
                params={"ipAddress": ip, "maxAgeInDays": 90},
                headers={"Key": "ABUSEIPDB_KEY"},  # Would be set from env
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json().get('data', {})
                result['sources']['abuseipdb'] = {
                    "score": data.get('abuseConfidenceScore', 0),
                    "reports": data.get('totalReports', 0),
                    "is_whitelisted": data.get('isWhitelisted', False)
                }
        except:
            pass
        
        # Determine risk level
        if result['sources'].get('abuseipdb', {}).get('score', 0) > min_abuse_score:
            result['risk_level'] = 'HIGH'
            self.alerts.append({
                "type": "ip_reputation",
                "severity": "HIGH",
                "ip": ip,
                "timestamp": datetime.now().isoformat()
            })
        
        return result
    
    def check_malware_urls(self, domains: List[str]) -> Dict[str, Any]:
        """Check domains against malware/phishing databases"""
        
        results = {}
        
        for domain in domains:
            domain_result = {
                "domain": domain,
                "malware": False,
                "phishing": False,
                "sources": []
            }
            
            # URLhaus check
            try:
                resp = requests.get(
                    f"{self.sources['urlhaus']}/host/",
                    params={"host": domain},
                    timeout=5
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('query_status') == 'ok' and data.get('urls'):
                        domain_result['malware'] = True
                        domain_result['sources'].append('urlhaus')
                        for url_data in data['urls'][:3]:  # Top 3
                            self.alerts.append({
                                "type": "malware_url",
                                "severity": "CRITICAL",
                                "domain": domain,
                                "url": url_data.get('url'),
                                "timestamp": datetime.now().isoformat()
                            })
            except:
                pass
            
            results[domain] = domain_result
        
        return results
    
    def scan_c2_servers(self, ip_list: List[str]) -> Dict[str, List[Dict]]:
        """Scan for known C2 (command & control) server IPs"""
        
        # This would integrate with feeds like:
        # - Feodo Tracker
        # - URLhaus C2 list
        # - abuse.ch lists
        
        c2_findings = []
        
        for ip in ip_list:
            # Check against known C2 IPs (would use abuse.ch feeds)
            c2_findings.append({
                "ip": ip,
                "is_c2": False,  # Placeholder
                "family": None
            })
        
        return {"c2_servers": c2_findings}
    
    def track_threat_actors(self, indicators: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        Track threat actors based on TTPs and indicators
        indicators: {
            "domains": [...],
            "ips": [...],
            "file_hashes": [...]
        }
        """
        
        findings = {
            "actor_matches": [],
            "ttps": [],
            "campaigns": []
        }
        
        # Would correlate with MITRE ATT&CK framework
        # and threat reports
        
        return findings
    
    def get_threat_feeds(self) -> Dict[str, List[str]]:
        """Get curated list of threat feeds and their update status"""
        
        feeds = {
            "malwaredomains": "https://www.malwaredomains.com/",
            "phishtank": "https://www.phishtank.com/",
            "abuse_ch": "https://abuse.ch/",
            "mitre_attack": "https://attack.mitre.org/",
            "nvd": "https://nvd.nist.gov/",
            "cert": "https://www.cert.org/",
            "shadowserver": "https://www.shadowserver.org/"
        }
        
        return feeds
    
    def generate_threat_report(self) -> str:
        """Generate consolidated threat intelligence report"""
        
        report = []
        report.append("=== THREAT INTELLIGENCE REPORT ===\n")
        report.append(f"Generated: {datetime.now().isoformat()}\n\n")
        
        if self.alerts:
            report.append("⚠️  ALERTS\n")
            for alert in self.alerts:
                report.append(f"[{alert['severity']}] {alert['type']}: {alert.get('ip', alert.get('domain', 'unknown'))}\n")
        else:
            report.append("✓ No critical alerts\n")
        
        report.append("\nAvailable Threat Feeds:\n")
        for feed, url in self.get_threat_feeds().items():
            report.append(f"- {feed}: {url}\n")
        
        return "".join(report)

if __name__ == "__main__":
    intel = ThreatIntel()
    print(intel.generate_threat_report())
