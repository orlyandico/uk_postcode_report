# Standard library imports
import os
import re
import sys
import tempfile
import time
import warnings
from datetime import datetime, timedelta
import random

# Third-party imports
import boto3
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from markitdown import MarkItDown
import requests

MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"
#MODEL_ID = "amazon.nova-pro-v1:0"
AWS_REGION = "us-west-2"
AWS_PROFILE = "us-west-2-profile"

# Suppress the specific datetime warning from botocore
warnings.filterwarnings('ignore', category=DeprecationWarning,
                       message='datetime.datetime.utcnow.*')



def html_to_plain_text(html_string):
    """
    Convert HTML string to plain text, removing links and image references.

    Args:
        html_string (str): String containing HTML content

    Returns:
        str: Plain text with HTML tags and media references removed
    """
    # Create BeautifulSoup object with 'html.parser'
    soup = BeautifulSoup(html_string, 'html.parser')

    # Remove all script and style elements
    for script in soup(["script", "style"]):
        script.decompose()

    # Remove all images
    for img in soup.find_all('img'):
        img.decompose()

    # Replace links with their text content
    for a in soup.find_all('a'):
        a.replace_with(a.text)

    # Get text and normalize whitespace
    text = soup.get_text()
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = ' '.join(chunk for chunk in chunks if chunk)

    return text.strip()


def cleanup_temp_file(filename):
    try:
        os.unlink(filename)
    except OSError as e:
        print(f"Warning: Could not delete temporary file {filename}: {e}")
    finally:
        if os.path.exists(filename):
            print(f"Warning: Temporary file {filename} still exists")

def get_streetcheck_data(postcode, data_type="postcode", data_date=None):
    """
    Get data from StreetCheck for a given postcode
    Args:
        postcode: UK postcode
        data_type: Either "postcode" or "houseprices" for different page types
    Returns:
        str: HTML content of the page
    """
    # Clean the postcode - remove spaces and convert to uppercase
    postcode = postcode.strip().replace(" ", "").lower()

    # Base URL with path based on data type
    base_url = "https://www.streetcheck.co.uk/"
    if data_type == "houseprices":
        base_url += "houseprices/"
    elif data_type == "postcode":
        base_url += "postcode/"
    elif data_type == "crime":
        base_url += f"crime/"
    else:
        raise ValueError("data_type must be either 'postcode', 'houseprices', or 'crime'")

    # Common user agents to rotate between
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0"
    ]

    # Headers to simulate a real browser
    headers = {
        "User-Agent": random.choice(user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1"
    }

    try:
        # Add a small random delay to simulate human behavior
        time.sleep(random.uniform(1, 3))

        # Make the request
        response = requests.get(
            base_url + postcode + (f"/{data_date}" if data_date else ""),
            headers=headers,
            timeout=10,
            verify=True
        )

        # Raise an exception for bad status codes
        response.raise_for_status()
        print(f"Fetched {data_type} data for postcode {postcode}" + (f"/{data_date}" if data_date else ""))

        # Return the HTML content
        return html_to_plain_text(response.text)

    except requests.RequestException as e:
        print(f"Error fetching {data_type} data for postcode {postcode}: {str(e)}")
        return None




def initialize_bedrock_client(aws_profile: str) -> boto3.client:
    session = boto3.Session(profile_name=aws_profile)
    return session.client('bedrock-runtime', AWS_REGION)


def get_content_summary(bedrock_runtime: boto3.client, text_content: str) -> str:
    prompt = '''
You are a data analyst specializing in demographic and housing statistics. Your task is to create a concise, factual summary of a given area based on the provided information. Here's the content you need to analyze:

<area_description>
{text}
</area_description>

Please follow these steps to create your summary:

1. Carefully read through the provided content.

2. In your analysis, identify and extract key information about:
    - The area's general characteristics
    - Available amenities, including broadband speed
    - Demographics
    - Crime (note that three months worth of crime data is here, break down by month); make sure to report the total count by month
    - Notable statistics

3. Pay special attention to the following categories and their associated percentages:
    - Housing types
    - Housing tenure
    - Housing prices
    - Household deprivation
    - Economic activity
    - Ethnic groups

4. Specifically highlight:
    - The percentage of social rented housing
    - The percentage of households with deprivation across all dimensions
    - The level of unemployment
    - The total count of crimes reported by category

5. Present your work as a crisp summary of all the data you have gathered. Make sure to:
    - Quote specific statistics and percentages from the text for each category
    - Calculate the total percentage for each category
    - If percentages within a category exceed 100%, show your work in adjusting the figures proportionally to ensure they sum to 100%
    - Organize the extracted information into clear categories (e.g., Housing, Demographics, Economy)
    - List any other key facts and statistics you've identified; make sure to note the level of deprivation in total, and in more than one dimension

Remember to maintain a professional and objective tone throughout your data extraction and summary.

Here is an example of the report that you must write:

<example_report>
### Summary of High Street, Kimpton, Hitchin, SG4 8PT

#### General Characteristics
High Street is located in Kimpton, Hitchin, within the North Hertfordshire Local Authority. It falls within the Codicote & Kimpton ward/electoral division and the Hitchin constituency. The area is classified as a Small Town or Fringe Area.

#### Amenities
- **Broadband:** Ultrafast broadband (300Mbps+) is available
- **Nearest Services:**
  - Railway Station: Harpenden (3.4 miles)
  - Primary School: Kimpton Primary School (130 yards)
  - Secondary School: Katherine Warington School (2.6 miles)
  - GP Surgery: Whitwell Surgery (1.9 miles)

#### Demographics
- **Population:** 327 residents
- **Gender:** 47% male (153), 53% female (174)

- **Ethnic Groups:**
  - White: 93.6% (306)
  - Mixed Ethnicity: 5.8% (19)
  - Indian: 0.3% (1)
  - Other Asian: 0.3% (1)

#### Economy
- **Economic Activity:**
  - Full-Time Employee: 28.1% (72)
  - Part-Time Employee: 11.7% (30)
  - Self Employed: 19.1% (49)
  - Unemployed: 3.1% (8)
  - Full-Time Student: 5.5% (14)
  - Retired: 25.8% (66)
  - Other: 6.7% (17)

#### Housing
- **Housing Types:** (Total 127)
  - Detached: 35.4% (45)
  - Semi-Detached: 29.1% (37)
  - Terraced: 33.9% (43)
  - Flats: 1.6% (2)

- **Housing Tenure:** (Total 127)
  - Owned Outright: 43.3% (55)
  - Owned with Mortgage: 40.9% (52)
  - Social Rented: 7.1% (9)
  - Private Rented: 8.7% (11)

- **Household Deprivation:**
  - Not Deprived: 68.5% (87)
  - Deprived in One Dimension: 26.8% (34)
  - Deprived in Two Dimensions: 3.9% (5)
  - Deprived in Three Dimensions: 0.8% (1)
  - Deprived in Four Dimensions: 0%

#### Crime Statistics
- **October 2024:** 3 total crimes (1 Anti-social behaviour, 1 Vehicle crime, 1 Violence and sexual offences)
- **November 2024:** 3 total crimes (1 Anti-social behaviour, 1 Other theft, 1 Violence and sexual offences)
- **December 2024:** 9 total crimes (1 Anti-social behaviour, 2 Vehicle crime, 5 Violence and sexual offences, 1 Other crime)

#### Notable Statistics
- **Social Rented Housing:** 7.1% (9/127)
- **Households with Deprivation in One or More Dimensions:** 31.5% (40/127)
- **Unemployment Rate:** 3.1% (8/256)
- **Recent House Sale:** £777,500 (June 2021)
</example_report>

    '''.format(text=text_content)

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "text": prompt
                }
            ]
        }
    ]

    inference_config = {
        "temperature": 0.0,
        "maxTokens": 2048,
        "topP": 1,
    }

    try:
        response = bedrock_runtime.converse(
            modelId=MODEL_ID,
            messages=messages,
            inferenceConfig=inference_config
        )
        return response['output']['message']['content'][0]['text']
    except Exception as err:
        print(f"Error getting summary: {err.response['Error']['Message']}")
        return None


