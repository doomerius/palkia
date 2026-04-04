# PALKIA OSINT Tools

Security monitoring and threat intelligence for DOOMERIUS.

## Components

### 1. **monitor.py** - Data Breach & Domain Monitoring
- Check if email appears in known data breaches (haveibeenpwned API)
- Monitor domain reputation
- Track DNS changes for early warning of compromises
- Detect exposed credentials in public sources

### 2. **threat_intel.py** - Threat Intelligence Aggregation
- IP reputation checking (AbuseIPDB, etc.)
- Malware/phishing URL detection (URLhaus, abuse.ch)
- C2 server detection
- Threat actor tracking via TTPs
- Integration with MITRE ATT&CK framework

### 3. **personal_brand.py** - Online Presence Monitoring
- Track mentions across Reddit, Twitter, HackerNews, GitHub
- Monitor for impersonation accounts
- Reputation scoring
- Brand health reports

### 4. **cli.py** - Command-Line Interface
Unified CLI for all monitoring functions:

```bash
# Check if email is in breaches
python cli.py check-breaches --email wmd@palkia.io

# Check domain reputation
python cli.py check-reputation

# Monitor brand mentions
python cli.py monitor-brand

# Generate full security report
python cli.py security-report --full

# Configure monitoring
python cli.py configure

# Show status
python cli.py status
```

## Setup

### Requirements
```bash
pip install click requests dnspython
```

### Optional (for enhanced features)
```bash
pip install GitGuardian  # Credential detection
pip install twitter-api  # Twitter integration
pip install python-nessus  # Vulnerability scanning
```

### Initial Configuration
```bash
python cli.py configure
# Enter email, domains, aliases
```

## Integration with n8n

These tools integrate with n8n workflows for automated monitoring:

1. **Daily Brand Monitor** - runs `personal_brand.py`, saves findings to memory
2. **Weekly Threat Report** - aggregates findings, sends summary email
3. **Breach Alert** - notifies immediately if new breach detected

## Security Notes

- Never commit API keys — use environment variables
- Breach checking uses haveibeenpwned's free API (public, anonymous)
- Some features require API keys for:
  - AbuseIPDB (IP reputation)
  - Twitter API (mention tracking)
  - GitHub API (optional, for higher rate limits)

## Future Enhancements

- [ ] Port scanning & vulnerability assessment
- [ ] SSL/TLS certificate monitoring
- [ ] Email security (DMARC/SPF/DKIM checking)
- [ ] OAuth app audit (connected apps)
- [ ] DNS hijacking detection
- [ ] BGP hijacking alerts
- [ ] Real-time alerting via Telegram
- [ ] Historical trend analysis
- [ ] AI-powered anomaly detection

## Usage Flow

```
Daily (automated via n8n):
1. Check for data breaches
2. Monitor domain reputation
3. Track brand mentions
4. Check threat feeds

Weekly:
- Generate consolidated report
- Identify trends
- Update security posture
- Send summary to DOOMERIUS

On-demand:
- Run specific checks via CLI
- Generate reports
- Investigate alerts
```

## Contact & Support

Part of the PALKIA infrastructure for protecting DOOMERIUS's digital footprint.
