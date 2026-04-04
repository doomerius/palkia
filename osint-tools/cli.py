#!/usr/bin/env python3
"""
PALKIA OSINT CLI
Unified command-line interface for security monitoring
"""

import click
import json
import sys
from datetime import datetime
from pathlib import Path

# Import local modules
from monitor import OsintMonitor
from threat_intel import ThreatIntel
from personal_brand import PersonalBrandMonitor

class Config:
    """Configuration for OSINT monitor"""
    
    def __init__(self, config_file=None):
        self.config_file = config_file or Path.home() / ".palkia" / "osint-config.json"
        self.config = self.load_config()
    
    def load_config(self):
        """Load config from file"""
        if self.config_file.exists():
            with open(self.config_file) as f:
                return json.load(f)
        return self.default_config()
    
    def default_config(self):
        return {
            "email": "wmd@palkia.io",
            "domains": ["palkia.io", "doomerius.dk"],
            "aliases": ["doomerius", "palkia"],
            "monitoring_enabled": True
        }
    
    def save(self):
        """Save config to file"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)

@click.group()
@click.version_option()
def cli():
    """PALKIA OSINT - Security monitoring and threat intelligence"""
    pass

@cli.command()
@click.option('--email', default=None, help='Primary email to monitor')
@click.option('--format', type=click.Choice(['text', 'json']), default='text')
def check_breaches(email, format):
    """Check if email appears in known data breaches"""
    
    config = Config().config
    email = email or config['email']
    
    click.echo(f"Checking {email} for data breaches...")
    monitor = OsintMonitor(email)
    breaches = monitor.check_breaches()
    
    if format == 'json':
        click.echo(json.dumps(breaches, indent=2))
    else:
        if breaches and "error" not in breaches[0]:
            click.echo(f"⚠️  Found in {len(breaches)} breaches:")
            for breach in breaches:
                click.echo(f"  - {breach.get('Name')} ({breach.get('BreachDate')})")
                click.echo(f"    Data: {', '.join(breach.get('DataClasses', []))}")
        else:
            click.echo("✓ No breaches found")

@cli.command()
@click.option('--format', type=click.Choice(['text', 'json']), default='text')
def check_reputation(format):
    """Check domain reputation"""
    
    config = Config().config
    monitor = OsintMonitor(
        email=config['email'],
        domains=config['domains']
    )
    
    reputation = monitor.check_domain_reputation()
    
    if format == 'json':
        click.echo(json.dumps(reputation, indent=2))
    else:
        for domain, info in reputation.items():
            click.echo(f"\n{domain}:")
            if info.get('ip'):
                click.echo(f"  IP: {info['ip']}")
            for check, result in info.get('checks', {}).items():
                if isinstance(result, bool):
                    symbol = "✓" if result else "✗"
                    click.echo(f"  {symbol} {check}")

@cli.command()
def monitor_brand():
    """Monitor personal brand mentions"""
    
    config = Config().config
    monitor = PersonalBrandMonitor(
        name="DOOMERIUS",
        aliases=config['aliases']
    )
    
    click.echo(monitor.generate_brand_report())

@cli.command()
def threat_intel():
    """Generate threat intelligence report"""
    
    intel = ThreatIntel()
    click.echo(intel.generate_threat_report())

@cli.command()
@click.option('--full', is_flag=True, help='Run all checks')
def security_report(full):
    """Generate full security report"""
    
    config = Config().config
    
    click.echo("=== PALKIA SECURITY REPORT ===\n")
    click.echo(f"Generated: {datetime.now().isoformat()}\n")
    
    # Breaches
    click.echo("--- BREACHES ---")
    monitor = OsintMonitor(config['email'], config['domains'])
    breaches = monitor.check_breaches()
    if breaches and "error" not in str(breaches[0]):
        click.echo(f"⚠️  Email in {len(breaches)} breaches")
    else:
        click.echo("✓ No breaches")
    
    # Domain reputation
    click.echo("\n--- DOMAIN REPUTATION ---")
    rep = monitor.check_domain_reputation()
    for domain in config['domains']:
        if domain in rep:
            click.echo(f"✓ {domain}")
    
    # Brand mentions
    click.echo("\n--- BRAND MONITORING ---")
    brand = PersonalBrandMonitor("DOOMERIUS", config['aliases'])
    mentions = brand.search_mentions()
    total_mentions = sum(len(m) for m in mentions.values() if isinstance(m, list))
    click.echo(f"Found {total_mentions} recent mentions")
    
    # Threat intel
    click.echo("\n--- THREAT INTEL ---")
    intel = ThreatIntel()
    if intel.alerts:
        click.echo(f"⚠️  {len(intel.alerts)} alerts")
    else:
        click.echo("✓ No critical alerts")

@cli.command()
@click.option('--email', prompt='Email to monitor')
@click.option('--domain', multiple=True, prompt='Domain to monitor')
@click.option('--alias', multiple=True, prompt='Name aliases')
def configure(email, domain, alias):
    """Configure OSINT monitoring"""
    
    config = Config()
    config.config['email'] = email
    config.config['domains'] = list(domain) if domain else config.config['domains']
    config.config['aliases'] = list(alias) if alias else config.config['aliases']
    config.save()
    
    click.echo("✓ Configuration saved")
    click.echo(json.dumps(config.config, indent=2))

@cli.command()
def status():
    """Show monitoring status"""
    
    config = Config()
    click.echo("=== OSINT Monitor Status ===\n")
    click.echo(f"Email: {config.config['email']}")
    click.echo(f"Domains: {', '.join(config.config['domains'])}")
    click.echo(f"Aliases: {', '.join(config.config['aliases'])}")
    click.echo(f"Monitoring: {'Enabled' if config.config.get('monitoring_enabled') else 'Disabled'}")

if __name__ == '__main__':
    cli()
