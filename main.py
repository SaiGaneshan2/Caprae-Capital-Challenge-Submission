import os
import requests
import csv
import time
import json
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from groq import Groq
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
import logging
from datetime import datetime
from typing import List, Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('lead_generation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class EnhancedLeadGenerationTool:
    def __init__(self):
        # API Keys
        self.GROQ_API_KEY = "put your api here"
        self.SERPER_API_KEY = "put your api here"
        
        # Initialize Groq client
        self.groq_client = Groq(api_key=self.GROQ_API_KEY)
        
        # Setup Chrome options for Selenium
        self.chrome_options = Options()
        self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--window-size=1920x1080")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        self.chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)
        self.chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Configuration
        self.max_retries = 3
        self.relevance_threshold = 0.6  # 60% of results must be relevant
        
        logger.info("Enhanced Lead Generation Tool initialized")
    
    def search_companies(self, query: str, num_results: int = 10) -> List[Dict]:
        """Search for companies using Serper API with improved error handling"""
        logger.info(f"🔍 Searching for: {query}")
        
        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": self.SERPER_API_KEY,
            "Content-Type": "application/json"
        }
        data = {
            "q": query,
            "num": num_results * 2,  # Get more results to filter for relevance
            "type": "search"
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            results = response.json().get("organic", [])
            
            logger.info(f"✅ Found {len(results)} search results")
            return results
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Search API request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Unexpected search error: {e}")
            return []
    
    def evaluate_relevance(self, search_results: List[Dict], original_query: str) -> List[Dict]:
        """Evaluate relevance of search results using Groq LLM"""
        logger.info("🤖 Evaluating relevance of search results...")
        
        # Prepare results summary for LLM
        results_summary = []
        for i, result in enumerate(search_results):
            results_summary.append({
                "index": i,
                "title": result.get("title", ""),
                "snippet": result.get("snippet", ""),
                "link": result.get("link", "")
            })
        
        prompt = f"""
        Analyze the following search results and determine their relevance to the search query: "{original_query}"
        
        For each result, evaluate if it matches what the user is looking for based on:
        1. Company type/industry alignment
        2. Geographic relevance (if specified)
        3. Business model relevance
        4. Overall match to search intent
        
        Return a JSON array where each object has:
        - index: The result index
        - is_relevant: true/false
        - confidence: 0.0-1.0 (how confident you are)
        - reason: Brief explanation of relevance decision
        
        Search Results:
        {json.dumps(results_summary, indent=2)}
        
        Return only valid JSON format.
        """
        
        try:
            chat_completion = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama3-8b-8192",
                temperature=0.1,
                max_tokens=2000
            )
            
            response_text = chat_completion.choices[0].message.content
            
            # Extract JSON from response
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1
            json_str = response_text[json_start:json_end]
            
            relevance_data = json.loads(json_str)
            
            # Add relevance info to original results
            enhanced_results = []
            for result in search_results:
                enhanced_result = result.copy()
                
                # Find matching relevance data
                relevance_info = None
                for rel_data in relevance_data:
                    if rel_data.get("index") == search_results.index(result):
                        relevance_info = rel_data
                        break
                
                if relevance_info:
                    enhanced_result["is_relevant"] = relevance_info.get("is_relevant", False)
                    enhanced_result["relevance_confidence"] = relevance_info.get("confidence", 0.0)
                    enhanced_result["relevance_reason"] = relevance_info.get("reason", "No reason provided")
                else:
                    enhanced_result["is_relevant"] = False
                    enhanced_result["relevance_confidence"] = 0.0
                    enhanced_result["relevance_reason"] = "Could not evaluate relevance"
                
                enhanced_results.append(enhanced_result)
            
            # Calculate relevance statistics
            relevant_count = sum(1 for r in enhanced_results if r.get("is_relevant", False))
            total_count = len(enhanced_results)
            relevance_rate = relevant_count / total_count if total_count > 0 else 0
            
            logger.info(f"✅ Relevance evaluation complete: {relevant_count}/{total_count} relevant ({relevance_rate:.1%})")
            
            return enhanced_results
            
        except Exception as e:
            logger.error(f"❌ Relevance evaluation failed: {e}")
            # Return original results with default relevance
            return [{**result, "is_relevant": True, "relevance_confidence": 0.5, "relevance_reason": "Could not evaluate"} 
                    for result in search_results]
    
    def refine_search_query(self, original_query: str, failed_results: List[Dict]) -> str:
        """Generate a refined search query based on failed results"""
        logger.info("🔍 Refining search query based on irrelevant results...")
        
        failed_titles = [result.get("title", "") for result in failed_results if not result.get("is_relevant", True)]
        
        prompt = f"""
        The original search query "{original_query}" returned mostly irrelevant results.
        
        Irrelevant results included:
        {json.dumps(failed_titles, indent=2)}
        
        Generate a more specific and targeted search query that would return better results.
        Consider:
        1. Adding more specific keywords
        2. Including location modifiers if needed
        3. Adding industry-specific terms
        4. Excluding common irrelevant terms
        
        Return only the refined search query as plain text, no explanation.
        """
        
        try:
            chat_completion = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama3-8b-8192",
                temperature=0.3,
                max_tokens=100
            )
            
            refined_query = chat_completion.choices[0].message.content.strip()
            logger.info(f"✅ Refined query: {refined_query}")
            return refined_query
            
        except Exception as e:
            logger.error(f"❌ Query refinement failed: {e}")
            return original_query + " company contact information"
    
    def clean_html_content(self, html_content: str) -> str:
        """Clean and extract meaningful text from HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            element.decompose()
        
        # Get text content
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        # Limit text length for LLM
        return text[:8000]
    
    def scrape_website(self, url: str) -> Optional[str]:
        """Scrape website content using Selenium with better error handling"""
        logger.info(f"🌐 Scraping: {url}")
        
        driver = None
        try:
            driver = webdriver.Chrome(options=self.chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Set page load timeout
            driver.set_page_load_timeout(30)
            
            driver.get(url)
            time.sleep(5)  # Wait for JS to load
            
            html_content = driver.page_source
            cleaned_content = self.clean_html_content(html_content)
            
            logger.info(f"✅ Scraped {len(cleaned_content)} characters from {url}")
            return cleaned_content
            
        except WebDriverException as e:
            logger.error(f"❌ WebDriver error for {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error scraping {url}: {e}")
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    
    def extract_lead_info(self, content: str, website_url: str) -> Dict:
        """Extract lead information using Groq LLM with enhanced prompting"""
        logger.info("🤖 Extracting lead information with AI...")
        
        prompt = f"""
        Analyze the following website content and extract comprehensive lead generation information.
        
        Return information in JSON format with these fields:
        - company_name: The main company name
        - email: Email addresses (comma-separated if multiple, prioritize contact/sales emails)
        - phone: Phone numbers (comma-separated if multiple, format: +1-XXX-XXX-XXXX)
        - linkedin: LinkedIn company page or key personnel URLs
        - website: The website URL
        - industry: Specific industry/business type
        - description: Compelling company description (50-100 words)
        - address: Full physical address
        - contact_person: Names and titles of key contacts
        - services: Main services/products (comma-separated)
        - company_size: Employee count estimate or range
        - founded_year: Year company was founded
        - revenue_range: Estimated revenue range if available
        - technologies: Key technologies used (if tech company)
        - social_media: Other social media profiles (Twitter, Facebook, etc.)
        
        Website URL: {website_url}
        
        Content:
        {content}
        
        Return only valid JSON. Use "N/A" for missing information.
        """
        
        try:
            chat_completion = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama3-8b-8192",
                temperature=0.1,
                max_tokens=1500
            )
            
            response_text = chat_completion.choices[0].message.content
            
            # Extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            json_str = response_text[json_start:json_end]
            
            lead_data = json.loads(json_str)
            logger.info("✅ Successfully extracted lead information")
            return lead_data
            
        except json.JSONDecodeError:
            logger.error("❌ Failed to parse JSON from LLM response")
            return self._create_fallback_lead_data(website_url, content)
        except Exception as e:
            logger.error(f"❌ LLM extraction failed: {e}")
            return self._create_fallback_lead_data(website_url, content)
    
    def _create_fallback_lead_data(self, website_url: str, content: str) -> Dict:
        """Create fallback lead data with enhanced regex extraction"""
        # Enhanced regex patterns
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        phone_pattern = r'(\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})'
        linkedin_pattern = r'https?://(?:www\.)?linkedin\.com/(?:company|in)/[A-Za-z0-9_-]+'
        
        emails = re.findall(email_pattern, content)
        phones = re.findall(phone_pattern, content)
        linkedin_urls = re.findall(linkedin_pattern, content)
        
        # Extract company name from domain
        domain = urlparse(website_url).netloc.replace('www.', '')
        company_name = domain.split('.')[0].title()
        
        return {
            "company_name": company_name,
            "email": ', '.join(emails[:3]) if emails else "N/A",
            "phone": ', '.join(['-'.join(phone[1:]) for phone in phones[:2]]) if phones else "N/A",
            "linkedin": ', '.join(linkedin_urls[:2]) if linkedin_urls else "N/A",
            "website": website_url,
            "industry": "N/A",
            "description": content[:200] + "..." if len(content) > 200 else content,
            "address": "N/A",
            "contact_person": "N/A",
            "services": "N/A",
            "company_size": "N/A",
            "founded_year": "N/A",
            "revenue_range": "N/A",
            "technologies": "N/A",
            "social_media": "N/A"
        }
    
    def generate_leads_dataframe(self, search_query: str, num_results: int = 5) -> pd.DataFrame:
        """Main function to generate leads and return as pandas DataFrame"""
        logger.info("🚀 Starting Enhanced AI-Powered Lead Generation...")
        logger.info(f"Query: {search_query}")
        logger.info(f"Target Results: {num_results}")
        logger.info("-" * 50)
        
        current_query = search_query
        retry_count = 0
        
        while retry_count < self.max_retries:
            logger.info(f"Attempt {retry_count + 1}/{self.max_retries}")
            
            # Step 1: Search for companies
            search_results = self.search_companies(current_query, num_results * 2)
            
            if not search_results:
                logger.error("❌ No search results found")
                return pd.DataFrame()
            
            # Step 2: Evaluate relevance
            evaluated_results = self.evaluate_relevance(search_results, search_query)
            
            # Step 3: Check if we have enough relevant results
            relevant_results = [r for r in evaluated_results if r.get("is_relevant", False)]
            relevance_rate = len(relevant_results) / len(evaluated_results) if evaluated_results else 0
            
            if relevance_rate >= self.relevance_threshold:
                logger.info(f"✅ Sufficient relevance rate: {relevance_rate:.1%}")
                break
            else:
                logger.warning(f"⚠️ Low relevance rate: {relevance_rate:.1%}")
                if retry_count < self.max_retries - 1:
                    current_query = self.refine_search_query(search_query, evaluated_results)
                    retry_count += 1
                    continue
                else:
                    logger.warning("Max retries reached, proceeding with current results")
                    break
        
        # Step 4: Process the best results
        final_results = relevant_results[:num_results] if relevant_results else evaluated_results[:num_results]
        
        if not final_results:
            logger.error("❌ No results to process")
            return pd.DataFrame()
        
        # Step 5: Scrape and extract leads
        all_leads = []
        
        for i, result in enumerate(final_results, 1):
            logger.info(f"\n[{i}/{len(final_results)}] Processing: {result['title']}")
            
            # Scrape website content
            content = self.scrape_website(result['link'])
            
            if content:
                # Extract lead information
                lead_data = self.extract_lead_info(content, result['link'])
                
                # Add metadata
                lead_data['search_title'] = result['title']
                lead_data['search_snippet'] = result.get('snippet', '')
                lead_data['is_relevant'] = result.get('is_relevant', False)
                lead_data['relevance_confidence'] = result.get('relevance_confidence', 0.0)
                lead_data['relevance_reason'] = result.get('relevance_reason', '')
                lead_data['scraped_at'] = datetime.now().isoformat()
                
                all_leads.append(lead_data)
                
                logger.info(f"✅ Lead extracted: {lead_data.get('company_name', 'Unknown')}")
            else:
                logger.warning("❌ Failed to scrape content")
            
            # Respectful delay
            time.sleep(2)
        
        # Step 6: Create DataFrame
        if all_leads:
            df = pd.DataFrame(all_leads)
            
            # Reorder columns for better readability
            column_order = [
                "company_name", "email", "phone", "linkedin", "website", "industry", 
                "description", "address", "contact_person", "services", "company_size",
                "founded_year", "revenue_range", "technologies", "social_media",
                "is_relevant", "relevance_confidence", "relevance_reason", 
                "search_title", "search_snippet", "scraped_at"
            ]
            
            # Reorder columns if they exist
            available_columns = [col for col in column_order if col in df.columns]
            df = df[available_columns]
            
            logger.info(f"\n🎉 Lead generation complete! {len(all_leads)} leads generated")
            
            # Display summary
            logger.info("\n📊 SUMMARY:")
            relevant_leads = df[df['is_relevant'] == True] if 'is_relevant' in df.columns else df
            logger.info(f"Relevant leads: {len(relevant_leads)}/{len(df)}")
            
            return df
        else:
            logger.error("❌ No leads were successfully generated")
            return pd.DataFrame()


# Main function that can be called directly
def generate_leads(search_query: str, num_results: int = 5) -> pd.DataFrame:
    """
    Generate leads based on search query and return as pandas DataFrame
    
    Args:
        search_query (str): The search query for finding companies
        num_results (int): Number of results to process (default: 5)
    
    Returns:
        pd.DataFrame: DataFrame containing lead information
    """
    tool = EnhancedLeadGenerationTool()
    return tool.generate_leads_dataframe(search_query, num_results)


# Example usage
if __name__ == "__main__":
    # Example usage of the function
    search_query = "SaaS companies in San Francisco"
    num_results = 5
    
    # Generate leads and get DataFrame
    leads_df = generate_leads(search_query, num_results)
    
    # Display results
    if not leads_df.empty:
        print("\n✅ Leads generated successfully!")
        print(f"Shape: {leads_df.shape}")
        print("\nFirst few rows:")
        print(leads_df.head())
        
        # Optionally save to CSV
        leads_df.to_csv('leads_output.csv', index=False)
        print("\n💾 Results also saved to 'leads_output.csv'")
    else:
        print("❌ No leads were generated")