# get trailing 3 months of crime data
def get_three_months_data(postcode):
    results = ""
    current_date = datetime.now()
    four_months_ago = current_date - relativedelta(months=4)

    # Iterate through the last 3 months (2 months ago, 1 month ago, and current month)
    for i in range(3):
        # Calculate the date for this iteration
        target_date = four_months_ago + relativedelta(months=i)
        formatted_date = target_date.strftime('%Y/%m')

        # Get data for this month
        postcode_html = get_streetcheck_data(postcode, "crime", formatted_date)

        if postcode_html:
            results += f"Data for {formatted_date}:\n"
            results += postcode_html + "\n\n"  # Add double newline for separation

    return results


def main():
    # Set default postcode for Knightsbridge/Kensington area
    default_postcode = "SW72BU"  # One of London's most expensive areas

    # Get postcode from command line or use default
    if len(sys.argv) > 1:
        postcode = sys.argv[1].strip().replace(" ", "").lower()
        if not postcode:  # If postcode is empty after cleaning
            postcode = default_postcode
    else:
        postcode = default_postcode

    # Create filename
    output_filename = f"postcode_summary_{postcode}.md"

    # Exit if file already exists
    if os.path.exists(output_filename):
        print(f"Error: {output_filename} already exists.")
        sys.exit(1)

    # Get both types of HTML content
    postcode_html = get_streetcheck_data(postcode, "postcode")
    prices_html = get_streetcheck_data(postcode, "houseprices")
    results = ""

    # Process postcode data if available
    if postcode_html:
        results += postcode_html + "\n\n"  # Add double newline for separation
    if prices_html:
        results += prices_html

    # get the crime data
    crime_text = get_three_months_data(postcode)
    results += crime_text

    # Initialize Bedrock client
    bedrock_runtime = initialize_bedrock_client(AWS_PROFILE)

    # Get summary
    summary = get_content_summary(bedrock_runtime, results)

    # Calculate token estimates and costs
    input_tokens = len(results) // 4
    output_tokens = len(summary) // 4
    input_price = input_tokens // 1000 * 0.0008
    output_price = output_tokens // 1000 * 0.0032

    print(f'''
## Token Usage Statistics
- Input tokens (approx): {input_tokens:,} (${input_price:.2f})
- Output tokens (approx): {output_tokens:,} (${output_price:.2f})
- Total inference cost: ${(input_price + output_price):.2f}
''')
    # Prepare the complete output text
    output_text = f"""# Postcode Summary for {postcode}

{summary}
"""

    # Write to file
    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(output_text)
        print(f"Summary written to: {output_filename}")
    except Exception as e:
        print(f"Error writing to file: {e}")

if __name__ == "__main__":
    main()
