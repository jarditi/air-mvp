#!/usr/bin/env python3
"""
Test Script for Email Contact Filtering Service (Task 2.5.4)

This script demonstrates the metadata-only email contact filtering functionality
with two-way validation, professional scoring, and spam detection.

Features tested:
- Email contact extraction and filtering
- Two-way communication validation  
- Professional contact scoring
- Spam and automation detection
- Contact quality validation
- Cold outreach suggestions
- Service health monitoring
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any

import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# Setup logging and console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
console = Console()

# Test configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

# Test data
TEST_INTEGRATION_ID = "test-gmail-integration-123"
TEST_CONTACT_EMAIL = "test@example.com"


class EmailContactFilteringTester:
    """Test class for email contact filtering service"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.auth_headers = {
            "Authorization": "Bearer test-token",
            "Content-Type": "application/json"
        }
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def test_service_health(self) -> Dict[str, Any]:
        """Test email contact filtering service health"""
        console.print("\n🏥 [bold blue]Testing Email Contact Filtering Service Health[/bold blue]")
        
        try:
            response = await self.client.get(
                f"{API_BASE}/email-contacts/health",
                headers=self.auth_headers
            )
            
            if response.status_code == 200:
                data = response.json()
                console.print("✅ Service health check passed")
                
                # Display health information
                health_table = Table(title="Service Health Status")
                health_table.add_column("Property", style="cyan")
                health_table.add_column("Value", style="green")
                
                health_data = data.get('data', {})
                health_table.add_row("Status", health_data.get('status', 'unknown'))
                health_table.add_row("Service", health_data.get('service_name', 'unknown'))
                health_table.add_row("Version", health_data.get('version', 'unknown'))
                health_table.add_row("Features", str(len(health_data.get('features_available', []))))
                health_table.add_row("Last Check", health_data.get('last_check', 'unknown'))
                
                console.print(health_table)
                
                # Display available features
                features = health_data.get('features_available', [])
                if features:
                    console.print(f"\n📋 Available Features: {', '.join(features)}")
                
                return data
            else:
                console.print(f"❌ Health check failed: {response.status_code}")
                return {"error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            console.print(f"❌ Health check error: {e}")
            return {"error": str(e)}
    
    async def test_email_contact_extraction(self) -> Dict[str, Any]:
        """Test email contact extraction and filtering"""
        console.print("\n📧 [bold blue]Testing Email Contact Extraction[/bold blue]")
        
        try:
            # Test extraction request
            extraction_request = {
                "integration_id": TEST_INTEGRATION_ID,
                "days_back": 90,
                "max_messages": 500,
                "min_message_count": 2,
                "require_two_way": True
            }
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Extracting email contacts...", total=None)
                
                response = await self.client.post(
                    f"{API_BASE}/email-contacts/extract",
                    headers=self.auth_headers,
                    json=extraction_request
                )
                
                progress.update(task, completed=True)
            
            if response.status_code == 200:
                data = response.json()
                console.print("✅ Email contact extraction completed")
                
                # Display extraction results
                result_data = data.get('data', {})
                
                results_table = Table(title="Email Contact Extraction Results")
                results_table.add_column("Metric", style="cyan")
                results_table.add_column("Count", style="green")
                results_table.add_column("Description", style="yellow")
                
                results_table.add_row(
                    "Contacts Analyzed", 
                    str(result_data.get('contacts_analyzed', 0)),
                    "Total unique contacts found in emails"
                )
                results_table.add_row(
                    "Contacts Extracted", 
                    str(result_data.get('contacts_extracted', 0)),
                    "Contacts meeting quality criteria"
                )
                results_table.add_row(
                    "Two-Way Validated", 
                    str(result_data.get('two_way_validated', 0)),
                    "Contacts with bidirectional communication"
                )
                results_table.add_row(
                    "Professional Contacts", 
                    str(result_data.get('professional_contacts', 0)),
                    "Contacts with professional indicators"
                )
                results_table.add_row(
                    "Automated Filtered", 
                    str(result_data.get('automated_filtered', 0)),
                    "Automated senders removed"
                )
                results_table.add_row(
                    "Spam Filtered", 
                    str(result_data.get('spam_filtered', 0)),
                    "Spam contacts removed"
                )
                results_table.add_row(
                    "Processing Time", 
                    f"{result_data.get('processing_time_seconds', 0):.2f}s",
                    "Time taken for analysis"
                )
                
                console.print(results_table)
                
                # Display statistics
                stats = result_data.get('statistics', {})
                if stats:
                    console.print(f"\n📊 [bold]Statistics:[/bold]")
                    console.print(f"   • Average messages per contact: {stats.get('avg_messages_per_contact', 0):.1f}")
                    console.print(f"   • Average threads per contact: {stats.get('avg_threads_per_contact', 0):.1f}")
                    console.print(f"   • Average relationship strength: {stats.get('avg_relationship_strength', 0):.2f}")
                    console.print(f"   • Corporate domains: {stats.get('corporate_domains', 0)}")
                    console.print(f"   • Personal domains: {stats.get('personal_domains', 0)}")
                
                # Display sample contacts
                contacts = result_data.get('contacts', [])
                if contacts:
                    console.print(f"\n👥 [bold]Sample Contacts ({len(contacts)} total):[/bold]")
                    for i, contact in enumerate(contacts[:3]):  # Show first 3
                        console.print(f"   {i+1}. Tier: {contact.get('tier', 'unknown')}, Score: {contact.get('quality_score', 0):.2f}")
                
                return data
            else:
                console.print(f"❌ Email extraction failed: {response.status_code}")
                console.print(f"Response: {response.text}")
                return {"error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            console.print(f"❌ Email extraction error: {e}")
            return {"error": str(e)}
    
    async def test_contact_validation(self) -> Dict[str, Any]:
        """Test individual contact quality validation"""
        console.print("\n🔍 [bold blue]Testing Contact Quality Validation[/bold blue]")
        
        try:
            validation_request = {
                "integration_id": TEST_INTEGRATION_ID,
                "contact_email": TEST_CONTACT_EMAIL
            }
            
            response = await self.client.post(
                f"{API_BASE}/email-contacts/validate",
                headers=self.auth_headers,
                json=validation_request
            )
            
            if response.status_code == 200:
                data = response.json()
                console.print("✅ Contact validation completed")
                
                # Display validation results
                result_data = data.get('data', {})
                
                validation_table = Table(title=f"Contact Validation: {TEST_CONTACT_EMAIL}")
                validation_table.add_column("Property", style="cyan")
                validation_table.add_column("Value", style="green")
                
                validation_table.add_row("Found", str(result_data.get('found', False)))
                if result_data.get('found'):
                    validation_table.add_row("Message Count", str(result_data.get('message_count', 0)))
                    validation_table.add_row("Thread Count", str(result_data.get('thread_count', 0)))
                    validation_table.add_row("Two-Way Communication", str(result_data.get('has_two_way', False)))
                    validation_table.add_row("Professional", str(result_data.get('is_professional', False)))
                    validation_table.add_row("Automated", str(result_data.get('is_automated', False)))
                    validation_table.add_row("Response Rate", f"{result_data.get('response_rate', 0):.2f}")
                    validation_table.add_row("Relationship Strength", f"{result_data.get('relationship_strength', 0):.2f}")
                    validation_table.add_row("Quality Assessment", result_data.get('quality_assessment', 'unknown'))
                    validation_table.add_row("Last Contact", result_data.get('last_contact', 'unknown'))
                else:
                    validation_table.add_row("Reason", result_data.get('reason', 'Unknown'))
                
                console.print(validation_table)
                return data
            else:
                console.print(f"❌ Contact validation failed: {response.status_code}")
                return {"error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            console.print(f"❌ Contact validation error: {e}")
            return {"error": str(e)}
    
    async def test_filtering_statistics(self) -> Dict[str, Any]:
        """Test filtering statistics retrieval"""
        console.print("\n📈 [bold blue]Testing Filtering Statistics[/bold blue]")
        
        try:
            response = await self.client.get(
                f"{API_BASE}/email-contacts/stats",
                headers=self.auth_headers,
                params={"integration_id": TEST_INTEGRATION_ID}
            )
            
            if response.status_code == 200:
                data = response.json()
                console.print("✅ Statistics retrieved successfully")
                
                # Display statistics
                stats_data = data.get('data', {})
                
                stats_table = Table(title="Email Filtering Statistics")
                stats_table.add_column("Metric", style="cyan")
                stats_table.add_column("Value", style="green")
                
                stats_table.add_row("Last Run", stats_data.get('last_filtering_run', 'unknown'))
                stats_table.add_row("Emails Analyzed", str(stats_data.get('total_emails_analyzed', 0)))
                stats_table.add_row("Contacts Extracted", str(stats_data.get('contacts_extracted', 0)))
                stats_table.add_row("Contacts Filtered", str(stats_data.get('contacts_filtered', 0)))
                stats_table.add_row("Two-Way Validated", str(stats_data.get('two_way_validated', 0)))
                stats_table.add_row("Professional Contacts", str(stats_data.get('professional_contacts', 0)))
                stats_table.add_row("Automated Filtered", str(stats_data.get('automated_filtered', 0)))
                stats_table.add_row("Spam Filtered", str(stats_data.get('spam_filtered', 0)))
                stats_table.add_row("Avg Quality Score", f"{stats_data.get('avg_quality_score', 0):.2f}")
                
                console.print(stats_table)
                
                # Display top domains
                top_domains = stats_data.get('top_domains', [])
                if top_domains:
                    console.print(f"\n🏢 [bold]Top Domains:[/bold]")
                    for domain in top_domains:
                        console.print(f"   • {domain.get('domain', 'unknown')}: {domain.get('count', 0)} contacts")
                
                return data
            else:
                console.print(f"❌ Statistics retrieval failed: {response.status_code}")
                return {"error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            console.print(f"❌ Statistics error: {e}")
            return {"error": str(e)}
    
    async def test_cold_outreach_suggestions(self) -> Dict[str, Any]:
        """Test cold outreach suggestions"""
        console.print("\n🎯 [bold blue]Testing Cold Outreach Suggestions[/bold blue]")
        
        try:
            response = await self.client.get(
                f"{API_BASE}/email-contacts/suggestions/cold",
                headers=self.auth_headers,
                params={
                    "integration_id": TEST_INTEGRATION_ID,
                    "limit": 10
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                console.print("✅ Cold outreach suggestions retrieved")
                
                # Display suggestions
                suggestions_data = data.get('data', {})
                suggestions = suggestions_data.get('suggestions', [])
                
                if suggestions:
                    suggestions_table = Table(title="Cold Outreach Suggestions")
                    suggestions_table.add_column("Email", style="cyan")
                    suggestions_table.add_column("Score", style="green")
                    suggestions_table.add_column("Reason", style="yellow")
                    suggestions_table.add_column("Action", style="magenta")
                    
                    for suggestion in suggestions:
                        suggestions_table.add_row(
                            suggestion.get('email', 'unknown'),
                            str(suggestion.get('score', 0)),
                            suggestion.get('reason', 'No reason provided'),
                            suggestion.get('suggested_action', 'No action suggested')
                        )
                    
                    console.print(suggestions_table)
                else:
                    console.print("📭 No cold outreach suggestions available")
                
                console.print(f"\n📊 Total suggestions: {suggestions_data.get('total_count', 0)}")
                console.print(f"Suggestion type: {suggestions_data.get('suggestion_type', 'unknown')}")
                
                return data
            else:
                console.print(f"❌ Suggestions retrieval failed: {response.status_code}")
                return {"error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            console.print(f"❌ Suggestions error: {e}")
            return {"error": str(e)}


async def run_comprehensive_test():
    """Run comprehensive test of email contact filtering service"""
    console.print(Panel.fit(
        "[bold blue]Email Contact Filtering Service Test Suite[/bold blue]\n"
        "[yellow]Task 2.5.4: Email-based contact filtering with two-way validation[/yellow]\n"
        "[green]Testing metadata-only analysis for privacy and performance[/green]",
        title="🧪 Test Suite"
    ))
    
    async with EmailContactFilteringTester() as tester:
        results = {}
        
        # Test 1: Service Health
        results['health'] = await tester.test_service_health()
        
        # Test 2: Email Contact Extraction
        results['extraction'] = await tester.test_email_contact_extraction()
        
        # Test 3: Contact Validation
        results['validation'] = await tester.test_contact_validation()
        
        # Test 4: Filtering Statistics
        results['statistics'] = await tester.test_filtering_statistics()
        
        # Test 5: Cold Outreach Suggestions
        results['suggestions'] = await tester.test_cold_outreach_suggestions()
        
        # Summary
        console.print("\n" + "="*60)
        console.print("[bold green]📋 Test Summary[/bold green]")
        
        success_count = sum(1 for result in results.values() if 'error' not in result)
        total_tests = len(results)
        
        console.print(f"✅ Successful tests: {success_count}/{total_tests}")
        
        if success_count == total_tests:
            console.print("[bold green]🎉 All tests passed! Email contact filtering service is working correctly.[/bold green]")
        else:
            console.print("[bold yellow]⚠️  Some tests failed. Check the output above for details.[/bold yellow]")
        
        # Display key features demonstrated
        console.print(f"\n[bold blue]🚀 Key Features Demonstrated:[/bold blue]")
        console.print("   • Metadata-only email analysis (privacy-friendly)")
        console.print("   • Two-way communication validation")
        console.print("   • Professional contact scoring")
        console.print("   • Spam and automation detection")
        console.print("   • Relationship strength calculation")
        console.print("   • Contact quality assessment")
        console.print("   • Cold outreach suggestions")
        
        return results


if __name__ == "__main__":
    try:
        results = asyncio.run(run_comprehensive_test())
        
        # Save results to file
        with open("email_contact_filtering_test_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        console.print(f"\n💾 Test results saved to: email_contact_filtering_test_results.json")
        
    except KeyboardInterrupt:
        console.print("\n⚠️ Test interrupted by user")
    except Exception as e:
        console.print(f"\n❌ Test failed with error: {e}")
        logger.exception("Test execution failed") 